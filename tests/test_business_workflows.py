import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.database import database


class TemporaryDatabaseTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        folder = Path(self.temp_dir.name) / "data"
        self.paths = patch.multiple(
            database, DB_FOLDER=folder, DB_FILE=folder / "test.db"
        )
        self.paths.start()
        database.crear_tablas()

    def tearDown(self):
        self.paths.stop()
        self.temp_dir.cleanup()


class SaleWorkflowTests(TemporaryDatabaseTest):
    def test_sales_analysis_respects_custom_date_range(self):
        actual = database.guardar_venta(
            [("Café", 60)], 60, personas=1,
            origen="Facebook", pagos=[("Efectivo", 60)],
        )
        anterior = database.guardar_venta(
            [("Chilaquiles", 150), ("Café", 60)], 210, personas=2,
            metodo="Pago dividido", origen="Recomendación",
            pagos=[("Efectivo", 100), ("Tarjeta", 110)],
        )
        conn = database.conectar()
        try:
            conn.execute(
                "UPDATE ventas SET fecha='2026-07-10 09:00:00' WHERE id=?",
                (anterior,),
            )
            conn.execute(
                "UPDATE ventas SET fecha='2026-08-15 10:00:00' WHERE id=?",
                (actual,),
            )
            conn.commit()
        finally:
            conn.close()

        agosto = database.obtener_analisis_ventas("2026-08-01", "2026-08-31")
        self.assertEqual(agosto["tickets"], 1)
        self.assertEqual(agosto["venta_total"], 60)
        self.assertEqual(agosto["productos"][0][:2], ("Café", 1))
        self.assertEqual(agosto["origenes"][0][0], "Facebook")

        ambos = database.obtener_analisis_ventas("2026-07-01", "2026-08-31")
        self.assertEqual(ambos["tickets"], 2)
        self.assertEqual(ambos["venta_total"], 270)
        self.assertEqual(ambos["personas"], 3)
        self.assertEqual(len(ambos["ventas"]), 2)
        self.assertEqual(
            {fila[0] for fila in ambos["origenes"]},
            {"Facebook", "Recomendación"},
        )

    def test_split_payment_updates_sale_and_cash_summary(self):
        venta_id = database.guardar_venta(
            [("Chilaquiles", 150), ("Café", 60)],
            210,
            metodo="Pago dividido",
            personas=2,
            origen="Recomendación",
            pagos=[("Efectivo", 100), ("Tarjeta", 110)],
        )

        self.assertEqual(database.obtener_detalle_venta(venta_id), [
            ("Chilaquiles", 1, 150.0), ("Café", 1, 60.0)
        ])
        resumen = database.obtener_resumen_hoy()
        self.assertEqual(resumen["tickets"], 1)
        self.assertEqual(resumen["venta_total"], 210)
        self.assertEqual(resumen["personas"], 2)
        metodos = database.obtener_resumen_metodos_hoy()
        self.assertEqual(metodos["Efectivo"]["total"], 100)
        self.assertEqual(metodos["Tarjeta"]["total"], 110)

    def test_invalid_sale_does_not_leave_partial_records(self):
        with self.assertRaises(ValueError):
            database.guardar_venta(
                [("Café", 60)], 60, pagos=[("Crédito", 60)]
            )
        conn = database.conectar()
        try:
            for table in ("ventas", "venta_pagos", "detalle_venta"):
                self.assertEqual(
                    conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0
                )
        finally:
            conn.close()


class EmployeeWorkflowTests(TemporaryDatabaseTest):
    def test_employee_pin_roles_deactivation_and_audit(self):
        empleado_id = database.crear_empleado("Ana", "1234", "Mesero")
        empleado = database.autenticar_empleado(
            empleado_id, "1234", ("Mesero",)
        )
        self.assertEqual(empleado["nombre"], "Ana")
        self.assertIsNone(database.autenticar_empleado(empleado_id, "9999"))
        self.assertIsNone(database.autenticar_empleado(
            empleado_id, "1234", ("Cocina",)
        ))

        database.cambiar_pin_empleado(empleado_id, "5678")
        self.assertIsNone(database.autenticar_empleado(empleado_id, "1234"))
        empleado = database.autenticar_empleado(empleado_id, "5678")
        database.registrar_auditoria(empleado, "Prueba", "Empleado", empleado_id)
        self.assertEqual(database.obtener_auditoria(1)[0][2], "Prueba")

        database.actualizar_empleado(empleado_id, "Ana", "Mesero", False)
        self.assertIsNone(database.autenticar_empleado(empleado_id, "5678"))


class OrderWorkflowTests(TemporaryDatabaseTest):
    def test_takeout_order_appears_as_active_account(self):
        referencia = "Para llevar #1045 · Laura"
        pedido_id, total = database.crear_pedido_desde_pc(
            referencia, "Caja", [("Chilaquiles", 150.0)]
        )

        self.assertGreater(pedido_id, 0)
        self.assertEqual(total, 150.0)
        cuentas = {
            fila["mesa"]: fila for fila in database.obtener_resumen_mesas()
        }
        self.assertIn(referencia, cuentas)
        self.assertTrue(cuentas[referencia]["ocupada"])
        self.assertEqual(cuentas[referencia]["total"], 150.0)

    def test_order_preserves_individual_and_shared_accounts(self):
        pedido_id, total = database.crear_pedido_movil(
            "Mesa 5", "Ana", [
                {"producto_id": 1, "cantidad": 1, "cuenta_numero": 1},
                {"producto_id": 2, "cantidad": 1, "cuenta_numero": 2},
                {
                    "producto_id": 3, "cantidad": 1,
                    "cuentas_compartidas": [1, 2],
                },
            ]
        )
        cuentas = database.obtener_cuentas_pedidos([pedido_id])
        self.assertEqual(len(cuentas), 2)
        self.assertTrue(all(cuentas))
        self.assertAlmostEqual(
            sum(precio for cuenta in cuentas for _nombre, precio in cuenta),
            total,
            places=2,
        )
        etiquetas = database.obtener_etiquetas_cuentas_pedido(pedido_id)
        self.assertIn("Cuenta 1", etiquetas[1])
        self.assertIn("Cuenta 2", etiquetas[2])
        self.assertIn("Compartido", etiquetas[3])

    def test_paying_one_diner_keeps_the_other_diner_and_table_open(self):
        pedido_id, _total = database.crear_pedido_movil(
            "Mesa 7", "Ana", [
                {"producto_id": 1, "cantidad": 1, "cuenta_numero": 1},
                {"producto_id": 2, "cantidad": 1, "cuenta_numero": 2},
            ]
        )
        cuentas = database.obtener_comensales_mesa("Mesa 7")
        self.assertEqual([c["total"] for c in cuentas], [150.0, 135.0])

        venta_id = database.guardar_venta(cuentas[0]["productos"], 150.0)
        database.registrar_pago_comensal(
            "Mesa 7", 1, venta_id, cuentas[0]["pedido_ids"]
        )

        cuentas = database.obtener_comensales_mesa("Mesa 7")
        self.assertEqual(cuentas[0]["estado"], "PAGADO")
        self.assertEqual(cuentas[0]["total"], 0)
        self.assertEqual(cuentas[1]["estado"], "ABIERTO")
        self.assertEqual(cuentas[1]["total"], 135.0)
        mesa = next(
            m for m in database.obtener_resumen_mesas()
            if m["mesa"] == "Mesa 7"
        )
        self.assertTrue(mesa["ocupada"])
        self.assertEqual(mesa["total"], 135.0)
        self.assertEqual(
            database.obtener_estado_pedido_movil(pedido_id)[4], "Parcial"
        )

        cuenta_dos = next(
            c for c in database.obtener_comensales_mesa("Mesa 7")
            if c["numero"] == 2
        )
        venta_dos = database.guardar_venta(
            cuenta_dos["productos"], cuenta_dos["total"]
        )
        database.registrar_pago_comensal(
            "Mesa 7", 2, venta_dos, cuenta_dos["pedido_ids"]
        )
        self.assertEqual(
            database.obtener_estado_pedido_movil(pedido_id)[4], "Cobrado"
        )
        mesa = next(
            m for m in database.obtener_resumen_mesas()
            if m["mesa"] == "Mesa 7"
        )
        self.assertFalse(mesa["ocupada"])
        self.assertEqual(mesa["total"], 0)

    def test_new_items_for_paid_diner_reopen_only_new_order(self):
        pedido_id, _ = database.crear_pedido_movil(
            "Mesa 8", "Ana", [
                {"producto_id": 1, "cantidad": 1, "cuenta_numero": 1},
                {"producto_id": 2, "cantidad": 1, "cuenta_numero": 2},
            ]
        )
        cuenta = database.obtener_comensales_mesa("Mesa 8")[0]
        venta_id = database.guardar_venta(cuenta["productos"], cuenta["total"])
        database.registrar_pago_comensal(
            "Mesa 8", 1, venta_id, cuenta["pedido_ids"]
        )
        nuevo_id, _ = database.crear_pedido_desde_pc(
            "Mesa 8", "Caja", [("Café", 60.0)],
            comensal_numero=1,
        )
        abiertas = {
            c["numero"]: c for c in database.obtener_comensales_mesa("Mesa 8")
        }
        self.assertEqual(abiertas[1]["productos"], [("Café", 60.0)])
        self.assertEqual(abiertas[1]["pedido_ids"], [nuevo_id])
        self.assertEqual(abiertas[2]["total"], 135.0)

    def test_kitchen_can_deliver_one_unit_at_a_time(self):
        pedido_id, _total = database.crear_pedido_movil(
            "Mesa 2", "Ana", [{"producto_id": 1, "cantidad": 2}]
        )
        detalle_id = database.obtener_detalle_comanda_cocina(pedido_id)[0][0]

        self.assertFalse(database.entregar_unidad_comanda(pedido_id, detalle_id))
        detalle = database.obtener_detalle_comanda_cocina(pedido_id)[0]
        self.assertEqual((detalle[3], detalle[4]), (2, 1))
        self.assertEqual(
            database.obtener_estado_pedido_movil(pedido_id)[5], "Preparando"
        )

        self.assertTrue(database.entregar_unidad_comanda(pedido_id, detalle_id))
        self.assertEqual(
            database.obtener_estado_pedido_movil(pedido_id)[5], "Entregado"
        )
        with self.assertRaisesRegex(ValueError, "ya fue entregado"):
            database.entregar_unidad_comanda(pedido_id, detalle_id)

    def test_order_moves_from_waiter_to_kitchen_and_checkout(self):
        pedido_id, total = database.crear_pedido_movil(
            "Mesa 3", "Ana", [{"producto_id": 1, "cantidad": 2}], "Sin cebolla"
        )
        self.assertEqual(total, 300)
        self.assertEqual(database.contar_pedidos_pendientes(), 1)
        self.assertEqual(database.obtener_detalle_pedido_movil(pedido_id)[0][2], 2)

        database.actualizar_estado_cocina(pedido_id, "Preparando")
        self.assertEqual(database.obtener_estado_pedido_movil(pedido_id)[5], "Preparando")
        database.actualizar_estado_cocina(pedido_id, "Entregado")
        self.assertEqual(database.obtener_comandas_cocina(), [])

        database.actualizar_estado_pedido_movil(pedido_id, "En caja")
        venta_id = database.guardar_venta([("Chilaquiles", 150)] * 2, 300)
        database.actualizar_estado_pedido_movil(pedido_id, "Cobrado", venta_id)
        self.assertEqual(database.obtener_estado_pedido_movil(pedido_id)[4], "Cobrado")

    def test_order_rejects_unavailable_product_and_excess_quantity(self):
        database.establecer_producto_activo(1, False)
        with self.assertRaises(ValueError):
            database.crear_pedido_movil(
                "Mesa 1", "Ana", [{"producto_id": 1, "cantidad": 1}]
            )
        with self.assertRaises(ValueError):
            database.crear_pedido_movil(
                "Mesa 1", "Ana", [{"producto_id": 2, "cantidad": 51}]
            )


class ExpenseAndProductWorkflowTests(TemporaryDatabaseTest):
    def test_expense_correction_annulment_and_events(self):
        gasto_id = database.registrar_gasto(
            "Gas", "Servicios", 300, metodo_pago="Efectivo"
        )
        database.corregir_gasto(
            gasto_id, "Gas LP", "Servicios", 320,
            database.obtener_gasto(gasto_id)["fecha"], "Tarjeta", "Importe correcto"
        )
        self.assertEqual(database.obtener_gasto(gasto_id)["importe"], 320)
        database.anular_gasto(gasto_id, "Registro duplicado")
        self.assertEqual(database.obtener_gasto(gasto_id)["estado"], "Anulado")
        self.assertEqual(
            [evento[0] for evento in database.obtener_eventos_gasto(gasto_id)],
            ["Alta", "Correccion", "Anulacion"],
        )
        self.assertEqual(database.obtener_resumen_gastos_hoy()["total"], 0)

    def test_products_and_expenses_reject_non_finite_values(self):
        for value in (float("nan"), float("inf"), -1):
            with self.subTest(product=value):
                with self.assertRaises(ValueError):
                    database.agregar_producto("Inválido", value)
            with self.subTest(expense=value):
                with self.assertRaises(ValueError):
                    database.registrar_gasto("Inválido", "Otros", value)


if __name__ == "__main__":
    unittest.main()
