/**
 * Server-side reads of the JSON on disk.
 *
 * The storefront reads product files directly rather than going through the
 * API, so an approved rewrite shows up on the next request with no rebuild and
 * no cache to bust. That is the whole reason the storefront is not a static
 * export here.
 */
import fs from "node:fs/promises";
import path from "node:path";
import YAML from "yaml";

const ROOT = path.resolve(process.cwd(), "..");
const DATA = path.join(ROOT, "data");

export type Product = {
  id: string;
  name: string;
  price: number;
  specs: Record<string, string | number | boolean>;
  description: string;
  edit_history: EditEntry[];
  semantic_links: SemanticLink[];
};

export type EditEntry = {
  at: string;
  added: string;
  replaced?: string;
  based_on: string[];
  proposal_id?: string;
};

export type SemanticLink = {
  intent: string;
  round?: number;
  evidenced_by?: string;
  rank?: number | null;
};

export type Persona = {
  id: string;
  seed_id: string;
  origin: "real" | "synthetic";
  need: string;
  must_have: string[];
  prefer: string[];
  context: string[];
  angle: string;
  query: string;
  source_answers?: Record<string, string>;
};

export type Gap = {
  id: string;
  product_id: string;
  intent: string;
  type: "fixable" | "needs_evidence" | "not_applicable" | "already_covered";
  supporting_specs: string[];
  rationale: string;
  evidenced_by?: string;
  rank?: number | null;
};

export type Report = {
  round: number;
  generated_at: string;
  dataset: string;
  search_k: number;
  totals: { products: number; queries: number; surfaced: number; never_surfaced: number };
  intents: { label: string; count: number; examples: string[] }[];
  never_surfaced: { product_id: string; missed: string[] }[];
  gaps: Gap[];
};

export type Proposal = {
  id: string;
  gap_id: string;
  product_id: string;
  intent: string;
  action: "rewrite" | "flag" | "skip" | "no_change";
  new_description: string | null;
  based_on: string[];
  reason: string;
  status: "pending" | "approved" | "rejected";
  created_at: string;
  downgraded_from?: string;
  rejected_description?: string;
  traceability_failures?: string[];
  link?: SemanticLink;
  applied?: string;
};

export type Config = {
  dataset: string;
  search_k: number;
  persona_count: number;
  llm: { provider: string; model: string };
};

async function readJson<T>(file: string, fallback: T): Promise<T> {
  try {
    return JSON.parse(await fs.readFile(file, "utf-8")) as T;
  } catch {
    return fallback;
  }
}

export async function getConfig(): Promise<Config> {
  const raw = await fs.readFile(path.join(ROOT, "config.yaml"), "utf-8");
  return YAML.parse(raw) as Config;
}

export async function getProducts(): Promise<Product[]> {
  const cfg = await getConfig();
  const dir = path.join(DATA, "datasets", cfg.dataset, "products");
  const files = (await fs.readdir(dir)).filter((f) => f.endsWith(".json")).sort();
  return Promise.all(
    files.map(async (f) => JSON.parse(await fs.readFile(path.join(dir, f), "utf-8")))
  );
}

export async function getProduct(id: string): Promise<Product | null> {
  const cfg = await getConfig();
  const file = path.join(DATA, "datasets", cfg.dataset, "products", `${id}.json`);
  return readJson<Product | null>(file, null);
}

export async function getDatasetMeta(): Promise<{
  display_name: string;
  currency: string;
  icon: string;
  spec_labels: Record<string, string>;
  unsupported_attributes: string[];
}> {
  const cfg = await getConfig();
  const raw = await fs.readFile(
    path.join(DATA, "datasets", cfg.dataset, "meta.yaml"),
    "utf-8"
  );
  return YAML.parse(raw) as never;
}

export async function getPersonas(): Promise<Persona[]> {
  const dir = path.join(DATA, "personas");
  try {
    const files = (await fs.readdir(dir)).filter((f) => f.endsWith(".json")).sort();
    return Promise.all(
      files.map(async (f) => JSON.parse(await fs.readFile(path.join(dir, f), "utf-8")))
    );
  } catch {
    return [];
  }
}

export async function getReport(): Promise<Report | null> {
  return readJson<Report | null>(path.join(DATA, "report.json"), null);
}

export async function getProposals(): Promise<Proposal[]> {
  const dir = path.join(DATA, "proposals");
  try {
    const files = (await fs.readdir(dir)).filter((f) => f.endsWith(".json")).sort();
    return Promise.all(
      files.map(async (f) => JSON.parse(await fs.readFile(path.join(dir, f), "utf-8")))
    );
  } catch {
    return [];
  }
}

export async function getScores(): Promise<Record<string, Record<string, { verdict: string }>>> {
  return readJson(path.join(DATA, "scores.json"), {});
}

export async function getLinks(): Promise<Record<string, SemanticLink[]>> {
  return readJson(path.join(DATA, "links.json"), {});
}

export async function getRound(n: number): Promise<
  { persona_id: string; query: string; angle: string; returned: string[]; never_returned: string[] }[]
> {
  try {
    const raw = await fs.readFile(path.join(DATA, "logs", `round_${n}.jsonl`), "utf-8");
    return raw
      .split("\n")
      .filter((l) => l.trim())
      .map((l) => JSON.parse(l));
  } catch {
    return [];
  }
}
