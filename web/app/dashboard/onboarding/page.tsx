"use client";

import { useState } from "react";
import { AgentChip, Button, GlassPanel, Icon } from "@/components/glass";
import { post } from "@/lib/client";

const QUESTIONS: { key: keyof Answers; label: string; placeholder: string }[] = [
  { key: "last_bought", label: "What did you last buy?",
    placeholder: "A 14-inch work laptop, about $1,200." },
  { key: "almost_bought", label: "What did you almost buy instead?",
    placeholder: "A lighter laptop with a better screen that cost more." },
  { key: "why_not", label: "Why didn't you?",
    placeholder: "I wasn't sure the battery would last a full day out." },
  { key: "never_compromise", label: "What would you never compromise on?",
    placeholder: "A screen I can read outdoors. I work on site." },
];

type Answers = {
  last_bought: string;
  almost_bought: string;
  why_not: string;
  never_compromise: string;
};

type Parsed = {
  id: string;
  need: string;
  must_have: string[];
  prefer: string[];
  context: string[];
  query: string;
  source_answers: Record<string, string>;
};

const EMPTY: Answers = {
  last_bought: "", almost_bought: "", why_not: "", never_compromise: "",
};

export default function Onboarding() {
  const [answers, setAnswers] = useState<Answers>(EMPTY);
  const [parsed, setParsed] = useState<Parsed | null>(null);
  const [origin, setOrigin] = useState<"parsed" | "manual">("parsed");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const complete = Object.values(answers).every((v) => v.trim());
  const saveable = !!parsed?.need.trim() && !!parsed?.query.trim();

  async function parse() {
    setBusy(true); setError(null); setSaved(false);
    try {
      setParsed(await post<Parsed>("/api/onboard/parse", answers));
      setOrigin("parsed");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  /**
   * Straight to the editor, no model call. The four answers are still kept
   * verbatim as provenance -- only the parsing is skipped.
   */
  function enterManually() {
    setError(null); setSaved(false); setOrigin("manual");
    setParsed({
      id: "seed_01", need: "", must_have: [], prefer: [], context: [],
      query: "", source_answers: { ...answers },
    });
  }

  async function save() {
    if (!parsed) return;
    setBusy(true); setError(null);
    try {
      await post("/api/onboard/save", parsed);
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  function editList(key: "must_have" | "prefer" | "context", value: string) {
    if (!parsed) return;
    setParsed({ ...parsed, [key]: value.split("\n").filter((l) => l.trim()) });
  }

  return (
    <div className="flex flex-col gap-stack-lg max-w-3xl">
      <div>
        <h1 className="font-headline-lg text-headline-lg text-on-surface uppercase mb-2">Onboarding</h1>
        <p className="font-body-md text-body-md text-on-surface-variant">
          Four questions. Your answers become the seed persona that every
          synthetic persona is generated from, so the result is shown back to
          you to correct before it is saved.
        </p>
      </div>

      <div className="flex flex-col gap-stack-md">
        {QUESTIONS.map((q) => (
          <div key={q.key} className="flex flex-col gap-2">
            <label className="font-label-caps text-label-caps uppercase text-on-surface-variant">
              {q.label}
            </label>
            <textarea
              rows={2}
              value={answers[q.key]}
              placeholder={q.placeholder}
              onChange={(e) => setAnswers({ ...answers, [q.key]: e.target.value })}
              className={`${inputCls} resize-y`}
            />
          </div>
        ))}

        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={parse} disabled={!complete || busy}>
            {busy && origin === "parsed" ? "Parsing…" : "Parse into a persona"}
          </Button>
          <Button variant="secondary" onClick={enterManually} disabled={busy}>
            Write the persona myself
          </Button>
        </div>
        <p className="font-body-sm text-body-sm text-on-surface-variant -mt-1">
          Parsing uses the model. Writing it yourself needs no API key and no
          network &mdash; useful when you want the run to start immediately.
        </p>
      </div>

      {error && (
        <GlassPanel className="p-4 border-l-4 border-error">
          <pre className="font-label-caps text-[12px] text-on-error-container whitespace-pre-wrap">
            {error}
          </pre>
          <p className="font-body-sm text-body-sm text-on-surface-variant mt-3">
            You can still continue &mdash; use{" "}
            <button onClick={enterManually} className="text-electric-cyan underline">
              write the persona myself
            </button>
            , which skips the model entirely.
          </p>
        </GlassPanel>
      )}

      {parsed && (
        <GlassPanel className="p-6 flex flex-col gap-stack-md">
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-headline-lg-mobile text-headline-lg-mobile text-on-surface uppercase">
              {origin === "manual" ? "Your persona" : "Parsed persona"}
            </h2>
            <AgentChip tone={origin === "manual" ? "neutral" : "agent"}>
              {origin === "manual" ? "written by hand" : "editable"}
            </AgentChip>
          </div>
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            {origin === "manual"
              ? "Describe the shopper in your own words. Need and query are required; the rest sharpen the personas spawned from this seed."
              : "Correct anything the parse got wrong. This is the only place your own words shape the run."}
          </p>

          <Field label="Need" hint="one sentence, what they're shopping for">
            <input
              value={parsed.need}
              placeholder="A durable neutral road trainer for half marathon training"
              onChange={(e) => setParsed({ ...parsed, need: e.target.value })}
              className={inputCls}
            />
          </Field>
          <Field label="Query it would type" hint="how they'd actually search">
            <input
              value={parsed.query}
              placeholder="durable road trainer with room in the forefoot under $160"
              onChange={(e) => setParsed({ ...parsed, query: e.target.value })}
              className={inputCls}
            />
          </Field>
          {(["must_have", "prefer", "context"] as const).map((k) => (
            <Field key={k} label={k.replace("_", " ")} hint="one per line">
              <textarea
                rows={3}
                value={parsed[k].join("\n")}
                onChange={(e) => editList(k, e.target.value)}
                className={`${inputCls} resize-y`}
              />
            </Field>
          ))}

          <div className="flex items-center gap-4">
            <Button onClick={save} disabled={busy || !saveable}>
              {busy ? "Saving…" : "Save seed persona"}
            </Button>
            {!saveable && (
              <span className="font-label-caps text-label-caps text-outline">
                need and query are required
              </span>
            )}
            {saved && (
              <span className="flex items-center gap-2">
                <AgentChip tone="good" dot>saved</AgentChip>
                <a
                  href="/dashboard/run"
                  className="font-label-caps text-label-caps uppercase text-electric-cyan flex items-center gap-1"
                >
                  Spawn personas
                  <Icon name="arrow_forward" className="text-[16px]" />
                </a>
              </span>
            )}
          </div>
        </GlassPanel>
      )}
    </div>
  );
}

const inputCls =
  "w-full p-3 rounded-md border border-glass-border bg-surface-container-low text-on-surface " +
  "placeholder-on-surface-variant/60 focus:outline-none focus:ring-2 " +
  "focus:ring-electric-cyan focus:bg-surface-container transition-all " +
  "font-body-md text-body-md";

function Field({
  label, hint, children,
}: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <label className="font-label-caps text-label-caps uppercase text-on-surface-variant">
        {label}
        {hint && <span className="normal-case text-outline"> · {hint}</span>}
      </label>
      {children}
    </div>
  );
}
