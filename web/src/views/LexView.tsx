import { OctagonX, Play, ShieldCheck, ShieldExclamationPoint } from "lucide-react";
import { useState } from "react";
import { api, type AuditEntry, type LexDrill } from "../api";
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
  const [drill, setDrill] = useState<{ state: "idle" | "running" | "done" | "error"; result?: LexDrill; error?: string }>({
    state: "idle",
  });

  const runDrill = async () => {
    setDrill({ state: "running" });
    try {
      setDrill({ state: "done", result: await api.lexDrill() });
      tail.reload();
    } catch (e) {
      setDrill({ state: "error", error: errorText(e) });
    }
  };

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

      <Section title="Test the boundary" note="Ask the crawler to cross the line">
        <div className="drill">
          <p className="control-sub">
            Six forbidden requests go to the same gate every real request passes: logging in, credentials in the address, an
            unauthorised onion, the open internet, a leaked archive and an executable. A refused request never leaves this machine,
            and each refusal is written to the audit chain.
          </p>
          <button type="button" className="btn btn--primary" onClick={runDrill} disabled={drill.state === "running"}>
            <ShieldCheck size={16} aria-hidden /> {drill.state === "running" ? "Testing" : "Test the boundary"}
          </button>
          {drill.state === "error" && drill.error && <ErrorNote error={drill.error} retry={runDrill} />}
          {drill.result && (
            <div className="table-wrap">
              <table className="ledger ledger--dense drill-table">
                <thead>
                  <tr>
                    <th scope="col">Attempt</th>
                    <th scope="col">Request</th>
                    <th scope="col">Lex</th>
                    <th scope="col" className="num">
                      Audit #
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {drill.result.attempts.map((a) => (
                    <tr key={a.attempt}>
                      <td>{a.attempt}</td>
                      <td className="mono break cell-detail">
                        {a.method} {a.url.length > 64 ? `${a.url.slice(0, 40)}…${a.url.slice(-20)}` : a.url}
                      </td>
                      <td className={a.allowed ? "fail" : ""}>
                        <b>{a.allowed ? "Allowed" : "Refused"}</b>
                        <span className="cell-sub">{a.reason}</span>
                      </td>
                      <td className="mono num">{a.audit_seq}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className={`drill-verdict${drill.result.passed ? "" : " fail"}`}>
                {drill.result.refused} of {drill.result.total} refused. Audit chain{" "}
                {drill.result.audit.ok ? `intact across ${drill.result.audit.entries_checked} entries` : "BROKEN"}.
              </p>
            </div>
          )}
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
