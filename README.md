# 📚 Sistema de Gestión de Biblioteca

## 🎯 Propósito del proyecto 

Diseñar e implementar un **sistema web de gestión bibliotecaria** que centralice y automatice los procesos clave —**autenticación por roles, catálogo, préstamos, devoluciones, reservas, sanciones, notificaciones por email, reportes y gráficos**— utilizando **Python + Streamlit** y **MySQL**, con **seguridad JWT**, **PDFs** y **métricas operativas** en tiempo real.

### Objetivo general
Digitalizar el ciclo completo de la biblioteca para **acelerar la atención**, **reducir errores** e **incrementar la puntualidad de devoluciones**, garantizando **integridad de datos**, **trazabilidad** y **experiencia clara** para administradores, bibliotecarios y usuarios finales (estudiantes/docentes).

### Objetivos específicos
- **Eficiencia operativa:** registrar préstamos/devoluciones en minutos con validaciones de stock, horario y sanciones.
- **Prevención de morosidad:** recordatorios y alertas por email (por vencer, vencidos, reservas pendientes).
- **Calidad del inventario:** bloqueo seguro de eliminaciones con relaciones y control de duplicados (ISBN).
- **Autonomía del usuario:** panel personal con **mis préstamos**, **mis reservas**, **mis sanciones** y descargas en PDF.
- **Gestión basada en datos:** reportes y **gráficos multicolor** (en español) por mes/categoría/facultad/top libros.
- **Seguridad y cumplimiento:** **JWT**, contraseñas con **SHA-256**, permisos por rol y logs de notificaciones.
- **Despliegue simple:** configuración por `secrets.toml` (MySQL, JWT, SMTP) y plantillas de correo parametrizables.

### Alcance funcional (versión actual)
- **Incluye:** usuarios/roles, catálogo, préstamos/devoluciones, reservas, sanciones, notificaciones SMTP, reportes PDF, gráficos, perfil de usuario, configuración en vivo.
- **No incluye (por ahora):** pasarela de pagos de multas, lector físico de códigos de barras, app móvil nativa (el enfoque es **web first**; podría integrarse a futuro).

### Indicadores de éxito (KPIs sugeridos)
- ⏱️ **Tiempo medio de atención** por préstamo/devolución.  
- 📈 **% de devoluciones a tiempo** y **reducción de atrasos** mes a mes.  
- 📬 **Tasa de apertura** de emails de recordatorio/atraso.  
- 📚 **Exactitud del inventario** (coincidencia físico–sistema).  
- 🧑‍💻 **Préstamos/hora por operador** y **errores bloqueados** por reglas.  

---

## 🔐 Autenticación y autorización

- ⏱️ **JWT (24 h)** con **renovación automática** al acercarse el vencimiento.
- 🔒 Contraseñas con **hash SHA-256**.
- 🔑 Login por **username**, **email** o **código UNT**.
- 🎓 Estudiantes: email institucional automático `g{código}@unitru.edu.pe`.
- ✅ **Validación de cuentas** a cargo de bibliotecarios.
- 🧭 **`require_auth`** con control **estricto por rol**.

---

## 👥 Gestión de usuarios

**Admin**
- ➕ Alta de **bibliotecarios**, 🔍 búsqueda, ✅ validar / 🚫 activar-desactivar, 🔁 cambiar rol y 🗑️ eliminar.
- 🔐 Generación de **contraseñas seguras**.
- 🧪 Validaciones: **DNI (8 dígitos)**, **nombre (solo letras)**, **username (≥ 4)**.

**Bibliotecario**
- 👩‍🎓 Gestión de **estudiantes y docentes**.
- 📨 **Valida** cuentas pendientes.

**Usuario (dashboard `usuario.py`)**
- ✏️ Edita **perfil** y consulta **mis préstamos**, **mis reservas**, **mis sanciones**.
- 🧾 Descarga **reportes personales**.

---

## 📚 Libros

- 🔎 Búsqueda por **título / autor / ISBN / categoría** y vista detallada.
- 🧩 CRUD de **libros**, **autores** y **categorías**.
- 🧱 **Bloqueos inteligentes**: no se elimina si hay **préstamos activos**, **historial** o **reservas**.
- 🖼️ Subida de **portadas (JPG/PNG)** con validación y **fallback** `assets/default_cover`.

---

## 📖 Préstamos

- 🗂️ Cards **paginadas** de libros, selector de **usuario** y **operador**.
- 🔁 **Devoluciones** con estados: **devuelto / dañado / perdido**.
- 🕒 **Horario**: **07:00–14:45 (America/Lima)**.
- 🛡️ Reglas: **bloqueo por sanciones**, validación de **stock** y **duplicados**.
- 📈 **Métricas rápidas** y **anulación segura** de préstamos activos.

---

## 📌 Reservas

- 🧾 Ver pendientes, **entregar** (convierte a préstamo) o **cancelar**.
- 🛠️ Crear reservas **manuales** para usuarios.
- 👤 Usuario: **reservar** y ver **mis reservas**.
- 📦 **Cupo** = disponibles − pendientes.
- ⏳ **Expiran automáticamente** (configurable).
- 🚫 **Bloqueo por sanciones**.

---

## ⚠️ Sanciones

- 👁️‍🗨️ Ver **activas** e **histórico**.
- ➕ **Crear** (días, monto, motivo) y 🟢 **condonar/finalizar**.
- 👤 Usuario: consulta **sus sanciones** (activas e histórico).

---

## 📊 Reportes y gráficos

- 📅 Reportes por rango: **activos**, **atrasados**, **devueltos**, **top libros**, **top usuarios**, **sanciones**, **reservas**, **inventario**.
- 🖼️ Gráficos **multicolor** (matplotlib) y en **español**:
  - por **mes**, **categoría**, **facultad**
  - **Top 10** libros
  - **Préstamos vs reservas**
  - **Sanciones** por estado/mes
- ⬇️ **Descarga en PDF** de tablas y gráficos.

---

## 🏠 Dashboards por rol

- **Admin**: control total (usuarios, libros, préstamos, reservas, sanciones, configuraciones, reportes, gráficos).
- **Bibliotecario**: préstamos/devoluciones, reservas, validaciones, libros, sanciones, gráficos y **notificaciones**.
- **Estudiante/Docente**: catálogo y panel personal (préstamos / reservas / sanciones / reportes).

---

## 🧰 Utilidades y servicios (módulos clave)

- **`utils/alert_utils.py`** → `show_sweet_alert(title, text, icon)` con tema **claro/oscuro** y estilos para **success / error / warning / info**.
- **`utils/alerts.py`** → Detecta **por vencer**, **vencidos**, **reservas por expirar**; muestra en UI y **envía correos** (sin duplicar en el día).
- **`utils/email_manager.py`** → SMTP con **TLS**, plantillas **Jinja** o HTML, **envío masivo** y registro en `notificaciones` (si existe).
- **`utils/image_manager.py`** → Valida **extensión** y **peso**, guarda con nombre único, **elimina** obsoletos, usa **default_cover** si falta.
- **`utils/reports.py`** → Exportación **PDF** robusta (ReportLab ⚑ / FPDF fallback), encabezados en **español**, fechas **12 h (Lima)**, tablas anchas en **apaisado**.
- **`database/models.py`** → Esquema: `usuarios`, `libros`, `autores`, `categorias`, `prestamos`, `reservas`, `sanciones`, `configuracion`, `sedes`, `facultades`, `escuelas`, `notificaciones` (+ *seeds*).
- **`database/procedures.py`** → Procedimientos:
  - `registrar_prestamo(libro, usuario, operador, cantidad)`
  - `registrar_devolucion(prestamo, estado, observaciones)`
  - `eliminar_prestamo_activo(prestamo)`
  - `eliminar_libro_y_prestamos(libro)`

---

## ⚙️ Configuración de variables (MySQL, JWT, SMTP y App)

> 💡 **Recomendado**: usar `/.streamlit/secrets.toml` (no lo subas a git).

```toml
# 📦 Base de datos MySQL
DB_HOST = "TU_HOST"
DB_NAME = "TU_DB"
DB_USER = "TU_USUARIO"
DB_PASSWORD = "TU_PASSWORD"
DB_PORT = 3306

# 🔐 JWT
JWT_SECRET = "CAMBIA-ESTA-CLAVE-LARGA-Y-ALEATORIA"

# ✉️ SMTP (Mailtrap, Gmail, Outlook, etc.)
SMTP_SERVER = "smtp.TU_PROVEEDOR.com"
SMTP_PORT = 587
SMTP_USERNAME = "TU_USUARIO_SMTP"
SMTP_PASSWORD = "TU_PASSWORD_SMTP"
SMTP_USE_TLS = true
SMTP_FROM_NAME = "Biblioteca UNT"
SMTP_FROM_EMAIL = "no-reply@TU-DOMINIO.edu"

# 🛠️ App
MAX_FILE_SIZE_MB = 5
ALLOWED_IMAGE_EXTENSIONS = "jpg,jpeg,png,gif"
APP_NAME = "Sistema de Gestión de Biblioteca"
APP_VERSION = "1.0.0"

## 📜 Licencia
MIT License – Ver LICENSE para detalles completos.

Nota: Proyecto desarrollado con fines academicos.

## 👩‍💻 Autores

1. José Andrés Farro Lagos - Universidad Nacional de Trujillo
2. Stefany Marisel Pérez Bazán - Universidad Nacional de Trujillo
3.   **Asesor:** Dr. Juan Pedro Santos Fernández - Universidad Nacional de Trujillo