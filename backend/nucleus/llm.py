"""LLM access, behind one interface.

build.md specifies the Anthropic API. This build uses OpenAI at the user's
request, so the provider is a config line rather than a code path baked through
the agents: every agent calls `client.json(...)` and never imports a vendor SDK.

What this module is responsible for beyond making the call:

  throttling   a client-side token bucket plus a concurrency cap, so a run
               cannot burst against the account's limits
  retries      exponential backoff with jitter on 429 and 5xx, honouring
               Retry-After when the API sends it
  timeouts     no call hangs a demo indefinitely
  accounting   every call's token usage is recorded, so a run can report what
               it actually cost

Temperature is pinned to 0 in config for run-to-run stability -- build.md flags
"numbers move between runs" as a top failure mode.
"""
from __future__ import annotations

import json
import os
import random
import re
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Protocol, TypeVar

from .config import Config, load as load_config


class LLMError(RuntimeError):
    pass


class MissingCredentials(LLMError):
    """Raised with the exact command needed to fix it."""


class LLMClient(Protocol):
    def json(self, system: str, user: str) -> Any:
        """Return parsed JSON from the model."""


# --------------------------------------------------------------------- usage
@dataclass
class Usage:
    """What a run actually spent. Cheap to keep, and it makes cost visible."""
    calls: int = 0
    failed: int = 0
    retries: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(self, *, prompt: int, completion: int, seconds: float,
               retries: int = 0) -> None:
        with self._lock:
            self.calls += 1
            self.retries += retries
            self.prompt_tokens += prompt
            self.completion_tokens += completion
            self.seconds += seconds

    def record_failure(self) -> None:
        with self._lock:
            self.failed += 1

    def cost(self, cfg: Config) -> float:
        return (self.prompt_tokens / 1e6 * cfg.llm.price_per_1m_input
                + self.completion_tokens / 1e6 * cfg.llm.price_per_1m_output)

    def summary(self, cfg: Config) -> str:
        bits = [
            f"{self.calls} calls",
            f"{self.prompt_tokens:,} in / {self.completion_tokens:,} out tokens",
            f"{self.seconds:.1f}s",
        ]
        if self.retries:
            bits.append(f"{self.retries} retries")
        if self.failed:
            bits.append(f"{self.failed} failed")
        if cfg.llm.price_per_1m_input or cfg.llm.price_per_1m_output:
            bits.append(f"~${self.cost(cfg):.4f}")
        return "  ".join(bits)


USAGE = Usage()


# ---------------------------------------------------------------- throttling
class RateLimiter:
    """Requests-per-minute token bucket plus a hard concurrency cap.

    Deliberately simple and client-side. It is not trying to mirror the
    server's accounting -- it exists so a burst of parallel calls degrades into
    a queue instead of a wall of 429s.
    """

    def __init__(self, requests_per_minute: int, max_concurrency: int):
        self.rpm = max(1, requests_per_minute)
        self._times: deque[float] = deque()
        self._lock = threading.Lock()
        self._slots = threading.Semaphore(max(1, max_concurrency))

    def __enter__(self):
        self._slots.acquire()
        self._wait_for_slot()
        return self

    def __exit__(self, *exc):
        self._slots.release()
        return False

    def _wait_for_slot(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                while self._times and now - self._times[0] >= 60.0:
                    self._times.popleft()
                if len(self._times) < self.rpm:
                    self._times.append(now)
                    return
                sleep_for = 60.0 - (now - self._times[0])
            time.sleep(max(0.01, sleep_for))


# ------------------------------------------------------------------- parsing
def _extract_json(text: str) -> Any:
    """Parse a JSON payload, tolerating fenced code blocks."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"[\{\[].*[\}\]]", text, re.DOTALL)
        if not m:
            raise LLMError(f"model did not return JSON:\n{text[:500]}")
        return json.loads(m.group(0))


def _retry_after(exc: Exception) -> float | None:
    """Honour the API's own Retry-After when it tells us how long to wait."""
    headers = getattr(getattr(exc, "response", None), "headers", None)
    if not headers:
        return None
    for key in ("retry-after-ms", "retry-after"):
        raw = headers.get(key)
        if raw:
            try:
                v = float(raw)
                return v / 1000.0 if key.endswith("ms") else v
            except ValueError:
                pass
    return None


# ------------------------------------------------------------------- clients
class OpenAIClient:
    #: transient conditions worth another attempt
    RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}

    def __init__(self, cfg: Config):
        self.cfg = cfg
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise MissingCredentials(
                "OPENAI_API_KEY is not set.\n"
                "  Put it in a .env file at the repo root:\n"
                '      OPENAI_API_KEY=sk-...\n'
                "  (.env is gitignored and loaded automatically), or export it\n"
                '  in the shell:  setx OPENAI_API_KEY "sk-..."  then restart.'
            )
        try:
            from openai import OpenAI
        except ImportError as e:  # pragma: no cover
            raise LLMError("the `openai` package is not installed") from e
        self._client = OpenAI(api_key=key, timeout=cfg.llm.timeout_seconds,
                              max_retries=0)  # retries handled here, with backoff
        self._limiter = RateLimiter(cfg.llm.requests_per_minute,
                                    cfg.llm.max_concurrency)

    def json(self, system: str, user: str) -> Any:
        attempt, retries = 0, 0
        started = time.monotonic()

        while True:
            try:
                with self._limiter:
                    resp = self._create(system, user)
                usage = getattr(resp, "usage", None)
                USAGE.record(
                    prompt=getattr(usage, "prompt_tokens", 0) or 0,
                    completion=getattr(usage, "completion_tokens", 0) or 0,
                    seconds=time.monotonic() - started,
                    retries=retries,
                )
                choice = resp.choices[0]
                # A truncated response is not malformed JSON, and reporting it
                # as a parse error sends you looking in the wrong place.
                if getattr(choice, "finish_reason", None) == "length":
                    USAGE.record_failure()
                    raise LLMError(
                        f"Response hit the {self.cfg.llm.max_output_tokens}-token "
                        f"output cap and was cut off mid-JSON. Raise "
                        f"llm.max_output_tokens in config.yaml, or ask the agent "
                        f"for fewer items per call.")
                return _extract_json(choice.message.content or "")

            except Exception as e:
                status = getattr(e, "status_code", None)
                transient = (
                    status in self.RETRY_STATUS
                    or isinstance(e, (TimeoutError, ConnectionError))
                    or "timeout" in type(e).__name__.lower()
                    or "connection" in type(e).__name__.lower()
                )
                attempt += 1
                if not transient or attempt > self.cfg.llm.max_retries:
                    USAGE.record_failure()
                    raise self._explain(e, status, attempt) from e

                retries += 1
                delay = _retry_after(e) or self._backoff(attempt)
                time.sleep(delay)

    def _create(self, system: str, user: str):
        kwargs: dict[str, Any] = dict(
            model=self.cfg.llm.model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            max_tokens=self.cfg.llm.max_output_tokens,
        )
        try:
            return self._client.chat.completions.create(
                temperature=self.cfg.llm.temperature, **kwargs)
        except Exception as e:
            msg = str(e).lower()
            # Reasoning models reject an explicit temperature, and some reject
            # max_tokens in favour of max_completion_tokens. Adapt rather than
            # fail -- but only for those specific complaints.
            if "temperature" in msg:
                return self._client.chat.completions.create(**kwargs)
            if "max_tokens" in msg and "max_completion_tokens" in msg:
                kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
                return self._client.chat.completions.create(**kwargs)
            raise

    def _backoff(self, attempt: int) -> float:
        """Exponential, capped, with jitter so parallel workers don't sync up."""
        raw = self.cfg.llm.retry_base_seconds * (2 ** (attempt - 1))
        return min(raw, self.cfg.llm.retry_max_seconds) * (0.5 + random.random())

    def _explain(self, e: Exception, status: int | None, attempt: int) -> LLMError:
        if status == 401:
            return LLMError(
                "OpenAI rejected the API key (401). Check OPENAI_API_KEY in .env.")
        if status == 429:
            return LLMError(
                f"Rate limited after {attempt} attempts. Lower "
                f"llm.max_concurrency or llm.requests_per_minute in config.yaml, "
                f"or wait for the quota window to reset.\n  {e}")
        if status == 404:
            return LLMError(
                f"Model {self.cfg.llm.model!r} is not available to this key (404). "
                f"Pick one the key can reach and update llm.model.\n  {e}")
        if status == 403:
            return LLMError(
                f"Access to {self.cfg.llm.model!r} is forbidden for this "
                f"organisation (403) -- some models need org verification.\n  {e}")
        return LLMError(f"OpenAI call failed ({status or type(e).__name__}): {e}")


class AnthropicClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise MissingCredentials(
                "ANTHROPIC_API_KEY is not set.\n"
                "  Add it to .env, or export it in the shell."
            )
        try:
            import anthropic
        except ImportError as e:  # pragma: no cover
            raise LLMError("the `anthropic` package is not installed") from e
        self._client = anthropic.Anthropic(api_key=key,
                                           timeout=cfg.llm.timeout_seconds)
        self._limiter = RateLimiter(cfg.llm.requests_per_minute,
                                    cfg.llm.max_concurrency)

    def json(self, system: str, user: str) -> Any:
        started = time.monotonic()
        with self._limiter:
            resp = self._client.messages.create(
                model=self.cfg.llm.model,
                max_tokens=self.cfg.llm.max_output_tokens,
                temperature=self.cfg.llm.temperature,
                system=system + "\n\nRespond with JSON only.",
                messages=[{"role": "user", "content": user}],
            )
        u = getattr(resp, "usage", None)
        USAGE.record(prompt=getattr(u, "input_tokens", 0) or 0,
                     completion=getattr(u, "output_tokens", 0) or 0,
                     seconds=time.monotonic() - started)
        return _extract_json("".join(
            b.text for b in resp.content if getattr(b, "type", "") == "text"))


class OfflineClient:
    """Explicitly unavailable rather than silently degraded."""

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def json(self, system: str, user: str) -> Any:
        raise MissingCredentials(
            "llm.provider is 'offline', so no model is available.\n"
            "  Set a key and switch config.yaml llm.provider to 'openai'."
        )


_PROVIDERS = {
    "openai": OpenAIClient,
    "anthropic": AnthropicClient,
    "offline": OfflineClient,
}


def get_client(cfg: Config | None = None) -> LLMClient:
    cfg = cfg or load_config()
    try:
        factory = _PROVIDERS[cfg.llm.provider]
    except KeyError:
        raise LLMError(
            f"unknown llm.provider {cfg.llm.provider!r}; "
            f"expected one of {sorted(_PROVIDERS)}"
        ) from None
    return factory(cfg)


# ---------------------------------------------------------------- concurrency
T = TypeVar("T")
R = TypeVar("R")


def map_parallel(fn: Callable[[T], R], items: Iterable[T],
                 workers: int, progress: Callable[[int, int], None] | None = None
                 ) -> list[R]:
    """Run `fn` over `items` with bounded parallelism, preserving input order.

    The report classifies one product per call; doing those serially is the
    slowest part of a run. The client's own rate limiter still gates the actual
    requests, so raising workers cannot outrun the throttle.
    """
    items = list(items)
    if not items:
        return []
    if workers <= 1 or len(items) == 1:
        out = []
        for i, item in enumerate(items, 1):
            out.append(fn(item))
            if progress:
                progress(i, len(items))
        return out

    from concurrent.futures import ThreadPoolExecutor

    results: list[Any] = [None] * len(items)
    done = 0
    lock = threading.Lock()

    def run(idx_item):
        nonlocal done
        idx, item = idx_item
        value = fn(item)
        with lock:
            done += 1
            if progress:
                progress(done, len(items))
        return idx, value

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for idx, value in pool.map(run, enumerate(items)):
            results[idx] = value
    return results


def preflight(cfg: Config | None = None) -> str:
    """Verify credentials and that the pinned model actually answers."""
    cfg = cfg or load_config()
    client = get_client(cfg)
    started = time.monotonic()
    out = client.json(
        "You are a connectivity check. Reply with JSON only.",
        'Reply with exactly {"ok": true}.',
    )
    if not isinstance(out, dict) or not out.get("ok"):
        raise LLMError(f"unexpected preflight response: {out!r}")
    return (f"{cfg.llm.provider}/{cfg.llm.model} OK "
            f"({time.monotonic() - started:.2f}s, temp={cfg.llm.temperature}, "
            f"<={cfg.llm.requests_per_minute} req/min, "
            f"{cfg.llm.max_concurrency} concurrent)")
