import { ArrowRight, Check, Download, FileText, Landmark, Network, UserSearch } from "lucide-react";
import { useState, type ReactNode } from "react";
import { api, ApiError, type Alert, type AttributionLink, type BuiltPack, type Deep, type ItemRecord } from "../api";
import { ErrorNote, Fact, Facts, HashText, Lead, Loading, PrecedenceTag, Section, Stamp, tiltFor } from "../components";
import {
  actCode,
  ago,
  between,
  btc,
  clearing,
  dtg,
  errorText,
  family,
  incCode,
  indian,
  indicatorKind,
  istDay,
  istFull,
  istTime,
  kindLabel,
  lifetime,
  msgNo,
  onionHost,
  precedence,
  sector,
  seconds,
  shortHash,
  sourceLabel,
  verdictLabel,
} from "../format";
import { href, useResource } from "../hooks";
import { useNow, useStore } from "../store";

const CHECKSUMMED = new Set(["aadhaar", "gstin", "pan"]);

const FACTOR_LABEL: Record<string, string> = {
  sector: "Sector weight",
  sensitivity: "Data sensitivity",
  scale: "Claimed scale",
  india_relevance: "India relevance",
  credibility: "Seller credibility",
  category: "Category",
  authenticity_multiplier: "Authenticity multiplier",
  age_hours: "Age at first sight (h)",
};

function claimedScale(reasons: string[] | undefined): number | null {
  for (const r of reasons ?? []) {
    const m = r.match(/claimed scale:\s*([\d,]+)\s*records/i);
    if (m) return Number(m[1].replaceAll(",", ""));
  }
  return null;
}

function identifierSummary(item: ItemRecord): ReactNode {
  const groups = new Map<string, { n: number; valid: number }>();
  for (const ind of item.indicators) {
    const g = groups.get(ind.kind) ?? { n: 0, valid: 0 };
    g.n += 1;
    if (ind.valid) g.valid += 1;
    groups.set(ind.kind, g);
  }
  if (!groups.size) return <span className="pencil">None found</span>;
  return (
    <ul className="inline-list">
      {[...groups.entries()].map(([kind, g]) => (
        <li key={kind}>
          {indicatorKind(kind)} <span className="mono">×{g.n}</span>
          {CHECKSUMMED.has(kind) && (
            <span className={g.valid === g.n ? "" : "fail"}>
              {" "}
              ({g.valid} of {g.n} pass checksum)
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

function evidenceLine(e: AttributionLink) {
  return e.evidence.map((ev, i) => {
    let text: string;
    if (ev.family === "operational") text = `Same ${indicatorKind(ev.kind ?? "identifier")} ${ev.display ?? ""}`.trim();
    else if (ev.family === "stylometry")
      text = `Writing style ${ev.similarity?.toFixed(2)} similar (z ${ev.z?.toFixed(1)})`;
    else if (ev.family === "money") text = `Wallets in the same cluster ${ev.cluster ?? ""} (${ev.basis ?? "heuristic"})`;
    else text = family(ev.family);
    return <li key={i}>{text}</li>;
  });
}

function Recommended({ alert, deep, item }: { alert: Alert; deep: Deep | null; item: ItemRecord | null }) {
  const steps: ReactNode[] = [];
  const c = clearing(alert);
  const org = alert.orgs[0]?.org;
  if (alert.deleted) steps.push("The post is gone from the site. Rely on the sealed capture; build the evidence pack now.");
  if (c.state === "RETURNED") steps.push("The claim fails the deep lane's checks. Acknowledge it and keep watching the seller for a genuine sample.");
  if (c.state !== "RETURNED" && org) steps.push(`Notify ${org} and CERT-In. Both drafts are generated inside the evidence pack.`);
  const exposure = Object.values(deep?.money ?? {}).flatMap((m) => m.exposure ?? []);
  if (exposure.length) {
    const e = exposure[0];
    steps.push(`Prepare a BNSS §94 notice to ${e.entity} for the KYC behind ${e.deposits.length} deposit addresses (draft in the pack).`);
  }
  if (deep?.attribution?.actor) steps.push(`Read actor file ${actCode(deep.attribution.actor.id)} before contacting the victim; this seller has history.`);
  if (!steps.length && item) steps.push("Acknowledge, then decide whether an evidence pack is needed.");
  if (!steps.length) return null;
  return (
    <ol className="steps">
      {steps.map((s, i) => (
        <li key={i}>{s}</li>
      ))}
    </ol>
  );
}

export function Voucher({ alert, landing }: { alert: Alert; landing: boolean }) {
  const { versions, patchAlert } = useStore();
  const now = useNow();
  const item = useResource(() => api.item(alert.item_id), [alert.item_id, versions.items, alert.deleted]);
  const deep = useResource<Deep | null>(
    () =>
      api.deep(alert.item_id).catch((e: unknown) => {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }),
    [alert.item_id, alert.provisional, versions.deep],
  );
  const [acking, setAcking] = useState(false);
  const [ackError, setAckError] = useState<string | null>(null);
  const [pack, setPack] = useState<{ state: "idle" | "building" | "done" | "error"; result?: BuiltPack; error?: string }>({ state: "idle" });

  const c = clearing(alert);
  const p = precedence(alert.severity);
  const ruledAfter = alert.deep ? between(alert.created_at, alert.deep.first_assessed_at ?? alert.deep.assessed_at) : null;
  const fastP = alert.fast ? precedence(alert.fast.severity) : null;
  const d = deep.data;
  const it = item.data;
  // The slip lists the checks behind the verdict, without repeating the sentence it already prints.
  const memoChecks = (d?.authenticity.reasons ?? []).filter((r) => !c.reason.toLowerCase().includes(r.toLowerCase()));
  const scale = claimedScale(alert.reasons);
  const actor = d?.attribution?.actor ?? null;
  const moneyEntries = Object.entries(d?.money ?? {});
  const cluster = moneyEntries.find(([, m]) => m.cluster_id)?.[1].cluster_id ?? null;
  const incident = d?.correlation?.incident ?? null;

  const acknowledge = async () => {
    setAcking(true);
    setAckError(null);
    try {
      patchAlert(await api.ack(alert.id));
    } catch (e) {
      setAckError(errorText(e));
    } finally {
      setAcking(false);
    }
  };

  const buildPack = async () => {
    setPack({ state: "building" });
    try {
      setPack({ state: "done", result: await api.buildPack(alert.item_id) });
    } catch (e) {
      setPack({ state: "error", error: errorText(e) });
    }
  };

  const factorKeys = [...new Set([...Object.keys(alert.factors ?? {}), ...Object.keys(alert.deep?.factors ?? {})])].filter(
    (k) => k in FACTOR_LABEL,
  );

  return (
    <article className="voucher" aria-labelledby="voucher-title">
      <div className="counterfoil">
        <span className="cf-no mono">{msgNo(alert.item_id)}</span>
        <PrecedenceTag severity={alert.severity} />
        <span className="cf-dtg mono" title={istFull(alert.first_seen)}>
          DTG {dtg(alert.first_seen)}
        </span>
        {alert.simulated ? <span className="sim-tag cf-sim">Simulated</span> : null}
        <span className={`cf-ack${alert.status === "new" ? " is-pending" : ""}`}>
          {alert.status === "new" ? "Awaiting acknowledgement" : alert.status === "acknowledged" ? "Acknowledged" : "Backfill"}
        </span>
      </div>

      <div className="v-body">
        <header className="v-head">
          <div className="v-titles">
            <h2 id="voucher-title">{alert.title}</h2>
            <p className="v-sub">
              {alert.categories[0]?.label ?? "Suspicious post"}
              {alert.orgs.length > 0 &&
                ` · ${alert.orgs.map((o) => `${o.org} (${sector(o.sector)}${o.city ? `, ${o.city}` : ""})`).join("; ")}`}
            </p>
          </div>
          <div className="v-stamp">
            <Stamp state={c.state} size="lg" landing={landing} tilt={tiltFor(alert.id) - 2} />
          </div>
        </header>

        <Section title="Clearing" note="The deep lane's verdict on the claim" id="sec-clearing">
          <div className="clearing">
            <div className={`memo memo--${c.state.toLowerCase()}`}>
              <p className="memo-head">
                {c.state === "RETURNED" ? "Return memo" : c.state === "CLEARED" ? "Clearing note" : "Awaiting the deep lane"}
              </p>
              <p className="memo-reason">
                {!c.reason.toLowerCase().startsWith(c.short.toLowerCase()) && <b>{c.short}. </b>}
                {c.reason}
              </p>
              {d && c.state !== "UNCLEARED" && memoChecks.length > 0 && (
                <ul className="memo-checks">
                  {memoChecks.map((r, i) => (
                    <li key={i}>{r.charAt(0).toUpperCase() + r.slice(1)}</li>
                  ))}
                </ul>
              )}
            </div>
            <dl className="lanes">
              <div>
                <dt>Fast lane, on capture</dt>
                <dd>
                  <span className="mono">{(fastP ?? p).name}</span>
                  <span className="pencil">
                    {" · score "}
                    <span className="mono">{(alert.fast?.score ?? alert.score).toFixed(1)}</span> of 100
                  </span>
                  <span className="lane-when">
                    {istDay(alert.created_at)} {istTime(alert.created_at)} IST
                  </span>
                </dd>
              </div>
              <div>
                <dt>Deep lane, on verdict</dt>
                <dd>
                  {alert.deep ? (
                    <>
                      <span className="mono">{precedence(alert.deep.severity).name}</span>
                      <span className="pencil">
                        {" · score "}
                        <span className="mono">{alert.deep.score.toFixed(1)}</span> of 100
                      </span>
                      <span className="lane-when">
                        {ruledAfter !== null && ruledAfter >= 0 && ruledAfter < 600
                          ? `Ruled ${seconds(ruledAfter)} after the fast lane`
                          : `Re-checked ${istDay(alert.deep.assessed_at)} ${istTime(alert.deep.assessed_at)} IST`}
                      </span>
                    </>
                  ) : (
                    <span className="pencil">Pending</span>
                  )}
                </dd>
              </div>
            </dl>
            {factorKeys.length > 0 && (
              <details className="detail">
                <summary>How the precedence was set</summary>
                <table className="factor-table">
                  <thead>
                    <tr>
                      <th scope="col">Factor</th>
                      <th scope="col">Fast</th>
                      <th scope="col">Deep</th>
                    </tr>
                  </thead>
                  <tbody>
                    {factorKeys.map((k) => (
                      <tr key={k}>
                        <th scope="row">{FACTOR_LABEL[k]}</th>
                        <td className="mono">{alert.factors?.[k] ?? "—"}</td>
                        <td className="mono">{alert.deep?.factors?.[k] ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {(alert.reasons?.length ?? 0) > 0 && (
                  <ul className="reason-list">
                    {alert.reasons?.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                )}
              </details>
            )}
          </div>
        </Section>

        <Section title="Facts" note="Observed by Libertas and sealed" id="sec-facts">
          <Facts>
            <Fact label="Source">
              {sourceLabel(alert.source_name)} · {kindLabel(alert.kind)}
              {alert.simulated ? <span className="sim-tag">Simulated</span> : null}
            </Fact>
            <Fact label="Address">
              <span className="mono break">{onionHost(alert.url)}</span>
            </Fact>
            <Fact label="Posted by">
              <span className="mono">{alert.author ?? "unknown"}</span>
              <span className="pencil"> (alias as shown on the site)</span>
            </Fact>
            <Fact label="Posted">{istFull(alert.posted_at)}</Fact>
            <Fact label="First captured">
              {istFull(alert.first_seen)}
              {alert.detection_lag_s !== null && <span className="pencil"> · {seconds(alert.detection_lag_s)} after posting</span>}
            </Fact>
            <Fact label="Capture SHA-256">
              <HashText value={alert.first_capture_sha} />
            </Fact>
            <Fact label="On the site">
              {alert.deleted_at ? (
                <span className="gone-fact">
                  Removed at {istTime(alert.deleted_at)} · online for {lifetime(alert.posted_at ?? alert.first_seen, alert.deleted_at)}
                </span>
              ) : it ? (
                <>Still online · last seen {ago(it.last_seen, now)}</>
              ) : (
                "—"
              )}
            </Fact>
            {it && it.versions.length > 1 && <Fact label="Edits">{it.versions.length} versions captured</Fact>}
            <Fact label="Identifiers">{it ? identifierSummary(it) : item.error ? "—" : "Loading"}</Fact>
            {scale !== null && (
              <Fact label="Claimed scale">
                {indian(scale)} records <span className="pencil">(the poster's claim, not verified)</span>
              </Fact>
            )}
          </Facts>
        </Section>

        <Section title="Leads" tone="pencil" note="Inferences to verify before action" id="sec-leads">
          {deep.loading && !d ? (
            <Loading label="Reading the deep lane" />
          ) : deep.error ? (
            <ErrorNote error={deep.error} retry={deep.reload} />
          ) : !d ? (
            <p className="pencil lead-empty">The deep lane has not ruled on this message yet. Leads appear here when it does.</p>
          ) : (
            <ul className="leads">
              <Lead
                title={
                  <>
                    Authenticity: {verdictLabel(d.authenticity.verdict)}, score <span className="mono">{d.authenticity.score.toFixed(2)}</span> of 1
                  </>
                }
              >
                <p className="lead-notes-p">The basis is on the clearing slip above: checksums, sample geography and the seller's history.</p>
              </Lead>
              {d.attribution?.links.slice(0, 2).map((l) => (
                <Lead
                  key={l.account_id}
                  truth={l.truth}
                  p={l.probability}
                  title={
                    <>
                      <span className="mono">{d.attribution?.alias}</span> is probably the same operator as{" "}
                      <span className="mono">{l.alias}</span> on {sourceLabel(l.source)}
                    </>
                  }
                >
                  <ul className="lead-notes">{evidenceLine(l)}</ul>
                </Lead>
              ))}
              {actor && (
                <Lead
                  truth={actor.truth}
                  p={actor.confidence}
                  title={
                    <>
                      Actor file <a href={href(["actors", actor.id])}>{actCode(actor.id)} {actor.label}</a>: {actor.members.length} aliases,{" "}
                      {actor.prior_items} earlier posts
                    </>
                  }
                >
                  {actor.prior_targets.length > 0 && <p className="lead-notes-p">Earlier targets: {actor.prior_targets.join(", ")}</p>}
                </Lead>
              )}
              {d.correlation?.escalation && (
                <Lead title={<>Escalation: {d.correlation.escalation.actor} has a new target, {d.correlation.escalation.new_targets.join(", ")}</>} />
              )}
              {moneyEntries.map(([wallet, m]) => (
                <Lead
                  key={wallet}
                  title={
                    <>
                      Wallet <span className="mono">{shortHash(wallet, 10, 6)}</span>{" "}
                      {m.cluster_id ? (
                        <>
                          sits in cluster{" "}
                          <a className="mono" href={href(["money", m.cluster_id])}>
                            {m.cluster_id}
                          </a>{" "}
                          ({m.size} addresses)
                        </>
                      ) : (
                        "has no cluster yet"
                      )}
                    </>
                  }
                >
                  <ul className="lead-notes">
                    {m.exposure.map((e) => (
                      <li key={e.entity}>
                        The cluster paid <span className="mono">{btc(e.sats)} BTC</span> to {e.entity} in {e.deposits.length} deposits
                      </li>
                    ))}
                    {m.flags.map((f) => (
                      <li key={f}>{f.charAt(0).toUpperCase() + f.slice(1)}</li>
                    ))}
                    <li>{m.note.charAt(0).toUpperCase() + m.note.slice(1)}.</li>
                  </ul>
                </Lead>
              ))}
              {d.correlation?.wallet_links.map((wl, i) => (
                <Lead key={`wl-${i}`} title={<>The same wallet cluster appears in {wl.items.length} other posts</>}>
                  <ul className="lead-notes">
                    {wl.items.slice(0, 4).map((x) => (
                      <li key={x.id}>
                        <a href={href(["log", x.id])}>{msgNo(x.id)}</a> by <span className="mono">{x.author}</span> on {sourceLabel(x.source)}
                      </li>
                    ))}
                  </ul>
                </Lead>
              ))}
              {incident && (
                <Lead
                  title={
                    <>
                      Part of incident <a href={href(["incidents", incident.id])}>{incCode(incident.id)}</a>: {incident.title}
                    </>
                  }
                />
              )}
            </ul>
          )}
        </Section>

        <Section title="Captured text" note="Text only, identifiers masked" id="sec-text">
          {it ? (
            <pre className="captured" tabIndex={0} aria-label="Captured text of the post, identifiers masked">
              {it.body_text || "(no text captured)"}
            </pre>
          ) : item.error ? (
            <ErrorNote error={item.error} retry={item.reload} />
          ) : (
            <Loading label="Opening the capture" />
          )}
        </Section>

        <Section title="Next actions" id="sec-next">
          <Recommended alert={alert} deep={d} item={it} />
          <div className="actions">
            {alert.status === "new" ? (
              <button type="button" className="btn btn--primary" onClick={acknowledge} disabled={acking}>
                <Check size={16} strokeWidth={2.25} aria-hidden />
                {acking ? "Acknowledging" : "Acknowledge"}
              </button>
            ) : (
              <span className="done-note">
                <Check size={15} aria-hidden /> {alert.status === "acknowledged" ? `Acknowledged ${istTime(alert.updated_at)}` : "Backfill entry"}
              </span>
            )}
            <button type="button" className="btn" onClick={buildPack} disabled={pack.state === "building"}>
              <FileText size={16} aria-hidden />
              {pack.state === "building" ? "Sealing and signing" : pack.state === "done" ? "Build another pack" : "Build evidence pack"}
            </button>
          </div>
          {ackError && <ErrorNote error={ackError} />}
          {pack.state === "error" && pack.error && <ErrorNote error={pack.error} retry={buildPack} />}
          {pack.state === "done" && pack.result && (
            <div className="pack-done" role="status">
              <p>
                <span className="mono">{pack.result.pack_id}</span> sealed: {pack.result.files} files, {pack.result.captures} captures,{" "}
                {pack.result.timestamped} of {pack.result.batches} batches carry an RFC 3161 timestamp.
              </p>
              <p className="pack-hash">
                Manifest <HashText value={pack.result.manifest_sha256} />
              </p>
              <a className="btn btn--sm" href={pack.result.download} download>
                <Download size={15} aria-hidden /> Download ZIP
              </a>
            </div>
          )}
          <ul className="follow">
            {actor && (
              <li>
                <a href={href(["actors", actor.id])}>
                  <UserSearch size={15} aria-hidden /> Actor file {actCode(actor.id)}
                </a>
              </li>
            )}
            <li>
              <a href={href(["graph"], { focus: `item:${alert.item_id}` })}>
                <Network size={15} aria-hidden /> Graph around this post
              </a>
            </li>
            {cluster && (
              <li>
                <a href={href(["money", cluster])}>
                  <Landmark size={15} aria-hidden /> Passbook {cluster}
                </a>
              </li>
            )}
            {incident && (
              <li>
                <a href={href(["incidents", incident.id])}>
                  <ArrowRight size={15} aria-hidden /> Incident {incCode(incident.id)}
                </a>
              </li>
            )}
            <li>
              <a href={href(["item", alert.item_id])}>
                <ArrowRight size={15} aria-hidden /> Full captured record
              </a>
            </li>
          </ul>
        </Section>
      </div>
    </article>
  );
}
