// Domain language for the Forum: precedence, IST date-time groups, clearing, codes and figures.
import type { Alert, Severity } from "./api";

export type PrecedenceName = "FLASH" | "IMMEDIATE" | "PRIORITY" | "ROUTINE";

const PRECEDENCE: Record<Severity, { name: PrecedenceName; rank: number }> = {
  CRITICAL: { name: "FLASH", rank: 0 },
  HIGH: { name: "IMMEDIATE", rank: 1 },
  MEDIUM: { name: "PRIORITY", rank: 2 },
  LOW: { name: "ROUTINE", rank: 3 },
};

export const PRECEDENCE_ORDER: PrecedenceName[] = ["FLASH", "IMMEDIATE", "PRIORITY", "ROUTINE"];

export function precedence(severity: string | undefined | null) {
  return PRECEDENCE[severity as Severity] ?? PRECEDENCE.LOW;
}

// ---------- time (all display in IST) ----------
const TZ = "Asia/Kolkata";
const fmtTime = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" });
const fmtDay = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, day: "2-digit", month: "short" });
const fmtWeekday = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, weekday: "short", day: "2-digit", month: "short" });
const fmtFull = new Intl.DateTimeFormat("en-GB", {
  timeZone: TZ, day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
});
const fmtParts = new Intl.DateTimeFormat("en-GB", {
  timeZone: TZ, day: "2-digit", month: "short", year: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
});
const fmtNumeric = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, day: "2-digit", month: "2-digit", year: "numeric" });

/** ISO strings, epoch milliseconds (the live clock) or epoch seconds (block times) all become a Date. */
export function toDate(v: string | number | null | undefined): Date | null {
  if (v === null || v === undefined || v === "") return null;
  const d = typeof v === "number" ? new Date(v < 1e11 ? v * 1000 : v) : new Date(v);
  return Number.isNaN(d.getTime()) ? null : d;
}

type When = string | number | null | undefined;

export const istTime = (v: When) => {
  const d = toDate(v);
  return d ? fmtTime.format(d) : "—";
};
export const istDay = (v: When) => {
  const d = toDate(v);
  return d ? fmtDay.format(d) : "—";
};
export const istWeekday = (v: When) => {
  const d = toDate(v);
  return d ? fmtWeekday.format(d) : "—";
};
export const istFull = (v: When) => {
  const d = toDate(v);
  return d ? `${fmtFull.format(d)} IST` : "—";
};
/** Passbook date, as Indian banks print it: 17-11-2026. */
export const passbookDate = (v: When) => {
  const d = toDate(v);
  return d ? fmtNumeric.format(d).replaceAll("/", "-") : "—";
};

/** Date-time group in IST, e.g. "172347 NOV 26": day, hour, minute, month, year. */
export function dtg(v: When): string {
  const d = toDate(v);
  if (!d) return "—";
  const p = Object.fromEntries(fmtParts.formatToParts(d).map((x) => [x.type, x.value]));
  return `${p.day}${p.hour}${p.minute} ${String(p.month).toUpperCase()} ${p.year}`;
}

export const sameIstDay = (a: When, b: When) => {
  const x = toDate(a);
  const y = toDate(b);
  return !!x && !!y && fmtDay.format(x) === fmtDay.format(y);
};

export function ago(v: When, now: number): string {
  const d = toDate(v);
  if (!d) return "—";
  const s = Math.max(0, Math.round((now - d.getTime()) / 1000));
  if (s < 60) return `${s} s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} h ${m % 60} min ago`;
  return `${Math.floor(h / 24)} d ago`;
}

export function seconds(sec: number | null | undefined): string {
  if (sec === null || sec === undefined || Number.isNaN(sec)) return "—";
  if (sec < 10) return `${sec.toFixed(1)} s`;
  if (sec < 120) return `${Math.round(sec)} s`;
  const m = Math.floor(sec / 60);
  if (m < 120) return `${m} min ${Math.round(sec % 60)} s`;
  return `${Math.floor(m / 60)} h ${m % 60} min`;
}

/** Seconds from one moment to another, or null when either is unknown. */
export function between(from: When, to: When): number | null {
  const a = toDate(from);
  const b = toDate(to);
  return a && b ? (b.getTime() - a.getTime()) / 1000 : null;
}

export function lifetime(from: When, to: When): string {
  const a = toDate(from);
  const b = toDate(to);
  if (!a || !b) return "—";
  return seconds((b.getTime() - a.getTime()) / 1000);
}

// ---------- codes and figures ----------
export const msgNo = (itemId: number) => `MSG-${String(itemId).padStart(4, "0")}`;
export const actCode = (id: number) => `ACT-${String(id).padStart(2, "0")}`;
export const incCode = (id: number) => `INC-${String(id).padStart(2, "0")}`;

export function shortHash(h: string | null | undefined, head = 8, tail = 8): string {
  if (!h) return "—";
  return h.length <= head + tail + 1 ? h : `${h.slice(0, head)}…${h.slice(-tail)}`;
}

export const sourceLabel = (name: string | null | undefined) => (name || "").replace(/\s*\(SIM\)\s*$/i, "");
export const btc = (sats: number) => (sats / 1e8).toFixed(8);
export const prob = (p: number | null | undefined) => (p === null || p === undefined ? "—" : p.toFixed(3));
const nfIN = new Intl.NumberFormat("en-IN");
export const indian = (n: number) => nfIN.format(n);

export function onionHost(url: string | null | undefined): string {
  if (!url) return "—";
  const m = url.match(/^[a-z]+:\/\/([^/]+)(\/.*)?$/i);
  if (!m) return url;
  const host = m[1];
  const label = host.replace(/\.onion$/i, "");
  const shortHost = label.length > 16 ? `${label.slice(0, 6)}…${label.slice(-4)}.onion` : host;
  return `${shortHost}${m[2] ?? ""}`;
}

const SECTOR: Record<string, string> = {
  banking: "Banking", telecom: "Telecom", government: "Government", health: "Health", healthcare: "Health",
  education: "Education", logistics: "Logistics", power: "Power", energy: "Energy", insurance: "Insurance",
};
export const sector = (s: string) => SECTOR[s] ?? s.charAt(0).toUpperCase() + s.slice(1).replaceAll("_", " ");

const INDICATOR: Record<string, string> = {
  aadhaar: "Aadhaar", pan: "PAN", gstin: "GSTIN", ifsc: "IFSC", upi: "UPI ID", mobile_in: "Mobile", email: "Email",
  wallet_btc: "Bitcoin wallet", wallet_xmr: "Monero wallet", wallet_trx: "Tron wallet", wallet_eth: "Ethereum wallet",
  tox_id: "Tox ID", session_id: "Session ID", telegram: "Telegram", pgp: "PGP key", jabber: "Jabber", onion: "Onion address",
};
export const indicatorKind = (k: string) => INDICATOR[k] ?? k.replaceAll("_", " ");

const FAMILY: Record<string, string> = { operational: "Shared identifier", stylometry: "Writing style", money: "Money trail" };
export const family = (f: string) => FAMILY[f] ?? f;

const TRUTH: Record<string, string> = { T1: "Shared identifier", T2: "Heuristic only", T3: "Corroborated" };
export const truthLabel = (t: string | null | undefined) => (t ? TRUTH[t] ?? t : "—");

const KIND: Record<string, string> = {
  forum_thread: "Forum thread", market_listing: "Market listing", leak_post: "Leak-blog post", leakblog_post: "Leak-blog post",
  paste: "Paste", forum: "Forum", market: "Market", leakblog: "Leak blog",
};
export const kindLabel = (k: string | null | undefined) => (k ? KIND[k] ?? k.replaceAll("_", " ") : "—");

// ---------- clearing (the deep lane's verdict, read like a cheque) ----------
export type ClearingState = "UNCLEARED" | "CLEARED" | "RETURNED";

export interface Clearing {
  state: ClearingState;
  short: string;
  reason: string;
}

export function clearing(a: Pick<Alert, "provisional" | "deep">): Clearing {
  if (a.provisional || !a.deep) {
    return { state: "UNCLEARED", short: "Deep lane pending", reason: "Fast-lane reading only. The deep lane has not ruled yet." };
  }
  const first = a.deep.reasons?.[0] ?? "";
  const why = first.startsWith("Authenticity:") ? authenticitySentence(first.replace(/^Authenticity:\s*/, "")) : "";
  switch (a.deep.authenticity) {
    case "recycled":
      return { state: "RETURNED", short: "Recycled data", reason: why || "The sample matches data already seen in an earlier leak." };
    case "likely_fake":
      return { state: "RETURNED", short: "Likely fake", reason: why || "The sample identifiers fail their checksums." };
    case "likely_genuine":
      return { state: "CLEARED", short: "Sample checks out", reason: why || "The sample data passes the checksum and geography checks." };
    default:
      return {
        state: "CLEARED",
        short: "Claim stands",
        reason: why || "The deep lane found no reason to return it. This post carries no sample that can be tested.",
      };
  }
}

/** "likely fake (0.55): most sample identifiers fail…" → "Likely fake, authenticity score 0.55 of 1. Most sample identifiers fail…." */
export function authenticitySentence(raw: string): string {
  const m = raw.match(/^(likely genuine|likely fake|recycled|unverifiable)\s*\(([\d.]+)\):?\s*(.*)$/i);
  if (!m) return raw ? raw.charAt(0).toUpperCase() + raw.slice(1) : "";
  const rest = m[3].trim();
  const tail = rest ? ` ${rest.charAt(0).toUpperCase()}${rest.slice(1)}${/[.!?]$/.test(rest) ? "" : "."}` : "";
  return `${verdictLabel(m[1].toLowerCase().replace(" ", "_"))}, authenticity score ${Number(m[2]).toFixed(2)} of 1.${tail}`;
}

const VERDICT: Record<string, string> = {
  likely_genuine: "Likely genuine", likely_fake: "Likely fake", recycled: "Recycled", unverifiable: "Not verifiable",
};
export const verdictLabel = (v: string | null | undefined) => (v ? VERDICT[v] ?? v : "—");

export const isUnacked = (a: Alert) => a.status === "new";

/** Ranking for the message log: precedence first, then the newest date-time group. */
export function compareMessages(a: Alert, b: Alert): number {
  const r = precedence(a.severity).rank - precedence(b.severity).rank;
  if (r !== 0) return r;
  return (toDate(b.first_seen)?.getTime() ?? 0) - (toDate(a.first_seen)?.getTime() ?? 0);
}

export function errorText(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
