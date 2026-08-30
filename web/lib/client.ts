"use client";

/** Small fetch helpers. The API is proxied through /api by next.config.mjs. */

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function handle(res: Response) {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* keep statusText */
    }
    if (res.status === 428) {
      // MissingCredentials -- the message already says exactly what to run.
      throw new ApiError(detail, res.status);
    }
    throw new ApiError(detail, res.status);
  }
  return res.json();
}

export async function get<T>(path: string): Promise<T> {
  return handle(await fetch(path, { cache: "no-store" }));
}

export async function post<T>(path: string, body?: unknown): Promise<T> {
  return handle(
    await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  );
}
