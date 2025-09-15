# src/utils/email_manager.py 
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Optional, List, Dict

import streamlit as st

# UI alert
try:
    from src.utils.alert_utils import show_sweet_alert as _ui_alert
except Exception:
    def _ui_alert(title, text, icon="info"):
        st.info(f"{title}: {text}")

# Jinja2 
try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    JINJA_OK = True
except Exception:
    JINJA_OK = False


class EmailManager:
    def __init__(self):
        # SMTP 
        self.smtp_server = str(st.secrets.get("SMTP_SERVER", "sandbox.smtp.mailtrap.io"))
        self.smtp_port = int(st.secrets.get("SMTP_PORT", 2525))
        self.smtp_username = str(st.secrets.get("SMTP_USERNAME", ""))
        self.smtp_password = str(st.secrets.get("SMTP_PASSWORD", ""))
        self.use_tls = bool(st.secrets.get("SMTP_USE_TLS", True))
        self.from_name = str(st.secrets.get("SMTP_FROM_NAME", "Biblioteca UNT"))
        self.from_email = str(st.secrets.get("SMTP_FROM_EMAIL", self.smtp_username or "no-reply@biblioteca.edu"))

        # Datos de BD 
        self.db_name = str(st.secrets.get("DB_NAME", "biblioteca_db"))

        # Templates
        self.templates_dir = Path(__file__).resolve().parents[2] / "templates" / "emails"
        self.env = None
        if JINJA_OK and self.templates_dir.exists():
            self.env = Environment(
                loader=FileSystemLoader(str(self.templates_dir)),
                autoescape=select_autoescape(["html", "xml"])
            )

    # ---------- Templates ----------
    def _render_template(self, name: str, context: Dict) -> Optional[str]:
        if self.env:
            try:
                tpl = self.env.get_template(name)
                return tpl.render(**context)
            except Exception:
                return None
        return None

    def _basic_wrapper(self, subject: str, inner_html: str) -> str:
        return f"""
        <!doctype html>
        <html><head><meta charset="utf-8"><title>{subject}</title></head>
        <body style="font-family:Segoe UI,Tahoma,Arial,sans-serif;background:#f9f9f9;margin:0;padding:24px">
          <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:8px;padding:24px;border:1px solid #eee">
            <h2 style="margin-top:0">{subject}</h2>
            {inner_html}
            <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
            <p style="color:#888;font-size:13px">© Biblioteca UNT</p>
          </div>
        </body></html>
        """

    # ---------- Logger seguro ----------
    def _table_exists(self, db, table: str) -> bool:
        try:
            q = "SELECT 1 FROM information_schema.tables WHERE table_schema=%s AND table_name=%s LIMIT 1"
            res = db.execute_query(q, (self.db_name, table))
            return bool(res)
        except Exception:
            return False

    def _log_notification(self, subject: str, to_email: str, estado: str = "enviado") -> None:
        # Evita mostrar el error si no existe la tabla
        try:
            from src.database.database import DatabaseManager
            db = DatabaseManager()
            if not self._table_exists(db, "notificaciones"):
                return
            db.execute_query(
                "INSERT INTO notificaciones (usuario_id, tipo, asunto, mensaje, estado) "
                "VALUES ((SELECT user_id FROM usuarios WHERE email=%s), %s, %s, %s, %s)",
                (to_email, "email", subject, f"Email enviado: {subject}", estado),
                return_result=False
            )
        except Exception:
            pass

    # ---------- Envío base ----------
    def send_email(self, to_email: str, subject: str, html: Optional[str] = None, text: Optional[str] = None) -> bool:
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email
            msg["Subject"] = subject

            if text:
                msg.attach(MIMEText(text, "plain", "utf-8"))
            if html:
                msg.attach(MIMEText(html, "html", "utf-8"))

            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls(context=context)
                server.login(self.smtp_username, self.smtp_password)
                server.sendmail(self.from_email, [to_email], msg.as_string())

            self._log_notification(subject, to_email, "enviado")
            return True

        except Exception as e:
            self._log_notification(subject, to_email, "error")
            _ui_alert("Error al enviar correo", str(e), "error")
            return False

    # ---------- Dominios ----------
    def send_prestamo_confirmacion(self, user_email: str, usuario_nombre: str,
                                   libro_titulo: str, fecha_prestamo: str, fecha_devolucion: str) -> bool:
        subject = f"Confirmación de Préstamo — {libro_titulo}"
        html = self._render_template("prestamo_confirmacion.html", {
            "subject": subject,
            "usuario_nombre": usuario_nombre,
            "libro_titulo": libro_titulo,
            "fecha_prestamo": fecha_prestamo,
            "fecha_devolucion": fecha_devolucion
        })
        if not html:
            inner = (f"<p>Estimado/a {usuario_nombre},</p>"
                     f"<p>Se registró el préstamo del libro <b>“{libro_titulo}”</b>.</p>"
                     f"<p><b>Fecha de préstamo:</b> {fecha_prestamo}<br>"
                     f"<b>Fecha estimada de devolución:</b> {fecha_devolucion}</p>")
            html = self._basic_wrapper(subject, inner)
        return self.send_email(user_email, subject, html=html)

    def send_recordatorio(self, user_email: str, usuario_nombre: str,
                          libro_titulo: str, fecha_devolucion: str, dias_restantes: int) -> bool:
        subject = f"Recordatorio de Devolución — {libro_titulo}"
        html = self._render_template("recordatorio.html", {
            "subject": subject,
            "usuario_nombre": usuario_nombre,
            "libro_titulo": libro_titulo,
            "fecha_devolucion": fecha_devolucion,
            "dias_restantes": dias_restantes
        })
        if not html:
            inner = (f"<p>Hola {usuario_nombre},</p>"
                     f"<p>El préstamo de <b>“{libro_titulo}”</b> vence el <b>{fecha_devolucion}</b> "
                     f"(en {dias_restantes} día(s)).</p>")
            html = self._basic_wrapper(subject, inner)
        return self.send_email(user_email, subject, html=html)

    def send_atraso(self, user_email: str, usuario_nombre: str,
                    libro_titulo: str, fecha_prevista: str, dias_atraso: int) -> bool:
        subject = f"⚠️ Atraso de Devolución — {libro_titulo}"
        html = self._render_template("atraso.html", {
            "subject": subject,
            "usuario_nombre": usuario_nombre,
            "libro_titulo": libro_titulo,
            "fecha_prevista": fecha_prevista,
            "dias_atraso": dias_atraso
        })
        if not html:
            inner = (f"<p>Hola {usuario_nombre},</p>"
                     f"<p>El préstamo de <b>“{libro_titulo}”</b> está atrasado "
                     f"({dias_atraso} día(s)). Fecha prevista: <b>{fecha_prevista}</b>.</p>")
            html = self._basic_wrapper(subject, inner)
        return self.send_email(user_email, subject, html=html)

    def send_reserva_pendiente(self, user_email: str, usuario_nombre: str,
                               libro_titulo: str, fecha_reserva: str, dias_espera: int) -> bool:
        subject = f"Reserva Pendiente — {libro_titulo}"
        html = self._render_template("reserva_pendiente.html", {
            "subject": subject,
            "usuario_nombre": usuario_nombre,
            "libro_titulo": libro_titulo,
            "fecha_reserva": fecha_reserva,
            "dias_espera": dias_espera
        })
        if not html:
            inner = (f"<p>Hola {usuario_nombre},</p>"
                     f"<p>Tu reserva de <b>“{libro_titulo}”</b> está pendiente desde "
                     f"<b>{fecha_reserva}</b> ({dias_espera} día(s)).</p>")
            html = self._basic_wrapper(subject, inner)
        return self.send_email(user_email, subject, html=html)

    # ---------- Bulk ----------
    def bulk_atrasos(self, rows: List[Dict]) -> Dict[str, int]:
        ok = 0
        for r in rows:
            ok += 1 if self.send_atraso(
                r["email"], r["nombre_completo"], r["titulo"], r["fecha_prevista"], r["dias_atraso"]
            ) else 0
        return {"ok": ok, "total": len(rows)}

    def bulk_por_vencer(self, rows: List[Dict]) -> Dict[str, int]:
        ok = 0
        for r in rows:
            ok += 1 if self.send_recordatorio(
                r["email"], r["nombre_completo"], r["titulo"], r["fecha_prevista"], int(r["dias_restantes"])
            ) else 0
        return {"ok": ok, "total": len(rows)}

    def bulk_reservas(self, rows: List[Dict]) -> Dict[str, int]:
        ok = 0
        for r in rows:
            ok += 1 if self.send_reserva_pendiente(
                r["email"], r["nombre_completo"], r["titulo"], r["fecha_reserva_str"], int(r["dias_espera"])
            ) else 0
        return {"ok": ok, "total": len(rows)}
