# src/services/usuarios.py - Gestión de usuarios
import streamlit as st
import pandas as pd
from src.database.database import DatabaseManager
from src.utils.alert_utils import show_sweet_alert
from src.auth.auth import AuthManager
import re
import secrets
import string

def generar_password(longitud=12):
    """
    Genera una contraseña aleatoria segura cumpliendo los requisitos:
    - Al menos una mayúscula
    - Al menos una minúscula
    - Al menos un número
    - Al menos un carácter especial
    """
    caracteres = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    while True:
        password = ''.join(secrets.choice(caracteres) for _ in range(longitud))
        if (any(c.islower() for c in password) and
            any(c.isupper() for c in password) and
            any(c.isdigit() for c in password) and
            any(c in "!@#$%^&*()-_=+" for c in password)):
            return password

def gestion_usuarios(db_manager, show_sweet_alert):
    """
    Gestión de usuarios por parte del administrador.
    Permite visualizar, buscar, validar, cambiar el estado, eliminar y asignar roles a los usuarios.
    """
    st.subheader("Gestión de Usuarios")

    # --- Card de Registro de Usuarios ---
    with st.expander("Registrar Nuevo Bibliotecario", expanded=False):
        st.write("#### Registro de Usuario")

        nombre_completo = st.text_input("Nombre Completo (como figura en DNI)", key="reg_user_nombre")
        usuario = st.text_input("Nombre de Usuario", help="Mínimo 4 caracteres", key="reg_user_user")
        dni = st.text_input("Número de DNI (8 dígitos)", max_chars=8, key="reg_user_dni")
        
        # Selector de rol
        role = st.selectbox(
            "Rol del usuario",
            ["bibliotecario"],
            key="reg_user_role"
        )

        if st.button("Registrar Bibliotecario", key="btn_reg_user"):
            if not nombre_completo or not usuario or not dni:
                show_sweet_alert("Error", "Por favor, complete todos los campos.", "error")
            elif not re.fullmatch(r"^(?=.*[A-Za-z])[A-Za-z0-9_]{4,}$", usuario):
                show_sweet_alert("Error", "El nombre de usuario debe tener al menos 4 caracteres, contener al menos una letra y solo puede incluir letras, números o guiones bajos.", "error")
            elif not len(dni) == 8 or not dni.isdigit():
                show_sweet_alert("Error", "El DNI debe tener exactamente 8 dígitos numéricos.", "error")
            elif not re.match(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+$", nombre_completo):
                show_sweet_alert("Error", "El nombre completo solo puede contener letras y espacios.", "error")
            else:
                # Validar duplicados exactos
                existing_user = db_manager.execute_query(
                    "SELECT * FROM usuarios WHERE LOWER(nombre_completo) = LOWER(%s) OR dni = %s OR username = %s",
                    (nombre_completo, dni, usuario)
                )
                if existing_user:
                    show_sweet_alert("Error", "Ya existe un usuario con el mismo nombre, DNI o nombre de usuario.", "error")
                else:
                    auth_manager = AuthManager()
                    email = f"{dni}@unitru.edu.pe"  # correo generado automáticamente
                    password = generar_password()    # contraseña aleatoria

                    success, message = auth_manager.register_user(
                        username=usuario,
                        password=password,
                        nombre_completo=nombre_completo,
                        role=role,
                        dni=dni,
                        codigo_unt=None, 
                        escuela_id=None,
                        facultad_id=None,
                        email=email,
                        validado=False
                    )

                    if success:
                        show_sweet_alert(
                            "Éxito",
                            f"{message} | 📧 Correo generado: {email} | 🔑 Contraseña: {password}",
                            "success"
                        )
                    else:
                        show_sweet_alert("Error", message, "error")
                        
    # --- Gestión de Usuarios Existentes ---
    # Búsqueda de usuarios
    search_term = st.text_input("🔍 Buscar usuario por nombre, correo o código")

    try:
        if search_term:
            query = """
            SELECT user_id, nombre_completo, email, role, codigo_unt, dni, validado, activo
            FROM usuarios
            WHERE role != 'admin'
            AND (nombre_completo LIKE %s OR email LIKE %s OR codigo_unt LIKE %s)
            ORDER BY nombre_completo
            """
            usuarios_data = db_manager.execute_query(
                query, (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%")
            )
        else:
            query = """
            SELECT user_id, nombre_completo, email, role, codigo_unt, dni, validado, activo
            FROM usuarios
            WHERE role != 'admin'
            ORDER BY nombre_completo
            """
            usuarios_data = db_manager.execute_query(query)

        if usuarios_data:
            df = pd.DataFrame(usuarios_data)

            df = df.rename(columns={
                "user_id": "ID",
                "nombre_completo": "Nombres",
                "email": "Correo",
                "role": "Rol",
                "codigo_unt": "Código",
                "dni": "DNI",
                "validado": "Validado",
                "activo": "Activo"
            })

            df['Validado'] = df['Validado'].map({1: "Sí", 0: "No"})
            df['Activo'] = df['Activo'].map({1: "Sí", 0: "No"})

            df.index = df.index + 1
            df.index.name = "#"

            # Verificar unicidad de correo, código y dni
            duplicados = df[df.duplicated(subset=["Correo", "Código", "DNI"], keep=False)]
            if not duplicados.empty:
                st.warning("⚠️ Se detectaron registros duplicados en **Correo, Código o DNI** (nombres pueden repetirse).")
                st.dataframe(duplicados, use_container_width=True)

            def resaltar_estado(val):
                if isinstance(val, str):
                    color = "background-color: #d4edda; color: #155724;" if val == "Sí" else "background-color: #f8d7da; color: #721c24;"
                    return f"{color} font-weight: bold; border-radius: 5px; text-align: center; padding: 4px;"
                return ""

            styled_df = df.style.applymap(resaltar_estado, subset=["Validado", "Activo"])

            st.dataframe(styled_df, use_container_width=True)
            st.markdown("---")

            # Acciones sobre usuarios
            st.write("### Acciones sobre Usuarios")

            user_options = {
                f"{row['Nombres']} - {row['Correo']} - {row['Rol']}": {
                    'id': row['ID'],
                    'validado': row['Validado'] == 'Sí',
                    'activo': row['Activo'] == 'Sí',
                    'rol': row['Rol']
                }
                for _, row in df.iterrows()
            }

            all_user_keys = list(user_options.keys())

            if not all_user_keys:
                st.info("No hay usuarios disponibles para gestionar.")
                return

            selected_user_key = st.selectbox("Seleccionar usuario", all_user_keys)

            if selected_user_key:
                selected_user_info = user_options.get(selected_user_key)
                if selected_user_info:
                    user_id_to_act = selected_user_info['id']
                    is_validado = selected_user_info['validado']
                    is_activo = selected_user_info['activo']
                    current_role = selected_user_info['rol']

                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.write("#### Gestión de Validación")
                        accion_validar = st.selectbox(
                            "Estado de Validación",
                            ["Validar", "Invalidar"],
                            index=1 if is_validado else 0,
                            key=f"accion_validar_{user_id_to_act}"
                        )

                        if st.button("Aplicar Validación", key=f"apply_validation_{user_id_to_act}"):
                            new_validado_status = (accion_validar == "Validar")
                            db_manager.execute_query(
                                "UPDATE usuarios SET validado = %s WHERE user_id = %s",
                                (new_validado_status, user_id_to_act),
                                return_result=False
                            )
                            show_sweet_alert("Éxito", f"Usuario {'validado' if new_validado_status else 'invalidado'} correctamente.", "success")
                            st.rerun()

                    with col2:
                        st.write("#### Gestión de Activación")
                        accion_activo = st.selectbox(
                            "Estado de Activación",
                            ["Activar", "Desactivar"],
                            index=1 if is_activo else 0,
                            key=f"accion_activo_{user_id_to_act}"
                        )

                        if st.button("Aplicar Activación", key=f"apply_activation_{user_id_to_act}"):
                            new_activo_status = (accion_activo == "Activar")
                            db_manager.execute_query(
                                "UPDATE usuarios SET activo = %s WHERE user_id = %s",
                                (new_activo_status, user_id_to_act),
                                return_result=False
                            )
                            show_sweet_alert("Éxito", f"Estado de usuario {'activado' if new_activo_status else 'desactivado'} correctamente.", "success")
                            st.rerun()
                    
                    with col3:
                        st.write("#### Gestión de Roles")
                        nuevo_rol = st.selectbox(
                            "Rol del usuario",
                            ["estudiante", "docente"],
                            index=0 if current_role == "estudiante" else 1,
                            key=f"rol_select_{user_id_to_act}"
                        )
                        
                        if st.button("Cambiar Rol", key=f"change_role_{user_id_to_act}"):
                            db_manager.execute_query(
                                "UPDATE usuarios SET role = %s WHERE user_id = %s",
                                (nuevo_rol, user_id_to_act),
                                return_result=False
                            )
                            show_sweet_alert("Éxito", f"Rol del usuario cambiado a {nuevo_rol} correctamente.", "success")
                            st.rerun()
                        
                        # Eliminar usuario
                        st.write("#### Eliminar Usuario")
                        delete_key = f"delete_confirm_{user_id_to_act}"
                        
                        if delete_key not in st.session_state:
                            st.session_state[delete_key] = False
                            
                        if not st.session_state[delete_key]:
                            if st.button("Eliminar Usuario", key=f"delete_user_{user_id_to_act}"):
                                st.session_state[delete_key] = True
                                st.rerun()
                        else:
                            st.warning("¿Está seguro de que desea eliminar este usuario? Esta acción no se puede deshacer.")
                            col_confirm, col_cancel = st.columns(2)
                            
                            with col_confirm:
                                if st.button("Confirmar Eliminación", key=f"confirm_delete_{user_id_to_act}"):
                                    db_manager.execute_query(
                                        "DELETE FROM usuarios WHERE user_id = %s",
                                        (user_id_to_act,),
                                        return_result=False
                                    )
                                    if delete_key in st.session_state:
                                        del st.session_state[delete_key]
                                    show_sweet_alert("Éxito", "Usuario eliminado correctamente.", "success")
                                    st.rerun()
                            
                            with col_cancel:
                                if st.button("Cancelar", key=f"cancel_delete_{user_id_to_act}"):
                                    if delete_key in st.session_state:
                                        del st.session_state[delete_key]
                                    st.rerun()
                else:
                    st.warning("❌ No se encontró información para el usuario seleccionado. Recargue la página.")

        else:
            show_sweet_alert("Información", "No hay usuarios registrados en el sistema.", "info")

    except Exception as e:
        show_sweet_alert("Error", f"❌ Error al obtener o gestionar los usuarios: {e}", "error")

def validar_cuentas(db_manager, show_sweet_alert):
    """
    Función para que el bibliotecario valide cuentas de usuarios pendientes.
    """
    st.subheader("Cuentas Pendientes de Validación")

    usuarios_pendientes = db_manager.execute_query(
        "SELECT user_id, nombre_completo, role, email FROM usuarios WHERE validado = FALSE AND activo = TRUE AND role IN ('estudiante','docente')"
    )

    if not usuarios_pendientes:
        st.info("No hay cuentas pendientes por validar.")
        return

    for user in usuarios_pendientes:
        with st.container():
            if not re.match(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+$", user['nombre_completo']):
                st.warning(f"⚠️ El nombre del usuario '{user['nombre_completo']}' contiene caracteres no permitidos.")
                
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"**{user['nombre_completo']}**")
                st.write(f"Rol: {user['role'].capitalize()}")
                st.caption(f"Email: {user['email']}")
            with col2:
                if st.button("Validar", key=f"validate_{user['user_id']}"):
                    db_manager.execute_query(
                        "UPDATE usuarios SET validado = TRUE, fecha_validacion = NOW() WHERE user_id = %s",
                        (user['user_id'],),
                        return_result=False
                    )
                    show_sweet_alert("Cuenta Validada", f"La cuenta de {user['nombre_completo']} ha sido validada.", "success")
                    st.rerun()
            with col3:
                if st.button("Rechazar", key=f"reject_{user['user_id']}"):
                    db_manager.execute_query(
                        "UPDATE usuarios SET activo = FALSE WHERE user_id = %s",
                        (user['user_id'],),
                        return_result=False
                    )
                    show_sweet_alert("Cuenta Rechazada", f"❌ La cuenta de {user['nombre_completo']} ha sido rechazada y desactivada.", "success")
                    st.rerun()
            st.divider()

def gestion_usuarios_bibliotecario(db_manager, show_sweet_alert):
    """
    Gestión de usuarios para bibliotecario:
    - No puede registrar bibliotecarios
    - Acciones solo sobre estudiantes y docentes
    """
    st.subheader("Gestión de Usuarios")

    search_term = st.text_input("🔍 Buscar usuario por nombre, correo o código")

    try:
        if search_term:
            query = """
            SELECT user_id, nombre_completo, email, role, codigo_unt, dni, validado, activo
            FROM usuarios
            WHERE role IN ('estudiante','docente')
            AND (nombre_completo LIKE %s OR email LIKE %s OR codigo_unt LIKE %s)
            ORDER BY nombre_completo
            """
            usuarios_data = db_manager.execute_query(
                query, (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%")
            )
        else:
            query = """
            SELECT user_id, nombre_completo, email, role, codigo_unt, dni, validado, activo
            FROM usuarios
            WHERE role IN ('estudiante','docente')
            ORDER BY nombre_completo
            """
            usuarios_data = db_manager.execute_query(query)

        if usuarios_data:
            df = pd.DataFrame(usuarios_data)
            df = df.rename(columns={
                "user_id": "ID",
                "nombre_completo": "Nombres",
                "email": "Correo",
                "role": "Rol",
                "codigo_unt": "Código",
                "dni": "DNI",
                "validado": "Validado",
                "activo": "Activo"
            })

            df['Validado'] = df['Validado'].map({1: "Sí", 0: "No"})
            df['Activo'] = df['Activo'].map({1: "Sí", 0: "No"})
            df.index = df.index + 1
            df.index.name = "#"

            st.dataframe(df, use_container_width=True)
            st.markdown("---")

            # Acciones solo sobre estudiante/docente
            st.write("### Acciones sobre Usuarios")
            user_options = {
                f"{row['Nombres']} - {row['Correo']} - {row['Rol']}": {
                    'id': row['ID'],
                    'validado': row['Validado'] == 'Sí',
                    'activo': row['Activo'] == 'Sí',
                    'rol': row['Rol']
                }
                for _, row in df.iterrows()
            }

            if not user_options:
                st.info("No hay usuarios disponibles para gestionar.")
                return

            selected_user_key = st.selectbox("Seleccionar usuario", list(user_options.keys()))

            if selected_user_key:
                selected_user_info = user_options[selected_user_key]
                user_id_to_act = selected_user_info['id']
                is_validado = selected_user_info['validado']
                is_activo = selected_user_info['activo']
                current_role = selected_user_info['rol']

                col1, col2, col3 = st.columns(3)

                # Validación
                with col1:
                    st.write("#### Gestión de Validación")
                    accion_validar = st.selectbox(
                        "Estado de Validación",
                        ["Validar", "Invalidar"],
                        index=1 if is_validado else 0,
                        key=f"accion_validar_{user_id_to_act}"
                    )
                    if st.button("Aplicar Validación", key=f"apply_validation_{user_id_to_act}"):
                        db_manager.execute_query(
                            "UPDATE usuarios SET validado = %s WHERE user_id = %s",
                            (accion_validar == "Validar", user_id_to_act),
                            return_result=False
                        )
                        show_sweet_alert("Éxito", f"Usuario {'validado' if accion_validar=='Validar' else 'invalidado'} correctamente.", "success")
                        st.rerun()

                # Activación
                with col2:
                    st.write("#### Gestión de Activación")
                    accion_activo = st.selectbox(
                        "Estado de Activación",
                        ["Activar", "Desactivar"],
                        index=1 if is_activo else 0,
                        key=f"accion_activo_{user_id_to_act}"
                    )
                    if st.button("Aplicar Activación", key=f"apply_activation_{user_id_to_act}"):
                        db_manager.execute_query(
                            "UPDATE usuarios SET activo = %s WHERE user_id = %s",
                            (accion_activo == "Activar", user_id_to_act),
                            return_result=False
                        )
                        show_sweet_alert("Éxito", f"Usuario {'activado' if accion_activo=='Activar' else 'desactivado'} correctamente.", "success")
                        st.rerun()

                # Roles
                with col3:
                    st.write("#### Gestión de Roles")
                    nuevo_rol = st.selectbox(
                        "Rol del usuario",
                        ["estudiante", "docente"],
                        index=0 if current_role == "estudiante" else 1,
                        key=f"rol_select_{user_id_to_act}"
                    )
                    if st.button("Cambiar Rol", key=f"change_role_{user_id_to_act}"):
                        db_manager.execute_query(
                            "UPDATE usuarios SET role = %s WHERE user_id = %s",
                            (nuevo_rol, user_id_to_act),
                            return_result=False
                        )
                        show_sweet_alert("Éxito", f"Rol cambiado a {nuevo_rol}.", "success")
                        st.rerun()

        else:
            st.info("No hay usuarios registrados.")
    except Exception as e:
        show_sweet_alert("Error", f"❌ {e}", "error")
