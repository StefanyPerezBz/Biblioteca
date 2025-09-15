# src/dashboards/admin.py - Dashboard para administradores UNT
import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import os

from src.database.database import DatabaseManager
from src.services.usuarios import gestion_usuarios
from src.services.libros import gestion_libros
from src.services.prestamos import gestion_prestamos
from src.services.reservas import gestion_reservas
from src.services.sanciones import gestion_sanciones
from src.services.reportes import gestion_reportes
from src.services.configuracion import gestion_configuracion
from src.utils.alert_utils import show_sweet_alert
from src.services.graficos import generar_graficos
from src.services.perfil import perfil_usuario
from src.utils.image_manager import ImageManager
from src.auth.auth import require_auth

LIMA_TZ = ZoneInfo("America/Lima")

def _fmt12_lima(value) -> str:
    try:
        if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
            ts = int(value)
            dt = datetime.fromtimestamp(ts, tz=LIMA_TZ)
            return dt.strftime("%d/%m/%Y %I:%M %p")
        if isinstance(value, str):
            try:
                dt_naive = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                dt = dt_naive.replace(tzinfo=LIMA_TZ)
                return dt.strftime("%d/%m/%Y %I:%M %p")
            except Exception:
                try:
                    dt_iso = datetime.fromisoformat(value)
                    if dt_iso.tzinfo is None:
                        dt_iso = dt_iso.replace(tzinfo=LIMA_TZ)
                    return dt_iso.astimezone(LIMA_TZ).strftime("%d/%m/%Y %I:%M %p")
                except Exception:
                    return str(value)
        if isinstance(value, datetime):
            dt = value.astimezone(LIMA_TZ) if value.tzinfo else value.replace(tzinfo=LIMA_TZ)
            return dt.strftime("%d/%m/%Y %I:%M %p")
        return str(value)
    except Exception:
        return str(value)

def admin_dashboard(user):

    # --- Auth (JWT) ---
    require_auth(required_roles=("admin",))

    st.title("Administrador UNT")
    st.write(f"Bienvenido, **{user['nombre_completo']}**")

    db_manager = DatabaseManager()
    image_manager = ImageManager()

    # Mostrar información del usuario 
    mostrar_info_usuario(user, image_manager, db_manager)

    # --- Métricas rápidas ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        total_usuarios = db_manager.execute_query(
            "SELECT COUNT(*) AS c FROM usuarios WHERE activo = TRUE"
        )[0]['c']
        st.metric("Usuarios", total_usuarios)
    with col2:
        total_libros = db_manager.execute_query(
            "SELECT COUNT(*) AS c FROM libros WHERE activo = TRUE"
        )[0]['c']
        st.metric("Libros", total_libros)
    with col3:
        prestamos_activos = db_manager.execute_query(
            "SELECT COUNT(*) AS c FROM prestamos WHERE estado = 'activo'"
        )[0]['c']
        st.metric("Préstamos Activos", prestamos_activos)
    with col4:
        atrasados = db_manager.execute_query(
            "SELECT COUNT(*) AS c FROM prestamos WHERE estado='activo' AND fecha_devolucion_estimada < UNIX_TIMESTAMP()"
        )[0]['c']
        st.metric("Atrasados", atrasados, delta=None, delta_color="inverse")

    st.divider()

    # --- Sidebar ---
    st.sidebar.title("Panel de Administración")
    opcion = st.sidebar.radio(
        "Seleccionar sección",
        [
            "Inicio",
            "Gestión de Usuarios",
            "Gestión de Libros",
            "Gestión de Préstamos",
            "Gestión de Reservas",
            "Gestión de Sanciones",
            "Configuración del Sistema",
            "Reportes y Estadísticas",
            "Gráficos Estadísticos",
            "Mi Perfil"
        ],
        index=0
    )

    st.sidebar.markdown("---")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.clear()
        show_sweet_alert("Sesión Cerrada", "Has cerrado sesión correctamente.", "success")
        st.rerun()

    # --- Contenido ---
    if opcion == "Inicio":
        st.header("Resumen General")

        st.write("### Préstamos recientes")
        recientes = db_manager.execute_query(
            """
            SELECT p.prestamo_id, l.titulo, u.nombre_completo, u.role, p.fecha_prestamo
            FROM prestamos p
            JOIN libros l ON p.libro_id = l.libro_id
            JOIN usuarios u ON p.usuario_id = u.user_id
            WHERE p.estado = 'activo'
            ORDER BY p.fecha_prestamo DESC
            LIMIT 10
            """
        ) or []
        if recientes:
            for i in recientes:
                st.info(f"📖 **{i['titulo']}** a **{i['nombre_completo']}** ({i['role']}) — {_fmt12_lima(i['fecha_prestamo'])}")
        else:
            st.info("No hay préstamos activos recientes.")

        st.write("### Cuentas pendientes de validación")
        pendientes = db_manager.execute_query(
            "SELECT user_id, nombre_completo, role, fecha_registro FROM usuarios WHERE validado=FALSE AND activo=TRUE ORDER BY fecha_registro"
        ) or []
        if pendientes:
            for u in pendientes:
                tono = "error" if u["role"] == "bibliotecario" else "warning"
                msg = f"{'Bibliotecario' if u['role']=='bibliotecario' else u['role'].capitalize()} pendiente: **{u['nombre_completo']}** — {_fmt12_lima(u['fecha_registro'])}"
                if tono == "error":
                    st.error(msg)
                else:
                    st.warning(msg)
        else:
            st.success("No hay cuentas pendientes de validación.")

    elif opcion == "Gestión de Usuarios":
        gestion_usuarios(db_manager, show_sweet_alert)

    elif opcion == "Gestión de Libros":
        gestion_libros(db_manager, show_sweet_alert, user.get("role"))

    elif opcion == "Gestión de Préstamos":
        gestion_prestamos()

    elif opcion == "Gestión de Reservas":
        gestion_reservas(db_manager, user, show_sweet_alert)

    elif opcion == "Gestión de Sanciones":
        gestion_sanciones(db_manager, show_sweet_alert, user=user)

    elif opcion == "Configuración del Sistema":
        gestion_configuracion(db_manager, show_sweet_alert)

    elif opcion == "Reportes y Estadísticas":
        gestion_reportes(db_manager, user)

    elif opcion == "Gráficos Estadísticos":
        generar_graficos(db_manager)

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