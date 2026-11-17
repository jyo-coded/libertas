import { ArrowLeft, Network } from "lucide-react";
import { api } from "../api";
import { Empty, ErrorNote, HashText, Lead, Loading, Section, ViewHeader } from "../components";
import { btc, istTime, msgNo, passbookDate, shortHash } from "../format";
import { href, replaceRoute, useMedia, useResource } from "../hooks";
import { useSourceName, useStore } from "../store";

const HEURISTIC_NOTE: Record<string, string> = {
  "common-input ownership": "spent together in one transaction",
  "consolidation sweep": "swept together into one address",
};

export function MoneyView({ selectedId }: { selectedId: string | null }) {
  const { versions } = useStore();
  const sourceName = useSourceName();
  const clusters = useResource(() => api.clusters(), [versions.deep]);
  const wide = useMedia("(min-width: 761px)");
  const list = clusters.data ?? [];
  const chosen = list.find((c) => c.id === selectedId) ?? (wide && selectedId === null ? list[0] : undefined);
  const ledger = useResource(() => (chosen ? api.ledger(chosen.id) : Promise.resolve(null)), [chosen?.id, versions.deep]);
  const lg = ledger.data;
  // Totals on a net basis, the way a passbook prints them: change returning to the cluster is not income.
  const totals = (lg?.entries ?? []).reduce(
    (t, e) => {
      const net = e.credit_sats - e.debit_sats;
      return { debit: t.debit + Math.max(0, -net), credit: t.credit + Math.max(0, net) };
    },
    { debit: 0, credit: 0 },
  );

  return (
    <div className={`split split--wide-detail${!wide && chosen ? " is-reading" : ""}`}>
      <section className="split-list" aria-labelledby="money-title">
        <ViewHeader title="Money" latin="Moneta" />
        <p className="view-intro">
          Wallet clusters seeded from addresses in posts, traced on the chain through Esplora. Each cluster reads like a passbook.
        </p>
        {clusters.error && !clusters.data ? (
          <ErrorNote error={clusters.error} retry={clusters.reload} />
        ) : !clusters.data ? (
          <Loading label="Opening passbooks" />
        ) : list.length === 0 ? (
          <Empty title="No wallet clusters yet">A cluster opens when a post carries a Bitcoin address that has moved money.</Empty>
        ) : (
          <ol className="index-list" aria-label="Wallet clusters">
            {list.map((c) => (
              <li key={c.id}>
                <a
                  href={href(["money", c.id])}
                  className={`index-row${chosen?.id === c.id ? " is-selected" : ""}`}
                  aria-current={chosen?.id === c.id ? "true" : undefined}
                  onClick={(e) => {
                    e.preventDefault();
                    replaceRoute(href(["money", c.id]));
                  }}
                >
                  <span className="mono index-code">{c.id}</span>
                  <span className="index-main">
                    <span className="index-title">
                      {c.size} {c.size === 1 ? "address" : "addresses"}{c.exposure.length > 0 ? ` · paid ${c.exposure.map((e) => e.entity.split(" (")[0]).join(", ")}` : ""}
                    </span>
                    <span className="index-meta">
                      Seen in {c.seen_in_items.length} {c.seen_in_items.length === 1 ? "post" : "posts"}
                      {c.peel_chains.length > 0 && ` · ${c.peel_chains.length} peel ${c.peel_chains.length === 1 ? "chain" : "chains"}`}
                    </span>
                  </span>
                </a>
              </li>
            ))}
          </ol>
        )}
      </section>

      <div className="split-detail">
        {!wide && chosen && (
          <a className="back" href="#/money">
            <ArrowLeft size={16} aria-hidden /> Money
          </a>
        )}
        {!chosen ? (
          wide && clusters.data && list.length > 0 ? <Empty title="Select a cluster">Its passbook opens here.</Empty> : null
        ) : ledger.error && !lg ? (
          <ErrorNote error={ledger.error} retry={ledger.reload} />
        ) : !lg ? (
          <Loading label="Writing up the passbook" />
        ) : (
          <article className="passbook" aria-labelledby="pb-title">
            <header className="pb-head">
              <div>
                <h2 id="pb-title">
                  Passbook <span className="mono">{lg.cluster.id}</span>
                </h2>
                <p className="pb-sub">
                  {lg.cluster.size} addresses on {lg.cluster.chain.toLowerCase() === "btc" ? "Bitcoin" : lg.cluster.chain}
                  {lg.cluster.chain.toLowerCase() === "btc" && " (regtest simulation)"} · holder unknown · clustering is a lead, not proof of common ownership
                </p>
              </div>
              <dl className="pb-totals">
                <div>
                  <dt>Total received</dt>
                  <dd className="mono">{btc(totals.credit)}</dd>
                </div>
                <div>
                  <dt>Total paid out</dt>
                  <dd className="mono">{btc(totals.debit)}</dd>
                </div>
                <div>
                  <dt>Balance</dt>
                  <dd className="mono">{btc(totals.credit - totals.debit)}</dd>
                </div>
              </dl>
            </header>

            <div className="pb-table-wrap" tabIndex={0} aria-label="Passbook entries, scrolls sideways on small screens">
              <table className="pb-table">
                <caption className="sr">Transactions touching cluster {lg.cluster.id}, oldest first, amounts in BTC</caption>
                <thead>
                  <tr>
                    <th scope="col">Date (IST)</th>
                    <th scope="col">Particulars</th>
                    <th scope="col">Txn ref.</th>
                    <th scope="col" className="num">
                      Withdrawals
                    </th>
                    <th scope="col" className="num">
                      Deposits
                    </th>
                    <th scope="col" className="num">
                      Balance
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {lg.entries.map((e) => {
                    const net = e.credit_sats - e.debit_sats;
                    const detail: string[] = [];
                    if (e.entity_sats) detail.push(`${btc(e.entity_sats)} to the exchange`);
                    else if (e.debit_sats && e.external_sats) detail.push(`${btc(e.external_sats)} to outside addresses`);
                    if (e.debit_sats && e.credit_sats) detail.push(`${btc(e.credit_sats)} change back to the cluster`);
                    if (e.fee_sats) detail.push(`fee ${btc(e.fee_sats)}`);
                    return (
                      <tr key={e.txid} className={e.entity ? "is-exit" : ""}>
                        <td className="mono nowrap">
                          {passbookDate(e.time)}
                          <span className="cell-sub">{istTime(e.time)}</span>
                        </td>
                        <td>
                          {e.particulars.replace(/\s*\(.*\)$/, "")}
                          {e.peel && <span className="peel-tag">Peel hop</span>}
                          <span className="cell-sub">
                            {detail.length > 0 && <span className="mono">{detail.join(" · ")} · </span>}
                            <span className="mono">block {e.height}</span>
                          </span>
                        </td>
                        <td className="mono nowrap">
                          <span title={e.txid}>{shortHash(e.txid, 6, 4)}</span>
                        </td>
                        <td className="mono num">{net < 0 ? btc(-net) : ""}</td>
                        <td className="mono num">{net > 0 ? btc(net) : ""}</td>
                        <td className="mono num">{btc(e.balance_sats)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {lg.cluster.exposure.length > 0 && (
              <Section title="Exit points" note="Where the money left the cluster">
                <ul className="exits">
                  {lg.cluster.exposure.map((x) => (
                    <li key={x.entity}>
                      <p>
                        <b>{x.entity}</b> received <span className="mono">{btc(x.sats)} BTC</span> into {x.deposits.length} deposit addresses.
                      </p>
                      <p className="pencil">
                        A BNSS §94 notice to this exchange for the KYC behind these deposits is drafted inside the evidence pack of any linked
                        message.
                      </p>
                      <ul className="mono addr-list">
                        {x.deposits.map((d) => (
                          <li key={d}>
                            <HashText value={d} head={12} tail={6} />
                          </li>
                        ))}
                      </ul>
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            <Section title="Why these addresses are grouped" tone="pencil" note="Chain heuristics, each a lead">
              <ul className="leads">
                {lg.cluster.flags.map((f) => (
                  <Lead key={f} title={f.charAt(0).toUpperCase() + f.slice(1)} />
                ))}
                {lg.cluster.evidence.slice(0, 8).map((ev, i) => (
                  <Lead
                    key={i}
                    p={ev.confidence}
                    title={
                      <>
                        {ev.heuristic.charAt(0).toUpperCase() + ev.heuristic.slice(1)}: <span className="mono">{shortHash(ev.a, 10, 4)}</span> and{" "}
                        <span className="mono">{shortHash(ev.b, 10, 4)}</span>
                      </>
                    }
                  >
                    <p className="lead-notes-p">
                      {HEURISTIC_NOTE[ev.heuristic] ?? "linked by on-chain behaviour"} in <span className="mono">{shortHash(ev.txid, 8, 6)}</span>
                    </p>
                  </Lead>
                ))}
              </ul>
            </Section>

            <Section title="Seen in posts" note="Where these wallets were advertised">
              <ul className="post-list">
                {lg.cluster.seen_in_items.map((it) => (
                  <li key={it.id}>
                    <a className="mono" href={href(["log", it.id])}>
                      {msgNo(it.id)}
                    </a>
                    <span className="post-title">{it.title}</span>
                    <span className="pencil nowrap">
                      <span className="mono">{it.author}</span> · {sourceName(it.source_id)}
                    </span>
                  </li>
                ))}
              </ul>
              <ul className="follow">
                <li>
                  <a href={href(["graph"], { focus: `cluster:${lg.cluster.id}` })}>
                    <Network size={15} aria-hidden /> Graph around this cluster
                  </a>
                </li>
              </ul>
            </Section>
          </article>
        )}
      </div>
    </div>
  );
}
