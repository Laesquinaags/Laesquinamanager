import time
import unittest
from unittest.mock import Mock, patch

from app import mobile_server


class MobileSessionTests(unittest.TestCase):
    def setUp(self):
        with mobile_server._sessions_lock:
            mobile_server._sessions.clear()

    def test_session_accepts_authorized_role(self):
        empleado = {"id": 1, "nombre": "Ana", "rol": "Mesero"}
        token = mobile_server._create_session(empleado)
        handler = Mock(headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(
            mobile_server._session_from_header(handler, ("Mesero",)),
            empleado,
        )

    def test_expired_session_is_removed(self):
        token = "expirado"
        with mobile_server._sessions_lock:
            mobile_server._sessions[token] = (
                {"id": 1, "nombre": "Ana", "rol": "Mesero"},
                time.time() - 1,
            )
        handler = Mock(headers={"Authorization": f"Bearer {token}"})

        self.assertIsNone(mobile_server._session_from_header(handler))
        self.assertNotIn(token, mobile_server._sessions)

    def test_session_rejects_unauthorized_role(self):
        token = mobile_server._create_session(
            {"id": 1, "nombre": "Ana", "rol": "Mesero"}
        )
        handler = Mock(headers={"Authorization": f"Bearer {token}"})

        self.assertIsNone(
            mobile_server._session_from_header(handler, ("Cocina",))
        )

    def test_owner_dashboard_accepts_only_administrator(self):
        admin = {"id": 1, "nombre": "Guillermo", "rol": "Administrador"}
        waiter = {"id": 2, "nombre": "Ana", "rol": "Mesero"}
        admin_handler = Mock(headers={
            "Authorization": f"Bearer {mobile_server._create_session(admin)}"
        })
        waiter_handler = Mock(headers={
            "Authorization": f"Bearer {mobile_server._create_session(waiter)}"
        })

        self.assertEqual(
            mobile_server._session_from_header(admin_handler, ("Administrador",)),
            admin,
        )
        self.assertIsNone(
            mobile_server._session_from_header(waiter_handler, ("Administrador",))
        )


class MobilePageSafetyTests(unittest.TestCase):
    def test_mobile_page_uses_text_nodes_for_database_values(self):
        self.assertIn("b.textContent=p.nombre", mobile_server.MOBILE_HTML)
        self.assertIn("name.textContent=p.nombre", mobile_server.MOBILE_HTML)
        self.assertNotIn("`${p.nombre}<small>", mobile_server.MOBILE_HTML)

    def test_owner_page_is_read_only_and_escapes_database_text(self):
        self.assertIn("a.textContent=left", mobile_server.OWNER_HTML)
        self.assertNotIn("/api/pedidos", mobile_server.OWNER_HTML)
        self.assertNotIn("/api/cocina/estado", mobile_server.OWNER_HTML)


if __name__ == "__main__":
    unittest.main()
