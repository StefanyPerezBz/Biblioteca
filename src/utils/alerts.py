# src/utils/alerts.py - Sistema de alertas y notificaciones
import streamlit as st
import time
from datetime import datetime

def show_alert(title, text, icon="success", button="OK", timer=None):
    """
    Muestra una alerta de SweetAlert en Streamlit
    """
    if icon == "success":
        st.success(f"{title}: {text}")
    elif icon == "error":
        st.error(f"{title}: {text}")
    elif icon == "warning":
        st.warning(f"{title}: {text}")
    elif icon == "info":
        st.info(f"{title}: {text}")
    
    if timer:
        time.sleep(timer/1000)  

def verificar_alertas():
    """
    Verifica condiciones que requieren alertas y las muestra/envía
    """
    # Solo ejecutar para administradores y bibliotecarios
    if 'user' not in st.session_state or st.session_state.user['role'] not in ['admin', 'bibliotecario']:
        return
    
    # Importar aquí para evitar circularidad
    from src.database.database import DatabaseManager
    from src.utils.email_manager import EmailManager
    
    db_manager = DatabaseManager()
    email_manager = EmailManager()
    
    # Alertas para préstamos próximos a vencer (en los próximos 2 días)
    prestamos_proximos_vencer = db_manager.execute_query("""
        SELECT p.prestamo_id, l.titulo, u.nombre, u.apellido, u.email,
               p.fecha_devolucion_estimada,
               FLOOR((p.fecha_devolucion_estimada - UNIX_TIMESTAMP()) / 86400) as dias_restantes
        FROM prestamos p
        JOIN libros l ON p.libro_id = l.libro_id
        JOIN usuarios u ON p.usuario_id = u.user_id
        WHERE p.estado = 'activo'
        AND p.fecha_devolucion_estimada BETWEEN UNIX_TIMESTAMP() AND UNIX_TIMESTAMP() + 172800
        ORDER BY p.fecha_devolucion_estimada
    """)
    
    if prestamos_proximos_vencer:
        for prestamo in prestamos_proximos_vencer:
            # Mostrar alerta en la interfaz
            if prestamo['dias_restantes'] <= 1:
                show_alert("Préstamo por vencer", 
                          f"El libro '{prestamo['titulo']}' prestado a {prestamo['nombre']} {prestamo['apellido']} vence hoy.", 
                          "warning")
            else:
                show_alert("Préstamo por vencer", 
                          f"El libro '{prestamo['titulo']}' prestado a {prestamo['nombre']} {prestamo['apellido']} vence en {int(prestamo['dias_restantes'])} días.", 
                          "info")
            
            # Enviar correo de recordatorio (solo una vez al día)
            last_notification = db_manager.execute_query(
                "SELECT MAX(fecha_envio) as ultimo_envio FROM notificaciones WHERE prestamo_id = %s AND tipo = 'recordatorio_vencimiento'",
                (prestamo['prestamo_id'],)
            )
            
            should_send_email = True
            if last_notification and last_notification[0]['ultimo_envio']:
                # Verificar si ya se envió una notificación hoy
                if last_notification[0]['ultimo_envio'].date() == datetime.now().date():
                    should_send_email = False
            
            if should_send_email and prestamo['email']:
                # Enviar correo electrónico
                return_date = datetime.fromtimestamp(prestamo['fecha_devolucion_estimada']).strftime('%d/%m/%Y')
                email_manager.send_reminder_notification(
                    prestamo['email'], 
                    prestamo['titulo'], 
                    int(prestamo['dias_restantes'])
                )
    
    # Alertas para préstamos vencidos
    prestamos_vencidos = db_manager.execute_query("""
        SELECT p.prestamo_id, l.titulo, u.nombre, u.apellido, u.email,
               p.fecha_devolucion_estimada,
               FLOOR((UNIX_TIMESTAMP() - p.fecha_devolucion_estimada) / 86400) as dias_vencido
        FROM prestamos p
        JOIN libros l ON p.libro_id = l.libro_id
        JOIN usuarios u ON p.usuario_id = u.user_id
        WHERE p.estado = 'activo'
        AND p.fecha_devolucion_estimada < UNIX_TIMESTAMP()
        ORDER BY p.fecha_devolucion_estimada
    """)
    
    if prestamos_vencidos:
        for prestamo in prestamos_vencidos:
            show_alert("Préstamo vencido", 
                      f"El libro '{prestamo['titulo']}' prestado a {prestamo['nombre']} {prestamo['apellido']} está vencido hace {int(prestamo['dias_vencido'])} días.", 
                      "error")
    
    # Alertas para reservas próximas a expirar
    reservas_proximas_expirar = db_manager.execute_query("""
        SELECT r.reserva_id, l.titulo, u.nombre, u.apellido, u.email,
               r.fecha_expiracion,
               FLOOR((r.fecha_expiracion - UNIX_TIMESTAMP()) / 3600) as horas_restantes
        FROM reservas r
        JOIN libros l ON r.libro_id = l.libro_id
        JOIN usuarios u ON r.usuario_id = u.user_id
        WHERE r.estado = 'pendiente'
        AND r.fecha_expiracion BETWEEN UNIX_TIMESTAMP() AND UNIX_TIMESTAMP() + 43200
        ORDER BY r.fecha_expiracion
    """)
    
    if reservas_proximas_expirar:
        for reserva in reservas_proximas_expirar:
            show_alert("Reserva por expirar", 
                      f"La reserva del libro '{reserva['titulo']}' por {reserva['nombre']} {reserva['apellido']} expira en {int(reserva['horas_restantes'])} horas.", 
                      "warning")