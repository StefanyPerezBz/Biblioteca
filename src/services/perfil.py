# src/services/perfil.py
import os
import re
import streamlit as st
from typing import Optional

from src.database.database import DatabaseManager
from src.utils.alert_utils import show_sweet_alert
from src.utils.image_manager import ImageManager
from src.auth.auth import AuthManager  # para hash/verify de contraseñas

# ---------------------------
# Validaciones
# ---------------------------

def _validar_nombre(nombre: str) -> tuple[bool, Optional[str]]:
    if not nombre or not nombre.strip():
        return False, "El nombre no puede estar vacío."
    if not re.fullmatch(r"^[A-Za-zÁÉÍÓÚáéíóúÜüÑñ\s]+$", nombre.strip()):
        return False, "El nombre solo puede contener letras y espacios."
    return True, None

def _validar_username(username: str) -> tuple[bool, Optional[str]]:
    if not re.fullmatch(r"^(?=.*[A-Za-z])[A-Za-z0-9_]{4,}$", username or ""):
        return False, "El usuario debe tener ≥ 4 caracteres, al menos 1 letra y solo letras/números/_"
    return True, None

def _validar_password(pwd: str) -> tuple[bool, Optional[str]]:
    if not pwd or len(pwd) < 8:
        return False, "La contraseña debe tener al menos 8 caracteres."
    if not re.search(r"[a-z]", pwd):
        return False, "La contraseña debe incluir al menos 1 minúscula."
    if not re.search(r"[A-Z]", pwd):
        return False, "La contraseña debe incluir al menos 1 mayúscula."
    if not re.search(r"\d", pwd):
        return False, "La contraseña debe incluir al menos 1 número."
    if not re.search(r"[!@#$%^&*()\\-_=+]", pwd):
        return False, "La contraseña debe incluir al menos 1 carácter especial (!@#$%^&*()-_=+)."
    return True, None

# ---------------------------
# Vista principal de perfil
# ---------------------------

def perfil_usuario(db: DatabaseManager, user: dict, show_alert=show_sweet_alert):
    """
    Vista de perfil autocontenida.
    Permite que el propio usuario edite nombre, usuario, contraseña y foto con validaciones.
    El DNI es solo lectura.
    """
    st.subheader("Mi Perfil")

    img = ImageManager()
    auth = AuthManager()

    # --- Datos actuales (lectura) ---
    row = db.execute_query(
        """
        SELECT u.user_id, u.username, u.role, u.nombre_completo, u.email, u.dni, u.codigo_unt,
               u.foto_perfil_id, u.sede_id, u.password_hash,
               s.nombre AS sede,
               f.nombre AS facultad,
               e.nombre AS escuela
        FROM usuarios u
        LEFT JOIN sedes s      ON u.sede_id = s.sede_id
        LEFT JOIN facultades f ON u.facultad_id = f.facultad_id
        LEFT JOIN escuelas e   ON u.escuela_id = e.escuela_id
        WHERE u.user_id = %s
        """,
        (int(user["user_id"]),)
    )
    if not row:
        st.error("No se pudo cargar tu perfil.")
        return
    u = row[0]

    colA, colB = st.columns([1, 2])

    # --- Columna A: imagen + acciones ---
    with colA:
        foto_path = u.get("foto_perfil_id")
        if foto_path and os.path.exists(foto_path):
            st.image(foto_path, width=160)
        else:
            st.image(img.get_default_cover(), width=160)

        subir = st.file_uploader("Actualizar foto (JPG/PNG)", type=["jpg", "jpeg", "png"])

        if st.button("Eliminar foto de perfil"):
            old = u.get("foto_perfil_id")
            if old and os.path.exists(old) and "default" not in os.path.basename(old).lower():
                try:
                    img.delete_image_by_path(old)
                except Exception:
                    pass

            default_path = img.get_default_cover()
            db.execute_query(
                "UPDATE usuarios SET foto_perfil_id=%s WHERE user_id=%s",
                (default_path, int(u["user_id"])),
                return_result=False
            )

            if "user" in st.session_state and isinstance(st.session_state["user"], dict):
                st.session_state["user"]["foto_perfil_id"] = default_path

            show_alert("Éxito", "Se eliminó tu foto de perfil. Ahora se muestra la predeterminada.", "success")
            st.rerun()

        st.caption("Se recomienda una imagen cuadrada.")

    # --- Columna B: datos solo lectura ---
    with colB:
        st.text_input("Rol", value=(u.get("role") or "-").capitalize(), disabled=True)
        st.text_input("Correo", value=u.get("email") or "-", disabled=True)
        st.text_input("DNI", value=u.get("dni") or "-", disabled=True)  # <- solo lectura
        st.text_input("Código UNT", value=u.get("codigo_unt") or "-", disabled=True)
        st.text_input("Sede", value=u.get("sede") or "No especificada", disabled=True)

        rol = (u.get("role") or "").lower()
        if rol in ("estudiante", "docente"):
            st.text_input("Facultad", value=u.get("facultad") or "No especificada", disabled=True)
            st.text_input("Carrera/Escuela", value=u.get("escuela") or "No especificada", disabled=True)

    st.markdown("---")

    # --- Edición controlada por el usuario ---
    with st.form("perfil_form"):
        c1, c2 = st.columns(2)

        with c1:
            editar_nombre = st.checkbox("Quiero editar mi nombre", value=False)
            nombre_nuevo = st.text_input(
                "Nombre completo",
                value=u.get("nombre_completo") or "",
                disabled=not editar_nombre,
                help="Solo letras y espacios."
            )

            editar_username = st.checkbox("Quiero editar mi usuario", value=False)
            username_nuevo = st.text_input(
                "Usuario (para iniciar sesión)",
                value=u.get("username") or "",
                disabled=not editar_username,
                help="≥ 4 caracteres, al menos 1 letra; solo letras, números o _"
            )

        with c2:
            editar_password = st.checkbox("Quiero cambiar mi contraseña", value=False)
            pwd_actual = st.text_input(
                "Contraseña actual",
                type="password",
                disabled=not editar_password
            )
            pwd_nuevo = st.text_input(
                "Nueva contraseña",
                type="password",
                disabled=not editar_password
            )
            pwd_conf = st.text_input(
                "Confirmar nueva contraseña",
                type="password",
                disabled=not editar_password
            )

        # ---------------------------
        # Previsualización de impacto (sin DNI)
        # ---------------------------
        impacto = []
        if editar_username and (username_nuevo != (u.get("username") or "")):
            impacto.append(f"• Se actualizará tu **usuario** a **{username_nuevo}** (lo usarás para iniciar sesión).")
        if editar_password:
            impacto.append("• Se actualizará tu **contraseña**.")
        if subir is not None:
            impacto.append("• Se actualizará tu **foto de perfil**.")

        if impacto:
            st.warning("**Previsualización de cambios e impacto:**\n\n" + "\n".join(impacto))

        confirmar = st.checkbox("Confirmo que entiendo los cambios derivados.")
        col_guardar, col_cancel = st.columns(2)
        guardar = col_guardar.form_submit_button("Guardar cambios")
        cancelar = col_cancel.form_submit_button("Cancelar")

    if cancelar:
        st.rerun()

    if not guardar:
        return

    if impacto and not confirmar:
        return show_alert("Confirmación requerida", "Marca la casilla de confirmación para aplicar los cambios.", "warning")

    # ---------------------------
    # Procesar validaciones (sin DNI)
    # ---------------------------
    cambios = {}

    # Nombre
    if editar_nombre and (nombre_nuevo.strip() != (u.get("nombre_completo") or "").strip()):
        ok, msg = _validar_nombre(nombre_nuevo)
        if not ok:
            return show_alert("Error", msg, "error")
        cambios["nombre_completo"] = nombre_nuevo.strip()

    # Usuario
    if editar_username and (username_nuevo != (u.get("username") or "")):
        ok, msg = _validar_username(username_nuevo)
        if not ok:
            return show_alert("Error", msg, "error")
        dupu = db.execute_query(
            "SELECT COUNT(*) AS c FROM usuarios WHERE username = %s AND user_id != %s",
            (username_nuevo, int(u["user_id"]))
        )
        if dupu and int(dupu[0]["c"]) > 0:
            return show_alert("Error", f"El usuario '{username_nuevo}' ya existe.", "error")
        cambios["username"] = username_nuevo

    # Foto (subida)
    if subir is not None:
        nueva_foto_path = img.save_image(subir, "perfil", str(u["user_id"]))
        if not nueva_foto_path:
            return  
        old = u.get("foto_perfil_id")
        cambios["foto_perfil_id"] = nueva_foto_path

        if old and os.path.exists(old) and "default" not in os.path.basename(old).lower():
            try:
                img.delete_image_by_path(old)
            except Exception:
                pass

    # Contraseña
    if editar_password:
        if not pwd_actual or not pwd_nuevo or not pwd_conf:
            return show_alert("Error", "Completa contraseña actual, nueva y confirmación.", "error")
        if pwd_nuevo != pwd_conf:
            return show_alert("Error", "La confirmación de contraseña no coincide.", "error")
        ok, msg = _validar_password(pwd_nuevo)
        if not ok:
            return show_alert("Error", msg, "error")
        try:
            stored = u.get("password_hash")
            if hasattr(auth, "verify_password"):
                if not auth.verify_password(pwd_actual, stored):
                    return show_alert("Error", "La contraseña actual no es correcta.", "error")
            new_hash = auth.hash_password(pwd_nuevo)
            cambios["password_hash"] = new_hash
        except Exception as e:
            return show_alert("Error", f"No se pudo actualizar la contraseña: {e}", "error")

    if not cambios:
        return show_alert("Sin cambios", "No seleccionaste ningún cambio para guardar.", "info")

    # ---------------------------
    # UPDATE dinámico
    # ---------------------------
    campos = ", ".join([f"{k}=%s" for k in cambios.keys()])
    params = list(cambios.values()) + [int(u["user_id"])]
    try:
        db.execute_query(
            f"UPDATE usuarios SET {campos} WHERE user_id=%s",
            params,
            return_result=False
        )

        if "user" in st.session_state and isinstance(st.session_state["user"], dict):
            st.session_state["user"].update({
                "nombre_completo": cambios.get("nombre_completo", u.get("nombre_completo")),
                "email": cambios.get("email", u.get("email")),
                "username": cambios.get("username", u.get("username")),
                "foto_perfil_id": cambios.get("foto_perfil_id", u.get("foto_perfil_id")),
            })

        # Mensaje de éxito + recordatorios
        extra = []
        if "username" in cambios:
            extra.append("• Recuerda usar tu **nuevo usuario** al iniciar sesión.")
        if "password_hash" in cambios:
            extra.append("• Tu **contraseña** fue actualizada.")

        texto = "Perfil actualizado correctamente."
        if extra:
            texto += "\n\n" + "\n".join(extra)

        show_alert("Éxito", texto, "success")
        st.rerun()

    except Exception as e:
        s = str(e)
        if "1062" in s:
            if "username" in s.lower():
                show_alert("Error", "Ese usuario ya está en uso.", "error")
            elif "email" in s.lower():
                show_alert("Error", "Ese correo ya está en uso.", "error")
            else:
                show_alert("Error", "Conflicto de datos únicos.", "error")
        else:
            show_alert("Error", s, "error")
