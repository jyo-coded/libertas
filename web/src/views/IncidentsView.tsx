import { ArrowLeft, Network } from "lucide-react";
import { api } from "../api";
import { Empty, ErrorNote, Lead, Loading, Section, ViewHeader } from "../components";
import { incCode, istDay, istFull, istTime, msgNo } from "../format";
import { href, replaceRoute, useMedia, useResource } from "../hooks";
import { useSourceName, useStore } from "../store";

export function IncidentsView({ selectedId }: { selectedId: number | null }) {
  const { versions } = useStore();
  const sourceName = useSourceName();
  const res = useResource(() => api.incidents(), [versions.deep]);
  const wide = useMedia("(min-width: 761px)");
  const list = res.data ?? [];
  const selected = list.find((i) => i.id === selectedId) ?? (wide && selectedId === null ? list[0] : undefined);

  return (
    <div className={`split${!wide && selected ? " is-reading" : ""}`}>
      <section className="split-list" aria-labelledby="inc-title">
        <ViewHeader title="Incidents" latin="Codex" />
        <p className="view-intro">Posts that name the same organisation, grouped across sites. One incident is one victim's case file.</p>
        {res.error && !res.data ? (
          <ErrorNote error={res.error} retry={res.reload} />
        ) : !res.data ? (
          <Loading label="Opening the case files" />
        ) : list.length === 0 ? (
          <Empty title="No incidents yet">An incident opens when two or more posts name the same organisation.</Empty>
        ) : (
          <ol className="index-list" aria-label="Incidents, most recent first">
            {list.map((inc) => (
              <li key={inc.id}>
                <a
                  href={href(["incidents", inc.id])}
                  className={`index-row${selected?.id === inc.id ? " is-selected" : ""}`}
                  aria-current={selected?.id === inc.id ? "true" : undefined}
                  onClick={(e) => {
                    e.preventDefault();
                    replaceRoute(href(["incidents", inc.id]));
                  }}
                >
                  <span className="mono index-code">{incCode(inc.id)}</span>
                  <span className="index-main">
                    <span className="index-title">{inc.org}</span>
                    <span className="index-meta">
                      {inc.item_ids.length} posts · {inc.sources.length} {inc.sources.length === 1 ? "site" : "sites"} · last {istDay(inc.last_seen)}{" "}
                      {istTime(inc.last_seen)}
                    </span>
                  </span>
                </a>
              </li>
            ))}
          </ol>
        )}
      </section>

      <div className="split-detail">
        {!wide && selected && (
          <a className="back" href="#/incidents">
            <ArrowLeft size={16} aria-hidden /> Incidents
          </a>
        )}
        {selected ? (
          <article className="sheet" aria-labelledby="inc-sheet-title">
            <header className="sheet-head">
              <span className="mono sheet-code">{incCode(selected.id)}</span>
              <h2 id="inc-sheet-title">{selected.org}</h2>
              <p className="sheet-sub">
                {selected.item_ids.length} posts across {selected.sources.map(sourceName).join(", ")} · first seen {istFull(selected.first_seen)}
              </p>
            </header>
            <Section title="Timeline" note="Each post as captured, oldest first">
              <table className="ledger">
                <thead>
                  <tr>
                    <th scope="col">First seen (IST)</th>
                    <th scope="col">Message</th>
                    <th scope="col">Site</th>
                    <th scope="col">Post</th>
                    <th scope="col">On site</th>
                  </tr>
                </thead>
                <tbody>
                  {selected.summary.timeline.map((t) => (
                    <tr key={t.item_id}>
                      <td className="mono nowrap">
                        {istDay(t.first_seen)} {istTime(t.first_seen)}
                      </td>
                      <td className="mono nowrap">
                        <a href={href(["log", t.item_id])}>{msgNo(t.item_id)}</a>
                      </td>
                      <td>{sourceName(t.source)}</td>
                      <td>
                        <a href={href(["item", t.item_id])}>{t.title}</a>
                        <span className="cell-sub">{t.category}</span>
                      </td>
                      <td>{t.deleted ? <span className="gone-fact">Removed</span> : "Online"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Section>
            {selected.summary.shared_datasets.length > 0 && (
              <Section title="Leads" tone="pencil" note="Inferences to verify before action">
                <ul className="leads">
                  {selected.summary.shared_datasets.map((sd, i) => (
                    <Lead
                      key={i}
                      title={
                        <>
                          {sd.items.map((x, j) => (
                            <span key={x}>
                              {j > 0 && " and "}
                              <a href={href(["item", x])}>{msgNo(x)}</a>
                            </span>
                          ))}{" "}
                          share {sd.shared_identifiers} sample identifiers
                        </>
                      }
                    >
                      <p className="lead-notes-p">{sd.note.charAt(0).toUpperCase() + sd.note.slice(1)}: one dataset resold under different names.</p>
                    </Lead>
                  ))}
                </ul>
              </Section>
            )}
            <Section title="Next actions">
              <ul className="follow">
                <li>
                  <a href={href(["graph"], { focus: `incident:${selected.id}` })}>
                    <Network size={15} aria-hidden /> Graph around this incident
                  </a>
                </li>
                <li>
                  <a href={href(["log", selected.item_ids[selected.item_ids.length - 1]])}>Open the latest message and build its evidence pack</a>
                </li>
              </ul>
            </Section>
          </article>
        ) : wide && res.data && list.length > 0 ? (
          <Empty title="Select an incident">Its timeline and leads open here.</Empty>
        ) : null}
      </div>
    </div>
  );
}
