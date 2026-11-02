"""PDF generation (ReportLab) with corporate header, page numbers and diagonal watermark."""
import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import utcnow as _now

NAVY = colors.HexColor("#1e293b")
ACCENT = colors.HexColor("#4f46e5")

_styles = getSampleStyleSheet()
STYLES = {
    "title": ParagraphStyle("t", parent=_styles["Title"], fontSize=18, textColor=NAVY, spaceAfter=4),
    "sub": ParagraphStyle("s", parent=_styles["Normal"], fontSize=9.5, textColor=colors.HexColor("#475569"),
                          alignment=TA_CENTER, spaceAfter=10),
    "h": ParagraphStyle("h", parent=_styles["Heading2"], fontSize=12.5, textColor=ACCENT, spaceBefore=10,
                        spaceAfter=4),
    "p": ParagraphStyle("p", parent=_styles["Normal"], fontSize=9.5, leading=13.5),
    "cell": ParagraphStyle("c", parent=_styles["Normal"], fontSize=8.5, leading=11),
    "small": ParagraphStyle("sm", parent=_styles["Normal"], fontSize=7.5, textColor=colors.HexColor("#64748b"),
                            leading=10),
}


def P(text, style="p"):
    return Paragraph(escape(str(text if text is not None else "")).replace("\n", "<br/>"), STYLES[style])


def make_pdf(title, subtitle="", blocks=(), watermark=None, footer_note="Boardroom Hub – Confidential"):
    """blocks: list of tuples ("h", text) | ("p", text) | ("table", rows) | ("kv", [(k, v), ...])
    | ("sig", [name, ...]) | ("space", mm)."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=20 * mm,
                            bottomMargin=18 * mm, title=title, author="Boardroom Hub")
    story = [P(title, "title")]
    if subtitle:
        story.append(P(subtitle, "sub"))
    width = A4[0] - 32 * mm
    for block in blocks:
        kind = block[0]
        if kind == "h":
            story.append(P(block[1], "h"))
        elif kind == "p":
            story.append(P(block[1]))
            story.append(Spacer(1, 3))
        elif kind == "space":
            story.append(Spacer(1, block[1] * mm))
        elif kind in ("table", "kv"):
            rows = block[1]
            if not rows:
                story.append(P("No records.", "small"))
                continue
            if kind == "kv":
                data = [[P(k, "cell"), P(v, "cell")] for k, v in rows]
                t = Table(data, colWidths=[width * 0.3, width * 0.7])
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            else:
                data = [[P(c, "cell") for c in row] for row in rows]
                t = Table(data, repeatRows=1, colWidths=[width / len(rows[0])] * len(rows[0]))
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP")]))
                for c in range(len(rows[0])):
                    data[0][c] = Paragraph(f"<font color='white'><b>{escape(str(rows[0][c]))}</b></font>",
                                           STYLES["cell"])
            story.append(t)
            story.append(Spacer(1, 6))
        elif kind == "sig":
            names = block[1]
            cells = [[P("_______________________", "p") for _ in names], [P(n, "cell") for n in names]]
            t = Table(cells, colWidths=[width / max(1, len(names))] * len(names))
            story.append(Spacer(1, 10))
            story.append(t)

    stamp = _now().strftime("%Y-%m-%d %H:%M UTC")

    def decorate(canvas, doc_):
        canvas.saveState()
        canvas.setStrokeColor(ACCENT)
        canvas.setLineWidth(1.2)
        canvas.line(16 * mm, A4[1] - 13 * mm, A4[0] - 16 * mm, A4[1] - 13 * mm)
        canvas.setFont("Helvetica-Bold", 8.5)
        canvas.setFillColor(NAVY)
        canvas.drawString(16 * mm, A4[1] - 11 * mm, "ENTERPRISE GOVERNANCE & BOARDROOM MEETING HUB")
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(16 * mm, 10 * mm, f"{footer_note} · Generated {stamp}")
        canvas.drawRightString(A4[0] - 16 * mm, 10 * mm, f"Page {doc_.page}")
        if watermark:
            canvas.setFont("Helvetica-Bold", 30)
            canvas.setFillColor(colors.Color(0.31, 0.27, 0.9, alpha=0.08))
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 20, "CONFIDENTIAL")
            canvas.setFont("Helvetica", 13)
            canvas.drawCentredString(0, -10, watermark)
        canvas.restoreState()

    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return buf.getvalue()
