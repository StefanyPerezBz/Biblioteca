# src/services/prestamos.py
# ------------------------------------------------------------
# Vistas y helpers para gestión de préstamos
# - Admin: gestion_prestamos()
# - Bibliotecario: gestion_prestamos_bibliotecario(), gestion_devoluciones()
# ------------------------------------------------------------
import os
from math import ceil
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from src.database.database import DatabaseManager
from src.utils.alert_utils import show_sweet_alert

# Estados finales permitidos por el procedimiento registrar_devolucion
ESTADOS_DEVOLUCION = {
    "Devuelto": "devuelto",
    "Dañado": "dañado",
    "Perdido": "perdido"
}

# ------------------------------------------------------------
# Utilidades de formato y horario
# ------------------------------------------------------------
LIMA = ZoneInfo("America/Lima")

def fmt12(ts):
    """Convierte epoch a 'DD/MM/YYYY hh:mm AM/PM' en zona America/Lima."""
    try:
        return datetime.fromtimestamp(int(ts), tz=LIMA).strftime('%d/%m/%Y %I:%M %p')
    except Exception:
        return "-"

def _en_horario_habil(dt: datetime | None = None) -> bool:
    """
    True si la hora local de Lima está entre 07:00 y 14:45 (inclusive).
    """
    now = dt or datetime.now(tz=LIMA)
    t = now.time()
    return (t >= dt_time(7, 0)) and (t <= dt_time(14, 45))

def _mensaje_mysql_amigable(texto):
    """Extrae un mensaje legible del error de MySQL."""
    s = str(texto)
    if ": " in s:
        return s.split(": ", 1)[1].strip()
    return s

# ------------------------------------------------------------
# Imagen por defecto (robusta)
# ------------------------------------------------------------
def _default_cover_path():
    """
    Devuelve la primera ruta existente para la imagen por defecto.
    Intenta en este orden:
      - assets/default_cover.jpg
      - assets/default_cover.png
      - default_cover.jpg
      - default_cover.png
    Si no encuentra ninguna, retorna None (se mostrará placeholder textual).
    """
    candidates = [
        "assets/default_cover.jpg",
        "assets/default_cover.png",
        "default_cover.jpg",
        "default_cover.png",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

# ------------------------------------------------------------
# BLOQUEO DE USUARIOS SANCIONADOS
# ------------------------------------------------------------

def _usuario_sancionado_vigente(db: DatabaseManager, user_id: int) -> bool:
    """Retorna True si el usuario tiene sanción vigente (sancionado=TRUE y fin > ahora o fin NULL)."""
    r = db.execute_query(
        "SELECT sancionado, COALESCE(fecha_fin_sancion,0) AS fin FROM usuarios WHERE user_id=%s",
        (int(user_id),)
    )
    if not r:
        return False
    sanc = bool(r[0]["sancionado"]) if isinstance(r[0]["sancionado"], (int, bool)) else str(r[0]["sancionado"]).lower() == 'true'
    fin = int(r[0]["fin"] or 0)
    now = int(datetime.now(tz=LIMA).timestamp())
    return sanc and (fin == 0 or fin > now)

# ------------------------------------------------------------
# Paginación UI
# ------------------------------------------------------------

def _paginador(total_items: int, state_key: str, page_size_default: int, page_size_options: list[int]):
    """
    Renderiza controles de paginación y devuelve (page_index, page_size, total_pages).
    - page_index es 0-based.
    """
    if f"{state_key}_page" not in st.session_state:
        st.session_state[f"{state_key}_page"] = 0
    if f"{state_key}_size" not in st.session_state:
        st.session_state[f"{state_key}_size"] = page_size_default

    cols = st.columns([1, 3, 2, 1, 1])
    with cols[1]:
        page_size = st.selectbox("Tamaño de página", page_size_options, index=page_size_options.index(page_size_default), key=f"{state_key}_size_select")
        st.session_state[f"{state_key}_size"] = page_size

    page_size = st.session_state[f"{state_key}_size"]
    total_pages = max(1, ceil(total_items / page_size))
    page_index = min(st.session_state[f"{state_key}_page"], total_pages - 1)

    with cols[0]:
        if st.button("<< Anterior", disabled=(page_index <= 0), key=f"{state_key}_prev"):
            page_index -= 1
    with cols[3]:
        if st.button("Siguiente >>", disabled=(page_index >= total_pages - 1), key=f"{state_key}_next"):
            page_index += 1
    with cols[2]:
        st.markdown(f"**Página {page_index + 1} de {total_pages}**")

    st.session_state[f"{state_key}_page"] = page_index
    return page_index, page_size, total_pages

# ------------------------------------------------------------
# Libros disponibles (con búsqueda + paginación)
# ------------------------------------------------------------

def _contar_libros_disponibles(db: DatabaseManager, search: str = "") -> int:
    q = """
        SELECT COUNT(*) AS c
        FROM libros l
        JOIN autores a ON l.autor_id = a.autor_id
        WHERE l.activo = TRUE
          AND l.ejemplares_disponibles > 0
          AND (l.titulo LIKE %s OR a.nombre_completo LIKE %s OR l.isbn LIKE %s)
    """
    like = f"%{search or ''}%"
    res = db.execute_query(q, (like, like, like))
    return int(res[0]["c"]) if res else 0


def _listar_libros_disponibles(db: DatabaseManager, search: str, limit: int, offset: int):
    q = f"""
        SELECT l.libro_id,
               l.titulo,
               a.nombre_completo AS autor,
               l.ejemplares_disponibles,
               l.ejemplares_totales,
               l.anio_publicacion,
               l.editorial,
               l.isbn,
               l.portada_id AS portada
        FROM libros l
        JOIN autores a ON l.autor_id = a.autor_id
        WHERE l.activo = TRUE
          AND l.ejemplares_disponibles > 0
          AND (l.titulo LIKE %s OR a.nombre_completo LIKE %s OR l.isbn LIKE %s)
        ORDER BY l.titulo
        LIMIT %s OFFSET %s
    """
    like = f"%{search or ''}%"
    return db.execute_query(q, (like, like, like, int(limit), int(offset))) or []


def _selector_libro_card(db: DatabaseManager, key_prefix="loan"):
    """
    Muestra libros disponibles en formato de cards (portada + info + botón).
    Incluye búsqueda y paginación. Devuelve el libro_id seleccionado (o None).
    """
    st.write("#### Seleccionar libro")
    search = st.text_input(
        "Buscar por título / autor / ISBN",
        key=f"{key_prefix}_busca_libro",
        placeholder="Ej.: Programación, García Márquez, 978..."
    )

    # Si cambia la búsqueda, reseteamos la página
    if st.session_state.get(f"{key_prefix}_last_search") != search:
        st.session_state[f"{key_prefix}_last_search"] = search
        st.session_state[f"{key_prefix}_libros_page"] = 0

    total_libros = _contar_libros_disponibles(db, search)
    page_index, page_size, total_pages = _paginador(
        total_libros, state_key=f"{key_prefix}_libros", page_size_default=9, page_size_options=[6, 9, 12, 15]
    )
    offset = page_index * page_size

    libros = _listar_libros_disponibles(db, search, limit=page_size, offset=offset)
    if not libros:
        st.info("No hay libros disponibles que coincidan con la búsqueda.")
        return None, None

    selected_id = st.session_state.get(f"{key_prefix}_libro_sel")
    selected_row = None

    cols_per_row = 3
    for i in range(0, len(libros), cols_per_row):
        row = st.columns(cols_per_row)
        for j, col in enumerate(row):
            if i + j >= len(libros):
                break
            lib = libros[i + j]
            with col:
                portada_path = lib.get("portada")
                if portada_path and os.path.exists(portada_path):
                    st.image(portada_path, width=140)
                else:
                    fallback = _default_cover_path()
                    if fallback:
                        st.image(fallback, width=140)
                    else:
                        st.caption("🖼️ Sin portada")

                st.markdown(f"**{lib['titulo']}**")
                st.caption(f"{lib.get('autor','')} · {lib.get('editorial','')} · {lib.get('anio_publicacion','')}")
                st.caption(f"Disponibles: {lib['ejemplares_disponibles']}/{lib['ejemplares_totales']} · ISBN: {lib.get('isbn','-')}")
                if st.button("Seleccionar", key=f"{key_prefix}_lib_{lib['libro_id']}"):
                    st.session_state[f"{key_prefix}_libro_sel"] = lib["libro_id"]
                    selected_id = lib["libro_id"]
                    selected_row = lib

    ini = offset + 1
    fin = offset + len(libros)
    st.caption(f"Mostrando {ini}–{fin} de {total_libros} libros disponibles")

    if selected_id and not selected_row:
        for lib in libros:
            if lib["libro_id"] == selected_id:
                selected_row = lib
                break

    if selected_id:
        st.success(f"Libro seleccionado: #{selected_id}")
    return selected_id, selected_row

# ------------------------------------------------------------
# Usuarios (destinatario) y operadores
# ------------------------------------------------------------

def _select_usuario_final(db: DatabaseManager, key_prefix="loan"):
    """Selector de destinatario **excluyendo usuarios con sanción vigente**."""
    st.write("#### Seleccionar destinatario")
    q = (
        "SELECT user_id, nombre_completo, role, codigo_unt, dni "
        "FROM usuarios "
        "WHERE activo = TRUE AND validado = TRUE AND role IN ('estudiante','docente') "
        "AND NOT (sancionado = TRUE AND (fecha_fin_sancion IS NULL OR fecha_fin_sancion > UNIX_TIMESTAMP())) "
        "ORDER BY nombre_completo"
    )
    usuarios = db.execute_query(q) or []
    if not usuarios:
        st.info("No hay usuarios válidos (sin sanción vigente) disponibles.")
        return None, None

    etiquetas = [
        f"{u['nombre_completo']} — {u['role']} — "
        f"{'COD: ' + u.get('codigo_unt','') if u.get('codigo_unt') else 'DNI: ' + (u.get('dni') or '')}"
        for u in usuarios
    ]
    idx = st.selectbox(
        "Destinatario",
        list(range(len(etiquetas))),
        key=f"{key_prefix}_dest",
        format_func=lambda i: etiquetas[i],
    )
    return usuarios[idx]["user_id"], usuarios[idx]


def _select_operador(db: DatabaseManager, key_prefix="loan"):
    st.write("#### Seleccionar operador")
    q = """
        SELECT user_id, nombre_completo, role
        FROM usuarios
        WHERE activo = TRUE
          AND (
               role = 'admin'
               OR (role = 'bibliotecario' AND validado = TRUE)
          )
        ORDER BY role, nombre_completo
    """
    ops = db.execute_query(q) or []
    if not ops:
        st.warning("No hay operadores activos (admin / bibliotecario validado).")
        return None, None

    etiquetas = [f"{o['nombre_completo']} — {o['role']}"] if not ops else [f"{o['nombre_completo']} — {o['role']}" for o in ops]
    idx = st.selectbox(
        "Operador",
        list(range(len(etiquetas))),
        key=f"{key_prefix}_oper",
        format_func=lambda i: etiquetas[i],
    )
    return ops[idx]["user_id"], ops[idx]

# ------------------------------------------------------------
# Tabla de préstamos activos (paginada + eliminar)
# ------------------------------------------------------------

def _contar_prestamos_activos(db: DatabaseManager) -> int:
    res = db.execute_query("SELECT COUNT(*) AS c FROM prestamos WHERE estado='activo'")
    return int(res[0]["c"]) if res else 0


def _listar_prestamos_activos(db: DatabaseManager, limit: int, offset: int):
    q = """
        SELECT p.prestamo_id, l.titulo, u.nombre_completo AS usuario, u.role, p.cantidad,
               p.fecha_prestamo, p.fecha_devolucion_estimada
        FROM prestamos p
        JOIN libros l ON p.libro_id = l.libro_id
        JOIN usuarios u ON p.usuario_id = u.user_id
        WHERE p.estado='activo'
        ORDER BY p.fecha_prestamo DESC
        LIMIT %s OFFSET %s
    """
    return db.execute_query(q, (int(limit), int(offset))) or []


def _fila_prestamo_con_acciones(db: DatabaseManager, row: dict, disable_actions: bool = False):
    """
    Renderiza una fila tipo tabla con botón de Eliminar (anulación = registrar_devolucion 'devuelto').
    """
    c = st.columns([1, 3, 3, 1, 2, 2, 2])
    c[0].markdown(f"**{row['prestamo_id']}**")
    c[1].markdown(f"{row['titulo']}")
    c[2].markdown(f"{row['usuario']} ({row['role']})")
    c[3].markdown(f"{row['cantidad']}")
    c[4].markdown(fmt12(row["fecha_prestamo"]))
    c[5].markdown(fmt12(row["fecha_devolucion_estimada"]))
    with c[6]:
        if st.button("Eliminar", key=f"del_{row['prestamo_id']}", disabled=disable_actions):
            res = db.call_procedure("eliminar_prestamo_activo", [int(row["prestamo_id"])])
            if isinstance(res, dict) and res.get("error"):
                st.error(_mensaje_mysql_amigable(res["error"]))
            elif res:
                st.success("Préstamo eliminado (anulado) correctamente.")
                st.rerun()
            else:
                st.error("No se pudo eliminar el préstamo.")


def _tabla_prestamos_activos_pag(db: DatabaseManager):
    st.write("### Préstamos activos")
    total = _contar_prestamos_activos(db)
    page_index, page_size, _ = _paginador(total, state_key="prestamos_tbl", page_size_default=10, page_size_options=[5, 10, 20, 50])
    offset = page_index * page_size

    head = st.columns([1, 3, 3, 1, 2, 2, 2])
    head[0].markdown("**ID**")
    head[1].markdown("**Libro**")
    head[2].markdown("**Usuario (Rol)**")
    head[3].markdown("**Cant.**")
    head[4].markdown("**Prestado**")
    head[5].markdown("**Devolución estimada**")
    head[6].markdown("**Acciones**")

    rows = _listar_prestamos_activos(db, limit=page_size, offset=offset)
    if not rows:
        st.info("No hay registros para mostrar.")
        return

    for r in rows:
        _fila_prestamo_con_acciones(db, r, disable_actions=not _en_horario_habil())

    ini = offset + 1
    fin = offset + len(rows)
    st.caption(f"Mostrando {ini}–{fin} de {total} préstamos activos")

# ------------------------------------------------------------
# Vistas
# ------------------------------------------------------------

def gestion_prestamos():
    """
    Panel de ADMIN:
      - Métricas rápidas
      - Registrar préstamo (con operador seleccionable, selector en cards paginado)
      - Tabla de préstamos activos PAGINADA con botón Eliminar (anulación)
    """
    st.subheader("Gestión de Préstamos")
    db = DatabaseManager()

    # Métricas
    col1, col2, col3, col4 = st.columns(4)
    try:
        col1.metric("Activos", db.execute_query("SELECT COUNT(*) AS c FROM prestamos WHERE estado='activo'")[0]["c"])
        col2.metric("Atrasados", db.execute_query("SELECT COUNT(*) AS c FROM prestamos WHERE estado='activo' AND fecha_devolucion_estimada < UNIX_TIMESTAMP()")[0]["c"])
        col3.metric("Devueltos (30d)", db.execute_query("SELECT COUNT(*) AS c FROM prestamos WHERE estado='devuelto' AND fecha_devolucion_real >= UNIX_TIMESTAMP()-30*86400")[0]["c"])
        col4.metric("Usuarios sancionados", db.execute_query("SELECT COUNT(*) AS c FROM usuarios WHERE sancionado=TRUE AND (fecha_fin_sancion IS NULL OR fecha_fin_sancion>UNIX_TIMESTAMP())")[0]["c"]) 
    except Exception:
        st.warning("No se pudieron calcular algunas métricas.")

    st.markdown("---")
    st.write("### Crear nuevo préstamo")

    if not _en_horario_habil():
        st.warning("⏰ Los préstamos solo se registran entre **07:00 AM** y **02:45 PM** (hora de Lima).")

    libro_id, libro_row = _selector_libro_card(db, key_prefix="adm")
    destinatario_id, _ = _select_usuario_final(db, key_prefix="adm")
    operador_id, _ = _select_operador(db, key_prefix="adm")

    cantidad_max = int(libro_row["ejemplares_disponibles"]) if libro_row else 1
    cantidad = st.number_input(
        "Cantidad a prestar",
        min_value=1,
        max_value=max(1, cantidad_max),
        value=1,
        step=1,
        help="La cantidad no puede exceder el stock disponible."
    )

    # Defensa en profundidad: revalidar sanción justo antes de habilitar/registrar
    bloqueado = bool(destinatario_id and _usuario_sancionado_vigente(db, destinatario_id))
    if bloqueado:
        st.error("El destinatario tiene una sanción vigente. No se pueden registrar préstamos.")

    if st.button("Registrar Préstamo", disabled=not (libro_id and destinatario_id and operador_id) or not _en_horario_habil() or bloqueado):
        res = db.call_procedure("registrar_prestamo", [int(libro_id), int(destinatario_id), int(operador_id), int(cantidad)])
        if isinstance(res, dict) and res.get("error"):
            st.error(_mensaje_mysql_amigable(res["error"]))
        elif res:
            st.success("✅ Préstamo registrado correctamente.")
            st.rerun()
        else:
            st.error("❌ No se pudo registrar el préstamo. Revisa restricciones/stock.")

    st.markdown("---")
    _tabla_prestamos_activos_pag(db)


def gestion_prestamos_bibliotecario(db_manager: DatabaseManager, user, show_sweet_alert):
    """
    Panel de BIBLIOTECARIO:
      - Registrar préstamo como OPERADOR (él mismo) — selector cards paginado
      - Registrar devoluciones (pantalla aparte)
    """
    st.subheader("Registro de préstamos (Bibliotecario)")
    st.caption("Solo docentes o estudiantes pueden ser destinatarios del préstamo.")

    if not _en_horario_habil():
        st.warning("⏰ Los préstamos solo se registran entre **07:00 AM** y **02:45 PM** (hora de Lima).")

    libro_id, libro_row = _selector_libro_card(db_manager, key_prefix=f"bib_{user['user_id']}")
    destinatario_id, _ = _select_usuario_final(db_manager, key_prefix=f"bib_{user['user_id']}")

    cantidad_max = int(libro_row["ejemplares_disponibles"]) if libro_row else 1
    cantidad = st.number_input(
        "Cantidad a prestar",
        min_value=1,
        max_value=max(1, cantidad_max),
        value=1,
        step=1
    )

    # Defensa: revalidar sanción
    bloqueado = bool(destinatario_id and _usuario_sancionado_vigente(db_manager, destinatario_id))
    if bloqueado:
        st.error("El destinatario tiene una sanción vigente. No se pueden registrar préstamos.")

    if st.button("Registrar Préstamo", disabled=not (libro_id and destinatario_id) or not _en_horario_habil() or bloqueado):
        res = db_manager.call_procedure("registrar_prestamo", [int(libro_id), int(destinatario_id), int(user["user_id"]), int(cantidad)])
        if isinstance(res, dict) and res.get("error"):
            show_sweet_alert("Error", _mensaje_mysql_amigable(res["error"]), "error")
        elif res:
            show_sweet_alert("Éxito", "Préstamo registrado correctamente.", "success")
            st.rerun()
        else:
            show_sweet_alert("Error", "No se pudo registrar el préstamo.", "error")


# ------------------------------------------------------------
# Gestión de devoluciones 
# ------------------------------------------------------------

def gestion_devoluciones(db_manager: DatabaseManager, user, show_sweet_alert):
    """
    Panel de BIBLIOTECARIO: registrar devoluciones/cierre de préstamo.
    """
    st.subheader("Devoluciones")

    if not _en_horario_habil():
        st.warning("⏰ Las devoluciones solo se registran entre **07:00 AM** y **02:45 PM** (hora de Lima).")

    q = """
        SELECT p.prestamo_id, l.titulo, u.nombre_completo, u.role, p.cantidad,
               p.fecha_prestamo, p.fecha_devolucion_estimada
        FROM prestamos p
        JOIN libros l ON p.libro_id = l.libro_id
        JOIN usuarios u ON p.usuario_id = u.user_id
        WHERE p.estado = 'activo'
        ORDER BY p.fecha_prestamo DESC
        LIMIT 200
    """
    prs = db_manager.execute_query(q) or []
    if not prs:
        st.info("No hay préstamos activos.")
        return

    etiquetas = [
        f"#{x['prestamo_id']} — {x['titulo']} — {x['nombre_completo']} "
        f"({x['role']}) · Prestado: {fmt12(x['fecha_prestamo'])} · Dev. estimada: {fmt12(x['fecha_devolucion_estimada'])}"
        for x in prs
    ]
    idx = st.selectbox("Préstamo activo", list(range(len(etiquetas))), format_func=lambda i: etiquetas[i])
    prestamo_id = prs[idx]["prestamo_id"]

    estado = st.selectbox("Estado final del libro", list(ESTADOS_DEVOLUCION.keys()))
    obs = st.text_area("Observaciones (opcional)")

    if st.button("Registrar Devolución", disabled=not _en_horario_habil()):
        estado_sql = ESTADOS_DEVOLUCION[estado]
        res = db_manager.call_procedure("registrar_devolucion", [int(prestamo_id), estado_sql, obs])

        if isinstance(res, dict) and res.get("error"):
            show_sweet_alert("Error", _mensaje_mysql_amigable(res["error"]), "error")
        elif res:
            show_sweet_alert("Éxito", "Devolución registrada correctamente.", "success")
            st.rerun()
        else:
            show_sweet_alert("Error", "No se pudo registrar la devolución.", "error")
