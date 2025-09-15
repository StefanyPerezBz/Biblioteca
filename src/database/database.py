# src/database/database.py - Gestión de base de datos 
import mysql.connector
from mysql.connector import Error
import streamlit as st

class DatabaseManager:
    def __init__(self):
        self.connection = None

    # -----------------------------
    # Conexión
    # -----------------------------
    def get_connection(self):
        """
        Retorna una conexión viva a MySQL. Reutiliza la misma conexión
        mientras esté abierta y conectada.
        """
        if self.connection is None or not self.connection.is_connected():
            try:
                self.connection = mysql.connector.connect(
                    host=st.secrets["DB_HOST"],
                    database=st.secrets["DB_NAME"],
                    user=st.secrets["DB_USER"],
                    password=st.secrets["DB_PASSWORD"],
                    port=st.secrets["DB_PORT"]
                )
            except Error as e:
                self.show_alert_local("Error", f"❌ Error conectando a la base de datos: {e}", "error")
                return None
        return self.connection

    # -----------------------------
    # Alerts locales 
    # -----------------------------
    def show_alert_local(self, title, text, icon="success"):
        if icon == "success":
            st.success(f"{title}: {text}")
        elif icon == "error":
            st.error(f"{title}: {text}")
        elif icon == "warning":
            st.warning(f"{title}: {text}")
        elif icon == "info":
            st.info(f"{title}: {text}")

    # -----------------------------
    # Consultas genéricas
    # -----------------------------
    def execute_query(self, query, params=None, return_result=True):
        """
        Ejecuta una consulta SQL.
        Usa cursor 'buffered' para evitar 'commands out of sync' por resultados sin leer.
        """
        conn = self.get_connection()
        if conn is None:
            return None

        cursor = None
        try:
            cursor = conn.cursor(dictionary=True, buffered=True)
            cursor.execute(query, params or ())
            if return_result:
                rows = cursor.fetchall()
                return rows
            else:
                conn.commit()
                return True
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            self.show_alert_local("Error", f"❌ Error ejecutando consulta: {e}", "error")
            return None
        finally:
            if cursor:
                cursor.close()

    # -----------------------------
    # Procedimientos almacenados
    # -----------------------------
    def call_procedure(self, procedure_name, params=None):
        """
        Ejecuta un procedimiento almacenado de forma segura, sin mostrar alert:
        - Usa cursor.callproc(.)
        - Consume TODOS los result sets con stored_results()
        - En error NO muestra alert, retorna dict con información del error
        """
        conn = self.get_connection()
        if conn is None:
            return {"error": "No se pudo abrir la conexión a la base de datos"}

        cursor = None
        try:
            cursor = conn.cursor(dictionary=True) 
            args = tuple(params) if params else ()
            cursor.callproc(procedure_name, args)

            results = []
            for result in cursor.stored_results():
                rows = result.fetchall()
                if rows:
                    results.extend(rows)

            conn.commit()
            return results if results else True

        except mysql.connector.Error as e:
            try:
                for _ in cursor.stored_results():
                    pass
            except Exception:
                pass
            try:
                conn.rollback()
            except Exception:
                pass

            return {
                "error": str(e),
                "errno": getattr(e, "errno", None),
                "sqlstate": getattr(e, "sqlstate", None),
            }

        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            return {"error": str(e)}

        finally:
            if cursor:
                cursor.close()
