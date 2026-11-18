# Libertas — Phase 0 (hackathon build)

Dark Web Intelligence & Monitoring Platform for the TN Cyber Police hackathon (PS-04).

- Design: [docs/LIBERTAS_BLUEPRINT.md](docs/LIBERTAS_BLUEPRINT.md)
- Progress and measurements: [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md)

## Safety first

- **Development mode.** Libertas can reach only ShadowNet (our fictional underground) and a few legitimate benchmark onions. Lex refuses everything else, including all clearnet traffic.
- **Zero execution.** Libertas keeps text and metadata only. It runs no JavaScript and downloads no files. Raw responses are stored gzip-compressed and without file extensions in `var/quarantine/`, so nothing can open them by accident.
- **Kill switch.** Use Halt collection in the Forum header, which refuses every new request and also cuts the ones already on the wire. From a terminal, run `python -m libertas kill`; Lex then refuses every new request, though a request already in flight can still finish. Every halt is written to the audit chain.
- **Localhost hardening.** The API answers only to a local Host header. Writes need the Forum's own client header, so a web page on another site cannot trigger them. The live feed refuses foreign origins. Personal identifiers are masked before any text reaches the browser.
- **Everything in ShadowNet is fictional.** Domains use the reserved `.example` TLD, and identity numbers come from ranges never issued to real people.

## Run it (Windows, from `C:\JyoBuilds\Libertas`)

1. One-time setup:
   ```
   python -m venv .venv
   .venv\Scripts\python -m pip install -r requirements.txt
   ```
2. Terminal 1 starts the fictional underground on Tor. Add `--reseed` for a fresh world:
   ```
   .venv\Scripts\python -m shadownet up
   ```
3. Terminal 2 starts Libertas:
   ```
   .venv\Scripts\python -m libertas up
   ```
4. Open both pages:
   - **Forum, the investigator console:** http://127.0.0.1:8700/ (the earlier minimal page is at `/classic`)
   - **ShadowNet control panel** (local only, never on Tor): http://127.0.0.1:8600/

   Press a preset in the panel and watch the alert arrive.
5. Measure detection and deletion timing end to end:
   ```
   .venv\Scripts\python scripts\demo_measure.py
   ```

Run the tests with `.venv\Scripts\python -m pytest -q`.

## Rehearse and drill (M7)

With ShadowNet and Libertas both running:

- **Demo rehearsal:** runs blueprint §20 end to end and times every beat. The beats are the live incident, the explainable verdict, the graph, deletion, an evidence pack verified offline, the Lex boundary test, the kill switch and the audit chain. `--runs 3` is the acceptance test.
  ```
  .venv\Scripts\python scripts\rehearse.py --runs 3
  ```
- **Failure drills:** break things on purpose:
  - a Tor client crash;
  - a source going offline;
  - a CAPTCHA wall;
  - an HTTP 429 rate limit;
  - randomised page markup;
  - posts deleted after 60 s;
  - the kill switch mid-run.

  Add `deadline` to run the 4-minute ransomware countdown.
  ```
  .venv\Scripts\python scripts\drills.py all
  ```
- **Lex boundary test:** ask the crawler to log in, leave Tor or download a file, and see every attempt refused and audited. It is also a button on the Policy & audit page.
  ```
  .venv\Scripts\python -m libertas drill-lex
  ```
- **Backup video:** start Windows' screen recorder (Win + Alt + R, or the Snipping Tool's video mode), then run `scripts\rehearse.py --pace 8`. It pauses 8 s after each beat so the Forum can be shown on screen.

Results appear on the Forum's **Readiness** page, next to the live heartbeat. The heartbeat is a canary onion that changes every minute, so time to detect is measured around the clock. ShadowNet's adversary modes can also be switched by hand in its control panel.

The built Forum ships in `libertas/api/forum/`. To change and rebuild it (Node 20+):
```
cd web
npm install
npm run build
```
While editing, `npm run dev` serves it on http://localhost:5173 and forwards `/api` and `/ws` to a running Libertas.

## What runs

- **Fast lane, within seconds of capture:** normalisation, watchlist matching, indicator extraction and an explainable severity score, producing a *provisional* alert.
- **Deep lane, about a second later:** leak authenticity, Stilus attribution, Moneta chain forensics (against ShadowChain, the simulated Bitcoin ledger on port 8605) and Nexus incidents. The alert becomes *deep-confirmed* or is downgraded, with reasons.
- **Forum:** the message log ranks unacknowledged traffic by precedence. Each message is logged UNCLEARED, and the deep lane's CLEARED or RETURNED stamp lands in place. The voucher keeps facts (ink) apart from leads (pencil), with Acknowledge and Build evidence pack. Further views cover incidents, actors, the graph, the money passbook, the explorer, evidence, sources, and policy and audit.
- **Interactive API docs:** http://127.0.0.1:8700/api/docs. Useful endpoints include `/api/alerts`, `/api/actors`, `/api/links`, `/api/incidents`, `/api/wallets/{address}`, `/api/graph?focus=item:ID` and `/api/path?a=...&b=...`.

## Notes

- **Tor.** Both programs start their own Tor instances from the `tor.exe` installed with Tor Browser; set `LIBERTAS_TOR_EXE` to use another. Tor Browser itself doesn't need to be open. Each Tor instance exits automatically when its parent program stops.
- **Telegram alerts (optional).** Create a bot with @BotFather yourself, then set `LIBERTAS_TELEGRAM_BOT_TOKEN` and `LIBERTAS_TELEGRAM_CHAT_ID` in the terminal before step 3. CRITICAL and HIGH alerts on fresh posts are then pushed to that chat.
- **Viewing ShadowNet in Tor Browser.** ShadowLock is public. The other three sites ask for a client key; the control panel shows it.
