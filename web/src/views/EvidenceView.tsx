import { Download } from "lucide-react";
import { api } from "../api";
import { Empty, ErrorNote, HashText, Loading, Section, ViewHeader } from "../components";
import { istFull, istTime, msgNo } from "../format";
import { href, useResource } from "../hooks";

const DRAFT_NAME: Record<string, string> = {
  certificate: "BSA §63 certificate",
  victim: "Victim notification",
  "CERT-In": "CERT-In incident report",
  BNSS94: "BNSS §94 notice",
};

function draftLabel(path: string): string {
  const file = path.split("/").pop() ?? path;
  const key = Object.keys(DRAFT_NAME).find((k) => file.includes(k));
  if (!key) return file;
  if (key === "BNSS94") {
    const m = file.match(/BNSS94_notice_(.+?)_DRAFT/);
    return `${DRAFT_NAME[key]} to ${m ? m[1].split("_").slice(0, 2).join(" ") : "the exchange"}`;
  }
  return DRAFT_NAME[key];
}

export function EvidenceView() {
  const packs = useResource(() => api.packs(), []);
  const tab = useResource(() => api.tabularium(), []);
  const t = tab.data;
  const timestamped = t?.batches_by_status?.timestamped ?? 0;
  const batches = t ? Object.values(t.batches_by_status).reduce((a, b) => a + b, 0) : 0;

  return (
    <div className="page">
      <ViewHeader title="Evidence" latin="Tabularium" />
      <p className="view-intro">
        Every capture is hashed, sealed into a Merkle batch, signed with the unit's Ed25519 key and timestamped under RFC 3161. Only the
        digest leaves this machine.
      </p>

      <Section title="Vault" note="Sealing runs every two minutes">
        {tab.error && !t ? (
          <ErrorNote error={tab.error} retry={tab.reload} />
        ) : !t ? (
          <Loading label="Reading the vault" />
        ) : (
          <dl className="vault">
            <div>
              <dt>Captures sealed</dt>
              <dd className="mono">{t.captures_sealed.toLocaleString("en-IN")}</dd>
            </div>
            <div>
              <dt>Batches timestamped</dt>
              <dd className="mono">
                {timestamped} of {batches}
              </dd>
            </div>
            {t.last_batch && (
              <>
                <div>
                  <dt>Latest batch</dt>
                  <dd>
                    <span className="mono">#{t.last_batch.id}</span>, {t.last_batch.size} leaves, sealed {istTime(t.last_batch.created_at)}
                  </dd>
                </div>
                <div>
                  <dt>Merkle root</dt>
                  <dd>
                    <HashText value={t.last_batch.root} />
                  </dd>
                </div>
                <div>
                  <dt>Timestamp</dt>
                  <dd>{t.last_batch.tsa_gen_time ? istFull(t.last_batch.tsa_gen_time) : "Awaiting the timestamp authority"}</dd>
                </div>
              </>
            )}
          </dl>
        )}
      </Section>

      <Section title="Evidence packs" note="Build one from any message's Next actions">
        {packs.error && !packs.data ? (
          <ErrorNote error={packs.error} retry={packs.reload} />
        ) : !packs.data ? (
          <Loading label="Listing packs" />
        ) : packs.data.length === 0 ? (
          <Empty title="No evidence packs yet">Open a message and choose Build evidence pack. The ZIP verifies offline with its own verify.py.</Empty>
        ) : (
          <ol className="packs">
            {packs.data.map((p) => (
              <li key={p.id} className="pack">
                <header className="pack-head">
                  <span className="mono pack-id">{p.id}</span>
                  <a className="btn btn--sm" href={`/api/evidence/${encodeURIComponent(p.id)}.zip`} download>
                    <Download size={15} aria-hidden /> ZIP
                  </a>
                </header>
                <p className="pack-line">
                  For <a href={href(["log", p.item_id])}>{msgNo(p.item_id)}</a> · built {istFull(p.created_at)} by {p.created_by} · {p.summary.files} files,{" "}
                  {p.summary.captures} captures, {p.summary.timestamped} of {p.summary.batches} batches timestamped
                </p>
                <dl className="pack-hashes">
                  <div>
                    <dt>Manifest SHA-256</dt>
                    <dd>
                      <HashText value={p.manifest_sha256} />
                    </dd>
                  </div>
                  <div>
                    <dt>ZIP SHA-256</dt>
                    <dd>
                      <HashText value={p.zip_sha256} />
                    </dd>
                  </div>
                </dl>
                {p.summary.legal_drafts.length > 0 && (
                  <p className="pack-drafts">
                    Drafts for officer review: {p.summary.legal_drafts.map(draftLabel).join(" · ")}
                  </p>
                )}
              </li>
            ))}
          </ol>
        )}
        <p className="table-note pencil">
          To check a pack anywhere, unzip it and run <code>python verify.py</code>. It re-hashes every file, replays the Merkle proofs and checks
          the signature and timestamp token without contacting Libertas.
        </p>
      </Section>
    </div>
  );
}
