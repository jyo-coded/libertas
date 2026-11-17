# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

React + Vite + TypeScript single-page app (confirmed by the user, 18 Nov 2026), served by the existing Libertas FastAPI
backend on localhost: REST under `/api`, live events over the WebSocket `/ws`. Backend is Python 3.13; Node 22 builds the UI.

## Users

- **Primary:** investigators and analysts of the Tamil Nadu Cyber Crime Wing. They watch the dark web for threats to Indian
  (especially Tamil Nadu) organisations, triage alerts, follow leads across aliases, wallets and sites, and prepare
  court-ready evidence. They work under time pressure and must be able to defend every claim in court.
- **Evaluating audience (now):** hackathon judges, the user's Head of Department and a government technology consultant,
  watching a live demo. Officers come first (confirmed); the dashboard should demo well because it looks and behaves like
  a working tool, not a showpiece.

## Product Purpose

Libertas turns underground cybercrime activity into correlated, court-ready, actionable intelligence. It:
- watches Tor, I2P and Telegram sources;
- raises an alert within seconds of a post;
- confirms or corrects each alert about a second later with deeper analysis (authenticity, attribution, money trail,
  incidents);
- produces evidence packs that verify independently.

Success: an officer sees a credible threat fast, understands why it matters, and can act on it with evidence that holds up.

## Positioning

- **Two-speed intelligence:** a provisional alert in seconds, then a deep-lane verdict that can downgrade fakes and recycled
  leaks before anyone is paged.
- **Facts and leads are always separated** (truth levels T0–T4). Attribution and blockchain clustering are investigative
  leads, never proof.
- **Evidence first:** every capture is hashed, Merkle-sealed, signed and RFC 3161 timestamped, and packs verify without
  Libertas.
- **Lawful by design:** a policy engine (Lex) enforces the legal boundary in code, with a kill switch and a tamper-evident
  audit chain.

## Operating Context

- **Demo:** shown both on a projector or big screen to a room and up close on the laptop (Windows, 1920×1080-class).
  The layout must stay legible at projection distance and still reward close inspection.
- **Daily use (future):** officers at desks in long sessions. Live updates arrive continuously, and urgent alerts also go to
  phones via Telegram.
- **Data:** everything is currently SIMULATED (ShadowNet: fictional organisations, aliases, wallets and identifiers), and
  every screen must make that obvious.
- **Language:** English UI. Tamil support is undecided.

## Capabilities and Constraints

**Backend capabilities already exposed by the API:**
- source health (Aquila watch sessions, Pulsus descriptor intelligence);
- alerts (fast lane and deep lane), items and search;
- item detail with indicators, versions and captures, plus the deep assessment;
- actors and alias links (Stilus);
- wallets and clusters with exchange exposure (Moneta);
- incidents, the graph and evidence paths (Nexus);
- evidence packs (build and download) and Tabularium batch status;
- audit verification and tail, kill switch and resume, and a WebSocket event stream.

**Constraints:**
- Never render captured HTML or any captured content as markup: text only (stored-XSS safety), under a strict CSP
  (`script-src 'self'`).
- Personal identifiers appear only masked; the backend never exposes raw values.
- Leads (T2/T3) must be visually distinct from facts (T0/T1/T4).
- Runs offline on localhost: no external CDNs, web fonts or analytics at runtime.
- Times are shown in IST for officers, with UTC available on demand.

## Brand Commitments

- **Name:** Libertas.
- **Module names** are Latin and part of the product language:
  - Speculatores (collection), Aquila (scheduler), Pulsus (descriptor sensor), Janus (gate)
  - Tabularium (evidence vault), Interpres (understanding), Stilus (attribution), Moneta (money), Nexus (graph)
  - Vigiles (alerts), Augur (early warning), Codex (cases and evidence), Forum (this dashboard), Lex (law and policy)
- **Line in use:** "Justice wears a blindfold so she judges without bias. Libertas keeps its eyes wide open, and still
  acts only on evidence."
- **Tone:** sober, precise, evidential. No hype and no hacker clichés.

## Evidence on Hand

- **Live data** from the running system (simulated): about 40 items, alerts across CRITICAL/HIGH/MEDIUM, 4 recovered
  actors, a wallet cluster with exchange exposure, 6 incidents, and evidence packs.
- **Measured results** in `docs/BUILD_PLAN.md`: detection about 12–25 s, deep confirmation about 1 s, 60 tests passing.
- **Absences:** no real cases, customers, endorsements or deployments exist, and none may be implied.

## Product Principles

1. **Evidence before assertion:** every number and claim leads back to captures and hashes.
2. **Speed with humility:** show provisional verdicts instantly, then show how and why they changed.
3. **Leads are not proof:** make inference and uncertainty visible, never hidden.
4. **Lawful by construction:** safety controls (kill switch, policy, audit) are first-class, not settings.
5. **Calm under pressure:** an officer should know within five seconds what needs attention now.

## Accessibility & Inclusion

- Projector legibility: large type, strong contrast, no colour-only meaning.
- Keyboard navigation for core workflows.
- Respects reduced-motion preferences.
