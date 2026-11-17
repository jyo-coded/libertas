import { Search } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { Empty, ErrorNote, Loading, ViewHeader } from "../components";
import { istDay, istTime, kindLabel, msgNo } from "../format";
import { href, replaceRoute, useResource } from "../hooks";
import { useSourceName, useStore } from "../store";

export function ExplorerView({ q, source }: { q: string; source: string }) {
  const { status, versions } = useStore();
  const sourceName = useSourceName();
  const [draft, setDraft] = useState(q);
  useEffect(() => setDraft(q), [q]);
  const res = useResource(() => api.items(q, source), [q, source, versions.items]);

  const submit = (nextQ: string, nextSource: string) => {
    const query: Record<string, string> = {};
    if (nextQ.trim()) query.q = nextQ.trim();
    if (nextSource) query.source = nextSource;
    replaceRoute(href(["explorer"], query));
  };

  return (
    <div className="page">
      <ViewHeader title="Explorer" latin="Interpres" />
      <p className="view-intro">Search every captured post by words in its title or text. Results are text records; no page is ever rendered.</p>
      <form
        className="search"
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          submit(draft, source);
        }}
      >
        <label className="field field--grow">
          <span className="field-label">Words</span>
          <span className="search-box">
            <Search size={16} aria-hidden />
            <input
              type="search"
              className="input"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Organisation, alias, wallet, phrase"
              autoComplete="off"
              spellCheck={false}
            />
          </span>
        </label>
        <label className="field">
          <span className="field-label">Site</span>
          <select className="select" value={source} onChange={(e) => submit(draft, e.target.value)}>
            <option value="">All sites</option>
            {(status?.sources ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {sourceName(s.id)}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className="btn btn--primary">
          Search
        </button>
      </form>

      {res.error && !res.data ? (
        <ErrorNote error={res.error} retry={res.reload} />
      ) : !res.data ? (
        <Loading label="Searching captures" />
      ) : res.data.length === 0 ? (
        <Empty title={q ? `Nothing captured matches “${q}”` : "No posts captured yet"}>
          {q ? "Try an organisation name, an alias or part of a wallet address." : "Posts appear here as soon as a source is read."}
        </Empty>
      ) : (
        <>
          <p className="result-count" role="status">
            {res.data.length} {res.data.length === 1 ? "post" : "posts"}
            {q && <> matching “{q}”</>}
            {source && <> on {sourceName(source)}</>}
          </p>
          <div className="table-wrap">
            <table className="ledger ledger--rows">
              <thead>
                <tr>
                  <th scope="col">Message</th>
                  <th scope="col">Post</th>
                  <th scope="col">Site</th>
                  <th scope="col">Alias</th>
                  <th scope="col">First seen (IST)</th>
                  <th scope="col">On site</th>
                </tr>
              </thead>
              <tbody>
                {res.data.map((it) => (
                  <tr key={it.id}>
                    <td className="mono nowrap">
                      <a href={href(["item", it.id])}>{msgNo(it.id)}</a>
                    </td>
                    <td>
                      <a href={href(["item", it.id])}>{it.title || "(untitled)"}</a>
                      <span className="cell-sub">{kindLabel(it.kind)}</span>
                    </td>
                    <td className="nowrap">{sourceName(it.source_id)}</td>
                    <td className="mono">{it.author ?? "—"}</td>
                    <td className="mono nowrap">
                      {istDay(it.first_seen)} {istTime(it.first_seen)}
                    </td>
                    <td>{it.deleted_at ? <span className="gone-fact">Removed</span> : "Online"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
