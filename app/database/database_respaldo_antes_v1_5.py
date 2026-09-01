import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

DB_FOLDER = Path("data")
DB_FILE = DB_FOLDER / "la_esquina.db"


def conectar():
    DB_FOLDER.mkdir(exist_ok=True)
    return sqlite3.connect(DB_FILE)


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
            FOREIGN KEY (venta_id) REFERENCES ventas(id)
        )
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


def guardar_venta(productos, total, metodo="Efectivo", personas=1, origen="No registrado"):
    conn = conectar()
    cur = conn.cursor()

    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cur.execute("""
        INSERT INTO ventas (fecha, total, metodo, personas, origen)
        VALUES (?, ?, ?, ?, ?)
    """, (fecha, total, metodo, personas, origen))

    venta_id = cur.lastrowid

    for nombre, precio in productos:
        cur.execute("""
            INSERT INTO detalle_venta
            (venta_id, producto, cantidad, precio)
            VALUES (?, ?, ?, ?)
        """, (venta_id, nombre, 1, precio))

    conn.commit()
    conn.close()

    return venta_id


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
            ORDER BY orden, nombre
        """)
    else:
        cur.execute("""
            SELECT id, nombre, precio, categoria, activo, orden
            FROM productos
            ORDER BY activo DESC, orden, nombre
        """)

    productos = cur.fetchall()
    conn.close()
    return productos


def agregar_producto(nombre, precio, categoria="General"):
    nombre = nombre.strip()

    if not nombre:
        raise ValueError("El nombre del producto no puede estar vacío.")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT COALESCE(MAX(orden), 0) + 1 FROM productos")
    orden = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO productos(nombre, precio, categoria, activo, orden)
        VALUES (?, ?, ?, 1, ?)
    """, (nombre, float(precio), categoria.strip() or "General", orden))

    producto_id = cur.lastrowid
    conn.commit()
    conn.close()
    return producto_id


def actualizar_producto(producto_id, nombre, precio, categoria):
    nombre = nombre.strip()

    if not nombre:
        raise ValueError("El nombre del producto no puede estar vacío.")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        UPDATE productos
        SET nombre = ?, precio = ?, categoria = ?
        WHERE id = ?
    """, (
        nombre,
        float(precio),
        categoria.strip() or "General",
        int(producto_id),
    ))

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
        SELECT metodo, COUNT(*), COALESCE(SUM(total), 0)
        FROM ventas
        WHERE substr(fecha, 1, 10) = ?
        GROUP BY metodo
        ORDER BY metodo
    """, (hoy,))

    filas = cur.fetchall()
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

    return resumen


def obtener_corte_caja_hoy():
    resumen = obtener_resumen_hoy()
    metodos = obtener_resumen_metodos_hoy()

    efectivo = metodos.get("Efectivo", {}).get("total", 0.0)
    tarjeta = metodos.get("Tarjeta", {}).get("total", 0.0)
    transferencia = metodos.get("Transferencia", {}).get("total", 0.0)

    return {
        "venta_total": resumen["venta_total"],
        "tickets": resumen["tickets"],
        "personas": resumen["personas"],
        "ticket_promedio": resumen["ticket_promedio"],
        "efectivo": efectivo,
        "tarjeta": tarjeta,
        "transferencia": transferencia,
        "metodos": metodos,
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
