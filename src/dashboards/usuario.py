# src/dashboards/usuario.py - Dashboard para usuarios UNT
import streamlit as st
import pandas as pd
from datetime import datetime
import time
import os
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go

from src.database.database import DatabaseManager
from src.utils.image_manager import ImageManager
from src.services.libros import gestion_libros
from src.utils.alert_utils import show_sweet_alert
from src.services.perfil import perfil_usuario 
from src.auth.auth import require_auth

LIMA_TZ = "America/Lima"

# ============================
# Helper sanciones
# ============================
def _usuario_sancionado_vigente(db: DatabaseManager, user_id: int) -> bool:
    r = db.execute_query(
        "SELECT sancionado, COALESCE(fecha_fin_sancion,0) AS fin FROM usuarios WHERE user_id=%s",
        (int(user_id),)
    )
    if not r:
        return False
    sanc = bool(r[0]["sancionado"]) if isinstance(r[0]["sancionado"], (int, bool)) else str(r[0]["sancionado"]).lower() == 'true'
    fin = int(r[0]["fin"] or 0)
    return sanc and (fin == 0 or fin > int(time.time()))

# ============================
# Dashboard principal
# ============================
def usuario_dashboard(user):

    # --- Auth (JWT) ---
    require_auth(required_roles=("estudiante","docente",))

    """Dashboard UNT"""
    titulo_rol = "Estudiante" if user['role'] == 'estudiante' else "Docente"
    st.title(f"🎓 {titulo_rol} UNT")
    st.write(f"Bienvenido, **{user['nombre_completo']}**")

    db_manager = DatabaseManager()
    image_manager = ImageManager()

    # Verificar si está sancionado
    sanc_bloq = _usuario_sancionado_vigente(db_manager, int(user['user_id']))
    if sanc_bloq:
        if user.get('fecha_fin_sancion'):
            fecha_fin = datetime.fromtimestamp(user['fecha_fin_sancion']).strftime('%d/%m/%Y')
            show_sweet_alert(
                "Sanción Activa",
                f"Tienes una sanción activa hasta el {fecha_fin}. No puedes realizar préstamos, reservas, renovaciones ni cancelaciones.",
                "warning"
            )
        else:
            show_sweet_alert(
                "Sanción Activa",
                "Tienes una sanción activa. No puedes realizar préstamos, reservas, renovaciones ni cancelaciones.",
                "warning"
            )

    # Mostrar información del usuario 
    mostrar_info_usuario(user, image_manager, db_manager)

    # Métricas personales
    col1, col2, col3 = st.columns(3)

    with col1:
        prestamos_activos = db_manager.execute_query(
            "SELECT COUNT(*) as count FROM prestamos WHERE usuario_id = %s AND estado = 'activo'",
            (user['user_id'],)
        )[0]['count']
        st.metric("Préstamos Activos", prestamos_activos)

    with col2:
        reservas_pendientes = db_manager.execute_query(
            "SELECT COUNT(*) as count FROM reservas WHERE usuario_id = %s AND estado = 'pendiente'",
            (user['user_id'],)
        )[0]['count']
        st.metric("Reservas Pendientes", reservas_pendientes)

    with col3:
        sanciones_activas = db_manager.execute_query(
            "SELECT COUNT(*) as count FROM sanciones WHERE usuario_id = %s AND estado = 'activa'",
            (user['user_id'],)
        )[0]['count']
        st.metric("Sanciones Activas", sanciones_activas)

    st.divider()

    # Menú de navegación
    opcion = st.sidebar.radio("Navegación", [
        "Inicio",
        "Catálogo de Libros",
        "Mis Préstamos",
        "Mis Reservas",
        "Mis Sanciones",
        "Mi Perfil"
    ])

    if opcion == "Inicio":
        mostrar_inicio(db_manager, user)
    elif opcion == "Catálogo de Libros":
        gestion_libros(db_manager, show_sweet_alert, user['role'])
    elif opcion == "Mis Préstamos":
        st.header("Mis Préstamos Activos")
        mostrar_prestamos(db_manager, user, sanc_bloq)
    elif opcion == "Mis Reservas":
        st.header("Mis Reservas Pendientes")
        mostrar_reservas(db_manager, user, sanc_bloq)
    elif opcion == "Mis Sanciones":
        st.header("Historial de Sanciones")
        mostrar_sanciones(db_manager, user)
    elif opcion == "Mi Perfil":
        perfil_usuario(db_manager, user, show_sweet_alert)

    if st.sidebar.button("Cerrar Sesión"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

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

# ============================
# Secciones de contenido
# ============================
def mostrar_inicio(db_manager, user):
    """Muestra la página de inicio con estadísticas y resumen"""    
    # Resumen de actividad reciente
    st.subheader("📈 Mi Actividad Reciente")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Libros leídos este mes
        libros_mes = db_manager.execute_query("""
            SELECT COUNT(*) as total
            FROM prestamos 
            WHERE usuario_id = %s 
            AND fecha_prestamo >= UNIX_TIMESTAMP(LAST_DAY(NOW()) + INTERVAL 1 DAY - INTERVAL 1 MONTH)
            AND fecha_prestamo < UNIX_TIMESTAMP(LAST_DAY(NOW()) + INTERVAL 1 DAY)
        """, (user['user_id'],))[0]['total']
        st.metric("Libros este mes", libros_mes)
    
    with col2:
        # Días sin devoluciones atrasadas
        dias_sin_atraso = db_manager.execute_query("""
            SELECT DATEDIFF(NOW(), FROM_UNIXTIME(MAX(fecha_devolucion_real))) as dias
            FROM prestamos 
            WHERE usuario_id = %s 
            AND estado = 'devuelto'
            AND fecha_devolucion_real <= fecha_devolucion_estimada
        """, (user['user_id'],))
        dias = dias_sin_atraso[0]['dias'] if dias_sin_atraso and dias_sin_atraso[0]['dias'] is not None else 0
        st.metric("Días sin atrasos", dias)
    
    with col3:
        # Porcentaje de libros devueltos a tiempo
        total_prestamos = db_manager.execute_query("""
            SELECT COUNT(*) as total
            FROM prestamos 
            WHERE usuario_id = %s 
            AND estado = 'devuelto'
        """, (user['user_id'],))[0]['total']
        
        atiempo = db_manager.execute_query("""
            SELECT COUNT(*) as total
            FROM prestamos 
            WHERE usuario_id = %s 
            AND estado = 'devuelto'
            AND fecha_devolucion_real <= fecha_devolucion_estimada
        """, (user['user_id'],))[0]['total']
        
        porcentaje = (atiempo / total_prestamos * 100) if total_prestamos > 0 else 100
        st.metric("Devoluciones a tiempo", f"{porcentaje:.1f}%")
    
    # Gráficos estadísticos
    st.subheader("📊 Mis Estadísticas")
    
    # Obtener estadísticas de préstamos por categoría
    categorias_stats = db_manager.execute_query("""
        SELECT c.nombre as categoria, COUNT(p.prestamo_id) as total
        FROM prestamos p
        JOIN libros l ON p.libro_id = l.libro_id
        JOIN categorias c ON l.categoria_id = c.categoria_id
        WHERE p.usuario_id = %s
        GROUP BY c.nombre
        ORDER BY total DESC
        LIMIT 5
    """, (user['user_id'],))
    
    if categorias_stats:
        col1, col2 = st.columns(2)
        
        with col1:
            df_categorias = pd.DataFrame(categorias_stats)
            fig = px.pie(df_categorias, values='total', names='categoria', 
                         title='Préstamos por Categoría')
            st.plotly_chart(fig, use_container_width=True)
    
    # Obtener estadísticas de préstamos por mes
    prestamos_mensuales = db_manager.execute_query("""
        SELECT 
            YEAR(FROM_UNIXTIME(fecha_prestamo)) as año,
            MONTH(FROM_UNIXTIME(fecha_prestamo)) as mes,
            COUNT(*) as total
        FROM prestamos 
        WHERE usuario_id = %s
        GROUP BY año, mes
        ORDER BY año, mes
    """, (user['user_id'],))
    
    if prestamos_mensuales:
        with col2:
            df_mensual = pd.DataFrame(prestamos_mensuales)
            df_mensual['periodo'] = df_mensual['año'].astype(str) + '-' + df_mensual['mes'].astype(str).str.zfill(2)
            
            fig = px.bar(df_mensual, x='periodo', y='total', 
                         title='Préstamos por Mes', labels={'periodo': 'Mes', 'total': 'Préstamos'})
            st.plotly_chart(fig, use_container_width=True)
    
    # Próximas devoluciones
    st.subheader("📅 Próximas Devoluciones")
    proximas_devoluciones = db_manager.execute_query("""
        SELECT l.titulo, a.nombre_completo as autor, 
               FROM_UNIXTIME(p.fecha_devolucion_estimada) as fecha_devolucion
        FROM prestamos p
        JOIN libros l ON p.libro_id = l.libro_id
        JOIN autores a ON l.autor_id = a.autor_id
        WHERE p.usuario_id = %s 
        AND p.estado = 'activo'
        ORDER BY p.fecha_devolucion_estimada ASC
        LIMIT 5
    """, (user['user_id'],))
    
    if proximas_devoluciones:
        for devolucion in proximas_devoluciones:
            dias_restantes = (devolucion['fecha_devolucion'] - datetime.now()).days
            st.info(
                f"**{devolucion['titulo']}** por {devolucion['autor']}\n"
                f"Vence: {devolucion['fecha_devolucion'].strftime('%d/%m/%Y')} "
                f"({dias_restantes} días restantes)"
            )
    else:
        st.success("No tienes devoluciones pendientes.")
    
    # Recomendaciones basadas en historial
    st.subheader("🎯 Recomendaciones para ti")
    recomendaciones = db_manager.execute_query("""
        SELECT l.titulo, a.nombre_completo as autor, c.nombre as categoria,
               l.ejemplares_disponibles, l.portada_id
        FROM libros l
        JOIN autores a ON l.autor_id = a.autor_id
        JOIN categorias c ON l.categoria_id = c.categoria_id
        WHERE l.activo = TRUE
        AND l.ejemplares_disponibles > 0
        AND l.categoria_id IN (
            SELECT DISTINCT l2.categoria_id
            FROM prestamos p
            JOIN libros l2 ON p.libro_id = l2.libro_id
            WHERE p.usuario_id = %s
        )
        AND l.libro_id NOT IN (
            SELECT libro_id FROM prestamos WHERE usuario_id = %s
        )
        ORDER BY l.ejemplares_disponibles DESC
        LIMIT 3
    """, (user['user_id'], user['user_id']))
    
    if recomendaciones:
        for libro in recomendaciones:
            col1, col2 = st.columns([1, 3])
            with col1:
                if libro['portada_id'] and os.path.exists(libro['portada_id']):
                    st.image(libro['portada_id'], width=80)
                else:
                    st.image(ImageManager().get_default_cover(), width=80)
            with col2:
                st.write(f"**{libro['titulo']}**")
                st.write(f"*{libro['autor']}*")
                st.write(f"Categoría: {libro['categoria']}")
                st.write(f"Disponibles: {libro['ejemplares_disponibles']}")
    else:
        st.info("Explora nuestro catálogo para descubrir nuevos libros.")

def mostrar_prestamos(db_manager, user, sanc_bloq: bool):
    prestamos = db_manager.execute_query("""
        SELECT p.prestamo_id, l.titulo, a.nombre_completo as autor, l.portada_id,
               FROM_UNIXTIME(p.fecha_prestamo) as fecha_prestamo,
               FROM_UNIXTIME(p.fecha_devolucion_estimada) as fecha_devolucion_estimada,
               p.renovaciones, p.estado
        FROM prestamos p
        JOIN libros l ON p.libro_id = l.libro_id
        JOIN autores a ON l.autor_id = a.autor_id
        WHERE p.usuario_id = %s AND p.estado = 'activo'
    """, (user['user_id'],))

    if prestamos:
        for prestamo in prestamos:
            st.markdown(f"**{prestamo['titulo']}** por {prestamo['autor']}")
            st.markdown(
                f"Préstamo: {prestamo['fecha_prestamo'].strftime('%d/%m/%Y')} | "
                f"Devolución: **{prestamo['fecha_devolucion_estimada'].strftime('%d/%m/%Y')}**"
            )
            st.caption(f"Renovaciones: {prestamo['renovaciones']}")

            if sanc_bloq:
                st.warning("No puedes renovar préstamos mientras tengas sanciones activas.")
            else:
                max_renov = int(db_manager.execute_query(
                    "SELECT valor FROM configuracion WHERE parametro = 'max_renovaciones'"
                )[0]['valor'])
                if prestamo['renovaciones'] < max_renov:
                    if st.button("Renovar", key=f"renovar_{prestamo['prestamo_id']}"):
                        renovar_prestamo(db_manager, prestamo['prestamo_id'], user)
                else:
                    st.warning("Máximo de renovaciones alcanzado.")
            st.divider()
    else:
        st.info("No tienes préstamos activos.")

def mostrar_reservas(db_manager, user, sanc_bloq: bool):
    reservas = db_manager.execute_query("""
        SELECT r.reserva_id, l.titulo, a.nombre_completo as autor,
               FROM_UNIXTIME(r.fecha_reserva) as fecha_reserva,
               FROM_UNIXTIME(r.fecha_expiracion) as fecha_expiracion
        FROM reservas r
        JOIN libros l ON r.libro_id = l.libro_id
        JOIN autores a ON l.autor_id = a.autor_id
        WHERE r.usuario_id = %s AND r.estado = 'pendiente'
    """, (user['user_id'],))

    if reservas:
        for reserva in reservas:
            st.markdown(f"**{reserva['titulo']}** por {reserva['autor']}")
            st.markdown(
                f"Reservado: {reserva['fecha_reserva'].strftime('%d/%m/%Y')} | "
                f"Expira: **{reserva['fecha_expiracion'].strftime('%d/%m/%Y')}**"
            )

            if sanc_bloq:
                st.warning("No puedes cancelar reservas mientras tengas sanciones activas.")
            else:
                if st.button("Cancelar Reserva", key=f"cancelar_{reserva['reserva_id']}"):
                    cancelar_reserva(reserva['reserva_id'])
            st.divider()
    else:
        st.info("No tienes reservas pendientes.")

# ============================
# Sanciones y acciones extra
# ============================
def _df_sanciones_espanol(sanciones_raw: list[dict]) -> pd.DataFrame:
    """Convierte filas de sanciones a un DataFrame con encabezados en español."""
    if not sanciones_raw:
        return pd.DataFrame(columns=["Motivo", "Inicio", "Fin", "Monto (S/)", "Estado"])

    def _fmt(dt: datetime) -> str:
        try:
            return dt.strftime('%d/%m/%Y %I:%M %p')
        except Exception:
            return "-"

    filas = []
    for r in sanciones_raw:
        estado = (r.get('estado') or '').strip()
        estado = estado.capitalize() if estado else '-'
        filas.append({
            "Motivo": r.get('motivo', '-') or '-',
            "Inicio": _fmt(r.get('fecha_inicio')),
            "Fin": _fmt(r.get('fecha_fin')),
            "Monto (S/)": f"{float(r.get('monto') or 0):.2f}",
            "Estado": estado,
        })
    return pd.DataFrame(filas)


def _paginador_df(df: pd.DataFrame):
    """UI de paginación sin tocar la BD. Devuelve el DF de la página actual."""
    if df is None or df.empty:
        return df, 1, 1

    col_a, col_b = st.columns([1, 3])
    with col_a:
        page_size = st.selectbox("Filas por página", [5, 10, 20, 50], index=1)
    total = len(df)
    total_pages = max((total + page_size - 1) // page_size, 1)

    if 'sanciones_pag' not in st.session_state:
        st.session_state['sanciones_pag'] = 1

    with col_b:
        page = st.number_input("Página", min_value=1, max_value=total_pages, value=st.session_state['sanciones_pag'], step=1)

    st.session_state['sanciones_pag'] = page

    start = (page - 1) * page_size
    end = start + page_size
    df_page = df.iloc[start:end]
    st.caption(f"Página {page} de {total_pages} • {total} registros")
    return df_page, page, total_pages


def _pdf_from_df(df: pd.DataFrame, titulo: str = "Historial de Sanciones") -> bytes | None:
    """Genera un PDF simple (paisaje A4) con una tabla desde un DataFrame."""
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=landscape(A4), leftMargin=18, rightMargin=18, topMargin=18, bottomMargin=18
        )
        styles = getSampleStyleSheet()
        elements = [Paragraph(titulo, styles['Heading2']), Spacer(1, 6)]

        data = [list(df.columns)] + df.astype(str).values.tolist()
        tbl = Table(data, repeatRows=1)
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),  
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgoldenrodyellow]),
        ]))
        elements.append(tbl)
        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()
        return pdf
    except Exception as e:
        st.error(f"No se pudo generar el PDF: {e}")
        return None


def mostrar_sanciones(db_manager, user):
    """Muestra las sanciones del usuario (historial) en español + paginación + exportar PDF."""
    sanciones_raw = db_manager.execute_query(
        """
        SELECT s.motivo,
               FROM_UNIXTIME(s.fecha_inicio) AS fecha_inicio,
               FROM_UNIXTIME(s.fecha_fin)     AS fecha_fin,
               s.monto,
               s.estado
        FROM sanciones s
        WHERE s.usuario_id = %s
        ORDER BY s.fecha_inicio DESC
        """,
        (user['user_id'],)
    )

    if sanciones_raw:
        df = _df_sanciones_espanol(sanciones_raw)
        df_page, page, total_pages = _paginador_df(df)
        st.dataframe(df_page, use_container_width=True)

        # Botones de descarga
        colx, coly = st.columns(2)
        with colx:
            pdf_page = _pdf_from_df(df_page, titulo=f"Historial de Sanciones – Página {page}")
            if pdf_page:
                st.download_button(
                    "Descargar PDF (página actual)",
                    data=pdf_page,
                    file_name=f"sanciones_pagina_{page}.pdf",
                    mime="application/pdf",
                    key=f"dl_pdf_pag_{page}"
                )
        with coly:
            pdf_all = _pdf_from_df(df, titulo="Historial de Sanciones – Completo")
            if pdf_all:
                st.download_button(
                    "Descargar PDF (todo)",
                    data=pdf_all,
                    file_name="sanciones_historial_completo.pdf",
                    mime="application/pdf",
                    key="dl_pdf_all"
                )
    else:
        st.info("No tienes sanciones registradas.")


def renovar_prestamo(db_manager, prestamo_id, user):
    """Renueva un préstamo"""
    max_renovaciones = int(db_manager.execute_query(
        "SELECT valor FROM configuracion WHERE parametro = 'max_renovaciones'"
    )[0]['valor'])
    prestamo_actual = db_manager.execute_query(
        "SELECT renovaciones FROM prestamos WHERE prestamo_id = %s",
        (prestamo_id,)
    )

    if prestamo_actual[0]['renovaciones'] >= max_renovaciones:
        show_sweet_alert("Límite de Renovación", "Ya has alcanzado el límite de renovaciones para este préstamo.", "warning")
        return

    # Obtener días de renovación según el rol
    if user['role'] == 'estudiante':
        dias_extra = int(db_manager.execute_query(
            "SELECT valor FROM configuracion WHERE parametro = 'dias_renovacion_estudiante'"
        )[0]['valor'])
    else:
        dias_extra = int(db_manager.execute_query(
            "SELECT valor FROM configuracion WHERE parametro = 'dias_renovacion_docente'"
        )[0]['valor'])

    # Calcular nueva fecha de devolución
    prestamo_info = db_manager.execute_query(
        "SELECT fecha_devolucion_estimada FROM prestamos WHERE prestamo_id = %s",
        (prestamo_id,)
    )
    fecha_base = prestamo_info[0]['fecha_devolucion_estimada']
    nueva_fecha = fecha_base + (dias_extra * 86400)

    db_manager.execute_query(
        "UPDATE prestamos SET fecha_devolucion_estimada = %s, renovaciones = renovaciones + 1 WHERE prestamo_id = %s",
        (nueva_fecha, prestamo_id),
        return_result=False
    )

    show_sweet_alert(
        "Préstamo Renovado",
        f"Préstamo renovado hasta {datetime.fromtimestamp(nueva_fecha).strftime('%d/%m/%Y')}",
        "success"
    )
    st.rerun()


def cancelar_reserva(reserva_id):
    """Cancela una reserva"""
    db_manager = DatabaseManager()
    db_manager.execute_query(
        "UPDATE reservas SET estado = 'cancelada' WHERE reserva_id = %s",
        (reserva_id,),
        return_result=False
    )
    show_sweet_alert("Reserva Cancelada", "Reserva cancelada correctamente.", "success")
    st.rerun()
