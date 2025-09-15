# main.py - Principal de la aplicación UNT
import streamlit as st
from src.database.database import DatabaseManager
from src.auth.auth import AuthManager
from src.utils.image_manager import ImageManager
from src.utils.email_manager import EmailManager
from src.dashboards.admin import admin_dashboard
from src.dashboards.bibliotecario import bibliotecario_dashboard
from src.dashboards.usuario import usuario_dashboard
from src.database.models import init_database
from src.utils.alerts import verificar_alertas
from src.utils.alert_utils import show_sweet_alert
import time
import re

# Configuración de la página
st.set_page_config(
    page_title="Sistema Gestión de Biblioteca UNT",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializar managers globales
db_manager = DatabaseManager()
image_manager = ImageManager()
email_manager = EmailManager()

# --- Funciones de soporte ---
def get_facultades_options():
    """Obtiene lista de facultades para filtros"""
    db_manager = DatabaseManager()
    facultades = db_manager.execute_query("SELECT facultad_id, nombre FROM facultades WHERE activa = TRUE ORDER BY nombre")
    return {f['nombre']: f['facultad_id'] for f in facultades} if facultades else {}

def get_escuelas_options():
    """Obtiene lista de escuelas para filtros"""
    db_manager = DatabaseManager()
    escuelas = db_manager.execute_query("SELECT escuela_id, nombre FROM escuelas WHERE activa = TRUE ORDER BY nombre")
    return {e['nombre']: e['escuela_id'] for e in escuelas} if escuelas else {}

# --- Funciones de vista ---
def mostrar_login():
    """Muestra el formulario de inicio de sesión y registro"""
    
    # --- CONTENIDO DE BIENVENIDA CENTRADO Y EN UN CARD ---
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("<h1 style='text-align: center;'>Sistema de Gestión de Biblioteca</h1>", unsafe_allow_html=True)
            st.markdown("<h3 style='text-align: center;'>Bienvenido a la plataforma de la Biblioteca Central de la Universidad Nacional de Trujillo.</h3>", unsafe_allow_html=True)

    with st.expander("Información de Acceso", expanded=True):
        st.write(
            """
            Para acceder, inicia sesión con tu usuario y contraseña. Si aún no tienes una cuenta, regístrate a través de la pestaña correspondiente.
            
            **Validación de cuentas:** Las cuentas de estudiantes y docentes deben ser validadas por el administrador o bibliotecario del sistema.
            """
        )

    # --- Funciones de soporte ---
    MAX_LOGIN_ATTEMPTS = 5

    if "login_attempts" not in st.session_state:
       st.session_state.login_attempts = 0

    login_form, register_form = st.tabs(["Iniciar Sesión", "Registrarse"])

    with login_form:
        st.subheader("Inicio de Sesión")
        username = st.text_input("Usuario, correo o código", key="login_username")
        password = st.text_input("Contraseña", type="password", key="login_password")
        
        if st.button("Ingresar"):
            if st.session_state.login_attempts >= MAX_LOGIN_ATTEMPTS:
                show_sweet_alert("Error", f"Has excedido el máximo de {MAX_LOGIN_ATTEMPTS} intentos. Intenta más tarde.", "error")
            elif not username or not password:
                show_sweet_alert("Error", "Por favor, complete todos los campos.", "error")
            else:
                auth_manager = AuthManager()
                # success, user = auth_manager.login_user(username, password)
                token, user = auth_manager.login_user(username, password)
                if token and user:
                    # Nuevo chequeo de estado de usuario
                    if not user.get('validado'):
                        show_sweet_alert("Error", "Tu cuenta aún no ha sido validada. Por favor, contacta con el responsable para activarla.", "error")
                    elif not user.get('activo'):
                        show_sweet_alert("Error", "Tu cuenta ha sido desactivada. Por favor, contacta con el responsable para más información.", "error")
                    else:
                        st.session_state.token = token 
                        st.session_state.user = user
                        st.session_state.logged_in = True
                        st.session_state.login_attempts = 0  # Reinicia intentos
                        st.rerun()
                else:
                    st.session_state.login_attempts += 1
                    show_sweet_alert("Error", f"Usuario o contraseña incorrectos. Intentos restantes: {MAX_LOGIN_ATTEMPTS - st.session_state.login_attempts}", "error")

    with register_form:
        st.subheader("Formulario de Registro")
        st.write("Seleccione el tipo de cuenta que desea crear:")
        account_type = st.radio("Tipo de Cuenta", ["Estudiante", "Docente"], horizontal=True)

        if account_type == "Estudiante":
            st.write("#### Registro de Estudiante")
            nombre_completo = st.text_input("Nombre Completo (como figura en DNI/Carnet)", key="reg_est_nombre")
            usuario = st.text_input("Nombre de Usuario", help="Mínimo 4 caracteres", key="reg_est_user")
            password = st.text_input("Contraseña", type="password", help="Mínimo 8 caracteres, con mayúscula, minúscula, número y carácter especial", key="reg_est_pass")
            dni = st.text_input("Número de DNI (8 dígitos)", max_chars=8, key="reg_est_dni")
            codigo_unt = st.text_input("Código UNT", help="Mínimo 6 caracteres", key="reg_est_codigo")
            
            facultades_options = get_facultades_options()
            facultad_seleccionada_nombre = st.selectbox("Facultad", list(facultades_options.keys()))
            
            escuelas_options = get_escuelas_options()
            escuela_seleccionada_nombre = st.selectbox("Escuela", list(escuelas_options.keys()))

            if st.button("Registrar como Estudiante"):
                # Validaciones de campos
                if not nombre_completo or not usuario or not password or not dni or not codigo_unt:
                    show_sweet_alert("Error", "Por favor, complete todos los campos.", "error")
                elif not re.match(r"^[A-Za-z0-9_]+$", usuario):
                    show_sweet_alert("Error", "El nombre de usuario solo puede contener letras, números y guiones bajos.", "error")
                elif len(usuario) < 4:
                    show_sweet_alert("Error", "El nombre de usuario debe tener al menos 4 caracteres.", "error")
                elif not (len(password) >= 8 and re.search("[a-z]", password) and re.search("[A-Z]", password) and re.search("[0-9]", password) and re.search("[^a-zA-Z0-9]", password)):
                    show_sweet_alert("Error", "La contraseña debe tener al menos 8 caracteres, incluyendo una mayúscula, una minúscula, un número y un carácter especial.", "error")
                elif not len(dni) == 8 or not dni.isdigit():
                    show_sweet_alert("Error", "El DNI debe tener 8 dígitos y numérico.", "error")
                elif not len(codigo_unt) >= 6 or not codigo_unt.isdigit():
                    show_sweet_alert("Error", "El código UNT debe tener al menos 6 dígitos numéricos.", "error")
                elif not re.match(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+$", nombre_completo):
                    show_sweet_alert("Error", "El nombre completo solo puede contener letras y espacios, sin números ni caracteres especiales.", "error")
                else:
                    # Validación de duplicados: nombre, username, dni, codigo_unt
                    existing_user = db_manager.execute_query(
                        "SELECT * FROM usuarios WHERE LOWER(nombre_completo) = LOWER(%s) OR LOWER(username) = LOWER(%s) OR dni = %s OR codigo_unt = %s",
                        (nombre_completo, usuario, dni, codigo_unt)
                    )
                    if existing_user:
                        show_sweet_alert("Error", "Ya existe un usuario con el mismo nombre, usuario, DNI o código UNT.", "error")
                    else:
                        auth_manager = AuthManager()
                        escuela_id = escuelas_options.get(escuela_seleccionada_nombre)
                        facultad_id = facultades_options.get(facultad_seleccionada_nombre)
                        email = f"{codigo_unt}@unitru.edu.pe" # Email generado automáticamente
                        
                        success, message = auth_manager.register_user(
                            username=usuario,
                            password=password,
                            nombre_completo=nombre_completo,
                            role='estudiante',
                            dni=dni,
                            codigo_unt=codigo_unt,
                            escuela_id=escuela_id,
                            facultad_id=facultad_id,
                            email=email,
                            validado=False
                        )

                        if success:
                            show_sweet_alert("Éxito", message, "success")
                        else:
                            show_sweet_alert("Error", message, "error")

        elif account_type == "Docente":
            st.write("#### Registro de Docente")
            nombre_completo = st.text_input("Nombre Completo (como figura en DNI/Carnet)", key="reg_doc_nombre")
            usuario = st.text_input("Nombre de Usuario", help="Mínimo 4 caracteres", key="reg_doc_user")
            password = st.text_input("Contraseña", type="password", help="Mínimo 8 caracteres, con mayúscula, minúscula, número y carácter especial", key="reg_doc_pass")
            dni = st.text_input("Número de DNI (8 dígitos)", max_chars=8, key="reg_doc_dni")
            email = st.text_input("Correo Electrónico UNT", key="reg_doc_email")

            facultades_options = get_facultades_options()
            facultad_seleccionada_nombre = st.selectbox("Facultad", list(facultades_options.keys()))
            
            escuelas_options = get_escuelas_options()
            escuela_seleccionada_nombre = st.selectbox("Escuela", list(escuelas_options.keys()))
            
            if st.button("Registrar como Docente"):
                # Validaciones de campos
                if not nombre_completo or not usuario or not password or not dni or not email:
                    show_sweet_alert("Error", "Por favor, complete todos los campos.", "error")
                elif not re.match(r"^[A-Za-z0-9_]+$", usuario):
                    show_sweet_alert("Error", "El nombre de usuario solo puede contener letras, números y guiones bajos.", "error")
                elif len(usuario) < 4:
                    show_sweet_alert("Error", "El nombre de usuario debe tener al menos 4 caracteres.", "error")
                elif not (len(password) >= 8 and re.search("[a-z]", password) and re.search("[A-Z]", password) and re.search("[0-9]", password) and re.search("[^a-zA-Z0-9]", password)):
                    show_sweet_alert("Error", "La contraseña debe tener al menos 8 caracteres, incluyendo una mayúscula, una minúscula, un número y un carácter especial.", "error")
                elif not len(dni) == 8 or not dni.isdigit():
                    show_sweet_alert("Error", "El DNI debe tener 8 dígitos numéricos.", "error")
                elif not re.match(r"^[^@]+@unitru\.edu\.pe$", email):
                    show_sweet_alert("Error", "El correo electrónico debe terminar en @unitru.edu.pe.", "error")
                elif not re.match(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+$", nombre_completo):
                    show_sweet_alert("Error", "El nombre completo solo puede contener letras y espacios, sin números ni caracteres especiales.", "error")
                else:
                    # Validación de nombre completo duplicado
                    existing_user = db_manager.execute_query(
                        "SELECT * FROM usuarios WHERE LOWER(nombre_completo) = LOWER(%s) OR LOWER(username) = LOWER(%s) OR dni = %s OR LOWER(email) = LOWER(%s)" ,
                        (nombre_completo, usuario, dni, email)
                    )
                    if existing_user:
                        show_sweet_alert("Error", "Ya existe un usuario con el mismo nombre, correo,usuario o DNI.", "error")
                    else:
                        auth_manager = AuthManager()
                        escuela_id = escuelas_options.get(escuela_seleccionada_nombre)
                        facultad_id = facultades_options.get(facultad_seleccionada_nombre)
                        
                        success, message = auth_manager.register_user(
                            username=usuario,
                            password=password,
                            nombre_completo=nombre_completo,
                            role='docente',
                            dni=dni,
                            codigo_unt=None, 
                            escuela_id=escuela_id,
                            facultad_id=facultad_id,
                            email=email,
                            validado=False
                        )

                        if success:
                            show_sweet_alert("Éxito", message, "success")
                        else:
                            show_sweet_alert("Error", message, "error")

# Lógica principal de la aplicación
if "token" not in st.session_state:
    init_database()
    mostrar_login()
else:
    # Lógica de enrutamiento basada en el rol del usuario
    user = st.session_state.user
    if user['role'] == 'admin':
        admin_dashboard(user)
    elif user['role'] == 'bibliotecario':
        bibliotecario_dashboard(user)
    else: # estudiante o docente
        usuario_dashboard(user)
