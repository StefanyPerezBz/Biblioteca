# src/dashboards/bibliotecario.py - Dashboard para bibliotecarios UNT
import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os

from src.database.database import DatabaseManager
from src.services.prestamos import gestion_prestamos_bibliotecario, gestion_devoluciones
from src.services.reservas import gestion_reservas
from src.services.usuarios import validar_cuentas  
from src.services.libros import gestion_libros
from src.utils.alert_utils import show_sweet_alert
from src.utils.email_manager import EmailManager  
from src.services.sanciones import gestion_sanciones
from src.services.perfil import perfil_usuario 
from src.utils.image_manager import ImageManager
from src.auth.auth import require_auth
import math

# --------- Utilidades locales ----------
def _fmt_fecha(ts: int) -> str:
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%d/%m/%Y")
    except Exception:
        return "-"

def _mensaje_atraso(row: dict) -> str:
    return (
        f"Hola {row['nombre_completo']}, te escribe la Biblioteca UNT. "
        f"El préstamo del libro “{row['titulo']}” está atrasado {row['dias_atraso']} día(s) "
        f"(fecha prevista: {_fmt_fecha(row['fecha_devolucion_estimada'])}). "
        f"Por favor realiza la devolución a la brevedad. Si ya devolviste, ignora este mensaje."
    )

def _mensaje_por_vencer(row: dict) -> str:
    return (
        f"Hola {row['nombre_completo']}, recordatorio de la Biblioteca UNT: "
        f"el préstamo del libro “{row['titulo']}” vence el {_fmt_fecha(row['fecha_devolucion_estimada'])} "
        f"(en {row['dias_restantes']} día(s)). Gracias por tu puntualidad."
    )

def _mensaje_reserva(row: dict) -> str:
    return (
        f"Hola {row['nombre_completo']}, tu reserva del libro “{row['titulo']}” "
        f"está pendiente desde {_fmt_fecha(row['fecha_reserva'])}. "
        f"Acércate a recogerla o actualiza tu reserva. Si ya lo hiciste, ignora este mensaje."
    )

def bibliotecario_dashboard(user):

    # --- Auth (JWT) ---
    require_auth(required_roles=("bibliotecario","admin",))

    """Dashboard para bibliotecarios UNT"""
    st.title(f"📚 Bibliotecario UNT")
    st.write(f"Bienvenido, **{user['nombre_completo']}**")

    db_manager = DatabaseManager()
    image_manager = ImageManager()

    # Mostrar información del usuario 
    mostrar_info_usuario(user, image_manager, db_manager)

    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        prestamos_activos = db_manager.execute_query(
            "SELECT COUNT(*) as count FROM prestamos WHERE estado = 'activo'"
        )[0]['count']
        st.metric("Préstamos Activos", prestamos_activos)
    with col2:
        prestamos_atrasados = db_manager.execute_query(
            "SELECT COUNT(*) as count FROM prestamos WHERE estado = 'activo' AND fecha_devolucion_estimada < UNIX_TIMESTAMP()"
        )[0]['count']
        st.metric("Préstamos Atrasados", prestamos_atrasados, delta=None, delta_color="inverse")
    with col3:
        reservas_pendientes = db_manager.execute_query(
            "SELECT COUNT(*) as count FROM reservas WHERE estado = 'pendiente'"
        )[0]['count']
        st.metric("Reservas Pendientes", reservas_pendientes)
    with col4:
        usuarios_nuevos = db_manager.execute_query(
            "SELECT COUNT(*) as count FROM usuarios WHERE validado = FALSE AND activo = TRUE"
        )[0]['count']
        st.metric("Cuentas por Validar", usuarios_nuevos)

    st.divider()

    opcion = st.sidebar.radio("Opciones", [
        "Inicio",
        "Gestionar Préstamos y Devoluciones",
        "Gestión de Usuarios",
        "Gestionar Reservas",
        "Gestión de Libros",
        "Gestión de Sanciones",
        "Gráficos Estadísticos",
        "Alertas y Notificaciones",
        "Mi Perfil"
    ])

    # --- Probar correo rápido ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("✉️ Probar correo")
    test_to = st.sidebar.text_input("Enviar prueba a:", value=user.get("email", "you@example.com"))
    if st.sidebar.button("Enviar prueba ahora"):
        em = EmailManager()
        ok = em.send_email(test_to, "Biblioteca UNT",
                           html="<p>¡Hola! Esto es una prueba desde la Biblioteca UNT.</p>")
        show_sweet_alert("Prueba de correo", "¡Enviado!" if ok else "Fallo en el envío", "success" if ok else "error")

    # --- Botón de cerrar sesión ---
    st.sidebar.markdown("---")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.clear()
        show_sweet_alert("Sesión Cerrada", "Has cerrado sesión correctamente.", "success")
        st.rerun()

    # === Contenido ===
    if opcion == "Inicio":
        st.header("Resumen General")
        # Préstamos atrasados (Top 10)
        st.write("### Préstamos Atrasados (Top 10)")
        prestamos_atrasados = db_manager.execute_query("""
            SELECT p.prestamo_id, l.titulo, u.nombre_completo, u.email, u.role, s.nombre as sede,
                   p.fecha_devolucion_estimada,
                   FLOOR((UNIX_TIMESTAMP() - p.fecha_devolucion_estimada) / 86400) as dias_atraso
            FROM prestamos p
            JOIN libros l ON p.libro_id = l.libro_id
            JOIN usuarios u ON p.usuario_id = u.user_id
            LEFT JOIN sedes s ON u.sede_id = s.sede_id
            WHERE p.estado = 'activo'
            AND p.fecha_devolucion_estimada < UNIX_TIMESTAMP()
            ORDER BY p.fecha_devolucion_estimada ASC
            LIMIT 10
        """)
        if prestamos_atrasados:
            df_atrasados = pd.DataFrame(prestamos_atrasados)
            st.dataframe(df_atrasados, use_container_width=True)
            for prestamo in prestamos_atrasados:
                show_sweet_alert(
                    "Alerta de Atraso",
                    f"El libro '{prestamo['titulo']}' de {prestamo['nombre_completo']} "
                    f"({prestamo['role'].capitalize()}) tiene {prestamo['dias_atraso']} días de atraso.",
                    "warning"
                )
        else:
            st.success("No hay préstamos atrasados.")
        validar_cuentas(db_manager, show_sweet_alert)

    elif opcion == "Gestionar Préstamos y Devoluciones":
        tab1, tab2 = st.tabs(["Registrar Préstamo", "Registrar Devolución"])
        with tab1:
            gestion_prestamos_bibliotecario(db_manager, user, show_sweet_alert)
        with tab2:
            gestion_devoluciones(db_manager, user, show_sweet_alert)

    elif opcion == "Gestión de Usuarios":
        from src.services.usuarios import gestion_usuarios_bibliotecario
        gestion_usuarios_bibliotecario(db_manager, show_sweet_alert)

    elif opcion == "Gestionar Reservas":
        gestion_reservas(db_manager, user, show_sweet_alert)

    elif opcion == "Gestión de Libros":
        gestion_libros(db_manager, show_sweet_alert, user.get("role"))

    elif opcion == "Gestión de Sanciones":
        gestion_sanciones(db_manager, show_sweet_alert, user=user)

    elif opcion == "Gráficos Estadísticos":
        from src.services.graficos import generar_graficos_bibliotecario
        generar_graficos_bibliotecario(db_manager)

    elif opcion == "Alertas y Notificaciones":
        st.header("Alertas y Notificaciones")

        with st.expander("⚙️ Configuración de umbrales", expanded=False):
            dias_por_vencer = st.number_input(
                "Días para considerar 'por vencer' (incluye hoy)", min_value=1, max_value=30, value=3, step=1
            )
            dias_reserva_pendiente = st.number_input(
                "Días para alerta de reservas pendientes", min_value=1, max_value=60, value=3, step=1
            )

        tabs = st.tabs(["Préstamos atrasados", "Préstamos por vencer", "Reservas pendientes", "Mensajes (lote)"])
        em = EmailManager()

        # --- Préstamos atrasados ---
        with tabs[0]:
            atrasados = db_manager.execute_query(f"""
                SELECT p.prestamo_id, l.titulo, u.nombre_completo, u.email,
                       p.fecha_devolucion_estimada,
                       FLOOR((UNIX_TIMESTAMP() - p.fecha_devolucion_estimada) / 86400) as dias_atraso
                FROM prestamos p
                JOIN libros l ON p.libro_id = l.libro_id
                JOIN usuarios u ON p.usuario_id = u.user_id
                WHERE p.estado = 'activo'
                  AND p.fecha_devolucion_estimada < UNIX_TIMESTAMP()
                ORDER BY p.fecha_devolucion_estimada ASC
            """)
            if atrasados:
                df = pd.DataFrame(atrasados)
                df["fecha_prevista"] = df["fecha_devolucion_estimada"].apply(_fmt_fecha)
                df["mensaje"] = df.apply(_mensaje_atraso, axis=1)
                mostrar = df[["prestamo_id", "nombre_completo", "email", "titulo", "dias_atraso", "fecha_prevista", "mensaje"]]
                st.dataframe(mostrar, use_container_width=True, hide_index=True)

                # Botón de envío
                if st.button("✉️ Enviar correos — Atrasos"):
                    rows = mostrar.to_dict("records")
                    res = em.bulk_atrasos(rows)
                    show_sweet_alert("Envío completado", f"Enviados {res['ok']} de {res['total']} correos.", "success" if res["ok"] else "warning")

                csv = mostrar.to_csv(index=False).encode("utf-8")
                st.download_button("Descargar mensajes (CSV)", csv, "mensajes_atrasos.csv", "text/csv")
            else:
                st.success("Sin préstamos atrasados ✅")

        # --- Préstamos por vencer ---
        with tabs[1]:
            por_vencer = db_manager.execute_query(f"""
                SELECT p.prestamo_id, l.titulo, u.nombre_completo, u.email,
                       p.fecha_devolucion_estimada,
                       CEIL((p.fecha_devolucion_estimada - UNIX_TIMESTAMP()) / 86400) as dias_restantes
                FROM prestamos p
                JOIN libros l ON p.libro_id = l.libro_id
                JOIN usuarios u ON p.usuario_id = u.user_id
                WHERE p.estado = 'activo'
                  AND p.fecha_devolucion_estimada BETWEEN UNIX_TIMESTAMP()
                      AND (UNIX_TIMESTAMP() + {int(dias_por_vencer)} * 86400)
                ORDER BY p.fecha_devolucion_estimada ASC
            """)
            if por_vencer:
                df = pd.DataFrame(por_vencer)
                df["fecha_prevista"] = df["fecha_devolucion_estimada"].apply(_fmt_fecha)
                df["mensaje"] = df.apply(_mensaje_por_vencer, axis=1)
                mostrar = df[["prestamo_id", "nombre_completo", "email", "titulo", "dias_restantes", "fecha_prevista", "mensaje"]]
                st.dataframe(mostrar, use_container_width=True, hide_index=True)

                if st.button("✉️ Enviar correos — Por vencer"):
                    rows = mostrar.to_dict("records")
                    res = em.bulk_por_vencer(rows)
                    show_sweet_alert("Envío completado", f"Enviados {res['ok']} de {res['total']} correos.", "success" if res["ok"] else "warning")

                csv = mostrar.to_csv(index=False).encode("utf-8")
                st.download_button("Descargar mensajes (CSV)", csv, "mensajes_por_vencer.csv", "text/csv")
            else:
                st.success("No hay préstamos próximos a vencer en el rango seleccionado ✅")

        # --- Reservas pendientes ---
        with tabs[2]:
            reservas = db_manager.execute_query(f"""
                SELECT r.reserva_id, l.titulo, u.nombre_completo, u.email,
                       r.fecha_reserva,
                       FLOOR((UNIX_TIMESTAMP() - r.fecha_reserva) / 86400) as dias_espera
                FROM reservas r
                JOIN libros l ON r.libro_id = l.libro_id
                JOIN usuarios u ON r.usuario_id = u.user_id
                WHERE r.estado = 'pendiente'
                  AND r.fecha_reserva < (UNIX_TIMESTAMP() - {int(dias_reserva_pendiente)} * 86400)
                ORDER BY r.fecha_reserva ASC
            """)
            if reservas:
                df = pd.DataFrame(reservas)
                df["fecha_reserva_str"] = df["fecha_reserva"].apply(_fmt_fecha)
                df["mensaje"] = df.apply(_mensaje_reserva, axis=1)
                mostrar = df[["reserva_id", "nombre_completo", "email", "titulo", "dias_espera", "fecha_reserva_str", "mensaje"]]
                st.dataframe(mostrar, use_container_width=True, hide_index=True)

                if st.button("✉️ Enviar correos — Reservas"):
                    rows = mostrar.to_dict("records")
                    res = em.bulk_reservas(rows)
                    show_sweet_alert("Envío completado", f"Enviados {res['ok']} de {res['total']} correos.", "success" if res["ok"] else "warning")

                csv = mostrar.to_csv(index=False).encode("utf-8")
                st.download_button("Descargar mensajes (CSV)", csv, "mensajes_reservas.csv", "text/csv")
            else:
                st.success("No hay reservas pendientes fuera del umbral configurado ✅")

        # --- Mensajes en lote (vista previa y copia rápida) ---
        with tabs[3]:
            st.caption("Mensajes listos para copiar/pegar o descargar.")
            lotes = []

            atrasados_all = db_manager.execute_query("""
                SELECT p.prestamo_id, l.titulo, u.nombre_completo,
                       p.fecha_devolucion_estimada,
                       FLOOR((UNIX_TIMESTAMP() - p.fecha_devolucion_estimada) / 86400) as dias_atraso
                FROM prestamos p
                JOIN libros l ON p.libro_id = l.libro_id
                JOIN usuarios u ON p.usuario_id = u.user_id
                WHERE p.estado = 'activo'
                  AND p.fecha_devolucion_estimada < UNIX_TIMESTAMP()
                ORDER BY p.fecha_devolucion_estimada ASC
            """)
            for r in atrasados_all or []:
                lotes.append(_mensaje_atraso(r))

            por_vencer_all = db_manager.execute_query(f"""
                SELECT p.prestamo_id, l.titulo, u.nombre_completo,
                       p.fecha_devolucion_estimada,
                       CEIL((p.fecha_devolucion_estimada - UNIX_TIMESTAMP()) / 86400) as dias_restantes
                FROM prestamos p
                JOIN libros l ON p.libro_id = l.libro_id
                JOIN usuarios u ON p.usuario_id = u.user_id
                WHERE p.estado = 'activo'
                  AND p.fecha_devolucion_estimada BETWEEN UNIX_TIMESTAMP()
                      AND (UNIX_TIMESTAMP() + {int(dias_por_vencer)} * 86400)
                ORDER BY p.fecha_devolucion_estimada ASC
            """)
            for r in por_vencer_all or []:
                lotes.append(_mensaje_por_vencer(r))

            reservas_all = db_manager.execute_query(f"""
                SELECT r.reserva_id, l.titulo, u.nombre_completo,
                       r.fecha_reserva,
                       FLOOR((UNIX_TIMESTAMP() - r.fecha_reserva) / 86400) as dias_espera
                FROM reservas r
                JOIN libros l ON r.libro_id = l.libro_id
                JOIN usuarios u ON r.usuario_id = u.user_id
                WHERE r.estado = 'pendiente'
                  AND r.fecha_reserva < (UNIX_TIMESTAMP() - {int(dias_reserva_pendiente)} * 86400)
                ORDER BY r.fecha_reserva ASC
            """)
            for r in reservas_all or []:
                lotes.append(_mensaje_reserva(r))

            texto_lote = "\n\n".join(lotes) if lotes else "No hay mensajes para generar en este momento."
            st.text_area("Vista previa", value=texto_lote, height=260)

            buffer = io.BytesIO(texto_lote.encode("utf-8"))
            st.download_button("Descargar lote de mensajes (.txt)", buffer, "mensajes_lote.txt", "text/plain")

            show_sweet_alert(
                "Resumen de notificaciones",
                f"Mensajes generados: {len(lotes)}",
                "success" if lotes else "info"
            )

    elif opcion == "Mi Perfil":
        perfil_usuario(db_manager, user, show_sweet_alert)

# ============================
# Helpers UI
# ============================
def mostrar_info_usuario(user, image_manager: ImageManager, db_manager: DatabaseManager):
    st.sidebar.title("Perfil de Usuario")

    if user.get('foto_perfil_id') and os.path.exists(user['foto_perfil_id']):
        st.sidebar.image(user['foto_perfil_id'], width=100)
    else:
        st.sidebar.image(image_manager.get_default_cover(), width=100)

    st.sidebar.markdown(f'<div class="user-card">', unsafe_allow_html=True)
    st.sidebar.write(f"**{user['nombre_completo']}**")
    st.sidebar.write(f"**{user['role'].capitalize()} UNT**")
    if user.get('codigo_unt'):
        st.sidebar.write(f"**Código:** {user['codigo_unt']}")
    st.sidebar.write(f"**Sede:** {user.get('sede', 'No especificada')}")
    st.sidebar.markdown('</div>', unsafe_allow_html=True)

# --- Helpers: traducción + paginación de tablas ---
def _render_tabla_paginada(df: pd.DataFrame, col_map: dict, order: list, key_prefix: str, page_sizes=(10, 20, 50)):
    """
    - col_map: {"col_original": "Columna en Español"}
    - order:   ["col_original", ...] en el orden deseado
    - key_prefix: clave única por tabla/pestaña (ej. "atrasos", "porvencer", "reservas")
    """
    if df is None or df.empty:
        st.info("No hay datos para mostrar.")
        return None, None

    # Renombrar y reordenar columnas
    ordered = df[order].copy()
    renamed = ordered.rename(columns=col_map)

    # Selección de tamaño de página
    cols = st.columns([1, 1, 2, 2])
    with cols[0]:
        page_size = st.selectbox("Filas por página", page_sizes, index=0, key=f"{key_prefix}_page_size")
    total_rows = len(renamed)
    total_pages = max(1, math.ceil(total_rows / page_size))

    # Estado de paginación por tabla
    page_key = f"{key_prefix}_page"
    if page_key not in st.session_state:
        st.session_state[page_key] = 1

    # Controles de paginación
    with cols[1]:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        if st.button("⟵ Anterior", key=f"{key_prefix}_prev", disabled=st.session_state[page_key] <= 1):
            st.session_state[page_key] -= 1
    with cols[2]:
        current = st.number_input("Página", 1, total_pages, value=st.session_state[page_key], key=f"{key_prefix}_page_input")
        st.session_state[page_key] = int(current)
    with cols[3]:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        if st.button("Siguiente ⟶", key=f"{key_prefix}_next", disabled=st.session_state[page_key] >= total_pages):
            st.session_state[page_key] += 1

    # Slicing de la página
    start = (st.session_state[page_key] - 1) * page_size
    end = start + page_size
    page_df = renamed.iloc[start:end]

    st.caption(f"Página {st.session_state[page_key]} de {total_pages} — {total_rows} filas")
    st.dataframe(page_df, use_container_width=True, hide_index=True)

    # Descarga de la tabla completa (ya en español)
    csv_full = renamed.to_csv(index=False).encode("utf-8")
    st.download_button("Descargar tabla (CSV)", csv_full, f"tabla_{key_prefix}.csv", "text/csv")

    return renamed, page_df
