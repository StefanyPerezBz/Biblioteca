# src/utils/alert_utils.py
# Alertas compatibles con dark/light mode
import streamlit as st

def show_sweet_alert(title, text, icon="info"):
    """
    Muestra una alerta con diseño mejorado y compatible con modo oscuro/claro.
    - icon: "success", "error", "warning", "info"
    """
    styles = {
        "success": {"bg": "#1e4620", "border": "#28a745", "icon": "✅"},
        "error":   {"bg": "#4b1d1d", "border": "#dc3545", "icon": "❌"},
        "warning": {"bg": "#4b3d1d", "border": "#ffc107", "icon": "⚠️"},
        "info":    {"bg": "#1d3d4b", "border": "#17a2b8", "icon": "ℹ️"},
    }

    s = styles.get(icon, styles["info"])

    st.markdown(
        f"""
        <div style="
            padding: 1rem;
            margin: 0.5rem 0;
            border-radius: 10px;
            background-color: {s['bg']};
            border-left: 6px solid {s['border']};
            box-shadow: 0px 2px 6px rgba(0,0,0,0.4);
            font-size: 0.95rem;
            color: white;
        ">
            <strong>{s['icon']} {title}</strong><br>
            {text}
        </div>
        """,
        unsafe_allow_html=True
    )