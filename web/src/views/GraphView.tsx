import cytoscape, { type Core, type ElementDefinition, type StylesheetJson } from "cytoscape";
import { ArrowRight, Crosshair, Route, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, type GEdge, type GNode, type PathStep } from "../api";
import { Empty, ErrorNote, Loading, PrecedenceTag, ViewHeader } from "../components";
import { actCode, incCode, istFull, msgNo, prob, truthLabel } from "../format";
import { href, replaceRoute, useProjector, useResource } from "../hooks";
import { useStore } from "../store";

const TYPE_LABEL: Record<string, string> = {
  actor: "Actor (lead)", account: "Alias", item: "Post", org: "Organisation", source: "Site", wallet: "Wallet",
  cluster: "Wallet cluster", entity: "Exchange or service", incident: "Incident", indicator: "Identifier",
};

const isLead = (e: GEdge) =>
  e.probability !== undefined || /lead|linked|heuristic|sent .* to|part of/i.test(e.relation);

/** Canvas labels stay short enough to read on a projector: posts show their message number and a cleaned title. */
function canvasLabel(n: GNode): string {
  const clip = (t: string, max: number) => (t.length > max ? `${t.slice(0, max - 1).trimEnd()}…` : t);
  if (n.type === "item") {
    const title = n.label.replace(/^(\s*\[[^\]]*\]\s*)+/, "").trim();
    return `${msgNo(Number(n.id.split(":")[1]))}\n${clip(title, 44)}`;
  }
  if (n.type === "actor") return n.label.replace(/^Actor:\s*/, "Actor ");
  return clip(n.label.replace(/\s*\(SIM\)$/, ""), 40);
}

function token(name: string, fallback: string): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

function buildStyle(scale: number): StylesheetJson {
  const ink = token("--ink", "#1b2116");
  const pencil = token("--pencil", "#5b6169");
  const rail = token("--rail", "#2e3a24");
  const violet = token("--cleared", "#5b3fa0");
  const font = token("--font-sans", "sans-serif");
  const f = (px: number) => px * scale;
  return [
    {
      selector: "node",
      style: {
        label: "data(label)", "font-family": font, "font-size": f(12.5), color: ink, "text-valign": "bottom",
        "text-margin-y": f(4), "text-wrap": "wrap", "text-max-width": `${f(150)}px`, "line-height": 1.25,
        width: f(20), height: f(20),
        "background-color": "#ffffff", "border-width": 1.5, "border-color": ink, "text-background-color": "#eef1ea",
        "text-background-opacity": 0.85, "text-background-padding": "1px", "text-background-shape": "roundrectangle",
      },
    },
    { selector: 'node[type = "actor"]', style: { shape: "diamond", width: f(34), height: f(34), "background-color": rail, "border-color": rail, "font-weight": 600 } },
    { selector: 'node[type = "account"]', style: { shape: "ellipse", width: f(22), height: f(22) } },
    { selector: 'node[type = "item"]', style: { shape: "round-rectangle", width: f(26), height: f(18), "border-width": 2.5 } },
    { selector: 'node[severity = "CRITICAL"]', style: { "border-color": token("--flash", "#b42318") } },
    { selector: 'node[severity = "HIGH"]', style: { "border-color": token("--immediate", "#b54708") } },
    { selector: 'node[severity = "MEDIUM"]', style: { "border-color": token("--priority", "#1d4ed8") } },
    { selector: 'node[severity = "LOW"]', style: { "border-color": token("--routine", "#5b6169") } },
    { selector: 'node[type = "org"]', style: { shape: "hexagon", width: f(26), height: f(24), "background-color": "#f6f8f3", "border-color": pencil } },
    { selector: 'node[type = "source"]', style: { shape: "rectangle", width: f(26), height: f(18), "background-color": "#dfe5d6", "border-color": rail } },
    { selector: 'node[type = "wallet"]', style: { shape: "ellipse", width: f(13), height: f(13), "background-color": "#e9ece4", "border-color": pencil } },
    { selector: 'node[type = "cluster"]', style: { shape: "barrel", width: f(26), height: f(22), "background-color": "#e9ece4", "border-color": ink } },
    { selector: 'node[type = "entity"]', style: { shape: "tag", width: f(28), height: f(20), "border-width": 2 } },
    { selector: 'node[type = "incident"]', style: { shape: "round-tag", width: f(26), height: f(22), "background-color": "#f1ece0", "border-color": pencil } },
    { selector: 'node[type = "indicator"]', style: { width: f(10), height: f(10), "border-color": pencil, label: "" } },
    {
      selector: "edge",
      style: { width: 1.2, "line-color": "#9aa38f", "curve-style": "bezier", "font-family": font, "font-size": f(9), color: ink },
    },
    { selector: "edge[lead = 1]", style: { "line-style": "dashed", "line-dash-pattern": [5, 4], "line-color": pencil, width: 1.4 } },
    { selector: "edge[money = 1]", style: { "target-arrow-shape": "triangle", "target-arrow-color": pencil, "arrow-scale": 0.8 } },
    { selector: ".faded", style: { opacity: 0.18 } },
    {
      selector: "node:selected",
      style: { "underlay-color": ink, "underlay-opacity": 0.12, "underlay-padding": f(7), "border-width": 3 },
    },
    {
      selector: "edge.show-label",
      style: {
        label: "data(relation)", "text-rotation": "autorotate", "text-background-color": "#ffffff", "text-background-opacity": 0.92,
        "text-background-padding": "2px",
      },
    },
    { selector: "node.on-path", style: { "border-color": violet, "border-width": 3.5 } },
    { selector: "edge.on-path", style: { "line-color": violet, "line-style": "solid", width: 3.5, "z-index": 10, label: "data(relation)", "text-background-color": "#ffffff", "text-background-opacity": 0.92, "text-background-padding": "2px", "text-rotation": "autorotate", color: violet } },
  ] as StylesheetJson;
}

function openLink(n: GNode): { to: string; label: string } | null {
  const [type, id] = [n.id.slice(0, n.id.indexOf(":")), n.id.slice(n.id.indexOf(":") + 1)];
  if (type === "item") return { to: href(["log", id]), label: `Open ${msgNo(Number(id))}` };
  if (type === "actor") return { to: href(["actors", id]), label: `Open actor file ${actCode(Number(id))}` };
  if (type === "incident") return { to: href(["incidents", id]), label: `Open incident ${incCode(Number(id))}` };
  if (type === "cluster") return { to: href(["money", id]), label: `Open passbook ${id}` };
  return null;
}

export function GraphView({ focus: focusParam, depthParam }: { focus: string | null; depthParam: number }) {
  const { versions } = useStore();
  const projector = useProjector();
  const actors = useResource(() => api.actors(), [versions.deep]);
  const incidents = useResource(() => api.incidents(), [versions.deep]);
  const clusters = useResource(() => api.clusters(), [versions.deep]);
  const focus = focusParam ?? (actors.data?.[0] ? `actor:${actors.data[0].id}` : null);
  const depth = Math.min(3, Math.max(1, depthParam || 2));
  const graph = useResource(() => (focus ? api.graph(focus, depth) : Promise.resolve(null)), [focus, depth, versions.deep]);

  const box = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [selected, setSelected] = useState<GNode | null>(null);
  const [pathEnds, setPathEnds] = useState<{ a: GNode | null; b: GNode | null }>({ a: null, b: null });
  const [path, setPath] = useState<{ steps: PathStep[] | null; error: string | null; loading: boolean }>({ steps: null, error: null, loading: false });

  const data = graph.data;
  const nodeById = useMemo(() => new Map((data?.nodes ?? []).map((n) => [n.id, n])), [data]);
  const scale = projector ? 1.2 : 1;

  // Build the canvas whenever the subgraph changes.
  useEffect(() => {
    if (!box.current || !data || data.nodes.length === 0) return;
    // Hop distance from the focus decides the ring: the focus sits in the centre, each hop is one ring out.
    const hops = new Map<string, number>([[data.focus, 0]]);
    const adj = new Map<string, string[]>();
    for (const e of data.edges) {
      adj.set(e.source, [...(adj.get(e.source) ?? []), e.target]);
      adj.set(e.target, [...(adj.get(e.target) ?? []), e.source]);
    }
    const queue = [data.focus];
    while (queue.length) {
      const cur = queue.shift() as string;
      for (const nb of adj.get(cur) ?? []) {
        if (!hops.has(nb)) {
          hops.set(nb, (hops.get(cur) ?? 0) + 1);
          queue.push(nb);
        }
      }
    }
    const maxHop = Math.max(0, ...hops.values());
    const typeRank: Record<string, number> = { actor: 9, account: 8, source: 7, item: 6, org: 5, incident: 4, cluster: 3, wallet: 2, entity: 1 };
    const elements: ElementDefinition[] = [
      ...data.nodes.map((n) => ({
        data: {
          id: n.id, label: canvasLabel(n), type: n.type, severity: n.severity ?? "",
          ring: (maxHop - (hops.get(n.id) ?? maxHop)) + (typeRank[n.type] ?? 0) / 100,
        },
      })),
      ...data.edges.map((e, i) => ({
        data: {
          id: `e${i}`, source: e.source, target: e.target, relation: e.relation,
          lead: isLead(e) ? 1 : 0, money: /sent .* to/i.test(e.relation) ? 1 : 0,
        },
      })),
    ];
    const cy = cytoscape({
      container: box.current,
      elements,
      style: buildStyle(scale),
      layout: {
        name: "concentric", animate: false, padding: 40, startAngle: (3 / 2) * Math.PI, avoidOverlap: true,
        nodeDimensionsIncludeLabels: true, minNodeSpacing: 28, spacingFactor: 0.9,
        concentric: (n: cytoscape.NodeSingular) => n.data("ring") as number, levelWidth: () => 1,
      } as cytoscape.LayoutOptions,
      minZoom: 0.3,
      maxZoom: 2.5,
    });
    const focusNode = cy.getElementById(data.focus);
    if (focusNode.nonempty()) focusNode.select();
    cy.on("select", "node", (evt) => {
      const id = evt.target.id() as string;
      cy.elements().removeClass("faded show-label");
      const hood = evt.target.closedNeighborhood();
      cy.elements().difference(hood).addClass("faded");
      hood.edges().addClass("show-label");
      setSelected(nodeById.get(id) ?? null);
    });
    cy.on("unselect", "node", () => {
      cy.elements().removeClass("faded show-label");
      setSelected(null);
    });
    cyRef.current = cy;
    const ro = new ResizeObserver(() => cy.resize());
    ro.observe(box.current);
    return () => {
      ro.disconnect();
      cy.destroy();
      cyRef.current = null;
    };
  }, [data, nodeById, scale]);

  // Paint the evidence path in the reserved violet.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass("on-path");
    if (!path.steps) return;
    for (const s of path.steps) {
      cy.getElementById(s.from).addClass("on-path");
      cy.getElementById(s.to).addClass("on-path");
      cy.edges().filter((e) => (e.source().id() === s.from && e.target().id() === s.to) || (e.source().id() === s.to && e.target().id() === s.from)).addClass("on-path");
    }
  }, [path.steps, data]);

  useEffect(() => {
    const { a, b } = pathEnds;
    if (!a || !b || a.id === b.id) return;
    let live = true;
    setPath({ steps: null, error: null, loading: true });
    api.path(a.id, b.id).then(
      (r) => live && setPath({ steps: r.steps, error: null, loading: false }),
      (e: unknown) => live && setPath({ steps: null, error: String(e), loading: false }),
    );
    return () => {
      live = false;
    };
  }, [pathEnds]);

  const go = (nextFocus: string, nextDepth = depth) => {
    setSelected(null);
    setPathEnds({ a: null, b: null });
    setPath({ steps: null, error: null, loading: false });
    replaceRoute(href(["graph"], { focus: nextFocus, depth: String(nextDepth) }));
  };

  const neighbours = useMemo(() => {
    if (!selected || !data) return [];
    return data.edges
      .filter((e) => e.source === selected.id || e.target === selected.id)
      .map((e) => ({ edge: e, other: nodeById.get(e.source === selected.id ? e.target : e.source) }))
      .filter((x) => x.other);
  }, [selected, data, nodeById]);

  const focusKnown =
    !!focus &&
    ((actors.data ?? []).some((a) => `actor:${a.id}` === focus) ||
      (incidents.data ?? []).some((i) => `incident:${i.id}` === focus) ||
      (clusters.data ?? []).some((c) => `cluster:${c.id}` === focus));

  return (
    <div className="graph-view">
      <header className="graph-head">
        <ViewHeader title="Graph" latin="Nexus" />
        <div className="graph-controls">
          <label className="field">
            <span className="field-label">Around</span>
            <select value={focus ?? ""} onChange={(e) => go(e.target.value)} className="select">
              {!focusKnown && focus && <option value={focus}>{nodeById.get(focus)?.label ?? focus}</option>}
              <optgroup label="Actor files">
                {(actors.data ?? []).map((a) => (
                  <option key={a.id} value={`actor:${a.id}`}>
                    {actCode(a.id)} {a.label}
                  </option>
                ))}
              </optgroup>
              <optgroup label="Incidents">
                {(incidents.data ?? []).map((i) => (
                  <option key={i.id} value={`incident:${i.id}`}>
                    {incCode(i.id)} {i.org}
                  </option>
                ))}
              </optgroup>
              <optgroup label="Wallet clusters">
                {(clusters.data ?? []).map((c) => (
                  <option key={c.id} value={`cluster:${c.id}`}>
                    {c.id} ({c.size} addresses)
                  </option>
                ))}
              </optgroup>
            </select>
          </label>
          <div className="seg" role="group" aria-label="Depth in hops">
            {[1, 2, 3].map((d) => (
              <button key={d} type="button" className="seg-btn" aria-pressed={depth === d} onClick={() => focus && go(focus, d)}>
                {d} {d === 1 ? "hop" : "hops"}
              </button>
            ))}
          </div>
        </div>
      </header>

      <div className="graph-body">
        <div className="graph-canvas-wrap">
          {graph.error && !data ? (
            <ErrorNote error={graph.error} retry={graph.reload} />
          ) : !focus || (graph.loading && !data) ? (
            <Loading label="Drawing the graph" />
          ) : data && data.nodes.length === 0 ? (
            <Empty title="Nothing to draw around this node">{data.error ?? "It has no recorded connections yet."}</Empty>
          ) : (
            <div className="graph-canvas" ref={box} role="img" aria-label={`Relationship graph around ${nodeById.get(focus)?.label ?? focus}: ${data?.nodes.length ?? 0} nodes, ${data?.edges.length ?? 0} connections. The panel beside it lists the selected node's connections as text.`} />
          )}
          <ul className="graph-legend" aria-label="Legend">
            <li>
              <span className="lg-line" aria-hidden /> Observed fact
            </li>
            <li>
              <span className="lg-line lg-line--lead" aria-hidden /> Lead (inferred)
            </li>
            <li>
              <span className="lg-line lg-line--path" aria-hidden /> Evidence path
            </li>
            <li>
              <span className="lg-shape lg-shape--actor" aria-hidden /> Actor
            </li>
            <li>
              <span className="lg-shape lg-shape--item" aria-hidden /> Post, edged by precedence
            </li>
          </ul>
        </div>

        <aside className="graph-side" aria-label="Selected node and evidence path">
          {selected ? (
            <section className="gs-node">
              <h2 className="gs-label">{selected.label}</h2>
              <p className="gs-type">{TYPE_LABEL[selected.type] ?? selected.type}</p>
              <dl className="gs-facts">
                {selected.severity && (
                  <div>
                    <dt>Precedence</dt>
                    <dd>
                      <PrecedenceTag severity={selected.severity} /> <span className="mono">{selected.score?.toFixed(1)}</span>
                    </dd>
                  </div>
                )}
                {selected.truth && (
                  <div>
                    <dt>Truth level</dt>
                    <dd>
                      {selected.truth} {truthLabel(selected.truth)}
                    </dd>
                  </div>
                )}
                {selected.first_seen && (
                  <div>
                    <dt>First seen</dt>
                    <dd>{istFull(selected.first_seen)}</dd>
                  </div>
                )}
              </dl>
              <div className="gs-actions">
                {openLink(selected) && (
                  <a className="btn btn--sm" href={openLink(selected)!.to}>
                    <ArrowRight size={15} aria-hidden /> {openLink(selected)!.label}
                  </a>
                )}
                {selected.id !== data?.focus && (
                  <button type="button" className="btn btn--sm" onClick={() => go(selected.id)}>
                    <Crosshair size={15} aria-hidden /> Centre here
                  </button>
                )}
                <button type="button" className="btn btn--sm" onClick={() => setPathEnds((p) => ({ ...p, a: selected }))}>
                  <Route size={15} aria-hidden /> Path from here
                </button>
                <button type="button" className="btn btn--sm" onClick={() => setPathEnds((p) => ({ ...p, b: selected }))}>
                  <Route size={15} aria-hidden /> Path to here
                </button>
              </div>
              <h3 className="gs-h">Connections</h3>
              <ul className="gs-links">
                {neighbours.map(({ edge, other }, i) => (
                  <li key={i} className={isLead(edge) ? "is-lead" : ""}>
                    <span className="gs-rel">{edge.relation}</span>{" "}
                    <button
                      type="button"
                      className="link-btn"
                      onClick={() => {
                        const cy = cyRef.current;
                        if (!cy) return;
                        cy.getElementById(selected.id).unselect();
                        cy.getElementById(other!.id).select();
                      }}
                    >
                      {other!.label}
                    </button>
                    {edge.probability !== undefined && <span className="mono pencil"> P {prob(edge.probability)}</span>}
                  </li>
                ))}
              </ul>
            </section>
          ) : (
            <p className="gs-hint">Select a node to read its connections. Dashed lines are leads; solid lines are what Libertas observed.</p>
          )}

          <section className="gs-path" aria-labelledby="gs-path-title">
            <h3 id="gs-path-title" className="gs-h">
              Evidence path
            </h3>
            <p className="gs-ends">
              <span>{pathEnds.a ? pathEnds.a.label : <span className="pencil">Choose a start</span>}</span>
              <ArrowRight size={14} aria-hidden />
              <span>{pathEnds.b ? pathEnds.b.label : <span className="pencil">Choose an end</span>}</span>
              {(pathEnds.a || pathEnds.b) && (
                <button
                  type="button"
                  className="icon-btn"
                  aria-label="Clear the evidence path"
                  onClick={() => {
                    setPathEnds({ a: null, b: null });
                    setPath({ steps: null, error: null, loading: false });
                  }}
                >
                  <X size={14} aria-hidden />
                </button>
              )}
            </p>
            {path.loading && <Loading label="Tracing" />}
            {path.error && <ErrorNote error={path.error} />}
            {path.steps && path.steps.length === 0 && <p className="pencil">No chain of recorded links joins these two.</p>}
            {path.steps && path.steps.length > 0 && (
              <ol className="path-steps">
                {path.steps.map((s, i) => (
                  <li key={i}>
                    <span>{s.from_label}</span>
                    <span className="path-rel">
                      {s.relation}
                      {s.probability !== undefined && <span className="mono"> · P {prob(s.probability)}</span>}
                      {s.truth && <span> · {s.truth}</span>}
                    </span>
                    <span>{s.to_label}</span>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}
