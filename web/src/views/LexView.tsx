import { OctagonX, Play, ShieldCheck, ShieldExclamationPoint } from "lucide-react";
import { useState } from "react";
import { api, type AuditEntry } from "../api";
import { ErrorNote, HashText, Loading, Section, ViewHeader } from "../components";
import { errorText, istFull, istTime } from "../format";
import { useResource } from "../hooks";
import { useStore } from "../store";

const RULES: { rule: string; how: string }[] = [
  { rule: "Allowlist only", how: "Collection reaches only the simulated ShadowNet services and benchmark onions until an authorised pilot." },
  { rule: "Read, never act", how: "GET requests only. No forms, no logins, no purchases, no messages to anyone on a site." },
  { rule: "No CAPTCHA automation", how: "Libertas carries no CAPTCHA solver and never submits a form, so a CAPTCHA or login wall ends the read for that page." },
  { rule: "Nothing captured is executed", how: "Pages are stored as bytes and reduced to text. No script runs, no captured page is rendered, no file is opened." },
  {
    rule: "Personal data stays masked",
    how: "Aadhaar and mobile numbers, email addresses and the names printed beside them are masked in every readable copy, including this console. The sealed capture keeps the exact bytes for court.",
  },
  { rule: "Only digests leave the machine", how: "The timestamp authority receives a SHA-256 digest, never content." },
  { rule: "Every decision is recorded", how: "Refusals, alerts, rescoring, takedowns, evidence exports and operator actions go into a hash-chained audit log; every capture is sealed in a Merkle batch." },
];

function detail(e: AuditEntry): string {
  try {
    const d = JSON.parse(e.detail_json || "{}") as Record<string, unknown>;
    return Object.entries(d)
      .slice(0, 4)
      .map(([k, v]) => `${k.replaceAll("_", " ")}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
      .join(" · ");
  } catch {
    return "";
  }
}

export function LexView() {
  const { status, refreshStatus } = useStore();
  const tail = useResource(() => api.auditTail(), [status?.counts?.audit_log]);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const engaged = !!status?.kill_engaged;
  const audit = status?.audit;

  const toggle = async () => {
    setBusy(true);
    setError(null);
    try {
      if (engaged) await api.resume();
      else await api.kill(reason.trim() || "Halted from the policy page");
      setReason("");
      await refreshStatus();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <ViewHeader title="Policy & audit" latin="Lex" />
      <p className="view-intro">What Libertas will and will not do, the switch that stops it, and the chained record that proves what it did.</p>

      <Section title="Collection control" note={status ? `Mode: ${status.lex?.mode ?? status.mode}` : undefined}>
        <div className={`control${engaged ? " is-halted" : ""}`}>
          <div className="control-state">
            {engaged ? <OctagonX size={22} aria-hidden /> : <Play size={22} aria-hidden />}
            <div>
              <p className="control-title">{engaged ? "Collection is halted" : "Collection is running"}</p>
              <p className="control-sub">
                {engaged
                  ? "Every fetch is refused at the gate until the switch is released. Captures already sealed stay intact."
                  : "The kill switch stops every fetch within seconds. It also works offline: python -m libertas kill"}
              </p>
            </div>
          </div>
          <form
            className="control-form"
            onSubmit={(e) => {
              e.preventDefault();
              void toggle();
            }}
          >
            {!engaged && (
              <label className="field field--grow">
                <span className="field-label">Reason, for the audit log</span>
                <input className="input" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. legal hold, suspected compromise" maxLength={200} />
              </label>
            )}
            <button type="submit" className={`btn ${engaged ? "btn--primary" : "btn--danger"}`} disabled={busy || !status}>
              {busy ? "Working" : engaged ? "Release and resume" : "Halt all collection"}
            </button>
          </form>
          {error && <ErrorNote error={error} />}
        </div>
      </Section>

      <Section title="Rules in force" note={
          status?.lex
            ? `${status.lex.allowlist_size} allowlisted onions · ${
                status.lex.blocklist_size ? `${status.lex.blocklist_size.toLocaleString("en-IN")} abuse-blocklist hashes` : "no abuse blocklist loaded"
              }`
            : undefined
        }>
        <dl className="rules">
          {RULES.map((r) => (
            <div key={r.rule}>
              <dt>{r.rule}</dt>
              <dd>{r.how}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section
        title="Audit chain"
        note={
          audit ? (
            <span className={`chain-state${audit.ok ? "" : " is-broken"}`}>
              {audit.ok ? <ShieldCheck size={14} aria-hidden /> : <ShieldExclamationPoint size={14} aria-hidden />}
              {audit.ok ? `Intact across ${audit.entries_checked} entries` : `Broken at entry #${audit.broken_at_seq}`}
            </span>
          ) : undefined
        }
      >
        {audit?.head && (
          <p className="chain-head">
            Head of chain <HashText value={audit.head} />
          </p>
        )}
        {tail.error && !tail.data ? (
          <ErrorNote error={tail.error} retry={tail.reload} />
        ) : !tail.data ? (
          <Loading label="Reading the audit log" />
        ) : (
          <div className="table-wrap">
            <table className="ledger ledger--dense">
              <thead>
                <tr>
                  <th scope="col" className="num">
                    #
                  </th>
                  <th scope="col">Time (IST)</th>
                  <th scope="col">Actor</th>
                  <th scope="col">Action</th>
                  <th scope="col">Target</th>
                  <th scope="col">Detail</th>
                  <th scope="col">Entry hash</th>
                </tr>
              </thead>
              <tbody>
                {tail.data.map((e) => (
                  <tr key={e.seq}>
                    <td className="mono num">{e.seq}</td>
                    <td className="mono nowrap" title={istFull(e.ts)}>
                      {istTime(e.ts)}
                    </td>
                    <td className="mono">{e.actor}</td>
                    <td>
                      {e.action.replaceAll("_", " ")}
                      {e.decision && <span className="cell-sub">{e.decision}</span>}
                    </td>
                    <td className="mono">{e.target}</td>
                    <td className="cell-detail">{detail(e)}</td>
                    <td className="mono pencil" title={e.hash}>
                      {e.hash.slice(0, 10)}…
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </div>
  );
}
