import { api } from "../api";
import { Empty, ErrorNote, Loading, Section, ViewHeader } from "../components";
import { ago, istTime, kindLabel, seconds } from "../format";
import { useResource } from "../hooks";
import { useNow, useSourceName, useStore } from "../store";

const yesNo = (v: boolean | number | null | undefined) => (v === null || v === undefined ? "—" : v ? "Yes" : "No");

export function SourcesView() {
  const { status, statusError, refreshStatus, versions } = useStore();
  const now = useNow();
  const sourceName = useSourceName();
  const descriptors = useResource(() => api.descriptors(), [versions.sources]);

  return (
    <div className="page">
      <ViewHeader title="Sources" latin="Speculatores" />
      <p className="view-intro">
        Allowlisted onion services, read through Tor with GET requests only. Pulsus fetches each service's descriptor separately, so an outage
        or a defence change shows before a page fails.
      </p>

      <Section title="Watch list" note={status?.ttd ? `Median time to detect ${seconds(status.ttd.median_s)}, p95 ${seconds(status.ttd.p95_s)} over ${status.ttd.n} posts` : undefined}>
        {statusError && !status ? (
          <ErrorNote error={statusError} retry={refreshStatus} />
        ) : !status ? (
          <Loading label="Reading source health" />
        ) : status.sources.length === 0 ? (
          <Empty title="No sources allowlisted">Lex blocks every fetch until a source is allowlisted.</Empty>
        ) : (
          <div className="table-wrap">
            <table className="ledger">
              <thead>
                <tr>
                  <th scope="col">Site</th>
                  <th scope="col">State</th>
                  <th scope="col">Last pulse</th>
                  <th scope="col" className="num">
                    Pulses
                  </th>
                  <th scope="col">Descriptor</th>
                  <th scope="col" className="num">
                    Posts
                  </th>
                  <th scope="col">Circuit</th>
                </tr>
              </thead>
              <tbody>
                {status.sources.map((s) => {
                  const h = s.health ?? {};
                  const d = h.descriptor;
                  return (
                    <tr key={s.id}>
                      <td>
                        {sourceName(s.id)}
                        <span className="cell-sub">
                          {kindLabel(s.kind)} · <span className="mono">{s.onion.slice(0, 10)}…onion</span>
                        </span>
                      </td>
                      <td>
                        <span className={`health-state${h.state === "watching" ? "" : " is-bad"}`}>
                          <span className="health-dot" aria-hidden />
                          {h.state ?? "starting"}
                        </span>
                        {h.consecutive_failures ? <span className="cell-sub">{h.consecutive_failures} failures in a row</span> : null}
                        {h.wall && (
                          <span className="cell-sub">
                            Wall since {istTime(h.wall.since)}: {h.wall.detail}, {h.wall.hits} {h.wall.hits === 1 ? "refusal" : "refusals"}
                          </span>
                        )}
                        {h.throttled_until && new Date(h.throttled_until).getTime() > now && (
                          <span className="cell-sub">Slowed to one request every {h.throttle_gap_s ?? 3} s until {istTime(h.throttled_until)} (site rate limit)</span>
                        )}
                        {h.drift && (
                          <span className="cell-sub fail">
                            Layout drift: {h.drift.count} {h.drift.count === 1 ? "page" : "pages"} no longer parse; nothing is guessed until an
                            analyst checks the adapter
                          </span>
                        )}
                        {h.deadline_watch && (
                          <span className="cell-sub">
                            Countdown on “{h.deadline_watch.title}” ends {istTime(h.deadline_watch.deadline)}: polling every{" "}
                            {h.deadline_watch.interval_s} s
                          </span>
                        )}
                      </td>
                      <td className="nowrap">
                        {h.last_pulse_at ? ago(h.last_pulse_at, now) : "—"}
                        {h.last_pulse_s ? <span className="cell-sub mono">{h.last_pulse_s.toFixed(2)} s · {h.last_outcome}</span> : null}
                      </td>
                      <td className="mono num">{h.pulses ?? 0}</td>
                      <td>
                        {d ? (
                          <>
                            {d.result === "RECEIVED" ? "Received" : d.result}
                            <span className="cell-sub">
                              {d.private ? "Client authorisation required" : `${d.intro_points ?? "—"} intro points · PoW ${d.pow_enabled ? "on" : "off"}`}
                            </span>
                          </>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="mono num">{s.items}</td>
                      <td className="mono pencil">{h.isolation_id ?? "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section title="Descriptor log" note="Pulsus observations, newest first">
        {descriptors.error && !descriptors.data ? (
          <ErrorNote error={descriptors.error} retry={descriptors.reload} />
        ) : !descriptors.data ? (
          <Loading label="Reading the descriptor log" />
        ) : descriptors.data.length === 0 ? (
          <Empty title="No descriptor observations yet">Pulsus runs every few minutes per source.</Empty>
        ) : (
          <div className="table-wrap">
            <table className="ledger ledger--dense">
              <thead>
                <tr>
                  <th scope="col">Observed (IST)</th>
                  <th scope="col">Site</th>
                  <th scope="col">Result</th>
                  <th scope="col" className="num">
                    Time
                  </th>
                  <th scope="col" className="num">
                    Intro points
                  </th>
                  <th scope="col">PoW</th>
                  <th scope="col">Client auth</th>
                </tr>
              </thead>
              <tbody>
                {descriptors.data.map((d) => (
                  <tr key={d.id}>
                    <td className="mono nowrap">{istTime(d.observed_at)}</td>
                    <td>{sourceName(d.source_id ?? "")}</td>
                    <td>
                      {d.result}
                      {d.error && <span className="cell-sub">{d.error}</span>}
                    </td>
                    <td className="mono num">{d.seconds !== null ? `${d.seconds.toFixed(2)} s` : "—"}</td>
                    <td className="mono num">{d.intro_points ?? "—"}</td>
                    <td>{d.pow_enabled === null ? "—" : d.pow_enabled ? `On, effort ${d.pow_effort ?? 0}` : "Off"}</td>
                    <td>{yesNo(d.private)}</td>
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
