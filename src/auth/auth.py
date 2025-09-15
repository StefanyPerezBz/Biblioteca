# src/auth/auth.py - Gestión de autenticación JWT 
import jwt
import hashlib
import streamlit as st
import re
import time
from typing import Iterable, Optional
from datetime import datetime, timedelta
from src.database.database import DatabaseManager
from src.utils.alert_utils import show_sweet_alert

class AuthManager:
    def __init__(self):
        self.secret_key = st.secrets["JWT_SECRET"]
        self.db_manager = DatabaseManager()

    def generate_token(self, user_id, username, role):
        payload = {
            'user_id': user_id,
            'username': username,
            'role': role,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        token = jwt.encode(payload, self.secret_key, algorithm='HS256')
        return token

    def verify_token(self, token):
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            show_sweet_alert("Sesión expirada", "❌ Por favor, inicie sesión nuevamente.", "warning")
            return None
        except jwt.InvalidTokenError:
            show_sweet_alert("Token inválido", "❌ Por favor, inicie sesión nuevamente.", "error")
            return None

    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()
    
    def login_user(self, usuario, password):
        hashed_password = self.hash_password(password)
        query = """
            SELECT u.user_id, u.username, u.role,
                   u.nombre_completo, u.email,
                   u.dni, u.codigo_unt, u.escuela_id, u.facultad_id, u.sede_id,
                   u.foto_perfil_id, u.activo, u.validado,
                   u.sancionado, u.fecha_fin_sancion,
                   e.nombre as escuela, f.nombre as facultad, s.nombre as sede
            FROM usuarios u
            LEFT JOIN escuelas e ON u.escuela_id = e.escuela_id
            LEFT JOIN facultades f ON u.facultad_id = f.facultad_id
            LEFT JOIN sedes s ON u.sede_id = s.sede_id
            WHERE (u.username = %s OR u.email = %s OR u.codigo_unt = %s) AND u.password_hash = %s AND u.activo = TRUE
        """
        result = self.db_manager.execute_query(query, (usuario, usuario, usuario, hashed_password))
        
        if result:
            user = result[0]
            token = self.generate_token(user['user_id'], user['username'], user['role'])
            return token, user
        else:
            return None, None

    def _generar_email_estudiante(self, codigo_matricula):
        """Genera el email automático para estudiantes según el formato UNT."""
        if not codigo_matricula or len(codigo_matricula) < 2:
            return None
        parte_email = codigo_matricula[1:] # Eliminar el primer dígito
        return f"g{parte_email}@unitru.edu.pe"

    def register_user(self, username, password, nombre_completo, role, dni, codigo_unt=None, email=None, escuela_id=None, facultad_id=None, sede_id=1, validado=False):
        """Registra un nuevo usuario en la base de datos."""
        
        if self.db_manager.execute_query("SELECT dni FROM usuarios WHERE dni = %s", (dni,)):
            return False, "El DNI ingresado ya está registrado."
        
        if self.db_manager.execute_query("SELECT username FROM usuarios WHERE username = %s", (username,)):
            return False, "El usuario ya está en uso."
        
        if role == 'estudiante':
            if not codigo_unt:
                return False, "El código de matrícula es obligatorio para estudiantes."
            if self.db_manager.execute_query("SELECT codigo_unt FROM usuarios WHERE codigo_unt = %s", (codigo_unt,)):
                return False, "El código de matrícula ya está registrado."
            
            # Generar email automático para estudiante
            email = self._generar_email_estudiante(codigo_unt)
            if self.db_manager.execute_query("SELECT email FROM usuarios WHERE email = %s", (email,)):
                return False, f"El correo electrónico ({email}) ya existe. Por favor, contacte a soporte."
        
        # Validar el correo si se proporciona
        if email and self.db_manager.execute_query("SELECT email FROM usuarios WHERE email = %s", (email,)):
            return False, f"El email ({email}) ya existe."
        elif email and not re.match(r"^[a-zA-Z0-9._%+-]+@unitru\.edu\.pe$", email):
            return False, "Por favor, ingrese un correo electrónico válido que termine en @unitru.edu.pe."

        hashed_password = self.hash_password(password)
        
        query = """
            INSERT INTO usuarios 
            (username, password_hash, role, nombre_completo, dni, codigo_unt, email, escuela_id, facultad_id, sede_id, validado, activo) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            username, hashed_password, role, nombre_completo, dni,
            codigo_unt, email, escuela_id, facultad_id, sede_id,
            validado, True
        )
        
        result = self.db_manager.execute_query(query, params, return_result=False)
        
        if result:
            return True, "Usuario registrado correctamente. Su cuenta debe ser validada por un bibliotecario antes de poder acceder al sistema."
        else:
            return False, "Error al registrar el usuario. Por favor, inténtelo de nuevo."

    def validate_user_account(self, user_id, validated_by):
        """Valida una cuenta de usuario pendiente"""
        result = self.db_manager.execute_query(
            "UPDATE usuarios SET validado = TRUE, fecha_validacion = UNIX_TIMESTAMP(), validado_por = %s WHERE user_id = %s",
            (validated_by, user_id),
            return_result=False
        )
        
        if result:
            user_info = self.db_manager.execute_query(
                "SELECT nombre_completo, email FROM usuarios WHERE user_id = %s",
                (user_id,)
            )
            
            if user_info:
                pass
            
            return True, "Cuenta validada correctamente"
        
        return False, "Error al validar la cuenta"

# --- Helpers de sesión y guardas JWT ---

def _clear_session_and_reload(msg: str):
    # Limpia sesión y recarga UI
    for k in ("logged_in", "user", "token"):
        if k in st.session_state:
            del st.session_state[k]
    try:
        show_sweet_alert("Sesión finalizada", msg, "warning")
    except Exception:
        pass
    st.rerun()

class JWTGuard:
    def __init__(self, secret: str):
        self.secret = secret
        self.alg = "HS256"

    def verify(self, token: str) -> dict:
        return jwt.decode(token, self.secret, algorithms=[self.alg])

    def maybe_refresh(self, payload: dict) -> Optional[str]:
        # Renueva si faltan < 15 min para expirar
        now = int(time.time())
        exp = int(payload.get("exp", 0))
        if exp - now <= 15 * 60:
            am = AuthManager()
            return am.generate_token(payload["user_id"], payload["username"], payload["role"])
        return None

def require_auth(required_roles: Optional[Iterable[str]] = None) -> dict:
    """
    Verifica JWT en st.session_state['token'] y rol (si se indica).
    Si expira o es inválida, limpia sesión y recarga.
    Devuelve el payload válido.
    """
    token = st.session_state.get("token")
    if not token:
        _clear_session_and_reload("Debes iniciar sesión nuevamente.")
        st.stop()

    guard = JWTGuard(st.secrets["JWT_SECRET"])
    try:
        payload = guard.verify(token)
    except jwt.ExpiredSignatureError:
        _clear_session_and_reload("Tu sesión expiró. Vuelve a iniciar sesión.")
        st.stop()
    except jwt.InvalidTokenError:
        _clear_session_and_reload("Token inválido. Vuelve a iniciar sesión.")
        st.stop()

    # Chequeo de rol (opcional)
    if required_roles:
        role = str(payload.get("role", "")).lower()
        req = {r.lower() for r in required_roles}
        if role not in req:
            try:
                show_sweet_alert("Acceso denegado", "No tienes permisos para acceder aquí.", "error")
            except Exception:
                pass
            st.stop()

    # Renovación silenciosa si está por vencer
    new_token = guard.maybe_refresh(payload)
    if new_token:
        st.session_state["token"] = new_token

    return payload

def logout():
    """Cierra sesión de forma coherente en toda la app."""
    for k in ("logged_in", "user", "token"):
        if k in st.session_state:
            del st.session_state[k]
    try:
        show_sweet_alert("Sesión cerrada", "Has cerrado sesión correctamente.", "success")
    except Exception:
        pass
    st.rerun()
