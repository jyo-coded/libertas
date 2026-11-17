"""Evidence report PDF. Facts (T0/T1) and investigative leads (T2/T3) are kept visibly separate; personal data
is masked; times are shown in IST, as Indian courts expect."""
from __future__ import annotations

import os
import re
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle

_UNSUPPORTED = re.compile("[\U00010000-\U0010FFFF\u2600-\u27BF\uFE0F]")
_FONTS: tuple[str, str] | None = None
INK, MUTED, LINE, WARN = colors.HexColor("#1b1f24"), colors.HexColor("#5b6470"), colors.HexColor("#c9ced6"), colors.HexColor("#b3261e")
HEAD_BG, LEAD_BG = colors.HexColor("#eef1f5"), colors.HexColor("#fff6e5")


def _fonts() -> tuple[str, str]:
    global _FONTS
    if _FONTS:
        return _FONTS
    regular, bold = "Helvetica", "Helvetica-Bold"
    win = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    try:
        if (win / "arial.ttf").exists() and (win / "arialbd.ttf").exists():
            pdfmetrics.registerFont(TTFont("LibSans", str(win / "arial.ttf")))
            pdfmetrics.registerFont(TTFont("LibSans-Bold", str(win / "arialbd.ttf")))
            regular, bold = "LibSans", "LibSans-Bold"
    except Exception:
        pass
    _FONTS = (regular, bold)
    return _FONTS


def _clean(text, limit: int | None = None) -> str:
    t = _UNSUPPORTED.sub("", str(text if text is not None else ""))
    return t[:limit] if limit else t


def _styles() -> dict:
    regular, bold = _fonts()
    base = getSampleStyleSheet()
    s = {
        "title": ParagraphStyle("t", parent=base["Title"], fontName=bold, fontSize=20, textColor=INK, spaceAfter=4),
        "h1": ParagraphStyle("h1", parent=base["Heading2"], fontName=bold, fontSize=12.5, textColor=INK, spaceBefore=10,
                             spaceAfter=5),
        "body": ParagraphStyle("b", parent=base["BodyText"], fontName=regular, fontSize=9, leading=12, textColor=INK),
        "small": ParagraphStyle("s", parent=base["BodyText"], fontName=regular, fontSize=7.5, leading=9.5, textColor=MUTED),
        "cell": ParagraphStyle("c", parent=base["BodyText"], fontName=regular, fontSize=7.8, leading=9.6, textColor=INK),
        "cellb": ParagraphStyle("cb", parent=base["BodyText"], fontName=bold, fontSize=7.8, leading=9.6, textColor=INK),
        "mono": ParagraphStyle("m", parent=base["Code"], fontName="Courier", fontSize=6.6, leading=8.2, textColor=INK,
                               leftIndent=0, firstLineIndent=0),
        "pre": ParagraphStyle("p", parent=base["Code"], fontName="Courier", fontSize=7, leading=8.6, textColor=INK,
                              leftIndent=0, firstLineIndent=0),
        "warn": ParagraphStyle("w", parent=base["BodyText"], fontName=bold, fontSize=9, leading=12, textColor=WARN),
        "lead": ParagraphStyle("l", parent=base["BodyText"], fontName=regular, fontSize=8.6, leading=11.4, textColor=INK,
                               leftIndent=8, bulletIndent=0),
    }
    return s


def _p(text, style) -> Paragraph:
    return Paragraph(escape(_clean(text)), style)


def _table(rows: list[list], widths: list[float], header: bool = True, bg=None) -> Table:
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
             ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), HEAD_BG))
    if bg is not None:
        style.append(("BACKGROUND", (0, 1 if header else 0), (-1, -1), bg))
    t.setStyle(TableStyle(style))
    return t


def _pre(text: str, style, width: int = 118, max_lines: int = 140) -> Preformatted:
    lines = []
    for raw in _clean(text).splitlines() or [""]:
        lines.extend(textwrap.wrap(raw, width) or [""])
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"... ({len(lines) - max_lines} more lines in the pack's text file)"]
    return Preformatted("\n".join(lines), style)


def build_report_pdf(path: Path, ctx: dict) -> None:
    s = _styles()
    regular, bold = _fonts()
    W = A4[0] - 32 * mm

    def decorate(canvas, doc):
        canvas.saveState()
        if ctx["simulation"]:
            canvas.setFont(bold, 58)
            canvas.setFillColor(colors.Color(0.85, 0.15, 0.15, alpha=0.08))
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, "SIMULATION")
            canvas.rotate(-35)
            canvas.translate(-A4[0] / 2, -A4[1] / 2)
        canvas.setFont(bold, 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(16 * mm, A4[1] - 11 * mm, f"LIBERTAS EVIDENCE PACK {ctx['pack_id']}")
        canvas.drawRightString(A4[0] - 16 * mm, A4[1] - 11 * mm, "CONFIDENTIAL: LAW ENFORCEMENT")
        canvas.setFont(regular, 7)
        canvas.drawString(16 * mm, 10 * mm, f"Generated {ctx['generated_ist']}  ·  {ctx['system']}  ·  signing key "
                                            f"{ctx['signing_fingerprint'][:16]}…")
        canvas.drawRightString(A4[0] - 16 * mm, 10 * mm, f"page {doc.page}")
        canvas.restoreState()

    story = [_p("Evidence report", s["title"]), _p(ctx["pack_id"], s["small"]), Spacer(1, 4)]
    if ctx["simulation"]:
        story.append(_p("SIMULATION: this pack was produced from ShadowNet training data. Every organisation, person, "
                        "wallet and identifier in it is fictional.", s["warn"]))
        story.append(Spacer(1, 4))
    deep = ctx.get("deep") or {}
    summary = [
        ["Subject", ctx["item"]["title"]],
        ["Source", f"{ctx['source']['name']} · {ctx['source']['onion']}.onion"],
        ["Posted by (alias)", ctx["item"]["author"] or "—"],
        ["Category", ctx["category"]],
        ["Organisations named", ", ".join(ctx["orgs"]) or "none"],
        ["Severity", f"fast lane {ctx['fast_severity']} · deep lane {deep.get('severity', 'n/a')} (score {ctx['score']})"],
        ["Generated", f"{ctx['generated_ist']}  ({ctx['generated_utc']} UTC)"],
        ["Unit / operator", f"{ctx['unit']} / {ctx['operator']}"],
        ["Evidence signing key", f"Ed25519 · {ctx['signing_fingerprint']}"],
    ]
    story.append(_table([[_p(k, s["cellb"]), _p(v, s["cell"])] for k, v in summary], [38 * mm, W - 38 * mm], header=False))

    e = ctx["existence"]
    story += [_p("1. Existence window", s["h1"]),
              _table([[_p(h, s["cellb"]) for h in ("Claimed post time (by the site)", "First seen by Libertas",
                                                   "Last seen present", "First seen absent (deleted)")],
                      [_p(e["claimed_posted_ist"], s["cell"]), _p(e["first_seen_ist"], s["cell"]),
                       _p(e["last_seen_ist"], s["cell"]), _p(e["first_seen_absent_ist"], s["cell"])]],
                     [W / 4] * 4),
              _p("Times are in IST. The claimed post time comes from the site and is not independently verified; "
                 "the other times come from Libertas's own capture records.", s["small"])]

    story.append(_p("2. Facts: observed and extracted (T0/T1)", s["h1"]))
    rows = [[_p(h, s["cellb"]) for h in ("#", "Captured (IST)", "HTTP", "Bytes", "SHA-256 of the original capture",
                                          "Merkle batch / timestamp")]]
    for i, c in enumerate(ctx["captures"]):
        rows.append([_p(str(i + 1), s["cell"]), _p(c["fetched_ist"], s["cell"]), _p(str(c["status"]), s["cell"]),
                     _p(str(c["bytes"]), s["cell"]), _p(c["sha256"], s["mono"]),
                     _p(f"batch {c['batch_id']}: {c['tsa_time_ist']}", s["cell"])])
    story.append(_table(rows, [7 * mm, 31 * mm, 11 * mm, 14 * mm, 83 * mm, W - 146 * mm]))
    if ctx["indicators"]:
        story.append(Spacer(1, 5))
        rows = [[_p(h, s["cellb"]) for h in ("Indicator", "Value (personal data masked)", "Valid")]]
        for ind in ctx["indicators"][:40]:
            rows.append([_p(ind["kind"], s["cell"]), _p(ind["display"], s["mono"]),
                         _p({1: "yes", 0: "no"}.get(ind["valid"], "unverified"), s["cell"])])
        story.append(_table(rows, [32 * mm, W - 52 * mm, 20 * mm]))

    story += [_p("3. Captured content (first capture; personal data masked)", s["h1"]), _pre(ctx["text"], s["pre"])]

    story.append(_p("4. Investigative leads: inferred, NOT proof (T2/T3)", s["h1"]))
    story.append(_p("The following are produced by automated analysis (authenticity tests, stylometry, operational "
                    "overlaps and blockchain heuristics). They direct investigation; they do not establish identity "
                    "or ownership.", s["small"]))
    for r in deep.get("reasons", []) or ["Deep-lane analysis not available for this item."]:
        story.append(Paragraph(escape(_clean(r)), s["lead"], bulletText="•"))
    if ctx.get("attribution_links"):
        rows = [[_p(h, s["cellb"]) for h in ("Linked alias", "Source", "P", "Truth", "Evidence families")]]
        for l in ctx["attribution_links"][:10]:
            rows.append([_p(l["alias"], s["cell"]), _p(l["source"], s["cell"]), _p(f"{l['probability']:.3f}", s["cell"]),
                         _p(l["truth"], s["cell"]), _p(", ".join(sorted({x.get('kind') or x['family'] for x in l['evidence']})),
                                                       s["cell"])])
        story += [Spacer(1, 4), _table(rows, [34 * mm, 38 * mm, 14 * mm, 14 * mm, W - 100 * mm], bg=LEAD_BG)]
    if ctx.get("exposures"):
        rows = [[_p(h, s["cellb"]) for h in ("Wallet in the post", "Cluster", "Destination entity", "BTC", "Deposits")]]
        for x in ctx["exposures"]:
            rows.append([_p(x["wallet"], s["mono"]), _p(x["cluster"], s["cell"]), _p(x["entity"], s["cell"]),
                         _p(str(x["btc"]), s["cell"]), _p(str(len(x["deposits"])), s["cell"])])
        story += [Spacer(1, 4), _table(rows, [62 * mm, 26 * mm, W - 116 * mm, 14 * mm, 14 * mm], bg=LEAD_BG)]

    story.append(_p("5. Integrity, timestamps and chain of custody", s["h1"]))
    rows = [[_p(h, s["cellb"]) for h in ("Batch", "Merkle root (SHA-256)", "Leaves", "Independent timestamp (IST)",
                                          "Timestamp authority")]]
    for bid, b in ctx["batches"].items():
        rows.append([_p(str(bid), s["cell"]), _p(b["root"], s["mono"]), _p(str(b["size"]), s["cell"]),
                     _p(b["tsa_time_ist"], s["cell"]), _p(b["tsa_name"], s["cell"])])
    story.append(_table(rows, [12 * mm, 83 * mm, 13 * mm, 30 * mm, W - 138 * mm]))
    audit = ctx["audit"]
    audit_text = (f"intact ({audit['entries_checked']} entries, head {audit.get('head', '')[:16]}…)" if audit.get("ok")
                  else f"BROKEN at entry {audit.get('broken_at_seq')}")
    story.append(_p(f"Each batch root is signed with the Libertas evidence key (Ed25519, fingerprint "
                    f"{ctx['signing_fingerprint']}). Hash-chained audit log at export: {audit_text}. Identical "
                    f"re-checks are condensed here; manifest.json lists every custody event.", s["small"]))
    rows = [[_p(h, s["cellb"]) for h in ("Time (IST)", "Actor", "Event", "Target", "Decision / detail")]]
    for c in ctx["custody_view"][-45:]:
        rows.append([_p(c["time_ist"], s["cell"]), _p(c["actor"], s["cell"]), _p(c["action"], s["cell"]),
                     _p(c["target"], s["cell"]), _p(c["detail"], s["cell"])])
    story += [Spacer(1, 4), _table(rows, [30 * mm, 22 * mm, 30 * mm, 34 * mm, W - 116 * mm])]

    story += [PageBreak(), _p("Annex A: Certificate under Section 63(4)(c), BSA 2023 (draft)", s["h1"]),
              _pre(ctx["section63_text"], s["pre"], width=112, max_lines=400)]
    story += [PageBreak(), _p("Annex B: Legal-request drafts in this pack", s["h1"])]
    for name, desc in ctx["legal_files"]:
        story.append(Paragraph(f"<b>{escape(name)}</b>: {escape(_clean(desc))}", s["body"]))
    story += [_p("Annex C: How to verify this pack independently", s["h1"]), _pre(ctx["verify_text"], s["pre"])]

    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=17 * mm,
                            bottomMargin=16 * mm, title=f"Libertas evidence pack {ctx['pack_id']}", author="Libertas",
                            subject=ctx["item"]["title"][:120])
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
