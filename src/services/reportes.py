# src/services/reportes.py - Reportes y estadísticas por rol 
import os
from typing import List, Dict, Tuple, Optional
import streamlit as st
import pandas as pd
from datetime import datetime, date, time as dt_time, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from src.database.database import DatabaseManager
from src.utils.alert_utils import show_sweet_alert

try:
    from src.utils.reports import generar_reporte_pdf 
except Exception:
    generar_reporte_pdf = None

LIMA = ZoneInfo("America/Lima")


# ---------------------------
# Utilidades generales
# ---------------------------
def _fmt12(ts) -> str:
    """Convierte epoch a 'DD/MM/YYYY hh:mm AM/PM' (hora Lima)."""
    try:
        return datetime.fromtimestamp(int(ts), tz=LIMA).strftime('%d/%m/%Y %I:%M %p')
    except Exception:
        return "-"


def _date_defaults() -> Tuple[date, date]:
    hoy = date.today()
    return hoy - timedelta(days=30), hoy


def _to_ts_range(d1: date, d2: date) -> Tuple[int, int]:
    """Convierte fechas a epoch [00:00:00, 23:59:59]."""
    if d1 > d2:
        d1, d2 = d2, d1
    start = int(datetime.combine(d1, dt_time.min).timestamp())
    end = int(datetime.combine(d2, dt_time.max).timestamp())
    return start, end


def _traducir_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Traduce encabezados y normaliza valores visibles en la UI sin afectar la BD.
    """
    if df is None or df.empty:
        return df

    if "atrasado" in df.columns:
        df["atrasado"] = df["atrasado"].map({1: "Sí", True: "Sí", 0: "No", False: "No"}).fillna(df["atrasado"])

    if "role" in df.columns:
        df["role"] = df["role"].astype(str).str.capitalize()

    if "estado" in df.columns:
        df["estado"] = df["estado"].astype(str).str.capitalize()

    mapping = {
        # préstamos
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
        # libros / inventario
        "libro_id": "ID Libro",
        "editorial": "Editorial",
        "isbn": "ISBN",
        "categoria": "Categoría",
        "ejemplares_disponibles": "Disponibles",
        "ejemplares_totales": "Totales",
        "prestados_activos": "Prestados activos",
        "veces_prestado": "Veces prestado",
        # sanciones
        "sancion_id": "ID Sanción",
        "motivo": "Motivo",
        "monto": "Monto",
        "fecha_inicio": "Inicio",
        "fecha_fin": "Fin",
        # reservas
        "reserva_id": "ID Reserva",
        "fecha_reserva": "Fecha de reserva",
        "fecha_expiracion": "Expira",
    }

    rename_cols = {c: mapping[c] for c in df.columns if c in mapping}
    if rename_cols:
        df = df.rename(columns=rename_cols)

    return df


def _mostrar_df(datos: List[Dict], formato_humano: bool = True):
    """Muestra DataFrame formateando epoch a 12h y traduciendo encabezados a español."""
    if not datos:
        st.info("No hay datos para el periodo/criterio seleccionado.")
        return

    df = pd.DataFrame(datos)

    if formato_humano:
        for col in df.columns:
            if (col.startswith("fecha_") or col.endswith("_ts") or col.endswith("_epoch")) and df[col].notna().any():
                try:
                    df[col] = df[col].apply(_fmt12)
                except Exception:
                    pass

    df = _traducir_df(df)

    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"{len(df)} registro(s)")


def _boton_descarga_pdf(report_id: str, datos: List[Dict], titulo: str):
    """
    Muestra directamente un st.download_button con el PDF listo.
    (Genera el PDF y lo carga como bytes para evitar problemas de no-descarga.)
    """
    if generar_reporte_pdf is None:
        show_sweet_alert("PDF no disponible", "❌ No se encontró el generador de PDF.", "error")
        return

    try:
        res = generar_reporte_pdf(report_id, datos, titulo)

        pdf_bytes: bytes
        file_name: str = f"{report_id}.pdf"

        if isinstance(res, (bytes, bytearray)):
            pdf_bytes = bytes(res)

        elif hasattr(res, "read"):
            try:
                file_name = getattr(res, "name", file_name)
            except Exception:
                pass
            pdf_bytes = res.read()

        elif isinstance(res, (str, os.PathLike, Path)):
            p = Path(res)
            file_name = p.name or file_name
            with open(p, "rb") as f:
                pdf_bytes = f.read()

        else:
            raise TypeError(f"Tipo de retorno no soportado: {type(res)}. Retorna bytes, BytesIO o ruta.")

        st.download_button(
            label="Descargar PDF",
            data=pdf_bytes,
            file_name=file_name,
            mime="application/pdf",
            key=f"dl_{report_id}_{len(datos)}_{abs(hash(titulo)) % 10000}"
        )
    except Exception as e:
        show_sweet_alert("❌ Error al generar PDF", str(e), "error")


# ---------------------------
# VISTA: Admin / Bibliotecario
# ---------------------------
def _admin_biblio_view(db: DatabaseManager):
    st.subheader("Reportes y Estadísticas")

    tipos = [
        "Préstamos activos",
        "Préstamos atrasados",
        "Préstamos devueltos",
        "Libros más prestados",
        "Usuarios con más préstamos",
        "Sanciones aplicadas",
        "Reservas activas",
        "Inventario de libros",
    ]
    report_type = st.selectbox("Tipo de reporte", tipos, index=0)

    c1, c2 = st.columns(2)
    default_ini, default_fin = _date_defaults()
    with c1:
        f_ini = st.date_input("Fecha de inicio", value=default_ini, key="rep_adm_ini")
    with c2:
        f_fin = st.date_input("Fecha de fin", value=default_fin, key="rep_adm_fin")

    if st.button("Generar", key="btn_rep_admin"):
        ts_ini, ts_fin = _to_ts_range(f_ini, f_fin)
        datos: List[Dict] = []
        titulo = f"Reporte — {report_type}"

        if report_type == "Préstamos activos":
            datos = db.execute_query(
                """
                SELECT p.prestamo_id,
                       l.titulo,
                       a.nombre_completo AS autor,
                       u.nombre_completo AS usuario,
                       u.role,
                       p.cantidad,
                       p.fecha_prestamo,
                       p.fecha_devolucion_estimada,
                       (p.fecha_devolucion_estimada < UNIX_TIMESTAMP()) AS atrasado
                FROM prestamos p
                JOIN libros l   ON p.libro_id = l.libro_id
                JOIN autores a  ON l.autor_id = a.autor_id
                JOIN usuarios u ON p.usuario_id = u.user_id
                WHERE p.estado = 'activo'
                  AND p.fecha_prestamo BETWEEN %s AND %s
                ORDER BY p.fecha_devolucion_estimada
                """,
                (ts_ini, ts_fin),
            ) or []

        elif report_type == "Préstamos atrasados":
            datos = db.execute_query(
                """
                SELECT p.prestamo_id,
                       l.titulo,
                       a.nombre_completo AS autor,
                       u.nombre_completo AS usuario,
                       u.role,
                       p.cantidad,
                       p.fecha_prestamo,
                       p.fecha_devolucion_estimada
                FROM prestamos p
                JOIN libros l   ON p.libro_id = l.libro_id
                JOIN autores a  ON l.autor_id = a.autor_id
                JOIN usuarios u ON p.usuario_id = u.user_id
                WHERE p.estado = 'activo'
                  AND p.fecha_devolucion_estimada < UNIX_TIMESTAMP()
                  AND p.fecha_devolucion_estimada BETWEEN %s AND %s
                ORDER BY p.fecha_devolucion_estimada DESC
                """,
                (ts_ini, ts_fin),
            ) or []

        elif report_type == "Préstamos devueltos":
            datos = db.execute_query(
                """
                SELECT p.prestamo_id,
                       l.titulo,
                       a.nombre_completo AS autor,
                       u.nombre_completo AS usuario,
                       u.role,
                       p.cantidad,
                       p.fecha_prestamo,
                       p.fecha_devolucion_estimada,
                       p.fecha_devolucion_real,
                       p.estado,
                       p.observaciones
                FROM prestamos p
                JOIN libros l   ON p.libro_id = l.libro_id
                JOIN autores a  ON l.autor_id = a.autor_id
                JOIN usuarios u ON p.usuario_id = u.user_id
                WHERE p.estado IN ('devuelto','dañado','perdido')
                  AND p.fecha_devolucion_real BETWEEN %s AND %s
                ORDER BY p.fecha_devolucion_real DESC
                """,
                (ts_ini, ts_fin),
            ) or []

        elif report_type == "Libros más prestados":
            datos = db.execute_query(
                """
                SELECT l.libro_id,
                       l.titulo,
                       a.nombre_completo AS autor,
                       l.editorial,
                       l.isbn,
                       c.nombre AS categoria,
                       COUNT(p.prestamo_id) AS veces_prestado
                FROM prestamos p
                JOIN libros l     ON p.libro_id = l.libro_id
                JOIN autores a    ON l.autor_id = a.autor_id
                JOIN categorias c ON l.categoria_id = c.categoria_id
                WHERE p.fecha_prestamo BETWEEN %s AND %s
                GROUP BY l.libro_id, l.titulo, a.nombre_completo, l.editorial, l.isbn, c.nombre
                ORDER BY veces_prestado DESC, l.titulo
                LIMIT 50
                """,
                (ts_ini, ts_fin),
            ) or []

        elif report_type == "Usuarios con más préstamos":
            datos = db.execute_query(
                """
                SELECT u.user_id,
                       u.nombre_completo AS usuario,
                       u.role,
                       COUNT(p.prestamo_id) AS prestamos
                FROM prestamos p
                JOIN usuarios u ON p.usuario_id = u.user_id
                WHERE p.fecha_prestamo BETWEEN %s AND %s
                GROUP BY u.user_id, u.nombre_completo, u.role
                ORDER BY prestamos DESC, usuario
                LIMIT 50
                """,
                (ts_ini, ts_fin),
            ) or []

        elif report_type == "Sanciones aplicadas":
            datos = db.execute_query(
                """
                SELECT s.sancion_id,
                       u.nombre_completo AS usuario,
                       u.role,
                       s.motivo,
                       s.monto,
                       s.estado,
                       s.fecha_inicio,
                       s.fecha_fin,
                       l.titulo AS libro
                FROM sanciones s
                JOIN usuarios u ON s.usuario_id = u.user_id
                LEFT JOIN prestamos p ON s.prestamo_id = p.prestamo_id
                LEFT JOIN libros l     ON p.libro_id = l.libro_id
                WHERE s.fecha_inicio BETWEEN %s AND %s
                ORDER BY s.fecha_inicio DESC
                """,
                (ts_ini, ts_fin),
            ) or []

        elif report_type == "Reservas activas":
            datos = db.execute_query(
                """
                SELECT r.reserva_id,
                       l.titulo,
                       u.nombre_completo AS usuario,
                       u.role,
                       r.fecha_reserva,
                       r.fecha_expiracion,
                       r.estado
                FROM reservas r
                JOIN libros l   ON r.libro_id = l.libro_id
                JOIN usuarios u ON r.usuario_id = u.user_id
                WHERE r.estado = 'pendiente'
                  AND r.fecha_reserva BETWEEN %s AND %s
                ORDER BY r.fecha_expiracion
                """,
                (ts_ini, ts_fin),
            ) or []

        elif report_type == "Inventario de libros":
            datos = db.execute_query(
                """
                SELECT l.libro_id,
                       l.titulo,
                       a.nombre_completo AS autor,
                       l.editorial,
                       l.isbn,
                       c.nombre AS categoria,
                       l.ejemplares_disponibles,
                       l.ejemplares_totales,
                       (SELECT COALESCE(SUM(cantidad),0)
                          FROM prestamos p
                         WHERE p.libro_id = l.libro_id
                           AND p.estado='activo') AS prestados_activos
                FROM libros l
                JOIN autores a    ON l.autor_id = a.autor_id
                JOIN categorias c ON l.categoria_id = c.categoria_id
                WHERE l.activo = TRUE
                ORDER BY l.titulo
                """,
            ) or []

        # Mostrar tabla traducida y botón de descarga PDF
        _mostrar_df(datos, formato_humano=True)
        _boton_descarga_pdf(report_type.lower().replace(" ", "_"), datos, titulo)

        if report_type in ("Préstamos activos", "Préstamos atrasados", "Préstamos devueltos"):
            colm1, colm2, colm3 = st.columns(3)
            tot = db.execute_query(
                "SELECT COUNT(*) AS c FROM prestamos WHERE fecha_prestamo BETWEEN %s AND %s",
                (ts_ini, ts_fin)
            )[0]["c"]
            colm1.metric("Préstamos (periodo)", tot)
            act = db.execute_query(
                "SELECT COUNT(*) AS c FROM prestamos WHERE estado='activo'"
            )[0]["c"]
            colm2.metric("Activos hoy", act)
            atr = db.execute_query(
                "SELECT COUNT(*) AS c FROM prestamos WHERE estado='activo' AND fecha_devolucion_estimada < UNIX_TIMESTAMP()"
            )[0]["c"]
            colm3.metric("Atrasados hoy", atr)


# ---------------------------
# VISTA: Docente / Estudiante
# ---------------------------
def _usuario_view(db: DatabaseManager, user: Dict):
    st.subheader("Mis reportes")

    tab1, tab2 = st.tabs(["Mis préstamos", "Mis sanciones"])

    # --- Mis préstamos ---
    with tab1:
        default_ini, default_fin = _date_defaults()
        c1, c2 = st.columns(2)
        with c1:
            f_ini = st.date_input("Desde", value=default_ini, key="mis_prest_ini")
        with c2:
            f_fin = st.date_input("Hasta", value=default_fin, key="mis_prest_fin")

        filtro = st.radio("Tipo", ["Activos", "Historial"], horizontal=True)

        if st.button("Generar", key="btn_mis_prest"):
            ts_ini, ts_fin = _to_ts_range(f_ini, f_fin)
            datos: List[Dict] = []
            titulo = f"Mis préstamos — {filtro}"

            if filtro == "Activos":
                datos = db.execute_query(
                    """
                    SELECT p.prestamo_id,
                           l.titulo,
                           p.cantidad,
                           p.fecha_prestamo,
                           p.fecha_devolucion_estimada,
                           (p.fecha_devolucion_estimada < UNIX_TIMESTAMP()) AS atrasado
                    FROM prestamos p
                    JOIN libros l ON p.libro_id = l.libro_id
                    WHERE p.usuario_id = %s
                      AND p.estado = 'activo'
                      AND p.fecha_prestamo BETWEEN %s AND %s
                    ORDER BY p.fecha_devolucion_estimada
                    """,
                    (int(user["user_id"]), ts_ini, ts_fin),
                ) or []
            else:
                datos = db.execute_query(
                    """
                    SELECT p.prestamo_id,
                           l.titulo,
                           p.cantidad,
                           p.fecha_prestamo,
                           p.fecha_devolucion_estimada,
                           p.fecha_devolucion_real,
                           p.estado
                    FROM prestamos p
                    JOIN libros l ON p.libro_id = l.libro_id
                    WHERE p.usuario_id = %s
                      AND p.estado IN ('devuelto','dañado','perdido')
                      AND p.fecha_devolucion_real BETWEEN %s AND %s
                    ORDER BY p.fecha_devolucion_real DESC
                    """,
                    (int(user["user_id"]), ts_ini, ts_fin),
                ) or []

            _mostrar_df(datos, formato_humano=True)
            _boton_descarga_pdf("mis_prestamos", datos, titulo)

    # --- Mis sanciones ---
    with tab2:
        default_ini, default_fin = _date_defaults()
        c1, c2 = st.columns(2)
        with c1:
            f_ini = st.date_input("Desde", value=default_ini, key="mis_sanc_ini")
        with c2:
            f_fin = st.date_input("Hasta", value=default_fin, key="mis_sanc_fin")

        if st.button("Generar", key="btn_mis_sanc"):
            ts_ini, ts_fin = _to_ts_range(f_ini, f_fin)
            datos = db.execute_query(
                """
                SELECT s.sancion_id,
                       s.motivo,
                       s.monto,
                       s.estado,
                       s.fecha_inicio,
                       s.fecha_fin,
                       l.titulo AS libro
                FROM sanciones s
                LEFT JOIN prestamos p ON s.prestamo_id = p.prestamo_id
                LEFT JOIN libros l     ON p.libro_id = l.libro_id
                WHERE s.usuario_id = %s
                  AND s.fecha_inicio BETWEEN %s AND %s
                ORDER BY s.fecha_inicio DESC
                """,
                (int(user["user_id"]), ts_ini, ts_fin),
            ) or []
            _mostrar_df(datos, formato_humano=True)
            _boton_descarga_pdf("mis_sanciones", datos, "Mis sanciones")


# ---------------------------
# Entrada pública
# ---------------------------
def gestion_reportes(db_manager: Optional[DatabaseManager] = None, user: Optional[Dict] = None):
    """
    Enruta la vista según el rol:
    - admin / bibliotecario: vista completa con tipos de reporte
    - docente / estudiante: vista personal (mis préstamos / mis sanciones)
    """
    db = db_manager or DatabaseManager()
    role = (user or {}).get("role", "admin")
    if role in ("admin", "bibliotecario"):
        _admin_biblio_view(db)
    else:
        if not user or "user_id" not in user:
            st.info("No se pudo identificar al usuario.")
            return
        _usuario_view(db, user)


def generar_reportes_admin():
    gestion_reportes()

def generar_reportes_usuario(user: Dict):
    gestion_reportes(user=user)
