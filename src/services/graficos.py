# src/services/graficos.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
import tempfile

# ===========================
# Utilidades de color
# ===========================
def _palette(n, cmap_name="tab20"):
    """
    Devuelve una lista de n colores distintos a partir de un colormap.
    Usa muestreo discreto para que siempre haya variedad aunque n sea grande.
    """
    n = max(1, int(n))
    cmap = plt.cm.get_cmap(cmap_name, max(n, 3))
    return [cmap(i) for i in range(n)]

def _apply_tight_layout(fig):
    try:
        fig.tight_layout()
    except Exception:
        pass

# ============================================================
# Función para ADMIN
# ============================================================
def generar_graficos(db_manager):
    st.subheader("📊 Reportes y Estadísticas")

    figs = []

    # Usuarios por Rol (Pie multicolor)
    usuarios = db_manager.execute_query("SELECT role, COUNT(*) as total FROM usuarios GROUP BY role") or []
    df_usuarios = pd.DataFrame(usuarios)
    if not df_usuarios.empty:
        labels = df_usuarios["role"].astype(str).tolist()
        vals = df_usuarios["total"].tolist()
        colors = _palette(len(vals), "Set3")

        fig, ax = plt.subplots()
        ax.pie(vals, labels=labels, autopct='%1.1f%%', startangle=90, colors=colors)
        ax.set_title("Distribución de Usuarios por Rol")
        ax.legend(labels, title="Roles", loc="best")
        _apply_tight_layout(fig)
        st.pyplot(fig)
        figs.append(fig)

    # Usuarios por Facultad (Barras multicolor)
    usuarios_fac = db_manager.execute_query("""
        SELECT f.nombre AS facultad, COUNT(*) AS total
        FROM usuarios u
        JOIN facultades f ON u.facultad_id = f.facultad_id
        GROUP BY f.nombre
    """) or []
    df_fac = pd.DataFrame(usuarios_fac)
    if not df_fac.empty:
        labels = df_fac["facultad"].astype(str).tolist()
        vals = df_fac["total"].tolist()
        colors = _palette(len(vals), "tab20")

        fig, ax = plt.subplots()
        ax.bar(labels, vals, color=colors)
        ax.set_title("Usuarios Registrados por Facultad")
        ax.set_ylabel("Cantidad de Usuarios")
        plt.xticks(rotation=45, ha="right")
        _apply_tight_layout(fig)
        st.pyplot(fig)
        figs.append(fig)

    # Nuevos Usuarios por Mes (línea, color elegido dinámicamente)
    usuarios_mes = db_manager.execute_query("""
        SELECT DATE_FORMAT(fecha_registro, '%Y-%m') as mes, COUNT(*) as total
        FROM usuarios
        GROUP BY mes
        ORDER BY mes
    """) or []
    df_um = pd.DataFrame(usuarios_mes)
    if not df_um.empty:
        color = _palette(1, "Dark2")[0]
        fig, ax = plt.subplots()
        ax.plot(df_um["mes"], df_um["total"], marker="o", color=color)
        ax.set_title("Nuevos Usuarios Registrados por Mes")
        ax.set_xlabel("Mes (Año-Mes)")
        ax.set_ylabel("Cantidad de Usuarios")
        plt.xticks(rotation=45, ha="right")
        _apply_tight_layout(fig)
        st.pyplot(fig)
        figs.append(fig)

    # Top 10 Libros Más Prestados (Barras multicolor)
    libros = db_manager.execute_query("""
        SELECT l.titulo, COUNT(*) as total
        FROM prestamos p
        JOIN libros l ON p.libro_id = l.libro_id
        GROUP BY l.titulo
        ORDER BY total DESC
        LIMIT 10
    """) or []
    df_libros = pd.DataFrame(libros)
    if not df_libros.empty:
        labels = df_libros["titulo"].astype(str).tolist()
        vals = df_libros["total"].tolist()
        colors = _palette(len(vals), "tab20")

        fig, ax = plt.subplots()
        ax.bar(labels, vals, color=colors)
        ax.set_title("📚 Top 10 Libros Más Prestados")
        ax.set_ylabel("Cantidad de Préstamos")
        plt.xticks(rotation=45, ha="right")
        _apply_tight_layout(fig)
        st.pyplot(fig)
        figs.append(fig)

    # Préstamos por Mes (línea, color dinámico)
    prestamos = db_manager.execute_query("""
        SELECT DATE_FORMAT(FROM_UNIXTIME(fecha_prestamo), '%Y-%m') as mes, COUNT(*) as total
        FROM prestamos
        GROUP BY mes
        ORDER BY mes
    """) or []
    df_pres = pd.DataFrame(prestamos)
    if not df_pres.empty:
        color = _palette(1, "Dark2")[0]
        fig, ax = plt.subplots()
        ax.plot(df_pres["mes"], df_pres["total"], marker="o", color=color)
        ax.set_title("Préstamos Registrados por Mes")
        ax.set_xlabel("Mes (Año-Mes)")
        ax.set_ylabel("Cantidad de Préstamos")
        plt.xticks(rotation=45, ha="right")
        _apply_tight_layout(fig)
        st.pyplot(fig)
        figs.append(fig)

    # Categorías más Populares por Préstamos (Barras multicolor)
    cat = db_manager.execute_query("""
        SELECT c.nombre AS categoria, COUNT(*) AS total
        FROM prestamos p
        JOIN libros l ON p.libro_id = l.libro_id
        JOIN categorias c ON l.categoria_id = c.categoria_id
        GROUP BY c.nombre
        ORDER BY total DESC
        LIMIT 10
    """) or []
    df_cat = pd.DataFrame(cat)
    if not df_cat.empty:
        labels = df_cat["categoria"].astype(str).tolist()
        vals = df_cat["total"].tolist()
        colors = _palette(len(vals), "tab20")

        fig, ax = plt.subplots()
        ax.bar(labels, vals, color=colors)
        ax.set_title("Categorías Más Populares (por Préstamos)")
        ax.set_ylabel("Cantidad de Préstamos")
        plt.xticks(rotation=45, ha="right")
        _apply_tight_layout(fig)
        st.pyplot(fig)
        figs.append(fig)

    # Reservas por Estado (Barras multicolor)
    reservas = db_manager.execute_query("SELECT estado, COUNT(*) as total FROM reservas GROUP BY estado") or []
    df_res = pd.DataFrame(reservas)
    if not df_res.empty:
        labels = df_res["estado"].astype(str).tolist()
        vals = df_res["total"].tolist()
        colors = _palette(len(vals), "Set3")

        fig, ax = plt.subplots()
        ax.bar(labels, vals, color=colors)
        ax.set_title("Reservas por Estado")
        ax.set_ylabel("Cantidad de Reservas")
        _apply_tight_layout(fig)
        st.pyplot(fig)
        figs.append(fig)

    # Comparativa Préstamos vs Reservas por Mes (dos líneas, colores distintos)
    comp = db_manager.execute_query("""
        SELECT mes, 
            SUM(tipo='prestamo') AS prestamos, 
            SUM(tipo='reserva') AS reservas
        FROM (
            SELECT DATE_FORMAT(FROM_UNIXTIME(fecha_prestamo), '%Y-%m') as mes, 'prestamo' as tipo FROM prestamos
            UNION ALL
            SELECT DATE_FORMAT(FROM_UNIXTIME(fecha_reserva), '%Y-%m') as mes, 'reserva' as tipo FROM reservas
        ) t
        GROUP BY mes
        ORDER BY mes
    """) or []
    df_comp = pd.DataFrame(comp)
    if not df_comp.empty:
        c1, c2 = _palette(2, "Dark2")
        fig, ax = plt.subplots()
        ax.plot(df_comp["mes"], df_comp["prestamos"], marker="o", label="Préstamos", color=c1)
        ax.plot(df_comp["mes"], df_comp["reservas"], marker="s", label="Reservas", color=c2)
        ax.set_title("Comparativa: Préstamos vs Reservas por Mes")
        ax.set_xlabel("Mes (Año-Mes)")
        ax.set_ylabel("Cantidad")
        ax.legend()
        plt.xticks(rotation=45, ha="right")
        _apply_tight_layout(fig)
        st.pyplot(fig)
        figs.append(fig)

    # Sanciones por Estado (Pie multicolor)
    sanciones = db_manager.execute_query("SELECT estado, COUNT(*) as total FROM sanciones GROUP BY estado") or []
    df_sanc = pd.DataFrame(sanciones)
    if not df_sanc.empty:
        labels = df_sanc["estado"].astype(str).tolist()
        vals = df_sanc["total"].tolist()
        colors = _palette(len(vals), "Set3")

        fig, ax = plt.subplots()
        ax.pie(vals, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90)
        ax.set_title("Sanciones por Estado")
        _apply_tight_layout(fig)
        st.pyplot(fig)
        figs.append(fig)

    # Sanciones por Mes (Barras multicolor por mes)
    sanc_mes = db_manager.execute_query("""
        SELECT DATE_FORMAT(FROM_UNIXTIME(fecha_inicio), '%Y-%m') as mes, COUNT(*) as total
        FROM sanciones
        GROUP BY mes
        ORDER BY mes
    """) or []
    df_sm = pd.DataFrame(sanc_mes)
    if not df_sm.empty:
        labels = df_sm["mes"].astype(str).tolist()
        vals = df_sm["total"].tolist()
        colors = _palette(len(vals), "tab20")

        fig, ax = plt.subplots()
        ax.bar(labels, vals, color=colors)
        ax.set_title("Sanciones Registradas por Mes")
        ax.set_xlabel("Mes (Año-Mes)")
        ax.set_ylabel("Cantidad de Sanciones")
        plt.xticks(rotation=45, ha="right")
        _apply_tight_layout(fig)
        st.pyplot(fig)
        figs.append(fig)

    # Exportación PDF
    if figs and st.button("Descargar Reporte en PDF"):
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []
        elements.append(Paragraph("Reporte Estadístico - Administrador", styles['Title']))
        elements.append(Spacer(1, 0.2*inch))
        for fig in figs:
            tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            fig.savefig(tmpfile.name, dpi=150, bbox_inches="tight")
            elements.append(Image(tmpfile.name, width=5*inch, height=3*inch))
            elements.append(Spacer(1, 0.2*inch))
        doc.build(elements)
        buffer.seek(0)
        st.download_button("Descargar PDF", data=buffer, file_name="reporte_admin.pdf", mime="application/pdf")

# ============================================================
# Función para BIBLIOTECARIO
# ============================================================
def generar_graficos_bibliotecario(db_manager):
    import matplotlib.pyplot as plt
    import pandas as pd
    import streamlit as st
    from io import BytesIO
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import inch
    import tempfile

    st.subheader("📊 Reportes y Estadísticas (Bibliotecario)")
    figs = []

    # Préstamos activos por rol (Pie multicolor)
    q1 = """
        SELECT u.role, COUNT(*) AS total
        FROM prestamos p
        JOIN usuarios u ON p.usuario_id = u.user_id
        WHERE p.estado = 'activo'
        GROUP BY u.role
    """
    df1 = pd.DataFrame(db_manager.execute_query(q1) or [])
    if not df1.empty:
        labels = df1["role"].astype(str).tolist()
        vals = df1["total"].tolist()
        colors = _palette(len(vals), "Set3")

        fig, ax = plt.subplots()
        ax.pie(vals, labels=labels, autopct="%1.1f%%", startangle=90, colors=colors)
        ax.set_title("Distribución de Préstamos Activos por Rol")
        ax.legend(labels, title="Roles", loc="best")
        _apply_tight_layout(fig)
        st.pyplot(fig); figs.append(fig)

    # Préstamos registrados por mes (línea, color dinámico)
    q2 = """
        SELECT DATE_FORMAT(FROM_UNIXTIME(fecha_prestamo), '%Y-%m') AS mes, COUNT(*) AS total
        FROM prestamos
        GROUP BY mes
        ORDER BY mes
    """
    df2 = pd.DataFrame(db_manager.execute_query(q2) or [])
    if not df2.empty:
        color = _palette(1, "Dark2")[0]
        fig, ax = plt.subplots()
        ax.plot(df2["mes"], df2["total"], marker="o", color=color)
        ax.set_title("Préstamos Registrados por Mes")
        ax.set_xlabel("Mes (Año-Mes)")
        ax.set_ylabel("Cantidad de Préstamos")
        plt.xticks(rotation=45, ha="right")
        _apply_tight_layout(fig)
        st.pyplot(fig); figs.append(fig)

    # Préstamos activos por categoría (Barras multicolor)
    q3 = """
        SELECT c.nombre AS categoria, COUNT(*) AS total
        FROM prestamos p
        JOIN libros l ON p.libro_id = l.libro_id
        JOIN categorias c ON l.categoria_id = c.categoria_id
        WHERE p.estado = 'activo'
        GROUP BY c.nombre
        ORDER BY total DESC
        LIMIT 15
    """
    df3 = pd.DataFrame(db_manager.execute_query(q3) or [])
    if not df3.empty:
        labels = df3["categoria"].astype(str).tolist()
        vals = df3["total"].tolist()
        colors = _palette(len(vals), "tab20")

        fig, ax = plt.subplots()
        ax.bar(labels, vals, color=colors)
        ax.set_title("Préstamos Activos por Categoría")
        ax.set_ylabel("Cantidad de Préstamos")
        plt.xticks(rotation=45, ha="right")
        _apply_tight_layout(fig)
        st.pyplot(fig); figs.append(fig)

    # Top 10 libros más prestados (histórico) (Barras multicolor)
    q4 = """
        SELECT l.titulo, COUNT(*) AS total
        FROM prestamos p
        JOIN libros l ON p.libro_id = l.libro_id
        GROUP BY l.titulo
        ORDER BY total DESC
        LIMIT 10
    """
    df4 = pd.DataFrame(db_manager.execute_query(q4) or [])
    if not df4.empty:
        labels = df4["titulo"].astype(str).tolist()
        vals = df4["total"].tolist()
        colors = _palette(len(vals), "tab20")

        fig, ax = plt.subplots()
        ax.bar(labels, vals, color=colors)
        ax.set_title("📚 Top 10 Libros Más Prestados (Histórico)")
        ax.set_ylabel("Cantidad de Préstamos")
        plt.xticks(rotation=45, ha="right")
        _apply_tight_layout(fig)
        st.pyplot(fig); figs.append(fig)

    # Reservas por estado (Barras multicolor)
    q5 = "SELECT estado, COUNT(*) AS total FROM reservas GROUP BY estado"
    df5 = pd.DataFrame(db_manager.execute_query(q5) or [])
    if not df5.empty:
        labels = df5["estado"].astype(str).tolist()
        vals = df5["total"].tolist()
        colors = _palette(len(vals), "Set3")

        fig, ax = plt.subplots()
        ax.bar(labels, vals, color=colors)
        ax.set_title("Reservas por Estado")
        ax.set_ylabel("Cantidad de Reservas")
        _apply_tight_layout(fig)
        st.pyplot(fig); figs.append(fig)

    # Reservas por mes (línea, color dinámico)
    q6 = """
        SELECT DATE_FORMAT(FROM_UNIXTIME(fecha_reserva), '%Y-%m') AS mes, COUNT(*) AS total
        FROM reservas
        GROUP BY mes
        ORDER BY mes
    """
    df6 = pd.DataFrame(db_manager.execute_query(q6) or [])
    if not df6.empty:
        color = _palette(1, "Dark2")[0]
        fig, ax = plt.subplots()
        ax.plot(df6["mes"], df6["total"], marker="s", color=color)
        ax.set_title("Reservas Registradas por Mes")
        ax.set_xlabel("Mes (Año-Mes)")
        ax.set_ylabel("Cantidad de Reservas")
        plt.xticks(rotation=45, ha="right")
        _apply_tight_layout(fig)
        st.pyplot(fig); figs.append(fig)

    # Comparativa: Préstamos vs Reservas por mes (dos líneas, colores distintos)
    q7 = """
        SELECT mes, 
               SUM(tipo='prestamo') AS prestamos, 
               SUM(tipo='reserva')  AS reservas
        FROM (
            SELECT DATE_FORMAT(FROM_UNIXTIME(fecha_prestamo), '%Y-%m') AS mes, 'prestamo' AS tipo FROM prestamos
            UNION ALL
            SELECT DATE_FORMAT(FROM_UNIXTIME(fecha_reserva),  '%Y-%m') AS mes, 'reserva'  AS tipo FROM reservas
        ) t
        GROUP BY mes
        ORDER BY mes
    """
    df7 = pd.DataFrame(db_manager.execute_query(q7) or [])
    if not df7.empty:
        c1, c2 = _palette(2, "Dark2")
        fig, ax = plt.subplots()
        ax.plot(df7["mes"], df7["prestamos"], marker="o", label="Préstamos", color=c1)
        ax.plot(df7["mes"], df7["reservas"],  marker="s", label="Reservas",  color=c2)
        ax.set_title("Comparativa: Préstamos vs Reservas por Mes")
        ax.set_xlabel("Mes (Año-Mes)")
        ax.set_ylabel("Cantidad")
        ax.legend()
        plt.xticks(rotation=45, ha="right")
        _apply_tight_layout(fig)
        st.pyplot(fig); figs.append(fig)

    # Atrasos por Rol (Barras multicolor)
    q8 = """
        SELECT u.role, COUNT(*) AS total
        FROM prestamos p
        JOIN usuarios u ON p.usuario_id = u.user_id
        WHERE p.estado='activo' AND p.fecha_devolucion_estimada < UNIX_TIMESTAMP()
        GROUP BY u.role
    """
    df8 = pd.DataFrame(db_manager.execute_query(q8) or [])
    if not df8.empty:
        labels = df8["role"].astype(str).tolist()
        vals = df8["total"].tolist()
        colors = _palette(len(vals), "tab20")

        fig, ax = plt.subplots()
        ax.bar(labels, vals, color=colors)
        ax.set_title("Atrasos por Rol (Préstamos Vencidos)")
        ax.set_ylabel("Cantidad de Préstamos Vencidos")
        _apply_tight_layout(fig)
        st.pyplot(fig); figs.append(fig)

    # Devoluciones por estado final (Pie multicolor)
    q9 = """
        SELECT estado, COUNT(*) AS total
        FROM prestamos
        WHERE estado IN ('devuelto','dañado','perdido')
        GROUP BY estado
        ORDER BY total DESC
    """
    df9 = pd.DataFrame(db_manager.execute_query(q9) or [])
    if not df9.empty:
        labels = [str(s).capitalize() for s in df9["estado"]]
        vals = df9["total"].tolist()
        colors = _palette(len(vals), "Set3")

        fig, ax = plt.subplots()
        ax.pie(vals, labels=labels, autopct="%1.1f%%", startangle=90, colors=colors)
        ax.set_title("Devoluciones por Estado Final (Histórico)")
        _apply_tight_layout(fig)
        st.pyplot(fig); figs.append(fig)

    # Tiempo promedio de préstamo por categoría (Barras multicolor)
    q10 = """
        SELECT c.nombre AS categoria,
               ROUND(AVG((p.fecha_devolucion_real - p.fecha_prestamo) / 86400), 2) AS dias_prom
        FROM prestamos p
        JOIN libros l ON p.libro_id = l.libro_id
        JOIN categorias c ON l.categoria_id = c.categoria_id
        WHERE p.estado = 'devuelto' AND p.fecha_devolucion_real IS NOT NULL
        GROUP BY c.nombre
        HAVING dias_prom IS NOT NULL
        ORDER BY dias_prom DESC
        LIMIT 12
    """
    df10 = pd.DataFrame(db_manager.execute_query(q10) or [])
    if not df10.empty:
        labels = df10["categoria"].astype(str).tolist()
        vals = df10["dias_prom"].tolist()
        colors = _palette(len(vals), "tab20")

        fig, ax = plt.subplots()
        ax.bar(labels, vals, color=colors)
        ax.set_title("Tiempo Promedio de Préstamo por Categoría (días)")
        ax.set_ylabel("Días promedio")
        plt.xticks(rotation=45, ha="right")
        _apply_tight_layout(fig)
        st.pyplot(fig); figs.append(fig)

    # Sanciones activas por rol (Barras multicolor)
    q11 = """
        SELECT u.role, COUNT(*) AS total
        FROM sanciones s
        JOIN usuarios u ON s.usuario_id = u.user_id
        WHERE s.estado='activa'
        GROUP BY u.role
    """
    df11 = pd.DataFrame(db_manager.execute_query(q11) or [])
    if not df11.empty:
        labels = df11["role"].astype(str).tolist()
        vals = df11["total"].tolist()
        colors = _palette(len(vals), "tab20")

        fig, ax = plt.subplots()
        ax.bar(labels, vals, color=colors)
        ax.set_title("Sanciones Activas por Rol")
        ax.set_ylabel("Cantidad de Sanciones")
        _apply_tight_layout(fig)
        st.pyplot(fig); figs.append(fig)

    # Exportación PDF
    if figs and st.button("Descargar Reporte en PDF"):
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []
        elements.append(Paragraph("Reporte Estadístico - Bibliotecario", styles["Title"]))
        elements.append(Spacer(1, 0.2 * inch))
        for fig in figs:
            tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            fig.savefig(tmpfile.name, dpi=150, bbox_inches="tight")
            elements.append(Image(tmpfile.name, width=5 * inch, height=3 * inch))
            elements.append(Spacer(1, 0.2 * inch))
        doc.build(elements)
        buffer.seek(0)
        st.download_button(
            "Descargar PDF",
            data=buffer,
            file_name="reporte_bibliotecario.pdf",
            mime="application/pdf",
        )

# ============================================================
# Función para USUARIO (Estudiante / Docente)
# ============================================================
def generar_graficos_usuario(db_manager, user):
    st.subheader("📊 Mis Estadísticas de Biblioteca")

    figs = []

    # Préstamos por Categoría (Barras multicolor)
    cat = db_manager.execute_query("""
        SELECT c.nombre AS categoria, COUNT(*) AS total
        FROM prestamos p
        JOIN libros l ON p.libro_id = l.libro_id
        JOIN categorias c ON l.categoria_id = c.categoria_id
        WHERE p.usuario_id = %s
        GROUP BY c.nombre
        ORDER BY total DESC
    """, (user["user_id"],)) or []
    df_cat = pd.DataFrame(cat)
    if not df_cat.empty:
        labels = df_cat["categoria"].astype(str).tolist()
        vals = df_cat["total"].tolist()
        colors = _palette(len(vals), "tab20")

        fig, ax = plt.subplots()
        ax.bar(labels, vals, color=colors)
        ax.set_title("📚 Mis Préstamos por Categoría")
        ax.set_ylabel("Cantidad de Préstamos")
        plt.xticks(rotation=45, ha="right")
        _apply_tight_layout(fig)
        st.pyplot(fig)
        figs.append(fig)

    # Préstamos por Mes (línea, color dinámico)
    pres = db_manager.execute_query("""
        SELECT DATE_FORMAT(FROM_UNIXTIME(fecha_prestamo), '%Y-%m') as mes, COUNT(*) as total
        FROM prestamos
        WHERE usuario_id = %s
        GROUP BY mes
        ORDER BY mes
    """, (user["user_id"],)) or []
    df_pres = pd.DataFrame(pres)
    if not df_pres.empty:
        color = _palette(1, "Dark2")[0]
        fig, ax = plt.subplots()
        ax.plot(df_pres["mes"], df_pres["total"], marker="o", color=color)
        ax.set_title("📅 Mis Préstamos por Mes")
        ax.set_xlabel("Mes (Año-Mes)")
        ax.set_ylabel("Cantidad de Préstamos")
        plt.xticks(rotation=45, ha="right")
        _apply_tight_layout(fig)
        st.pyplot(fig)
        figs.append(fig)

    if figs and st.button("Descargar Reporte en PDF"):
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []
        elements.append(Paragraph("Reporte Estadístico", styles['Title']))
        elements.append(Spacer(1, 0.2*inch))
        for fig in figs:
            tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            fig.savefig(tmpfile.name, dpi=150, bbox_inches="tight")
            elements.append(Image(tmpfile.name, width=5*inch, height=3*inch))
            elements.append(Spacer(1, 0.2*inch))
        doc.build(elements)
        buffer.seek(0)
        st.download_button("Descargar PDF", data=buffer, file_name="reporte_usuario.pdf", mime="application/pdf")
