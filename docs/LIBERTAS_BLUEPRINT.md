# LIBERTAS — System Blueprint

**Dark Web Intelligence & Monitoring Platform · PS-04 · TN Cyber Police Hackathon**
Version 1.1 · 17 November 2026 · Status: design, awaiting review before build

> **New in v1.1:** measurements on the live Tor network (§3.3), the Pulsus content-free sensor (§11.13), faster time-to-detect targets (§10), and ten new capabilities (#52–#61).
> **New in v1.2:** how onion markets actually live (§3.4), the zero-execution guarantee (§11.14), where a VPN fits (§15), and the Phase 0 laptop setup with its safety gate (§18).
> **Build status:** Phase 0 (M0–M7) is built and verified live through Tor. The §20 demo passed three times in a row without intervention, and seven failure drills pass (M7).
> - A leak post is alerted in about 12–25 s, and a deletion is caught in about 22 s with the evidence kept.
> - The deep lane confirms or corrects each alert about 1 s later, with authenticity, attribution, money trail and incident context.
> - One-click evidence packs verify offline (M5).
> - The Forum console (M6) shows each message logged in pencil, then stamped CLEARED or RETURNED when the deep lane rules.
> Progress and measurements are in [BUILD_PLAN.md](BUILD_PLAN.md).

> Justice wears a blindfold so she judges without bias. Libertas keeps its eyes wide open, and still acts only on evidence.

---

## Contents

**Part A — Purpose and terrain**
1. Mission
2. A night in the life of Libertas
3. The terrain: overheads, the adversary's playbook, field measurements on Tor

**Part B — Capabilities**
4. The capability map (61 capabilities, 7 pillars)
5. The brief vs. Libertas
6. What Libertas is not

**Part C — Architecture**
7. Architecture principles
8. System overview
9. Modules
10. The two-speed pipeline and time-to-detect budget
11. Speculatores: the crawler
12. Data model and truth levels
13. Intelligence engines
14. Evidence and legal layer
15. Security architecture and threat model
16. Overheads and capacity planning
17. The lawful boundary
18. Technology stack

**Part D — Making it real**
19. ShadowNet: the demo world
20. Demo script
21. Roadmap
22. Repository layout
23. Success metrics
24. Inputs needed
25. References

---

# PART A — PURPOSE AND TERRAIN

## 1. Mission

Libertas turns underground cybercrime activity into **correlated, court-ready, actionable intelligence**. It has to be fast enough that a deleted post is still evidence, and careful enough that nothing it produces embarrasses an officer in court.

Three promises:

1. **See it early and keep it.** Watch the places where new activity first appears, and capture everything on first sight with forensic integrity.
2. **Connect what criminals keep separate.** Aliases, forums, wallets, datasets and victims go into one graph, and every link is backed by evidence.
3. **Turn intelligence into action.** Libertas produces the alerts, victim notifications, legal-request drafts and evidence packs, so investigators spend their time investigating rather than formatting.

One constraint makes Libertas trustworthy: **it operates up to the legal line and is engineered so it cannot cross it.**

## 2. A night in the life of Libertas

*All names below are fictional. The sequence is what the architecture is designed to do.*

| Time | What happens |
|---|---|
| 02:13:07 | A thread appears on an underground forum: *"Kaveri Telecom — 1.2 crore subscribers, fresh, sample inside."* |
| 02:13:41 | Aquila, the pulse scheduler, polls the forum's "new posts" page on its 30-second cycle and sees the thread. The thread, the author's profile and a screenshot are captured, hashed with SHA-256 and timestamped. |
| 02:13:42 | **Fast lane:** the watchlist matches "Kaveri Telecom" (telecom sector, Tamil Nadu) and the rules classify the post as a data-leak sale with high India relevance. A provisional **CRITICAL** alert reaches the duty officer's phone. |
| 02:15 | **Deep lane:** 98% of the Aadhaar-format numbers in the sample pass the Verhoeff checksum, and the phone numbers carry TN prefixes, so the leak is scored *likely genuine*. Stilus scores the new alias `n1ghtcr4wl` at 0.87 against `cybo_kaal`, who sold a 2025 healthcare dump, and a shared PGP key corroborates the link. Moneta finds that the BTC address in the post received funds from a cluster seen in two earlier listings. |
| 02:19 | The same ad appears on a Telegram channel. Nexus merges both into a single incident with a cross-platform timeline. |
| 02:41 | The seller deletes the forum thread. Libertas records *deleted after 28 min*; the capture is already in the vault. |
| 08:30 | The investigator opens the case and finds, ready for review: the graph, the timeline, an evidence pack with a BSA §63 certificate draft, a draft notice to the exchange where the wallet cashes out, and a victim notification for Kaveri Telecom's CISO. |

## 3. The terrain

### 3.1 Overheads we have to design around

| Constraint | Reality | Design response |
|---|---|---|
| **Tor latency** | Measured (§3.3): about 6.5 s for a cold first contact including the descriptor, 4 s on a new circuit, 1.35 s for a new connection on an existing circuit, and **0.5 s** on a kept-alive connection. | Warm, isolated keep-alive *watch sessions* for priority sources, and concurrency across circuits for everything else. |
| **Onion proof-of-work** | Since Tor 0.4.8, a service under DoS can demand a client puzzle. The effort scales with the attack, from milliseconds up to about a minute of work. | Run a Tor build with the PoW module, track the effort each site demands, and back off from sites under attack. |
| **DDoS front-ends (EndGame and similar)** | NGINX/Lua front-ends serve CAPTCHAs, rate-limit per Tor circuit, set cookies and queue visitors. | A human-in-the-loop Challenge Desk, persistent sessions and strict per-site politeness. **No automated CAPTCHA solving.** |
| **Onions cannot be enumerated** | v3 onion addresses use blinded keys, so there is no way to list every onion service. | Discovery comes from links, feeds, intelligence, mirror lists, Telegram and I2P address books. |
| **Churn** | Forums are seized and splinter. BreachForums was seized in Oct 2025, and rival "successors" were fighting over the name in 2026. Mirrors rotate and phishing clones copy markets. | Track a site's identity rather than its URL, resolve mirrors, and keep an actor's history continuous across forum shutdowns. |
| **Ephemerality** | Posts are deleted within minutes, leak sites remove victims who pay, and Telegram messages disappear. | Pulse polling, push-based sources, capture on first sight, and recorded windows for when content existed. |
| **The shift to Telegram** | India-targeted leaks often surface on Telegram first. A 750M-record telecom dataset was advertised on Telegram on 14 Jan 2024 and on BreachForums nine days later. Star Health customer data was exposed through Telegram bots in 2024, and the insurer obtained an injunction from a Tamil Nadu court. | Telegram is a first-class, real-time source. |
| **Gated content** | Logins, invitations, reputation thresholds, "reply to see hidden content" and paid sections. | Public collection by default. Gated access only through officer-controlled personas recorded in the Authorization Ledger (§17). |
| **Language** | Russian-language elite forums, English-language markets, Hinglish and Tanglish on Telegram, plus slang and code words. | A multilingual pipeline with a slang lexicon and translation. |
| **Volume** | Millions of pages, most of them noise or duplicates. | Deduplication by content hash and near-duplicate detection, prioritised processing and tiered storage. |

### 3.2 The adversary's playbook

This table covers how criminals evade monitoring, and how they would try to attack Libertas itself.

| # | Tactic | Example | How Libertas counters it |
|---|---|---|---|
| 1 | Post and delete quickly | "24-hour exclusive" ads | Pulse polling, capture on first sight, deletion events |
| 2 | Bot detection | Missing Referer headers, robotic timing, CSS-hidden honeypot links, randomised HTML class names | Headers consistent with Tor Browser, human-like pacing, following only visible links, parsing that doesn't depend on class names |
| 3 | Bans and throttling | Banning a circuit or cookie, slowing suspicious clients | Circuit health scoring, back-off, separate sessions within politeness limits, alerts when ban signals appear |
| 4 | Text obfuscation | l33t speak, homoglyphs (Cyrillic "А" in "Аadhaar"), zero-width characters, text inside images, base64 | Unicode, confusables and leet normalisation, OCR, decoding |
| 5 | Code words | "fullz", "combo", "logs", "KYC'd current account", "panel", "lookup" | A slang lexicon, semantic embeddings and vocabulary supplied by analysts |
| 6 | Defeating stylometry | Rewriting posts with an LLM, deliberately imitating another actor | Multi-signal fusion, so stylometry is never used alone. An AI-rewrite flag lowers its weight. |
| 7 | Fake or recycled leaks | Old breaches repackaged as "fresh" | Leak authenticity scoring and near-duplicate matching against known leak fingerprints |
| 8 | Framing and poisoning | Planting an innocent person's name or a rival's wallet in a post | Source credibility, a corroboration requirement, single-source warnings, and human approval before any action |
| 9 | Cloaking | Serving crawlers different content | Re-fetching key pages through different circuits and fingerprints to compare |
| 10 | Unmasking the investigators | Clearnet images embedded in onion pages, canary documents in "samples", timing correlation | Tor-only egress, never fetching clearnet resources from onion content, opening documents only in a sandbox, no real identities |
| 11 | Hostile payloads | Malware in samples, browser exploits, decompression bombs, crawler traps | A dirty zone, sandboxed browsers, a content-disarm gate, size and time caps, trap detection |
| 12 | Laundering crypto | Monero, CoinJoin and mixers, chain-hopping through swap services, USDT on TRON, peel chains | Heuristics with confidence scores, CoinJoin flags, tracking swap and exchange touchpoints, TRON support, honest Monero limits |
| 13 | Exit scams and seizures | Markets vanishing with funds, law-enforcement seizure banners | Seizure-banner detection, monitoring warrant canaries, tracking migrations |
| 14 | Attacking the evidence | Defence counsel claiming a capture was altered | Hashing at capture, RFC 3161 timestamps, signed WACZ archives, chain of custody, BSA §63 certificate |

### 3.3 Field measurements on the live Tor network

On 17 Nov 2026 we measured Tor itself from the team laptop, through a dedicated Tor client (the official tor binary with its own data folder). We contacted only well-known legitimate onion services: the Tor Project, DuckDuckGo, BBC, the SecureDrop directory and Ahmia, plus remembered addresses for the New York Times and ProPublica. **No criminal service was contacted.**

The sample is small (five live sites, one run), so treat the numbers as indicative. Well-run sites like these are also faster than overloaded criminal services behind DDoS front-ends. The scripts and raw results are in `research/tor-field-test/`.

**Fetch latency** (total time for one HTTP request)

| Situation | What Tor has to do | Median | Range |
|---|---|---|---|
| Cold first contact | Fetch the descriptor (1–1.5 s), then build introduction and rendezvous circuits | ≈ 6.5 s | — |
| First contact, descriptor already cached | Build introduction and rendezvous circuits | 5.3 s | 2.9–7.0 s |
| New circuit, descriptor cached | Build a new, isolated rendezvous circuit | 4.1 s | 3.0–5.5 s |
| New connection on an existing circuit | Open a new stream only | 1.35 s | 0.8–2.6 s |
| Kept-alive connection | Just the HTTP request | **0.49 s** | 0.4–1.7 s |

**Descriptor probes** (no page content touched)

| Target | Result | Time | Directory servers asked |
|---|---|---|---|
| 5 live onions | Descriptor received | 1.0–1.5 s | 1 |
| 2 stale real addresses and 3 random valid addresses | Not found | 4.7–6.1 s | 6 |

For comparison, an HTTP attempt on the dead addresses took 7–12 s to fail.

**What a descriptor reveals.** A v3 descriptor is encrypted with keys derived from the onion address, so any client that knows the address can read it; that's how every Tor client connects. Decrypting the five live descriptors showed:

| Site | Introduction points | Proof-of-work defence | Single onion service (location not hidden) |
|---|---|---|---|
| Tor Project | 8 | No | No |
| DuckDuckGo | 10 | No | Yes |
| BBC | 3 | No | Yes |
| SecureDrop directory | 3 | **Armed, effort 0** (not under attack) | No |
| Ahmia | 10 | No | No |

**Other results**
- **Isolation works.** The same SOCKS credentials exited through the same relay twice; different credentials used a different relay.
- **Seed lists rot.** Two of the seven well-known addresses (NYT and ProPublica, from memory) no longer have descriptors. Even major publishers move their onions.

**What this changed in the architecture**
1. **Connection reuse is worth about 10×** (0.5 s against 5 s). Aquila now keeps warm, isolated keep-alive *watch sessions* to priority sources (§11.2), and the time-to-detect budget tightens (§10).
2. **There is a content-free sensor layer.** A descriptor probe tells alive from dead without loading a page, and reveals proof-of-work status, infrastructure scale and whether a service hides its location. This is now **Pulsus** (§11.13). It can watch thousands of onions, including blocklisted ones whose pages Libertas must never load.
3. **Check liveness before fetching.** Confirming a dead onion takes about 5 s by descriptor against 7–12 s by HTTP. For a live onion the probe isn't wasted work, because it warms the descriptor the first fetch needs anyway.
4. **Proof-of-work effort is live intelligence.** An effort above zero means the service is asking visitors to do work, which means it's being flooded: a rival's attack, extortion, pressure, or a rush after a big leak drop. It's both an event and a crawl-cost signal.
5. **A single onion service is an OPSEC lead.** A service published this way connects directly to the relays it uses, so it doesn't hide its server's location from them. For a criminal service that's a serious mistake. Libertas only flags it; any follow-up is a decision for authorised investigators under legal process.
6. **Discovery has to be continuous**, because addresses go stale even for legitimate sites.

### 3.4 How an onion marketplace actually lives

A common mental model is *"a website that sits on someone's own device and changes every 24 hours."* It's half right, and the half that's right matters.

- **It really can run on anyone's machine.** An onion service is an ordinary web server running Tor: a laptop, a Raspberry Pi or a rented server. It needs no public IP, because Tor connects outward. Serious markets run several servers behind one address; the 8–10 introduction points measured in §3.3 are what that looks like from outside.
- **The address is the site's public key.** It doesn't change by itself. It changes only when the operator generates a new key, typically after a seizure, an exit scam or a phishing war.
- **What rotates every 24 hours** is where the site is listed. Tor divides time into 24-hour periods, and each period derives a new "blinded" key from the address. That moves the site's descriptor to different directory servers every day. The descriptor itself expires every 3 hours (measured: lifetime 180 minutes) and is republished. Introduction points also shift as relays come and go.
- **What operators rotate by choice:** fresh mirrors during DDoS attacks, private per-user links, and invitation-only (restricted-discovery) addresses.

**Libertas's answer:**
- It tracks a site's *identity* (keys, PGP-signed mirror lists, fingerprints), not one URL.
- Pulsus re-checks liveness continuously and survives the daily directory rotation, because it asks Tor for the descriptor exactly as a client would.
- Capture on first sight means a site vanishing overnight doesn't take the evidence with it.

---

# PART B — CAPABILITIES

## 4. The capability map

**Legend:** `[B]` in the problem brief · `[+]` beyond the brief · **Demo / V1 / V2** is when the capability ships (Demo = hackathon build, V1 = pilot, V2 = operations).

### Pillar I — SEE: collection and coverage (*Speculatores*)

| # | Capability | What it does | Tag | Ships |
|---|---|---|---|---|
| 1 | Multi-network collection | Tor v3 onions, I2P eepsites, public Telegram channels and groups, clearnet underground forums and paste sites, ransomware leak sites, CTI feeds | [B][+] | Demo (Tor, Telegram) / V1 |
| 2 | Discovery engine | Seeds from Ahmia, deepdarkCTI and ransomware group lists; link snowballing; PGP-signed mirror lists; links posted on Telegram; I2P address books. Classifies each site's type automatically. | [B] | V1 |
| 3 | **Aquila pulse monitoring** | Polls "new posts", "latest listings" and "victims" pages every 15–60 s, receives Telegram pushes within seconds, and revisits everything else adaptively | [B][+] | Demo |
| 4 | **First-sight forensic capture** | WARC, screenshot, DOM, text and headers; SHA-256; RFC 3161 timestamp; signed WACZ | [B][+] | Demo |
| 5 | Change, edit and deletion tracking | Diffs, price changes, "deleted after N min", victims removed from leak sites (often a sign the victim paid) | [B] | Demo |
| 6 | Mirror, clone and phishing-clone resolution | Groups onion addresses into one site identity, checks mirrors against PGP-signed mirror lists, and flags lookalike addresses that share a vanity prefix with a known site, plus clones that swap in different wallet addresses | [+] | V1 |
| 7 | Coverage observatory | Uptime, last seen, time-to-detect per source, blind spots, ban signals | [+] | Demo (basic) |
| 8 | Lawful access modes | Public → analyst-assisted (a human solves the challenge) → authorized persona (Authorization Ledger) | [+] | Demo (ledger UI) |
| 9 | Liveness probes | Descriptor-level checks of whether an onion is online, without loading pages. Measured: alive in 1–1.5 s, dead confirmed in about 5 s (§3.3). | [+] | Demo |
| 10 | Seizure and exit-scam detection | Law-enforcement banners, stale warrant canaries, sudden downtime, migration announcements | [+] | V1 |
| 52 | **Pulsus descriptor intelligence** | For any onion, without loading a page: proof-of-work status (armed, current effort), introduction-point count (infrastructure scale), single-onion-service flag (an OPSEC lead), private-service flag, uptime history (§11.13) | [+] | Demo |
| 53 | **Warm watch sessions** | Persistent, isolated keep-alive connections to priority sources: about 0.5 s per poll against about 5 s cold (measured) | [+] | Demo |
| 54 | Cheapest-signal-first polling | Descriptor → the forum engine's RSS/Atom feed or the site's JSON endpoint → conditional GET → full page → browser | [+] | Demo (partial) |
| 55 | Deadline-aware scheduling | Parses ransomware countdown timers, tightens polling as the deadline nears, and warns the victim before publication | [+] | Demo |

### Pillar II — UNDERSTAND: extraction and classification (*Interpres*)

| # | Capability | What it does | Tag | Ships |
|---|---|---|---|---|
| 11 | Universal indicator extraction | Emails, domains, IPs, URLs and onion addresses. BTC, ETH, TRON, XMR and LTC addresses checked against Base58Check, Bech32, EIP-55 and TRON checksums. PGP keys and fingerprints; Jabber, Tox, Session and Telegram handles; file hashes; CVEs; malware names. | [B] | Demo |
| 12 | **India identifier pack** | Aadhaar (Verhoeff check), PAN (format plus holder-type letter), GSTIN (checksum), IFSC, UPI IDs, +91 mobiles, PIN codes, and .gov.in/.nic.in/.ac.in/.res.in domains. Values are **masked and hashed on ingest.** | [+] | Demo |
| 13 | Organisation and sector resolver | Configurable watchlists of names, aliases, domains, email domains and brands; fuzzy and transliteration matching; sector tagging (healthcare, telecom, BFSI, government, education, critical infrastructure, corporate) | [B] | Demo |
| 14 | Threat classification | Data-leak sales, database dumps, ransomware claims, initial access sales, stealer logs and credentials, carding, fraud infrastructure (mule accounts, SIMs, UPI), malware and exploits, phishing kits, hacktivist claims, doxxing, counterfeit IDs. Policy-gated option: narcotics shipping to India. | [B][+] | Demo (core classes) |
| 15 | Anti-obfuscation | Unicode, homoglyph and leet folding; zero-width stripping; OCR; decoding of encoded text; slang lexicon | [+] | Demo (partial) |
| 16 | Multilingual pipeline | Language identification and translation: Russian, Chinese, Hindi, Tamil, and code-mixed Hinglish and Tanglish | [+] | V1 |
| 17 | **Leak authenticity scoring** | Tests a sample statistically (checksum validity rates, geographic consistency of phones and PIN codes, schema plausibility, overlap with known leaks) and rates it *genuine / recycled / unverifiable / likely fake* | [+] | Demo |
| 18 | Claim verification | Checks hacktivist defacement and DDoS claims against the target, and archives the result | [+] | V2 |

### Pillar III — CONNECT: attribution and correlation (*Stilus, Moneta, Nexus*)

| # | Capability | What it does | Tag | Ships |
|---|---|---|---|---|
| 19 | Persona engine | Links actors, aliases and accounts across forums and Telegram, and keeps that history continuous when a forum is seized | [B] | Demo |
| 20 | **Multi-signal attribution** | Combines stylometry (character n-grams, function words, neural authorship embeddings), behaviour (posting-hour profile, which suggests a timezone) and operational overlaps (PGP keys, wallets, handles, sample naming, pricing, reused images). Produces a calibrated score with the supporting evidence listed. | [B][+] | Demo |
| 21 | Bitcoin forensics | UTXO graph, common-input clustering, change detection, CoinJoin and mixer flags, peel chains | [B] | Demo (regtest) |
| 22 | Ethereum forensics | Transfers, token flows, smart-contract interactions | [B] | V1 |
| 23 | **TRON / USDT-TRC20 tracing** | Follows the main payment rail used to launder proceeds of Indian fraud | [+] | V1 |
| 24 | Monero intelligence | States the limits of tracing honestly; gathers off-chain intelligence (address mentions, swap touchpoints, view keys from lawfully seized wallets) | [B] | Demo (limitations card) |
| 25 | Exposure and VASP attribution | Measures how close a wallet is to exchanges, mixers and sanctioned entities, which shows who can be served a legal notice | [+] | V1 |
| 26 | Correlation graph and rules | Shared wallets, PGP keys or handles; the same dataset on several sites; a known actor targeting a new Indian organisation | [B] | Demo |
| 27 | Graph analytics | Communities (crews), brokers and central actors, predicted links (labelled as predictions) | [+] | V1 |
| 28 | Incident clustering | Merges every appearance of the same leak across sites into one incident, with first sighting and spread timeline | [+] | Demo |
| 29 | **Victim inference for anonymous access sales** | Matches listings like "Indian telecom, $500M revenue, 2,000 staff, VPN access" against an Indian company registry and ranks likely victims for confidential early warning. In Cyjax's analysis, access sales precede leak-site postings by about 20 days on average, so the warning window is real. | [+] | V1 |
| 56 | Telegram propagation graph | Tracks channels by numeric ID (which survives renames), follows forward chains to find where a leak first appeared and how it spread, and discovers new channels through forwards | [+] | V1 |
| 57 | Infrastructure fingerprint graph | Server headers, favicon hashes, page templates, anti-DDoS cookies and descriptor traits link sites run by the same operators | [+] | V1 |

### Pillar IV — ACT: alerting, response and prosecution (*Vigiles, Codex*)

| # | Capability | What it does | Tag | Ships |
|---|---|---|---|---|
| 30 | Explainable severity scoring | Sector criticality × data sensitivity × scale × credibility × actor track record × freshness × India relevance, with every factor visible | [B] | Demo |
| 31 | Multi-channel alerts | Live dashboard, Telegram bot with acknowledge buttons, email, SMS or webhook; deduplication, grouping and escalation timers | [B] | Demo |
| 32 | Case management | Cases, tasks, notes, assignments, linked evidence, status, two-person approvals | [B] | Demo (basic) |
| 33 | **Court-ready evidence pack** | PDF, WACZ archive, hash manifest, chain of custody, timestamp tokens, and a **BSA §63 certificate draft** (Part A prefilled; a Part B worksheet for the expert) | [+] | Demo |
| 34 | Legal-request drafting | BNSS §94 notices to exchanges and VASPs, Telegram legal requests, registrar and host abuse reports, IT Act §79(3)(b) takedown drafts, CERT-In incident reports. All are drafts for an officer to review. | [+] | V1 |
| 35 | Victim notification | An evidence-backed notice to the affected organisation and CERT-In, tracked until acknowledged | [+] | Demo (draft) |
| 36 | Disruption support | Takedown requests for phishing domains and channels; mule-account indicators exported for the I4C Suspect Registry through official channels | [+] | V2 |

### Pillar V — FORESEE: early warning (*Augur*)

| # | Capability | What it does | Tag | Ships |
|---|---|---|---|---|
| 37 | Emerging-threat radar | New topics, slang and scam types over time; spikes by sector | [+] | V1 |
| 38 | Actor trajectory | Detects an actor drifting between sectors, and escalates when a known actor targets a new Indian organisation | [B][+] | Demo (rule) |
| 39 | Organisation exposure score | One view per organisation: mentions, credentials for sale, phishing lookalikes from certificate-transparency logs, code leaks | [+] | V1 |
| 40 | Advisory drafting | Citizen advisories in English and Tamil about trending scams | [+] | V2 |
| 41 | Intelligence briefs | Daily and weekly PDF summaries | [+] | V1 |
| 58 | Underground price index | Price per record of Indian data by sector over time, from parsed listings; shows demand and helps prioritise | [+] | V1 |
| 59 | Organisation watch portal | Organisations prove they own a domain (DNS TXT record) and then receive their own exposure alerts, extending protection beyond what officers can watch by hand | [+] | V2 |

### Pillar VI — PROTECT: platform integrity (*Janus, Lex, Tabularium*)

| # | Capability | What it does | Tag | Ships |
|---|---|---|---|---|
| 42 | Dirty/clean zone separation | Collection is isolated from analysis, with content disarm and reconstruction in between | [B] | Demo (simplified) |
| 43 | Tamper-evident audit | A hash-chained log anchored to external timestamps | [B] | Demo |
| 44 | Access control | RBAC, per-case need-to-know, MFA, field-level PII encryption, retention and legal hold | [B] | Demo (RBAC) |
| 45 | Model governance | Every inference is stamped with the model, version and threshold, and can be reproduced | [B] | Demo |
| 46 | **Canary records** | With an organisation's consent, unique decoy records are seeded into each of its systems. If one surfaces in a leak, Libertas can show which system leaked. | [+] | V2 |
| 47 | CSAM safeguard | Images from risky categories are off by default; quarantine; hash-matching against authorised lists; mandatory escalation; never stored in the general vault | [+] | Demo (images off) |
| 60 | **Pre-contact checks** | Every onion is checksum-validated and checked against abuse blocklists (Ahmia's MD5-hashed blacklist, lists from authorities) before any HTTP contact. A blocked onion gets descriptor monitoring at most. | [+] | Demo |
| 61 | ShadowNet adversary mode | The demo world can switch on bans, CAPTCHAs, honeypot links, cloaking, proof-of-work and 60-second deletions, so the crawler's resilience is tested rather than assumed | [+] | Demo |

### Pillar VII — ASSIST: the investigator's experience (*Forum*)

| # | Capability | What it does | Tag | Ships |
|---|---|---|---|---|
| 48 | Investigator dashboard | Overview, explorer, actors, crypto, graph (2D and 3D), alerts, map, timelines | [B] | Demo |
| 49 | Analyst copilot (offline LLM) | Natural-language questions over the graph and search. Answers must cite evidence IDs, and the copilot's output is never treated as evidence. | [+] | V1 (Demo if hardware allows) |
| 50 | Pivot on anything | Click any indicator to see everything Libertas knows about it | [+] | Demo |
| 51 | Interoperability | STIX 2.1/TAXII, MISP, OpenCTI, and CSV/JSON exports for agency platforms | [+] | V1 |

## 5. The brief vs. Libertas

| The brief's final outcome | How Libertas delivers it | What goes beyond the brief |
|---|---|---|
| 1. Discover and crawl Tor hidden services | Speculatores, the discovery engine and Aquila | I2P, Telegram, feeds, Pulsus descriptor intelligence, warm watch sessions, seizure detection |
| 2. Extract and index forum content | Interpres, Postgres full-text search and pgvector | India identifier pack, multilingual pipeline, anti-obfuscation |
| 3. Detect and classify leak ads | Classifier plus watchlists | Authenticity scoring, incident clustering |
| 4. Find related aliases with stylometry | Stilus | Multi-signal fusion, AI-paraphrase flag, calibrated confidence |
| 5. Analyse crypto patterns | Moneta | TRON/USDT, VASP exposure, legal-notice drafts |
| 6. Correlate in a relationship graph | Nexus | Truth levels, evidence paths, graph analytics, victim inference |
| 7. Alert on Indian organisations | Vigiles | Push to phones, escalation, victim notification |
| 8. Investigator dashboard | Forum | Copilot, evidence packs, case management, replay of captured pages |

## 6. What Libertas is not

- **Not an offensive tool.** It doesn't exploit, break in or impersonate on its own.
- **Not mass surveillance of citizens.** It watches criminal marketplaces and the identifiers organisations register with it, not the public.
- **Not a verdict machine.** It produces evidence and leads. Officers investigate and courts decide.
- **Not a store of stolen data.** It records that a leak exists and how credible it is, without hoarding the leak itself.

---

# PART C — ARCHITECTURE

## 7. Architecture principles

1. **Two speeds.** Alerts never wait for heavy AI.
2. **Evidence first.** Content is captured, hashed and timestamped before any processing, and every derived fact points back to a capture.
3. **Hostile by default.** Only the dirty zone touches the underground; the clean zone never does.
4. **Policy as code.** The lawful boundary is enforced on every request, not by a written guideline.
5. **Modular monolith first, services later.** One codebase running as separate processes, split into services only when load requires it. This is the fastest path to a working system that can still scale.
6. **Idempotent everywhere.** Content-hash keys, at-least-once delivery and safe retries.
7. **Degrade gracefully.** If the deep lane is down, the fast lane still alerts. If Tor is slow, priority sources keep their place in the queue.
8. **Open standards.** STIX 2.1, WARC/WACZ, RFC 3161, OIDC.
9. **Sovereign deployment.** On-premises (for example at the State Data Centre) or on a MeitY-empanelled government cloud. No case data goes to foreign SaaS or cloud LLM APIs.

## 8. System overview

```
                         THE UNDERGROUND
   ┌──────────────────────────────────────────────────────────┐
   │ Tor .onion · I2P · Telegram · paste sites · leak sites    │
   │ clearnet forums · CTI feeds · CT logs · public blockchains │
   └────────────────────────────┬─────────────────────────────┘
                                │  Tor / I2P / MTProto / HTTPS only
╔═══════════════════════════════▼══════════════════════════════════════╗
║ DIRTY ZONE: touches hostile content, holds no intelligence           ║
║   Tor & I2P gateway fleet ── Circuit Manager ── AQUILA · PULSUS      ║
║   Fetchers: fast HTTP · sandboxed Tor Browser · Challenge Desk       ║
║   Telegram collectors · feed collectors                              ║
║   Capture: WARC · screenshot · DOM · SHA-256 → quarantine store      ║
╚═══════════════════════════════╤══════════════════════════════════════╝
                                │ JANUS gate (one-way): malware scan · content
                                │ disarm (text out, images re-encoded or dropped)
                                │ · CSAM screen · hash + RFC 3161 timestamp ·
                                │ LEX policy check
╔═══════════════════════════════▼══════════════════════════════════════╗
║ CLEAN ZONE: analysis, never contacts the underground                 ║
║                                                                      ║
║   Event bus ─► FAST LANE (seconds) ─────────► VIGILES ─► phones/web  ║
║       │        normalise · watchlist · IOC regex · rules · severity  ║
║       └──────► DEEP LANE (minutes)                                   ║
║                 INTERPRES  NLP · OCR · translation · classification  ║
║                 STILUS     stylometry & persona fusion               ║
║                 MONETA     blockchain forensics                      ║
║                 NEXUS      graph correlation & scoring               ║
║                 AUGUR      trends · victim inference · exposure      ║
║                                                                      ║
║   TABULARIUM evidence vault (content-addressed, encrypted, WORM)     ║
║   PostgreSQL (+pgvector, FTS) · graph DB · search · object store     ║
║   CODEX cases · evidence packs · legal drafts                        ║
║   FORUM dashboard + copilot  ◄── officers over VPN + MFA             ║
╚══════════════════════════════════════════════════════════════════════╝
   LEX spans everything: policy engine · Authorization Ledger · RBAC · audit chain
```

## 9. Modules

All module names are Latin, after Libertas herself.

| Module | Meaning | Responsibility | Core technology |
|---|---|---|---|
| **Speculatores** | Rome's scouts | Collection from Tor, I2P, Telegram and feeds; fetching; capture | asyncio, aiohttp-socks/httpx, tor + stem, i2pd, Telethon, tbselenium/Playwright, warcio |
| **Aquila** | The legion's eagle | The pulse scheduler inside Speculatores: adaptive revisits, the "hawk's eye" | Valkey sorted sets, a change-rate model |
| **Pulsus** | Heartbeat | The content-free sensor inside Speculatores: descriptor liveness, proof-of-work status, infrastructure traits | Tor control port (HSFETCH, HS_DESC events), stem |
| **Janus** | God of doorways | The one-way gate from dirty to clean zone: scanning, content disarm, hashing, timestamping | ClamAV/YARA, Pillow re-encoding, hashlib, RFC 3161 client |
| **Tabularium** | Rome's state archive | Evidence vault, chain of custody, WACZ packaging, timestamps | Content-addressed store, py-wacz, RFC 3161 TSA, OpenTimestamps |
| **Interpres** | Interpreter | Normalising, extracting, classifying, translating, OCR | pyahocorasick, validators, GLiNER, SetFit, sentence-transformers, Tesseract, Argos/IndicTrans2 |
| **Stilus** | Writing stylus | Stylometry and persona fusion | scikit-learn, character n-grams, LUAR-style embeddings, calibration |
| **Moneta** | The Roman mint | Blockchain forensics | Esplora/mempool API, Etherscan API V2, TronGrid, NetworkX, bitcoind regtest (demo) |
| **Nexus** | Binding tie | Correlation graph, rules, scoring | Neo4j, Cypher, graph algorithms |
| **Vigiles** | Rome's night watch | Alerts and escalation | WebSockets, Telegram Bot API, SMTP |
| **Augur** | Roman diviners | Trends, victim inference, exposure scores | BERTopic, registry matching |
| **Codex** | Bound book | Cases, evidence packs, legal drafts | Jinja2 templates, WeasyPrint |
| **Forum** | The public square | Dashboard and copilot | React, TypeScript, Cytoscape.js, react-force-graph, MapLibre, ECharts, Ollama |
| **Lex** | Law | Policy, Authorization Ledger, RBAC, audit | Python policy module, later OPA/Rego; Keycloak; hash-chained audit |

## 10. The two-speed pipeline and time-to-detect budget

**Fast lane (target: seconds).** Capture → Janus (text extraction and hash) → normalisation → **Aho-Corasick** matching against the whole watchlist → precompiled indicator regexes → rule classifier → provisional severity → alert marked *provisional*.
The fast lane loads no large models. Aho-Corasick is linear in the length of the text, so tens of thousands of watchlist terms add almost no cost per post.

**Deep lane (target: minutes).** NER, classification, embeddings, near-duplicate detection, translation, OCR, stylometry, blockchain enrichment, graph upserts and correlation rules, then a re-score. The alert is upgraded or downgraded with an explanation. LLM summaries run only for high-severity items.

**Cold lane (hourly or daily).** Graph algorithms, model retraining from analyst feedback, trend radar, reports.

**Delivery semantics.** At-least-once delivery through consumer groups, idempotent upserts keyed by content hash, and a dead-letter stream. History can be **replayed from the vault**, so any model upgrade can reprocess everything collected so far.

### Time-to-detect budget (design targets; fetch times measured in §3.3)

| Stage | Priority web source | Telegram |
|---|---|---|
| Wait for the next poll | 0–30 s (30 s interval, jittered) | Push, so about 0 s |
| Fetch over a warm keep-alive watch session (measured median 0.5 s) | 0.4–1.7 s | 0.1–1 s |
| Capture (text and hash; screenshot runs in parallel) | < 1 s | < 0.5 s |
| Fast lane | < 1 s | < 1 s |
| Notification delivery | 1–3 s | 1–3 s |
| **Total** | **typically 5–35 s, P95 < 45 s** | **typically 3–8 s, P95 < 15 s** |

Criminal services behind overloaded front-ends will be slower than the well-provisioned sites measured in §3.3. These targets get re-measured against ShadowNet's adversary mode (#61) and during the pilot.

**Heartbeat onion.** Libertas runs its own canary onion page that changes every minute, and measures its own end-to-end time-to-detect around the clock. When the number degrades, the operations panel turns red before an analyst notices.

## 11. Speculatores: the crawler

### 11.1 Circuit Manager
- A fleet of tor clients, using official Tor Project builds with the PoW module enabled (check with `tor --list-modules`). Each client exposes several SOCKS ports.
- **Circuit isolation per site** using distinct SOCKS credentials, which Tor isolates by default. A ban or slowdown on one site never affects another.
- **Connection reuse.** The rendezvous circuit is the expensive part of reaching an onion, so keep-alive connections are reused.
- Each circuit has a health score from its latency, errors and ban signals. A bad score triggers a NEWNYM or moves the site to a fresh circuit.
- **Remote DNS only** (socks5h / rdns), so .onion names never reach a DNS resolver.
- I2P runs through i2pd's HTTP proxy, with SAM for advanced cases. Arti, the Rust implementation of Tor, is evaluated as a second engine; C tor stays primary.
- **Measured (§3.3):** per-site isolation through SOCKS credentials works (same credentials, same exit relay; new credentials, a different one), and a kept-alive connection is about 10× faster than a cold one.
- **Liveness before fetch.** An HTTP attempt on a dead onion took 7–12 s to fail. A Pulsus probe confirms it dead in about 5 s, and for a live onion it warms the descriptor that the first fetch needs anyway (§11.13).

### 11.2 Aquila: adaptive scheduling
- Every URL has a priority *p* and an estimated change rate *λ*, learned from its history with a Poisson model.
- **Revisit interval = clamp(k / (λ·p), 15 s, 7 days)**, with ±20% jitter so the polling has no detectable rhythm.
- Pages have roles. **PULSE** pages (index, new posts, latest listings, leak-site victim lists) are revisited every 15–60 s; **THREAD** pages every few minutes; **PROFILE** pages every few hours; **ARCHIVE** pages every few days.
- **Event-triggered bursts.** A new item on a pulse page immediately schedules its detail page, the author's profile and linked media, subject to policy.
- **Per-site politeness.** One or two concurrent requests per onion, a minimum delay and a global budget. Onion services are fragile, and hammering them is both harmful and a quick way to get banned.
- Fair sharing with priority aging, so no source starves the others.
- **Warm watch sessions.** PULSE sources keep a persistent, isolated keep-alive connection, so each poll costs about 0.5 s instead of about 5 s (§3.3). A session that drops is rebuilt in the background, off the critical path.
- **Cheapest signal first.** Each poll climbs a ladder and stops as soon as it has its answer:
  1. the descriptor (is it alive?)
  2. the forum engine's own RSS/Atom feed (MyBB, XenForo and phpBB ship them) or the site's JSON endpoint
  3. a conditional GET (ETag / If-Modified-Since), so an unchanged page costs only a 304
  4. the full page
  5. the browser tier
- **Deadline-aware.** Ransomware leak sites show countdown timers. Aquila parses them and tightens polling as a deadline approaches, so the publication moment is captured and the victim can be warned before it.

### 11.3 Fetch tiers
- **T1 fast HTTP (async)** handles most onion pages, which work without JavaScript.
- **T2 sandboxed browser.** A real Tor Browser driven by tbselenium (the most consistent fingerprint) or Playwright with Firefox. JavaScript is off unless a site requires it. Each browser runs in a disposable container with no clearnet route.
- **T3 Challenge Desk (human in the loop).** When a CAPTCHA or queue appears, the task goes to an analyst, who solves it in a remote-browser view. The resulting session cookie is then reused within rate limits. **Libertas never solves CAPTCHAs automatically.**

### 11.4 Sessions and personas
- Cookie jars per site and per persona, with ban and logout detection and session keep-alive.
- A persona can only be used while an **Authorization Ledger** entry is active: case ID, sanctioning officer, scope (sites and actions) and validity window. Lex enforces this on every request.

### 11.5 Site adapters
- Templates for common forum engines and site types: MyBB, XenForo, phpBB, SMF, Discourse, common market scripts, ransomware leak blogs and paste sites.
- A generic fallback: main-content extraction with trafilatura plus heuristics to split pages into posts.
- **Self-healing.** Output validators catch layout drift (for example, "thread parsed 0 posts"), raise an alert and switch to the fallback parser. An offline LLM can propose new selectors for a human to approve. Adapters anchor on structure and text patterns rather than class names, so randomised classes don't break them.

### 11.6 Capture and integrity
- On first sight and on every change, Libertas stores the WARC record (request and response), a full-page screenshot, the DOM, the extracted text, the headers and circuit metadata.
- Every artifact is hashed with SHA-256 and stored under its hash, which gives deduplication for free.
- Captures are batched into a Merkle tree each minute, and **one RFC 3161 timestamp token** (optionally also an OpenTimestamps anchor) covers thousands of captures at little cost.
- Captures are packaged per case as **signed WACZ** and can be replayed in the dashboard exactly as the page looked.
- **Existence windows.** Recording *first seen*, *last seen present* and *first seen absent* gives a court a precise window in which the content existed.

### 11.7 Change detection
An exact hash plus a SimHash of the normalised text, and a structural diff. A deleted post becomes an event, with its last capture preserved.

### 11.8 Safety and operational security
- The collectors' only network route is Tor or I2P: an egress firewall and no DNS. **Nothing in onion content can trigger a clearnet fetch**, which blocks beacon-style unmasking.
- Archives, executables and documents are not downloaded by default; only their metadata is recorded. When a sample download is authorised, it opens only in a detonation sandbox.
- Caps on page size, response time, redirects, depth and pages per site per cycle; a decompression-bomb guard; detection of crawler traps (calendar loops, session IDs in URLs, endless pagination).
- **Honeypot links are avoided** by following only links a human could see.
- **Pre-contact checks.** Before any HTTP contact, every onion address is checksum-validated (v3 addresses carry a checksum) and checked against abuse blocklists: Ahmia's MD5-hashed blacklist plus lists supplied by authorities. A blocked onion gets descriptor-level monitoring at most, and its pages are never loaded.
- **Fingerprint discipline.** Headers and behaviour consistent with Tor Browser, and human-like pacing.
- **Differential crawling.** Key pages are re-fetched through a different circuit and fingerprint. Systematic differences are flagged as *suspected cloaking*.
- Workers are disposable and rebuilt from signed images. They keep no persistent state beyond the capture queue.

### 11.9 Telegram collector
- An MTProto client (Telethon) on dedicated, authorised accounts, joining **public** channels and groups only.
- Real-time handlers for new, edited and deleted messages. Only media metadata is collected by default; downloads follow policy.
- Handles FloodWait limits, shards channels across accounts and monitors each account's health.
- **Tracks channels by numeric ID**, which survives renames, and records forward headers. Libertas can then see where a leak first appeared and how it spread, and discover new channels through what gets forwarded.
- **Never queries "lookup bots" for citizens' data**, because that would mean accessing stolen data. Such bots are recorded as indicators instead.

### 11.10 Feeds and side channels
The ransomware.live API, RansomLook, abuse.ch (URLhaus, ThreatFox, MalwareBazaar), the OFAC SDN list of digital currency addresses, CERT-In advisories, certificate-transparency streams (lookalike domains of Indian banks and government sites), and monitoring of public code leaks containing Indian organisations' secrets.

### 11.11 Reliability engineering
- A crash-safe, persisted frontier; at-least-once processing; idempotent writes; retries with exponential backoff; a circuit breaker per site; a dead-letter queue; back-pressure.
- The heartbeat onion (§10) measures the system's own time-to-detect.
- Prometheus metrics feed Grafana dashboards: fetch latency, success rate, ban signals, queue depth and time-to-detect.

### 11.12 How Libertas compares

| | Typical open-source onion crawler | Libertas |
|---|---|---|
| Freshness | Fixed-interval or one-off crawls | Adaptive revisits, 15–60 s pulse polling, Telegram push, measured time-to-detect |
| Evidence | Saves HTML or text | WARC, screenshot, hashes, RFC 3161, signed WACZ, chain of custody |
| Ephemeral content | Lost when deleted | Capture on first sight, deletion events, existence windows |
| Anti-bot defences | Gets banned, or solves CAPTCHAs in legally risky ways | Politeness, circuit isolation, human Challenge Desk |
| Safety | Runs on the analyst's own machine | Dirty and clean zones, sandboxing, Tor-only egress, content disarm |
| Legality | Left to the operator | Policy engine and Authorization Ledger that cannot be bypassed |
| Parsing | Brittle selectors | Engine templates, drift detection, self-healing |
| Coverage | Tor only | Tor, I2P, Telegram, leak sites, feeds, CT logs |
| Observability | Logs | Source health, blind spots, SLOs, heartbeat canary |
| Cost of watching | Every check loads a page | Descriptor checks for thousands of onions; pages load only when something may have changed |

### 11.13 Pulsus: the content-free sensor
*Pulsus* is Latin for heartbeat. It is the part of Libertas that can watch an onion without ever opening it.

- **How it works.** Pulsus asks Tor's control port to fetch a service's descriptor (`HSFETCH`) and listens for the result (`HS_DESC` events). It then reads the cached descriptor and decrypts it with the public onion address, exactly as any Tor client does before connecting. No connection is made to the service itself.
- **What it records for each onion, each time:**
  - alive or not found, and how long the lookup took
  - the number of introduction points (Tor's default is 3; 8–10 usually means tuning or load-balancing across several servers)
  - proof-of-work: whether it's armed, and the suggested effort (above 0 means the service is under load right now)
  - whether it's a single onion service (an OPSEC lead, §3.3)
  - whether it's private: a service with restricted discovery can't be decrypted without credentials, which itself shows it's invitation-only
  - when the descriptor changed
- **What it builds from that:** uptime histories and outage alerts, "back online" alerts for sites that went dark, under-attack alerts, OPSEC-weakness leads, and infrastructure traits for the fingerprint graph (#57).
- **Cost and etiquette.** One probe is a single small directory request. A live onion answers in 1–1.5 s; a dead one is confirmed in about 5 s after six directories are asked. Probes are spread out (every 15–60 minutes per onion, depending on priority) under a global rate cap, so Libertas never burdens the directory system.
- **Limits.** Pulsus never sees content. Everything it learns is what Tor itself publishes so that clients can connect.

### 11.14 The zero-execution guarantee
This is the most common way home-built crawlers hurt their owners. A scraper that "processes everything", scripts and files included, can make the machine unusable or compromise it. Libertas collects **text and metadata only**, and nothing it fetches is ever run.

- **No JavaScript engine in the collector.** The T1 fetcher is a plain HTTP client. HTML is parsed with a non-executing parser, and `<script>`, `<style>`, `<iframe>`, `<object>`, `<embed>`, `<svg>` and similar tags are removed before text is extracted. The T2 browser tier isn't used in Phase 0 at all; when it arrives, JavaScript stays off and it runs only in a disposable container.
- **No files.** Only HTML, plain text, JSON and RSS/Atom/XML responses are accepted, and anything else is refused before its body is read. Links to archives, executables, documents and images are recorded as metadata (URL, extension, declared size) and never fetched. Nothing is ever unzipped or extracted.
- **Hostile-input parsing.** XML is parsed with `defusedxml`, which blocks entity-expansion and external-entity attacks. Compressed responses are decompressed by Libertas itself with a hard output cap, which guards against decompression bombs. Responses are capped at 2 MB and 60 s, with at most 3 redirects, and every redirect target is re-checked by Lex.
- **Quarantine store.** Raw responses are kept only as evidence: gzip-compressed, named by their SHA-256 and **without file extensions**, so nothing on the machine (a double-click, a previewer, an indexer) opens or runs them.
- **Resource governor.** Collectors run at below-normal process priority with caps on concurrency, queue length and response size, so a crawl can never make the laptop unusable.
- **Kill switch.** A single command halts all collection immediately, and the halt is recorded in the audit chain.
- **Analysts never see live hostile HTML.** The dashboard shows escaped text and Libertas-generated views only. A hostile page can't attack an investigator's browser through stored XSS.
- **Development allowlist.** In development mode, Lex refuses every onion that isn't explicitly listed (ShadowNet plus benchmark sites), so the crawler can't wander into the real dark web by following a link.

## 12. Data model and truth levels

**Entities:** Site (with its mirrors), Page, Capture, Thread, Post/Listing, Account (an alias on one site), Actor (a cluster of personas), Organisation, Sector, Dataset/Leak, Incident, Indicator, Wallet, WalletCluster, Transaction, MalwareFamily, TelegramChannel, DescriptorObservation (what Pulsus saw, and when), Case, Alert, Authorization.

**Example edges:** Account–POSTED→Post · Post–MENTIONS→Organisation · Post–ADVERTISES→Dataset · Post–CONTAINS→Wallet · Account–SIMILAR_STYLE{score}→Account · Account–SHARES_PGP→Account · Account–ALIAS_OF{score}→Actor · Wallet–IN_CLUSTER→WalletCluster · WalletCluster–PAID→WalletCluster · Dataset–BELONGS_TO→Organisation · Incident–INCLUDES→Post · Actor–TARGETED→Sector.

**Every node and edge carries** the IDs of its source captures, the method that produced it (rule, regex or model@version), a confidence, a truth level, and first-seen and last-seen times.

### Truth levels
This is how Libertas separates verified findings from ML predictions, as the brief requires.

| Level | Meaning | Example | In the UI |
|---|---|---|---|
| **T0 Observed** | Captured, hashed and timestamped | Screenshot of the listing | Solid |
| **T1 Extracted** | Parsed deterministically from a capture | Wallet address in the post | Solid |
| **T2 Inferred** | Model or heuristic output, with a confidence | 0.87 style match | Dashed, with a % |
| **T3 Corroborated** | Supported by at least two independent signals or sources | Style match plus a shared PGP key | Double line |
| **T4 Verified** | Confirmed by an analyst, with notes | Officer confirms the link | Badge |

Evidence packs present only T0, T1 and T4 as facts. T2 and T3 appear under a separate heading, **"Investigative leads."**

## 13. Intelligence engines

### 13.1 Interpres: understanding text
**Pipeline:** language identification → normalisation (NFKC, confusables, leet, zero-width characters) → decoding of base64 and hex snippets → OCR where policy permits → indicator extraction and validation → India identifier pack (masked, with salted hashes) → watchlist matching (Aho-Corasick, fuzzy and transliteration) → NER (GLiNER, multilingual) → classification (SetFit few-shot on multilingual embeddings, with zero-shot fallback; DarkBERT if academic access is granted) → embeddings (pgvector) → near-duplicate detection (MinHash, SimHash) → translation where needed.

**Leak authenticity scoring** looks at:
- the share of identifiers that pass their checksums (Aadhaar Verhoeff, GSTIN, Luhn)
- geographic consistency (mobile number series and PIN codes against the claimed organisation's region)
- schema plausibility (the fields a hospital would have, compared with a telecom)
- date ranges
- overlap with fingerprints of previously seen leaks (MinHash over hashed sample values)
- the seller's reputation

The result is *likely genuine / recycled / unverifiable / likely fake*, with reasons. **Raw PII is never stored in clear**, only masked display values and salted hashes.

### 13.2 Stilus: who is behind an alias
| Signal family | Examples | Strength |
|---|---|---|
| Operational overlaps | Same PGP key or fingerprint, wallet, Jabber/Tox/Session/Telegram handle or email | Near-deterministic |
| Stylometry | Character 3–5-gram TF-IDF, function words, punctuation, casing, emoji habits, neural authorship embeddings (LUAR-style) | Probabilistic |
| Behaviour | Posting-hour histogram (a hint at timezone, e.g. UTC+5:30), cadence, reply patterns | Supporting |
| Commerce fingerprints | Price formats, escrow preferences, sample file naming, ad templates | Supporting |
| Media | Perceptual-hash reuse of images | Strong when present |

- **Candidates** come from approximate-nearest-neighbour search over embeddings, avoiding n² pairwise comparisons. **Fusion** is a calibrated model (logistic regression or gradient boosting with Platt or isotonic calibration) that outputs a probability and the evidence that contributed to it.
- **Guards:**
  - a minimum amount of text before stylometry counts
  - an **AI-rewrite flag** that lowers stylometry's weight, since 2025 research shows LLM paraphrasing defeats authorship verification
  - a mimicry check for an alias that sits suspiciously close to a famous actor's public posts
- **Wording:** *"Possible link, 0.82, supported by: shared PGP key (T1), style similarity 0.79 (T2), same active hours (T2)."* Libertas never says "is the same person."

### 13.3 Moneta: following the money
- **Address detection and validation** for every supported chain. Data comes from Esplora/mempool.space (BTC), Etherscan API V2 (ETH and EVM chains) and TronGrid/Tronscan (TRON), with self-hosted nodes and indexers later.
- **Bitcoin:** a transaction graph bounded to N hops; common-input clustering that skips CoinJoin-shaped transactions; change-address heuristics (script-type match, round payment amounts, fresh addresses, optimal change), each with a confidence; CoinJoin and mixer detection (equal-value outputs, known coordinator patterns); peel-chain detection; exposure scoring against labelled entities.
- **Labels:** the OFAC SDN digital currency addresses, open datasets of ransomware payments, community TagPacks (GraphSense), analyst tags and exchange clusters.
- **TRON/USDT:** TRC-20 transfer graphs, detection of hops to exchanges, and patterns of peer-to-peer off-ramping. The output names the *nearest regulated exchange*, which feeds the legal-notice draft. Indian VASPs are FIU-IND reporting entities under the PMLA.
- **Monero limitations card.** Stealth addresses, 16-member ring signatures and RingCT hide the sender, receiver and amount. The FCMP++ upgrade (in testing, with a stressnet fork in October 2026 and mainnet expected in 2027) expands the anonymity set to over 150 million outputs, which removes decoy-based heuristics. Libertas therefore focuses on **off-chain XMR intelligence**: address and payment-ID reuse across listings, touchpoints with swap services, requests to exchanges, and view keys from lawfully seized wallets.
- **A heuristic is not proof of ownership.** Every cluster carries a confidence score and a *heuristic* label.
- **Scaling path:** GraphSense (MIT licence, Spark and Cassandra) for BTC and ETH analytics at national scale.

### 13.4 Nexus: connecting the dots
- **Correlation rules:**
  - the same wallet appearing in two or more listings links those listings and accounts
  - the same dataset fingerprint on two sites creates one incident
  - a known actor mentioning a new Indian organisation triggers an escalation alert
  - a style match plus a shared handle produces a T3 link
  - a seller moving to a new forum after a seizure is linked as the same persona
- **Algorithms:** Leiden or Louvain communities (crews), betweenness (brokers), PageRank (influence), link prediction (labelled as prediction), and the **shortest evidence path** between two entities, which answers *"how exactly is this wallet connected to this actor?"*
- **Scoring:** the severity formula (§4, #30), with every factor value shown.

### 13.5 Augur: early warning
- Topic modelling over time windows (BERTopic), detection of new terms, and spike detection per sector.
- **Victim inference.** The attributes of an anonymised listing (country, sector, revenue band, employee count, access type, technology hints) are matched against an Indian organisation registry (MCA company data, sector lists, public revenue bands). The result is a ranked shortlist with reasons, visible only to authorised users and used only for confidential early warning to the organisation and CERT-In.
- An exposure score for each watched organisation.
- An **underground price index** for Indian data: price per record by sector over time, parsed from listings.

## 14. Evidence and legal layer (*Tabularium + Codex*)

- **Chain of custody.** For every capture, Libertas records which collector and policy collected it, when, and how. Every access to it is logged.
- **Timestamps.** RFC 3161 tokens from FreeTSA in the prototype and from a TSA run by an Indian licensed CA in production, optionally with OpenTimestamps anchoring as well.
- **Contents of an evidence pack:**
  - a cover summary
  - a chronological list of captures with their hashes
  - screenshots and extracted text
  - existence windows
  - a graph excerpt with truth levels
  - the WACZ archive, hash manifest and timestamp tokens
  - the chain-of-custody log
  - a **BSA §63 certificate draft**: Part A prefilled with system details and hash values (with the algorithm), plus a Part B worksheet for the examining expert. The Supreme Court upheld §63(4)'s certificate and hash-value requirement in 2026.
- **Legal drafts.** Codex templates that an officer edits:
  - a BNSS §94 notice to a VASP or exchange
  - a Telegram legal-request package with channel and message IDs and timestamps. Telegram reportedly disclosed user data to Indian authorities 14,641 times in 2024.
  - registrar and hosting abuse reports
  - an IT Act §79(3)(b) takedown draft for routing through official channels such as the Sahyog portal
  - a CERT-In incident report
  - a notification to the victim organisation, which helps it meet CERT-In's 6-hour reporting rule and its DPDP breach duties
- **Every output is a draft.** An officer reviews and signs it.

## 15. Security architecture and threat model

- **Identity and access.** Keycloak (OIDC) with WebAuthn/FIDO2 MFA. Roles: Administrator, Supervisor, Investigator, Analyst, Auditor and Liaison, with per-case need-to-know.
- **Lex policy-as-code.** Example rules:
  - Collectors may not send a POST, log in or submit a form unless an active authorisation covers that site and action.
  - The dirty zone has no clearnet egress.
  - Exporting unmasked PII requires a supervisor's approval.
  - Creating or activating a persona requires two approvals.
  - Archives and executables can be downloaded only to the sandbox, and only under a case authorisation.
- **Encryption.** TLS on every internal connection, disk encryption, envelope encryption with per-case keys through OpenBao (the open-source fork of Vault), and column-level encryption of PII.
- **Audit.** An append-only, hash-chained log of every login, search, view, export and policy decision. A daily Merkle root is timestamped externally, so any tampering is detectable.
- **Exports** carry an invisible watermark per officer, so a leaked report can be traced.
- **Network.** Segmented zones, WireGuard VPN for officers, no inbound connections from the internet, and egress allowlists.
- **Supply chain.** Pinned dependencies, an SBOM (Syft), image scanning (Trivy) and signed images (cosign).
- **Resilience.** Encrypted backups with an offline copy, and object lock (WORM) on the evidence store.
- **Data protection.** Minimisation, masking, retention schedules and legal hold. Whether the DPDP Act §17 exemption for prevention, detection and investigation of offences applies is to be confirmed by legal counsel.
- **Where a VPN fits.** A VPN *before* Tor (laptop → VPN → Tor) hides the fact that Tor is in use from the local network and ISP. It doesn't make Tor more anonymous, and it adds a provider who can see connection metadata. Never put a VPN *after* Tor. For development on ShadowNet and legitimate onions a VPN isn't required. If a network blocks Tor, Tor bridges are the first fix. In production, traffic leaves through agency-controlled infrastructure, not a consumer VPN account. Running a VPN such as Proton on the team laptop is harmless in the VPN → Tor order, and is the team's own choice.
- **Tor Browser hygiene for the team.** Keep the default window size (Tor Browser's letterboxing hides your screen size, and full-screen undoes that), use the Safest security level, install no add-ons, and never log in to personal accounts in it.

### How someone would try to bring Libertas down

| Threat | Attack | Defence |
|---|---|---|
| Unmask the agency | Beacon resources, canary documents, timing correlation | Tor-only egress, no clearnet fetches, sandboxed documents, jitter |
| Blind the crawler | Bans, CAPTCHAs, PoW, layout changes | Circuit isolation, politeness, Challenge Desk, alternative sources, drift detection |
| Poison the intelligence | Fake leaks, framing, cloaking | Authenticity scoring, corroboration, differential crawling, truth levels |
| Defeat attribution | LLM paraphrasing, imitation | Multi-signal fusion, AI-rewrite flag, calibrated scores |
| Compromise the platform | Phishing an analyst, exploiting the web app, malware in captured content | MFA, least privilege, content-disarm gate, zone separation, patching |
| Insider misuse | Leaking intelligence, snooping on cases | Need-to-know, two-person approvals, audit chain, watermarks, access-anomaly alerts |
| Discredit the evidence | "The capture was altered" | Hash at capture, RFC 3161, signed WACZ, chain of custody, §63 certificate |
| Overwhelm the analysts | A flood of junk posts | Deduplication, grouping, severity scoring, classifiers trained on feedback |
| Legal exposure | The crawler crosses a line | Lex policy engine, Authorization Ledger, immutable logs |
| Harmful content | Exposure to CSAM | Images off by default, hash-matching, quarantine, escalation |

## 16. Overheads and capacity planning

### 16.1 Where time goes

| Overhead | Typical cost | Mitigation |
|---|---|---|
| First contact with an onion | Measured median ≈ 6.5 s (5.3 s plus a 1–1.5 s descriptor fetch) | Warm keep-alive watch sessions for priority sources |
| Page fetch | Measured: 0.5 s kept-alive, 1.35 s on a new connection, 4.1 s on a new circuit | Concurrency across isolated circuits |
| Descriptor probe | Measured: 1–1.5 s alive, about 5 s dead; one small directory request | Spread probes over time, with a rate cap |
| Headless browser | 5–30 s per page; 300–500 MB RAM | Only when needed, pooled, JS off by default |
| PoW under attack | Milliseconds up to about 1 min per connection | Track effort, back off |
| OCR | 0.5–3 s per image on CPU | Asynchronous, and only for images that pass policy |
| Transformer NER or classifier | About 10–100 ms per post on CPU | Batched, deep lane only |
| Local LLM | Seconds to tens of seconds per answer on CPU | Never in the fast lane; only high-severity summaries and the copilot |
| Blockchain APIs | Rate limits, 100–1000 ms per call | Caching, batching, bounded hops, self-hosted indexers later |
| Storage growth | Screenshots dominate | Content-addressed dedup, zstd compression, tiering, retention |

### 16.2 The prototype on a laptop (Docker Desktop + WSL2)

| Component | Approximate RAM |
|---|---|
| PostgreSQL + pgvector | 0.5–1 GB |
| Neo4j | 1–2 GB |
| Valkey | 0.1 GB |
| 4 Tor clients + i2pd | 0.3 GB |
| API and workers | 1–2 GB |
| ML models (GLiNER, embeddings, classifier) | 1–2 GB |
| 1–2 headless browsers | 0.5–1 GB |
| Dashboard dev server | 0.3 GB |
| *Optional* local LLM (7–8B, 4-bit) | 5–6 GB |

16 GB of RAM is enough without the LLM; 32 GB is comfortable with it. A GPU speeds up the AI parts but isn't required. Keep Docker volumes inside WSL2's own filesystem rather than on `C:\`, which is much faster for databases.

### 16.3 Production (indicative; to be validated by load tests)
- **Collectors:** 3–6 nodes (8 vCPU, 16 GB each) running 20–60 Tor clients in total, plus 2 nodes for Telegram.
- **Processing:** 2–4 nodes with 1–2 GPUs for NLP and the LLM.
- **Data:** PostgreSQL primary and replica, a 3-node OpenSearch cluster, 1–3 graph nodes, and an object store with WORM.
- **Operations:** Kubernetes (k3s or RKE2), Prometheus, Grafana and central logging.

## 17. The lawful boundary (*Lex*)

| Category | How Libertas handles it | Examples |
|---|---|---|
| ✅ **Allowed by default** | Done automatically | Public pages with no login; public Telegram channels; public leak-site pages; CTI feeds; public blockchain data; passive metadata (headers, PGP keys, favicons) |
| 🟡 **Authorised only** (Authorization Ledger plus supervisor approval) | Officers only, within scope, logged | Logged-in access through officer-controlled accounts; interactions needed to reveal content; downloading samples to the sandbox; long-running persona operations |
| ⛔ **Never** | Blocked in code | Exploiting vulnerabilities; using leaked or stolen credentials; brute force; automated CAPTCHA solving; DDoS; querying lookup bots for citizens' data; buying stolen data; storing CSAM; deploying malware |

**Development rule.** Until an authorised pilot, Libertas contacts only ShadowNet and well-known legitimate onion services, as in the §3.3 measurements. Descriptor probes are ordinary Tor client lookups that touch no site content, but they are still rate-limited.

**Legal anchors**, to be validated by the department's legal adviser:
- IT Act 2000: §43, §66, §66B, §67B, §69, §72A, §79, §79A
- BNS 2023: §111 (organised crime), §317, §318
- BNSS 2023: §94
- BSA 2023: §63 and the certificate in its Schedule
- DPDP Act 2023 and DPDP Rules 2025
- CERT-In Directions of 28 April 2022

## 18. Technology stack

| Layer | Prototype (hackathon) | Production |
|---|---|---|
| Languages | Python 3.12 (backend, ML), TypeScript (UI) | Same |
| API | FastAPI with WebSockets | Same, behind a gateway |
| Collectors | asyncio, aiohttp-socks/httpx, tor + stem, Telethon, Playwright/tbselenium | Plus i2pd, Arti (evaluation), distributed workers |
| Event bus and queue | Valkey Streams | NATS JetStream or Kafka |
| System of record | PostgreSQL 16 with pgvector and full-text search | Same, high-availability |
| Graph | Neo4j Community | Neo4j or Memgraph cluster; GraphSense for chains |
| Search | Postgres full-text search | OpenSearch |
| Objects | Content-addressed filesystem | SeaweedFS/S3 with object lock |
| ML | sentence-transformers, GLiNER, SetFit, scikit-learn, Tesseract | Plus GPUs, IndicTrans2, fine-tuned models |
| LLM | Ollama with a small open model (optional) | vLLM on-premises |
| Evidence | warcio, py-wacz, RFC 3161 client, OpenTimestamps, WeasyPrint | Plus an Indian CA's TSA and HSM-backed signing |
| Auth | JWT with roles | Keycloak with WebAuthn, OpenBao |
| Policy | Python policy module (same rules) | OPA/Rego |
| UI | React, Vite, TypeScript, Tailwind, Cytoscape.js, react-force-graph-3d, MapLibre, ECharts | Same |
| Operations | Docker Compose | Kubernetes, Prometheus, Grafana, Loki |

**Licensing.** Prefer permissively licensed or openly governed projects: Valkey over Redis, OpenSearch over Elasticsearch, OpenBao over Vault. Check AGPL obligations (for example RansomLook's) before bundling anything.
**Maps.** Any map of India must use Survey of India–compliant boundaries.

**Phase 0 on the team laptop (16 GB RAM).** The hackathon build runs natively as a modular monolith: Python processes, SQLite in WAL mode, in-process queues and NetworkX for the graph. It uses the official `tor.exe` already installed with Tor Browser, run as separate Libertas-owned instances. This keeps the laptop responsive and the demo free of Docker. The data layer stays swappable for PostgreSQL, Valkey and Neo4j.

**Safety gate before any real source.** Phase 0 enforces egress in code: an allowlist, SOCKS-only clients and remote DNS. Before Phase 1 touches any real source, collectors must move into containers whose *network* allows only Tor.

---

# PART D — MAKING IT REAL

## 19. ShadowNet: the demo world

ShadowNet is a realistic underground built for demonstration, so the demo never touches real criminals or real stolen data.

- **Four real onion services on the Tor network**, restricted with Tor client authorisation so that only Libertas can reach them, and each carrying a **SIMULATION** banner:
  1. **Kaal Forum**, a MyBB-style forum with leaks, access sales and hidden-content threads
  2. **Sona Bazaar**, a marketplace with listings, vendor pages, PGP keys and BTC/XMR prices
  3. **ShadowLock**, a ransomware leak blog with victims and countdown timers
  4. **DeadDrop**, a paste site
  - plus a private Telegram test channel.
- **Fictional Indian organisations:** Kaveri Telecom, Vaigai Health Trust, Coromandel Co-operative Bank, Thamirabarani University and others. No real organisation is named.
- **Synthetic actors:** about 12 aliases controlled by 4 hidden "people". Each person has designed writing quirks, active hours, and reused PGP keys and wallets. Because the ground truth is known, Stilus can be scored honestly.
- **Synthetic money:** a Bitcoin regtest chain (real Bitcoin software running a private chain) with scripted payments, a CoinJoin-shaped transaction and a peel chain. TRON/USDT flows are simulated as data.
- **Synthetic identities in samples** are drawn from ranges never issued to real people (for example Aadhaar-format numbers starting with 1, which UIDAI never issues), and the validators run in a simulation profile. Some samples are deliberately invalid, so the authenticity scorer has something to catch.
- A **demo control panel** schedules background activity and triggers the live post.
- **Adversary mode (#61).** ShadowNet can switch on the defences real sites use: bans, CAPTCHAs, honeypot links, cloaking, proof-of-work, randomised HTML and posts deleted within 60 seconds. The crawler's resilience is tested rather than assumed, and the demo can show Libertas coping live.

## 20. Demo script (about 7 minutes)

| Time | Beat |
|---|---|
| 0:00 | **The problem.** Leaks hit Telegram first, Star Health's data leaked through bots, and access sales precede ransomware by about 20 days. |
| 0:45 | **Libertas in 30 seconds:** the pillars and zones. The coverage observatory shows ShadowNet online and a live time-to-detect heartbeat. |
| 1:30 | **Live incident.** A teammate posts a leak ad on Kaal Forum through Tor Browser, or into the Telegram channel from a phone. The judges watch the clock. **The alert lands on the HoD's phone.** |
| 2:30 | Open the alert: severity explained factor by factor, authenticity *likely genuine*, masked statistics from the sample. |
| 3:15 | **The graph.** The new alias, a Stilus match to a known actor with its evidence list, a shared wallet, the regtest BTC cluster, two earlier listings and the affected organisations. Switch to the 3D view. |
| 4:15 | **Deletion.** The seller deletes the post. Libertas shows *deleted after 2 min* and replays the preserved capture. |
| 4:45 | **Evidence pack.** A PDF with hashes, timestamps, chain of custody and the §63 certificate draft, plus a BNSS §94 notice draft and a victim notification draft. |
| 5:45 | **Lex.** Try to make the crawler log in without authorisation. The policy engine blocks it and the attempt appears in the audit chain: *Libertas cannot cross the line.* |
| 6:15 | Roadmap, and the ask: a pilot with the TN Cyber Crime Wing. |

**Backup:** a pre-recorded video of the full flow, in case the venue network blocks Tor.

## 21. Roadmap

### Phase 0 — Hackathon build (the big step)
Everything tagged **Demo** in §4. Each step in the build order leaves a running system:

1. Repository, Docker Compose, PostgreSQL, Valkey, Neo4j, Tor container.
2. ShadowNet sites, data generator and onion services.
3. Speculatores: Circuit Manager, Pulsus, Aquila with warm watch sessions, pre-contact checks, T1 fetcher, adapters, capture and hashing.
4. Fast lane and Vigiles (dashboard feed and Telegram bot). **This is the first end-to-end milestone.**
5. Interpres deep lane: India pack, classification, authenticity scoring.
6. Nexus graph, Stilus, Moneta (regtest).
7. Tabularium and Codex: timestamps, WACZ, evidence-pack PDF, §63 draft.
8. Forum polish (2D/3D graph, map, timelines), the Lex demo, the audit chain.
9. Rehearsal, failure drills, backup video.

### Phase 1 — Pilot (1–3 months)
Selected real public sources (Tor forums, leak sites, public Telegram channels); a TN organisation watchlist built with consent; Keycloak; OpenSearch; legal review; a TSA from an Indian CA; live ETH and TRON analysis.

### Phase 2 — Operations (3–9 months)
Distributed collectors, victim inference, the copilot, STIX/MISP/OpenCTI interoperability, the Challenge Desk, canary records with partner organisations, and interfaces with I4C platforms through official channels.

### Phase 3 — Scale
Federation across districts and states, GraphSense, models fine-tuned on labelled real data, round-the-clock operations.

## 22. Repository layout (modular monolith)

```
Libertas/
├─ docs/                 blueprint, architecture decisions, runbooks
├─ infra/                docker-compose, tor/i2p configs, policies
├─ libertas/             one Python package, many processes
│  ├─ common/            config, schemas, events, audit client
│  ├─ lex/               policy engine, Authorization Ledger, RBAC
│  ├─ speculatores/      circuits, aquila, fetchers, adapters, telegram, feeds
│  ├─ janus/             gate: scan, content disarm, hashing
│  ├─ tabularium/        vault, timestamps, WACZ, custody
│  ├─ interpres/         normalise, extract, india pack, classify, authenticity
│  ├─ stilus/            stylometry, persona fusion
│  ├─ moneta/            chains, heuristics, labels
│  ├─ nexus/             graph, rules, scoring
│  ├─ vigiles/           alerts, channels, escalation
│  ├─ augur/             trends, victim inference
│  ├─ codex/             cases, evidence packs, legal templates
│  └─ api/               FastAPI app
├─ web/                  React dashboard (Forum)
├─ shadownet/            demo world: sites, generator, regtest scripts
└─ tests/
```

## 23. Success metrics

These are demo targets on ShadowNet's synthetic data. Real-world performance will be lower and has to be measured during the pilot.

| Metric | Target |
|---|---|
| Time-to-detect, priority web source | P95 < 45 s |
| Time-to-detect, Telegram | P95 < 15 s |
| Liveness check (Pulsus) | ≤ 2 s alive, ≤ 7 s dead, no page loaded |
| Captures that are hashed and timestamped | 100% |
| Leak-ad classification F1 (ShadowNet test set) | ≥ 0.90 |
| Alias linking on held-out ShadowNet aliases | ≥ 0.85 top-1 precision |
| Alerts with evidence attached | 100% |
| Policy violations the crawler can perform | 0, proven by tests |

## 24. Inputs needed

1. Laptop specifications: RAM, CPU, GPU and free disk space.
2. Whether Docker Desktop and WSL2 are installed, and which Linux distribution.
3. Telegram: a separate number or account for the demo bot and collector.
4. The venue network: will Tor work there? If not, plan on a mobile hotspot plus the recorded backup.
5. Your teammate's strengths (frontend, ML or backend), to divide the build.
6. Approval of the Latin module names, or replacements.

## 25. References

Research used for this blueprint, all from public sources:

- Tor Project, *Introducing Proof-of-Work Defense for Onion Services* — https://blog.torproject.org/introducing-proof-of-work-defense-for-onion-services
- Tor Project, onion service DoS guidance — https://community.torproject.org/onion-services/advanced/dos/
- Arti 1.7.0 / 1.8.0 release notes — https://blog.torproject.org/arti_1_7_0_released/ · https://blog.torproject.org/arti_1_8_0_released/
- EndGame DDoS filter (ReliaQuest analysis) — https://reliaquest.com/blog/ddos-attacks-dark-web-endgame/
- Netacea, *How cybercriminals restrict access to underground forums* — https://netacea.com/blog/how-cybercriminals-restrict-access-to-underground-forums/
- Campobasso et al., *THREAT/crawl* — https://michelecampobasso.github.io/assets/papers/threatcrawl.pdf
- Turk, Pastrana, Collier, *A tight scrape* (Cambridge) — https://www.cl.cam.ac.uk/~bjc63/tight_scrape.pdf
- *Dizzy: large-scale crawling and analysis of onion services* — https://arxiv.org/abs/2209.07202
- Ransomware.live API — https://github.com/JMousqueton/api.ransomware.live · RansomLook — https://www.ransomlook.io/about
- Cyjax, *From initial access to ransomware attack: timelines* — https://www.cyjax.com/resources/blog/from-initial-access-to-ransomware-attack-an-analysis-of-timelines-from-iab-listings-on-cybercriminal-forums-to-extortion-attacks
- KELA, *BreachForums succession wars 2026* — https://www.kelacyber.com/blog/breachforums-succession-wars-2026/
- CyberInsider, *750 million Indian telecom subscribers' data sold* — https://cyberinsider.com/database-with-info-on-750-million-telecom-subscribers-sold-online/
- Star Health / Telegram chatbots — https://www.fastcompany.com/91194293/telegrams-chatbots-involved-massive-medical-data-breach
- Telegram data disclosures to authorities — https://techcrunch.com/2025/01/07/telegram-reports-spike-in-sharing-user-data-with-law-enforcement/
- I4C Suspect Registry, Samanvaya and Pratibimb — https://theprint.in/india/special-i4c-registry-led-to-blocking-of-rs-8031-cr-cyber-fraud-funds-govt/2802007
- Supreme Court upholds BSA §63(4) — https://www.scconline.com/blog/post/2026/07/08/sc-upholds-admissibility-of-electronic-evidence-under-section-63-4-bsa/
- LiveLaw, *Admissibility of electronic evidence under BSA §63* — https://livelaw.in/articles/electronic-evidence-admissibility-section-63-bhartiya-saksha-adhiniyam-2023-261511
- DSCI, *Insight brief on the DPDP Rules 2025* — https://www.dsci.in/files/content/knowledge-centre/2025/Insight-Brief-on-DPDP-Rules.pdf
- Webrecorder, *WACZ signing and verification* — https://specs.webrecorder.net/wacz-auth/0.1.0/ · Harvard LIL — https://lil.law.harvard.edu/our-work/wacz-signing
- LUAR (EMNLP 2021) — https://aclanthology.org/2021.emnlp-main.70/ · SYSML darknet forum migrants (EMNLP 2021) — https://aclanthology.org/2021.emnlp-main.548
- *Masks and Mimicry: LLM attacks on authorship verification* — https://arxiv.org/pdf/2503.19099.pdf
- GraphSense — https://arxiv.org/pdf/2102.13613 · https://www.ait.ac.at/en/research-topics/data-science-artificial-intelligence/solutions-services/graphsense
- USDT/TRC-20 mule-account laundering in India (Deccan Herald) — https://www.deccanherald.com/amp/story/india%2Futtar-pradesh%2Fup-cyber-mule-accounts-3674185
- Monero FCMP++ status — https://cryptoticker.io/en/monero-fcmp-stressnet-fork-october-2026/
- GLiNER — https://arxiv.org/pdf/2311.08526 · DarkBERT — https://arxiv.org/abs/2305.08596
- Certificate-transparency phishing detection (phishing_catcher) — https://phish.report/blog/phishing-catcher
- Tor specification, onion service descriptor encryption (pow-params, single-onion-service, flow-control) — https://spec.torproject.org/rend-spec/hsdesc-encrypt.html
- Ahmia blacklist (MD5-hashed onion addresses) — https://ahmia.fi/blacklist
- Libertas field measurements, 17 Nov 2026 (§3.3) — scripts and raw results in `research/tor-field-test/`

*Status notes: several sources are secondary reporting. Figures and legal points are marked for verification with the department's legal adviser before any operational use.*
