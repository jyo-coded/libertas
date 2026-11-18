import { useEffect } from "react";
import { api, type Rehearsal } from "../api";
import { Empty, ErrorNote, Fact, Facts, Loading, Section, ViewHeader } from "../components";
import { ago, istDay, istTime, seconds } from "../format";
import { useResource } from "../hooks";
import { useNow, useStore } from "../store";

const DRILL_LABEL: Record<string, string> = {
  "tor-down": "Tor client killed",
  "source-gone": "Source goes offline",
  captcha: "CAPTCHA wall",
  ratelimit: "Rate limit (HTTP 429)",
  randomise: "Randomised page markup",
  fastdelete: "Posts deleted after 60 s",
  killswitch: "Kill switch mid-run",
  deadline: "Ransomware deadline",
};

function streak(runs: Rehearsal[]): number {
  let n = 0;
  for (const r of runs) {
    if (!r.passed) break;
    n += 1;
  }
  return n;
}

export function ReadinessView() {
  const { status } = useStore();
  const now = useNow();
  const rehearsals = useResource(() => api.rehearsals(), []);
  const drills = useResource(() => api.drills(), []);
  const { reload: reloadR } = rehearsals;
  const { reload: reloadD } = drills;
  useEffect(() => {
    const t = window.setInterval(() => {
      reloadR();
      reloadD();
    }, 15_000);
    return () => window.clearInterval(t);
  }, [reloadR, reloadD]);

  const hb = status?.heartbeat;
  const tor = status?.tor;
  const runs = (rehearsals.data ?? []).slice(0, 5);
  const beats = runs[0]?.beats.map((b) => b.beat) ?? [];
  const passedInARow = streak(rehearsals.data ?? []);

  return (
    <div className="page">
      <ViewHeader title="Readiness" latin="Pulsus" />
      <p className="view-intro">
        Can Libertas be trusted right now? The heartbeat measures detection around the clock. Rehearsals run the demo end to end, and
        drills break things on purpose.
      </p>

      <Section title="Heartbeat" note="A canary onion that changes every minute">
        {!hb ? (
          <p className="pencil">The heartbeat starts once Libertas finds the canary onion in ShadowNet's registry.</p>
        ) : (
          <Facts>
            <Fact label="State">
              <span className={`readiness-state readiness-state--${hb.state === "ok" ? "ok" : hb.state === "starting" ? "idle" : "bad"}`}>
                {hb.state === "ok" ? "Beating" : hb.state === "starting" ? "Warming up" : hb.state}
              </span>
            </Fact>
            <Fact label="Latest detection">
              {hb.last_lag_s !== null ? (
                <>
                  <span className="mono">{seconds(hb.last_lag_s)}</span> from the canary changing to Libertas seeing it
                </>
              ) : (
                "Waiting for the first minute to turn over"
              )}
            </Fact>
            <Fact label="Median, p95">
              {hb.median_lag_s !== null ? (
                <span className="mono">
                  {seconds(hb.median_lag_s)}, {seconds(hb.p95_lag_s)}
                </span>
              ) : (
                "—"
              )}{" "}
              <span className="pencil">over {hb.samples} minutes</span>
            </Fact>
            {hb.recent_lags_s.length > 0 && (
              <Fact label="Last minutes">
                <span className="mono lag-row">{hb.recent_lags_s.map((l) => l.toFixed(1)).join("  ")}</span>
              </Fact>
            )}
            <Fact label="Canary">
              <span className="mono break">{hb.onion.slice(0, 10)}….onion</span> <span className="pencil">(public, read through Tor)</span>
            </Fact>
            {tor && (
              <Fact label="Tor client">
                {tor.state === "running" ? "Running" : tor.state}
                {tor.restarts > 0 && (
                  <span className="pencil">
                    {" "}
                    · restarted {tor.restarts}× by the watchdog, last outage {seconds(tor.last_outage_s)}{" "}
                    {tor.last_restart_at ? `(${ago(tor.last_restart_at, now)})` : ""}
                  </span>
                )}
              </Fact>
            )}
          </Facts>
        )}
      </Section>

      <Section
        title="Rehearsals"
        note={rehearsals.data && rehearsals.data.length > 0 ? `${passedInARow} passed in a row, newest first` : "The demo script, timed"}
      >
        {rehearsals.error && !rehearsals.data ? (
          <ErrorNote error={rehearsals.error} retry={rehearsals.reload} />
        ) : !rehearsals.data ? (
          <Loading label="Reading rehearsal results" />
        ) : runs.length === 0 ? (
          <Empty title="No rehearsals yet">
            Run <code>python scripts/rehearse.py --runs 3</code>. Each run is timed beat by beat and appears here.
          </Empty>
        ) : (
          <div className="table-wrap">
            <table className="ledger timing">
              <thead>
                <tr>
                  <th scope="col">Beat</th>
                  {runs.map((r) => (
                    <th scope="col" key={r.id} className="num">
                      {istDay(r.started_at)} {istTime(r.started_at)}
                      <span className={`run-result ${r.passed ? "is-pass" : "is-fail"}`}>{r.passed ? "Passed" : "Failed"}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {beats.map((beat) => (
                  <tr key={beat}>
                    <th scope="row">{beat}</th>
                    {runs.map((r) => {
                      const b = r.beats.find((x) => x.beat === beat);
                      return (
                        <td key={r.id} className={`num mono${b && !b.passed ? " fail" : ""}`} title={b?.detail}>
                          {b ? `${b.seconds.toFixed(1)} s${b.passed ? "" : ", failed"}` : "—"}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
            <ul className="beat-notes">
              {runs[0].beats.map((b) => (
                <li key={b.beat} className={b.passed ? "" : "fail"}>
                  <b>{b.beat}.</b> {b.detail}
                </li>
              ))}
            </ul>
          </div>
        )}
      </Section>

      <Section title="Failure drills" note="Broken on purpose, measured">
        {drills.error && !drills.data ? (
          <ErrorNote error={drills.error} retry={drills.reload} />
        ) : !drills.data ? (
          <Loading label="Reading drill results" />
        ) : drills.data.length === 0 ? (
          <Empty title="No drills yet">
            Run <code>python scripts/drills.py all</code> to break Tor, take a source offline and switch on ShadowNet's defences.
          </Empty>
        ) : (
          <div className="table-wrap">
            <table className="ledger">
              <thead>
                <tr>
                  <th scope="col">Drill</th>
                  <th scope="col">Result</th>
                  <th scope="col">What happened</th>
                  <th scope="col">When (IST)</th>
                </tr>
              </thead>
              <tbody>
                {drills.data.map((d) => (
                  <tr key={d.id}>
                    <td className="nowrap">{DRILL_LABEL[d.drill] ?? d.drill}</td>
                    <td className={d.passed ? "" : "fail"}>
                      <span className={`run-result ${d.passed ? "is-pass" : "is-fail"}`}>{d.passed ? "Passed" : "Failed"}</span>
                    </td>
                    <td>{d.summary}</td>
                    <td className="mono nowrap">
                      {istDay(d.started_at)} {istTime(d.started_at)}
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
