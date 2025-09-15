# src/services/libros.py - Gestión de libros
import streamlit as st
import pandas as pd
from datetime import datetime
from src.database.database import DatabaseManager
from src.utils.image_manager import ImageManager
from src.utils.alert_utils import show_sweet_alert
import os
import re

# Constante para la paginación
PAGE_SIZE = 10

# Validación de campos con mensajes más claros
def validar_campo(texto, tipo="texto"):
    """
    Valida campos de texto para títulos, editorial o ISBN.
    tipo: 
        "texto" -> letras, números, espacios, guiones, comas, puntos.
        "isbn" -> solo números y guiones.
        "nombre" -> solo letras y espacios (para autores y categorías)
    """
    if tipo == "texto":
        if not re.fullmatch(r"^[\wáéíóúÁÉÍÓÚüÜñÑ0-9\s\-,.:]+$", texto) or re.fullmatch(r"^[\(\)\/,]+$", texto):
            return False, "Solo se permiten letras, números, espacios, guiones, comas y puntos. No se permiten solo caracteres especiales."
    elif tipo == "isbn":
        if not re.fullmatch(r"^[0-9-]+$", texto):
            return False, "El ISBN solo puede contener números y guiones."
    elif tipo == "nombre":
        if not re.fullmatch(r"^[A-Za-zÁÉÍÓÚáéíóúÜüÑñ\s]+$", texto.strip()):
            return False, "Solo se permiten letras y espacios."
    return True, None

def gestion_libros(db_manager, show_sweet_alert, user_role):
    """Función para gestionar libros según el rol del usuario"""
    
    image_manager = ImageManager()
    default_cover = image_manager.get_default_cover()

    if 'active_card' not in st.session_state:
        st.session_state.active_card = None
    if 'selected_libro' not in st.session_state:
        st.session_state.selected_libro = None
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 1
    if 'search_term' not in st.session_state:
        st.session_state.search_term = ""
    if 'confirm_delete' not in st.session_state:
        st.session_state.confirm_delete = None
    if 'editing_autor' not in st.session_state:
        st.session_state.editing_autor = None
    if 'editing_categoria' not in st.session_state:
        st.session_state.editing_categoria = None
    if 'confirm_delete_autor' not in st.session_state:
        st.session_state.confirm_delete_autor = None
    if 'confirm_delete_categoria' not in st.session_state:
        st.session_state.confirm_delete_categoria = None

    # Determinar qué funcionalidades mostrar según el rol
    is_admin_bibliotecario = user_role in ['admin', 'bibliotecario']
    is_estudiante_docente = user_role in ['estudiante', 'docente']

    if is_admin_bibliotecario:
        st.subheader("Gestión de Libros")
        tab1, tab2, tab3 = st.tabs(["Listar Libros", "Agregar Nuevo", "Gestión de Autores/Categorías"])
    else:
        st.subheader("Catálogo de Libros")
        tab1 = st.container()

    # ========================
    # TAB 1: LISTAR LIBROS (PARA TODOS LOS ROLES)
    # ========================
    with tab1:
        st.write("### Catálogo de Libros")
        
        new_search_term = st.text_input("Buscar libro por título, autor, ISBN o categoría")
        if new_search_term != st.session_state.search_term:
            st.session_state.search_term = new_search_term
            st.session_state.current_page = 1
            st.session_state.active_card = None
            st.rerun()

        offset = (st.session_state.current_page - 1) * PAGE_SIZE
        
        query = """
            SELECT 
                l.libro_id, l.titulo, a.nombre_completo AS autor, l.isbn, 
                l.anio_publicacion, l.editorial, l.ejemplares_disponibles, 
                l.portada_id, c.nombre AS categoria,
                l.ejemplares_totales, l.categoria_id, l.autor_id
            FROM libros l
            JOIN autores a ON l.autor_id = a.autor_id
            JOIN categorias c ON l.categoria_id = c.categoria_id
            WHERE l.activo = TRUE 
              AND (l.titulo LIKE %s OR a.nombre_completo LIKE %s OR l.isbn LIKE %s OR c.nombre LIKE %s)
            ORDER BY l.titulo
            LIMIT %s OFFSET %s
        """
        params = [f"%{st.session_state.search_term}%"]*4 + [PAGE_SIZE, offset]
        libros_data = db_manager.execute_query(query, params)
        
        count_query = """
            SELECT COUNT(*) FROM libros l
            JOIN autores a ON l.autor_id = a.autor_id
            JOIN categorias c ON l.categoria_id = c.categoria_id
            WHERE l.activo = TRUE 
              AND (l.titulo LIKE %s OR a.nombre_completo LIKE %s OR l.isbn LIKE %s OR c.nombre LIKE %s)
        """
        total_libros = db_manager.execute_query(count_query, [f"%{st.session_state.search_term}%"]*4)
        total_count = total_libros[0]['COUNT(*)'] if total_libros else 0
        total_pages = (total_count + PAGE_SIZE - 1) // PAGE_SIZE

        # Listado
        if libros_data:
            st.write(f"Se encontraron los siguientes libros ({total_count} en total):")
            for libro in libros_data:
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.image(libro['portada_id'] if libro['portada_id'] and os.path.exists(libro['portada_id']) else default_cover, width=100)
                with col2:
                    st.markdown(f"**Título:** {libro['titulo']}")
                    st.markdown(f"**Autor:** {libro['autor']}")
                    st.markdown(f"**Disponibles:** {libro['ejemplares_disponibles']}/{libro['ejemplares_totales']}")
                    
                    if is_admin_bibliotecario:
                        col_detalles, col_editar, col_eliminar = st.columns([1, 1, 1])
                        
                        # Detalles
                        if col_detalles.button("Detalles", key=f"detalles_{libro['libro_id']}"):
                            st.session_state.active_card = f"detalles_{libro['libro_id']}" if st.session_state.active_card != f"detalles_{libro['libro_id']}" else None
                            st.session_state.selected_libro = libro if st.session_state.active_card else None
                            st.session_state.confirm_delete = None
                            st.rerun()
                        
                        # Editar
                        if col_editar.button("Editar", key=f"editar_{libro['libro_id']}"):
                            st.session_state.active_card = f"editar_{libro['libro_id']}" if st.session_state.active_card != f"editar_{libro['libro_id']}" else None
                            st.session_state.selected_libro = libro if st.session_state.active_card else None
                            st.session_state.confirm_delete = None
                            st.rerun()
                        
                        # Eliminar  — BLOQUEO SI HAY PRÉSTAMOS ACTIVOS
                        delete_label = "Eliminar" if st.session_state.confirm_delete != libro['libro_id'] else "Confirmar Eliminación"
                        if col_eliminar.button(delete_label, key=f"eliminar_{libro['libro_id']}"):
                            if st.session_state.confirm_delete == libro['libro_id']:
                                try:
                                    # ¿Préstamos ACTIVOS?
                                    cnt_act = db_manager.execute_query(
                                        "SELECT COUNT(*) AS c FROM prestamos WHERE libro_id = %s AND estado = 'activo'",
                                        (libro['libro_id'],)
                                    )
                                    if cnt_act and int(cnt_act[0]['c']) > 0:
                                        show_sweet_alert(
                                            "No permitido",
                                            "No se puede eliminar este libro: tiene préstamos activos. "
                                            "Elimine primero el/los préstamo(s) relacionados.",
                                            "error"
                                        )
                                        st.session_state.confirm_delete = None
                                        return 
                                    
                                    # ¿Reservas ACTIVAS?
                                    cnt_res = db_manager.execute_query(
                                        "SELECT COUNT(*) AS c FROM reservas WHERE libro_id = %s AND estado = 'pendiente'",
                                        (libro['libro_id'],)
                                    )
                                    if cnt_res and int(cnt_res[0]['c']) > 0:
                                        show_sweet_alert(
                                            "No permitido",
                                            "No se puede eliminar este libro: tiene reservas activas. "
                                            "Cancela primero todas las reservas pendientes de este libro.",
                                            "error"
                                        )
                                        st.session_state.confirm_delete = None
                                        return 

                                    # ¿Cualquier préstamo (historial)?
                                    cnt_all = db_manager.execute_query(
                                        "SELECT COUNT(*) AS c FROM prestamos WHERE libro_id = %s",
                                        (libro['libro_id'],)
                                    )
                                    if cnt_all and int(cnt_all[0]['c']) > 0:
                                        show_sweet_alert(
                                            "No permitido",
                                            "No se puede eliminar este libro: existen préstamos asociados en el historial. "
                                            "Elimine primero el/los préstamo(s) de este libro.",
                                            "error"
                                        )
                                        st.session_state.confirm_delete = None
                                        return 

                                    # Si no hay relación, eliminar
                                    if libro['portada_id'] and os.path.exists(libro['portada_id']) and "default_cover" not in os.path.basename(libro['portada_id']):
                                        image_manager.delete_image_by_path(libro['portada_id'])

                                    db_manager.execute_query(
                                        "DELETE FROM libros WHERE libro_id = %s",
                                        (libro['libro_id'],),
                                        return_result=False
                                    )
                                    show_sweet_alert("Éxito", "Libro eliminado completamente.", "success")
                                    st.session_state.confirm_delete = None
                                    st.session_state.active_card = None
                                    st.session_state.selected_libro = None
                                    st.rerun()

                                except Exception as e:
                                    emsg = str(e).lower()
                                    # 1451 = FK violation
                                    if "foreign key" in emsg or "1451" in emsg:
                                        show_sweet_alert(
                                            "No permitido",
                                            "No se puede eliminar este libro: existen préstamos o reservas relacionados."
                                            "Elimine primero el/los préstamo(s) y reserva(s) de este libro.",
                                            "error"
                                        )
                                    else:
                                        show_sweet_alert("Error", f"Error al eliminar el libro: {e}", "error")
                                    st.session_state.confirm_delete = None
                                    return 
                            else:
                                st.session_state.confirm_delete = libro['libro_id']
                                show_sweet_alert("Confirmar", "Presione de nuevo para confirmar la eliminación.", "warning")

                    else:
                        # Solo botón de detalles para estudiantes/docentes
                        if st.button("Ver Detalles", key=f"detalles_{libro['libro_id']}"):
                            st.session_state.active_card = f"detalles_{libro['libro_id']}" if st.session_state.active_card != f"detalles_{libro['libro_id']}" else None
                            st.session_state.selected_libro = libro if st.session_state.active_card else None
                            st.rerun()
                st.write("---")

            # Paginación
            col_prev, col_info, col_next = st.columns([1, 2, 1])
            if col_prev.button("<< Anterior", disabled=st.session_state.current_page == 1):
                st.session_state.current_page -= 1; st.session_state.active_card = None; st.rerun()
            col_info.write(f"Página {st.session_state.current_page} de {total_pages}")
            if col_next.button("Siguiente >>", disabled=st.session_state.current_page == total_pages):
                st.session_state.current_page += 1; st.session_state.active_card = None; st.rerun()
        else:
            st.info("❌ No se encontraron libros.")
        
        # ========================
        # Detalles o Edición (SOLO ADMIN/BIBLIOTECARIO)
        # ========================
        if st.session_state.active_card and is_admin_bibliotecario:
            card_type, libro_id = st.session_state.active_card.split('_')
            libro = st.session_state.selected_libro
            if not libro: 
                return
            
            if card_type == "detalles":
                st.subheader("Detalles del Libro")
                col_img, col_info = st.columns([1, 2])
                with col_img:
                    st.image(libro['portada_id'] if libro['portada_id'] and os.path.exists(libro['portada_id']) else default_cover, width=200)
                with col_info:
                    st.write(f"**Título:** {libro['titulo']}")
                    st.write(f"**Autor:** {libro['autor']}")
                    st.write(f"**Editorial:** {libro['editorial']}")
                    st.write(f"**Año:** {libro['anio_publicacion']}")
                    st.write(f"**ISBN:** {libro['isbn']}")
                    st.write(f"**Categoría:** {libro['categoria']}")
                    st.write(f"**Ejemplares totales:** {libro['ejemplares_totales']}")
                    st.write(f"**Ejemplares disponibles:** {libro['ejemplares_disponibles']}")

            elif card_type == "editar":
                with st.form("edit_book_form"):
                    st.write(f"### Editar Libro: {libro['titulo']}")
                    
                    autores_list = db_manager.execute_query("SELECT autor_id, nombre_completo FROM autores ORDER BY nombre_completo")
                    autores_options = {a['nombre_completo']: a['autor_id'] for a in autores_list}
                    default_autor = db_manager.execute_query("SELECT nombre_completo FROM autores WHERE autor_id = %s", (libro['autor_id'],))[0]['nombre_completo']
                    nuevo_autor = st.selectbox("Autor", list(autores_options.keys()), index=list(autores_options.keys()).index(default_autor))

                    categorias_list = db_manager.execute_query("SELECT categoria_id, nombre FROM categorias ORDER BY nombre")
                    categorias_options = {c['nombre']: c['categoria_id'] for c in categorias_list}
                    default_cat = db_manager.execute_query("SELECT nombre FROM categorias WHERE categoria_id = %s", (libro['categoria_id'],))[0]['nombre']
                    nueva_categoria = st.selectbox("Categoría", list(categorias_options.keys()), index=list(categorias_options.keys()).index(default_cat))

                    nuevo_titulo = st.text_input("Título", value=libro['titulo'])
                    nuevo_editorial = st.text_input("Editorial", value=libro['editorial'])
                    nuevo_anio = st.number_input("Año de Publicación", min_value=1500, max_value=datetime.now().year, value=libro['anio_publicacion'])
                    nuevo_isbn = st.text_input("ISBN", value=libro['isbn'])
                    nuevo_ejemplares = st.number_input("Ejemplares Totales", min_value=1, value=libro['ejemplares_totales'])
                    
                    st.markdown("---")
                    portada_file = st.file_uploader("Subir Nueva Portada (JPG, PNG)", type=["jpg", "jpeg", "png"])

                    col_save, col_cancel = st.columns(2)
                    if col_save.form_submit_button("Guardar Cambios"):
                        # Validaciones
                        valid, msg = validar_campo(nuevo_titulo, "texto")
                        if not valid: 
                            return show_sweet_alert("Error", f"Título inválido. {msg}", "error")
                        valid, msg = validar_campo(nuevo_editorial, "texto")
                        if not valid: 
                            return show_sweet_alert("Error", f"Editorial inválida. {msg}", "error")
                        if nuevo_isbn:
                            valid, msg = validar_campo(nuevo_isbn, "isbn")
                            if not valid: 
                                return show_sweet_alert("Error", msg, "error")

                        # Validación ISBN único 
                        if nuevo_isbn:
                            isbn_count = db_manager.execute_query("SELECT COUNT(*) FROM libros WHERE isbn = %s AND libro_id != %s", (nuevo_isbn, libro['libro_id']))
                            if isbn_count and isbn_count[0]['COUNT(*)'] > 0:
                                return show_sweet_alert("Error", f"Ya existe otro libro con el ISBN '{nuevo_isbn}'.", "error")

                        # Validación duplicado exacto de libro (mismo título + autor + editorial + año)
                        autor_id_update, categoria_id_update = autores_options[nuevo_autor], categorias_options[nueva_categoria]
                        dup_count = db_manager.execute_query(
                            "SELECT COUNT(*) FROM libros WHERE titulo=%s AND autor_id=%s AND editorial=%s AND anio_publicacion=%s AND libro_id!=%s", 
                            (nuevo_titulo, autor_id_update, nuevo_editorial, nuevo_anio, libro['libro_id'])
                        )
                        if dup_count and dup_count[0]['COUNT(*)'] > 0:
                            return show_sweet_alert("Error", "Ya existe otro libro con el mismo título, autor, editorial y año.", "error")

                        # Manejo de portada
                        new_portada_id = libro['portada_id']
                        if portada_file:
                            success, message = image_manager.validate_image(portada_file)
                            if success:
                                if libro['portada_id']: 
                                    image_manager.delete_image_by_path(libro['portada_id'])
                                new_portada_id = image_manager.save_image(portada_file, 'libro', 'temp_id')
                            else:
                                return show_sweet_alert("Error de Imagen", message, "error")

                        try:
                            activos_res = db_manager.execute_query(
                                "SELECT COALESCE(SUM(cantidad),0) AS total FROM prestamos WHERE libro_id = %s AND estado = 'activo'",
                                (libro['libro_id'],)
                            )
                            prestamos_activos = int(activos_res[0]['total']) if activos_res else 0

                            if nuevo_ejemplares < prestamos_activos:
                                return show_sweet_alert(
                                    "No permitido",
                                    f"No puede establecer 'Ejemplares Totales' ({nuevo_ejemplares}) por debajo de los préstamos activos ({prestamos_activos}).",
                                    "error"
                                )

                            ejemplares_disponibles_update = nuevo_ejemplares - prestamos_activos

                            db_manager.execute_query(
                                """UPDATE libros
                                   SET titulo=%s, autor_id=%s, editorial=%s, anio_publicacion=%s, isbn=%s,
                                       ejemplares_totales=%s, ejemplares_disponibles=%s, categoria_id=%s, portada_id=%s
                                   WHERE libro_id=%s""",
                                (nuevo_titulo, autor_id_update, nuevo_editorial, nuevo_anio, nuevo_isbn,
                                 int(nuevo_ejemplares), int(ejemplares_disponibles_update), categoria_id_update,
                                 new_portada_id, libro['libro_id']),
                                return_result=False
                            )
                            show_sweet_alert("Éxito", "Libro actualizado correctamente.", "success")
                            st.session_state.active_card = None; st.session_state.selected_libro = None
                        except Exception as e:
                            if "1062" in str(e) and "isbn" in str(e):
                                show_sweet_alert("Error", f"Ya existe otro libro con el ISBN '{nuevo_isbn}'.", "error")
                            else:
                                show_sweet_alert("Error de Base de Datos", str(e), "error")

                    if col_cancel.form_submit_button("Cancelar"):
                        st.session_state.active_card = None; st.session_state.selected_libro = None; st.rerun()

        # Detalles para estudiantes/docentes
        elif st.session_state.active_card and is_estudiante_docente:
            libro = st.session_state.selected_libro
            st.subheader("Detalles del Libro")
            col_img, col_info = st.columns([1, 2])
            with col_img:
                st.image(libro['portada_id'] if libro['portada_id'] and os.path.exists(libro['portada_id']) else default_cover, width=200)
            with col_info:
                st.write(f"**Título:** {libro['titulo']}")
                st.write(f"**Autor:** {libro['autor']}")
                st.write(f"**Editorial:** {libro['editorial']}")
                st.write(f"**Año de publicación:** {libro['anio_publicacion']}")
                st.write(f"**ISBN:** {libro['isbn']}")
                st.write(f"**Categoría:** {libro['categoria']}")
                st.write(f"**Ejemplares totales:** {libro['ejemplares_totales']}")
                st.write(f"**Ejemplares disponibles:** {libro['ejemplares_disponibles']}")
            
            if st.button("Cerrar Detalles"):
                st.session_state.active_card = None
                st.session_state.selected_libro = None
                st.rerun()

    # ========================
    # TAB 2: AGREGAR NUEVO LIBRO
    # ========================
    if is_admin_bibliotecario:
        with tab2:
            st.write("### Agregar Nuevo Libro")
            with st.form("add_book_form"):
                autores = db_manager.execute_query("SELECT autor_id, nombre_completo FROM autores ORDER BY nombre_completo")
                categorias = db_manager.execute_query("SELECT categoria_id, nombre FROM categorias ORDER BY nombre")
                
                autor = st.selectbox("Autor", [a['nombre_completo'] for a in autores]) if autores else st.text_input("Autor (ninguno registrado)")
                categoria = st.selectbox("Categoría", [c['nombre'] for c in categorias]) if categorias else st.text_input("Categoría (ninguna registrada)")
                
                titulo = st.text_input("Título")
                editorial = st.text_input("Editorial")
                anio = st.number_input("Año de Publicación", min_value=1500, max_value=datetime.now().year, value=datetime.now().year)
                isbn = st.text_input("ISBN")
                ejemplares = st.number_input("Ejemplares Totales", min_value=1, value=1)
                portada_file = st.file_uploader("Subir Portada (JPG, PNG)", type=["jpg", "jpeg", "png"])
                
                if st.form_submit_button("Agregar Libro"):
                    valid, msg = validar_campo(titulo, "texto")
                    if not valid: return show_sweet_alert("Error", f"Título inválido. {msg}", "error")
                    valid, msg = validar_campo(editorial, "texto")
                    if not valid: return show_sweet_alert("Error", f"Editorial inválida. {msg}", "error")
                    if isbn:
                        valid, msg = validar_campo(isbn, "isbn")
                        if not valid: return show_sweet_alert("Error", msg, "error")
                    
                    # Validación de duplicados antes de insertar
                    autor_id = next((a['autor_id'] for a in autores if a['nombre_completo'] == autor), None)
                    categoria_id = next((c['categoria_id'] for c in categorias if c['nombre'] == categoria), None)
                    
                    # Verificar si ya existe un libro con los mismos datos exactos (título + autor + editorial + año)
                    dup_count = db_manager.execute_query(
                        "SELECT COUNT(*) FROM libros WHERE titulo=%s AND autor_id=%s AND editorial=%s AND anio_publicacion=%s",
                        (titulo, autor_id, editorial, anio)
                    )
                    if dup_count and dup_count[0]['COUNT(*)'] > 0:
                        return show_sweet_alert("Error", "Ya existe un libro con el mismo título, autor, editorial y año.", "error")
                    
                    # Verificar ISBN único
                    if isbn:
                        isbn_count = db_manager.execute_query("SELECT COUNT(*) FROM libros WHERE isbn = %s", (isbn,))
                        if isbn_count and isbn_count[0]['COUNT(*)'] > 0:
                            return show_sweet_alert("Error", f"Ya existe otro libro con el ISBN '{isbn}'.", "error")
                    
                    # Portada
                    portada_id = default_cover
                    if portada_file:
                        success, message = image_manager.validate_image(portada_file)
                        if success:
                            portada_id = image_manager.save_image(portada_file, 'libro', 'temp_id')
                        else:
                            return show_sweet_alert("Error de Imagen", message, "error")
                    
                    try:
                        db_manager.execute_query(
                            """INSERT INTO libros (titulo, autor_id, editorial, anio_publicacion, isbn, 
                                                   ejemplares_totales, ejemplares_disponibles, categoria_id, portada_id) 
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                            (titulo, autor_id, editorial, anio, isbn, ejemplares, ejemplares, categoria_id, portada_id),
                            return_result=False
                        )
                        show_sweet_alert("Éxito", "Libro agregado correctamente.", "success")
                    except Exception as e:
                        if portada_file and portada_id != default_cover: image_manager.delete_image_by_path(portada_id)
                        show_sweet_alert("Error de Base de Datos", str(e), "error")

    # ========================
    # TAB 3: GESTIÓN AUTORES Y CATEGORÍAS 
    # ========================
    if is_admin_bibliotecario:
        with tab3:
            st.write("### Gestión de Autores y Categorías")
            subtab1, subtab2 = st.tabs(["Autores", "Categorías"])

            # ---- AUTORES ----
            with subtab1:
                st.write("#### Autores Registrados")
                autores = db_manager.execute_query("SELECT * FROM autores ORDER BY nombre_completo")
                
                if autores:
                    autores_df = pd.DataFrame(autores)
                    autores_df = autores_df.rename(columns={
                        'autor_id': 'ID',
                        'nombre_completo': 'Nombre Completo'
                    })
                    
                    # Mostrar tabla con opciones de edición/eliminación
                    for index, autor_row in autores_df.iterrows():
                        col1, col2, col3 = st.columns([3, 1, 1])
                        with col1:
                            st.write(f"**{autor_row['Nombre Completo']}**")
                        with col2:
                            if st.button("Editar", key=f"edit_autor_{autor_row['ID']}"):
                                st.session_state.editing_autor = autor_row['ID']
                                st.rerun()
                        with col3:
                            # Lógica de confirmación para eliminar autor
                            if st.session_state.confirm_delete_autor == autor_row['ID']:
                                if st.button("Confirmar", key=f"confirm_delete_autor_{autor_row['ID']}"):
                                    # Verificar si el autor está siendo usado
                                    uso_count = db_manager.execute_query(
                                        "SELECT COUNT(*) FROM libros WHERE autor_id = %s", 
                                        (autor_row['ID'],)
                                    )
                                    if uso_count and uso_count[0]['COUNT(*)'] > 0:
                                        show_sweet_alert("Error", "No se puede eliminar este autor porque está siendo usado en libros.", "error")
                                        st.session_state.confirm_delete_autor = None
                                    else:
                                        try:
                                            db_manager.execute_query("DELETE FROM autores WHERE autor_id = %s", (autor_row['ID'],), return_result=False)
                                            show_sweet_alert("Éxito", "Autor eliminado correctamente.", "success")
                                            st.session_state.confirm_delete_autor = None
                                        except Exception as e:
                                            show_sweet_alert("Error", f"Error al eliminar autor: {str(e)}", "error")
                                            st.session_state.confirm_delete_autor = None
                                elif st.button("Cancelar", key=f"cancel_delete_autor_{autor_row['ID']}"):
                                    st.session_state.confirm_delete_autor = None
                                    st.rerun()
                            else:
                                if st.button("Eliminar", key=f"delete_autor_{autor_row['ID']}"):
                                    st.session_state.confirm_delete_autor = autor_row['ID']
                                    st.rerun()
                        st.write("---")

                # Formulario para agregar o editar autor
                with st.form("autor_form"):
                    if st.session_state.editing_autor:
                        st.write("#### Editar Autor")
                        autor_actual = db_manager.execute_query(
                            "SELECT nombre_completo FROM autores WHERE autor_id = %s", 
                            (st.session_state.editing_autor,)
                        )
                        nombre_actual = autor_actual[0]['nombre_completo'] if autor_actual else ""
                        nuevo_nombre = st.text_input("Nombre del Autor", value=nombre_actual)
                    else:
                        st.write("#### Agregar Nuevo Autor")
                        nuevo_nombre = st.text_input("Nombre del Autor")

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("Guardar"):
                            if not nuevo_nombre.strip():
                                show_sweet_alert("Error", "El nombre del autor no puede estar vacío.", "error")
                            else:
                                valid, msg = validar_campo(nuevo_nombre, "nombre")
                                if not valid:
                                    show_sweet_alert("Error", msg, "error")
                                else:
                                    try:
                                        if st.session_state.editing_autor:
                                            # Verificar si ya existe otro autor con el mismo nombre
                                            exists = db_manager.execute_query(
                                                "SELECT COUNT(*) FROM autores WHERE LOWER(nombre_completo) = LOWER(%s) AND autor_id != %s", 
                                                (nuevo_nombre, st.session_state.editing_autor)
                                            )
                                            if exists and exists[0]['COUNT(*)'] > 0:
                                                show_sweet_alert("Error", "Ya existe otro autor con este nombre.", "error")
                                            else:
                                                # Editar autor existente
                                                db_manager.execute_query(
                                                    "UPDATE autores SET nombre_completo = %s WHERE autor_id = %s",
                                                    (nuevo_nombre, st.session_state.editing_autor),
                                                    return_result=False
                                                )
                                                show_sweet_alert("Éxito", "Autor actualizado correctamente.", "success")
                                                st.session_state.editing_autor = None
                                        else:
                                            # Agregar nuevo autor
                                            exists = db_manager.execute_query(
                                                "SELECT COUNT(*) FROM autores WHERE LOWER(nombre_completo) = LOWER(%s)", 
                                                (nuevo_nombre,)
                                            )
                                            if exists and exists[0]['COUNT(*)'] > 0:
                                                show_sweet_alert("Error", "Ya existe un autor con este nombre.", "error")
                                            else:
                                                db_manager.execute_query(
                                                    "INSERT INTO autores (nombre_completo) VALUES (%s)", 
                                                    (nuevo_nombre,), 
                                                    return_result=False
                                                )
                                                show_sweet_alert("Éxito", "Autor agregado correctamente.", "success")
                                    except Exception as e:
                                        show_sweet_alert("Error de Base de Datos", str(e), "error")
                    
                    with col2:
                        if st.session_state.editing_autor:
                            if st.form_submit_button("Cancelar"):
                                st.session_state.editing_autor = None
                                st.rerun()

            # ---- CATEGORÍAS ----
            with subtab2:
                st.write("#### Categorías Registradas")
                categorias = db_manager.execute_query("SELECT * FROM categorias ORDER BY nombre")
                
                if categorias:
                    categorias_df = pd.DataFrame(categorias)
                    categorias_df = categorias_df.rename(columns={
                        'categoria_id': 'ID',
                        'nombre': 'Nombre'
                    })
                    
                    # Mostrar tabla con opciones de edición/eliminación
                    for index, categoria_row in categorias_df.iterrows():
                        col1, col2, col3 = st.columns([3, 1, 1])
                        with col1:
                            st.write(f"**{categoria_row['Nombre']}**")
                        with col2:
                            if st.button("Editar", key=f"edit_cat_{categoria_row['ID']}"):
                                st.session_state.editing_categoria = categoria_row['ID']
                                st.rerun()
                        with col3:
                            # Lógica de confirmación para eliminar categoría
                            if st.session_state.confirm_delete_categoria == categoria_row['ID']:
                                if st.button("Confirmar", key=f"confirm_delete_cat_{categoria_row['ID']}"):
                                    # Verificar si la categoría está siendo usada
                                    uso_count = db_manager.execute_query(
                                        "SELECT COUNT(*) FROM libros WHERE categoria_id = %s", 
                                        (categoria_row['ID'],)
                                    )
                                    if uso_count and uso_count[0]['COUNT(*)'] > 0:
                                        show_sweet_alert("Error", "No se puede eliminar esta categoría porque está siendo usada en libros.", "error")
                                        st.session_state.confirm_delete_categoria = None
                                    else:
                                        try:
                                            db_manager.execute_query("DELETE FROM categorias WHERE categoria_id = %s", (categoria_row['ID'],), return_result=False)
                                            show_sweet_alert("Éxito", "Categoría eliminada correctamente.", "success")
                                            st.session_state.confirm_delete_categoria = None
                                        except Exception as e:
                                            show_sweet_alert("Error", f"Error al eliminar categoría: {str(e)}", "error")
                                            st.session_state.confirm_delete_categoria = None
                                elif st.button("Cancelar", key=f"cancel_delete_cat_{categoria_row['ID']}"):
                                    st.session_state.confirm_delete_categoria = None
                                    st.rerun()
                            else:
                                if st.button("Eliminar", key=f"delete_cat_{categoria_row['ID']}"):
                                    st.session_state.confirm_delete_categoria = categoria_row['ID']
                                    st.rerun()
                        st.write("---")

                # Formulario para agregar o editar categoría
                with st.form("categoria_form"):
                    if st.session_state.editing_categoria:
                        st.write("#### Editar Categoría")
                        categoria_actual = db_manager.execute_query(
                            "SELECT nombre FROM categorias WHERE categoria_id = %s", 
                            (st.session_state.editing_categoria,)
                        )
                        nombre_actual = categoria_actual[0]['nombre'] if categoria_actual else ""
                        nuevo_nombre = st.text_input("Nombre de la Categoría", value=nombre_actual)
                    else:
                        st.write("#### Agregar Nueva Categoría")
                        nuevo_nombre = st.text_input("Nombre de la Categoría")

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("Guardar"):
                            if not nuevo_nombre.strip():
                                show_sweet_alert("Error", "El nombre de la categoría no puede estar vacío.", "error")
                            else:
                                valid, msg = validar_campo(nuevo_nombre, "nombre")
                                if not valid:
                                    show_sweet_alert("Error", msg, "error")
                                else:
                                    try:
                                        if st.session_state.editing_categoria:
                                            # Verificar si ya existe otra categoría con el mismo nombre
                                            exists = db_manager.execute_query(
                                                "SELECT COUNT(*) FROM categorias WHERE LOWER(nombre) = LOWER(%s) AND categoria_id != %s", 
                                                (nuevo_nombre, st.session_state.editing_categoria)
                                            )
                                            if exists and exists[0]['COUNT(*)'] > 0:
                                                show_sweet_alert("Error", "Ya existe otra categoría con este nombre.", "error")
                                            else:
                                                # Editar categoría existente
                                                db_manager.execute_query(
                                                    "UPDATE categorias SET nombre = %s WHERE categoria_id = %s",
                                                    (nuevo_nombre, st.session_state.editing_categoria),
                                                    return_result=False
                                                )
                                                show_sweet_alert("Éxito", "Categoría actualizada correctamente.", "success")
                                                st.session_state.editing_categoria = None
                                        else:
                                            # Agregar nueva categoría
                                            exists = db_manager.execute_query(
                                                "SELECT COUNT(*) FROM categorias WHERE LOWER(nombre) = LOWER(%s)", 
                                                (nuevo_nombre,)
                                            )
                                            if exists and exists[0]['COUNT(*)'] > 0:
                                                show_sweet_alert("Error", "Ya existe una categoría con este nombre.", "error")
                                            else:
                                                db_manager.execute_query(
                                                    "INSERT INTO categorias (nombre) VALUES (%s)", 
                                                    (nuevo_nombre,), 
                                                    return_result=False
                                                )
                                                show_sweet_alert("Éxito", "Categoría agregada correctamente.", "success")
                                    except Exception as e:
                                        show_sweet_alert("Error de Base de Datos", str(e), "error")
                    
                    with col2:
                        if st.session_state.editing_categoria:
                            if st.form_submit_button("Cancelar"):
                                st.session_state.editing_categoria = None
                                st.rerun()
