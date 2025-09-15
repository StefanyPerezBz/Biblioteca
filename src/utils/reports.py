# src/utils/reports.py
# Generación robusta de PDF solo en memoria
from __future__ import annotations
from io import BytesIO
from datetime import datetime
from typing import List, Dict, Optional

try:
    from zoneinfo import ZoneInfo
    LIMA = ZoneInfo("America/Lima")
except Exception:
    LIMA = None

_HAS_REPORTLAB = False
_HAS_FPDF = False
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.platypus.tables import LongTable, TableStyle
    _HAS_REPORTLAB = True
except Exception:
    pass

if not _HAS_REPORTLAB:
    try:
        from fpdf import FPDF
        _HAS_FPDF = True
    except Exception:
        pass

# -------------------------
# Utilidades de formateo
# -------------------------
def _fmt12(ts: object) -> str:
    try:
        ival = int(ts)
    except Exception:
        return str(ts)
    if LIMA is not None:
        return datetime.fromtimestamp(ival, tz=LIMA).strftime('%d/%m/%Y %I:%M %p')
    return datetime.fromtimestamp(ival).strftime('%d/%m/%Y %I:%M %p')


def _translate_headers(keys: List[str]) -> List[str]:
    mapping = {
        "prestamo_id": "ID",
        "titulo": "Título",
        "autor": "Autor",
        "usuario": "Usuario",
        "role": "Rol",
        "cantidad": "Cantidad",
        "fecha_prestamo": "Fecha de préstamo",
        "fecha_devolucion_estimada": "Devolución estimada",
        "fecha_devolucion_real": "Devolución real",
        "observaciones": "Observaciones",
        "atrasado": "¿Atrasado?",
        "libro_id": "ID Libro",
        "editorial": "Editorial",
        "isbn": "ISBN",
        "categoria": "Categoría",
        "ejemplares_disponibles": "Disponibles",
        "ejemplares_totales": "Totales",
        "prestados_activos": "Prestados activos",
        "veces_prestado": "Veces prestado",
        "sancion_id": "ID Sanción",
        "motivo": "Motivo",
        "monto": "Monto",
        "fecha_inicio": "Inicio",
        "fecha_fin": "Fin",
        "reserva_id": "ID Reserva",
        "fecha_reserva": "Fecha de reserva",
        "fecha_expiracion": "Expira",
        "estado": "Estado",
    }
    return [mapping.get(k, k.replace("_", " ").capitalize()) for k in keys]


def _format_cell(key: str, val: object) -> str:
    if val is None:
        return "-"
    k = (key or "").lower()
    if k.startswith("fecha_") or k.endswith("_ts") or k.endswith("_epoch"):
        return _fmt12(val)
    if k in ("atrasado",):
        s = str(val)
        if s in ("1", "True", "true", "Sí", "Si"):
            return "Sí"
        if s in ("0", "False", "false", "No"):
            return "No"
    if k == "role":
        return str(val).capitalize()
    if k == "estado":
        return str(val).capitalize()
    if k == "monto":
        try:
            return f"S/ {float(val):.2f}"
        except Exception:
            return str(val)
    return str(val)

# -------------------------
# Render con REPORTLAB 
# -------------------------
def _render_with_reportlab(datos: List[Dict], titulo: str) -> bytes:
    from reportlab.platypus import KeepTogether

    if not datos:
        datos = [{"mensaje": "Sin datos para mostrar"}]
    keys = list(datos[0].keys())
    headers = _translate_headers(keys)

    styles = getSampleStyleSheet()
    body_style = ParagraphStyle("BodySmall", parent=styles["BodyText"], fontSize=9, leading=11)
    head_style = ParagraphStyle("HeadSmall", parent=styles["Heading4"], fontSize=10, leading=12)

    table_data = []
    table_data.append([Paragraph(str(h), head_style) for h in headers])
    for row in datos:
        table_data.append([Paragraph(_format_cell(k, row.get(k, "")), body_style) for k in keys])

    pagesize = A4 if len(headers) <= 7 else landscape(A4)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=pagesize, title=titulo or "Reporte",
                            leftMargin=1.3 * cm, rightMargin=1.3 * cm,
                            topMargin=1.7 * cm, bottomMargin=1.7 * cm)

    page_width, page_height = pagesize
    available_width = page_width - (doc.leftMargin + doc.rightMargin)

    from reportlab.platypus import LongTable, TableStyle
    col_widths = [available_width / len(headers)] * len(headers)

    table = LongTable(table_data, colWidths=col_widths, repeatRows=1, splitByRow=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F0F0F0")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
    ]))

    story = []
    story.append(Paragraph(titulo or "Reporte", styles["Heading2"]))
    ahora = datetime.now(tz=LIMA) if LIMA else datetime.now()
    story.append(Paragraph(f"Generado: {ahora.strftime('%d/%m/%Y %I:%M %p')}", styles["Normal"]))
    story.append(Spacer(1, 8))
    story.append(table)

    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        text = f"Página {doc_.page}"
        canvas.drawRightString(page_width - doc_.rightMargin, 1.0 * cm, text)
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

# -------------------------
# Render con FPDF (fallback)
# -------------------------
def _render_with_fpdf(datos: List[Dict], titulo: str) -> bytes:
    if not datos:
        datos = [{"mensaje": "Sin datos para mostrar"}]
    keys = list(datos[0].keys())
    headers = _translate_headers(keys)

    landscape_mode = len(headers) > 7
    pdf = FPDF(orientation="L" if landscape_mode else "P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, txt=(titulo or "Reporte"), ln=1)
    pdf.set_font("Arial", "", 9)
    ahora = datetime.now(tz=LIMA) if LIMA else datetime.now()
    pdf.cell(0, 8, txt=f"Generado: {ahora.strftime('%d/%m/%Y %I:%M %p')}", ln=1)
    pdf.ln(2)

    col_w = [pdf.w / len(headers)] * len(headers)

    pdf.set_font("Arial", "B", 9)
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 8, h, border=1)
    pdf.ln()

    pdf.set_font("Arial", "", 8)
    for row in datos:
        for i, k in enumerate(keys):
            pdf.multi_cell(col_w[i], 5, _format_cell(k, row.get(k, "")), border=1, align="L", max_line_height=5)
            x = pdf.get_x() + col_w[i]
            y = pdf.get_y() - 5
            pdf.set_xy(x, y)
        pdf.ln()

    pdf_bytes = pdf.output(dest="S").encode("latin1")
    return pdf_bytes

# ==============================
# API PÚBLICA
# ==============================
def generar_reporte_pdf(report_id: str, datos: List[Dict], titulo: Optional[str] = None) -> bytes:
    if not datos:
        datos = [{"mensaje": "Sin datos para mostrar"}]

    if _HAS_REPORTLAB:
        return _render_with_reportlab(datos, titulo or "Reporte")
    if _HAS_FPDF:
        return _render_with_fpdf(datos, titulo or "Reporte")

    raise RuntimeError("❌ No se encontró un motor para generar PDF. Instala reportlab o fpdf.")


def generar_reporte_excel(*args, **kwargs):
    raise NotImplementedError("❌ Solo se exporta PDF. Excel no está habilitado en este proyecto.")

def obtener_datos_reporte(*args, **kwargs):
    return []
