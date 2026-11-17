// Typed access to the Libertas API (same origin). Captured text arrives as data and is only ever rendered as text.

export type Severity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

export interface Category {
  category: string;
  label: string;
  confidence: number;
}

export interface OrgHit {
  org: string;
  sector: string;
  state?: string;
  city?: string;
}

export interface DeepSummary {
  severity: Severity;
  score: number;
  reasons: string[];
  factors: Record<string, number | null>;
  authenticity: string;
  actor: string | null;
  assessed_at: string;
  first_assessed_at?: string;
  latency_s: number | null;
}

export interface Alert {
  id: number;
  created_at: string;
  updated_at: string;
  item_id: number;
  source_id: string;
  severity: Severity;
  score: number;
  title: string;
  summary: string;
  status: "new" | "acknowledged" | "historical" | string;
  provisional: number;
  detection_lag_s: number | null;
  deleted: number;
  item_title: string;
  author: string | null;
  url: string;
  kind: string;
  posted_at: string | null;
  first_seen: string;
  deleted_at: string | null;
  first_capture_sha: string | null;
  source_name: string;
  simulated: number;
  categories: Category[];
  orgs: OrgHit[];
  sectors: string[];
  factors?: Record<string, number | null>;
  reasons?: string[];
  fast?: { severity: Severity; score: number };
  deep?: DeepSummary;
}

export interface Descriptor {
  id?: number;
  source_id?: string;
  observed_at?: string;
  onion: string;
  result: string;
  seconds: number | null;
  hsdirs_asked: number | null;
  intro_points: number | null;
  pow_enabled: boolean | number | null;
  pow_effort: number | null;
  single_onion: boolean | number | null;
  private: boolean | number | null;
  error: string;
}

export interface Health {
  state?: string;
  pulses?: number;
  consecutive_failures?: number;
  last_pulse_at?: string | null;
  last_pulse_s?: number | null;
  last_outcome?: string | null;
  descriptor?: Descriptor;
  isolation_id?: string;
}

export interface Source {
  id: string;
  name: string;
  kind: string;
  onion: string;
  adapter: string;
  priority: number;
  enabled: number;
  added_at: string;
  simulated: number;
  health: Health;
  items: number;
}

export interface AuditVerify {
  ok: boolean;
  entries_checked: number;
  head?: string;
  broken_at_seq?: number;
}

export interface Status {
  mode: string;
  unit?: string;
  kill_engaged: boolean;
  simulation: boolean;
  lex?: { mode: string; allowlist_size: number; blocklist_size: number };
  sources: Source[];
  ttd: { n: number; median_s: number; p95_s: number; max_s: number } | null;
  alerts_by_severity: Record<string, number>;
  counts: Record<string, number>;
  queue: number;
  audit: AuditVerify;
}

export interface Indicator {
  kind: string;
  value: string;
  display: string;
  valid: number | null;
  sensitive: number;
}

export interface ItemRow {
  id: number;
  source_id: string;
  kind: string;
  title: string;
  author: string | null;
  posted_at: string | null;
  first_seen: string;
  deleted_at: string | null;
}

export interface ItemRecord extends ItemRow {
  item_key: string;
  url: string;
  body_text: string;
  last_seen: string;
  last_checked: string | null;
  content_hash: string;
  first_capture_sha: string | null;
  last_capture_sha: string | null;
  detection_lag_s: number | null;
  extra: Record<string, unknown>;
  indicators: Indicator[];
  versions: { seen_at: string; content_hash: string; capture_sha: string | null }[];
  captures: {
    fetched_at: string;
    status: number | null;
    sha256: string | null;
    elapsed_s: number | null;
    outcome: string;
    isolation_id: string | null;
  }[];
}

export interface LinkEvidence {
  family: string;
  kind?: string;
  display?: string;
  weight?: number;
  items?: number[];
  similarity?: number;
  z?: number;
  p?: number;
  distinctive_shared_phrases?: string[];
  cluster?: string;
  wallets?: string[];
  basis?: string;
}

export interface ActorMember {
  account_id: number;
  alias: string;
  source: string;
  best_link: number;
}

export interface AttributionLink {
  account_id: number;
  alias: string;
  source: string;
  probability: number;
  truth: string;
  evidence: LinkEvidence[];
}

export interface Exposure {
  entity: string;
  type: string;
  sats: number;
  deposits: string[];
  txids: string[];
  btc: number;
}

export interface ClusterEvidence {
  a: string;
  b: string;
  heuristic: string;
  confidence: number;
  txid: string;
}

export interface WalletMoney {
  cluster_id: string | null;
  size: number;
  received_sats: number;
  sent_sats: number;
  tx_count: number;
  entity: string | null;
  exposure: Exposure[];
  flags: string[];
  note: string;
  peel_chains: number;
  evidence: ClusterEvidence[];
}

export interface Deep {
  item_id: number;
  assessed_at: string;
  method: string;
  score: number;
  severity: Severity;
  latency_s: number | null;
  authenticity: { verdict: string; score: number; signals: Record<string, number>; reasons: string[] };
  attribution: {
    account_id: number;
    alias: string;
    source: string;
    actor: {
      id: number;
      label: string;
      truth: string;
      confidence: number;
      members: ActorMember[];
      prior_items: number;
      prior_targets: string[];
    } | null;
    links: AttributionLink[];
  } | null;
  money: Record<string, WalletMoney> | null;
  correlation: {
    wallet_links: { cluster?: string; items: { id: number; author: string; source: string }[] }[];
    incident: { id: number; title: string; items: number; sources: string[] } | null;
    escalation: { actor: string; new_targets: string[]; previous_targets: string[] } | null;
  } | null;
  reasons: string[];
}

export interface Actor {
  id: number;
  anchor: string;
  label: string;
  confidence: number;
  truth: string;
  created_at: string;
  updated_at: string;
  members: ActorMember[];
}

export interface AliasLink {
  a: number;
  b: number;
  probability: number;
  truth: string;
  updated_at: string;
  evidence: LinkEvidence[];
  a_alias: string;
  a_source: string;
  b_alias: string;
  b_source: string;
}

export interface Incident {
  id: number;
  key: string;
  title: string;
  org: string;
  first_seen: string;
  last_seen: string;
  updated_at: string;
  item_ids: number[];
  sources: string[];
  summary: {
    timeline: { item_id: number; first_seen: string; source: string; title: string; deleted: boolean; category: string }[];
    shared_datasets: { items: number[]; shared_identifiers: number; note: string }[];
  };
}

export interface PeelChain {
  start: string;
  steps: { txid: string; change: string; paid_to: string; value: number }[];
  total_paid: number;
}

export interface Cluster {
  id: string;
  chain: string;
  size: number;
  label: string | null;
  addresses: string[];
  exposure: Exposure[];
  flags: string[];
  peel_chains: PeelChain[];
  evidence: ClusterEvidence[];
  seeds: string[];
  seen_in_items: { id: number; title: string; author: string | null; source_id: string }[];
  updated_at: string;
}

export interface LedgerEntry {
  txid: string;
  height: number;
  time: number;
  debit_sats: number;
  credit_sats: number;
  fee_sats: number;
  external_sats: number;
  entity_sats: number;
  particulars: string;
  entity: string | null;
  peel: boolean;
  balance_sats: number;
}

export interface Ledger {
  cluster: Cluster;
  entries: LedgerEntry[];
  note: string;
}

export interface Pack {
  id: string;
  created_at: string;
  item_id: number;
  alert_id: number | null;
  created_by: string;
  manifest_sha256: string;
  zip_sha256: string;
  summary: {
    captures: number;
    batches: number;
    timestamped: number;
    files: number;
    zip_bytes: number;
    legal_drafts: string[];
  };
}

export interface BuiltPack {
  pack_id: string;
  captures: number;
  batches: number;
  timestamped: number;
  files: number;
  manifest_sha256: string;
  zip_sha256: string;
  download: string;
}

export interface GNode {
  id: string;
  type: string;
  label: string;
  severity?: Severity;
  score?: number;
  truth?: string;
  source?: string;
  sector?: string;
  kind?: string;
  deleted?: boolean;
  first_seen?: string;
}

export interface GEdge {
  source: string;
  target: string;
  relation: string;
  probability?: number;
  truth?: string;
}

export interface Graph {
  focus: string;
  nodes: GNode[];
  edges: GEdge[];
  error?: string;
}

export interface PathStep {
  from: string;
  from_label: string;
  to: string;
  to_label: string;
  relation: string;
  probability?: number;
  truth?: string;
}

export interface Tabularium {
  batches_by_status: Record<string, number>;
  captures_sealed: number;
  last_batch: { id: number; created_at: string; root: string; size: number; status: string; tsa_gen_time: string | null } | null;
}

export interface AuditEntry {
  seq: number;
  ts: string;
  actor: string;
  action: string;
  target: string;
  decision: string;
  detail_json: string;
  hash: string;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// Writes carry this header. A cross-site page cannot attach it without a CORS preflight the API never grants.
const CLIENT = { "X-Libertas-Client": "forum" };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (init?.method && init.method !== "GET") Object.assign(headers, CLIENT);
  if (init?.body) headers["Content-Type"] = "application/json";
  let res: Response;
  try {
    res = await fetch(path, { ...init, headers, cache: "no-store" });
  } catch {
    throw new ApiError(0, "Libertas is not answering on this machine. Check that it is running.");
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (body && body.detail) detail = String(body.detail);
    } catch {
      /* the error body was not JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

const qs = (params: Record<string, string>) => new URLSearchParams(params).toString();

export const api = {
  status: () => request<Status>("/api/status"),
  alerts: () => request<Alert[]>("/api/alerts?limit=300"),
  ack: (alertId: number) => request<Alert>(`/api/alerts/${alertId}/ack`, { method: "POST" }),
  item: (id: number) => request<ItemRecord>(`/api/items/${id}`),
  deep: (id: number) => request<Deep>(`/api/items/${id}/deep`),
  items: (q: string, source: string) => request<ItemRow[]>(`/api/items?${qs({ q, source, limit: "120" })}`),
  actors: () => request<Actor[]>("/api/actors"),
  links: () => request<AliasLink[]>("/api/links"),
  incidents: () => request<Incident[]>("/api/incidents"),
  clusters: () => request<Cluster[]>("/api/clusters"),
  ledger: (id: string) => request<Ledger>(`/api/clusters/${encodeURIComponent(id)}/ledger`),
  graph: (focus: string, depth: number) => request<Graph>(`/api/graph?${qs({ focus, depth: String(depth) })}`),
  path: (a: string, b: string) => request<{ a: string; b: string; steps: PathStep[] }>(`/api/path?${qs({ a, b })}`),
  packs: () => request<Pack[]>("/api/evidence"),
  buildPack: (itemId: number) => request<BuiltPack>(`/api/items/${itemId}/evidence`, { method: "POST" }),
  tabularium: () => request<Tabularium>("/api/tabularium"),
  descriptors: () => request<Descriptor[]>("/api/descriptors?limit=80"),
  auditTail: () => request<AuditEntry[]>("/api/audit/tail?limit=60"),
  kill: (reason: string) =>
    request<{ kill_engaged: boolean }>("/api/kill", { method: "POST", body: JSON.stringify({ reason }) }),
  resume: () => request<{ kill_engaged: boolean }>("/api/resume", { method: "POST" }),
};
