import sqlite3
import unicodedata
import json
import hashlib
import secrets
import hmac
import math
from pathlib import Path
from datetime import datetime, timedelta

from app.paths import APPLICATION_FOLDER


DB_FOLDER = APPLICATION_FOLDER / "data"
DB_FILE = DB_FOLDER / "la_esquina.db"


def conectar():
    DB_FOLDER.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE, timeout=15)
    # SQLite no aplica las llaves foraneas de forma predeterminada. Debe
    # habilitarse en cada conexion para impedir detalles, pagos o pedidos
    # asociados a registros inexistentes.
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    # La caja y el servidor movil pueden leer/escribir al mismo tiempo. WAL
    # evita que una lectura bloquee innecesariamente una venta en curso.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def _columna_existe(cur, tabla, columna):
    cur.execute(f"PRAGMA table_info({tabla})")
    columnas = [fila[1] for fila in cur.fetchall()]
    return columna in columnas


def crear_tablas():
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS productos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            precio REAL NOT NULL,
            categoria TEXT DEFAULT 'General',
            activo INTEGER DEFAULT 1,
            orden INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ventas(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            total REAL,
            metodo TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS detalle_venta(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venta_id INTEGER NOT NULL,
            producto TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            precio REAL NOT NULL,
            FOREIGN KEY (venta_id) REFERENCES ventas(id) ON DELETE CASCADE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS venta_pagos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venta_id INTEGER NOT NULL,
            metodo TEXT NOT NULL,
            importe REAL NOT NULL CHECK(importe >= 0),
            FOREIGN KEY (venta_id) REFERENCES ventas(id)
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_venta_pagos_venta
        ON venta_pagos(venta_id)
    """)

    # v1.5 - Gastos. Migracion aditiva: no modifica ni elimina ventas previas.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS gastos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            concepto TEXT NOT NULL,
            categoria TEXT NOT NULL,
            importe REAL NOT NULL CHECK(importe > 0),
            fecha TEXT NOT NULL,
            metodo_pago TEXT NOT NULL,
            estado TEXT NOT NULL DEFAULT 'Activo',
            creado_en TEXT NOT NULL,
            actualizado_en TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS gasto_eventos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gasto_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            fecha_evento TEXT NOT NULL,
            motivo TEXT DEFAULT '',
            datos_anteriores TEXT,
            datos_nuevos TEXT,
            FOREIGN KEY (gasto_id) REFERENCES gastos(id)
        )
    """)

    # Pedidos enviados por celulares o tabletas en la red del restaurante.
    # Son independientes de las ventas hasta que caja los cobra.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pedidos_movil(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            mesa TEXT NOT NULL,
            mesero TEXT NOT NULL,
            notas TEXT DEFAULT '',
            total REAL NOT NULL,
            estado TEXT NOT NULL DEFAULT 'Pendiente',
            estado_cocina TEXT NOT NULL DEFAULT 'Nuevo',
            venta_id INTEGER,
            actualizado_en TEXT NOT NULL,
            cocina_actualizado_en TEXT NOT NULL,
            FOREIGN KEY (venta_id) REFERENCES ventas(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS detalle_pedido_movil(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER NOT NULL,
            producto_id INTEGER NOT NULL,
            producto TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            cantidad_entregada INTEGER NOT NULL DEFAULT 0,
            precio REAL NOT NULL,
            FOREIGN KEY (pedido_id) REFERENCES pedidos_movil(id),
            FOREIGN KEY (producto_id) REFERENCES productos(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS empleados(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE COLLATE NOCASE,
            pin_hash TEXT NOT NULL,
            rol TEXT NOT NULL,
            activo INTEGER NOT NULL DEFAULT 1,
            creado_en TEXT NOT NULL,
            actualizado_en TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS auditoria(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            empleado_id INTEGER,
            empleado TEXT NOT NULL,
            accion TEXT NOT NULL,
            entidad TEXT NOT NULL,
            entidad_id INTEGER,
            detalle TEXT DEFAULT '',
            FOREIGN KEY (empleado_id) REFERENCES empleados(id)
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_auditoria_fecha
        ON auditoria(fecha, id)
    """)

    # Club La Esquina. El celular identifica de forma unica al cliente.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS clientes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            telefono TEXT NOT NULL UNIQUE,
            cumpleanos TEXT DEFAULT '',
            email TEXT DEFAULT '',
            acepta_promociones INTEGER NOT NULL DEFAULT 0,
            puntos INTEGER NOT NULL DEFAULT 0,
            visitas INTEGER NOT NULL DEFAULT 0,
            total_compras REAL NOT NULL DEFAULT 0,
            activo INTEGER NOT NULL DEFAULT 1,
            creado_en TEXT NOT NULL,
            actualizado_en TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cliente_movimientos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            venta_id INTEGER,
            fecha TEXT NOT NULL,
            tipo TEXT NOT NULL,
            puntos INTEGER NOT NULL,
            detalle TEXT DEFAULT '',
            FOREIGN KEY(cliente_id) REFERENCES clientes(id),
            FOREIGN KEY(venta_id) REFERENCES ventas(id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_clientes_telefono ON clientes(telefono)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cliente_movimientos_cliente ON cliente_movimientos(cliente_id, id)")
    if not _columna_existe(cur, "ventas", "cliente_id"):
        cur.execute("ALTER TABLE ventas ADD COLUMN cliente_id INTEGER")

    # Recetas y costos por porcion. Las cantidades se guardan en la unidad
    # base elegida: gramos, mililitros o piezas.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ingredientes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE COLLATE NOCASE,
            unidad TEXT NOT NULL,
            cantidad_compra REAL NOT NULL CHECK(cantidad_compra > 0),
            costo_compra REAL NOT NULL CHECK(costo_compra >= 0),
            merma_pct REAL NOT NULL DEFAULT 0,
            activo INTEGER NOT NULL DEFAULT 1,
            creado_en TEXT NOT NULL,
            actualizado_en TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ingrediente_costos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ingrediente_id INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            cantidad_compra REAL NOT NULL,
            costo_compra REAL NOT NULL,
            merma_pct REAL NOT NULL,
            FOREIGN KEY(ingrediente_id) REFERENCES ingredientes(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS recetas(
            producto_id INTEGER PRIMARY KEY,
            costo_extra REAL NOT NULL DEFAULT 0,
            actualizado_en TEXT NOT NULL,
            FOREIGN KEY(producto_id) REFERENCES productos(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS receta_ingredientes(
            producto_id INTEGER NOT NULL,
            ingrediente_id INTEGER NOT NULL,
            cantidad REAL NOT NULL CHECK(cantidad > 0),
            PRIMARY KEY(producto_id, ingrediente_id),
            FOREIGN KEY(producto_id) REFERENCES productos(id),
            FOREIGN KEY(ingrediente_id) REFERENCES ingredientes(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS preparaciones(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE COLLATE NOCASE,
            unidad TEXT NOT NULL,
            rendimiento REAL NOT NULL CHECK(rendimiento > 0),
            costo_extra REAL NOT NULL DEFAULT 0,
            activo INTEGER NOT NULL DEFAULT 1,
            creado_en TEXT NOT NULL,
            actualizado_en TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS preparacion_ingredientes(
            preparacion_id INTEGER NOT NULL,
            ingrediente_id INTEGER NOT NULL,
            cantidad REAL NOT NULL CHECK(cantidad > 0),
            PRIMARY KEY(preparacion_id, ingrediente_id),
            FOREIGN KEY(preparacion_id) REFERENCES preparaciones(id),
            FOREIGN KEY(ingrediente_id) REFERENCES ingredientes(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS receta_preparaciones(
            producto_id INTEGER NOT NULL,
            preparacion_id INTEGER NOT NULL,
            cantidad REAL NOT NULL CHECK(cantidad > 0),
            PRIMARY KEY(producto_id, preparacion_id),
            FOREIGN KEY(producto_id) REFERENCES productos(id),
            FOREIGN KEY(preparacion_id) REFERENCES preparaciones(id)
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_pedidos_movil_estado_fecha
        ON pedidos_movil(estado, fecha)
    """)

    # Migracion para instalaciones que ya recibieron pedidos moviles.
    if not _columna_existe(cur, "pedidos_movil", "estado_cocina"):
        cur.execute("""
            ALTER TABLE pedidos_movil
            ADD COLUMN estado_cocina TEXT DEFAULT 'Nuevo'
        """)
    if not _columna_existe(cur, "pedidos_movil", "cocina_actualizado_en"):
        cur.execute("""
            ALTER TABLE pedidos_movil
            ADD COLUMN cocina_actualizado_en TEXT DEFAULT ''
        """)
    if not _columna_existe(cur, "pedidos_movil", "empleado_id"):
        cur.execute("ALTER TABLE pedidos_movil ADD COLUMN empleado_id INTEGER")
    if not _columna_existe(cur, "pedidos_movil", "numero_cuentas"):
        cur.execute(
            "ALTER TABLE pedidos_movil ADD COLUMN numero_cuentas INTEGER NOT NULL DEFAULT 1"
        )
    if not _columna_existe(cur, "pedidos_movil", "cuentas_json"):
        cur.execute("ALTER TABLE pedidos_movil ADD COLUMN cuentas_json TEXT DEFAULT ''")
    if not _columna_existe(cur, "pedidos_movil", "cuentas_pagadas_json"):
        cur.execute(
            "ALTER TABLE pedidos_movil ADD COLUMN cuentas_pagadas_json TEXT DEFAULT '[]'"
        )
    if not _columna_existe(cur, "detalle_pedido_movil", "cantidad_entregada"):
        cur.execute("""
            ALTER TABLE detalle_pedido_movil
            ADD COLUMN cantidad_entregada INTEGER NOT NULL DEFAULT 0
        """)
    if not _columna_existe(cur, "productos", "imagen"):
        cur.execute("ALTER TABLE productos ADD COLUMN imagen TEXT DEFAULT ''")
    if not _columna_existe(cur, "ventas", "empleado_id"):
        cur.execute("ALTER TABLE ventas ADD COLUMN empleado_id INTEGER")
    if not _columna_existe(cur, "gastos", "empleado_id"):
        cur.execute("ALTER TABLE gastos ADD COLUMN empleado_id INTEGER")

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_gastos_fecha_estado
        ON gastos(fecha, estado)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_gasto_eventos_gasto
        ON gasto_eventos(gasto_id, id)
    """)

    if not _columna_existe(cur, "ventas", "personas"):
        cur.execute("""
            ALTER TABLE ventas
            ADD COLUMN personas INTEGER DEFAULT 1
        """)

    if not _columna_existe(cur, "ventas", "origen"):
        cur.execute("""
            ALTER TABLE ventas
            ADD COLUMN origen TEXT DEFAULT 'No registrado'
        """)

    # Migraciones seguras de productos
    if not _columna_existe(cur, "productos", "categoria"):
        cur.execute("""
            ALTER TABLE productos
            ADD COLUMN categoria TEXT DEFAULT 'General'
        """)

    if not _columna_existe(cur, "productos", "activo"):
        cur.execute("""
            ALTER TABLE productos
            ADD COLUMN activo INTEGER DEFAULT 1
        """)

    if not _columna_existe(cur, "productos", "orden"):
        cur.execute("""
            ALTER TABLE productos
            ADD COLUMN orden INTEGER DEFAULT 0
        """)

    # Cargar menú inicial únicamente si la tabla está vacía.
    cur.execute("SELECT COUNT(*) FROM productos")
    if cur.fetchone()[0] == 0:
        productos_iniciales = [
            ("Chilaquiles", 150, "Alimentos"),
            ("Chilaquiles Rellenos", 135, "Alimentos"),
            ("Enchiladas Suizas", 130, "Alimentos"),
            ("Torta de Chilaquiles", 80, "Alimentos"),
            ("Omelette", 115, "Alimentos"),
            ("Huevos Rancheros", 100, "Alimentos"),
            ("Sándwich Jamón", 65, "Alimentos"),
            ("Sándwich Chorizo", 75, "Alimentos"),
            ("Pan Francés", 110, "Alimentos"),
            ("Bites 10", 110, "Bites"),
            ("Bites 15", 130, "Bites"),
            ("Bites 20", 150, "Bites"),
            ("Bites 30", 180, "Bites"),
            ("Café", 60, "Bebidas"),
            ("Capuchino", 70, "Bebidas"),
            ("Jugo", 45, "Bebidas"),
            ("Refresco", 30, "Bebidas"),
            ("Agua", 20, "Bebidas"),
            ("Agua de sabor", 30, "Bebidas"),
        ]

        cur.executemany("""
            INSERT INTO productos(nombre, precio, categoria, activo, orden)
            VALUES (?, ?, ?, 1, ?)
        """, [
            (nombre, precio, categoria, indice)
            for indice, (nombre, precio, categoria)
            in enumerate(productos_iniciales, start=1)
        ])

    conn.commit()
    conn.close()


def guardar_venta(productos, total, metodo="Efectivo", personas=1,
                  origen="No registrado", empleado_id=None, pagos=None,
                  cliente_id=None, puntos_usados=0):
    if not isinstance(productos, (list, tuple)) or not productos:
        raise ValueError("Agrega al menos un producto a la venta.")
    try:
        total = float(total)
        personas = int(personas)
        productos_normalizados = [
            (str(nombre).strip(), float(precio))
            for nombre, precio in productos
        ]
    except (TypeError, ValueError):
        raise ValueError("La venta contiene datos no válidos.") from None
    if not math.isfinite(total) or total <= 0:
        raise ValueError("El total de la venta debe ser mayor que cero.")
    if not 1 <= personas <= 50:
        raise ValueError("La venta debe incluir entre 1 y 50 personas.")
    if any(not nombre or not math.isfinite(precio) or precio < 0
           for nombre, precio in productos_normalizados):
        raise ValueError("La venta contiene un producto no válido.")
    total_productos = sum(precio for _nombre, precio in productos_normalizados)
    if abs(total_productos - total) > 0.01:
        raise ValueError("El total no coincide con los productos de la venta.")

    pagos = pagos or [(metodo, total)]
    try:
        pagos_normalizados = [
            (str(metodo_pago), float(importe_pago))
            for metodo_pago, importe_pago in pagos
        ]
    except (TypeError, ValueError):
        raise ValueError("Los pagos contienen datos no válidos.") from None
    try:
        puntos_usados = int(puntos_usados)
    except (TypeError, ValueError):
        raise ValueError("La cantidad de puntos no es válida.") from None
    if puntos_usados < 0:
        raise ValueError("La cantidad de puntos no es válida.")
    valor_puntos = round(puntos_usados * 0.50, 2)
    metodos_validos = ("Efectivo", "Tarjeta", "Transferencia", "Puntos")
    if not pagos_normalizados or any(
        metodo_pago not in metodos_validos
        or not math.isfinite(importe_pago) or importe_pago <= 0
        for metodo_pago, importe_pago in pagos_normalizados
    ):
        raise ValueError("Los pagos contienen un método o importe no válido.")
    if abs(sum(importe for _metodo, importe in pagos_normalizados) - total) > 0.01:
        raise ValueError("Los pagos no coinciden con el total de la venta.")
    importe_puntos = sum(importe for metodo_pago, importe in pagos_normalizados
                         if metodo_pago == "Puntos")
    if abs(importe_puntos - valor_puntos) > 0.01:
        raise ValueError("El valor de los puntos no coincide con el pago.")
    if puntos_usados and cliente_id is None:
        raise ValueError("Selecciona un cliente para utilizar puntos.")

    conn = conectar()
    try:
        cur = conn.cursor()
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        puntos_disponibles = 0
        if cliente_id is not None:
            cur.execute("SELECT activo, puntos FROM clientes WHERE id=?",
                        (int(cliente_id),))
            cliente = cur.fetchone()
            if cliente is None or not cliente[0]:
                raise ValueError("El cliente seleccionado ya no está activo.")
            puntos_disponibles = int(cliente[1])
            if puntos_usados > puntos_disponibles:
                raise ValueError("El cliente ya no tiene suficientes puntos.")
        cur.execute("""
            INSERT INTO ventas
            (fecha, total, metodo, personas, origen, empleado_id, cliente_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (fecha, total, metodo, personas, str(origen), empleado_id, cliente_id))
        venta_id = cur.lastrowid
        cur.executemany("""
            INSERT INTO venta_pagos(venta_id, metodo, importe)
            VALUES (?, ?, ?)
        """, [
            (venta_id, metodo_pago, importe_pago)
            for metodo_pago, importe_pago in pagos_normalizados
        ])
        cur.executemany("""
            INSERT INTO detalle_venta
            (venta_id, producto, cantidad, precio)
            VALUES (?, ?, 1, ?)
        """, [
            (venta_id, nombre, precio)
            for nombre, precio in productos_normalizados
        ])
        if cliente_id is not None:
            importe_pagado = max(0.0, total - valor_puntos)
            puntos = int(importe_pagado // 10)
            cur.execute("""
                UPDATE clientes SET puntos=puntos-?+?, visitas=visitas+1,
                    total_compras=total_compras+?, actualizado_en=? WHERE id=?
            """, (puntos_usados, puntos, total, fecha, int(cliente_id)))
            if puntos_usados:
                cur.execute("""
                    INSERT INTO cliente_movimientos
                    (cliente_id, venta_id, fecha, tipo, puntos, detalle)
                    VALUES (?, ?, ?, 'Canje', ?, ?)
                """, (int(cliente_id), venta_id, fecha, -puntos_usados,
                      f"Pago con puntos ${valor_puntos:.2f}"))
            cur.execute("""
                INSERT INTO cliente_movimientos
                (cliente_id, venta_id, fecha, tipo, puntos, detalle)
                VALUES (?, ?, ?, 'Compra', ?, ?)
            """, (int(cliente_id), venta_id, fecha, puntos,
                  f"Compra ${total:.2f}"))
        conn.commit()
        return venta_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def obtener_ventas_hoy():
    conn = conectar()
    cur = conn.cursor()

    hoy = datetime.now().strftime("%Y-%m-%d")

    cur.execute("""
        SELECT id, fecha, total, metodo, personas, origen
        FROM ventas
        WHERE substr(fecha, 1, 10) = ?
        ORDER BY fecha DESC
    """, (hoy,))

    ventas = cur.fetchall()
    conn.close()
    return ventas


def obtener_resumen_origen_hoy():
    conn = conectar()
    cur = conn.cursor()

    hoy = datetime.now().strftime("%Y-%m-%d")

    cur.execute("""
        SELECT origen, SUM(COALESCE(personas, 1))
        FROM ventas
        WHERE substr(fecha, 1, 10) = ?
        GROUP BY origen
        ORDER BY SUM(COALESCE(personas, 1)) DESC
    """, (hoy,))

    resumen = cur.fetchall()
    conn.close()
    return resumen


def obtener_top_productos_hoy(limite=8):
    conn = conectar()
    cur = conn.cursor()

    hoy = datetime.now().strftime("%Y-%m-%d")

    cur.execute("""
        SELECT d.producto,
               SUM(d.cantidad) AS unidades,
               SUM(d.cantidad * d.precio) AS ingreso
        FROM detalle_venta d
        JOIN ventas v ON v.id = d.venta_id
        WHERE substr(v.fecha, 1, 10) = ?
        GROUP BY d.producto
        ORDER BY unidades DESC, ingreso DESC
        LIMIT ?
    """, (hoy, limite))

    datos = cur.fetchall()
    conn.close()
    return datos


def obtener_resumen_hoy():
    conn = conectar()
    cur = conn.cursor()

    hoy = datetime.now().strftime("%Y-%m-%d")

    cur.execute("""
        SELECT
            COUNT(*) AS tickets,
            COALESCE(SUM(total), 0),
            COALESCE(SUM(COALESCE(personas, 1)), 0)
        FROM ventas
        WHERE substr(fecha, 1, 10) = ?
    """, (hoy,))

    tickets, venta_total, personas = cur.fetchone()
    conn.close()

    ticket_promedio = venta_total / tickets if tickets else 0
    promedio_persona = venta_total / personas if personas else 0

    return {
        "tickets": tickets,
        "venta_total": venta_total,
        "personas": personas,
        "ticket_promedio": ticket_promedio,
        "promedio_persona": promedio_persona,
    }


def obtener_analisis_ventas(fecha_inicio, fecha_fin):
    """Devuelve ventas y estadísticas completas para un rango inclusivo."""
    inicio = str(fecha_inicio).strip()
    fin = str(fecha_fin).strip()
    try:
        inicio_fecha = datetime.strptime(inicio, "%Y-%m-%d").date()
        fin_fecha = datetime.strptime(fin, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("El rango de fechas no es válido.") from None
    if inicio_fecha > fin_fecha:
        raise ValueError("La fecha inicial no puede ser posterior a la final.")

    conn = conectar()
    try:
        cur = conn.cursor()
        parametros = (inicio, fin)
        condicion = "date(substr(fecha, 1, 10)) BETWEEN date(?) AND date(?)"
        cur.execute(f"""
            SELECT COUNT(*), COALESCE(SUM(total), 0),
                   COALESCE(SUM(COALESCE(personas, 1)), 0),
                   COALESCE(MIN(total), 0), COALESCE(MAX(total), 0)
            FROM ventas WHERE {condicion}
        """, parametros)
        tickets, total, personas, ticket_minimo, ticket_maximo = cur.fetchone()

        cur.execute(f"""
            SELECT id, fecha, total, metodo, COALESCE(personas, 1),
                   COALESCE(origen, '')
            FROM ventas WHERE {condicion}
            ORDER BY fecha DESC, id DESC
        """, parametros)
        ventas = cur.fetchall()

        cur.execute(f"""
            SELECT substr(fecha, 1, 10), COUNT(*), COALESCE(SUM(total), 0),
                   COALESCE(SUM(COALESCE(personas, 1)), 0)
            FROM ventas WHERE {condicion}
            GROUP BY substr(fecha, 1, 10) ORDER BY substr(fecha, 1, 10)
        """, parametros)
        por_dia = cur.fetchall()

        cur.execute("""
            SELECT d.producto, SUM(d.cantidad),
                   SUM(d.cantidad * d.precio)
            FROM detalle_venta d JOIN ventas v ON v.id=d.venta_id
            WHERE date(substr(v.fecha, 1, 10)) BETWEEN date(?) AND date(?)
            GROUP BY d.producto
            ORDER BY SUM(d.cantidad) DESC, SUM(d.cantidad*d.precio) DESC
        """, parametros)
        productos = cur.fetchall()

        cur.execute("""
            SELECT p.metodo, COUNT(DISTINCT p.venta_id), SUM(p.importe)
            FROM venta_pagos p JOIN ventas v ON v.id=p.venta_id
            WHERE date(substr(v.fecha, 1, 10)) BETWEEN date(?) AND date(?)
            GROUP BY p.metodo ORDER BY SUM(p.importe) DESC
        """, parametros)
        metodos = cur.fetchall()

        cur.execute(f"""
            SELECT COALESCE(NULLIF(origen, ''), 'Sin clasificar'),
                   SUM(COALESCE(personas, 1)), COUNT(*), SUM(total)
            FROM ventas WHERE {condicion}
            GROUP BY COALESCE(NULLIF(origen, ''), 'Sin clasificar')
            ORDER BY SUM(total) DESC
        """, parametros)
        origenes = cur.fetchall()

        cur.execute("""
            SELECT COALESCE(e.nombre, 'Sin asignar'), COUNT(v.id),
                   COALESCE(SUM(v.total), 0)
            FROM ventas v LEFT JOIN empleados e ON e.id=v.empleado_id
            WHERE date(substr(v.fecha, 1, 10)) BETWEEN date(?) AND date(?)
            GROUP BY COALESCE(e.nombre, 'Sin asignar')
            ORDER BY SUM(v.total) DESC
        """, parametros)
        empleados = cur.fetchall()
    finally:
        conn.close()

    return {
        "inicio": inicio, "fin": fin, "tickets": tickets,
        "venta_total": total, "personas": personas,
        "ticket_promedio": total / tickets if tickets else 0,
        "promedio_persona": total / personas if personas else 0,
        "ticket_minimo": ticket_minimo, "ticket_maximo": ticket_maximo,
        "ventas": ventas, "por_dia": por_dia, "productos": productos,
        "metodos": metodos, "origenes": origenes, "empleados": empleados,
    }


def _rango_semana(fecha_ref=None):
    if fecha_ref is None:
        fecha_ref = datetime.now().date()

    lunes = fecha_ref - timedelta(days=fecha_ref.weekday())
    domingo = lunes + timedelta(days=6)
    return lunes, domingo


def obtener_resumen_semana_actual():
    lunes, domingo = _rango_semana()

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            COUNT(*),
            COALESCE(SUM(total), 0),
            COALESCE(SUM(COALESCE(personas, 1)), 0)
        FROM ventas
        WHERE date(substr(fecha, 1, 10)) BETWEEN date(?) AND date(?)
    """, (lunes.isoformat(), domingo.isoformat()))

    tickets, venta_total, personas = cur.fetchone()
    conn.close()

    return {
        "inicio": lunes.isoformat(),
        "fin": domingo.isoformat(),
        "tickets": tickets,
        "venta_total": venta_total,
        "personas": personas,
    }


def obtener_comparacion_semanal():
    hoy = datetime.now().date()
    lunes_actual, domingo_actual = _rango_semana(hoy)
    lunes_anterior = lunes_actual - timedelta(days=7)
    domingo_anterior = domingo_actual - timedelta(days=7)

    conn = conectar()
    cur = conn.cursor()

    def total_periodo(inicio, fin):
        cur.execute("""
            SELECT COALESCE(SUM(total), 0)
            FROM ventas
            WHERE date(substr(fecha, 1, 10)) BETWEEN date(?) AND date(?)
        """, (inicio.isoformat(), fin.isoformat()))
        return cur.fetchone()[0]

    actual = total_periodo(lunes_actual, domingo_actual)
    anterior = total_periodo(lunes_anterior, domingo_anterior)
    conn.close()

    variacion = ((actual - anterior) / anterior) * 100 if anterior > 0 else None

    return {
        "actual": actual,
        "anterior": anterior,
        "variacion_pct": variacion,
    }


def obtener_ventas_por_dia_semana_actual():
    lunes, domingo = _rango_semana()

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT substr(fecha, 1, 10) AS dia,
               COALESCE(SUM(total), 0),
               COALESCE(SUM(COALESCE(personas, 1)), 0),
               COUNT(*)
        FROM ventas
        WHERE date(substr(fecha, 1, 10)) BETWEEN date(?) AND date(?)
        GROUP BY substr(fecha, 1, 10)
        ORDER BY dia
    """, (lunes.isoformat(), domingo.isoformat()))

    filas = cur.fetchall()

    conn.close()

    por_fecha = {
        fila[0]: {
            "venta": fila[1],
            "personas": fila[2],
            "tickets": fila[3],
        }
        for fila in filas
    }

    dias = []
    nombres = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"]

    for i, nombre in enumerate(nombres):
        fecha = lunes + timedelta(days=i)
        datos = por_fecha.get(
            fecha.isoformat(),
            {"venta": 0, "personas": 0, "tickets": 0},
        )
        dias.append({
            "nombre": nombre,
            "fecha": fecha.isoformat(),
            **datos,
        })

    return dias


def obtener_comparativo_ventas_diarias():
    """Devuelve ventas por día de la semana actual y la anterior."""
    lunes_actual, _domingo_actual = _rango_semana()
    lunes_anterior = lunes_actual - timedelta(days=7)
    domingo_actual = lunes_actual + timedelta(days=6)

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT substr(fecha, 1, 10) AS dia, COALESCE(SUM(total), 0)
        FROM ventas
        WHERE date(substr(fecha, 1, 10)) BETWEEN date(?) AND date(?)
        GROUP BY substr(fecha, 1, 10)
    """, (lunes_anterior.isoformat(), domingo_actual.isoformat()))
    ventas = {fila[0]: float(fila[1]) for fila in cur.fetchall()}
    conn.close()

    nombres = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    return [
        {
            "nombre": nombre,
            "actual": ventas.get((lunes_actual + timedelta(days=i)).isoformat(), 0),
            "anterior": ventas.get((lunes_anterior + timedelta(days=i)).isoformat(), 0),
        }
        for i, nombre in enumerate(nombres)
    ]


def obtener_mezcla_clientes_hoy():
    conn = conectar()
    cur = conn.cursor()

    hoy = datetime.now().strftime("%Y-%m-%d")

    cur.execute("""
        SELECT
            COALESCE(SUM(
                CASE
                    WHEN origen = 'Ya había venido'
                    THEN COALESCE(personas, 1)
                    ELSE 0
                END
            ), 0) AS recurrentes,

            COALESCE(SUM(
                CASE
                    WHEN origen <> 'Ya había venido'
                         AND origen <> 'No registrado'
                    THEN COALESCE(personas, 1)
                    ELSE 0
                END
            ), 0) AS nuevos,

            COALESCE(SUM(
                CASE
                    WHEN origen = 'No registrado'
                    THEN COALESCE(personas, 1)
                    ELSE 0
                END
            ), 0) AS no_registrados
        FROM ventas
        WHERE substr(fecha, 1, 10) = ?
    """, (hoy,))

    recurrentes, nuevos, no_registrados = cur.fetchone()
    conn.close()

    total_clasificado = recurrentes + nuevos
    pct_recurrentes = (recurrentes / total_clasificado * 100) if total_clasificado else 0
    pct_nuevos = (nuevos / total_clasificado * 100) if total_clasificado else 0

    return {
        "recurrentes": recurrentes,
        "nuevos": nuevos,
        "no_registrados": no_registrados,
        "pct_recurrentes": pct_recurrentes,
        "pct_nuevos": pct_nuevos,
    }


# ----------------------------------------------------------------------
# EMPLEADOS, PIN Y AUDITORIA
# ----------------------------------------------------------------------

ROLES_EMPLEADO = ("Administrador", "Caja", "Mesero", "Cocina")


def _validar_pin(pin):
    pin = str(pin).strip()
    if not pin.isdigit() or not 4 <= len(pin) <= 8:
        raise ValueError("El PIN debe contener entre 4 y 8 numeros.")
    return pin


def _crear_pin_hash(pin):
    pin = _validar_pin(pin)
    salt = secrets.token_hex(16)
    iterations = 240000
    digest = hashlib.pbkdf2_hmac(
        "sha256", pin.encode("utf-8"), bytes.fromhex(salt), iterations
    ).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def _comprobar_pin(pin, almacenado):
    try:
        algoritmo, iteraciones, salt, esperado = almacenado.split("$", 3)
        if algoritmo != "pbkdf2_sha256":
            return False
        obtenido = hashlib.pbkdf2_hmac(
            "sha256", str(pin).encode("utf-8"),
            bytes.fromhex(salt), int(iteraciones)
        ).hex()
        return hmac.compare_digest(obtenido, esperado)
    except (ValueError, AttributeError):
        return False


def hay_empleados():
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM empleados")
    resultado = cur.fetchone()[0] > 0
    conn.close()
    return resultado


def crear_empleado(nombre, pin, rol="Mesero"):
    nombre = str(nombre).strip()
    if not nombre:
        raise ValueError("Escribe el nombre del empleado.")
    if rol not in ROLES_EMPLEADO:
        raise ValueError("Selecciona un rol valido.")
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = conectar()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO empleados
            (nombre, pin_hash, rol, activo, creado_en, actualizado_en)
            VALUES (?, ?, ?, 1, ?, ?)
        """, (nombre, _crear_pin_hash(pin), rol, ahora, ahora))
        empleado_id = cur.lastrowid
        conn.commit()
        return empleado_id
    except sqlite3.IntegrityError:
        conn.rollback()
        raise ValueError("Ya existe un empleado con ese nombre.")
    finally:
        conn.close()


def obtener_empleados(solo_activos=False):
    conn = conectar()
    cur = conn.cursor()
    filtro = "WHERE activo=1" if solo_activos else ""
    cur.execute(f"""
        SELECT id, nombre, rol, activo, creado_en, actualizado_en
        FROM empleados {filtro}
        ORDER BY activo DESC, nombre COLLATE NOCASE
    """)
    filas = cur.fetchall()

    conn.close()
    return filas


def autenticar_empleado(empleado_id, pin, roles=None):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, nombre, pin_hash, rol, activo
        FROM empleados WHERE id=?
    """, (int(empleado_id),))
    fila = cur.fetchone()
    conn.close()
    if fila is None or not fila[4] or not _comprobar_pin(pin, fila[2]):
        return None
    if roles and fila[3] not in roles:
        return None
    return {"id": fila[0], "nombre": fila[1], "rol": fila[3]}


def actualizar_empleado(empleado_id, nombre, rol, activo):
    nombre = str(nombre).strip()
    if not nombre or rol not in ROLES_EMPLEADO:
        raise ValueError("Completa nombre y rol validos.")
    conn = conectar()
    try:
        conn.execute("""
            UPDATE empleados SET nombre=?, rol=?, activo=?, actualizado_en=?
            WHERE id=?
        """, (nombre, rol, 1 if activo else 0,
              datetime.now().strftime("%Y-%m-%d %H:%M:%S"), int(empleado_id)))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise ValueError("Ya existe un empleado con ese nombre.")
    finally:
        conn.close()


def cambiar_pin_empleado(empleado_id, nuevo_pin):
    conn = conectar()
    conn.execute("""
        UPDATE empleados SET pin_hash=?, actualizado_en=? WHERE id=?
    """, (_crear_pin_hash(nuevo_pin),
          datetime.now().strftime("%Y-%m-%d %H:%M:%S"), int(empleado_id)))
    conn.commit()
    conn.close()


def registrar_auditoria(empleado, accion, entidad, entidad_id=None, detalle=""):
    empleado = empleado or {"id": None, "nombre": "Sistema"}
    conn = conectar()
    conn.execute("""
        INSERT INTO auditoria
        (fecha, empleado_id, empleado, accion, entidad, entidad_id, detalle)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        empleado.get("id"), empleado.get("nombre", "Sistema"),
        str(accion), str(entidad), entidad_id, str(detalle),
    ))
    conn.commit()
    conn.close()


def obtener_auditoria(limite=500):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT fecha, empleado, accion, entidad, entidad_id, detalle
        FROM auditoria ORDER BY id DESC LIMIT ?
    """, (int(limite),))
    filas = cur.fetchall()
    conn.close()
    return filas


# ----------------------------------------------------------------------
# RECETAS Y COSTOS
# ----------------------------------------------------------------------

UNIDADES_INGREDIENTE = ("g", "ml", "pieza")


def guardar_ingrediente(nombre, unidad, cantidad_compra, costo_compra,
                        merma_pct=0, ingrediente_id=None):
    nombre = " ".join(str(nombre).strip().split())
    unidad = str(unidad).strip()
    try:
        cantidad_compra = float(cantidad_compra)
        costo_compra = float(costo_compra)
        merma_pct = float(merma_pct)
    except (TypeError, ValueError):
        raise ValueError("Revisa cantidades, costo y merma.") from None
    if not nombre or unidad not in UNIDADES_INGREDIENTE:
        raise ValueError("Completa el nombre y selecciona una unidad.")
    if cantidad_compra <= 0 or costo_compra < 0 or not 0 <= merma_pct < 100:
        raise ValueError("La compra debe ser mayor a cero y la merma menor a 100%.")
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = conectar()
    try:
        cur = conn.cursor()
        if ingrediente_id is None:
            cur.execute("""
                INSERT INTO ingredientes
                (nombre, unidad, cantidad_compra, costo_compra, merma_pct,
                 creado_en, actualizado_en) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (nombre, unidad, cantidad_compra, costo_compra, merma_pct,
                  ahora, ahora))
            ingrediente_id = cur.lastrowid
        else:
            cur.execute("""
                UPDATE ingredientes SET nombre=?, unidad=?, cantidad_compra=?,
                    costo_compra=?, merma_pct=?, actualizado_en=? WHERE id=?
            """, (nombre, unidad, cantidad_compra, costo_compra, merma_pct,
                  ahora, int(ingrediente_id)))
        cur.execute("""
            INSERT INTO ingrediente_costos
            (ingrediente_id, fecha, cantidad_compra, costo_compra, merma_pct)
            VALUES (?, ?, ?, ?, ?)
        """, (ingrediente_id, ahora, cantidad_compra, costo_compra, merma_pct))
        conn.commit()
        return ingrediente_id
    except sqlite3.IntegrityError:
        conn.rollback()
        raise ValueError("Ya existe un ingrediente con ese nombre.") from None
    finally:
        conn.close()


def obtener_ingredientes(solo_activos=False):
    conn = conectar()
    filas = conn.execute("""
        SELECT id, nombre, unidad, cantidad_compra, costo_compra, merma_pct,
               activo, costo_compra/(cantidad_compra*(1-merma_pct/100.0))
        FROM ingredientes WHERE (?=0 OR activo=1)
        ORDER BY nombre COLLATE NOCASE
    """, (1 if solo_activos else 0,)).fetchall()
    conn.close()
    claves = ("id", "nombre", "unidad", "cantidad_compra", "costo_compra",
              "merma_pct", "activo", "costo_unitario")
    return [dict(zip(claves, fila)) for fila in filas]


def establecer_ingrediente_activo(ingrediente_id, activo):
    conn = conectar()
    conn.execute("UPDATE ingredientes SET activo=?, actualizado_en=? WHERE id=?",
                 (1 if activo else 0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                  int(ingrediente_id)))
    conn.commit(); conn.close()


def guardar_preparacion(nombre, unidad, rendimiento, costo_extra=0,
                        preparacion_id=None):
    nombre = " ".join(str(nombre).strip().split())
    unidad = str(unidad).strip()
    try:
        rendimiento, costo_extra = float(rendimiento), float(costo_extra)
    except (TypeError, ValueError):
        raise ValueError("Revisa rendimiento y costo extra.") from None
    if not nombre or unidad not in UNIDADES_INGREDIENTE or rendimiento <= 0 or costo_extra < 0:
        raise ValueError("Completa nombre, unidad, rendimiento y costo extra.")
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = conectar()
    try:
        if preparacion_id is None:
            cur = conn.execute("""
                INSERT INTO preparaciones
                (nombre, unidad, rendimiento, costo_extra, creado_en, actualizado_en)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (nombre, unidad, rendimiento, costo_extra, ahora, ahora))
            preparacion_id = cur.lastrowid
        else:
            conn.execute("""
                UPDATE preparaciones SET nombre=?, unidad=?, rendimiento=?,
                    costo_extra=?, actualizado_en=? WHERE id=?
            """, (nombre, unidad, rendimiento, costo_extra, ahora,
                  int(preparacion_id)))
        conn.commit(); return preparacion_id
    except sqlite3.IntegrityError:
        conn.rollback(); raise ValueError("Ya existe una preparación con ese nombre.") from None
    finally:
        conn.close()


def obtener_preparaciones(solo_activas=False):
    conn = conectar()
    filas = conn.execute("""
        SELECT p.id, p.nombre, p.unidad, p.rendimiento, p.costo_extra, p.activo,
               COALESCE(SUM(pi.cantidad*(i.costo_compra/
                 (i.cantidad_compra*(1-i.merma_pct/100.0)))),0)+p.costo_extra
        FROM preparaciones p
        LEFT JOIN preparacion_ingredientes pi ON pi.preparacion_id=p.id
        LEFT JOIN ingredientes i ON i.id=pi.ingrediente_id
        WHERE (?=0 OR p.activo=1) GROUP BY p.id ORDER BY p.nombre COLLATE NOCASE
    """, (1 if solo_activas else 0,)).fetchall()
    conn.close()
    return [{"id": f[0], "nombre": f[1], "unidad": f[2], "rendimiento": f[3],
             "costo_extra": f[4], "activo": f[5], "costo_total": f[6],
             "costo_unitario": f[6]/f[3] if f[3] else 0} for f in filas]


def establecer_preparacion_activa(preparacion_id, activa):
    conn = conectar(); conn.execute(
        "UPDATE preparaciones SET activo=?, actualizado_en=? WHERE id=?",
        (1 if activa else 0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         int(preparacion_id)))
    conn.commit(); conn.close()


def guardar_ingrediente_preparacion(preparacion_id, ingrediente_id, cantidad):
    cantidad = float(cantidad)
    if cantidad <= 0: raise ValueError("La cantidad debe ser mayor a cero.")
    conn = conectar(); conn.execute("""
        INSERT INTO preparacion_ingredientes(preparacion_id, ingrediente_id, cantidad)
        VALUES (?, ?, ?) ON CONFLICT(preparacion_id, ingrediente_id)
        DO UPDATE SET cantidad=excluded.cantidad
    """, (int(preparacion_id), int(ingrediente_id), cantidad))
    conn.commit(); conn.close()


def eliminar_ingrediente_preparacion(preparacion_id, ingrediente_id):
    conn = conectar(); conn.execute(
        "DELETE FROM preparacion_ingredientes WHERE preparacion_id=? AND ingrediente_id=?",
        (int(preparacion_id), int(ingrediente_id)))
    conn.commit(); conn.close()


def obtener_preparacion(preparacion_id):
    prep = next((p for p in obtener_preparaciones(False)
                 if p["id"] == int(preparacion_id)), None)
    if prep is None: return None
    conn = conectar(); filas = conn.execute("""
        SELECT i.id, i.nombre, i.unidad, pi.cantidad,
               pi.cantidad*(i.costo_compra/(i.cantidad_compra*(1-i.merma_pct/100.0)))
        FROM preparacion_ingredientes pi JOIN ingredientes i ON i.id=pi.ingrediente_id
        WHERE pi.preparacion_id=? ORDER BY i.nombre COLLATE NOCASE
    """, (int(preparacion_id),)).fetchall(); conn.close()
    prep["componentes"] = filas
    return prep


def guardar_preparacion_receta(producto_id, preparacion_id, cantidad):
    cantidad = float(cantidad)
    if cantidad <= 0: raise ValueError("La cantidad debe ser mayor a cero.")
    conn = conectar(); conn.execute("""
        INSERT INTO receta_preparaciones(producto_id, preparacion_id, cantidad)
        VALUES (?, ?, ?) ON CONFLICT(producto_id, preparacion_id)
        DO UPDATE SET cantidad=excluded.cantidad
    """, (int(producto_id), int(preparacion_id), cantidad))
    conn.commit(); conn.close()


def eliminar_preparacion_receta(producto_id, preparacion_id):
    conn = conectar(); conn.execute(
        "DELETE FROM receta_preparaciones WHERE producto_id=? AND preparacion_id=?",
        (int(producto_id), int(preparacion_id)))
    conn.commit(); conn.close()


def guardar_componente_receta(producto_id, ingrediente_id, cantidad):
    cantidad = float(cantidad)
    if cantidad <= 0:
        raise ValueError("La cantidad utilizada debe ser mayor a cero.")
    conn = conectar()
    conn.execute("""
        INSERT INTO receta_ingredientes(producto_id, ingrediente_id, cantidad)
        VALUES (?, ?, ?)
        ON CONFLICT(producto_id, ingrediente_id)
        DO UPDATE SET cantidad=excluded.cantidad
    """, (int(producto_id), int(ingrediente_id), cantidad))
    conn.commit(); conn.close()


def eliminar_componente_receta(producto_id, ingrediente_id):
    conn = conectar()
    conn.execute("DELETE FROM receta_ingredientes WHERE producto_id=? AND ingrediente_id=?",
                 (int(producto_id), int(ingrediente_id)))
    conn.commit(); conn.close()


def guardar_costo_extra_receta(producto_id, costo_extra):
    costo_extra = float(costo_extra)
    if costo_extra < 0:
        raise ValueError("El costo extra no puede ser negativo.")
    conn = conectar()
    conn.execute("""
        INSERT INTO recetas(producto_id, costo_extra, actualizado_en)
        VALUES (?, ?, ?) ON CONFLICT(producto_id) DO UPDATE SET
        costo_extra=excluded.costo_extra, actualizado_en=excluded.actualizado_en
    """, (int(producto_id), costo_extra,
          datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit(); conn.close()


def obtener_receta(producto_id):
    conn = conectar()
    componentes = conn.execute("""
        SELECT i.id, i.nombre, i.unidad, ri.cantidad,
               ri.cantidad*(i.costo_compra/(i.cantidad_compra*(1-i.merma_pct/100.0)))
        FROM receta_ingredientes ri JOIN ingredientes i ON i.id=ri.ingrediente_id
        WHERE ri.producto_id=? ORDER BY i.nombre COLLATE NOCASE
    """, (int(producto_id),)).fetchall()
    preparaciones = conn.execute("""
        SELECT p.id, p.nombre, p.unidad, rp.cantidad,
          rp.cantidad*((COALESCE((SELECT SUM(pi.cantidad*(i.costo_compra/
          (i.cantidad_compra*(1-i.merma_pct/100.0))))
          FROM preparacion_ingredientes pi JOIN ingredientes i ON i.id=pi.ingrediente_id
          WHERE pi.preparacion_id=p.id),0)+p.costo_extra)/p.rendimiento)
        FROM receta_preparaciones rp JOIN preparaciones p ON p.id=rp.preparacion_id
        WHERE rp.producto_id=? ORDER BY p.nombre COLLATE NOCASE
    """, (int(producto_id),)).fetchall()
    fila = conn.execute("SELECT costo_extra FROM recetas WHERE producto_id=?",
                        (int(producto_id),)).fetchone()
    conn.close()
    costo_preparaciones = sum(c[4] for c in preparaciones)
    return {"componentes": componentes, "preparaciones": preparaciones,
            "costo_extra": fila[0] if fila else 0.0,
            "costo_ingredientes": sum(c[4] for c in componentes),
            "costo_preparaciones": costo_preparaciones,
            "costo_total": sum(c[4] for c in componentes) + costo_preparaciones +
                           (fila[0] if fila else 0.0)}


def obtener_costos_productos():
    resultado = []
    for producto in obtener_productos(False):
        receta = obtener_receta(producto[0])
        costo = receta["costo_total"]
        precio = float(producto[2])
        resultado.append((producto[0], producto[1], precio, costo,
                          precio-costo, costo/precio*100 if precio else 0))
    return resultado


# ----------------------------------------------------------------------
# ADMINISTRACIÓN DE PRODUCTOS
# ----------------------------------------------------------------------

def obtener_productos(solo_activos=False):
    conn = conectar()
    cur = conn.cursor()

    if solo_activos:
        cur.execute("""
            SELECT id, nombre, precio, categoria, activo, orden
            FROM productos
            WHERE activo = 1
            ORDER BY nombre COLLATE NOCASE, id
        """)
    else:
        cur.execute("""
            SELECT id, nombre, precio, categoria, activo, orden
            FROM productos
            ORDER BY nombre COLLATE NOCASE, id
        """)

    productos = cur.fetchall()
    conn.close()
    productos.sort(key=lambda producto: (
        "".join(
            caracter for caracter in unicodedata.normalize("NFD", producto[1])
            if unicodedata.category(caracter) != "Mn"
        ).casefold(),
        producto[0],
    ))
    return productos


def agregar_producto(nombre, precio, categoria="General"):
    nombre = str(nombre).strip()
    try:
        precio = float(precio)
    except (TypeError, ValueError):
        raise ValueError("El precio debe ser un número válido.") from None

    if not nombre:
        raise ValueError("El nombre del producto no puede estar vacío.")
    if not math.isfinite(precio) or precio < 0:
        raise ValueError("El precio debe ser un número mayor o igual a cero.")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT COALESCE(MAX(orden), 0) + 1 FROM productos")
    orden = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO productos(nombre, precio, categoria, activo, orden)
        VALUES (?, ?, ?, 1, ?)
    """, (nombre, precio, str(categoria).strip() or "General", orden))

    producto_id = cur.lastrowid
    conn.commit()
    conn.close()
    return producto_id


def actualizar_producto(producto_id, nombre, precio, categoria):
    nombre = str(nombre).strip()
    try:
        precio = float(precio)
    except (TypeError, ValueError):
        raise ValueError("El precio debe ser un número válido.") from None

    if not nombre:
        raise ValueError("El nombre del producto no puede estar vacío.")
    if not math.isfinite(precio) or precio < 0:
        raise ValueError("El precio debe ser un número mayor o igual a cero.")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        UPDATE productos
        SET nombre = ?, precio = ?, categoria = ?
        WHERE id = ?
    """, (
        nombre,
        precio,
        str(categoria).strip() or "General",
        int(producto_id),
    ))

    conn.commit()
    conn.close()


def obtener_imagenes_productos():
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT id, COALESCE(imagen, '') FROM productos")
    imagenes = {fila[0]: fila[1] for fila in cur.fetchall()}
    conn.close()
    return imagenes


def actualizar_imagen_producto(producto_id, imagen):
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        "UPDATE productos SET imagen=? WHERE id=?",
        (str(imagen or ""), int(producto_id)),
    )
    if cur.rowcount != 1:
        conn.close()
        raise ValueError("No se encontró el producto.")
    conn.commit()
    conn.close()


def establecer_producto_activo(producto_id, activo):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        UPDATE productos
        SET activo = ?
        WHERE id = ?
    """, (1 if activo else 0, int(producto_id)))

    conn.commit()
    conn.close()


# ----------------------------------------------------------------------
# CORTE DE CAJA
# ----------------------------------------------------------------------

def obtener_resumen_metodos_hoy():
    conn = conectar()
    cur = conn.cursor()

    hoy = datetime.now().strftime("%Y-%m-%d")

    cur.execute("""
        SELECT p.metodo, COUNT(DISTINCT p.venta_id), COALESCE(SUM(p.importe), 0)
        FROM venta_pagos p
        JOIN ventas v ON v.id = p.venta_id
        WHERE substr(v.fecha, 1, 10) = ?
        GROUP BY p.metodo
        ORDER BY p.metodo
    """, (hoy,))

    filas = cur.fetchall()

    # Compatibilidad con ventas anteriores a la tabla venta_pagos.
    cur.execute("""
        SELECT v.metodo, COUNT(*), COALESCE(SUM(v.total), 0)
        FROM ventas v
        WHERE substr(v.fecha, 1, 10) = ?
          AND NOT EXISTS (
              SELECT 1 FROM venta_pagos p WHERE p.venta_id = v.id
          )
        GROUP BY v.metodo
    """, (hoy,))
    filas_antiguas = cur.fetchall()
    conn.close()

    resumen = {
        "Efectivo": {"tickets": 0, "total": 0.0},
        "Tarjeta": {"tickets": 0, "total": 0.0},
        "Transferencia": {"tickets": 0, "total": 0.0},
    }

    for metodo, tickets, total in filas:
        if metodo not in resumen:
            resumen[metodo] = {"tickets": 0, "total": 0.0}

        resumen[metodo]["tickets"] = tickets
        resumen[metodo]["total"] = total

    for metodo, tickets, total in filas_antiguas:
        if metodo not in resumen:
            resumen[metodo] = {"tickets": 0, "total": 0.0}
        resumen[metodo]["tickets"] += tickets
        resumen[metodo]["total"] += total

    return resumen


def obtener_corte_caja_hoy():
    resumen = obtener_resumen_hoy()
    metodos = obtener_resumen_metodos_hoy()

    efectivo = metodos.get("Efectivo", {}).get("total", 0.0)
    tarjeta = metodos.get("Tarjeta", {}).get("total", 0.0)
    transferencia = metodos.get("Transferencia", {}).get("total", 0.0)
    puntos = metodos.get("Puntos", {}).get("total", 0.0)

    gastos = obtener_resumen_gastos_hoy()

    return {
        "venta_total": resumen["venta_total"],
        "tickets": resumen["tickets"],
        "personas": resumen["personas"],
        "ticket_promedio": resumen["ticket_promedio"],
        "efectivo": efectivo,
        "tarjeta": tarjeta,
        "transferencia": transferencia,
        "puntos": puntos,
        "metodos": metodos,
        "gastos": gastos["total"],
        "gastos_efectivo": gastos["efectivo"],
        "gastos_tarjeta": gastos["tarjeta"],
        "gastos_transferencia": gastos["transferencia"],
        "resultado_dia": resumen["venta_total"] - gastos["total"],
        "flujo_efectivo_neto": efectivo - gastos["efectivo"],
    }


# ----------------------------------------------------------------------
# GASTOS Y AUDITORIA
# ----------------------------------------------------------------------

CATEGORIAS_GASTO = (
    "Insumos", "Gas", "Compras", "Mantenimiento",
    "Servicios", "Nomina", "Otros",
)

METODOS_GASTO = ("Efectivo", "Tarjeta", "Transferencia")


def _datos_gasto(fila):
    if fila is None:
        return None
    claves = (
        "id", "concepto", "categoria", "importe", "fecha",
        "metodo_pago", "estado", "creado_en", "actualizado_en",
    )
    return dict(zip(claves, fila))


def registrar_gasto(concepto, categoria, importe, fecha=None,
                    metodo_pago="Efectivo"):
    concepto = str(concepto).strip()
    categoria = str(categoria).strip()
    metodo_pago = str(metodo_pago).strip()
    try:
        importe = float(importe)
    except (TypeError, ValueError):
        raise ValueError("El importe debe ser un número válido.") from None

    if not concepto:
        raise ValueError("Escribe el concepto del gasto.")
    if not categoria:
        raise ValueError("Selecciona una categoria.")
    if not math.isfinite(importe) or importe <= 0:
        raise ValueError("El importe debe ser mayor que cero.")
    if metodo_pago not in METODOS_GASTO:
        raise ValueError("Selecciona un metodo de pago valido.")

    fecha = fecha or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = conectar()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO gastos
            (concepto, categoria, importe, fecha, metodo_pago, estado,
             creado_en, actualizado_en)
            VALUES (?, ?, ?, ?, ?, 'Activo', ?, ?)
        """, (concepto, categoria, importe, fecha, metodo_pago, ahora, ahora))
        gasto_id = cur.lastrowid
        nuevo = {
            "concepto": concepto, "categoria": categoria,
            "importe": importe, "fecha": fecha,
            "metodo_pago": metodo_pago, "estado": "Activo",
        }
        cur.execute("""
            INSERT INTO gasto_eventos
            (gasto_id, tipo, fecha_evento, datos_nuevos)
            VALUES (?, 'Alta', ?, ?)
        """, (gasto_id, ahora, json.dumps(nuevo, ensure_ascii=False)))
        conn.commit()
        return gasto_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def obtener_gastos_hoy(incluir_anulados=True):
    conn = conectar()
    cur = conn.cursor()
    hoy = datetime.now().strftime("%Y-%m-%d")
    filtro = "" if incluir_anulados else " AND estado = 'Activo'"
    cur.execute(f"""
        SELECT id, concepto, categoria, importe, fecha, metodo_pago, estado,
               creado_en, actualizado_en
        FROM gastos
        WHERE substr(fecha, 1, 10) = ? {filtro}
        ORDER BY fecha DESC, id DESC
    """, (hoy,))
    filas = [_datos_gasto(fila) for fila in cur.fetchall()]
    conn.close()
    return filas


def obtener_gasto(gasto_id):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, concepto, categoria, importe, fecha, metodo_pago, estado,
               creado_en, actualizado_en
        FROM gastos WHERE id = ?
    """, (int(gasto_id),))
    gasto = _datos_gasto(cur.fetchone())
    conn.close()
    return gasto


def corregir_gasto(gasto_id, concepto, categoria, importe, fecha,
                   metodo_pago, motivo):
    anterior = obtener_gasto(gasto_id)
    motivo = str(motivo).strip()
    concepto = str(concepto).strip()
    categoria = str(categoria).strip()
    metodo_pago = str(metodo_pago).strip()
    try:
        importe = float(importe)
    except (TypeError, ValueError):
        raise ValueError("El importe debe ser un número válido.") from None

    if anterior is None:
        raise ValueError("No se encontro el gasto.")
    if anterior["estado"] != "Activo":
        raise ValueError("Un gasto anulado no puede corregirse.")
    if not motivo:
        raise ValueError("Escribe el motivo de la correccion.")
    if (not concepto or not categoria or not math.isfinite(importe)
            or importe <= 0):
        raise ValueError("Completa todos los datos correctamente.")
    if metodo_pago not in METODOS_GASTO:
        raise ValueError("Selecciona un metodo de pago valido.")

    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nuevo = {
        "concepto": concepto, "categoria": categoria,
        "importe": importe, "fecha": fecha,
        "metodo_pago": metodo_pago, "estado": "Activo",
    }
    conn = conectar()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE gastos
            SET concepto=?, categoria=?, importe=?, fecha=?, metodo_pago=?,
                actualizado_en=?
            WHERE id=? AND estado='Activo'
        """, (concepto, categoria, importe, fecha, metodo_pago,
              ahora, int(gasto_id)))
        if cur.rowcount != 1:
            raise ValueError("El gasto cambio mientras se editaba.")
        cur.execute("""
            INSERT INTO gasto_eventos
            (gasto_id, tipo, fecha_evento, motivo,
             datos_anteriores, datos_nuevos)
            VALUES (?, 'Correccion', ?, ?, ?, ?)
        """, (int(gasto_id), ahora, motivo,
              json.dumps(anterior, ensure_ascii=False),
              json.dumps(nuevo, ensure_ascii=False)))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def anular_gasto(gasto_id, motivo):
    anterior = obtener_gasto(gasto_id)
    motivo = str(motivo).strip()
    if anterior is None:
        raise ValueError("No se encontro el gasto.")
    if anterior["estado"] != "Activo":
        raise ValueError("El gasto ya esta anulado.")
    if not motivo:
        raise ValueError("Escribe el motivo de la anulacion.")

    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nuevo = dict(anterior)
    nuevo["estado"] = "Anulado"
    conn = conectar()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE gastos SET estado='Anulado', actualizado_en=?
            WHERE id=? AND estado='Activo'
        """, (ahora, int(gasto_id)))
        if cur.rowcount != 1:
            raise ValueError("El gasto cambio mientras se anulaba.")
        cur.execute("""
            INSERT INTO gasto_eventos
            (gasto_id, tipo, fecha_evento, motivo,
             datos_anteriores, datos_nuevos)
            VALUES (?, 'Anulacion', ?, ?, ?, ?)
        """, (int(gasto_id), ahora, motivo,
              json.dumps(anterior, ensure_ascii=False),
              json.dumps(nuevo, ensure_ascii=False)))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def obtener_eventos_gasto(gasto_id):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT tipo, fecha_evento, motivo, datos_anteriores, datos_nuevos
        FROM gasto_eventos
        WHERE gasto_id = ?
        ORDER BY id
    """, (int(gasto_id),))
    filas = cur.fetchall()
    conn.close()
    return filas


def obtener_resumen_gastos_hoy():
    conn = conectar()
    cur = conn.cursor()
    hoy = datetime.now().strftime("%Y-%m-%d")
    cur.execute("""
        SELECT
            COALESCE(SUM(importe), 0),
            COALESCE(SUM(CASE WHEN metodo_pago='Efectivo' THEN importe ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN metodo_pago='Tarjeta' THEN importe ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN metodo_pago='Transferencia' THEN importe ELSE 0 END), 0)
        FROM gastos
        WHERE estado='Activo' AND substr(fecha, 1, 10) = ?
    """, (hoy,))
    total, efectivo, tarjeta, transferencia = cur.fetchone()
    conn.close()
    return {
        "total": total, "efectivo": efectivo,
        "tarjeta": tarjeta, "transferencia": transferencia,
    }


# ----------------------------------------------------------------------
# HISTORIAL DE VENTAS
# ----------------------------------------------------------------------

def obtener_historial_ventas(limite=200):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, fecha, total, metodo,
               COALESCE(personas, 1),
               COALESCE(origen, 'No registrado')
        FROM ventas
        ORDER BY fecha DESC
        LIMIT ?
    """, (int(limite),))

    filas = cur.fetchall()
    conn.close()
    return filas


def obtener_detalle_venta(venta_id):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT producto, cantidad, precio
        FROM detalle_venta
        WHERE venta_id = ?
        ORDER BY id
    """, (int(venta_id),))

    filas = cur.fetchall()
    conn.close()
    return filas


# ----------------------------------------------------------------------
# PEDIDOS DE CELULARES Y TABLETAS
# ----------------------------------------------------------------------

def crear_pedido_movil(mesa, mesero, items, notas="", empleado_id=None):
    mesa = str(mesa).strip()
    mesero = str(mesero).strip()
    notas = str(notas).strip()
    if not mesa:
        raise ValueError("Selecciona la mesa.")
    if not mesero:
        raise ValueError("Escribe el nombre del mesero.")
    if not isinstance(items, list) or not items:
        raise ValueError("Agrega al menos un producto.")

    cantidades = {}
    asignaciones = []
    numero_cuentas = 1
    for item in items:
        producto_id = int(item.get("producto_id", 0))
        cantidad = int(item.get("cantidad", 0))
        if producto_id <= 0 or cantidad <= 0 or cantidad > 50:
            raise ValueError("El pedido contiene una cantidad no valida.")
        cantidades[producto_id] = cantidades.get(producto_id, 0) + cantidad
        cuenta = int(item.get("cuenta_numero", 1) or 1)
        compartidas = sorted({
            int(valor) for valor in item.get("cuentas_compartidas", [])
            if str(valor).isdigit() and 1 <= int(valor) <= 8
        })
        if compartidas:
            numero_cuentas = max(numero_cuentas, max(compartidas))
            cuenta = 0
        elif not 1 <= cuenta <= 8:
            raise ValueError("La cuenta asignada debe estar entre 1 y 8.")
        else:
            numero_cuentas = max(numero_cuentas, cuenta)
        asignaciones.append({
            "producto_id": producto_id, "cantidad": cantidad,
            "cuenta_numero": cuenta, "cuentas_compartidas": compartidas,
        })

    conn = conectar()
    try:
        cur = conn.cursor()
        marcadores = ",".join("?" for _ in cantidades)
        cur.execute(f"""
            SELECT id, nombre, precio
            FROM productos
            WHERE activo=1 AND id IN ({marcadores})
        """, tuple(cantidades))
        productos = {fila[0]: fila for fila in cur.fetchall()}
        if len(productos) != len(cantidades):
            raise ValueError("Uno de los productos ya no esta disponible.")

        total = sum(
            float(productos[producto_id][2]) * cantidad
            for producto_id, cantidad in cantidades.items()
        )
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cuentas_guardadas = []
        for item in asignaciones:
            _id, nombre, precio = productos[item["producto_id"]]
            cuentas_guardadas.append({
                **item, "producto": nombre, "precio": float(precio),
            })
        cuentas_json = json.dumps(
            {"numero_cuentas": numero_cuentas, "items": cuentas_guardadas},
            ensure_ascii=False,
        )
        cur.execute("""
            INSERT INTO pedidos_movil
            (fecha, mesa, mesero, notas, total, estado, estado_cocina,
             empleado_id, numero_cuentas, cuentas_json,
             actualizado_en, cocina_actualizado_en)
            VALUES (?, ?, ?, ?, ?, 'Pendiente', 'Nuevo', ?, ?, ?, ?, ?)
        """, (
            ahora, mesa, mesero, notas, total, empleado_id,
            numero_cuentas, cuentas_json, ahora, ahora,
        ))
        pedido_id = cur.lastrowid
        for producto_id, cantidad in cantidades.items():
            _id, nombre, precio = productos[producto_id]
            cur.execute("""
                INSERT INTO detalle_pedido_movil
                (pedido_id, producto_id, producto, cantidad, precio)
                VALUES (?, ?, ?, ?, ?)
            """, (pedido_id, producto_id, nombre, cantidad, precio))
        conn.commit()
        return pedido_id, total
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def crear_pedido_desde_pc(
    mesa, mesero, productos, notas="", empleado_id=None,
    cuenta_numero=1, numero_cuentas=1,
):
    """Convierte el carrito de caja en una comanda, conservando el comensal."""
    if not productos:
        raise ValueError("Agrega al menos un producto.")
    cuenta_numero = int(cuenta_numero or 1)
    numero_cuentas = max(int(numero_cuentas or 1), cuenta_numero)
    if not 1 <= cuenta_numero <= 8 or not 1 <= numero_cuentas <= 8:
        raise ValueError("El comensal debe estar entre 1 y 8.")
    conn = conectar()
    cur = conn.cursor()
    cantidades = {}
    try:
        for nombre, precio in productos:
            cur.execute("""
                SELECT id FROM productos
                WHERE activo=1 AND nombre=? AND ABS(precio - ?) < 0.005
                ORDER BY id LIMIT 1
            """, (nombre, float(precio)))
            fila = cur.fetchone()
            if fila is None:
                raise ValueError(
                    f"El producto '{nombre}' ya no coincide con el menu activo."
                )
            cantidades[fila[0]] = cantidades.get(fila[0], 0) + 1
    finally:
        conn.close()
    items = [
        {
            "producto_id": producto_id,
            "cantidad": cantidad,
            "cuenta_numero": cuenta_numero,
        }
        for producto_id, cantidad in cantidades.items()
    ]
    return crear_pedido_movil(mesa, mesero, items, notas, empleado_id)


def crear_saldo_cuenta(mesa, empleado, productos):
    """Deja productos no cobrados en la mesa sin reenviarlos a cocina."""
    if not productos:
        return None
    empleado = empleado or {"id": None, "nombre": "Caja"}
    pedido_id, total = crear_pedido_desde_pc(
        mesa, empleado.get("nombre", "Caja"), productos,
        "Saldo pendiente de cuenta dividida", empleado.get("id"),
    )
    actualizar_estado_cocina(pedido_id, "Entregado")
    registrar_auditoria(
        empleado, "Conservar saldo", "Pedido", pedido_id,
        f"{mesa} - ${total:.2f}",
    )
    return pedido_id, total


def obtener_pedidos_movil(estados=("Pendiente", "En caja"), limite=200):
    conn = conectar()
    cur = conn.cursor()
    marcadores = ",".join("?" for _ in estados)
    cur.execute(f"""
        SELECT id, fecha, mesa, mesero, notas, total, estado, venta_id
        FROM pedidos_movil
        WHERE estado IN ({marcadores})
        ORDER BY CASE estado WHEN 'Pendiente' THEN 0 ELSE 1 END,
                 fecha, id
        LIMIT ?
    """, (*estados, int(limite)))
    filas = cur.fetchall()
    conn.close()
    return filas


def contar_pedidos_pendientes():
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM pedidos_movil WHERE estado='Pendiente'
    """)
    total = cur.fetchone()[0]
    conn.close()
    return total


def obtener_detalle_pedido_movil(pedido_id):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT producto_id, producto, cantidad, precio
        FROM detalle_pedido_movil
        WHERE pedido_id=? ORDER BY id
    """, (int(pedido_id),))
    filas = cur.fetchall()
    conn.close()
    return filas


def obtener_cuentas_pedidos(pedido_ids):
    """Reconstruye las cuentas capturadas por persona, incluidos compartidos."""
    ids = [int(pedido_id) for pedido_id in pedido_ids]
    if not ids:
        return []
    conn = conectar()
    cur = conn.cursor()
    marcadores = ",".join("?" for _ in ids)
    cur.execute(f"""
        SELECT numero_cuentas, cuentas_json
        FROM pedidos_movil WHERE id IN ({marcadores}) ORDER BY id
    """, ids)
    filas = cur.fetchall()
    conn.close()
    documentos = []
    maximo = 1
    for numero, texto in filas:
        if not texto:
            continue
        try:
            documento = json.loads(texto)
        except (TypeError, json.JSONDecodeError):
            continue
        documentos.append(documento)
        maximo = max(maximo, int(documento.get("numero_cuentas", numero or 1)))
    if maximo <= 1:
        return []
    cuentas = [[] for _ in range(min(maximo, 8))]
    for documento in documentos:
        for item in documento.get("items", []):
            nombre = str(item.get("producto", "Producto"))
            precio = float(item.get("precio", 0))
            cantidad = int(item.get("cantidad", 0))
            compartidas = [
                int(n) for n in item.get("cuentas_compartidas", [])
                if 1 <= int(n) <= len(cuentas)
            ]
            if compartidas:
                centavos = int(round(precio * cantidad * 100))
                base, sobrantes = divmod(centavos, len(compartidas))
                for posicion, numero_cuenta in enumerate(compartidas):
                    importe = (base + (1 if posicion < sobrantes else 0)) / 100
                    cuentas[numero_cuenta - 1].append((nombre, importe))
            else:
                numero_cuenta = int(item.get("cuenta_numero", 1) or 1)
                if 1 <= numero_cuenta <= len(cuentas):
                    cuentas[numero_cuenta - 1].extend(
                        [(nombre, precio)] * cantidad
                    )
    return cuentas if any(cuentas) else []


def obtener_etiquetas_cuentas_pedido(pedido_id):
    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        "SELECT cuentas_json FROM pedidos_movil WHERE id=?", (int(pedido_id),)
    )
    fila = cur.fetchone()
    conn.close()
    if not fila or not fila[0]:
        return {}
    try:
        items = json.loads(fila[0]).get("items", [])
    except (TypeError, json.JSONDecodeError):
        return {}
    etiquetas = {}
    for item in items:
        producto_id = int(item.get("producto_id", 0))
        compartidas = item.get("cuentas_compartidas", [])
        etiqueta = (
            "Compartido " + ", ".join(f"C{n}" for n in compartidas)
            if compartidas else f"Cuenta {int(item.get('cuenta_numero', 1) or 1)}"
        )
        etiquetas.setdefault(producto_id, set()).add(etiqueta)
    return {
        producto_id: " / ".join(sorted(valores))
        for producto_id, valores in etiquetas.items()
    }


def obtener_detalle_comanda_cocina(pedido_id):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, producto_id, producto, cantidad, cantidad_entregada, precio
        FROM detalle_pedido_movil
        WHERE pedido_id=? ORDER BY id
    """, (int(pedido_id),))
    filas = cur.fetchall()
    conn.close()
    return filas


def entregar_unidad_comanda(pedido_id, detalle_id):
    """Marca una unidad como entregada y cierra la comanda al completarla."""
    conn = conectar()
    try:
        cur = conn.cursor()
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("""
            UPDATE detalle_pedido_movil
            SET cantidad_entregada = cantidad_entregada + 1
            WHERE id=? AND pedido_id=? AND cantidad_entregada < cantidad
              AND EXISTS (
                  SELECT 1 FROM pedidos_movil
                  WHERE id=? AND estado <> 'Cancelado'
                    AND estado_cocina <> 'Entregado'
              )
        """, (int(detalle_id), int(pedido_id), int(pedido_id)))
        if cur.rowcount != 1:
            raise ValueError("El platillo ya fue entregado o no existe.")
        cur.execute("""
            SELECT COUNT(*)
            FROM detalle_pedido_movil
            WHERE pedido_id=? AND cantidad_entregada < cantidad
        """, (int(pedido_id),))
        completado = cur.fetchone()[0] == 0
        cur.execute("""
            UPDATE pedidos_movil
            SET estado_cocina=?, cocina_actualizado_en=?
            WHERE id=?
        """, ("Entregado" if completado else "Preparando", ahora, int(pedido_id)))
        conn.commit()
        return completado
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def actualizar_estado_pedido_movil(pedido_id, estado, venta_id=None):
    estados_validos = ("Pendiente", "En caja", "Cobrado", "Cancelado")
    if estado not in estados_validos:
        raise ValueError("Estado de pedido no valido.")
    conn = conectar()
    cur = conn.cursor()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    transiciones = {
        "Pendiente": ("En caja", "Cancelado"),
        "En caja": ("Pendiente", "Cobrado", "Cancelado"),
    }
    estados_origen = tuple(
        origen for origen, destinos in transiciones.items()
        if estado in destinos
    )
    marcadores = ",".join("?" for _ in estados_origen)
    cur.execute(f"""
        UPDATE pedidos_movil
        SET estado=?, venta_id=?, actualizado_en=?
        WHERE id=? AND estado IN ({marcadores})
    """, (estado, venta_id, ahora, int(pedido_id), *estados_origen))
    if cur.rowcount != 1:
        conn.close()
        raise ValueError("El pedido ya cambió de estado o no existe.")
    conn.commit()
    conn.close()


def obtener_pedidos_mesa(mesa):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, fecha, mesa, mesero, notas, total, estado,
               estado_cocina, venta_id
        FROM pedidos_movil
        WHERE mesa=? AND estado IN ('Pendiente', 'En caja')
        ORDER BY fecha, id
    """, (str(mesa),))
    filas = cur.fetchall()
    conn.close()
    return filas


def _leer_documento_cuentas(numero_cuentas, cuentas_json):
    try:
        documento = json.loads(cuentas_json) if cuentas_json else {}
    except (TypeError, json.JSONDecodeError):
        documento = {}
    documento.setdefault("numero_cuentas", int(numero_cuentas or 1))
    documento.setdefault("items", [])
    return documento


def _leer_cuentas_pagadas(texto):
    try:
        valores = json.loads(texto) if texto else []
    except (TypeError, json.JSONDecodeError):
        valores = []
    return {
        int(valor) for valor in valores
        if str(valor).isdigit() and 1 <= int(valor) <= 8
    }


def _cuentas_presentes(documento):
    presentes = set()
    for item in documento.get("items", []):
        compartidas = {
            int(valor) for valor in item.get("cuentas_compartidas", [])
            if str(valor).isdigit() and 1 <= int(valor) <= 8
        }
        if compartidas:
            presentes.update(compartidas)
        else:
            numero = int(item.get("cuenta_numero", 1) or 1)
            if 1 <= numero <= 8:
                presentes.add(numero)
    return presentes or {1}


def _productos_por_cuenta_documento(documento, numero):
    productos = []
    for item in documento.get("items", []):
        nombre = str(item.get("producto", "Producto"))
        precio = float(item.get("precio", 0))
        cantidad = int(item.get("cantidad", 0))
        compartidas = [
            int(valor) for valor in item.get("cuentas_compartidas", [])
            if str(valor).isdigit() and 1 <= int(valor) <= 8
        ]
        if compartidas:
            if numero not in compartidas:
                continue
            centavos = int(round(precio * cantidad * 100))
            base, sobrantes = divmod(centavos, len(compartidas))
            posicion = compartidas.index(numero)
            importe = (base + (1 if posicion < sobrantes else 0)) / 100
            if importe > 0:
                productos.append((f"{nombre} (compartido)", importe))
        elif int(item.get("cuenta_numero", 1) or 1) == numero:
            productos.extend([(nombre, precio)] * cantidad)
    return productos


def obtener_comensales_mesa(mesa):
    """Devuelve saldos y productos pendientes por comensal de una mesa."""
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, numero_cuentas, cuentas_json, cuentas_pagadas_json
        FROM pedidos_movil
        WHERE mesa=? AND estado IN ('Pendiente', 'En caja')
        ORDER BY fecha, id
    """, (str(mesa),))
    pedidos = cur.fetchall()
    resultado = {}
    maximo = 1
    for pedido_id, numero_cuentas, cuentas_json, pagadas_json in pedidos:
        documento = _leer_documento_cuentas(numero_cuentas, cuentas_json)
        maximo = max(maximo, min(8, int(documento.get("numero_cuentas", 1) or 1)))
        pagadas = _leer_cuentas_pagadas(pagadas_json)
        presentes = _cuentas_presentes(documento)
        if not documento.get("items"):
            cur.execute("""
                SELECT producto, cantidad, precio
                FROM detalle_pedido_movil WHERE pedido_id=? ORDER BY id
            """, (int(pedido_id),))
            documento = {
                "numero_cuentas": 1,
                "items": [
                    {
                        "producto": nombre, "cantidad": cantidad, "precio": precio,
                        "cuenta_numero": 1, "cuentas_compartidas": [],
                    }
                    for nombre, cantidad, precio in cur.fetchall()
                ],
            }
            presentes = {1}
        for numero in presentes:
            cuenta = resultado.setdefault(numero, {
                "numero": numero, "productos": [], "total": 0.0,
                "pagada": True, "pedido_ids": [],
            })
            productos = _productos_por_cuenta_documento(documento, numero)
            if numero not in pagadas:
                cuenta["pagada"] = False
                cuenta["pedido_ids"].append(int(pedido_id))
                cuenta["productos"].extend(productos)
                cuenta["total"] += sum(precio for _nombre, precio in productos)
    conn.close()
    cuentas = []
    for numero in range(1, maximo + 1):
        cuenta = resultado.get(numero, {
            "numero": numero, "productos": [], "total": 0.0,
            "pagada": False, "pedido_ids": [],
        })
        agrupados = {}
        orden = []
        for nombre, precio in cuenta["productos"]:
            clave = (nombre, float(precio))
            if clave not in agrupados:
                agrupados[clave] = 0
                orden.append(clave)
            agrupados[clave] += 1
        cuenta["productos"] = [
            {
                "nombre": nombre, "precio": precio, "cantidad": agrupados[(nombre, precio)],
                "subtotal": round(precio * agrupados[(nombre, precio)], 2),
            }
            for nombre, precio in orden
        ]
        cuenta["total"] = round(cuenta["total"], 2)
        cuentas.append(cuenta)
    return cuentas


def marcar_comensal_pagado(mesa, numero_comensal, venta_id=None):
    """Marca solo un comensal como pagado sin cerrar las demás cuentas."""
    numero_comensal = int(numero_comensal)
    if not 1 <= numero_comensal <= 8:
        raise ValueError("Comensal no válido.")
    conn = conectar()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, numero_cuentas, cuentas_json, cuentas_pagadas_json, estado
            FROM pedidos_movil
            WHERE mesa=? AND estado IN ('Pendiente', 'En caja')
            ORDER BY fecha, id
        """, (str(mesa),))
        filas = cur.fetchall()
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        afectados = 0
        for pedido_id, numero_cuentas, cuentas_json, pagadas_json, estado in filas:
            documento = _leer_documento_cuentas(numero_cuentas, cuentas_json)
            presentes = _cuentas_presentes(documento)
            if not documento.get("items"):
                presentes = {1}
            if numero_comensal not in presentes:
                continue
            pagadas = _leer_cuentas_pagadas(pagadas_json)
            pagadas.add(numero_comensal)
            completo = presentes.issubset(pagadas)
            if completo:
                cur.execute("""
                    UPDATE pedidos_movil
                    SET cuentas_pagadas_json=?, estado='Cobrado', venta_id=?,
                        actualizado_en=?
                    WHERE id=? AND estado IN ('Pendiente', 'En caja')
                """, (
                    json.dumps(sorted(pagadas)), venta_id, ahora, int(pedido_id),
                ))
            else:
                cur.execute("""
                    UPDATE pedidos_movil
                    SET cuentas_pagadas_json=?, actualizado_en=?
                    WHERE id=? AND estado IN ('Pendiente', 'En caja')
                """, (json.dumps(sorted(pagadas)), ahora, int(pedido_id)))
            afectados += cur.rowcount
        conn.commit()
        if not afectados:
            raise ValueError("Ese comensal ya está pagado o no tiene consumo pendiente.")
        return afectados
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def obtener_resumen_mesas():
    mesas = [f"Mesa {numero}" for numero in range(1, 21)] + ["Barra"]
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT mesa, COUNT(*), MIN(fecha), GROUP_CONCAT(DISTINCT mesero)
        FROM pedidos_movil
        WHERE estado IN ('Pendiente', 'En caja')
        GROUP BY mesa
    """)
    ocupadas = {}
    for mesa, pedidos, desde, meseros in cur.fetchall():
        comensales = obtener_comensales_mesa(mesa)
        total_pendiente = round(sum(
            cuenta["total"] for cuenta in comensales if not cuenta["pagada"]
        ), 2)
        ocupadas[mesa] = {
            "pedidos": pedidos, "total": total_pendiente,
            "desde": desde, "meseros": meseros or "",
            "comensales": comensales,
        }
    conn.close()
    # Los pedidos para llevar usan una referencia propia (cliente y folio).
    # Se agregan a la lista mientras estén activos para que puedan cargarse y
    # cobrarse igual que una mesa, sin ocupar una mesa física.
    extras = sorted(
        (mesa for mesa in ocupadas if mesa not in mesas),
        key=lambda valor: valor.casefold(),
    )
    mesas.extend(extras)
    return [
        {
            "mesa": mesa,
            "ocupada": mesa in ocupadas,
            **ocupadas.get(mesa, {
                "pedidos": 0, "total": 0.0,
                "desde": None, "meseros": "", "comensales": [],
            }),
        }
        for mesa in mesas
    ]


# ----------------------------------------------------------------------
# CLUB LA ESQUINA
# ----------------------------------------------------------------------

def _telefono_cliente(telefono):
    telefono = "".join(c for c in str(telefono) if c.isdigit())
    if len(telefono) < 10 or len(telefono) > 15:
        raise ValueError("Escribe un celular válido de 10 dígitos.")
    return telefono


def registrar_cliente(nombre, telefono, cumpleanos="", email="",
                      acepta_promociones=False):
    nombre = " ".join(str(nombre).strip().split())
    telefono = _telefono_cliente(telefono)
    cumpleanos = str(cumpleanos or "").strip()
    email = str(email or "").strip().lower()
    if len(nombre) < 2 or len(nombre) > 80:
        raise ValueError("Escribe tu nombre.")
    if cumpleanos:
        try:
            datetime.strptime(cumpleanos, "%Y-%m-%d")
        except ValueError:
            raise ValueError("La fecha de cumpleaños no es válida.") from None
    if email and ("@" not in email or len(email) > 120):
        raise ValueError("El correo no es válido.")
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = conectar()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM clientes WHERE telefono=?", (telefono,))
        fila = cur.fetchone()
        if fila:
            cliente_id = fila[0]
            cur.execute("""
                UPDATE clientes SET nombre=?, cumpleanos=?, email=?,
                    acepta_promociones=?, activo=1, actualizado_en=? WHERE id=?
            """, (nombre, cumpleanos, email, 1 if acepta_promociones else 0,
                  ahora, cliente_id))
        else:
            cur.execute("""
                INSERT INTO clientes
                (nombre, telefono, cumpleanos, email, acepta_promociones,
                 creado_en, actualizado_en)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (nombre, telefono, cumpleanos, email,
                  1 if acepta_promociones else 0, ahora, ahora))
            cliente_id = cur.lastrowid
        conn.commit()
        return obtener_cliente(cliente_id)
    finally:
        conn.close()


def obtener_cliente(cliente_id):
    conn = conectar()
    fila = conn.execute("""
        SELECT id, nombre, telefono, cumpleanos, email, acepta_promociones,
               puntos, visitas, total_compras, activo, creado_en, actualizado_en
        FROM clientes WHERE id=?
    """, (int(cliente_id),)).fetchone()
    conn.close()
    if fila is None:
        return None
    claves = ("id", "nombre", "telefono", "cumpleanos", "email",
              "acepta_promociones", "puntos", "visitas", "total_compras",
              "activo", "creado_en", "actualizado_en")
    return dict(zip(claves, fila))


def obtener_clientes(busqueda="", solo_activos=True):
    texto = str(busqueda).strip()
    patron = f"%{texto}%"
    conn = conectar()
    filas = conn.execute("""
        SELECT id, nombre, telefono, cumpleanos, email, acepta_promociones,
               puntos, visitas, total_compras, activo, creado_en, actualizado_en
        FROM clientes
        WHERE (?=0 OR activo=1) AND (nombre LIKE ? OR telefono LIKE ?)
        ORDER BY activo DESC, nombre COLLATE NOCASE LIMIT 1000
    """, (1 if solo_activos else 0, patron, patron)).fetchall()
    conn.close()
    claves = ("id", "nombre", "telefono", "cumpleanos", "email",
              "acepta_promociones", "puntos", "visitas", "total_compras",
              "activo", "creado_en", "actualizado_en")
    return [dict(zip(claves, fila)) for fila in filas]


def establecer_cliente_activo(cliente_id, activo):
    conn = conectar()
    conn.execute("UPDATE clientes SET activo=?, actualizado_en=? WHERE id=?",
                 (1 if activo else 0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                  int(cliente_id)))
    conn.commit()
    conn.close()


def obtener_comandas_cocina(incluir_entregadas=False, limite=100):
    conn = conectar()
    cur = conn.cursor()
    filtro = "" if incluir_entregadas else "AND estado_cocina <> 'Entregado'"
    cur.execute(f"""
        SELECT id, fecha, mesa, mesero, notas, total, estado,
               estado_cocina, cocina_actualizado_en
        FROM pedidos_movil
        WHERE estado <> 'Cancelado' {filtro}
        ORDER BY
            CASE estado_cocina
                WHEN 'Nuevo' THEN 0
                WHEN 'Preparando' THEN 1
                WHEN 'Listo' THEN 2
                ELSE 3
            END,
            fecha, id
        LIMIT ?
    """, (int(limite),))
    filas = cur.fetchall()
    conn.close()
    return filas


def actualizar_estado_cocina(pedido_id, estado_cocina):
    validos = ("Nuevo", "Preparando", "Listo", "Entregado")
    if estado_cocina not in validos:
        raise ValueError("Estado de cocina no valido.")
    conn = conectar()
    cur = conn.cursor()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
        UPDATE pedidos_movil
        SET estado_cocina=?, cocina_actualizado_en=?
        WHERE id=? AND estado <> 'Cancelado'
    """, (estado_cocina, ahora, int(pedido_id)))
    if cur.rowcount != 1:
        conn.close()
        raise ValueError("No se encontro la comanda.")
    if estado_cocina == "Entregado":
        cur.execute("""
            UPDATE detalle_pedido_movil
            SET cantidad_entregada=cantidad
            WHERE pedido_id=?
        """, (int(pedido_id),))
    conn.commit()
    conn.close()


def obtener_estado_pedido_movil(pedido_id):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, mesa, mesero, total, estado, estado_cocina, fecha
        FROM pedidos_movil WHERE id=?
    """, (int(pedido_id),))
    fila = cur.fetchone()
    conn.close()
    return fila
