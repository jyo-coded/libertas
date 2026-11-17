# Finish review packet: Forum (Libertas investigator console)

- **Build type:** code-led. There is no approved comp and no raster assets; every surface is HTML, CSS and SVG icons (lucide).
- **Direction contract:** `.impeccable/surfaces/web-src-app-tsx.md`. Source brief: `.impeccable/decision/forum-brief.md`. Product context: `PRODUCT.md`.
- **Mode:** Operate. Judged live on a projector and a laptop by a police HoD and a TNSTDC consultant.

## Shipped code

- **`web/src/`**
  - `main.tsx`, `App.tsx`: hash routes.
  - `Shell.tsx`: EXERCISE strip, masthead, rail.
  - `components.tsx`: precedence tag, clearing stamp, facts and leads, states.
  - `store.tsx`: live socket, clock, stamp-landing detection.
  - `format.ts`: IST date-time groups, precedence and clearing mapping, codes.
  - `hooks.ts`
  - `styles.css`: all tokens and styles; light only, by use scene.
  - `views/`: LogView and Voucher, Incidents, Actors, Graph (Cytoscape), Money (passbook), Explorer, ItemView, Evidence, Sources, Lex.
- **Built output:** `libertas/api/forum/`, served by FastAPI at `http://127.0.0.1:8700/`. The previous page is kept at `/classic`.

## Screenshots

These are from one batched inspection round plus one confirm round, all in `.impeccable/review/`.

- **Desktop, 1440×900:**
  - `desktop-01-log-first-viewport.jpg`: the first viewport, with log and voucher.
  - `desktop-02-voucher-leads.jpg`, `desktop-03-voucher-actions-pack.jpg`: the lower voucher after Acknowledge and Build evidence pack.
  - `desktop-04-incidents.jpg` through `desktop-12-lex.jpg`.
  - `desktop-06-graph.jpg` is the confirm-round capture, after the switch to a concentric layout.
- **Mobile, 375×812:**
  - `mobile-01-log.jpg`, `mobile-02-voucher.jpg`.
  - `mobile-03-passbook.jpg`: the confirm round, after the table min-width fix.

## Contract items and where they live

- **EXERCISE strip:** `Shell.tsx` `ExerciseStrip`, styled under `.exercise`. A SIMULATED tag also appears in the voucher facts.
- **Header:** unacknowledged precedence counts, collection state, time to detect, IST clock and kill switch with an inline confirm. A projector toggle sets larger type and firmer rules.
- **Olive rail:** plain-English labels, with the Latin module names set small beside them. The open section is notched into the page.
- **Message log (58%):** ranked by precedence, then DTG.
  - An unacknowledged mark (ink dot) stays until ACK.
  - A pad margin rule runs between the DTG and the subject.
  - Backfill entries sit below a divider.
  - Source health appears as one ruled board under the log.
- **Voucher (42%):**
  - A counterfoil (MSG number, precedence, DTG, ack state) above a perforation with punched notches.
  - The large clearing stamp.
  - Sections: Clearing (fast lane vs deep lane, plus a factor table), Facts in ink, Leads in pencil (dashed, graded by truth level and P), Captured text (masked, plain text in a `pre`), Next actions (recommended steps, Acknowledge, Build evidence pack, follow links).
- **Signature move:** a row is logged UNCLEARED in pencil (dashed graphite). When the deep-lane verdict arrives, `store.tsx` detects the UNCLEARED→CLEARED/RETURNED transition in a layout effect, and `.stamp--landing` plays once: 560 ms, expo-out, scale 1.85→1, a blur that clears, and the per-message tilt kept. It is verified live: MSG-0041 went UNCLEARED, then RETURNED 1.03 s later, then landing. Reduced motion disables it.
- **Stamps:** violet CLEARED, maroon RETURNED. Each has a double rule from inset shadows on its own paper colour, and an SVG turbulence mask for ink wear.
- **Type:** Public Sans Variable and Red Hat Mono, both self-hosted through fontsource. Mono is used only for DTGs, codes, hashes, figures, aliases and captured text.

## Known trade-offs to judge

- Most backfill rows are FLASH, because the simulated world is mostly critical leaks, so red dominates the lower log.
- The graph labels are small at depth 3.
- At 1365 px and below the rail collapses to icons; the labels stay available to screen readers and in tooltips.
- There is no dark theme. The use scene is a lit judging room and a projector, and the world is light by contract.

## Finish review: disposition "fix", and what was done

1. **Names unmasked:** fixed. `mask_pii` now masks the name cell of any sample row carrying a masked identifier, e.g. `S****** P.` (tests in `tests/test_masking.py`). The Lex rule text names it.
2. **Fake stamp texture:** fixed.
   - The turbulence mask is gone.
   - Log stamps are straight with a fixed width.
   - The voucher stamp is 1.45rem with a 2.5px double rule.
   - The RETURNED reason now travels on a "Return memo" slip; a "Clearing note" slip carries the CLEARED reason.
3. **Latin module names:** kept by decision. `PRODUCT.md` Brand Commitments names them as product language, and the user-approved blueprint uses them. They stay small, pencil and secondary. The rail footer now reads "Policy:".
4. **Seed key:** fixed. `6236d055` is corroborated from the concept-seed output (pool c3b204a1eed6) and recorded in `direction-round-1.json`.
5. **SIMULATION:** fixed.
   - The strip is saturated ochre `#efc845` at 0.92rem and never truncated.
   - A SIMULATED tag sits in the counterfoil.
6. **Legibility floor:** fixed. Root is 16px on desk and 18px on the projector. Precedence tags, stamps, ages, column heads and legends are at 0.74rem or larger. Collapse points moved to 1599, 1365 and 1180.
7. **Graph:** fixed. Labels are 12.5px and wrap at 150px. Posts show the MSG number plus the title with bracket tags stripped. Layout is rings by hop count.
8. **Labels:**
   - Fixed: "score 62.3 of 100" on both lanes, IST date and time on both lanes, and "Ruled 1.0 s after the fast lane".
   - Fixed: authenticity reads "Likely fake, authenticity score 0.55 of 1". Passbook dates are labelled IST.

Confirm captures:
- `desktop-13-confirm-log-voucher.jpg`.
- `desktop-14-confirm-graph-crop.jpg`: the pane captured a crop of the 1440 viewport.

The UNCLEARED pencil state lasts about 1 s live. It was verified by a DOM recorder during a live `fake_leak` run: MSG-0041 went UNCLEARED, then RETURNED 1034 ms later, then landed.
