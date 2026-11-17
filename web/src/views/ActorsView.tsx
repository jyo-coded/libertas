import { ArrowLeft, Landmark, Network } from "lucide-react";
import { useMemo } from "react";
import { api, type AliasLink, type LinkEvidence } from "../api";
import { Empty, ErrorNote, Lead, Loading, PrecedenceTag, Section, ViewHeader } from "../components";
import { actCode, indicatorKind, istDay, msgNo, prob, sourceLabel, truthLabel } from "../format";
import { href, replaceRoute, useMedia, useResource } from "../hooks";
import { useSourceName, useStore } from "../store";

function EvidenceItem({ ev }: { ev: LinkEvidence }) {
  if (ev.family === "operational") {
    return (
      <li>
        <b>Shared {indicatorKind(ev.kind ?? "identifier")}</b> <span className="mono">{ev.display}</span>
        {ev.items && ev.items.length > 0 && (
          <span className="pencil">
            {" "}
            in {ev.items.slice(0, 6).map((i) => msgNo(i)).join(", ")}
            {ev.items.length > 6 ? ` and ${ev.items.length - 6} more` : ""}
          </span>
        )}
      </li>
    );
  }
  if (ev.family === "stylometry") {
    return (
      <li>
        <b>Writing style</b> {ev.similarity?.toFixed(3)} similar, z {ev.z?.toFixed(2)}, weight capped at {prob(ev.p)}
        {ev.distinctive_shared_phrases && ev.distinctive_shared_phrases.length > 0 && (
          <span className="phrases">
            Shared phrases:{" "}
            {ev.distinctive_shared_phrases.slice(0, 4).map((ph, i) => (
              <q key={i}>{ph}</q>
            ))}
          </span>
        )}
      </li>
    );
  }
  if (ev.family === "money") {
    return (
      <li>
        <b>Money</b> wallets fall in cluster{" "}
        {ev.cluster ? (
          <a className="mono" href={href(["money", ev.cluster])}>
            {ev.cluster}
          </a>
        ) : (
          "—"
        )}{" "}
        <span className="pencil">({ev.basis ?? "heuristic"})</span>
      </li>
    );
  }
  return <li>{ev.family}</li>;
}

export function ActorsView({ selectedId }: { selectedId: number | null }) {
  const { versions } = useStore();
  const sourceName = useSourceName();
  const actors = useResource(() => api.actors(), [versions.deep]);
  const links = useResource(() => api.links(), [versions.deep]);
  const wide = useMedia("(min-width: 761px)");
  const list = actors.data ?? [];
  const selected = list.find((a) => a.id === selectedId) ?? (wide && selectedId === null ? list[0] : undefined);
  const graph = useResource(
    () => (selected ? api.graph(`actor:${selected.id}`, 2) : Promise.resolve(null)),
    [selected?.id, versions.deep],
  );

  const memberLinks: AliasLink[] = useMemo(() => {
    if (!selected) return [];
    const ids = new Set(selected.members.map((m) => m.account_id));
    return (links.data ?? []).filter((l) => ids.has(l.a) && ids.has(l.b));
  }, [selected, links.data]);

  const posts = (graph.data?.nodes ?? [])
    .filter((n) => n.type === "item")
    .sort((a, b) => (b.first_seen ?? "").localeCompare(a.first_seen ?? ""));
  const clusters = [...new Set(memberLinks.flatMap((l) => l.evidence.filter((e) => e.family === "money" && e.cluster).map((e) => e.cluster as string)))];

  return (
    <div className={`split${!wide && selected ? " is-reading" : ""}`}>
      <section className="split-list" aria-labelledby="act-title">
        <ViewHeader title="Actors" latin="Stilus" />
        <p className="view-intro">Aliases that are probably one operator. Every file is a lead built from shared identifiers, writing style and money.</p>
        {actors.error && !actors.data ? (
          <ErrorNote error={actors.error} retry={actors.reload} />
        ) : !actors.data ? (
          <Loading label="Opening actor files" />
        ) : list.length === 0 ? (
          <Empty title="No actor files yet">A file opens when two aliases are linked by at least one evidence family.</Empty>
        ) : (
          <ol className="index-list" aria-label="Actor files">
            {list.map((a) => (
              <li key={a.id}>
                <a
                  href={href(["actors", a.id])}
                  className={`index-row${selected?.id === a.id ? " is-selected" : ""}`}
                  aria-current={selected?.id === a.id ? "true" : undefined}
                  onClick={(e) => {
                    e.preventDefault();
                    replaceRoute(href(["actors", a.id]));
                  }}
                >
                  <span className="mono index-code">{actCode(a.id)}</span>
                  <span className="index-main">
                    <span className="index-title mono">{a.label}</span>
                    <span className="index-meta">
                      {a.members.length} aliases · {a.truth} {truthLabel(a.truth).toLowerCase()} · P {prob(a.confidence)}
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
          <a className="back" href="#/actors">
            <ArrowLeft size={16} aria-hidden /> Actors
          </a>
        )}
        {selected ? (
          <article className="sheet sheet--lead" aria-labelledby="act-sheet-title">
            <header className="sheet-head">
              <span className="mono sheet-code">{actCode(selected.id)}</span>
              <h2 id="act-sheet-title" className="mono">
                {selected.label}
              </h2>
              <p className="sheet-sub">
                Lead, {selected.truth} {truthLabel(selected.truth).toLowerCase()}, P {prob(selected.confidence)}. Attribution is for investigation, not
                proof of identity; writing style alone is capped so it can never decide a link.
              </p>
            </header>

            <Section title="Aliases" note="As each site shows them">
              <table className="ledger">
                <thead>
                  <tr>
                    <th scope="col">Alias</th>
                    <th scope="col">Site</th>
                    <th scope="col" className="num">
                      Strongest link
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {selected.members.map((m) => (
                    <tr key={m.account_id}>
                      <td className="mono">{m.alias}</td>
                      <td>{sourceLabel(m.source)}</td>
                      <td className="mono num">P {prob(m.best_link)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Section>

            <Section title="Why these aliases are linked" tone="pencil" note="Each link, with the evidence behind it">
              {links.error && !links.data ? (
                <ErrorNote error={links.error} retry={links.reload} />
              ) : memberLinks.length === 0 ? (
                <p className="pencil">No pairwise links above the reporting threshold.</p>
              ) : (
                <ul className="leads">
                  {memberLinks.map((l) => (
                    <Lead
                      key={`${l.a}-${l.b}`}
                      truth={l.truth}
                      p={l.probability}
                      title={
                        <>
                          <span className="mono">{l.a_alias}</span> ({sourceName(l.a_source)}) and <span className="mono">{l.b_alias}</span> (
                          {sourceName(l.b_source)})
                        </>
                      }
                    >
                      <ul className="lead-notes evidence-notes">
                        {l.evidence.map((ev, i) => (
                          <EvidenceItem key={i} ev={ev} />
                        ))}
                      </ul>
                    </Lead>
                  ))}
                </ul>
              )}
            </Section>

            <Section title="Posts by these aliases" note="Captured facts, newest first">
              {graph.loading && !graph.data ? (
                <Loading label="Collecting posts" />
              ) : posts.length === 0 ? (
                <p className="pencil">No posts captured for these aliases.</p>
              ) : (
                <ul className="post-list">
                  {posts.map((n) => {
                    const id = Number(n.id.split(":")[1]);
                    return (
                      <li key={n.id}>
                        {n.severity && <PrecedenceTag severity={n.severity} />}
                        <a href={href(["log", id])} className="mono">
                          {msgNo(id)}
                        </a>
                        <span className="post-title">{n.label}</span>
                        <span className="pencil nowrap">{istDay(n.first_seen)}</span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </Section>

            <Section title="Next actions">
              <ul className="follow">
                <li>
                  <a href={href(["graph"], { focus: `actor:${selected.id}` })}>
                    <Network size={15} aria-hidden /> Graph around {actCode(selected.id)}
                  </a>
                </li>
                {clusters.map((c) => (
                  <li key={c}>
                    <a href={href(["money", c])}>
                      <Landmark size={15} aria-hidden /> Passbook {c}
                    </a>
                  </li>
                ))}
              </ul>
            </Section>
          </article>
        ) : wide && actors.data && list.length > 0 ? (
          <Empty title="Select an actor file">The aliases, the evidence that links them and their posts open here.</Empty>
        ) : null}
      </div>
    </div>
  );
}
