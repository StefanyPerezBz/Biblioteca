# src/services/sanciones.py - Gestión simple de sanciones por rol (actualizado con paginación)
import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

from src.database.database import DatabaseManager
from src.utils.alert_utils import show_sweet_alert

LIMA = ZoneInfo("America/Lima")

def _fmt12(ts):
    """Convierte epoch a 'DD/MM/YYYY hh:mm AM/PM' en zona America/Lima."""
    try:
        return datetime.fromtimestamp(int(ts), tz=LIMA).strftime('%d/%m/%Y %I:%M %p')
    except Exception:
        return "-"

def _df_sanciones(rows, incluir_usuario=True):
    """Convierte rows de sanciones a DataFrame en español."""
    if not rows:
        return None
    out = []
    for r in rows:
        fila = {
            "ID": r["sancion_id"],
            "Motivo": r["motivo"],
            "Monto": r.get("monto", 0.0),
            "Estado": r["estado"].capitalize(),
            "Inicio": _fmt12(r["fecha_inicio"]),
            "Fin": _fmt12(r["fecha_fin"]),
        }
        if incluir_usuario:
            fila["Usuario"] = r.get("nombre_completo", "-")
            fila["Rol"] = r.get("role", "-")
        out.append(fila)
    return pd.DataFrame(out)

# ============================
# PAGINADOR AUXILIAR
# ============================
def _paginador_df(df: pd.DataFrame, key_prefix: str = ""):
    if df is None or df.empty:
        return df

    col_a, col_b = st.columns([1, 3])
    with col_a:
        page_size = st.selectbox("Filas por página", [5, 10, 20, 50], index=1, key=f"{key_prefix}_size")
    total = len(df)
    total_pages = max((total + page_size - 1) // page_size, 1)

    if f"{key_prefix}_pag" not in st.session_state:
        st.session_state[f"{key_prefix}_pag"] = 1

    with col_b:
        page = st.number_input(
            "Página",
            min_value=1,
            max_value=total_pages,
            value=st.session_state[f"{key_prefix}_pag"],
            step=1,
            key=f"{key_prefix}_input"
        )

    st.session_state[f"{key_prefix}_pag"] = page

    start = (page - 1) * page_size
    end = start + page_size
    df_page = df.iloc[start:end]
    st.caption(f"Página {page} de {total_pages} • {total} registros")
    return df_page

# ============================
# GESTIÓN DE SANCIONES
# ============================

def _hay_otras_sanciones_activas(db: DatabaseManager, user_id: int) -> bool:
    row = db.execute_query(
        "SELECT COUNT(*) AS c FROM sanciones WHERE usuario_id=%s AND estado='activa'",
        (user_id,)
    )
    return bool(row and int(row[0]["c"]) > 0)

def _listar_destinatarios(db: DatabaseManager):
    """Solo estudiantes y docentes activos."""
    q = """
        SELECT user_id, nombre_completo, role
        FROM usuarios
        WHERE activo = TRUE
          AND role IN ('estudiante','docente')
        ORDER BY role, nombre_completo
    """
    return db.execute_query(q) or []

def gestion_sanciones(db_manager: DatabaseManager, show_sweet_alert, user: dict | None = None):
    role = (user or {}).get("role", "admin")
    user_id = (user or {}).get("user_id")

    # =========================
    # ADMIN / BIBLIOTECARIO
    # =========================
    if role in ("admin", "bibliotecario"):
        st.subheader("Gestión de Sanciones")

        tab1, tab2, tab3 = st.tabs(["Activas", "Historial", "Crear sanción"])

        # ---- Activas ----
        with tab1:
            busc = st.text_input("Buscar por usuario o motivo")
            q = """
                SELECT s.sancion_id, u.nombre_completo, u.role, s.motivo, s.monto, s.estado,
                       s.fecha_inicio, s.fecha_fin
                FROM sanciones s
                JOIN usuarios u ON s.usuario_id = u.user_id
                WHERE s.estado='activa'
                  AND (u.nombre_completo LIKE %s OR s.motivo LIKE %s)
                ORDER BY s.fecha_fin
            """
            rows = db_manager.execute_query(q, (f"%{busc}%", f"%{busc}%")) or []
            df = _df_sanciones(rows, incluir_usuario=True)
            if df is not None and not df.empty:
                df_page = _paginador_df(df, key_prefix="sanc_act")
                st.dataframe(df_page, use_container_width=True)

                st.markdown("#### Finalizar (condonar) sanción")
                opciones = [f"#{r['sancion_id']} • {r['nombre_completo']} • {r['motivo']}" for r in rows]
                idx = st.selectbox("Selecciona sanción", list(range(len(opciones))), format_func=lambda i: opciones[i])
                sancion_id = rows[idx]["sancion_id"]

                if st.button("Finalizar sanción"):
                    db_manager.execute_query(
                        "UPDATE sanciones SET estado='condonada', fecha_fin=UNIX_TIMESTAMP() WHERE sancion_id=%s",
                        (sancion_id,),
                        return_result=False
                    )
                    uid_row = db_manager.execute_query("SELECT usuario_id FROM sanciones WHERE sancion_id=%s", (sancion_id,))
                    if uid_row:
                        uid = uid_row[0]["usuario_id"]
                        if not _hay_otras_sanciones_activas(db_manager, uid):
                            db_manager.execute_query(
                                "UPDATE usuarios SET sancionado=FALSE, fecha_fin_sancion=NULL WHERE user_id=%s",
                                (uid,),
                                return_result=False
                            )
                    show_sweet_alert("Listo", "Sanción finalizada (condonada).", "success")
                    st.rerun()
            else:
                st.success("No hay sanciones activas.")

        # ---- Historial ----
        with tab2:
            qh = """
                SELECT s.sancion_id, u.nombre_completo, u.role, s.motivo, s.monto, s.estado,
                       s.fecha_inicio, s.fecha_fin
                FROM sanciones s
                JOIN usuarios u ON s.usuario_id = u.user_id
                ORDER BY s.fecha_inicio DESC
                LIMIT 200
            """
            hist = db_manager.execute_query(qh) or []
            dfh = _df_sanciones(hist, incluir_usuario=True)
            if dfh is not None and not dfh.empty:
                df_page = _paginador_df(dfh, key_prefix="sanc_hist")
                st.dataframe(df_page, use_container_width=True)
            else:
                st.info("Sin historial por mostrar.")

        # ---- Crear sanción ----
        with tab3:
            st.caption("Crear sanción manual para estudiante/docente.")
            usuarios = _listar_destinatarios(db_manager)
            if not usuarios:
                st.info("No hay estudiantes/docentes activos.")
            else:
                etiquetas = [f"{u['nombre_completo']} — {u['role']}" for u in usuarios]
                idx = st.selectbox("Usuario", list(range(len(etiquetas))), format_func=lambda i: etiquetas[i])
                destinatario_id = usuarios[idx]["user_id"]

                motivo = st.text_area("Motivo", placeholder="Ej.: Conducta, atraso fuera de proceso, etc.")
                dias = st.number_input("Días de sanción", min_value=1, value=3, step=1)
                monto = st.number_input("Monto (opcional)", min_value=0.0, value=0.0, step=0.5, format="%.2f")

                if st.button("Crear sanción"):
                    if not motivo.strip():
                        show_sweet_alert("Falta motivo", "Escribe el motivo de la sanción.", "warning")
                    else:
                        db_manager.execute_query(
                            """INSERT INTO sanciones (usuario_id, prestamo_id, fecha_inicio, fecha_fin, motivo, monto, estado)
                               VALUES (%s, NULL, UNIX_TIMESTAMP(), UNIX_TIMESTAMP()+%s*86400, %s, %s, 'activa')""",
                            (destinatario_id, int(dias), motivo.strip(), float(monto)),
                            return_result=False
                        )
                        db_manager.execute_query(
                            "UPDATE usuarios SET sancionado=TRUE, fecha_fin_sancion=UNIX_TIMESTAMP()+%s*86400 WHERE user_id=%s",
                            (int(dias), destinatario_id),
                            return_result=False
                        )
                        show_sweet_alert("Éxito", "Sanción creada.", "success")
                        st.rerun()

    # =========================
    # DOCENTE / ESTUDIANTE
    # =========================
    else:
        st.subheader("Mis Sanciones")
        if not user_id:
            st.info("No se pudo identificar al usuario.")
            return

        tab1, tab2 = st.tabs(["Activas", "Historial"])

        with tab1:
            q = """
                SELECT sancion_id, motivo, monto, estado, fecha_inicio, fecha_fin
                FROM sanciones
                WHERE usuario_id=%s AND estado='activa'
                ORDER BY fecha_fin
            """
            rows = db_manager.execute_query(q, (user_id,)) or []
            df = _df_sanciones(rows, incluir_usuario=False)
            if df is not None and not df.empty:
                df_page = _paginador_df(df, key_prefix="mis_sanc_act")
                st.dataframe(df_page, use_container_width=True)
            else:
                st.success("No tienes sanciones activas.")

        with tab2:
            qh = """
                SELECT sancion_id, motivo, monto, estado, fecha_inicio, fecha_fin
                FROM sanciones
                WHERE usuario_id=%s
                ORDER BY fecha_inicio DESC
                LIMIT 200
            """
            rows = db_manager.execute_query(qh, (user_id,)) or []
            dfh = _df_sanciones(rows, incluir_usuario=False)
            if dfh is not None and not dfh.empty:
                df_page = _paginador_df(dfh, key_prefix="mis_sanc_hist")
                st.dataframe(df_page, use_container_width=True)
            else:
                st.info("Aún no tienes historial de sanciones.")
