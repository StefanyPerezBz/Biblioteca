# src/database/procedures.py
# ------------------------------------------------------------
# Procedimientos almacenados MySQL (con soporte de cantidad)
# - registrar_prestamo(p_libro_id, p_usuario_id, p_bibliotecario_id, p_cantidad)
# - registrar_devolucion(p_prestamo_id, p_estado_libro, p_observaciones)
# - eliminar_prestamo_activo(p_prestamo_id)
# - eliminar_libro_y_prestamos(p_libro_id)   
# ------------------------------------------------------------
from src.database.database import DatabaseManager
from src.utils.alert_utils import show_sweet_alert

def create_procedures() -> bool:
    """Crea o actualiza los procedimientos almacenados requeridos."""
    db = DatabaseManager()
    conn = db.get_connection()
    if conn is None:
        show_sweet_alert("Error", "No se pudo conectar a la base de datos", "error")
        return False

    try:
        cur = conn.cursor()

        cur.execute("""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'prestamos'
              AND COLUMN_NAME = 'cantidad'
        """)
        if cur.fetchone()[0] == 0:
            cur.execute("ALTER TABLE prestamos ADD COLUMN cantidad INT NOT NULL DEFAULT 1")

        # ============================== registrar_prestamo ==============================
        cur.execute("DROP PROCEDURE IF EXISTS registrar_prestamo")
        cur.execute("""
        CREATE PROCEDURE registrar_prestamo(
            IN p_libro_id INT,
            IN p_usuario_id INT,
            IN p_bibliotecario_id INT,
            IN p_cantidad INT
        )
        BEGIN
            -- Variables del prestatario (destinatario)
            DECLARE v_rol VARCHAR(20);
            DECLARE v_dias_prestamo INT;
            DECLARE v_max_prestamos INT;
            DECLARE v_prestamos_activos INT;

            -- Variables del libro/stock
            DECLARE v_ejemplares_disponibles INT;
            DECLARE v_fecha_devolucion_estimada BIGINT;
            DECLARE v_fecha_limite DATE; -- para fijar la hora 14:45

            -- Variables del operador (quien registra)
            DECLARE v_op_rol VARCHAR(20);
            DECLARE v_op_activo BOOLEAN;
            DECLARE v_op_validado BOOLEAN;

            -- Variables de horario
            DECLARE v_now TIME;

            -- ===== Horario permitido: 07:00:00 a 14:45:00 =====
            SET v_now = CURTIME();
            IF NOT (v_now >= '07:00:00' AND v_now <= '14:45:00') THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'Los préstamos solo se registran entre 07:00 AM y 02:45 PM';
            END IF;

            -- Validaciones básicas
            IF p_cantidad IS NULL OR p_cantidad <= 0 THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'La cantidad debe ser mayor a 0';
            END IF;

            IF p_bibliotecario_id = p_usuario_id THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El operador no puede prestarse libros a sí mismo';
            END IF;

            -- Validar operador: admin activo o bibliotecario activo y validado
            SELECT role, activo, COALESCE(validado, FALSE)
              INTO v_op_rol, v_op_activo, v_op_validado
              FROM usuarios
             WHERE user_id = p_bibliotecario_id;

            IF v_op_rol IS NULL OR v_op_activo = FALSE THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Operador inválido o inactivo';
            END IF;

            IF v_op_rol NOT IN ('admin','bibliotecario') THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El operador debe ser admin o bibliotecario';
            END IF;

            IF v_op_rol = 'bibliotecario' AND v_op_validado = FALSE THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El bibliotecario operador debe estar validado';
            END IF;

            -- Disponibilidad del libro (solo activos con stock)
            SELECT ejemplares_disponibles
              INTO v_ejemplares_disponibles
              FROM libros
             WHERE libro_id = p_libro_id
               AND activo = TRUE;

            IF v_ejemplares_disponibles IS NULL THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Libro no encontrado o inactivo';
            END IF;

            IF v_ejemplares_disponibles < p_cantidad THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'No hay ejemplares suficientes para la cantidad solicitada';
            END IF;

            -- Rol del DESTINATARIO
            SELECT role
              INTO v_rol
              FROM usuarios
             WHERE user_id = p_usuario_id
               AND activo = TRUE;

            IF v_rol IS NULL THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Usuario no encontrado o inactivo';
            END IF;

            -- Solo estudiante/docente pueden ser prestatarios
            IF v_rol NOT IN ('estudiante','docente') THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Solo docentes o estudiantes pueden recibir préstamos';
            END IF;

            -- Sanción vigente
            IF EXISTS (
                SELECT 1 FROM usuarios
                 WHERE user_id = p_usuario_id
                   AND sancionado = TRUE
                   AND (fecha_fin_sancion IS NULL OR fecha_fin_sancion > UNIX_TIMESTAMP())
            ) THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Usuario con sanción vigente';
            END IF;

            -- Configuración por rol
            IF v_rol = 'estudiante' THEN
                SELECT CAST(valor AS UNSIGNED) INTO v_dias_prestamo FROM configuracion WHERE parametro = 'dias_prestamo_estudiante';
                SELECT CAST(valor AS UNSIGNED) INTO v_max_prestamos FROM configuracion WHERE parametro = 'max_prestamos_estudiante';
            ELSE
                SELECT CAST(valor AS UNSIGNED) INTO v_dias_prestamo FROM configuracion WHERE parametro = 'dias_prestamo_docente';
                SELECT CAST(valor AS UNSIGNED) INTO v_max_prestamos FROM configuracion WHERE parametro = 'max_prestamos_docente';
            END IF;

            -- Límite de préstamos activos
            SELECT COUNT(*) INTO v_prestamos_activos
              FROM prestamos
             WHERE usuario_id = p_usuario_id
               AND estado = 'activo';

            IF v_prestamos_activos >= v_max_prestamos THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El usuario ha superado el límite de préstamos activos';
            END IF;

            -- Evitar préstamo activo duplicado del mismo libro
            IF EXISTS (
                SELECT 1 FROM prestamos
                 WHERE usuario_id = p_usuario_id
                   AND libro_id = p_libro_id
                   AND estado = 'activo'
            ) THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'No se puede prestar el mismo libro: ya existe un préstamo activo de este título para el usuario';
            END IF;

            -- Fecha estimada de devolución:
            -- Día límite = hoy + v_dias_prestamo, hora fija 14:45:00 (2:45 PM)
            SET v_fecha_limite = DATE(FROM_UNIXTIME(UNIX_TIMESTAMP() + v_dias_prestamo * 86400));
            SET v_fecha_devolucion_estimada = UNIX_TIMESTAMP(
                STR_TO_DATE(CONCAT(DATE_FORMAT(v_fecha_limite, '%Y-%m-%d'), ' 14:45:00'), '%Y-%m-%d %H:%i:%s')
            );

            -- Registrar préstamo
            INSERT INTO prestamos (
                libro_id, usuario_id, bibliotecario_id,
                fecha_prestamo, fecha_devolucion_estimada,
                estado, cantidad
            )
            VALUES (
                p_libro_id, p_usuario_id, p_bibliotecario_id,
                UNIX_TIMESTAMP(), v_fecha_devolucion_estimada,
                'activo', p_cantidad
            );

            -- Descontar stock: disponibles y totales
            UPDATE libros
               SET ejemplares_disponibles = ejemplares_disponibles - p_cantidad,
                   ejemplares_totales     = ejemplares_totales     - p_cantidad
             WHERE libro_id = p_libro_id;

            SELECT 1 AS success;
        END
        """)

        # ============================== registrar_devolucion ==============================
        cur.execute("DROP PROCEDURE IF EXISTS registrar_devolucion")
        cur.execute("""
        CREATE PROCEDURE registrar_devolucion(
            IN p_prestamo_id INT,
            IN p_estado_libro VARCHAR(20),
            IN p_observaciones TEXT
        )
        BEGIN
            -- Variables al inicio (regla MySQL)
            DECLARE v_libro_id INT;
            DECLARE v_usuario_id INT;
            DECLARE v_fecha_devolucion_estimada BIGINT;
            DECLARE v_cantidad INT DEFAULT 1;
            DECLARE v_dias_atraso INT DEFAULT 0;
            DECLARE v_monto_multa DECIMAL(10,2) DEFAULT 0.00;
            DECLARE v_dias_sancion INT DEFAULT 0;
            DECLARE v_fecha_fin_sancion BIGINT;
            DECLARE v_dias_extra INT;
            DECLARE v_costo_perdida DECIMAL(10,2) DEFAULT 0.00;
            DECLARE v_now TIME;

            -- ===== Horario permitido para registrar devoluciones: 07:00:00 a 14:45:00 =====
            SET v_now = CURTIME();
            IF NOT (v_now >= '07:00:00' AND v_now <= '14:45:00') THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'Las devoluciones solo se registran entre 07:00 AM y 02:45 PM';
            END IF;

            -- Datos del préstamo activo
            SELECT libro_id, usuario_id, fecha_devolucion_estimada, cantidad
              INTO v_libro_id, v_usuario_id, v_fecha_devolucion_estimada, v_cantidad
              FROM prestamos
             WHERE prestamo_id = p_prestamo_id
               AND estado = 'activo'
             FOR UPDATE;

            IF v_libro_id IS NULL THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Préstamo no encontrado o ya cerrado';
            END IF;

            -- Cerrar préstamo
            UPDATE prestamos
               SET estado = p_estado_libro,
                   fecha_devolucion_real = UNIX_TIMESTAMP(),
                   observaciones = p_observaciones
             WHERE prestamo_id = p_prestamo_id;

            -- Reponer stock si devuelto en buen estado
            IF p_estado_libro = 'devuelto' THEN
                UPDATE libros
                   SET ejemplares_disponibles = ejemplares_disponibles + v_cantidad,
                       ejemplares_totales     = ejemplares_totales     + v_cantidad
                 WHERE libro_id = v_libro_id;
            END IF;

            -- Multa/Sanción por atraso (si aplica)
            IF UNIX_TIMESTAMP() > v_fecha_devolucion_estimada THEN
                SET v_dias_atraso = FLOOR((UNIX_TIMESTAMP() - v_fecha_devolucion_estimada) / 86400);

                SELECT CAST(valor AS DECIMAL(10,2)) INTO v_monto_multa FROM configuracion WHERE parametro = 'costo_multa_diaria';
                SELECT CAST(valor AS UNSIGNED)   INTO v_dias_sancion FROM configuracion WHERE parametro = 'dias_sancion_atraso';

                SET v_monto_multa = v_monto_multa * v_dias_atraso;
                SET v_fecha_fin_sancion = UNIX_TIMESTAMP() + (v_dias_sancion * v_dias_atraso * 86400);

                INSERT INTO sanciones (usuario_id, prestamo_id, fecha_inicio, fecha_fin, motivo, monto, estado)
                VALUES (v_usuario_id, p_prestamo_id, UNIX_TIMESTAMP(), v_fecha_fin_sancion,
                        CONCAT('Devolución con ', v_dias_atraso, ' días de atraso'), v_monto_multa, 'activa');

                UPDATE usuarios
                   SET sancionado = TRUE,
                       fecha_fin_sancion = v_fecha_fin_sancion
                 WHERE user_id = v_usuario_id;
            END IF;

            -- Sanción por daño o pérdida (no se reponen existencias)
            IF p_estado_libro IN ('dañado','perdido') THEN
                SELECT CAST(valor AS UNSIGNED) INTO v_dias_extra FROM configuracion WHERE parametro = 'dias_sancion_danio_perdida';
                    
                -- Costo por daño/pérdida (por cada ejemplar)
                SELECT CAST(valor AS DECIMAL(10,2))
                  INTO v_costo_perdida
                  FROM configuracion
                WHERE parametro = 'costo_danio_perdida';

                SET v_fecha_fin_sancion = UNIX_TIMESTAMP() + (v_dias_extra * 86400);

                INSERT INTO sanciones (usuario_id, prestamo_id, fecha_inicio, fecha_fin, motivo, monto, estado)
                VALUES (v_usuario_id, p_prestamo_id, UNIX_TIMESTAMP(), v_fecha_fin_sancion,
                        CONCAT('Libro ', p_estado_libro), (v_costo_perdida * v_cantidad), 'activa');

                UPDATE usuarios
                   SET sancionado = TRUE,
                       fecha_fin_sancion = v_fecha_fin_sancion
                 WHERE user_id = v_usuario_id;
            END IF;

            SELECT 1 AS success;
        END
        """)

        # ============================== eliminar_prestamo_activo =========================
        cur.execute("DROP PROCEDURE IF EXISTS eliminar_prestamo_activo")
        cur.execute("""
        CREATE PROCEDURE eliminar_prestamo_activo(
            IN p_prestamo_id INT
        )
        BEGIN
            DECLARE v_libro_id INT;
            DECLARE v_cantidad INT;
            DECLARE v_now TIME;

            -- Horario permitido (igual que préstamo/devolución)
            SET v_now = CURTIME();
            IF NOT (v_now >= '07:00:00' AND v_now <= '14:45:00') THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'La eliminación de préstamos activos solo se registra entre 07:00 AM y 02:45 PM';
            END IF;

            -- Obtener datos del préstamo activo
            SELECT libro_id, cantidad
              INTO v_libro_id, v_cantidad
              FROM prestamos
             WHERE prestamo_id = p_prestamo_id
               AND estado = 'activo'
             FOR UPDATE;

            IF v_libro_id IS NULL THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Préstamo no encontrado o no está activo';
            END IF;

            -- Restaurar stock (como si nunca se hubiera prestado)
            UPDATE libros
               SET ejemplares_disponibles = ejemplares_disponibles + v_cantidad,
                   ejemplares_totales     = ejemplares_totales     + v_cantidad
             WHERE libro_id = v_libro_id;

            -- Eliminar físicamente el préstamo
            DELETE FROM prestamos
             WHERE prestamo_id = p_prestamo_id
               AND estado = 'activo';

            SELECT 1 AS success;
        END
        """)

        # ============================== eliminar_libro_y_prestamos ===============
        cur.execute("DROP PROCEDURE IF EXISTS eliminar_libro_y_prestamos")
        cur.execute("""
        CREATE PROCEDURE eliminar_libro_y_prestamos(
            IN p_libro_id INT
        )
        BEGIN
            DECLARE v_existe INT DEFAULT 0;

            DECLARE EXIT HANDLER FOR SQLEXCEPTION
            BEGIN
                ROLLBACK;
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'Error eliminando libro y préstamos relacionados';
            END;

            -- Verificar que el libro exista
            SELECT COUNT(*) INTO v_existe FROM libros WHERE libro_id = p_libro_id;
            IF v_existe = 0 THEN
                SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'El libro no existe';
            END IF;

            START TRANSACTION;

                -- Conservar sanciones, pero sin vínculo al préstamo eliminado
                UPDATE sanciones
                   SET prestamo_id = NULL
                 WHERE prestamo_id IN (SELECT prestamo_id FROM prestamos WHERE libro_id = p_libro_id);

                -- Eliminar reservas del libro
                DELETE FROM reservas
                 WHERE libro_id = p_libro_id;

                -- Eliminar préstamos del libro (activos o no)
                DELETE FROM prestamos
                 WHERE libro_id = p_libro_id;

                -- Eliminar el libro
                DELETE FROM libros
                 WHERE libro_id = p_libro_id;

            COMMIT;

            SELECT 1 AS success;
        END
        """)

        conn.commit()
        show_sweet_alert("Procedimientos listos", "Procedimientos almacenados creados/actualizados con éxito.", "success")
        return True
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        show_sweet_alert("Error", f"Error creando procedimientos: {e}", "error")
        return False
    finally:
        try:
            cur.close()
        except Exception:
            pass
