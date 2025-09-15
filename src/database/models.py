# src/database/models.py - Inicialización de la base de datos UNT
from src.database.database import DatabaseManager
from src.utils.alert_utils import show_sweet_alert
from src.auth.auth import AuthManager
from datetime import datetime
import streamlit as st
from src.database.procedures import create_procedures

def init_database():
    """Inicializa la base de datos con las tablas necesarias para UNT"""
    db_manager = DatabaseManager()
    
    # Para controlar si las tablas se crearon con éxito
    tables_created_successfully = True

    # Crear tablas si no existen
    create_tables_queries = [
        """
        CREATE TABLE IF NOT EXISTS facultades (
            facultad_id INT AUTO_INCREMENT PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL UNIQUE,
            descripcion TEXT,
            activa BOOLEAN DEFAULT TRUE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS escuelas (
            escuela_id INT AUTO_INCREMENT PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL UNIQUE,
            facultad_id INT,
            descripcion TEXT,
            activa BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (facultad_id) REFERENCES facultades(facultad_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS sedes (
            sede_id INT AUTO_INCREMENT PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL UNIQUE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            user_id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            role ENUM('estudiante', 'docente', 'bibliotecario', 'admin') NOT NULL,
            nombre_completo VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE,
            dni VARCHAR(8) UNIQUE,
            codigo_unt VARCHAR(10) UNIQUE,
            escuela_id INT,
            facultad_id INT,
            sede_id INT DEFAULT 1,
            foto_perfil_id VARCHAR(255) DEFAULT 'default_profile.jpg',
            activo BOOLEAN DEFAULT TRUE,
            validado BOOLEAN DEFAULT FALSE,
            sancionado BOOLEAN DEFAULT FALSE,
            fecha_fin_sancion BIGINT,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_validacion BIGINT,
            validado_por INT,
            FOREIGN KEY (escuela_id) REFERENCES escuelas(escuela_id),
            FOREIGN KEY (facultad_id) REFERENCES facultades(facultad_id),
            FOREIGN KEY (sede_id) REFERENCES sedes(sede_id),
            FOREIGN KEY (validado_por) REFERENCES usuarios(user_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS autores (
            autor_id INT AUTO_INCREMENT PRIMARY KEY,
            nombre_completo VARCHAR(255) NOT NULL UNIQUE,
            nacionalidad VARCHAR(100)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS categorias (
            categoria_id INT AUTO_INCREMENT PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL UNIQUE,
            descripcion TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS libros (
            libro_id INT AUTO_INCREMENT PRIMARY KEY,
            titulo VARCHAR(255) NOT NULL,
            autor_id INT,
            anio_publicacion INT,
            editorial VARCHAR(100),
            isbn VARCHAR(20) UNIQUE,
            categoria_id INT,
            ejemplares_totales INT NOT NULL DEFAULT 1,
            ejemplares_disponibles INT NOT NULL DEFAULT 1,
            portada_id VARCHAR(255) DEFAULT 'default_cover.jpg',
            activo BOOLEAN DEFAULT TRUE,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (autor_id) REFERENCES autores(autor_id),
            FOREIGN KEY (categoria_id) REFERENCES categorias(categoria_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS prestamos (
            prestamo_id INT AUTO_INCREMENT PRIMARY KEY,
            libro_id INT NOT NULL,
            usuario_id INT NOT NULL,
            bibliotecario_id INT NOT NULL,
            fecha_prestamo BIGINT NOT NULL,
            fecha_devolucion_estimada BIGINT NOT NULL,
            fecha_devolucion_real BIGINT,
            estado ENUM('activo', 'devuelto', 'atrasado', 'perdido', 'dañado') NOT NULL DEFAULT 'activo',
            observaciones TEXT,
            renovaciones INT DEFAULT 0,
            FOREIGN KEY (libro_id) REFERENCES libros(libro_id),
            FOREIGN KEY (usuario_id) REFERENCES usuarios(user_id),
            FOREIGN KEY (bibliotecario_id) REFERENCES usuarios(user_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS reservas (
            reserva_id INT AUTO_INCREMENT PRIMARY KEY,
            libro_id INT NOT NULL,
            usuario_id INT NOT NULL,
            fecha_reserva BIGINT NOT NULL,
            fecha_expiracion BIGINT NOT NULL,
            estado ENUM('pendiente', 'completada', 'cancelada', 'expirada') NOT NULL DEFAULT 'pendiente',
            FOREIGN KEY (libro_id) REFERENCES libros(libro_id),
            FOREIGN KEY (usuario_id) REFERENCES usuarios(user_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS sanciones (
            sancion_id INT AUTO_INCREMENT PRIMARY KEY,
            usuario_id INT NOT NULL,
            prestamo_id INT,
            fecha_inicio BIGINT NOT NULL,
            fecha_fin BIGINT NOT NULL,
            motivo TEXT NOT NULL,
            monto DECIMAL(10, 2) DEFAULT 0.00,
            estado ENUM('activa', 'pagada', 'condonada') NOT NULL DEFAULT 'activa',
            FOREIGN KEY (usuario_id) REFERENCES usuarios(user_id),
            FOREIGN KEY (prestamo_id) REFERENCES prestamos(prestamo_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS configuracion (
            parametro VARCHAR(50) PRIMARY KEY,
            valor VARCHAR(255) NOT NULL,
            descripcion TEXT,
            editable BOOLEAN DEFAULT TRUE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS notificaciones (
        notif_id INT AUTO_INCREMENT PRIMARY KEY,
        usuario_id INT NULL,
        tipo ENUM('email','sms','push') NOT NULL DEFAULT 'email',
        asunto VARCHAR(255) NULL,
        mensaje TEXT NOT NULL,
        estado ENUM('pendiente','enviado','error') NOT NULL DEFAULT 'enviado',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(user_id)
        )
        """
    ]

    for query in create_tables_queries:
        if db_manager.execute_query(query, return_result=False) is None:
            tables_created_successfully = False
            show_sweet_alert("Error de Conexión", db_manager.get_last_error(), "error")
            break

    if tables_created_successfully:
        try:            
            # Insertar sedes
            sedes = ["VALLE JEQUETEPEQUE"]
            for sede in sedes:
                check_sede = db_manager.execute_query("SELECT COUNT(*) as count FROM sedes WHERE nombre = %s", (sede,))
                if check_sede and check_sede[0]['count'] == 0:
                    db_manager.execute_query("INSERT INTO sedes (nombre) VALUES (%s)", (sede,), return_result=False)

            # Insertar facultades
            facultades = ["Facultad de Ingeniería", "Facultad de Ciencias Económicas", "Facultad de Enfermería", "Facultad de Ciencias Sociales", "Facultad de Ciencias Agropecuarias"]
            for facultad in facultades:
                check_fac = db_manager.execute_query("SELECT COUNT(*) as count FROM facultades WHERE nombre = %s", (facultad,))
                if check_fac and check_fac[0]['count'] == 0:
                    db_manager.execute_query("INSERT INTO facultades (nombre) VALUES (%s)", (facultad,), return_result=False)

            # Insertar escuelas
            escuelas = [
                ("Ingeniería de Sistemas", "Facultad de Ingeniería"),
                ("Ingeniería Informática", "Facultad de Ingeniería"),
                ("Ingeniería Industrial", "Facultad de Ingeniería"),
                ("Ingeniería Mecánica", "Facultad de Ingeniería"),
                ("Administración", "Facultad de Ciencias Económicas"),
                ("Contabilidad y Finanzas", "Facultad de Ciencias Económicas"),
                ("Enfermería", "Facultad de Enfermería"),
                ("Agronomía", "Facultad de Ciencias Agropecuarias"),
                ("Ingeniería Agroindustrial", "Facultad de Ciencias Agropecuarias"),
                ("Trabajo Social", "Facultad de Ciencias Sociales")

            ]
            for escuela, facultad_nombre in escuelas:
                check_escuela = db_manager.execute_query("SELECT COUNT(*) as count FROM escuelas WHERE nombre = %s", (escuela,))
                if check_escuela and check_escuela[0]['count'] == 0:
                    facultad = db_manager.execute_query("SELECT facultad_id FROM facultades WHERE nombre = %s", (facultad_nombre,))
                    if facultad:
                        facultad_id = facultad[0]['facultad_id']
                        db_manager.execute_query("INSERT INTO escuelas (nombre, facultad_id) VALUES (%s, %s)", (escuela, facultad_id), return_result=False)

            # Insertar autores predeterminados
            autores_base = [
                ("Gabriel García Márquez", "Colombiano"),
                ("Mario Vargas Llosa", "Peruano"),
                ("Julio Cortázar", "Argentino")
            ]
            for nombre, nacionalidad in autores_base:
                check_autor = db_manager.execute_query("SELECT COUNT(*) as count FROM autores WHERE nombre_completo = %s", (nombre,))
                if check_autor and check_autor[0]['count'] == 0:
                    db_manager.execute_query("INSERT INTO autores (nombre_completo, nacionalidad) VALUES (%s, %s)", (nombre, nacionalidad), return_result=False)

            # Insertar categorías
            categorias = ["Ficción", "No Ficción", "Ciencia y Tecnología", "Historia", "Literatura", "Ingeniería", "Ingeniería y Arquitectura", "Medicina y Salud", "Ciencias Sociales", "Literatura y Artes", "Historia y Geografía", "Economía y Administración", "Educación", "Derecho y Ciencias Políticas"]
            for categoria in categorias:
                check_cat = db_manager.execute_query("SELECT COUNT(*) as count FROM categorias WHERE nombre = %s", (categoria,))
                if check_cat and check_cat[0]['count'] == 0:
                    db_manager.execute_query("INSERT INTO categorias (nombre) VALUES (%s)", (categoria,), return_result=False)

            # Insertar parámetros de configuración predeterminados
            check_config = db_manager.execute_query("SELECT COUNT(*) as count FROM configuracion")
            if check_config and check_config[0]['count'] == 0:
                config_params = [
                    ("dias_prestamo_estudiante", "15", "Días de préstamo para estudiantes", True),
                    ("dias_prestamo_docente", "30", "Días de préstamo para docentes", True),
                    ("max_prestamos_estudiante", "3", "Máximo de préstamos activos para estudiantes", True),
                    ("max_prestamos_docente", "5", "Máximo de préstamos activos para docentes", True),
                    ("dias_reserva_expiracion", "2", "Días antes de que una reserva expire", True),
                    ("dias_renovacion_estudiante", "15", "Días de renovación para estudiantes", True),
                    ("dias_renovacion_docente", "30", "Días de renovación para docentes", True),
                    ("costo_multa_diaria", "2.00", "Costo por cada día de atraso", True),
                    ("max_renovaciones", "1", "Máximo de renovaciones permitidas", True),
                    ("costo_danio_perdida", "100.00", "Costo de sanción por libro dañado o perdido", True),
                    ("dias_sancion_atraso", "3", "Días de sanción por cada día de atraso", True),
                    ("url_repositorio_UNT", "https://dspace.unitru.edu.pe/", "URL del repositorio institucional UNT", False),
                    ("nombre_biblioteca", "Biblioteca UNT", "Nombre de la biblioteca por defecto", False),
                    ("dias_sancion_danio_perdida", "7", "Días de sanción por libro dañado o perdido", True),
                ]
                
                for param, valor, desc, editable in config_params:
                    db_manager.execute_query(
                        "INSERT INTO configuracion (parametro, valor, descripcion, editable) VALUES (%s, %s, %s, %s)",
                        (param, valor, desc, editable),
                        return_result=False
                    )
            
            # Insertar usuario administrador si no existe
            check_admin = db_manager.execute_query("SELECT COUNT(*) as count FROM usuarios WHERE role = 'admin'")
            if check_admin and check_admin[0]['count'] == 0:
                auth_manager = AuthManager()
                hashed_password = auth_manager.hash_password("admin123")
                
                # Obtener sede Jequetepeque
                sede_jequetepeque = db_manager.execute_query("SELECT sede_id FROM sedes WHERE nombre = 'VALLE JEQUETEPEQUE'")
                sede_id = sede_jequetepeque[0]['sede_id'] if sede_jequetepeque else 1
                
                result = db_manager.execute_query(
                    """INSERT INTO usuarios 
                    (username, password_hash, role, nombre_completo, email, validado, activo, sede_id) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    ("admin", hashed_password, "admin", "Administrador Principal", "admin@unitru.edu.pe", True, True, sede_id),
                    return_result=False
                )
                
                if result is None:
                    show_sweet_alert("Error", "No se pudo crear el usuario administrador. La base de datos no está lista. Vuelva a intentar.", "error")
        except Exception as e:
            st.error(f"Ocurrió un error al insertar datos predeterminados: {e}")
            show_sweet_alert("Error de Inicialización", "Ocurrió un error al poblar la base de datos con datos predeterminados.", "error")

create_procedures()