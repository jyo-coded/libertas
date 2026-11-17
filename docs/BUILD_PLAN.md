# Libertas — Build Master Plan (Phase 0: hackathon build)

This is the working plan. The *why* is in [LIBERTAS_BLUEPRINT.md](LIBERTAS_BLUEPRINT.md); this file is the *what next* and *what done means*.

## Ground rules (non-negotiable)

1. **Zero execution.** Libertas collects text and metadata only. No JavaScript, no file downloads, no unpacking, and no rendering of captured HTML in anyone's browser (blueprint §11.14).
2. **Development allowlist.** The crawler can only reach ShadowNet and listed benchmark onions. Lex refuses everything else, including clearnet.
3. **GET only.** No forms, logins or posting, except through Authorization Ledger entries, which arrive in a later phase.
4. **Laptop stays usable.** Below-normal process priority, capped concurrency and response sizes, and a kill switch.
5. **Synthetic data only.** ShadowNet is fictional: `.example` domains, identifiers from ranges never issued to real people, and a SIMULATION banner on every page.
6. **Every capture is hashed. Every key action is audited.**

## Runtime layout on the laptop

| Process | What it runs | Ports (localhost only) |
|---|---|---|
| `python -m shadownet up` | 4 fake underground sites, the demo control panel, and a Tor instance publishing them as onion services (restricted discovery) | sites 8601–8604, panel 8600, tor control 19061 |
| `python -m libertas up` | A Tor client instance, Pulsus, Aquila, the capture and fast-lane pipeline, and the API/dashboard | tor SOCKS 19050, control 19051, API 8700 |
| `python -m libertas kill` / `resume` | Kill switch | — |

Runtime data lives in `var/` (git-ignored): databases, the quarantine store and Tor data directories.

## Milestones

| # | Milestone | Done when |
|---|---|---|
| **M0** | Safety core: Lex (allowlist, GET-only, kill switch), hash-chained audit, zero-execution fetcher, quarantine store, sanitizer | Safety tests pass: clearnet, unlisted onions, POST, binary types, oversize and redirect escapes are all refused, and scripts are stripped |
| **M1** | ShadowNet live: forum, market, leak blog and paste site with seeded fictional actors and orgs, the control panel, and onion services with client authorisation | All 4 onions reachable through Tor by Libertas's client; the panel can publish and delete posts |
| **M2** | Collection: Tor client manager, Pulsus descriptor probes, Aquila watch sessions with the cheapest-signal ladder (RSS/JSON first), adapters, capture with hashing, change and deletion detection | New ShadowNet posts are captured through Tor; deletions are detected; descriptor observations are stored |
| **M3** | Fast lane and alerts: normalisation (homoglyphs, leet, zero-width), indicator extraction with validators, India identifier pack (masked and hashed), watchlist, rule classifier, explainable severity, alert API, WebSocket live feed, optional Telegram push | Publishing a leak ad in the panel produces an alert with severity factors and detection lag, end to end through Tor — **first end-to-end milestone** |
| **M4** | Deep lane: leak authenticity scoring, stylometry and persona linking, simulated ledger with BTC heuristics, NetworkX graph with correlation rules, incidents | A new alias is linked to its known persona with evidence; the wallet cluster connects listings |
| **M5** | Evidence: Merkle batching, RFC 3161 timestamps, evidence pack (HTML/PDF), BSA §63 draft, legal-request drafts | One click produces a verifiable evidence pack |
| **M6** | Forum dashboard (React): overview, live alerts, explorer, actor view, 2D/3D graph, crypto view, Lex demo | The demo script in blueprint §20 runs from the UI |
| **M7** | Hardening and rehearsal: ShadowNet adversary mode, heartbeat onion, deadline-aware scheduling, full test pass, backup video | The demo runs three times in a row without intervention |

## Safety gates

- **Gate A, before M2:** M0 safety tests green.
- **Gate B, before any non-ShadowNet onion:** only benchmark onions from the §3.3 list, and only through the allowlist.
- **Gate C, before Phase 1 (real sources):** containerised dirty zone with network-level Tor-only egress, legal review, and the Authorization Ledger live.

## Status log

- 17 Nov 2026 — Blueprint v1.2 approved for build. M0–M3 started.
- 17 Nov 2026 — **M0–M3 done; first end-to-end milestone reached live through Tor.** 43 automated tests pass (Gate A green).
  - **ShadowNet** runs as four real onion services: three private (client authorisation), and ShadowLock public with proof-of-work armed.
  - **Pulsus** reads their descriptors without loading pages. It reports the private sites as private, and ShadowLock as PoW armed (effort 0) with 3 introduction points.
  - **Live detection through Tor**, from post published to alert raised:

    | Scenario | Result | Detection lag | Wall clock to alert |
    |---|---|---|---|
    | Genuine Mullai Telecom leak | CRITICAL 91.2 | 12.1–12.5 s | 13–14 s |
    | Fake Marutham Bank leak (samples fail checksums) | HIGH 62.3, explained | 13.0 s | 14 s |
    | ShadowLock ransomware listing (JSON feed) | HIGH 74.4 | 8.6 s | 10 s |
    | Healthcare access sale | HIGH 73.0 | 12.7 s | 14 s |

  - **Deletion detection:** 66 s, then **22 s** after adding feed-absence hints. The original capture hash is kept every time.
  - **Safety observed live:** 0 honeypot hits, 0 Lex denials needed, no orphaned Tor processes after kills, and the audit chain intact.
  - **Bugs found and fixed:**
    - Verhoeff inverse table: generation was wrong, validation was right.
    - Leetspeak "1" can mean l *or* i.
    - Aadhaar false positives inside hex IDs and PGP fingerprints.
    - ShadowNet SQLite connection shared across threads.
    - Missing WebSocket library.
- 17 Nov 2026 — **M4 done: the deep lane is live through Tor.** 46 automated tests pass.
  - **What it adds:** leak authenticity scoring, Stilus attribution, Moneta chain forensics against ShadowChain (a simulated Esplora API), Nexus incidents and evidence paths, deep re-scoring, and alert push gating.
  - **Speed:** the deep lane confirms or corrects a fast alert **about 1.0 s** after it fires. A full pass over 34 items takes 0.29 s.

    | Live scenario | Fast lane | Deep lane |
    |---|---|---|
    | New alias n1ghtcr4wl posts a Mullai Telecom leak | CRITICAL 91.2 | CRITICAL 91.9: attributed to the cybo_kaal actor (T3, P=0.993 via a shared Tox ID, writing style and wallet cluster); 0.08 BTC traced to the SimEx exchange through a 4-hop peel chain; flagged as a new target |
    | Proof rows pasted on DeadDrop | — | HIGH 60: "Leak propagation", the same dataset now on 2 sites |
    | Old Neithal rows sold as a "fresh" Palai Water dump | CRITICAL 91.6 | **Downgraded to MEDIUM 57.4**: recycled, relabelled data |
    | Marutham Bank leak whose identifiers fail checksums | HIGH 62.3 | HIGH 65.6: likely fake |

  - **Attribution accuracy:** all 4 hidden personas recovered as T3 actors, matching ShadowNet's ground truth exactly, with no cross-persona links.
  - **Push gating:** phone pushes wait up to 6 s for the deep verdict, so a recycled or fake "CRITICAL" never pages an officer. This is covered by a test.
  - **Known limits, planned for later:**
    - The forum feed lists only the newest 20 threads; deeper backfill through section pages is planned for M7.
    - Stylometry uses pure-Python character n-grams for now; neural authorship embeddings and an AI-paraphrase flag come later.
    - Chain analysis covers BTC only; ETH and TRON are V1.
    - Chain data comes from the simulated ShadowChain; production must use a self-hosted Esplora node.
- 18 Nov 2026 — **M5 done: one-click, independently verifiable evidence packs.** 60 automated tests pass.
  - **Integrity chain:** captures are sealed into Merkle batches; each batch root is signed (Ed25519) and timestamped by FreeTSA (RFC 3161). Only the digest is sent to the TSA. The audit-chain head is a leaf in every batch.
  - **Pack contents:** bit-exact captures, PII-masked readable text, the signed manifest, Merkle proofs, timestamp tokens, the chain of custody, a PDF report (facts separated from leads, IST times, SIMULATION watermark), the BSA §63 certificate draft (Part A pre-filled with SHA-256 and MD5, Part B worksheet), a BNSS §94 notice to the exchange, a victim notification, a CERT-In report, and the standalone `verify.py`.
  - **Live result:** a pack for n1ghtcr4wl's post built in about 1 s. The downloaded ZIP verified **16/16 checks, ALL PASSED**, and OpenSSL independently confirmed the FreeTSA token covers the batch root. Changing one byte of a capture makes verification fail (tested).
- 18 Nov 2026 — **M6 done: Forum, the investigator console (React + Vite + TypeScript), served by Libertas at `/`.** 64 automated tests pass.
  - **Design:** a police signals log whose entries clear like cheques.
    - Messages are ranked by precedence (FLASH / IMMEDIATE / PRIORITY / ROUTINE), then by date-time group in IST.
    - Each message is logged UNCLEARED in pencil. When the deep lane rules, a violet CLEARED or maroon RETURNED stamp lands in place.
    - The voucher separates facts (ink) from leads (pencil, dashed, graded by truth level and P), shows the masked captured text, and offers next actions.
    - An EXERCISE strip marks the simulation on every screen.
  - **Views:** message log and voucher, incidents, actor files, relationship graph (rings by hop distance, with an evidence path in violet), money passbook (net withdrawals, deposits and running balance per wallet cluster, with exit points), explorer, full captured record, evidence vault and packs, sources and descriptor log, and policy and audit chain (with the kill switch).
  - **Live run through the UI:** a `fake_leak` post was logged 28.5 s after posting as UNCLEARED. 1.03 s later the deep lane's RETURNED stamp landed in place: likely fake, 0/4 Aadhaar checksums, attributed to the data_baniya / TrustedSeller_IN actor. Acknowledge and Build evidence pack both worked from the voucher: `LIB-EVD-20261117-00041-C8B4`, 13 files, 1/1 batches timestamped.
  - **Hardening added with the console:**
    - Personal identifiers, and the names printed beside them in leaked sample rows, are masked server-side before any text reaches the browser.
    - The Host header must be local (defeats DNS rebinding).
    - Every write needs the `X-Libertas-Client` header, which a cross-site page cannot send (defeats CSRF on kill, resume, acknowledge and evidence).
    - The live socket refuses foreign Origins.
    - The page is never cached, so a rebuild always reaches the officer.
    - All of this is covered by tests.
  - **Design review:** an independent finish review against the direction contract returned eight fixes. Seven were applied:
    - name masking;
    - no fake stamp texture, with a larger voucher stamp and a return-memo slip;
    - a stronger EXERCISE strip;
    - a 16 px base (18 px in projector mode) with a type floor;
    - readable graph labels;
    - scores labelled out of 100 and dates on both lanes;
    - the design seed recorded.

    The Latin module names stay, as the brand commitments in `PRODUCT.md` require. The design system is recorded in `DESIGN.md`.
  - **Build:** `cd web && npm install && npm run build`. The output goes to `libertas/api/forum/`. The previous minimal page remains at `/classic`.
- **Next:** M7, hardening and the demo rehearsal (blueprint §20 script end to end, a timing table on the projector, and failure drills: Tor down, a source gone, the kill switch mid-run).
