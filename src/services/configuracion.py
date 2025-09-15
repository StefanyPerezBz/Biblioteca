# src/services/configuracion.py - Gestión de configuración
import streamlit as st
from src.database.database import DatabaseManager
from src.utils.alert_utils import show_sweet_alert

def gestion_configuracion(db_manager, show_sweet_alert):
    """Función para gestionar la configuración del sistema"""
    st.subheader("Configuración del Sistema")
    
    config_params = db_manager.execute_query("SELECT * FROM configuracion ORDER BY parametro")
    
    if config_params:
        for param in config_params:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"**{param['parametro']}**")
                st.caption(param['descripcion'])
            with col2:
                new_value = st.text_input("Valor", value=param['valor'], key=param['parametro'])
            with col3:
                if st.button("Actualizar", key=f"upd_{param['parametro']}"):
                    db_manager.execute_query(
                        "UPDATE configuracion SET valor = %s WHERE parametro = %s",
                        (new_value, param['parametro']),
                        return_result=False
                    )
                    show_sweet_alert("Éxito", "Valor actualizado", "success")
        
        st.info("Los cambios en la configuración afectarán a todos los usuarios y operaciones del sistema.")
    else:
        st.info("❌ No hay parámetros de configuración disponibles.")