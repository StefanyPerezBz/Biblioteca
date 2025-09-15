# src/utils/image_manager.py - Gestión de imágenes
import os
import streamlit as st
from PIL import Image as PILImage
import base64
import time
from src.database.database import DatabaseManager
from src.utils.alert_utils import show_sweet_alert

class ImageManager:
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.upload_folder = "uploads"
        if not os.path.exists(self.upload_folder):
            os.makedirs(self.upload_folder)

    def get_default_cover(self):
       """Retorna la ruta de la imagen por defecto para portadas de libros"""
       return "assets/default_cover.jpg"

    def validate_image(self, image_file):
        """Valida que el archivo sea una imagen y cumpla con los requisitos"""
        try:
            # Verificar extensión
            allowed_extensions = ['jpg', 'jpeg', 'png']
            file_ext = image_file.name.split('.')[-1].lower()
            if file_ext not in allowed_extensions:
                return False, "Formato de archivo no permitido. Use JPG, JPEG o PNG."
            
            # Verificar tamaño (máximo 2MB)
            max_size = 2 * 1024 * 1024
            if image_file.size > max_size:
                return False, f"El archivo es demasiado grande. Tamaño máximo: 2MB."
            
            # Verificar que sea una imagen válida y obtener dimensiones
            image = PILImage.open(image_file)
            image.verify()
            
            return True, "Imagen válida"
        except Exception as e:
            return False, f"Error validando imagen: {str(e)}"
    
    def save_image(self, image_file, entity_type, entity_id):
        try:
            # Validar imagen
            is_valid, message = self.validate_image(image_file)
            if not is_valid:
                show_sweet_alert("Error", message, "error")
                return None
            
            # Generar nombre único para el archivo
            file_ext = image_file.name.split('.')[-1].lower()
            filename = f"{entity_type}_{entity_id}_{int(time.time())}.{file_ext}"
            filepath = os.path.join(self.upload_folder, filename)
            
            # Guardar archivo
            with open(filepath, "wb") as f:
                f.write(image_file.getbuffer())
            
            # Retornar el filepath en lugar del ID para una referencia directa
            return filepath
        except Exception as e:
            show_sweet_alert("Error", f"Error guardando imagen: {e}", "error")
            return None
    
    def delete_image_by_path(self, filepath):
        """Elimina un archivo de imagen dado su filepath."""
        try:
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
                return True
            return False
        except Exception as e:
            show_sweet_alert("Error", f"Error eliminando archivo de imagen: {e}", "error")
            return False
            
    def get_image(self, image_id):
        return None
    
    def get_entity_images(self, entity_type, entity_id):
        return []
    
    def display_image(self, image_data, caption=None, width=200):
        """Muestra una imagen en Streamlit"""
        if image_data:
            st.image(image_data, caption=caption, width=width)
        else:
            st.info("❌ No hay imagen disponible")