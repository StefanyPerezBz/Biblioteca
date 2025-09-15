# src/services/reservas.py - Gestión de reservas 
import os
from math import ceil
from datetime import datetime, date, time as dt_time, timedelta
from zoneinfo import ZoneInfo

import streamlit as st
from src.database.database import DatabaseManager
from src.utils.alert_utils import show_sweet_alert

LIMA = ZoneInfo("America/Lima")

# ---------------------------
# Helpers
# ---------------------------

def _fmt12(ts) -> str:
    try:
        return datetime.fromtimestamp(int(ts), tz=LIMA).strftime("%d/%m/%Y %I:%M %p")
    except Exception:
        return "-"


def _default_cover_path():
    for p in ("assets/default_cover.jpg", "assets/default_cover.png", "default_cover.jpg", "default_cover.png"):
        if os.path.exists(p):
            return p
    return None


def _paginador(total: int, key: str, default_size: int = 9, options=(6, 9, 12, 15)):
    if f"{key}_page" not in st.session_state:
        st.session_state[f"{key}_page"] = 0
    if f"{key}_size" not in st.session_state:
        st.session_state[f"{key}_size"] = default_size

    cols = st.columns([1, 3, 2, 1, 1])
    with cols[1]:
        size = st.selectbox("Tamaño de página", list(options), index=list(options).index(default_size), key=f"{key}_size_sel")
        st.session_state[f"{key}_size"] = size

    size = st.session_state[f"{key}_size"]
    total_pages = max(1, ceil(total / size))
    page = min(st.session_state[f"{key}_page"], total_pages - 1)

    with cols[0]:
        if st.button("<< Anterior", disabled=(page <= 0), key=f"{key}_prev"):
            page -= 1
    with cols[3]:
        if st.button("Siguiente >>", disabled=(page >= total_pages - 1), key=f"{key}_next"):
            page += 1
    with cols[2]:
        st.markdown(f"**Página {page + 1} de {total_pages}**")

    st.session_state[f"{key}_page"] = page
    return page, size, total_pages


def _en_horario_habil() -> bool:
    now = datetime.now(tz=LIMA).time()
    return (now >= dt_time(7, 0)) and (now <= dt_time(14, 45))


# ---------------------------
# Reglas de sanción
# ---------------------------

def _usuario_sancionado_vigente(db: DatabaseManager, user_id: int) -> bool:
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


# ---------------------------
# Libros reservables con paginación
# ---------------------------

def _contar_reservables(db: DatabaseManager, search: str) -> int:
    q = """
        SELECT COUNT(*) AS c
        FROM libros l
        JOIN autores a ON l.autor_id = a.autor_id
        WHERE l.activo = TRUE
          AND l.ejemplares_disponibles > 0
          AND (l.titulo LIKE %s OR a.nombre_completo LIKE %s OR l.isbn LIKE %s)
    """
    like = f"%{search or ''}%"
    r = db.execute_query(q, (like, like, like))
    return int(r[0]["c"]) if r else 0


def _listar_reservables(db: DatabaseManager, search: str, limit: int, offset: int):
    q = """
        SELECT l.libro_id, l.titulo, l.editorial, l.anio_publicacion, l.isbn,
               a.nombre_completo AS autor, l.ejemplares_disponibles, l.ejemplares_totales,
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


def _selector_libro_reserva(db: DatabaseManager, key_prefix: str):
    st.write("#### Seleccionar libro para reservar")
    search = st.text_input("Buscar por título / autor / ISBN", key=f"{key_prefix}_busca_libro",
                           placeholder="Ej.: Programación, García Márquez, 978...")

    if st.session_state.get(f"{key_prefix}_last_search") != search:
        st.session_state[f"{key_prefix}_last_search"] = search
        st.session_state[f"{key_prefix}_page"] = 0

    total = _contar_reservables(db, search)
    page, size, _ = _paginador(total, key=f"{key_prefix}_libros", default_size=9)
    offset = page * size
    libros = _listar_reservables(db, search, size, offset)

    if not libros:
        st.info("No hay libros disponibles que coincidan con la búsqueda.")
        return None, None

    sel_id = st.session_state.get(f"{key_prefix}_lib_sel")
    sel_row = None
    cols_per_row = 3

    for i in range(0, len(libros), cols_per_row):
        row = st.columns(cols_per_row)
        for j, col in enumerate(row):
            if i + j >= len(libros):
                break
            lib = libros[i + j]
            with col:
                portada = lib.get("portada")
                if portada and os.path.exists(portada):
                    st.image(portada, width=140)
                else:
                    fallback = _default_cover_path()
                    if fallback:
                        st.image(fallback, width=140)
                    else:
                        st.caption("🖼️ Sin portada")

                st.markdown(f"**{lib['titulo']}**")
                st.caption(f"{lib['autor']} · {lib['editorial']} · {lib['anio_publicacion']}")
                st.caption(f"Disponibles: {lib['ejemplares_disponibles']}/{lib['ejemplares_totales']} · ISBN: {lib.get('isbn', '-')}")
                if st.button("Seleccionar", key=f"{key_prefix}_lib_{lib['libro_id']}"):
                    st.session_state[f"{key_prefix}_lib_sel"] = lib["libro_id"]
                    sel_id = lib["libro_id"]
                    sel_row = lib

    if sel_id and not sel_row:
        for lib in libros:
            if lib["libro_id"] == sel_id:
                sel_row = lib
                break
    if sel_id:
        st.success(f"Libro seleccionado: #{sel_id}")

    ini = offset + 1
    fin = offset + len(libros)
    st.caption(f"Mostrando {ini}–{fin} de {total} libros disponibles")
    return sel_id, sel_row


# ---------------------------
# Reglas y acciones de reservas
# ---------------------------

def _actualizar_expiradas(db: DatabaseManager):
    db.execute_query(
        "UPDATE reservas SET estado='expirada' "
        "WHERE estado='pendiente' AND fecha_expiracion < UNIX_TIMESTAMP()",
        return_result=False
    )


def _dias_exp(db: DatabaseManager) -> int:
    r = db.execute_query("SELECT valor FROM configuracion WHERE parametro='dias_reserva_expiracion'")
    try:
        return int((r[0]["valor"] if r else "2") or "2")
    except Exception:
        return 2


def _hay_cupo_reserva(db: DatabaseManager, libro_id: int) -> bool:
    """Cupo = disponibles - reservas pendientes (no vencidas) > 0"""
    r1 = db.execute_query("SELECT ejemplares_disponibles AS d FROM libros WHERE libro_id=%s AND activo=TRUE", (libro_id,))
    if not r1 or int(r1[0]["d"]) <= 0:
        return False
    r2 = db.execute_query(
        "SELECT COUNT(*) AS c FROM reservas WHERE libro_id=%s AND estado='pendiente' AND fecha_expiracion >= UNIX_TIMESTAMP()",
        (libro_id,)
    )
    disponibles = int(r1[0]["d"])
    pendientes = int(r2[0]["c"]) if r2 else 0
    return (disponibles - pendientes) > 0


def _crear_reserva(db: DatabaseManager, libro_id: int, usuario_id: int) -> tuple[bool, str]:
    # Solo estudiante/docente y activos
    u = db.execute_query(
        "SELECT role, activo, sancionado, COALESCE(fecha_fin_sancion,0) AS fin_sanc "
        "FROM usuarios WHERE user_id=%s", (usuario_id,)
    )
    if not u or not u[0]["activo"]:
        return False, "Usuario no encontrado o inactivo"
    if u[0]["role"] not in ("estudiante", "docente"):
        return False, "Solo docentes o estudiantes pueden reservar"
    # Bloqueo por sanción vigente
    if u[0]["sancionado"] and (int(u[0]["fin_sanc"]) == 0 or int(u[0]["fin_sanc"]) > int(datetime.now(tz=LIMA).timestamp())):
        return False, "Usuario con sanción vigente"

    # Libro activo y con cupo
    l = db.execute_query("SELECT activo FROM libros WHERE libro_id=%s", (libro_id,))
    if not l or not l[0]["activo"]:
        return False, "Libro no encontrado o inactivo"

    if not _hay_cupo_reserva(db, libro_id):
        return False, "No hay cupo de reserva para este libro"

    # Sin préstamo activo de ese libro
    dup_prest = db.execute_query(
        "SELECT 1 FROM prestamos WHERE usuario_id=%s AND libro_id=%s AND estado='activo' LIMIT 1",
        (usuario_id, libro_id)
    )
    if dup_prest:
        return False, "Ya existe un préstamo activo de este libro para el usuario"

    # Sin reserva pendiente duplicada
    dup_res = db.execute_query(
        "SELECT 1 FROM reservas WHERE usuario_id=%s AND libro_id=%s AND estado='pendiente' "
        "AND fecha_expiracion >= UNIX_TIMESTAMP() LIMIT 1",
        (usuario_id, libro_id)
    )
    if dup_res:
        return False, "Ya existe una reserva pendiente para este libro"

    # Crear
    dias = _dias_exp(db)
    db.execute_query(
        "INSERT INTO reservas (libro_id, usuario_id, fecha_reserva, fecha_expiracion, estado) "
        "VALUES (%s, %s, UNIX_TIMESTAMP(), UNIX_TIMESTAMP()+%s*86400, 'pendiente')",
        (libro_id, usuario_id, int(dias)),
        return_result=False
    )
    return True, "Reserva registrada"


# ---------------------------
# Vistas: Admin/Bibliotecario
# ---------------------------

def _vista_admin_biblio(db: DatabaseManager, user: dict):
    st.subheader("Gestión de Reservas")
    _actualizar_expiradas(db)

    tabs = st.tabs(["Reservas pendientes", "Crear reserva", "Historial reciente"])

    # Pendientes
    with tabs[0]:
        r = db.execute_query(
            """
            SELECT r.reserva_id, r.libro_id, l.titulo,
                   u.user_id, u.nombre_completo AS usuario, u.role,
                   r.fecha_reserva, r.fecha_expiracion,
                   (r.fecha_expiracion < UNIX_TIMESTAMP()) AS expirada
            FROM reservas r
            JOIN libros l   ON r.libro_id = l.libro_id
            JOIN usuarios u ON r.usuario_id = u.user_id
            WHERE r.estado='pendiente'
            ORDER BY r.fecha_expiracion
            """
        ) or []
        if not r:
            st.info("No hay reservas pendientes.")
        else:
            head = st.columns([1, 3, 3, 2, 2, 2])
            head[0].markdown("**ID**")
            head[1].markdown("**Libro**")
            head[2].markdown("**Usuario (Rol)**")
            head[3].markdown("**Reservado**")
            head[4].markdown("**Expira**")
            head[5].markdown("**Acciones**")

            for row in r:
                c = st.columns([1, 3, 3, 2, 2, 2])
                c[0].markdown(f"**{row['reserva_id']}**")
                c[1].markdown(row["titulo"])
                c[2].markdown(f"{row['usuario']} ({row['role']})")
                c[3].markdown(_fmt12(row["fecha_reserva"]))
                c[4].markdown(_fmt12(row["fecha_expiracion"]))

                with c[5]:
                    # Entregar -> convierte en préstamo (cantidad 1), operador = user actual
                    sanc_bloq = _usuario_sancionado_vigente(db, int(row['user_id']))
                    entregar_dis = (not _en_horario_habil()) or bool(row["expirada"]) or sanc_bloq
                    if sanc_bloq:
                        st.warning("El usuario tiene sanción vigente; no se puede entregar.")

                    if st.button("Entregar", key=f"ent_{row['reserva_id']}", disabled=entregar_dis):
                        res = db.call_procedure(
                            "registrar_prestamo",
                            [int(row["libro_id"]), int(row["user_id"]), int(user["user_id"]), 1]
                        )
                        if isinstance(res, dict) and res.get("error"):
                            show_sweet_alert("Error", str(res["error"]).split(": ", 1)[-1], "error")
                        elif res:
                            db.execute_query(
                                "UPDATE reservas SET estado='completada' WHERE reserva_id=%s",
                                (int(row["reserva_id"]),),
                                return_result=False
                            )
                            show_sweet_alert("Éxito", "Préstamo registrado desde reserva.", "success")
                            st.rerun()
                        else:
                            show_sweet_alert("Error", "No se pudo completar la operación.", "error")

                    if st.button("Cancelar", key=f"can_{row['reserva_id']}", disabled=bool(row["expirada"])):
                        db.execute_query(
                            "UPDATE reservas SET estado='cancelada' WHERE reserva_id=%s",
                            (int(row["reserva_id"]),),
                            return_result=False
                        )
                        show_sweet_alert("Listo", "Reserva cancelada.", "success")
                        st.rerun()

    # Crear reserva para un usuario (docente/estudiante)
    with tabs[1]:
        st.caption("Crear reserva en nombre de un docente o estudiante.")
        lib_id, lib_row = _selector_libro_reserva(db, key_prefix="adm_res")
        # selector usuario permitido (SIN sanción vigente)
        usuarios = db.execute_query(
            "SELECT user_id, nombre_completo, role, sancionado, COALESCE(fecha_fin_sancion,0) AS fin "
            "FROM usuarios "
            "WHERE activo=TRUE AND validado=TRUE AND role IN ('docente','estudiante') "
            "AND NOT (sancionado = TRUE AND (fecha_fin_sancion IS NULL OR fecha_fin_sancion > UNIX_TIMESTAMP())) "
            "ORDER BY nombre_completo"
        ) or []
        destinatario_id = None
        if not usuarios:
            st.info("No hay usuarios válidos para reservar (sin sanción vigente).")
        else:
            etiquetas = [f"{u['nombre_completo']} — {u['role']}" for u in usuarios]
            idx = st.selectbox("Usuario", range(len(etiquetas)), format_func=lambda i: etiquetas[i], key="adm_res_usr")
            destinatario_id = usuarios[idx]["user_id"]

        bloqueado = bool(destinatario_id and _usuario_sancionado_vigente(db, destinatario_id))
        if bloqueado:
            st.error("El usuario tiene una sanción vigente. No se pueden crear reservas.")

        if st.button("Reservar", disabled=not (lib_id and destinatario_id) or bloqueado):
            ok, msg = _crear_reserva(db, int(lib_id), int(destinatario_id))
            if ok:
                show_sweet_alert("Éxito", msg, "success"); st.rerun()
            else:
                show_sweet_alert("No permitido", msg, "error")

    # Historial
    with tabs[2]:
        rows = db.execute_query(
            """
            SELECT r.reserva_id, l.titulo, u.nombre_completo AS usuario, u.role,
                   r.fecha_reserva, r.fecha_expiracion, r.estado
            FROM reservas r
            JOIN libros l   ON r.libro_id = l.libro_id
            JOIN usuarios u ON r.usuario_id = u.user_id
            ORDER BY r.fecha_reserva DESC
            LIMIT 200
            """
        ) or []
        if not rows:
            st.info("No hay historial por mostrar.")
        else:
            for row in rows:
                st.write(
                    f"#{row['reserva_id']} • {row['titulo']} • {row['usuario']} ({row['role']}) — "
                    f"Reserva: {_fmt12(row['fecha_reserva'])} • Expira: {_fmt12(row['fecha_expiracion'])} • "
                    f"Estado: {row['estado'].capitalize()}"
                )


# ---------------------------
# Vistas: Docente/Estudiante
# ---------------------------

def _vista_usuario(db: DatabaseManager, user: dict):
    st.subheader("Mis Reservas")
    _actualizar_expiradas(db)

    # Chequeo de sanción activa — deshabilita reservar
    sanc_bloq = _usuario_sancionado_vigente(db, int(user["user_id"]))

    tab1, tab2 = st.tabs(["Reservar libro", "Mis reservas"])

    # Reservar libro
    with tab1:
        lib_id, _ = _selector_libro_reserva(db, key_prefix=f"user{user['user_id']}")
        if sanc_bloq:
            st.warning("Tienes una sanción activa. No puedes realizar reservas.")
        if st.button("Reservar", disabled=not bool(lib_id) or sanc_bloq):
            ok, msg = _crear_reserva(db, int(lib_id), int(user["user_id"]))
            if ok:
                show_sweet_alert("Éxito", msg, "success"); st.rerun()
            else:
                show_sweet_alert("No permitido", msg, "error")

    # Mis reservas
    with tab2:
        r = db.execute_query(
            """
            SELECT r.reserva_id, l.titulo, r.fecha_reserva, r.fecha_expiracion, r.estado
            FROM reservas r
            JOIN libros l ON r.libro_id = l.libro_id
            WHERE r.usuario_id=%s
            ORDER BY r.fecha_reserva DESC
            """,
            (user["user_id"],)
        ) or []
        if not r:
            st.info("No tienes reservas registradas.")
        else:
            for row in r:
                st.write(
                    f"#{row['reserva_id']} • {row['titulo']} — "
                    f"Reserva: {_fmt12(row['fecha_reserva'])} • Expira: {_fmt12(row['fecha_expiracion'])} • "
                    f"Estado: {row['estado'].capitalize()}"
                )


# ---------------------------
# Entrada principal
# ---------------------------

def gestion_reservas(db_manager: DatabaseManager, user: dict, show_sweet_alert):
    if user.get("role") in ("admin", "bibliotecario"):
        _vista_admin_biblio(db_manager, user)
    else:
        _vista_usuario(db_manager, user)
