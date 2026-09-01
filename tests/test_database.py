import sqlite3
import tempfile
import unittest
import unicodedata
from pathlib import Path
from unittest.mock import patch

from app.database import database


class DatabaseConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_folder = Path(self.temp_dir.name) / "data"
        self.db_file = self.db_folder / "test.db"
        self.paths = patch.multiple(
            database,
            DB_FOLDER=self.db_folder,
            DB_FILE=self.db_file,
        )
        self.paths.start()

    def tearDown(self):
        self.paths.stop()
        self.temp_dir.cleanup()

    def test_connection_enables_integrity_and_concurrency_pragmas(self):
        conn = database.conectar()
        try:
            self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            self.assertEqual(conn.execute("PRAGMA synchronous").fetchone()[0], 1)
            self.assertEqual(conn.execute("PRAGMA busy_timeout").fetchone()[0], 15000)
        finally:
            conn.close()

    def test_product_image_reference_is_persistent(self):
        database.crear_tablas()
        database.actualizar_imagen_producto(1, "producto_1.jpg")
        self.assertEqual(
            database.obtener_imagenes_productos()[1], "producto_1.jpg"
        )

    def test_products_are_returned_in_spanish_alphabetical_order(self):
        database.crear_tablas()
        database.agregar_producto("Árbol", 10)
        database.agregar_producto("agua fresca", 20)
        database.agregar_producto("Zumo", 30)

        nombres = [producto[1] for producto in database.obtener_productos()]
        claves = [
            "".join(
                c for c in unicodedata.normalize("NFD", nombre)
                if unicodedata.category(c) != "Mn"
            ).casefold()
            for nombre in nombres
        ]
        self.assertEqual(claves, sorted(claves))

    def test_foreign_key_rejects_orphan_sale_detail(self):
        database.crear_tablas()
        conn = database.conectar()
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO detalle_venta
                    (venta_id, producto, cantidad, precio)
                    VALUES (?, ?, ?, ?)
                    """,
                    (999999, "Producto inexistente", 1, 10.0),
                )
        finally:
            conn.close()

    def test_sale_rejects_total_different_from_products(self):
        database.crear_tablas()
        with self.assertRaisesRegex(ValueError, "no coincide"):
            database.guardar_venta([("Café", 60)], 50)

        conn = database.conectar()
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM ventas").fetchone()[0], 0)
        finally:
            conn.close()

    def test_sale_rejects_non_finite_payment(self):
        database.crear_tablas()
        with self.assertRaisesRegex(ValueError, "importe no válido"):
            database.guardar_venta(
                [("Café", 60)], 60, pagos=[("Efectivo", float("nan"))]
            )

    def test_paid_order_cannot_return_to_pending(self):
        database.crear_tablas()
        pedido_id, _total = database.crear_pedido_movil(
            "Mesa 1", "Ana", [{"producto_id": 1, "cantidad": 1}]
        )
        database.actualizar_estado_pedido_movil(pedido_id, "En caja")
        venta_id = database.guardar_venta([("Chilaquiles", 150)], 150)
        database.actualizar_estado_pedido_movil(pedido_id, "Cobrado", venta_id)

        with self.assertRaisesRegex(ValueError, "cambió de estado"):
            database.actualizar_estado_pedido_movil(pedido_id, "Pendiente")


if __name__ == "__main__":
    unittest.main()
