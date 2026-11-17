import { ArrowLeft, Download, FileText, Network } from "lucide-react";
import { useState } from "react";
import { api, ApiError, type BuiltPack, type Deep } from "../api";
import { ErrorNote, Fact, Facts, HashText, Lead, Loading, PrecedenceTag, Section } from "../components";
import {
  ago,
  errorText,
  indicatorKind,
  istFull,
  kindLabel,
  lifetime,
  msgNo,
  onionHost,
  seconds,
  verdictLabel,
} from "../format";
import { href, useResource } from "../hooks";
import { useNow, useSourceName, useStore } from "../store";

export function ItemView({ id }: { id: number }) {
  const { alerts, versions } = useStore();
  const now = useNow();
  const sourceName = useSourceName();
  const item = useResource(() => api.item(id), [id, versions.items]);
  const deep = useResource<Deep | null>(
    () =>
      api.deep(id).catch((e: unknown) => {
        if (e instanceof ApiError && e.status === 404) return null;
        throw e;
      }),
    [id, versions.deep],
  );
  const [pack, setPack] = useState<{ state: "idle" | "building" | "done" | "error"; result?: BuiltPack; error?: string }>({ state: "idle" });
  const alert = (alerts ?? []).find((a) => a.item_id === id);
  const it = item.data;
  const d = deep.data;

  if (item.error && !it) {
    return (
      <div className="page">
        <ErrorNote error={item.error.includes("404") || item.error === "Not Found" ? `No captured post ${msgNo(id)}.` : item.error} retry={item.reload} />
      </div>
    );
  }
  if (!it) {
    return (
      <div className="page">
        <Loading label={`Opening ${msgNo(id)}`} />
      </div>
    );
  }

  const buildPack = async () => {
    setPack({ state: "building" });
    try {
      setPack({ state: "done", result: await api.buildPack(id) });
    } catch (e) {
      setPack({ state: "error", error: errorText(e) });
    }
  };

  return (
    <div className="page">
      <a className="back" href="#/explorer">
        <ArrowLeft size={16} aria-hidden /> Explorer
      </a>
      <article className="sheet record" aria-labelledby="rec-title">
        <header className="sheet-head">
          <span className="mono sheet-code">{msgNo(it.id)}</span>
          <h1 id="rec-title" className="record-title">
            {it.title || "(untitled)"}
          </h1>
          <p className="sheet-sub">
            {kindLabel(it.kind)} on {sourceName(it.source_id)} by <span className="mono">{it.author ?? "unknown"}</span>
            {alert && (
              <>
                {" · "}
                <PrecedenceTag severity={alert.severity} /> <a href={href(["log", it.id])}>open in the message log</a>
              </>
            )}
          </p>
        </header>

        <Section title="Facts" note="Observed by Libertas and sealed">
          <Facts>
            <Fact label="Address">
              <span className="mono break">{onionHost(it.url)}</span>
            </Fact>
            <Fact label="Posted">{istFull(it.posted_at)}</Fact>
            <Fact label="First captured">
              {istFull(it.first_seen)}
              {it.detection_lag_s !== null && <span className="pencil"> · {seconds(it.detection_lag_s)} after posting</span>}
            </Fact>
            <Fact label="On the site">
              {it.deleted_at ? (
                <span className="gone-fact">
                  Removed {istFull(it.deleted_at)} · online for {lifetime(it.posted_at ?? it.first_seen, it.deleted_at)}
                </span>
              ) : (
                <>Still online · last seen {ago(it.last_seen, now)}</>
              )}
            </Fact>
            <Fact label="Content SHA-256">
              <HashText value={it.content_hash} />
            </Fact>
            <Fact label="First capture">
              <HashText value={it.first_capture_sha} />
            </Fact>
            {it.last_capture_sha && it.last_capture_sha !== it.first_capture_sha && (
              <Fact label="Latest capture">
                <HashText value={it.last_capture_sha} />
              </Fact>
            )}
          </Facts>
        </Section>

        <Section title="Captured text" note="Text only, identifiers masked">
          <pre className="captured captured--tall" tabIndex={0} aria-label="Captured text of the post, identifiers masked">
            {it.body_text || "(no text captured)"}
          </pre>
        </Section>

        <Section title="Identifiers found" note="Personal identifiers shown masked; the key is a keyed hash, never the value">
          {it.indicators.length === 0 ? (
            <p className="pencil">None found in this post.</p>
          ) : (
            <div className="table-wrap">
              <table className="ledger">
                <thead>
                  <tr>
                    <th scope="col">Kind</th>
                    <th scope="col">As shown</th>
                    <th scope="col">Check</th>
                    <th scope="col">Key</th>
                  </tr>
                </thead>
                <tbody>
                  {it.indicators.map((ind, i) => (
                    <tr key={i}>
                      <td>{indicatorKind(ind.kind)}</td>
                      <td className="mono break">{ind.display}</td>
                      <td>{ind.valid === null ? "—" : ind.valid ? "Passes" : <span className="fail">Fails</span>}</td>
                      <td className="mono pencil">{ind.sensitive ? ind.value : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>

        <Section title="Captures" note="Each read of this post through Tor, newest first">
          <div className="table-wrap">
            <table className="ledger">
              <thead>
                <tr>
                  <th scope="col">Fetched (IST)</th>
                  <th scope="col">Outcome</th>
                  <th scope="col" className="num">
                    Time
                  </th>
                  <th scope="col">SHA-256</th>
                  <th scope="col">Circuit</th>
                </tr>
              </thead>
              <tbody>
                {it.captures.map((c, i) => (
                  <tr key={i}>
                    <td className="mono nowrap">{istFull(c.fetched_at).replace(" IST", "")}</td>
                    <td>
                      {c.outcome}
                      {c.status ? <span className="mono pencil"> {c.status}</span> : null}
                    </td>
                    <td className="mono num">{c.elapsed_s !== null ? `${c.elapsed_s.toFixed(1)} s` : "—"}</td>
                    <td>
                      <HashText value={c.sha256} head={8} tail={4} />
                    </td>
                    <td className="mono pencil">{c.isolation_id ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {it.versions.length > 1 && (
            <p className="pencil table-note">
              {it.versions.length} versions of the text were captured; each is sealed separately.
            </p>
          )}
        </Section>

        {d && (
          <Section title="Leads" tone="pencil" note="Inferences to verify before action">
            <ul className="leads">
              <Lead
                title={
                  <>
                    Authenticity: {verdictLabel(d.authenticity.verdict)}, score <span className="mono">{d.authenticity.score.toFixed(2)}</span> of 1
                  </>
                }
              >
                <ul className="lead-notes">
                  {d.authenticity.reasons.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </Lead>
              {d.reasons.slice(1).map((r, i) => (
                <Lead key={i} title={r} />
              ))}
            </ul>
          </Section>
        )}

        <Section title="Next actions">
          <div className="actions">
            <button type="button" className="btn btn--primary" onClick={buildPack} disabled={pack.state === "building"}>
              <FileText size={16} aria-hidden />
              {pack.state === "building" ? "Sealing and signing" : "Build evidence pack"}
            </button>
            <a className="btn" href={href(["graph"], { focus: `item:${it.id}` })}>
              <Network size={16} aria-hidden /> Graph around this post
            </a>
          </div>
          {pack.state === "error" && pack.error && <ErrorNote error={pack.error} retry={buildPack} />}
          {pack.state === "done" && pack.result && (
            <div className="pack-done" role="status">
              <p>
                <span className="mono">{pack.result.pack_id}</span> sealed: {pack.result.files} files, {pack.result.timestamped} of {pack.result.batches}{" "}
                batches timestamped.
              </p>
              <a className="btn btn--sm" href={pack.result.download} download>
                <Download size={15} aria-hidden /> Download ZIP
              </a>
            </div>
          )}
        </Section>
      </article>
    </div>
  );
}
