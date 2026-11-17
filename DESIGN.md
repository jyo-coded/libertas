---
name: Libertas Forum
description: The Libertas investigator console, a police signals log whose entries clear like cheques.
colors:
  rail: "#2e3a24"
  rail-hover: "#38462d"
  rail-current: "#475839"
  rail-ink: "#e9eddf"
  rail-pencil: "#b9c2a8"
  rail-line: "rgb(233 237 223 / 0.14)"
  pad-ground: "#eef1ea"
  pad-ground-deep: "#e3e8dc"
  voucher-white: "#ffffff"
  voucher-tint: "#f6f8f3"
  rule: "#d5dbcc"
  rule-strong: "#b4bca8"
  pad-margin-rule: "#e6c2c8"
  ink: "#1b2116"
  ink-soft: "#394133"
  pencil: "#5b6169"
  pencil-dark: "#474d54"
  flash: "#b42318"
  immediate: "#b54708"
  priority: "#1d4ed8"
  routine: "#5b6169"
  cleared-violet: "#5b3fa0"
  cleared-paper: "#f4f0fb"
  returned-maroon: "#8a1538"
  returned-paper: "#fcf0f3"
  watching-green: "#3f7a2a"
  watching-green-on-rail: "#a6d58f"
  exercise-ochre: "#efc845"
  exercise-ink: "#2b2200"
  exercise-line: "#b8901c"
typography:
  headline:
    fontFamily: "Public Sans Variable, Public Sans, system-ui, sans-serif"
    fontSize: "1.45rem"
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Public Sans Variable, Public Sans, system-ui, sans-serif"
    fontSize: "1.36rem"
    fontWeight: 650
    lineHeight: 1.25
    letterSpacing: "-0.01em"
  section:
    fontFamily: "Public Sans Variable, Public Sans, system-ui, sans-serif"
    fontSize: "0.96rem"
    fontWeight: 650
    lineHeight: 1.5
  body:
    fontFamily: "Public Sans Variable, Public Sans, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  body-small:
    fontFamily: "Public Sans Variable, Public Sans, system-ui, sans-serif"
    fontSize: "0.82rem"
    fontWeight: 400
    lineHeight: 1.4
  label:
    fontFamily: "Red Hat Mono, ui-monospace, Cascadia Mono, Consolas, monospace"
    fontSize: "0.74rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0.08em"
  precedence:
    fontFamily: "Red Hat Mono, ui-monospace, Cascadia Mono, Consolas, monospace"
    fontSize: "0.8rem"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.07em"
  stamp-sm:
    fontFamily: "Public Sans Variable, Public Sans, system-ui, sans-serif"
    fontSize: "0.74rem"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "0.13em"
  stamp-lg:
    fontFamily: "Public Sans Variable, Public Sans, system-ui, sans-serif"
    fontSize: "1.45rem"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "0.17em"
  data:
    fontFamily: "Red Hat Mono, ui-monospace, Cascadia Mono, Consolas, monospace"
    fontSize: "0.92rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "0"
    fontFeature: "tnum"
  captured:
    fontFamily: "Red Hat Mono, ui-monospace, Cascadia Mono, Consolas, monospace"
    fontSize: "0.8rem"
    fontWeight: 400
    lineHeight: 1.55
rounded:
  tag: "2px"
  sheet: "3px"
  control: "4px"
spacing:
  hair: "0.35rem"
  sm: "0.5rem"
  md: "0.75rem"
  pad: "1.25rem"
  section: "1.4rem"
  rail-width: "13.75rem"
  rail-width-collapsed: "4.25rem"
components:
  precedence-flash:
    backgroundColor: "{colors.flash}"
    textColor: "{colors.voucher-white}"
    typography: "{typography.precedence}"
    rounded: "{rounded.tag}"
    padding: "0.3rem 0.4rem"
    width: "6.4rem"
  precedence-immediate:
    backgroundColor: "{colors.immediate}"
    textColor: "{colors.voucher-white}"
    typography: "{typography.precedence}"
    rounded: "{rounded.tag}"
    padding: "0.3rem 0.4rem"
    width: "6.4rem"
  precedence-priority:
    backgroundColor: "{colors.priority}"
    textColor: "{colors.voucher-white}"
    typography: "{typography.precedence}"
    rounded: "{rounded.tag}"
    padding: "0.3rem 0.4rem"
    width: "6.4rem"
  precedence-routine:
    textColor: "{colors.routine}"
    typography: "{typography.precedence}"
    rounded: "{rounded.tag}"
    padding: "0.3rem 0.4rem"
    width: "6.4rem"
  stamp-cleared-sm:
    backgroundColor: "{colors.cleared-paper}"
    textColor: "{colors.cleared-violet}"
    typography: "{typography.stamp-sm}"
    rounded: "{rounded.sheet}"
    padding: "0.32rem 0.45rem 0.3rem 0.57rem"
    width: "6.4rem"
  stamp-returned-sm:
    backgroundColor: "{colors.returned-paper}"
    textColor: "{colors.returned-maroon}"
    typography: "{typography.stamp-sm}"
    rounded: "{rounded.sheet}"
    padding: "0.32rem 0.45rem 0.3rem 0.57rem"
    width: "6.4rem"
  stamp-uncleared-sm:
    textColor: "{colors.pencil}"
    typography: "{typography.stamp-sm}"
    rounded: "{rounded.sheet}"
    padding: "0.32rem 0.45rem 0.3rem 0.57rem"
    width: "6.4rem"
  stamp-cleared-lg:
    backgroundColor: "{colors.cleared-paper}"
    textColor: "{colors.cleared-violet}"
    typography: "{typography.stamp-lg}"
    rounded: "{rounded.sheet}"
    padding: "0.6rem 0.85rem 0.56rem 1.05rem"
  stamp-returned-lg:
    backgroundColor: "{colors.returned-paper}"
    textColor: "{colors.returned-maroon}"
    typography: "{typography.stamp-lg}"
    rounded: "{rounded.sheet}"
    padding: "0.6rem 0.85rem 0.56rem 1.05rem"
  memo-cleared:
    backgroundColor: "{colors.cleared-paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sheet}"
    padding: "0.6rem 0.8rem 0.65rem"
  memo-returned:
    backgroundColor: "{colors.returned-paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sheet}"
    padding: "0.6rem 0.8rem 0.65rem"
  memo-uncleared:
    textColor: "{colors.pencil}"
    rounded: "{rounded.sheet}"
    padding: "0.6rem 0.8rem 0.65rem"
  voucher:
    backgroundColor: "{colors.voucher-white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sheet}"
    padding: "1rem 1.25rem 1.5rem"
    width: "48rem"
  counterfoil:
    backgroundColor: "{colors.voucher-tint}"
    textColor: "{colors.ink}"
    padding: "0.7rem 1.25rem 0.75rem"
  lead:
    textColor: "{colors.pencil}"
    rounded: "{rounded.sheet}"
    padding: "0.62rem 0.8rem"
  passbook:
    backgroundColor: "{colors.voucher-white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sheet}"
    padding: "1.1rem 1.4rem 1.6rem"
    width: "68rem"
  button:
    backgroundColor: "{colors.voucher-white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0 0.95rem"
    height: "2.3rem"
  button-hover:
    backgroundColor: "{colors.voucher-tint}"
  button-primary:
    backgroundColor: "{colors.rail}"
    textColor: "{colors.rail-ink}"
    rounded: "{rounded.control}"
    padding: "0 0.95rem"
    height: "2.3rem"
  button-danger:
    backgroundColor: "{colors.flash}"
    textColor: "{colors.voucher-white}"
    rounded: "{rounded.control}"
    padding: "0 0.95rem"
    height: "2.3rem"
  input:
    backgroundColor: "{colors.voucher-white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
  rail-item:
    backgroundColor: "{colors.rail}"
    textColor: "{colors.rail-ink}"
    padding: "0.6rem 1rem"
  rail-item-hover:
    backgroundColor: "{colors.rail-hover}"
  rail-item-current:
    backgroundColor: "{colors.rail-current}"
    textColor: "{colors.rail-ink}"
  exercise-strip:
    backgroundColor: "{colors.exercise-ochre}"
    textColor: "{colors.exercise-ink}"
    padding: "0.45rem 1rem"
  sim-tag:
    backgroundColor: "{colors.exercise-ochre}"
    textColor: "{colors.exercise-ink}"
    rounded: "{rounded.tag}"
    padding: "0.12rem 0.35rem"
---

# Design System: Libertas Forum

## Overview

**Creative North Star: "The Signals Log That Clears Like Cheques"**

Forum is a police message pad crossed with a bank's clearing desk. Every alert is logged as a signal message with a precedence and an IST date-time group, written first in pencil as UNCLEARED, and then struck with the deep lane's ink stamp: violet CLEARED or maroon RETURNED, with the reason pinned on a slip the way a bank pins a return memo to a dishonoured cheque. The officer reads urgency from precedence and time, and reads truth from ink versus pencil.

The shell is an olive-khaki signal rail and masthead around a grey-green message-pad ground; the working documents (voucher, passbook, sheets) are white paper with a faint sheet shadow. Density is that of a working tool: ruled rows, tabular figures, tight 3px corners, no cards for their own sake. Source health is one ruled board, the money trail is a passbook ledger, and the open section is notched into the page from the rail. It refuses the category default of KPI cards stacked over a severity table.

The world is light only, by use scene: a lit judging room, a projector, and officers' desks. A projector mode raises the root size and firms the rules and graphite instead of switching themes. Simulation is never in doubt: an ochre EXERCISE strip sits above everything on every route.

**Key Characteristics:**
- Olive rail and masthead, grey-green pad ground, white paper sheets.
- Ink for facts, pencil graphite with dashed rules for leads and anything not yet ruled.
- Four precedence tags carry the urgency; two clearing stamps carry the verdict.
- Red Hat Mono for the signal form (DTGs, codes, hashes, figures, captured text); Public Sans for everything read as prose.
- One authored motion: the stamp landing on an UNCLEARED message.
- No raster imagery: icons are lucide SVG components, the brand mark and favicon are hand-authored SVG.

## Colors

A khaki-and-paper field palette in which saturated colour is reserved for precedence, verdict and simulation.

### Primary
- **Signal Rail Olive** (`rail`): the rail, the masthead, primary buttons, the pressed segment, and actor nodes in the graph. Its hover (`rail-hover`) and current-section (`rail-current`) steps exist only on the rail. Text on it is **Rail Bone** (`rail-ink`); secondary text, icons and Latin module names on it are **Rail Pencil** (`rail-pencil`), and dividers inside it are `rail-line`.

### Secondary: precedence
- **FLASH Red** (`flash`): FLASH tags and counts, critical post borders in the graph, and by extension halt and failure (the kill switch hover, failing source health, the danger button).
- **IMMEDIATE Amber** (`immediate`): IMMEDIATE tags, counts and graph borders.
- **PRIORITY Blue** (`priority`): PRIORITY tags, counts and graph borders.
- **ROUTINE Slate** (`routine`): ROUTINE tags, set as an outlined tag rather than a filled one so it reads as quieter.

### Tertiary: clearing and simulation
- **Clearing Violet** (`cleared-violet`): the CLEARED stamp and Clearing note, and also the focus ring and the evidence path in the graph (path edges, path nodes, path relation labels). Its paper is `cleared-paper`.
- **Return Maroon** (`returned-maroon`): the RETURNED stamp, the Return memo head and markers, failure text, and "gone" facts. Its paper is `returned-paper`.
- **EXERCISE Ochre** (`exercise-ochre`): the EXERCISE strip and the SIMULATED tag, with `exercise-ink` text and an `exercise-line` bottom rule.
- **Watching Green** (`watching-green`, and `watching-green-on-rail` on the olive): healthy source dots and an intact audit chain. Never a verdict colour.

### Neutral
- **Message-Pad Ground** (`pad-ground`): the page ground and graph canvas; **Pad Ground Deep** (`pad-ground-deep`) under the voucher pane, log column heads and the backfill divider.
- **Voucher White** (`voucher-white`): vouchers, passbook, sheets, boards and inputs; **Voucher Tint** (`voucher-tint`) for counterfoils, lane boxes, captured text, ledger heads and row hover.
- **Rule** (`rule`) and **Rule Strong** (`rule-strong`): hairlines and control borders; Rule Strong also draws every dashed (pencil) rule.
- **Pad Margin Rule** (`pad-margin-rule`): the single pink margin line running down the log between the DTG and the subject.
- **Fact Ink** (`ink`) and **Ink Soft** (`ink-soft`): facts, titles, body text.
- **Pencil Graphite** (`pencil`) and **Pencil Dark** (`pencil-dark`): leads, UNCLEARED, labels, ages, metadata. In projector mode both darken (to #4c5259 and #3d4248) and the rules firm up (#c4ccb8, #9da890).

### Named Rules
**The Ink and Pencil Rule.** Facts are set in ink on solid rules; leads and anything not yet ruled are set in pencil graphite on dashed rules. A lead is never set in ink, whatever its probability.

**The Violet Thread Rule.** Violet means "cleared and evidenced": the CLEARED stamp, the focus ring, and the evidence path in the graph. It is never used for decoration or for any other state.

**The Ochre Means Exercise Rule.** Ochre appears only where simulation is declared: the EXERCISE strip and the SIMULATED tag.

## Typography

**Display Font:** none; there is no display face.
**Body Font:** Public Sans Variable (with Public Sans, system-ui, sans-serif), self-hosted through fontsource.
**Label/Mono Font:** Red Hat Mono 400 and 600 (with ui-monospace, Cascadia Mono, Consolas, monospace), self-hosted through fontsource.

**Character:** a plain civic sans for everything read as language, and a typewriter-like mono for everything copied off a signal form. Weights step in small increments (450, 500, 600, 650), with 800 kept for the stamps.

Root sizes: **16px** on the desk, **18px** in projector mode (`data-display="projector"`), **15px** on phones (760px and below, in either mode). All type is in rem, so it scales with the root.

### Hierarchy
- **Headline** (650, 1.45rem, 1.2, -0.01em): view titles such as Message log, with the Latin module name set beside them.
- **Title** (650, 1.36rem to 1.4rem, 1.25): voucher, passbook and sheet titles.
- **Section** (650, 0.96rem): voucher section heads, followed by a rule that runs to the right edge (dashed for pencil sections).
- **Body** (400, 1rem, 1.5): facts, memo reasons, prose. Intros are capped at 64 to 72ch.
- **Body small** (400, 0.78rem to 0.9rem): fact labels, metadata, ages, notes, mostly in pencil.
- **Label** (Red Hat Mono 600, 0.74rem to 0.78rem, 0.04em to 0.08em, uppercase): log column heads, ledger heads, memo heads, the backfill divider.
- **Precedence** (Red Hat Mono 600, 0.8rem, 0.07em, uppercase): precedence tags and masthead counts.
- **Stamp** (Public Sans 800, uppercase): 0.74rem at 0.13em in the log, 1.45rem at 0.17em on the voucher.
- **Data** (Red Hat Mono, tabular figures): DTGs and times (0.92rem, 600 in the log), message numbers, hashes, scores and P values, aliases.
- **Captured** (Red Hat Mono 400, 0.8rem, 1.55, pre-wrap): captured post text.

### Named Rules
**The Signal-Form Mono Rule.** Red Hat Mono is allowed only for what a signals clerk would copy character by character: DTGs and clock times, MSG/ACT/INC codes, hashes and addresses, figures, scores and probabilities, aliases, captured text, and the signal-form labels (precedence words, column and ledger heads, memo heads, Latin module names, the EXERCISE words). Titles, facts, reasons and leads are set in Public Sans.

**The Legibility Floor Rule.** Nothing that carries meaning is set below 0.74rem: precedence tags, stamps, ages, column heads, legends and the phone EXERCISE strip all sit at 0.74rem or larger. On desk the EXERCISE strip is 0.92rem.

## Layout

The frame is a three-row grid: the EXERCISE strip, the masthead, then the rail beside the scrolling main area, filling 100dvh. The rail is 13.75rem wide and shares its column with the brand cell of the masthead.

The message log view splits the main area 58 / 42 between the log and the voucher pane (the voucher pane has a 23rem minimum). The log is a five-column grid: ack mark, precedence, DTG, subject, clearing, with `pad` (1.25rem) side padding and a 0.75rem column gap. A pink margin rule runs between the DTG and the subject through the header and every row. Rows are at least 3.75rem tall, ruled with hairlines; backfill sits below a labelled divider; source health sits under the log as one ruled board. Index views use a list and detail split (about 36 / 64); paper documents are centred and capped (voucher 48rem, sheets 62rem, passbook 68rem).

Spacing runs on a small set of steps: 0.35rem and 0.5rem inside components, 0.75rem between columns and items, 1.25rem as the pane gutter, and 1.4rem between voucher sections.

Breakpoints, all max-width:
- **1599px:** the masthead "Unacknowledged" label and the Projector button text become screen-reader only.
- **1365px:** the rail collapses to 4.25rem icons, with labels and Latin names kept for screen readers and in tooltips; the log and voucher split moves to 56 / 44.
- **1180px:** the masthead sub-line is dropped, the kill switch shows only its icon, and the log columns tighten (1rem gutter, 0.6rem gap).
- **760px:** phones. The root drops to 15px and the layout becomes one column. The rail becomes a sticky horizontal tab strip whose notch points down. The log and the voucher show one at a time. Message rows wrap the subject under the precedence line. Ledgers keep a minimum width (38rem, the passbook 44rem) and scroll sideways rather than crush.

## Elevation & Depth

Depth is almost entirely tonal and ruled: the olive frame, the pad ground, and white paper laid on it. One shadow exists, and it belongs to paper.

### Shadow Vocabulary
- **Sheet** (`box-shadow: 0 1px 2px rgb(27 33 22 / 0.06), 0 12px 30px -16px rgb(27 33 22 / 0.24)`): vouchers, the passbook and record sheets, the documents an officer would hold.
- **Stamp double rule** (`box-shadow: inset 0 0 0 1.5px <paper>, inset 0 0 0 2.5px <ink>` small; `inset 0 0 0 2.5px <paper>, inset 0 0 0 4px <ink>` large): not depth but the stamp's own inner frame, drawn with inset shadows on the stamp's paper colour.
- **Status halo** (`box-shadow: 0 0 0 3px` at 0.18 to 0.2 alpha): the collection dot in the masthead only.

### Named Rules
**The One Sheet Rule.** Only paper documents lift off the pad. Boards, rows, memos, leads, controls and tags stay flat and are separated by rules.

## Shapes

The form language is ruled stationery: hairline borders, dashed rules for pencil, and very small corners. There are three radii: 2px for tags (precedence, SIMULATED, peel), 3px for paper and slips (vouchers, stamps, memos, leads, boards, captured text), and 4px for controls (buttons, inputs, segments). Dots are the only round shapes (ack, health, collection). Three stationery cuts recur: the counterfoil's dashed perforation with half-circle punches at each end, the triangular notch that ties the current rail item to the page, and the matching notch on the selected log or index row pointing into the detail pane.

## Components

### Precedence Tag
A signal-form tag that always carries its word, so colour is never the only cue.
- **Shape:** 2px corners, 6.4rem minimum width (5.4rem on phones), mono 0.8rem uppercase.
- **Variants:** FLASH, IMMEDIATE and PRIORITY are filled with their colour and set in white; ROUTINE is outlined in slate on no fill.
- **Masthead counts:** the same colours as a split tag, the name on colour and the count on white. A zero count recedes into the rail as an outline in rail pencil.

### Clearing Stamp
The deep lane's verdict, struck like a clearing-house stamp.
- **Small (log):** straight, fixed 6.4rem width, 0.74rem, 800 weight, with a 1.5px border plus an inset double rule on the stamp's paper.
- **Large (voucher):** 1.45rem with a 2.5px double rule, tilted by a small per-message angle (between about -2.6 and -4.3 degrees) so it reads as struck by hand.
- **CLEARED:** violet on violet paper. **RETURNED:** maroon on maroon paper.
- **UNCLEARED:** pencil text on a 1px dashed pencil border, 600 weight, no fill and no tilt.
- **Motion:** `stamp-land`, 560 ms on `cubic-bezier(0.16, 1, 0.3, 1)` (expo-out). The stamp falls from scale 1.85 with a 1.5px blur, overshoots to 0.94, settles through 1.025 to 1, and keeps its tilt throughout. It plays once, only when a message changes from UNCLEARED to CLEARED or RETURNED, in the log and the voucher together. Under `prefers-reduced-motion: reduce` it is disabled.

### Memo Slip
The verdict's reason, pinned under the large stamp in the Clearing section.
- **Clearing note:** violet paper, a #c8bce6 border, and a violet mono uppercase head.
- **Return memo:** maroon paper, a #e3b3c0 border, and a maroon head.
- **Awaiting the deep lane:** dashed pencil border, no fill, pencil text.
- **Body:** the reason in body type, then supporting checks as a square-marker list below a dashed rule, with markers in the verdict colour.

### Voucher and Counterfoil
The white paper document for one message, carrying the sheet shadow and 3px corners.
- **Counterfoil:** a voucher-tint strip holding the MSG number, precedence tag, DTG, SIMULATED tag and acknowledgement state. Pending acknowledgement is an ink dot with ink text; acknowledged is pencil.
- **Perforation:** a dashed strong rule, with 1rem half-circle punches cut at both ends in the pane's ground colour.
- **Body sections:** Clearing (the fast-lane and deep-lane boxes, plus a factor table in a disclosure), Facts in ink, Leads in pencil, Captured text, and Next actions.

### Facts and Leads
- **Facts:** a two-column definition list (8.75rem pencil label, ink value) separated by faint hairlines; it stacks on phones.
- **Leads:** each lead is a pencil card with a 1px dashed strong border and 3px corners, with its title in pencil dark. A grade column on the right gives the truth level (T1 to T3, with a plain label) and the mono P value. Lead sections have a pencil icon and a dashed section rule. In the graph, lead edges are dashed pencil.

### Message Log Row
- **Default:** ink-soft title at 450 weight, clamped to 2 lines; pencil metadata separated by middots.
- **Unacknowledged:** an ink dot in the ack column, with the title in ink at 650 weight.
- **Acknowledged:** a pencil check. **Backfill:** a short rule.
- **Hover:** voucher tint. **Selected:** white, with a notch pointing into the voucher pane. **Focus:** the violet ring is drawn inset.

### Passbook Ledger
The money trail, set as an Indian bank passbook.
- **Head:** a 2px ink rule under the title, with totals as uppercase pencil labels over 1.05rem figures.
- **Table:** an ink rule under the column heads, vertical hairlines between columns, right-aligned tabular figures, and dates printed as DD-MM-YYYY with IST labelled.
- **Exit rows:** a pale tan fill (#f6f2e4). Peel hops are marked with a dashed pencil tag.
- **Generic ledgers:** use the same ruled table, with the head on voucher tint.

### Source-Health Board
One white ruled board under the log, divided into equal cells by hairlines (two columns on phones). Each cell gives the source name, a green or red state dot with its word, and pencil detail lines. It is never a row of separate cards.

### Navigation (Rail)
Each item has an 18px lucide icon, a plain-English label at 0.93rem, and the Latin module name in small pencil mono beside it.
- **Hover:** the rail hover step. **Current:** the rail current step, at 600 weight, with a triangular notch in the page ground cut into the right edge.
- **Footer:** the audit chain state (green shield, or red when broken) and the "Policy:" line.
- **Collapsed and mobile:** collapses to icons at 1365px, and becomes a horizontal strip on phones.

### Buttons and Inputs
- **Shape:** 4px corners. Buttons are 2.3rem tall (smaller at `btn--sm`), Public Sans 600 at 0.9rem.
- **Default:** a white button with a strong rule; on hover it fills with voucher tint and the border goes to ink soft.
- **Primary:** rail olive. **Danger:** FLASH red. **On-rail:** a transparent ghost with a bone border.
- **Inputs:** white with a strong rule; on focus the border and the 2px focus ring turn violet.
- **Transitions:** colour transitions run 150 ms (state feedback only) and are removed under reduced motion.

### EXERCISE Strip and SIMULATED Tag
- **Strip:** a full-width ochre band above the masthead on every route. It repeats "EXERCISE" in mono 600 at 0.16em letter spacing, followed by a plain sentence saying all data is simulated. It is 0.92rem on desk and 0.74rem on phones, where one word remains and the sentence wraps rather than truncates.
- **SIMULATED tag:** an ochre 2px tag, 0.78rem 700 uppercase, in the counterfoil and the facts.

### Captured Text
Captured text is set in a mono `pre`: pre-wrap, `overflow-wrap: anywhere`, on a tinted panel with a 14rem maximum height, focusable for scrolling. Identifiers in it arrive already masked.

### Iconography and Imagery
Icons are lucide-react SVG components at 13 to 18px. The brand mark (a ruled square with an L-shaped stroke) is inline SVG, and the favicon is a hand-authored SVG at `web/public/favicon.svg`. There are no shipping rasters, so no raster provenance applies.

## Do's and Don'ts

### Do:
- **Do** rank every message by precedence first and then by DTG, and show the precedence word in its tag, never colour alone.
- **Do** log a message in pencil as UNCLEARED (dashed, no fill) until the deep lane rules, then strike the stamp in place with `stamp-land` exactly once.
- **Do** keep log stamps straight at a fixed 6.4rem width, and tilt only the large voucher stamp.
- **Do** carry every verdict's reason on a Clearing note or Return memo slip under the large stamp.
- **Do** show every time in IST and say so ("IST" on the clock, on full dates and in passbook headings); DTGs follow the DDHHMM MON YY form.
- **Do** set captured content as plain text in a mono `pre`, and display personal identifiers and names only in the masked form the server sends (for example `S****** P.`).
- **Do** keep the EXERCISE strip visible and untruncated at every width while the data is simulated, and repeat a SIMULATED tag on the counterfoil.
- **Do** keep the Latin module names as secondary labels: small, in pencil mono, beside the plain-English label and never instead of it.
- **Do** raise the root to 18px and darken the rules and graphite for the projector, rather than adding a theme.

### Don't:
- **Don't** set a lead, an attribution or a cluster link in ink or on a solid rule; leads stay in pencil on dashed rules.
- **Don't** render captured HTML or any captured content as markup, or unmask an identifier on the client.
- **Don't** ship a dark theme; the use scene (a lit room, a projector, desks) is light by contract.
- **Don't** use violet, maroon or ochre for anything except clearing, return and simulation (violet also marks focus and the evidence path).
- **Don't** stack KPI cards over a severity table, or break source health into a row of cards.
- **Don't** add authored motion beyond the stamp landing, or play it on page load or on stamps that were already ruled.
- **Don't** set meaningful text below 0.74rem.
- **Don't** add a second shadow or lift rows, slips, tags or controls off the pad; only paper documents carry the sheet shadow.
