from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QListWidget,
    QMessageBox,
    QInputDialog,
    QDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QGroupBox,
    QProgressBar,
    QFormLayout,
    QDoubleSpinBox,
    QSpinBox,
    QDialogButtonBox,
    QScrollArea,
    QLineEdit,
    QComboBox,
    QDateTimeEdit,
    QTextEdit,
    QCheckBox,
)
from PySide6.QtCore import Qt, QDateTime, QTimer

from app.database.database import (
    guardar_venta,
    obtener_ventas_hoy,
    obtener_resumen_origen_hoy,
    obtener_resumen_hoy,
    obtener_resumen_semana_actual,
    obtener_comparacion_semanal,
    obtener_top_productos_hoy,
    obtener_ventas_por_dia_semana_actual,
    obtener_mezcla_clientes_hoy,
    obtener_productos,
    agregar_producto,
    actualizar_producto,
    establecer_producto_activo,
    obtener_resumen_metodos_hoy,
    obtener_corte_caja_hoy,
    obtener_historial_ventas,
    obtener_detalle_venta,
    CATEGORIAS_GASTO,
    METODOS_GASTO,
    registrar_gasto,
    obtener_gastos_hoy,
    obtener_gasto,
    corregir_gasto,
    anular_gasto,
    obtener_eventos_gasto,
    obtener_pedidos_movil,
    contar_pedidos_pendientes,
    obtener_detalle_pedido_movil,
    actualizar_estado_pedido_movil,
    obtener_resumen_mesas,
    obtener_pedidos_mesa,
    crear_pedido_desde_pc,
    ROLES_EMPLEADO,
    hay_empleados,
    crear_empleado,
    obtener_empleados,
    autenticar_empleado,
    actualizar_empleado,
    cambiar_pin_empleado,
    registrar_auditoria,
    obtener_auditoria,
    crear_saldo_cuenta,
)
from app.settings import cargar_configuracion, guardar_configuracion
from app.tickets import generar_ticket_pdf, imprimir_ticket, imprimir_cuenta
from app.mobile_server import start_mobile_server, mobile_url


class PagoDialog(QDialog):
    def __init__(self, total, parent=None):
        super().__init__(parent)
        self.total = float(total)
        self.resultado = None
        self.setWindowTitle("Forma de pago")
        self.resize(480, 330)
        principal = QVBoxLayout(self)
        titulo = QLabel(f"TOTAL A COBRAR: ${self.total:.2f}")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("font-size:22px;font-weight:bold;padding:10px;")
        principal.addWidget(titulo)
        formulario = QFormLayout()
        self.metodo = QComboBox()
        self.metodo.addItems(["Efectivo", "Tarjeta", "Transferencia", "Efectivo + Tarjeta"])
        self.efectivo = QDoubleSpinBox()
        self.efectivo.setRange(0, 1000000)
        self.efectivo.setDecimals(2)
        self.efectivo.setPrefix("$")
        self.efectivo.setValue(self.total)
        self.tarjeta = QDoubleSpinBox()
        self.tarjeta.setRange(0, 1000000)
        self.tarjeta.setDecimals(2)
        self.tarjeta.setPrefix("$")
        self.recibido = QDoubleSpinBox()
        self.recibido.setRange(0, 1000000)
        self.recibido.setDecimals(2)
        self.recibido.setPrefix("$")
        self.recibido.setValue(self.total)
        formulario.addRow("Forma de pago:", self.metodo)
        formulario.addRow("Parte en efectivo:", self.efectivo)
        formulario.addRow("Parte con tarjeta:", self.tarjeta)
        formulario.addRow("Efectivo recibido:", self.recibido)
        principal.addLayout(formulario)
        self.ayuda = QLabel()
        self.ayuda.setWordWrap(True)
        principal.addWidget(self.ayuda)
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.validar)
        botones.rejected.connect(self.reject)
        principal.addWidget(botones)
        self.metodo.currentTextChanged.connect(self.actualizar)
        self.efectivo.valueChanged.connect(self.ajustar_tarjeta)
        self.actualizar()

    def actualizar(self):
        metodo = self.metodo.currentText()
        mixto = metodo == "Efectivo + Tarjeta"
        solo_efectivo = metodo == "Efectivo"
        self.efectivo.setEnabled(mixto)
        self.tarjeta.setEnabled(mixto)
        self.recibido.setEnabled(mixto or solo_efectivo)
        if solo_efectivo:
            self.efectivo.setValue(self.total)
            self.tarjeta.setValue(0)
        elif metodo == "Tarjeta":
            self.efectivo.setValue(0); self.tarjeta.setValue(self.total)
        elif metodo == "Transferencia":
            self.efectivo.setValue(0); self.tarjeta.setValue(0)
        elif mixto:
            self.efectivo.setValue(round(self.total / 2, 2))
            self.ajustar_tarjeta()
        self.ayuda.setText(
            "En pago mixto, escribe la parte en efectivo; la parte de tarjeta "
            "se calcula automáticamente."
        )

    def ajustar_tarjeta(self):
        if self.metodo.currentText() == "Efectivo + Tarjeta":
            efectivo = min(self.efectivo.value(), self.total)
            self.tarjeta.blockSignals(True)
            self.tarjeta.setValue(round(self.total - efectivo, 2))
            self.tarjeta.blockSignals(False)
            if self.recibido.value() < efectivo:
                self.recibido.setValue(efectivo)

    def validar(self):
        metodo = self.metodo.currentText()
        if metodo == "Efectivo":
            pagos = [("Efectivo", self.total)]
            efectivo_cobrado = self.total
        elif metodo == "Tarjeta":
            pagos = [("Tarjeta", self.total)]
            efectivo_cobrado = 0
        elif metodo == "Transferencia":
            pagos = [("Transferencia", self.total)]
            efectivo_cobrado = 0
        else:
            efectivo_cobrado = self.efectivo.value()
            tarjeta = self.tarjeta.value()
            if efectivo_cobrado <= 0 or tarjeta <= 0 or abs(efectivo_cobrado + tarjeta - self.total) > 0.01:
                QMessageBox.warning(self, "Pago mixto", "Las dos partes deben ser mayores a cero y sumar el total.")
                return
            pagos = [("Efectivo", efectivo_cobrado), ("Tarjeta", tarjeta)]
        recibido = self.recibido.value() if efectivo_cobrado else None
        if efectivo_cobrado and recibido < efectivo_cobrado:
            QMessageBox.warning(self, "Efectivo", "El efectivo recibido es insuficiente.")
            return
        cambio = recibido - efectivo_cobrado if recibido is not None else None
        descripcion = metodo
        if metodo == "Efectivo + Tarjeta":
            descripcion = f"Mixto: Efectivo ${efectivo_cobrado:.2f} + Tarjeta ${self.tarjeta.value():.2f}"
        self.resultado = {
            "metodo_db": "Mixto" if len(pagos) > 1 else pagos[0][0],
            "descripcion": descripcion, "pagos": pagos,
            "recibido": recibido, "cambio": cambio,
        }
        self.accept()


class DividirCuentaDialog(QDialog):
    def __init__(self, productos, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dividir cuenta por productos")
        self.resize(650, 520)
        self.resultado = None
        principal = QVBoxLayout(self)
        titulo = QLabel("SELECCIONA LO QUE SE COBRARÁ AHORA")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("font-size:19px;font-weight:bold;padding:8px;")
        principal.addWidget(titulo)
        agrupados = {}
        for nombre, precio in productos:
            agrupados[(nombre, float(precio))] = agrupados.get((nombre, float(precio)), 0) + 1
        self.filas = []
        tabla = QTableWidget(len(agrupados), 4)
        tabla.setHorizontalHeaderLabels(["Producto", "Precio", "En cuenta", "Cobrar ahora"])
        tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        for fila, ((nombre, precio), cantidad) in enumerate(agrupados.items()):
            tabla.setItem(fila, 0, QTableWidgetItem(nombre))
            tabla.setItem(fila, 1, QTableWidgetItem(f"${precio:.2f}"))
            tabla.setItem(fila, 2, QTableWidgetItem(str(cantidad)))
            selector = QSpinBox()
            selector.setRange(0, cantidad)
            selector.setValue(0)
            tabla.setCellWidget(fila, 3, selector)
            self.filas.append((nombre, precio, cantidad, selector))
        principal.addWidget(tabla)
        nota = QLabel("Los productos que no selecciones permanecerán abiertos en la misma mesa.")
        nota.setWordWrap(True)
        principal.addWidget(nota)
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.validar)
        botones.rejected.connect(self.reject)
        principal.addWidget(botones)

    def validar(self):
        cobrar, restante = [], []
        for nombre, precio, cantidad, selector in self.filas:
            seleccionados = selector.value()
            cobrar.extend([(nombre, precio)] * seleccionados)
            restante.extend([(nombre, precio)] * (cantidad - seleccionados))
        if not cobrar:
            QMessageBox.warning(self, "Dividir cuenta", "Selecciona al menos un producto para cobrar.")
            return
        if not restante:
            QMessageBox.warning(self, "Dividir cuenta", "Seleccionaste toda la cuenta. Usa el botón COBRAR normal.")
            return
        self.resultado = (cobrar, restante)
        self.accept()


class ConfiguracionInicialDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crear Administrador principal")
        self.setModal(True)
        self.resize(500, 310)
        principal = QVBoxLayout(self)
        titulo = QLabel("CONFIGURACION INICIAL")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("font-size:22px;font-weight:bold;padding:8px;")
        principal.addWidget(titulo)
        texto = QLabel(
            "Crea el usuario que tendrá acceso completo al sistema. "
            "Guarda el PIN en un lugar seguro."
        )
        texto.setWordWrap(True)
        principal.addWidget(texto)
        formulario = QFormLayout()
        self.nombre = QLineEdit()
        self.nombre.setPlaceholderText("Ejemplo: Propietario")
        self.pin = QLineEdit()
        self.pin.setEchoMode(QLineEdit.Password)
        self.pin.setMaxLength(8)
        self.confirmar = QLineEdit()
        self.confirmar.setEchoMode(QLineEdit.Password)
        self.confirmar.setMaxLength(8)
        formulario.addRow("Nombre:", self.nombre)
        formulario.addRow("PIN (4 a 8 números):", self.pin)
        formulario.addRow("Confirmar PIN:", self.confirmar)
        principal.addLayout(formulario)
        guardar = QPushButton("CREAR ADMINISTRADOR")
        guardar.setMinimumHeight(48)
        guardar.setStyleSheet("font-weight:bold;background:#f2c94c;")
        guardar.clicked.connect(self.crear)
        principal.addWidget(guardar)

    def crear(self):
        if self.pin.text() != self.confirmar.text():
            QMessageBox.warning(self, "PIN", "Los dos PIN no coinciden.")
            return
        try:
            crear_empleado(
                self.nombre.text().strip(), self.pin.text(), "Administrador"
            )
        except Exception as error:
            QMessageBox.warning(self, "No se pudo crear", str(error))
            return
        self.accept()


class InicioSesionDialog(QDialog):
    def __init__(self, roles=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Iniciar sesión - La Esquina Manager")
        self.setModal(True)
        self.resize(430, 270)
        self.roles = roles
        self.empleado = None
        principal = QVBoxLayout(self)
        titulo = QLabel("INICIAR SESION")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("font-size:22px;font-weight:bold;padding:10px;")
        principal.addWidget(titulo)
        formulario = QFormLayout()
        self.lista = QComboBox()
        empleados = [e for e in obtener_empleados(True) if not roles or e[2] in roles]
        for empleado_id, nombre, rol, _activo, _creado, _actualizado in empleados:
            self.lista.addItem(f"{nombre} - {rol}", empleado_id)
        self.pin = QLineEdit()
        self.pin.setEchoMode(QLineEdit.Password)
        self.pin.setMaxLength(8)
        self.pin.returnPressed.connect(self.entrar)
        formulario.addRow("Empleado:", self.lista)
        formulario.addRow("PIN:", self.pin)
        principal.addLayout(formulario)
        entrar = QPushButton("ENTRAR")
        entrar.setMinimumHeight(48)
        entrar.setStyleSheet("font-weight:bold;background:#27ae60;color:white;")
        entrar.clicked.connect(self.entrar)
        principal.addWidget(entrar)

    def entrar(self):
        if self.lista.count() == 0:
            QMessageBox.warning(self, "Sin usuarios", "No hay empleados autorizados.")
            return
        empleado = autenticar_empleado(
            self.lista.currentData(), self.pin.text(), self.roles
        )
        if empleado is None:
            self.pin.clear()
            QMessageBox.warning(self, "Acceso denegado", "PIN incorrecto o usuario sin permiso.")
            return
        self.empleado = empleado
        self.accept()


class EmpleadosDialog(QDialog):
    def __init__(self, empleado_actual, parent=None):
        super().__init__(parent)
        self.empleado_actual = empleado_actual
        self.setWindowTitle("Empleados y permisos")
        self.resize(850, 570)
        principal = QVBoxLayout(self)
        titulo = QLabel("EMPLEADOS Y PERMISOS")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("font-size:22px;font-weight:bold;padding:7px;")
        principal.addWidget(titulo)
        self.tabla = QTableWidget(0, 4)
        self.tabla.setHorizontalHeaderLabels(["ID", "Empleado", "Rol", "Estado"])
        self.tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SingleSelection)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        principal.addWidget(self.tabla)
        botones = QHBoxLayout()
        for texto, funcion in (
            ("Agregar empleado", self.agregar),
            ("Editar rol / estado", self.editar),
            ("Cambiar PIN", self.cambiar_pin),
            ("Ver auditoría", self.ver_auditoria),
        ):
            boton = QPushButton(texto)
            boton.setMinimumHeight(43)
            boton.clicked.connect(funcion)
            botones.addWidget(boton)
        principal.addLayout(botones)
        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(self.accept)
        principal.addWidget(cerrar)
        self.recargar()

    def recargar(self):
        empleados = obtener_empleados()
        self.tabla.setRowCount(len(empleados))
        for fila, (eid, nombre, rol, activo, _creado, _actualizado) in enumerate(empleados):
            for columna, valor in enumerate((eid, nombre, rol, "Activo" if activo else "Inactivo")):
                self.tabla.setItem(fila, columna, QTableWidgetItem(str(valor)))

    def seleccionado(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            QMessageBox.warning(self, "Selecciona", "Selecciona un empleado.")
            return None
        return int(self.tabla.item(fila, 0).text())

    def agregar(self):
        nombre, ok = QInputDialog.getText(self, "Empleado", "Nombre:")
        if not ok or not nombre.strip(): return
        rol, ok = QInputDialog.getItem(self, "Rol", "Selecciona el rol:", ROLES_EMPLEADO, 2, False)
        if not ok: return
        pin, ok = QInputDialog.getText(self, "PIN", "PIN de 4 a 8 números:", QLineEdit.Password)
        if not ok: return
        try:
            eid = crear_empleado(nombre, pin, rol)
            registrar_auditoria(self.empleado_actual, "Crear", "Empleado", eid, f"{nombre} - {rol}")
            self.recargar()
        except Exception as error:
            QMessageBox.warning(self, "No se pudo crear", str(error))

    def editar(self):
        eid = self.seleccionado()
        if eid is None: return
        fila = self.tabla.currentRow()
        nombre_actual = self.tabla.item(fila, 1).text()
        rol_actual = self.tabla.item(fila, 2).text()
        activo_actual = self.tabla.item(fila, 3).text() == "Activo"
        nombre, ok = QInputDialog.getText(self, "Empleado", "Nombre:", text=nombre_actual)
        if not ok or not nombre.strip(): return
        rol, ok = QInputDialog.getItem(self, "Rol", "Rol:", ROLES_EMPLEADO, ROLES_EMPLEADO.index(rol_actual), False)
        if not ok: return
        activo = QMessageBox.question(self, "Estado", "¿El empleado debe quedar activo?", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes if activo_actual else QMessageBox.No) == QMessageBox.Yes
        if eid == self.empleado_actual["id"] and not activo:
            QMessageBox.warning(self, "No permitido", "No puedes desactivar tu propia sesión.")
            return
        try:
            actualizar_empleado(eid, nombre, rol, activo)
            registrar_auditoria(self.empleado_actual, "Editar", "Empleado", eid, f"{nombre} - {rol} - {'Activo' if activo else 'Inactivo'}")
            self.recargar()
        except Exception as error:
            QMessageBox.warning(self, "No se pudo editar", str(error))

    def cambiar_pin(self):
        eid = self.seleccionado()
        if eid is None: return
        pin, ok = QInputDialog.getText(self, "Nuevo PIN", "Nuevo PIN de 4 a 8 números:", QLineEdit.Password)
        if not ok: return
        try:
            cambiar_pin_empleado(eid, pin)
            registrar_auditoria(self.empleado_actual, "Cambiar PIN", "Empleado", eid, "PIN actualizado")
            QMessageBox.information(self, "PIN", "El PIN se actualizó correctamente.")
        except Exception as error:
            QMessageBox.warning(self, "PIN", str(error))

    def ver_auditoria(self):
        filas = obtener_auditoria(200)
        texto = "\n".join(
            f"{fecha} · {empleado} · {accion} {entidad} #{entidad_id or '-'} · {detalle}"
            for fecha, empleado, accion, entidad, entidad_id, detalle in filas
        ) or "Todavía no hay movimientos."
        dialogo = QDialog(self)
        dialogo.setWindowTitle("Auditoría")
        dialogo.resize(900, 600)
        layout = QVBoxLayout(dialogo)
        visor = QTextEdit()
        visor.setReadOnly(True)
        visor.setPlainText(texto)
        layout.addWidget(visor)
        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(dialogo.accept)
        layout.addWidget(cerrar)
        dialogo.exec()


class ConfiguracionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Configuración - La Esquina Manager")
        self.resize(460, 300)

        self.configuracion = cargar_configuracion()

        principal = QVBoxLayout(self)

        titulo = QLabel("CONFIGURACIÓN DEL NEGOCIO")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("""
            font-size: 22px;
            font-weight: bold;
            padding: 10px;
        """)
        principal.addWidget(titulo)

        formulario = QFormLayout()

        self.meta_venta_diaria = QDoubleSpinBox()
        self.meta_venta_diaria.setRange(0, 1000000)
        self.meta_venta_diaria.setDecimals(2)
        self.meta_venta_diaria.setPrefix("$")
        self.meta_venta_diaria.setValue(
            float(self.configuracion["meta_venta_diaria"])
        )

        self.meta_venta_semanal = QDoubleSpinBox()
        self.meta_venta_semanal.setRange(0, 10000000)
        self.meta_venta_semanal.setDecimals(2)
        self.meta_venta_semanal.setPrefix("$")
        self.meta_venta_semanal.setValue(
            float(self.configuracion["meta_venta_semanal"])
        )

        self.meta_personas_dia = QSpinBox()
        self.meta_personas_dia.setRange(1, 500)
        self.meta_personas_dia.setValue(
            int(self.configuracion["meta_personas_dia"])
        )

        formulario.addRow("Meta de venta diaria:", self.meta_venta_diaria)
        formulario.addRow("Meta de venta semanal:", self.meta_venta_semanal)
        formulario.addRow("Meta de personas por día:", self.meta_personas_dia)

        principal.addLayout(formulario)

        nota = QLabel(
            "Estas metas alimentan el Dashboard y puedes cambiarlas "
            "cuando quieras sin modificar el código."
        )
        nota.setWordWrap(True)
        nota.setStyleSheet("padding: 8px;")
        principal.addWidget(nota)

        botones = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        botones.accepted.connect(self.guardar)
        botones.rejected.connect(self.reject)
        principal.addWidget(botones)

    def guardar(self):
        nueva_configuracion = {
            "meta_venta_diaria": self.meta_venta_diaria.value(),
            "meta_venta_semanal": self.meta_venta_semanal.value(),
            "meta_personas_dia": self.meta_personas_dia.value(),
        }

        guardar_configuracion(nueva_configuracion)
        QMessageBox.information(
            self,
            "Configuración guardada",
            "Las metas se guardaron correctamente."
        )
        self.accept()


class DashboardDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Dashboard - La Esquina Manager")
        self.resize(1120, 820)

        config = cargar_configuracion()
        meta_venta_diaria = float(config["meta_venta_diaria"])
        meta_venta_semanal = float(config["meta_venta_semanal"])
        meta_personas_dia = int(config["meta_personas_dia"])

        exterior = QVBoxLayout(self)

        # SCROLL DEL DASHBOARD
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        contenido_scroll = QWidget()
        principal = QVBoxLayout(contenido_scroll)

        titulo = QLabel("DASHBOARD GERENCIAL")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("""
            font-size: 28px;
            font-weight: bold;
            padding: 8px;
        """)
        principal.addWidget(titulo)

        hoy = obtener_resumen_hoy()
        semana = obtener_resumen_semana_actual()
        comparacion = obtener_comparacion_semanal()
        mezcla = obtener_mezcla_clientes_hoy()

        tarjetas = QHBoxLayout()
        tarjetas.addWidget(self.crear_tarjeta(
            "VENTA HOY", f"${hoy['venta_total']:.2f}"
        ))
        tarjetas.addWidget(self.crear_tarjeta(
            "PERSONAS HOY", str(hoy["personas"])
        ))
        tarjetas.addWidget(self.crear_tarjeta(
            "TICKET PROMEDIO", f"${hoy['ticket_promedio']:.2f}"
        ))
        tarjetas.addWidget(self.crear_tarjeta(
            "VENTA / PERSONA", f"${hoy['promedio_persona']:.2f}"
        ))
        principal.addLayout(tarjetas)

        caja_metas = QGroupBox("Metas")
        layout_metas = QGridLayout(caja_metas)

        progreso_venta_hoy = self.crear_progreso(
            hoy["venta_total"],
            meta_venta_diaria,
            f"Venta diaria: ${hoy['venta_total']:.0f} / ${meta_venta_diaria:.0f}"
        )
        progreso_personas = self.crear_progreso(
            hoy["personas"],
            meta_personas_dia,
            f"Personas hoy: {hoy['personas']} / {meta_personas_dia}"
        )
        progreso_semana = self.crear_progreso(
            semana["venta_total"],
            meta_venta_semanal,
            f"Venta semanal: ${semana['venta_total']:.0f} / ${meta_venta_semanal:.0f}"
        )

        layout_metas.addWidget(progreso_venta_hoy, 0, 0)
        layout_metas.addWidget(progreso_personas, 0, 1)
        layout_metas.addWidget(progreso_semana, 1, 0, 1, 2)
        principal.addWidget(caja_metas)

        caja_semana = QGroupBox("Resumen semanal")
        layout_semana = QHBoxLayout(caja_semana)

        etiqueta_semana = QLabel(
            f"Venta semanal: ${semana['venta_total']:.2f}\n"
            f"Tickets: {semana['tickets']}\n"
            f"Personas: {semana['personas']}"
        )
        etiqueta_semana.setStyleSheet("font-size: 16px; padding: 6px;")
        layout_semana.addWidget(etiqueta_semana)

        if comparacion["variacion_pct"] is None:
            texto_comparacion = (
                "Comparación: sin datos suficientes de la semana anterior"
            )
        else:
            signo = "+" if comparacion["variacion_pct"] >= 0 else ""
            texto_comparacion = (
                f"Semana anterior: ${comparacion['anterior']:.2f}\n"
                f"Variación: {signo}{comparacion['variacion_pct']:.1f}%"
            )

        etiqueta_comparacion = QLabel(texto_comparacion)
        etiqueta_comparacion.setStyleSheet("font-size: 16px; padding: 6px;")
        layout_semana.addWidget(etiqueta_comparacion)
        principal.addWidget(caja_semana)

        caja_dias = QGroupBox("Ventas por día - Semana actual")
        layout_dias = QVBoxLayout(caja_dias)

        dias = obtener_ventas_por_dia_semana_actual()
        max_venta = max(
            [d["venta"] for d in dias] +
            [meta_venta_diaria if meta_venta_diaria else 1]
        )

        for d in dias:
            fila = QHBoxLayout()

            nombre = QLabel(
                f"{d['nombre']}  ${d['venta']:.0f}  |  {d['personas']} pers."
            )
            nombre.setMinimumWidth(180)

            barra = QProgressBar()
            barra.setRange(0, max(1, int(max_venta)))
            barra.setValue(int(d["venta"]))
            barra.setFormat(f"${d['venta']:.0f}")

            fila.addWidget(nombre)
            fila.addWidget(barra)
            layout_dias.addLayout(fila)

        principal.addWidget(caja_dias)

        contenido = QHBoxLayout()

        caja_clientes = QGroupBox("Clientes - Hoy")
        layout_clientes = QVBoxLayout(caja_clientes)

        etiqueta_mezcla = QLabel(
            f"Nuevos: {mezcla['nuevos']}  ({mezcla['pct_nuevos']:.0f}%)\n"
            f"Recurrentes: {mezcla['recurrentes']}  "
            f"({mezcla['pct_recurrentes']:.0f}%)\n"
            f"Sin clasificar: {mezcla['no_registrados']}"
        )
        etiqueta_mezcla.setStyleSheet("font-size: 16px; padding: 8px;")
        layout_clientes.addWidget(etiqueta_mezcla)

        tabla_origen = QTableWidget()
        tabla_origen.setColumnCount(2)
        tabla_origen.setHorizontalHeaderLabels(["Origen", "Personas"])

        origenes = obtener_resumen_origen_hoy()
        tabla_origen.setRowCount(len(origenes))

        for fila, (origen, personas) in enumerate(origenes):
            tabla_origen.setItem(
                fila, 0, QTableWidgetItem(str(origen))
            )
            tabla_origen.setItem(
                fila, 1, QTableWidgetItem(str(personas))
            )

        tabla_origen.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        tabla_origen.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeToContents
        )

        layout_clientes.addWidget(tabla_origen)
        contenido.addWidget(caja_clientes)

        caja_productos = QGroupBox("Productos más vendidos - Hoy")
        layout_productos = QVBoxLayout(caja_productos)

        tabla_productos = QTableWidget()
        tabla_productos.setColumnCount(3)
        tabla_productos.setHorizontalHeaderLabels(
            ["Producto", "Unidades", "Ingreso"]
        )

        productos = obtener_top_productos_hoy()
        tabla_productos.setRowCount(len(productos))

        for fila, (producto, unidades, ingreso) in enumerate(productos):
            tabla_productos.setItem(
                fila, 0, QTableWidgetItem(str(producto))
            )
            tabla_productos.setItem(
                fila, 1, QTableWidgetItem(str(unidades))
            )
            tabla_productos.setItem(
                fila, 2, QTableWidgetItem(f"${ingreso:.2f}")
            )

        tabla_productos.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        tabla_productos.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeToContents
        )
        tabla_productos.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeToContents
        )

        layout_productos.addWidget(tabla_productos)
        contenido.addWidget(caja_productos)
        principal.addLayout(contenido)

        principal.addStretch()

        scroll.setWidget(contenido_scroll)
        exterior.addWidget(scroll)

        boton_cerrar = QPushButton("Cerrar Dashboard")
        boton_cerrar.setMinimumHeight(42)
        boton_cerrar.clicked.connect(self.accept)
        exterior.addWidget(boton_cerrar)

    def crear_tarjeta(self, titulo, valor):
        caja = QGroupBox()
        layout = QVBoxLayout(caja)

        etiqueta_titulo = QLabel(titulo)
        etiqueta_titulo.setAlignment(Qt.AlignCenter)
        etiqueta_titulo.setStyleSheet(
            "font-size: 14px; font-weight: bold;"
        )

        etiqueta_valor = QLabel(valor)
        etiqueta_valor.setAlignment(Qt.AlignCenter)
        etiqueta_valor.setStyleSheet(
            "font-size: 25px; font-weight: bold; padding: 8px;"
        )

        layout.addWidget(etiqueta_titulo)
        layout.addWidget(etiqueta_valor)

        return caja

    def crear_progreso(self, actual, meta, texto):
        contenedor = QWidget()
        layout = QVBoxLayout(contenedor)
        layout.setContentsMargins(4, 4, 4, 4)

        etiqueta = QLabel(texto)
        etiqueta.setStyleSheet(
            "font-size: 14px; font-weight: bold;"
        )

        barra = QProgressBar()
        barra.setRange(0, 100)

        porcentaje = (
            int(min((actual / meta) * 100, 100))
            if meta else 0
        )

        barra.setValue(porcentaje)
        barra.setFormat(f"{porcentaje}%")

        layout.addWidget(etiqueta)
        layout.addWidget(barra)

        return contenedor


class HistorialDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Historial de ventas - La Esquina Manager")
        self.resize(980, 650)

        principal = QVBoxLayout(self)

        titulo = QLabel("HISTORIAL DE VENTAS")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet(
            "font-size: 22px; font-weight: bold; padding: 8px;"
        )
        principal.addWidget(titulo)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(6)
        self.tabla.setHorizontalHeaderLabels(
            ["Folio", "Fecha", "Total", "Pago", "Personas", "Origen"]
        )
        self.tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SingleSelection)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.tabla.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeToContents
        )
        self.tabla.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeToContents
        )
        self.tabla.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeToContents
        )
        self.tabla.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeToContents
        )
        self.tabla.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.Stretch
        )
        self.tabla.itemSelectionChanged.connect(self.mostrar_detalle)
        principal.addWidget(self.tabla, 2)

        detalle_box = QGroupBox("Detalle de la venta seleccionada")
        detalle_layout = QVBoxLayout(detalle_box)

        self.detalle = QTableWidget()
        self.detalle.setColumnCount(4)
        self.detalle.setHorizontalHeaderLabels(
            ["Producto", "Cantidad", "P. unitario", "Importe"]
        )
        self.detalle.setEditTriggers(QTableWidget.NoEditTriggers)
        self.detalle.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        for col in (1, 2, 3):
            self.detalle.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeToContents
            )

        detalle_layout.addWidget(self.detalle)
        principal.addWidget(detalle_box, 1)

        botones = QHBoxLayout()

        boton_actualizar = QPushButton("Actualizar")
        boton_actualizar.setMinimumHeight(42)
        boton_actualizar.clicked.connect(self.recargar)

        boton_reimprimir = QPushButton("Reimprimir ticket")
        boton_reimprimir.setMinimumHeight(42)
        boton_reimprimir.setStyleSheet("""
            QPushButton {
                font-size: 15px;
                font-weight: bold;
                background-color: #f2c94c;
                border-radius: 6px;
            }
        """)
        boton_reimprimir.clicked.connect(self.reimprimir)

        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.setMinimumHeight(42)
        boton_cerrar.clicked.connect(self.accept)

        botones.addWidget(boton_actualizar)
        botones.addWidget(boton_reimprimir)
        botones.addWidget(boton_cerrar)
        principal.addLayout(botones)

        self.recargar()

    def recargar(self):
        ventas = obtener_historial_ventas()
        self.tabla.setRowCount(len(ventas))

        for fila, venta in enumerate(ventas):
            venta_id, fecha, total, metodo, personas, origen = venta

            valores = [
                str(venta_id),
                str(fecha),
                f"${total:.2f}",
                str(metodo),
                str(personas),
                str(origen),
            ]

            for columna, valor in enumerate(valores):
                self.tabla.setItem(
                    fila, columna, QTableWidgetItem(valor)
                )

        self.detalle.setRowCount(0)

    def venta_seleccionada(self):
        fila = self.tabla.currentRow()

        if fila < 0:
            QMessageBox.warning(
                self,
                "Selecciona una venta",
                "Primero selecciona una venta del historial."
            )
            return None

        return {
            "id": int(self.tabla.item(fila, 0).text()),
            "fecha": self.tabla.item(fila, 1).text(),
            "total": float(
                self.tabla.item(fila, 2).text().replace("$", "")
            ),
            "metodo": self.tabla.item(fila, 3).text(),
            "personas": int(self.tabla.item(fila, 4).text()),
            "origen": self.tabla.item(fila, 5).text(),
        }

    def mostrar_detalle(self):
        venta = self.venta_seleccionada()

        if venta is None:
            return

        productos = obtener_detalle_venta(venta["id"])
        self.detalle.setRowCount(len(productos))

        for fila, (producto, cantidad, precio) in enumerate(productos):
            importe = cantidad * precio

            self.detalle.setItem(
                fila, 0, QTableWidgetItem(str(producto))
            )
            self.detalle.setItem(
                fila, 1, QTableWidgetItem(str(cantidad))
            )
            self.detalle.setItem(
                fila, 2, QTableWidgetItem(f"${precio:.2f}")
            )
            self.detalle.setItem(
                fila, 3, QTableWidgetItem(f"${importe:.2f}")
            )

    def reimprimir(self):
        venta = self.venta_seleccionada()

        if venta is None:
            return

        detalle = obtener_detalle_venta(venta["id"])

        if not detalle:
            QMessageBox.warning(
                self,
                "Sin detalle",
                "Esta venta no tiene productos registrados."
            )
            return

        productos = []

        for producto, cantidad, precio in detalle:
            for _ in range(int(cantidad)):
                productos.append((producto, precio))

        # Para ventas históricas no siempre conocemos recibido/cambio.
        ruta = generar_ticket_pdf(
            venta_id=venta["id"],
            productos=productos,
            total=venta["total"],
            metodo=venta["metodo"],
            personas=venta["personas"],
            origen=venta["origen"],
            recibido=None,
            cambio=None,
        )

        respuesta = QMessageBox.question(
            self,
            "Reimprimir ticket",
            f"¿Reimprimir el ticket #{venta['id']}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        if respuesta != QMessageBox.Yes:
            return

        try:
            imprimir_ticket(ruta)
            QMessageBox.information(
                self,
                "Ticket enviado",
                f"El ticket #{venta['id']} se envió a la impresora."
            )
        except Exception as error:
            QMessageBox.warning(
                self,
                "No se pudo imprimir",
                str(error)
            )


class ProductosDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Administrar productos - La Esquina Manager")
        self.resize(850, 560)

        principal = QVBoxLayout(self)

        titulo = QLabel("ADMINISTRAR PRODUCTOS")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet(
            "font-size: 22px; font-weight: bold; padding: 8px;"
        )
        principal.addWidget(titulo)

        nota = QLabel(
            "Los productos desactivados dejan de aparecer en el POS, "
            "pero conservan su historial de ventas."
        )
        nota.setWordWrap(True)
        principal.addWidget(nota)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(5)
        self.tabla.setHorizontalHeaderLabels(
            ["ID", "Producto", "Precio", "Categoría", "Estado"]
        )
        self.tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SingleSelection)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.tabla.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        self.tabla.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeToContents
        )
        self.tabla.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.Stretch
        )
        self.tabla.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeToContents
        )
        principal.addWidget(self.tabla)

        botones = QHBoxLayout()

        boton_agregar = QPushButton("Agregar producto")
        boton_agregar.setMinimumHeight(42)
        boton_agregar.clicked.connect(self.agregar)

        boton_editar = QPushButton("Editar / cambiar precio")
        boton_editar.setMinimumHeight(42)
        boton_editar.clicked.connect(self.editar)

        boton_estado = QPushButton("Activar / Desactivar")
        boton_estado.setMinimumHeight(42)
        boton_estado.clicked.connect(self.cambiar_estado)

        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.setMinimumHeight(42)
        boton_cerrar.clicked.connect(self.accept)

        botones.addWidget(boton_agregar)
        botones.addWidget(boton_editar)
        botones.addWidget(boton_estado)
        botones.addWidget(boton_cerrar)

        principal.addLayout(botones)
        self.recargar()

    def recargar(self):
        productos = obtener_productos(solo_activos=False)
        self.tabla.setRowCount(len(productos))

        for fila, producto in enumerate(productos):
            producto_id, nombre, precio, categoria, activo, _orden = producto

            self.tabla.setItem(
                fila, 0, QTableWidgetItem(str(producto_id))
            )
            self.tabla.setItem(
                fila, 1, QTableWidgetItem(nombre)
            )
            self.tabla.setItem(
                fila, 2, QTableWidgetItem(f"${precio:.2f}")
            )
            self.tabla.setItem(
                fila, 3, QTableWidgetItem(categoria or "General")
            )
            self.tabla.setItem(
                fila, 4,
                QTableWidgetItem("Activo" if activo else "Inactivo")
            )

    def _seleccionado(self):
        fila = self.tabla.currentRow()

        if fila < 0:
            QMessageBox.warning(
                self,
                "Selecciona un producto",
                "Primero selecciona una fila de la tabla."
            )
            return None

        producto_id = int(self.tabla.item(fila, 0).text())
        nombre = self.tabla.item(fila, 1).text()
        precio = float(
            self.tabla.item(fila, 2).text().replace("$", "")
        )
        categoria = self.tabla.item(fila, 3).text()
        activo = self.tabla.item(fila, 4).text() == "Activo"

        return producto_id, nombre, precio, categoria, activo

    def agregar(self):
        nombre, ok = QInputDialog.getText(
            self,
            "Nuevo producto",
            "Nombre del producto:"
        )
        if not ok or not nombre.strip():
            return

        precio, ok = QInputDialog.getDouble(
            self,
            "Precio de venta",
            f"Precio para {nombre.strip()}:",
            value=0.0,
            minValue=0.0,
            maxValue=100000.0,
            decimals=2,
        )
        if not ok:
            return

        categoria, ok = QInputDialog.getItem(
            self,
            "Categoría",
            "Selecciona una categoría:",
            ["Alimentos", "Bebidas", "Bites", "Paquetes", "Extras", "General"],
            0,
            True,
        )
        if not ok:
            return

        try:
            agregar_producto(nombre, precio, categoria)
        except Exception as error:
            QMessageBox.critical(
                self,
                "No se pudo agregar",
                str(error)
            )
            return

        self.recargar()

    def editar(self):
        seleccionado = self._seleccionado()
        if seleccionado is None:
            return

        producto_id, nombre_actual, precio_actual, categoria_actual, _activo = seleccionado

        nombre, ok = QInputDialog.getText(
            self,
            "Editar producto",
            "Nombre:",
            text=nombre_actual,
        )
        if not ok or not nombre.strip():
            return

        precio, ok = QInputDialog.getDouble(
            self,
            "Cambiar precio",
            "Precio de venta:",
            value=precio_actual,
            minValue=0.0,
            maxValue=100000.0,
            decimals=2,
        )
        if not ok:
            return

        categoria, ok = QInputDialog.getText(
            self,
            "Categoría",
            "Categoría:",
            text=categoria_actual,
        )
        if not ok:
            return

        try:
            actualizar_producto(
                producto_id,
                nombre,
                precio,
                categoria,
            )
        except Exception as error:
            QMessageBox.critical(
                self,
                "No se pudo actualizar",
                str(error)
            )
            return

        self.recargar()

    def cambiar_estado(self):
        seleccionado = self._seleccionado()
        if seleccionado is None:
            return

        producto_id, nombre, _precio, _categoria, activo = seleccionado

        accion = "desactivar" if activo else "activar"

        respuesta = QMessageBox.question(
            self,
            "Confirmar",
            f"¿Deseas {accion} '{nombre}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if respuesta != QMessageBox.Yes:
            return

        establecer_producto_activo(producto_id, not activo)
        self.recargar()


class GastoEdicionDialog(QDialog):
    def __init__(self, gasto=None, parent=None):
        super().__init__(parent)
        self.gasto = gasto
        self.setWindowTitle(
            "Corregir gasto" if gasto else "Registrar gasto"
        )
        self.resize(500, 390)
        principal = QVBoxLayout(self)
        formulario = QFormLayout()

        self.concepto = QLineEdit()
        self.categoria = QComboBox()
        self.categoria.addItems(CATEGORIAS_GASTO)
        self.importe = QDoubleSpinBox()
        self.importe.setRange(0.01, 10000000)
        self.importe.setDecimals(2)
        self.importe.setPrefix("$")
        self.fecha = QDateTimeEdit(QDateTime.currentDateTime())
        self.fecha.setDisplayFormat("dd/MM/yyyy HH:mm:ss")
        self.fecha.setCalendarPopup(True)
        self.metodo = QComboBox()
        self.metodo.addItems(METODOS_GASTO)
        self.motivo = QTextEdit()
        self.motivo.setMaximumHeight(75)

        formulario.addRow("Concepto:", self.concepto)
        formulario.addRow("Categoria:", self.categoria)
        formulario.addRow("Importe:", self.importe)
        formulario.addRow("Fecha y hora:", self.fecha)
        formulario.addRow("Metodo de pago:", self.metodo)
        if gasto:
            formulario.addRow("Motivo de la correccion:", self.motivo)

            self.concepto.setText(gasto["concepto"])
            self.categoria.setCurrentText(gasto["categoria"])
            self.importe.setValue(float(gasto["importe"]))
            fecha = QDateTime.fromString(gasto["fecha"], "yyyy-MM-dd HH:mm:ss")
            if fecha.isValid():
                self.fecha.setDateTime(fecha)
            self.metodo.setCurrentText(gasto["metodo_pago"])

        principal.addLayout(formulario)
        nota = QLabel(
            "Las correcciones no borran el registro anterior; "
            "quedan guardadas en la auditoria."
            if gasto else
            "El gasto se incluira en el resultado del dia."
        )
        nota.setWordWrap(True)
        principal.addWidget(nota)

        botones = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        botones.accepted.connect(self.validar)
        botones.rejected.connect(self.reject)
        principal.addWidget(botones)

    def validar(self):
        if not self.concepto.text().strip():
            QMessageBox.warning(self, "Dato faltante", "Escribe el concepto.")
            return
        if self.gasto and not self.motivo.toPlainText().strip():
            QMessageBox.warning(
                self, "Dato faltante",
                "Escribe el motivo de la correccion."
            )
            return
        self.accept()

    def datos(self):
        return {
            "concepto": self.concepto.text().strip(),
            "categoria": self.categoria.currentText(),
            "importe": self.importe.value(),
            "fecha": self.fecha.dateTime().toString("yyyy-MM-dd HH:mm:ss"),
            "metodo_pago": self.metodo.currentText(),
            "motivo": self.motivo.toPlainText().strip(),
        }


class GastosDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gastos del dia - La Esquina Manager")
        self.resize(1050, 620)
        principal = QVBoxLayout(self)

        titulo = QLabel("GASTOS DEL DIA")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("font-size: 22px; font-weight: bold; padding: 8px;")
        principal.addWidget(titulo)

        nota = QLabel(
            "Los gastos anulados permanecen visibles y no se suman. "
            "Todas las correcciones quedan registradas."
        )
        nota.setWordWrap(True)
        principal.addWidget(nota)

        self.tabla = QTableWidget(0, 7)
        self.tabla.setHorizontalHeaderLabels([
            "ID", "Fecha / hora", "Concepto", "Categoria",
            "Importe", "Metodo", "Estado",
        ])
        self.tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SingleSelection)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch
        )
        principal.addWidget(self.tabla)

        self.total = QLabel()
        self.total.setAlignment(Qt.AlignRight)
        self.total.setStyleSheet("font-size: 18px; font-weight: bold; padding: 6px;")
        principal.addWidget(self.total)

        botones = QHBoxLayout()
        for texto, funcion in (
            ("Registrar gasto", self.registrar),
            ("Corregir seleccionado", self.corregir),
            ("Anular seleccionado", self.anular),
            ("Ver auditoria", self.ver_auditoria),
        ):
            boton = QPushButton(texto)
            boton.setMinimumHeight(42)
            boton.clicked.connect(funcion)
            botones.addWidget(boton)
        cerrar = QPushButton("Cerrar")
        cerrar.setMinimumHeight(42)
        cerrar.clicked.connect(self.accept)
        botones.addWidget(cerrar)
        principal.addLayout(botones)
        self.recargar()

    def recargar(self):
        gastos = obtener_gastos_hoy(incluir_anulados=True)
        self.tabla.setRowCount(len(gastos))
        total = 0.0
        for fila, gasto in enumerate(gastos):
            valores = (
                gasto["id"], gasto["fecha"], gasto["concepto"],
                gasto["categoria"], f"${gasto['importe']:.2f}",
                gasto["metodo_pago"], gasto["estado"],
            )
            for columna, valor in enumerate(valores):
                item = QTableWidgetItem(str(valor))
                if gasto["estado"] == "Anulado":
                    item.setForeground(Qt.gray)
                self.tabla.setItem(fila, columna, item)
            if gasto["estado"] == "Activo":
                total += gasto["importe"]
        self.total.setText(f"Gastos activos del dia: ${total:.2f}")

    def gasto_seleccionado(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            QMessageBox.warning(
                self, "Selecciona un gasto",
                "Primero selecciona una fila de la tabla."
            )
            return None
        return obtener_gasto(int(self.tabla.item(fila, 0).text()))

    def registrar(self):
        dialogo = GastoEdicionDialog(parent=self)
        if dialogo.exec() != QDialog.Accepted:
            return
        datos = dialogo.datos()
        datos.pop("motivo")
        try:
            registrar_gasto(**datos)
        except Exception as error:
            QMessageBox.critical(self, "No se pudo registrar", str(error))
            return
        self.recargar()

    def corregir(self):
        gasto = self.gasto_seleccionado()
        if gasto is None:
            return
        if gasto["estado"] != "Activo":
            QMessageBox.warning(
                self, "Gasto anulado",
                "Un gasto anulado ya no puede corregirse."
            )
            return
        dialogo = GastoEdicionDialog(gasto, self)
        if dialogo.exec() != QDialog.Accepted:
            return
        try:
            corregir_gasto(gasto["id"], **dialogo.datos())
        except Exception as error:
            QMessageBox.critical(self, "No se pudo corregir", str(error))
            return
        self.recargar()

    def anular(self):
        gasto = self.gasto_seleccionado()
        if gasto is None:
            return
        motivo, ok = QInputDialog.getText(
            self, "Anular gasto",
            "Escribe el motivo obligatorio de la anulacion:"
        )
        if not ok or not motivo.strip():
            return
        respuesta = QMessageBox.question(
            self, "Confirmar anulacion",
            "El gasto seguira visible en el historial, marcado como anulado.\n\n"
            "¿Deseas continuar?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if respuesta != QMessageBox.Yes:
            return
        try:
            anular_gasto(gasto["id"], motivo)
        except Exception as error:
            QMessageBox.critical(self, "No se pudo anular", str(error))
            return
        self.recargar()

    def ver_auditoria(self):
        gasto = self.gasto_seleccionado()
        if gasto is None:
            return
        eventos = obtener_eventos_gasto(gasto["id"])
        texto = []
        for tipo, fecha, motivo, anteriores, nuevos in eventos:
            bloque = f"{fecha} - {tipo}"
            if motivo:
                bloque += f"\nMotivo: {motivo}"
            if anteriores:
                bloque += f"\nDatos anteriores: {anteriores}"
            if nuevos:
                bloque += f"\nDatos nuevos: {nuevos}"
            texto.append(bloque)
        QMessageBox.information(
            self, f"Auditoria del gasto #{gasto['id']}",
            "\n\n".join(texto) or "No hay movimientos."
        )


class PedidosMovilDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pedidos de meseros")
        self.resize(1050, 650)
        self.pedido_cargado = None
        principal = QVBoxLayout(self)

        titulo = QLabel("PEDIDOS DE CELULARES Y TABLETAS")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("font-size:22px;font-weight:bold;padding:8px;")
        principal.addWidget(titulo)

        direccion = QLabel(
            f"Dirección para los meseros: {mobile_url()}\n"
            "Los celulares deben estar conectados al mismo Wi-Fi."
        )
        direccion.setTextInteractionFlags(Qt.TextSelectableByMouse)
        direccion.setWordWrap(True)
        principal.addWidget(direccion)

        self.tabla = QTableWidget(0, 7)
        self.tabla.setHorizontalHeaderLabels([
            "Pedido", "Hora", "Mesa", "Mesero", "Notas", "Total", "Estado"
        ])
        self.tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SingleSelection)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        principal.addWidget(self.tabla)

        self.detalle = QTableWidget(0, 4)
        self.detalle.setHorizontalHeaderLabels([
            "Producto", "Cantidad", "Precio", "Importe"
        ])
        self.detalle.setEditTriggers(QTableWidget.NoEditTriggers)
        self.detalle.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.detalle.setMaximumHeight(210)
        principal.addWidget(self.detalle)
        self.tabla.itemSelectionChanged.connect(self.mostrar_detalle)

        botones = QHBoxLayout()
        cargar = QPushButton("Cargar pedido en caja")
        cargar.setMinimumHeight(45)
        cargar.setStyleSheet("font-weight:bold;background:#27ae60;color:white;")
        cargar.clicked.connect(self.cargar)
        cancelar = QPushButton("Cancelar pedido")
        cancelar.setMinimumHeight(45)
        cancelar.clicked.connect(self.cancelar)
        actualizar = QPushButton("Actualizar")
        actualizar.setMinimumHeight(45)
        actualizar.clicked.connect(self.recargar)
        cerrar = QPushButton("Cerrar")
        cerrar.setMinimumHeight(45)
        cerrar.clicked.connect(self.reject)
        for boton in (cargar, cancelar, actualizar, cerrar):
            botones.addWidget(boton)
        principal.addLayout(botones)
        self.recargar()

    def recargar(self):
        pedidos = obtener_pedidos_movil()
        self.tabla.setRowCount(len(pedidos))
        for fila, pedido in enumerate(pedidos):
            pedido_id, fecha, mesa, mesero, notas, total, estado, _venta_id = pedido
            valores = (
                pedido_id, fecha[11:16], mesa, mesero, notas,
                f"${total:.2f}", estado,
            )
            for columna, valor in enumerate(valores):
                self.tabla.setItem(fila, columna, QTableWidgetItem(str(valor)))
        self.detalle.setRowCount(0)

    def pedido_seleccionado(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            QMessageBox.warning(
                self, "Selecciona un pedido",
                "Primero selecciona una fila de la tabla."
            )
            return None
        return int(self.tabla.item(fila, 0).text())

    def mostrar_detalle(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            return
        pedido_id = int(self.tabla.item(fila, 0).text())
        detalles = obtener_detalle_pedido_movil(pedido_id)
        self.detalle.setRowCount(len(detalles))
        for numero, (_producto_id, producto, cantidad, precio) in enumerate(detalles):
            valores = (producto, cantidad, f"${precio:.2f}", f"${cantidad * precio:.2f}")
            for columna, valor in enumerate(valores):
                self.detalle.setItem(numero, columna, QTableWidgetItem(str(valor)))

    def cargar(self):
        pedido_id = self.pedido_seleccionado()
        if pedido_id is None:
            return
        detalles = obtener_detalle_pedido_movil(pedido_id)
        if not detalles:
            QMessageBox.warning(self, "Pedido vacío", "El pedido no tiene productos.")
            return
        actualizar_estado_pedido_movil(pedido_id, "En caja")
        self.pedido_cargado = (pedido_id, detalles)
        self.accept()

    def cancelar(self):
        pedido_id = self.pedido_seleccionado()
        if pedido_id is None:
            return
        respuesta = QMessageBox.question(
            self, "Cancelar pedido",
            "El pedido quedará cancelado y no se contará como venta.\n\n"
            "¿Deseas continuar?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if respuesta != QMessageBox.Yes:
            return
        actualizar_estado_pedido_movil(pedido_id, "Cancelado")
        self.recargar()


class MesasDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mapa de mesas")
        self.resize(1050, 720)
        self.mesa_seleccionada = None
        self.carga_mesa = None
        principal = QVBoxLayout(self)

        titulo = QLabel("MESAS Y BARRA")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("font-size:22px;font-weight:bold;padding:6px;")
        principal.addWidget(titulo)
        leyenda = QLabel(
            "Verde: libre   ·   Naranja: ocupada   ·   "
            "Una mesa permanece ocupada hasta cobrar o cancelar sus pedidos."
        )
        leyenda.setAlignment(Qt.AlignCenter)
        principal.addWidget(leyenda)

        self.panel_mesas = QWidget()
        self.grid_mesas = QGridLayout(self.panel_mesas)
        principal.addWidget(self.panel_mesas)

        self.resumen = QLabel("Selecciona una mesa ocupada para ver su cuenta.")
        self.resumen.setStyleSheet("font-size:15px;font-weight:bold;padding:6px;")
        principal.addWidget(self.resumen)

        self.detalle = QTableWidget(0, 5)
        self.detalle.setHorizontalHeaderLabels([
            "Pedido", "Producto", "Cantidad", "Precio", "Importe"
        ])
        self.detalle.setEditTriggers(QTableWidget.NoEditTriggers)
        self.detalle.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        principal.addWidget(self.detalle)

        botones = QHBoxLayout()
        cargar = QPushButton("Cargar cuenta completa en caja")
        cargar.setMinimumHeight(48)
        cargar.setStyleSheet("font-weight:bold;background:#27ae60;color:white;")
        cargar.clicked.connect(self.cargar_mesa)
        refrescar = QPushButton("Actualizar mesas")
        refrescar.setMinimumHeight(48)
        refrescar.clicked.connect(self.recargar)
        cerrar = QPushButton("Cerrar")
        cerrar.setMinimumHeight(48)
        cerrar.clicked.connect(self.reject)
        botones.addWidget(cargar)
        botones.addWidget(refrescar)
        botones.addWidget(cerrar)
        principal.addLayout(botones)
        self.recargar()

    def recargar(self):
        while self.grid_mesas.count():
            item = self.grid_mesas.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for indice, datos in enumerate(obtener_resumen_mesas()):
            mesa = datos["mesa"]
            if datos["ocupada"]:
                texto = f"{mesa}\n${datos['total']:.2f}\n{datos['pedidos']} pedido(s)"
                color = "#e7a33e"
            else:
                texto = f"{mesa}\nLIBRE"
                color = "#6fcf97"
            boton = QPushButton(texto)
            boton.setMinimumSize(150, 75)
            boton.setStyleSheet(
                f"font-size:14px;font-weight:bold;background:{color};"
                "border:1px solid #888;border-radius:8px;"
            )
            boton.clicked.connect(
                lambda checked=False, nombre=mesa: self.seleccionar_mesa(nombre)
            )
            self.grid_mesas.addWidget(boton, indice // 5, indice % 5)
        if self.mesa_seleccionada:
            self.seleccionar_mesa(self.mesa_seleccionada)

    def seleccionar_mesa(self, mesa):
        self.mesa_seleccionada = mesa
        pedidos = obtener_pedidos_mesa(mesa)
        filas = []
        total = 0.0
        notas = []
        for pedido in pedidos:
            pedido_id, fecha, _mesa, mesero, nota, subtotal, estado, cocina, _venta = pedido
            total += subtotal
            if nota:
                notas.append(f"#{pedido_id}: {nota}")
            for _producto_id, producto, cantidad, precio in obtener_detalle_pedido_movil(pedido_id):
                filas.append((pedido_id, producto, cantidad, precio, cantidad * precio))
        self.detalle.setRowCount(len(filas))
        for numero, valores in enumerate(filas):
            for columna, valor in enumerate(valores):
                texto = f"${valor:.2f}" if columna in (3, 4) else str(valor)
                self.detalle.setItem(numero, columna, QTableWidgetItem(texto))
        if pedidos:
            extra = f"   ·   Notas: {' | '.join(notas)}" if notas else ""
            self.resumen.setText(
                f"{mesa}: {len(pedidos)} pedido(s) · Total ${total:.2f}{extra}"
            )
        else:
            self.resumen.setText(f"{mesa}: LIBRE")

    def cargar_mesa(self):
        if not self.mesa_seleccionada:
            QMessageBox.warning(self, "Selecciona una mesa", "Primero selecciona una mesa.")
            return
        pedidos = obtener_pedidos_mesa(self.mesa_seleccionada)
        if not pedidos:
            QMessageBox.information(self, "Mesa libre", "Esta mesa no tiene pedidos pendientes.")
            return
        pedido_ids = []
        detalles = []
        for pedido in pedidos:
            pedido_id = pedido[0]
            pedido_ids.append(pedido_id)
            detalles.extend(obtener_detalle_pedido_movil(pedido_id))
            actualizar_estado_pedido_movil(pedido_id, "En caja")
        self.carga_mesa = (self.mesa_seleccionada, pedido_ids, detalles)
        self.accept()


class CuentasActivasDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cuentas activas")
        self.resize(1050, 680)
        self.cuenta_cargada = None
        principal = QVBoxLayout(self)

        titulo = QLabel("CUENTAS ACTIVAS")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("font-size:22px;font-weight:bold;padding:7px;")
        principal.addWidget(titulo)

        self.resumen_general = QLabel()
        self.resumen_general.setAlignment(Qt.AlignCenter)
        self.resumen_general.setStyleSheet(
            "font-size:15px;font-weight:bold;padding:7px;background:#fff3cd;"
        )
        principal.addWidget(self.resumen_general)

        self.tabla = QTableWidget(0, 7)
        self.tabla.setHorizontalHeaderLabels([
            "Mesa / Barra", "Abierta", "Tiempo", "Mesero(s)",
            "Pedidos", "Cocina", "Total",
        ])
        self.tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SingleSelection)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tabla.itemSelectionChanged.connect(self.mostrar_detalle)
        principal.addWidget(self.tabla)

        self.detalle = QTableWidget(0, 5)
        self.detalle.setHorizontalHeaderLabels([
            "Pedido", "Producto", "Cantidad", "Precio", "Importe"
        ])
        self.detalle.setEditTriggers(QTableWidget.NoEditTriggers)
        self.detalle.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.detalle.setMaximumHeight(220)
        principal.addWidget(self.detalle)

        self.notas = QLabel("Selecciona una cuenta para ver sus productos y notas.")
        self.notas.setWordWrap(True)
        self.notas.setStyleSheet("padding:6px;font-weight:bold;")
        principal.addWidget(self.notas)

        botones = QHBoxLayout()
        cargar = QPushButton("Cargar cuenta en caja")
        cargar.setMinimumHeight(48)
        cargar.setStyleSheet("font-weight:bold;background:#27ae60;color:white;")
        cargar.clicked.connect(self.cargar)
        actualizar = QPushButton("Actualizar")
        actualizar.setMinimumHeight(48)
        actualizar.clicked.connect(self.recargar)
        cerrar = QPushButton("Cerrar")
        cerrar.setMinimumHeight(48)
        cerrar.clicked.connect(self.reject)
        botones.addWidget(cargar)
        botones.addWidget(actualizar)
        botones.addWidget(cerrar)
        principal.addLayout(botones)

        self.temporizador = QTimer(self)
        self.temporizador.timeout.connect(self.recargar)
        self.temporizador.start(5000)
        self.recargar()

    @staticmethod
    def _tiempo_transcurrido(fecha):
        if not fecha:
            return "-"
        try:
            minutos = max(0, int(
                (datetime.now() - datetime.strptime(fecha, "%Y-%m-%d %H:%M:%S"))
                .total_seconds() // 60
            ))
            horas, minutos = divmod(minutos, 60)
            return f"{horas} h {minutos} min" if horas else f"{minutos} min"
        except ValueError:
            return "-"

    def recargar(self):
        mesa_actual = None
        fila_actual = self.tabla.currentRow()
        if fila_actual >= 0 and self.tabla.item(fila_actual, 0):
            mesa_actual = self.tabla.item(fila_actual, 0).text()
        cuentas = [m for m in obtener_resumen_mesas() if m["ocupada"]]
        self.tabla.setRowCount(len(cuentas))
        total_general = 0.0
        fila_a_seleccionar = None
        for fila, cuenta in enumerate(cuentas):
            pedidos = obtener_pedidos_mesa(cuenta["mesa"])
            estados = sorted({p[7] for p in pedidos})
            valores = (
                cuenta["mesa"], cuenta["desde"][11:16],
                self._tiempo_transcurrido(cuenta["desde"]),
                cuenta["meseros"], cuenta["pedidos"],
                ", ".join(estados), f"${cuenta['total']:.2f}",
            )
            total_general += cuenta["total"]
            for columna, valor in enumerate(valores):
                self.tabla.setItem(fila, columna, QTableWidgetItem(str(valor)))
            if cuenta["mesa"] == mesa_actual:
                fila_a_seleccionar = fila
        self.resumen_general.setText(
            f"Cuentas abiertas: {len(cuentas)}   ·   Total acumulado: ${total_general:.2f}"
        )
        if fila_a_seleccionar is not None:
            self.tabla.selectRow(fila_a_seleccionar)
        elif not cuentas:
            self.detalle.setRowCount(0)
            self.notas.setText("No hay cuentas activas.")

    def mesa_seleccionada(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            QMessageBox.warning(
                self, "Selecciona una cuenta",
                "Primero selecciona una cuenta activa."
            )
            return None
        return self.tabla.item(fila, 0).text()

    def mostrar_detalle(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            return
        mesa = self.tabla.item(fila, 0).text()
        pedidos = obtener_pedidos_mesa(mesa)
        filas = []
        notas = []
        for pedido in pedidos:
            pedido_id, _fecha, _mesa, mesero, nota, _total, _estado, cocina, _venta = pedido
            if nota:
                notas.append(f"Pedido #{pedido_id} ({mesero}): {nota}")
            for _producto_id, producto, cantidad, precio in obtener_detalle_pedido_movil(pedido_id):
                filas.append((pedido_id, producto, cantidad, precio, cantidad * precio))
        self.detalle.setRowCount(len(filas))
        for numero, valores in enumerate(filas):
            for columna, valor in enumerate(valores):
                texto = f"${valor:.2f}" if columna in (3, 4) else str(valor)
                self.detalle.setItem(numero, columna, QTableWidgetItem(texto))
        self.notas.setText("Notas: " + (" | ".join(notas) if notas else "Sin notas"))

    def cargar(self):
        mesa = self.mesa_seleccionada()
        if not mesa:
            return
        pedidos = obtener_pedidos_mesa(mesa)
        pedido_ids = []
        detalles = []
        for pedido in pedidos:
            pedido_id = pedido[0]
            pedido_ids.append(pedido_id)
            detalles.extend(obtener_detalle_pedido_movil(pedido_id))
            actualizar_estado_pedido_movil(pedido_id, "En caja")
        self.cuenta_cargada = (mesa, pedido_ids, detalles)
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        if not hay_empleados():
            inicial = ConfiguracionInicialDialog(self)
            if inicial.exec() != QDialog.Accepted:
                raise SystemExit("Configuración inicial cancelada")

        acceso = InicioSesionDialog(parent=self)
        if acceso.exec() != QDialog.Accepted or not acceso.empleado:
            raise SystemExit("Inicio de sesión cancelado")
        self.empleado_actual = acceso.empleado
        registrar_auditoria(
            self.empleado_actual, "Iniciar sesión", "Sistema", None,
            self.empleado_actual["rol"],
        )

        self.setWindowTitle(
            f"La Esquina Manager - {self.empleado_actual['nombre']} "
            f"({self.empleado_actual['rol']})"
        )
        self.resize(1200, 750)

        self.carrito = []
        self.total = 0.0
        self.notas_rapidas = []
        self.renglones_pedido = []
        self.pedidos_movil_actuales = []
        self.mesa_cuenta_actual = None
        self.carrito_cuenta_original = []
        self.carrito_restante_division = []
        self.servidor_movil_url = None
        self.servidor_movil_error = None

        self.productos = []
        self.cargar_productos()
        try:
            self.servidor_movil_url = start_mobile_server()
        except Exception as error:
            self.servidor_movil_error = str(error)
        self.crear_interfaz()

        self.temporizador_pedidos = QTimer(self)
        self.temporizador_pedidos.timeout.connect(
            self.actualizar_contador_pedidos
        )
        self.temporizador_pedidos.start(2000)
        self.actualizar_contador_pedidos()

    def crear_interfaz(self):
        principal = QWidget()
        self.setCentralWidget(principal)

        layout_principal = QHBoxLayout(principal)

        panel_productos = QWidget()
        layout_productos = QVBoxLayout(panel_productos)

        titulo = QLabel("LA ESQUINA MANAGER")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet(
            "font-size: 28px; font-weight: bold; padding: 12px;"
        )
        layout_productos.addWidget(titulo)

        sesion = QLabel(
            f"Sesión: {self.empleado_actual['nombre']} · "
            f"{self.empleado_actual['rol']}"
        )
        sesion.setAlignment(Qt.AlignCenter)
        sesion.setStyleSheet("font-weight:bold;color:#555;padding:3px;")
        layout_productos.addWidget(sesion)

        # Area desplazable: permite ver todos los productos incluso en
        # pantallas pequenas o cuando el menu crezca.
        scroll_productos = QScrollArea()
        scroll_productos.setWidgetResizable(True)
        scroll_productos.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )
        scroll_productos.setFrameShape(QScrollArea.NoFrame)

        contenido_productos = QWidget()
        grid = QGridLayout(contenido_productos)
        grid.setSpacing(8)
        grid.setContentsMargins(4, 4, 8, 4)

        fila = 0
        columna = 0

        for _id, nombre, precio, _categoria, _activo, _orden in self.productos:
            boton = QPushButton(f"{nombre}\n${precio:.0f}")
            boton.setMinimumSize(140, 62)
            boton.setMaximumHeight(72)
            boton.setStyleSheet("""
                QPushButton {
                    font-size: 14px;
                    font-weight: bold;
                    background-color: #f2c94c;
                    border: 1px solid #999;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #ffd95a;
                }
            """)

            boton.clicked.connect(
                lambda checked=False, n=nombre, p=precio:
                self.agregar_producto(n, p)
            )
            if self.empleado_actual["rol"] == "Cocina":
                boton.setEnabled(False)

            grid.addWidget(boton, fila, columna)
            columna += 1

            if columna == 4:
                columna = 0
                fila += 1

        for indice_columna in range(4):
            grid.setColumnStretch(indice_columna, 1)

        grid.setRowStretch(fila + 1, 1)
        scroll_productos.setWidget(contenido_productos)
        layout_productos.addWidget(scroll_productos)

        panel_pedido = QWidget()
        panel_pedido.setMinimumWidth(380)
        layout_pedido = QVBoxLayout(panel_pedido)

        titulo_pedido = QLabel("PEDIDO ACTUAL")
        titulo_pedido.setAlignment(Qt.AlignCenter)
        titulo_pedido.setStyleSheet(
            "font-size: 22px; font-weight: bold; padding: 10px;"
        )

        self.lista_pedido = QListWidget()
        self.lista_pedido.setStyleSheet("font-size: 16px;")

        self.label_total = QLabel("TOTAL: $0.00")
        self.label_total.setAlignment(Qt.AlignRight)
        self.label_total.setStyleSheet(
            "font-size: 26px; font-weight: bold; padding: 15px;"
        )

        boton_quitar = QPushButton("Quitar producto")
        boton_quitar.setMinimumHeight(45)
        boton_quitar.clicked.connect(self.quitar_producto)

        controles_cantidad = QWidget()
        layout_cantidad = QHBoxLayout(controles_cantidad)
        layout_cantidad.setContentsMargins(0, 0, 0, 0)
        boton_menos = QPushButton("− 1")
        boton_menos.setMinimumHeight(45)
        boton_menos.setStyleSheet("font-size:18px;font-weight:bold;")
        boton_menos.clicked.connect(self.quitar_producto)
        boton_mas = QPushButton("+ 1")
        boton_mas.setMinimumHeight(45)
        boton_mas.setStyleSheet("font-size:18px;font-weight:bold;")
        boton_mas.clicked.connect(self.aumentar_producto)
        layout_cantidad.addWidget(boton_menos)
        layout_cantidad.addWidget(boton_mas)

        self.boton_notas = QPushButton("Notas rápidas / Modificadores")
        self.boton_notas.setMinimumHeight(45)
        self.boton_notas.setStyleSheet(
            "font-weight:bold;background:#fff2cc;"
        )
        self.boton_notas.clicked.connect(self.agregar_nota_rapida)
        self.actualizar_boton_notas()

        boton_cancelar = QPushButton("Cancelar pedido")
        boton_cancelar.setMinimumHeight(45)
        boton_cancelar.clicked.connect(self.cancelar_pedido)

        boton_ventas = QPushButton("Ventas del día")
        boton_ventas.setMinimumHeight(45)
        boton_ventas.clicked.connect(self.mostrar_ventas_hoy)

        boton_historial = QPushButton("Historial / Reimprimir")
        boton_historial.setMinimumHeight(45)
        boton_historial.clicked.connect(self.abrir_historial)

        self.boton_pedidos = QPushButton("Pedidos de meseros")
        self.boton_pedidos.setMinimumHeight(50)
        self.boton_pedidos.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                background-color: #3498db;
                color: white;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        self.boton_pedidos.clicked.connect(self.abrir_pedidos_movil)
        if self.servidor_movil_url:
            self.boton_pedidos.setToolTip(
                f"Acceso para celulares: {self.servidor_movil_url}"
            )

        boton_mesas = QPushButton("Mesas y Barra")
        boton_mesas.setMinimumHeight(48)
        boton_mesas.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                background-color: #6fcf97;
                border-radius: 6px;
            }
        """)
        boton_mesas.clicked.connect(self.abrir_mesas)

        boton_cuentas = QPushButton("Cuentas activas")
        boton_cuentas.setMinimumHeight(46)
        boton_cuentas.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                background-color: #f6b93b;
                border-radius: 6px;
            }
        """)
        boton_cuentas.clicked.connect(self.abrir_cuentas_activas)

        boton_gastos = QPushButton("Gastos")
        boton_gastos.setMinimumHeight(45)
        boton_gastos.setStyleSheet("""
            QPushButton {
                font-size: 15px;
                font-weight: bold;
                background-color: #e7b45a;
                border-radius: 6px;
            }
        """)
        boton_gastos.clicked.connect(self.abrir_gastos)

        boton_corte = QPushButton("Corte de caja")
        boton_corte.setMinimumHeight(45)
        boton_corte.setStyleSheet("""
            QPushButton {
                font-size: 15px;
                font-weight: bold;
                background-color: #dddddd;
                border-radius: 6px;
            }
        """)
        boton_corte.clicked.connect(self.mostrar_corte_caja)

        boton_dashboard = QPushButton("Dashboard")
        boton_dashboard.setMinimumHeight(50)
        boton_dashboard.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                background-color: #333333;
                color: white;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #555555;
            }
        """)
        boton_dashboard.clicked.connect(self.abrir_dashboard)

        boton_productos = QPushButton("Productos")
        boton_productos.setMinimumHeight(45)
        boton_productos.setStyleSheet("""
            QPushButton {
                font-size: 15px;
                font-weight: bold;
                background-color: #f2c94c;
                border-radius: 6px;
            }
        """)
        boton_productos.clicked.connect(self.abrir_productos)

        boton_config = QPushButton("Configuración")
        boton_config.setMinimumHeight(45)
        boton_config.clicked.connect(self.abrir_configuracion)

        boton_empleados = QPushButton("Empleados / Usuarios")
        boton_empleados.setMinimumHeight(43)
        boton_empleados.setStyleSheet("font-weight:bold;background:#d9d2e9;")
        boton_empleados.clicked.connect(self.abrir_empleados)

        boton_cobrar = QPushButton("COBRAR")
        boton_cobrar.setFixedHeight(70)
        boton_cobrar.setStyleSheet("""
            QPushButton {
                font-size: 22px;
                font-weight: bold;
                background-color: #27ae60;
                color: white;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #219150;
            }
        """)
        boton_cobrar.clicked.connect(self.cobrar)

        boton_dividir = QPushButton("DIVIDIR CUENTA")
        boton_dividir.setFixedHeight(48)
        boton_dividir.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                background-color: #f6b93b;
                border-radius: 8px;
            }
        """)
        boton_dividir.clicked.connect(self.dividir_cuenta)

        boton_enviar_mesa = QPushButton("ENVIAR A MESA / COCINA")
        boton_enviar_mesa.setFixedHeight(58)
        boton_enviar_mesa.setStyleSheet("""
            QPushButton {
                font-size: 17px;
                font-weight: bold;
                background-color: #3498db;
                color: white;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        boton_enviar_mesa.clicked.connect(self.enviar_a_mesa_cocina)

        boton_imprimir_cuenta = QPushButton("IMPRIMIR CUENTA")
        boton_imprimir_cuenta.setFixedHeight(48)
        boton_imprimir_cuenta.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                background-color: #e6e6e6;
                border: 1px solid #999999;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #d5d5d5; }
        """)
        boton_imprimir_cuenta.clicked.connect(self.imprimir_cuenta_previa)

        rol = self.empleado_actual["rol"]
        es_admin = rol == "Administrador"
        es_caja = rol in ("Administrador", "Caja")
        boton_productos.setEnabled(es_admin)
        boton_config.setEnabled(es_admin)
        boton_empleados.setEnabled(es_admin)
        boton_gastos.setEnabled(es_admin)
        boton_dashboard.setEnabled(es_admin)
        boton_corte.setEnabled(es_caja)
        boton_historial.setEnabled(es_caja)
        boton_cobrar.setEnabled(es_caja)
        boton_dividir.setEnabled(es_caja)
        boton_enviar_mesa.setEnabled(rol in ("Administrador", "Caja", "Mesero"))
        boton_imprimir_cuenta.setEnabled(rol != "Cocina")
        boton_mesas.setEnabled(rol != "Cocina")
        boton_cuentas.setEnabled(rol != "Cocina")

        scroll_menu = QScrollArea()
        scroll_menu.setWidgetResizable(True)
        scroll_menu.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_menu.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_menu.setFrameShape(QScrollArea.NoFrame)

        contenido_menu = QWidget()
        layout_menu = QVBoxLayout(contenido_menu)
        layout_menu.setContentsMargins(0, 0, 6, 0)

        layout_menu.addWidget(controles_cantidad)
        layout_menu.addWidget(boton_quitar)
        layout_menu.addWidget(self.boton_notas)
        layout_menu.addWidget(boton_cancelar)
        layout_menu.addWidget(boton_ventas)
        layout_menu.addWidget(boton_historial)
        layout_menu.addWidget(self.boton_pedidos)
        layout_menu.addWidget(boton_mesas)
        layout_menu.addWidget(boton_cuentas)
        layout_menu.addWidget(boton_gastos)
        layout_menu.addWidget(boton_corte)
        layout_menu.addWidget(boton_dashboard)
        layout_menu.addWidget(boton_productos)
        layout_menu.addWidget(boton_config)
        layout_menu.addWidget(boton_empleados)

        # Conserva la altura natural de los botones para que el area use
        # desplazamiento vertical en lugar de comprimirlos.
        contenido_menu.setMinimumHeight(layout_menu.sizeHint().height())

        scroll_menu.setWidget(contenido_menu)

        layout_pedido.addWidget(titulo_pedido)
        layout_pedido.addWidget(self.lista_pedido)
        layout_pedido.addWidget(self.label_total)
        layout_pedido.addWidget(scroll_menu)
        layout_pedido.addWidget(boton_imprimir_cuenta)
        layout_pedido.addWidget(boton_dividir)
        layout_pedido.addWidget(boton_enviar_mesa)
        layout_pedido.addWidget(boton_cobrar)

        layout_principal.addWidget(panel_productos, 3)
        layout_principal.addWidget(panel_pedido, 1)
        self.actualizar_lista_pedido()
        self.actualizar_total()

    def agregar_producto(self, nombre, precio):
        clave = (nombre, precio)
        self.carrito.append((nombre, precio))
        self.total += precio
        self.actualizar_lista_pedido(clave)
        self.actualizar_total()

    def actualizar_lista_pedido(self, seleccionar=None):
        """Agrupa cantidades en pantalla sin cambiar el formato del carrito."""
        cantidades = {}
        orden = []
        for nombre, precio in self.carrito:
            clave = (nombre, precio)
            if clave not in cantidades:
                cantidades[clave] = 0
                orden.append(clave)
            cantidades[clave] += 1

        self.renglones_pedido = orden
        self.lista_pedido.clear()
        fila_seleccionada = -1
        for fila, clave in enumerate(orden):
            nombre, precio = clave
            cantidad = cantidades[clave]
            self.lista_pedido.addItem(
                f"{cantidad} × {nombre}  —  ${precio * cantidad:.2f}"
            )
            if clave == seleccionar:
                fila_seleccionada = fila
        if fila_seleccionada >= 0:
            self.lista_pedido.setCurrentRow(fila_seleccionada)

    def producto_seleccionado(self):
        fila = self.lista_pedido.currentRow()
        if fila < 0 or fila >= len(self.renglones_pedido):
            QMessageBox.information(
                self, "Selecciona un producto",
                "Selecciona primero un producto del pedido actual."
            )
            return None
        return self.renglones_pedido[fila]

    def aumentar_producto(self):
        clave = self.producto_seleccionado()
        if clave is None:
            return
        nombre, precio = clave
        self.carrito.append((nombre, precio))
        self.total += precio
        self.actualizar_lista_pedido(clave)
        self.actualizar_total()

    def quitar_producto(self):
        clave = self.producto_seleccionado()
        if clave is None:
            return
        if self.mesa_cuenta_actual:
            cantidad_actual = self.carrito.count(clave)
            cantidad_original = self.carrito_cuenta_original.count(clave)
            if cantidad_actual <= cantidad_original:
                QMessageBox.information(
                    self, "Producto ya enviado",
                    "Ese producto pertenece a una comanda anterior y no puede "
                    "quitarse desde esta pantalla."
                )
                return
        indice = self.carrito.index(clave)
        _, precio = self.carrito.pop(indice)
        self.total -= precio
        seleccionar = clave if clave in self.carrito else None
        self.actualizar_lista_pedido(seleccionar)
        self.actualizar_total()

    def agregar_nota_rapida(self):
        clave = self.producto_seleccionado()
        if clave is None:
            return
        nombre, _precio = clave
        opciones = (
            "Sin cebolla", "Sin crema", "Sin queso", "Sin salsa",
            "Salsa aparte", "Bien cocido", "Poco cocido", "Para llevar",
            "Otra indicación...",
        )
        opcion, ok = QInputDialog.getItem(
            self, "Nota rápida", f"Indicación para {nombre}:",
            opciones, 0, False,
        )
        if not ok:
            return
        if opcion == "Otra indicación...":
            opcion, ok = QInputDialog.getText(
                self, "Indicación especial", f"Nota para {nombre}:"
            )
            if not ok or not opcion.strip():
                return
        self.notas_rapidas.append(f"{nombre}: {opcion.strip()}")
        self.actualizar_boton_notas()

    def actualizar_boton_notas(self):
        if not hasattr(self, "boton_notas"):
            return
        cantidad = len(self.notas_rapidas)
        texto = "Notas rápidas / Modificadores"
        if cantidad:
            texto += f" ({cantidad})"
        self.boton_notas.setText(texto)
        self.boton_notas.setToolTip("\n".join(self.notas_rapidas))

    def cancelar_pedido(self):
        for pedido_id in self.pedidos_movil_actuales:
            try:
                actualizar_estado_pedido_movil(pedido_id, "Pendiente")
            except Exception:
                pass
        self.pedidos_movil_actuales = []
        self.mesa_cuenta_actual = None
        self.carrito_cuenta_original = []
        self.carrito_restante_division = []
        self.carrito.clear()
        self.notas_rapidas.clear()
        self.total = 0.0
        self.actualizar_lista_pedido()
        self.actualizar_boton_notas()
        self.actualizar_total()

    def actualizar_total(self):
        self.label_total.setText(
            f"TOTAL: ${self.total:.2f}"
        )

    def dividir_cuenta(self):
        if not self.carrito:
            QMessageBox.warning(self, "Cuenta vacía", "No hay productos para dividir.")
            return
        if not self.pedidos_movil_actuales or not self.mesa_cuenta_actual:
            QMessageBox.warning(
                self, "Cuenta sin mesa",
                "Primero carga una cuenta desde Cuentas activas o Mesas y Barra."
            )
            return
        if self.carrito_restante_division:
            QMessageBox.warning(self, "División activa", "Termina o cancela el cobro parcial actual.")
            return
        dialogo = DividirCuentaDialog(list(self.carrito), self)
        if dialogo.exec() != QDialog.Accepted or not dialogo.resultado:
            return
        cobrar, restante = dialogo.resultado
        self.carrito = cobrar
        self.carrito_restante_division = restante
        self.total = sum(precio for _nombre, precio in cobrar)
        self.actualizar_lista_pedido()
        self.actualizar_total()
        QMessageBox.information(
            self, "Cuenta dividida",
            f"Se cobrarán ahora {len(cobrar)} producto(s) por ${self.total:.2f}.\n"
            f"Quedarán {len(restante)} producto(s) abiertos en {self.mesa_cuenta_actual}."
        )

    def cobrar(self):
        if not self.carrito:
            QMessageBox.warning(
                self,
                "Pedido vacío",
                "Agrega al menos un producto."
            )
            return

        personas, ok = QInputDialog.getInt(
            self,
            "Personas",
            "¿Cuántas personas incluye esta venta?",
            value=1,
            minValue=1,
            maxValue=50,
            step=1,
        )

        if not ok:
            return

        origenes = [
            "Ya había venido",
            "Ya había visto el local",
            "Recomendación",
            "Facebook",
            "Instagram",
            "TikTok",
            "Google Maps",
            "UAA / Alberca",
            "Pasaba por aquí",
            "Otro",
        ]

        origen, ok = QInputDialog.getItem(
            self,
            "Origen del cliente",
            "¿Cómo conocieron o llegaron a La Esquina?",
            origenes,
            0,
            False,
        )

        if not ok:
            return

        dialogo_pago = PagoDialog(self.total, self)
        if dialogo_pago.exec() != QDialog.Accepted or not dialogo_pago.resultado:
            return
        pago = dialogo_pago.resultado
        metodo = pago["metodo_db"]
        metodo_ticket = pago["descripcion"]
        recibido = pago["recibido"]
        cambio = pago["cambio"]

        total_venta = self.total
        productos_ticket = list(self.carrito)

        venta_id = guardar_venta(
            self.carrito,
            total_venta,
            metodo,
            personas,
            origen,
            self.empleado_actual["id"],
            pago["pagos"],
        )
        registrar_auditoria(
            self.empleado_actual, "Cobrar", "Venta", venta_id,
            f"${total_venta:.2f} - {metodo_ticket}",
        )

        if self.carrito_restante_division:
            crear_saldo_cuenta(
                self.mesa_cuenta_actual,
                self.empleado_actual,
                self.carrito_restante_division,
            )

        if self.pedidos_movil_actuales:
            for pedido_id in self.pedidos_movil_actuales:
                actualizar_estado_pedido_movil(
                    pedido_id, "Cobrado", venta_id
                )
            self.pedidos_movil_actuales = []

        # Generar ticket PDF automáticamente
        try:
            ruta_ticket = generar_ticket_pdf(
                venta_id=venta_id,
                productos=productos_ticket,
                total=total_venta,
                metodo=metodo_ticket,
                personas=personas,
                origen=origen,
                recibido=recibido,
                cambio=cambio,
            )
        except Exception as error:
            ruta_ticket = None
            QMessageBox.warning(
                self,
                "Ticket",
                f"La venta se guardó, pero no se pudo generar el ticket.\n\n{error}"
            )

        if recibido is not None:
            mensaje = (
                f"Venta #{venta_id}\n\n"
                f"Personas: {personas}\n"
                f"Origen: {origen}\n"
                f"Total: ${total_venta:.2f}\n"
                f"Método: {metodo_ticket}\n"
                f"Efectivo recibido: ${recibido:.2f}\n"
                f"CAMBIO: ${cambio:.2f}\n\n"
                "Venta guardada correctamente."
            )
        else:
            mensaje = (
                f"Venta #{venta_id}\n\n"
                f"Personas: {personas}\n"
                f"Origen: {origen}\n"
                f"Total: ${total_venta:.2f}\n"
                f"Método: {metodo_ticket}\n\n"
                "Venta guardada correctamente."
            )

        QMessageBox.information(
            self,
            "Venta registrada",
            mensaje,
        )

        if ruta_ticket is not None:
            respuesta = QMessageBox.question(
                self,
                "Imprimir ticket",
                "¿Deseas imprimir el ticket?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )

            if respuesta == QMessageBox.Yes:
                try:
                    imprimir_ticket(ruta_ticket)
                except Exception as error:
                    QMessageBox.warning(
                        self,
                        "Impresión",
                        "No se pudo enviar el ticket a la impresora.\n\n"
                        f"{error}\n\n"
                        f"El PDF quedó guardado en:\n{ruta_ticket}"
                    )

        self.cancelar_pedido()

    def imprimir_cuenta_previa(self):
        if not self.carrito:
            QMessageBox.warning(
                self, "Pedido vacío",
                "Agrega al menos un producto antes de imprimir la cuenta."
            )
            return
        try:
            imprimir_cuenta(
                list(self.carrito), self.total, self.mesa_cuenta_actual
            )
        except Exception as error:
            QMessageBox.warning(
                self, "No se pudo imprimir",
                f"No se pudo imprimir la cuenta provisional.\n\n{error}"
            )
            return
        QMessageBox.information(
            self, "Cuenta impresa",
            "La cuenta provisional se envió a la impresora."
        )

    def enviar_a_mesa_cocina(self):
        if not self.carrito:
            QMessageBox.warning(
                self, "Pedido vacío",
                "Agrega al menos un producto antes de enviarlo."
            )
            return
        agregando_a_cuenta = bool(
            self.pedidos_movil_actuales and self.mesa_cuenta_actual
        )
        productos_a_enviar = list(self.carrito)
        if agregando_a_cuenta:
            productos_originales_pendientes = list(
                self.carrito_cuenta_original
            )
            productos_a_enviar = []
            for producto in self.carrito:
                if producto in productos_originales_pendientes:
                    productos_originales_pendientes.remove(producto)
                else:
                    productos_a_enviar.append(producto)
            if productos_originales_pendientes:
                QMessageBox.warning(
                    self, "Productos ya enviados",
                    "No se pueden quitar productos de una comanda anterior desde "
                    "esta pantalla. Restablece las cantidades originales o cancela "
                    "la carga de la cuenta."
                )
                return
            if not productos_a_enviar:
                QMessageBox.information(
                    self, "Sin productos nuevos",
                    "Agrega al menos un producto nuevo antes de reenviar a cocina."
                )
                return
        elif self.pedidos_movil_actuales:
            QMessageBox.warning(
                self, "Pedido ya asignado",
                "Este pedido ya pertenece a una mesa. Puedes cobrarlo o cancelar "
                "la carga para devolverlo a Cuentas activas."
            )
            return

        if agregando_a_cuenta:
            mesa = self.mesa_cuenta_actual
        else:
            zonas = [f"Mesa {numero}" for numero in range(1, 21)] + ["Barra"]
            mesa, ok = QInputDialog.getItem(
                self, "Enviar pedido", "Selecciona la mesa o Barra:",
                zonas, 0, False,
            )
            if not ok:
                return
        mesero, ok = QInputDialog.getText(
            self, "Mesero", "Nombre del mesero:", text="Caja"
        )
        if not ok or not mesero.strip():
            return
        notas_iniciales = "\n".join(self.notas_rapidas)
        notas, ok = QInputDialog.getMultiLineText(
            self, "Notas para cocina",
            "Indicaciones especiales (puedes dejarlo vacío):", notas_iniciales
        )
        if not ok:
            return

        try:
            pedido_id, total = crear_pedido_desde_pc(
                mesa, mesero.strip(), productos_a_enviar, notas.strip(),
                self.empleado_actual["id"],
            )
            registrar_auditoria(
                self.empleado_actual, "Enviar", "Pedido", pedido_id,
                f"{mesa} - ${total:.2f}",
            )
        except Exception as error:
            QMessageBox.critical(
                self, "No se pudo enviar el pedido", str(error)
            )
            return

        if agregando_a_cuenta:
            for pedido_anterior_id in self.pedidos_movil_actuales:
                actualizar_estado_pedido_movil(
                    pedido_anterior_id, "Pendiente"
                )

        self.pedidos_movil_actuales = []
        self.mesa_cuenta_actual = None
        self.carrito_cuenta_original = []
        self.carrito.clear()
        self.notas_rapidas.clear()
        self.total = 0.0
        self.actualizar_lista_pedido()
        self.actualizar_boton_notas()
        self.actualizar_total()
        self.actualizar_contador_pedidos()
        if agregando_a_cuenta:
            mensaje = (
                f"Los productos nuevos se agregaron a {mesa}.\n"
                f"Comanda #{pedido_id} enviada a cocina por ${total:.2f}."
            )
        else:
            mensaje = (
                f"Pedido #{pedido_id} enviado a {mesa} y a cocina.\n"
                f"Total acumulado de esta comanda: ${total:.2f}"
            )
        QMessageBox.information(self, "Pedido enviado", mensaje)

    def mostrar_ventas_hoy(self):
        ventas = obtener_ventas_hoy()

        if not ventas:
            QMessageBox.information(
                self,
                "Ventas del día",
                "Todavía no hay ventas registradas hoy.",
            )
            return

        total_dia = sum(
            venta[2] for venta in ventas
        )

        numero_ventas = len(ventas)

        total_personas = sum(
            (venta[4] or 1) for venta in ventas
        )

        ticket_promedio = (
            total_dia / numero_ventas
        )

        consumo_por_persona = (
            total_dia / total_personas
            if total_personas
            else 0
        )

        texto = (
            f"VENTAS DEL DÍA\n\n"
            f"Tickets: {numero_ventas}\n"
            f"Personas: {total_personas}\n"
            f"Venta total: ${total_dia:.2f}\n"
            f"Ticket promedio por ticket: ${ticket_promedio:.2f}\n"
            f"Venta promedio por persona: ${consumo_por_persona:.2f}\n\n"
            f"ORIGEN DE CLIENTES\n"
        )

        for origen, personas in obtener_resumen_origen_hoy():
            texto += f"• {origen}: {personas}\n"

        texto += "\nÚLTIMAS VENTAS\n"

        for venta in ventas[:10]:
            venta_id, fecha, total, metodo, personas, origen = venta
            hora = fecha[11:16]

            texto += (
                f"#{venta_id}  {hora}  ${total:.2f}  "
                f"{metodo}  {personas} pers.  {origen}\n"
            )

        QMessageBox.information(
            self,
            "Ventas del día",
            texto,
        )

    def abrir_historial(self):
        dialogo = HistorialDialog(self)
        dialogo.exec()

    def actualizar_contador_pedidos(self):
        if not hasattr(self, "boton_pedidos"):
            return
        try:
            pendientes = contar_pedidos_pendientes()
            texto = "Pedidos de meseros"
            if pendientes:
                texto += f" ({pendientes} pendiente{'s' if pendientes != 1 else ''})"
            self.boton_pedidos.setText(texto)
        except Exception:
            self.boton_pedidos.setText("Pedidos de meseros")

    def abrir_pedidos_movil(self):
        if self.servidor_movil_error:
            QMessageBox.warning(
                self, "Conexion para meseros",
                "No se pudo iniciar la conexion local.\n\n"
                f"{self.servidor_movil_error}"
            )
        dialogo = PedidosMovilDialog(self)
        if dialogo.exec() != QDialog.Accepted or not dialogo.pedido_cargado:
            self.actualizar_contador_pedidos()
            return
        pedido_id, detalles = dialogo.pedido_cargado
        if self.carrito:
            respuesta = QMessageBox.question(
                self, "Reemplazar pedido actual",
                "Ya hay productos en la caja. ¿Deseas reemplazarlos con el pedido de la mesa?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if respuesta != QMessageBox.Yes:
                actualizar_estado_pedido_movil(pedido_id, "Pendiente")
                return
        self.carrito.clear()
        self.notas_rapidas.clear()
        self.total = 0.0
        for _producto_id, producto, cantidad, precio in detalles:
            for _ in range(cantidad):
                self.carrito.append((producto, precio))
                self.total += precio
        self.actualizar_lista_pedido()
        self.actualizar_boton_notas()
        self.pedidos_movil_actuales = [pedido_id]
        self.mesa_cuenta_actual = None
        self.carrito_cuenta_original = []
        self.actualizar_total()
        self.actualizar_contador_pedidos()
        QMessageBox.information(
            self, "Pedido cargado",
            f"El pedido #{pedido_id} ya está en caja. Revísalo y cobra normalmente."
        )

    def abrir_mesas(self):
        dialogo = MesasDialog(self)
        if dialogo.exec() != QDialog.Accepted or not dialogo.carga_mesa:
            return
        mesa, pedido_ids, detalles = dialogo.carga_mesa
        if self.carrito:
            respuesta = QMessageBox.question(
                self, "Reemplazar pedido actual",
                "Ya hay productos en la caja. ¿Deseas reemplazarlos con la cuenta de la mesa?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if respuesta != QMessageBox.Yes:
                for pedido_id in pedido_ids:
                    actualizar_estado_pedido_movil(pedido_id, "Pendiente")
                return
        self.carrito.clear()
        self.notas_rapidas.clear()
        self.total = 0.0
        for _producto_id, producto, cantidad, precio in detalles:
            for _ in range(cantidad):
                self.carrito.append((producto, precio))
                self.total += precio
        self.actualizar_lista_pedido()
        self.actualizar_boton_notas()
        self.pedidos_movil_actuales = pedido_ids
        self.mesa_cuenta_actual = None
        self.carrito_cuenta_original = []
        self.actualizar_total()
        QMessageBox.information(
            self, "Cuenta cargada",
            f"La cuenta completa de {mesa} está en caja. Revísala y cobra normalmente."
        )

    def abrir_cuentas_activas(self):
        dialogo = CuentasActivasDialog(self)
        if dialogo.exec() != QDialog.Accepted or not dialogo.cuenta_cargada:
            return
        mesa, pedido_ids, detalles = dialogo.cuenta_cargada
        if self.carrito:
            respuesta = QMessageBox.question(
                self, "Reemplazar pedido actual",
                "Ya hay productos en la caja. ¿Deseas reemplazarlos con la cuenta activa?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if respuesta != QMessageBox.Yes:
                for pedido_id in pedido_ids:
                    actualizar_estado_pedido_movil(pedido_id, "Pendiente")
                return
        self.carrito.clear()
        self.notas_rapidas.clear()
        self.total = 0.0
        for _producto_id, producto, cantidad, precio in detalles:
            for _ in range(cantidad):
                self.carrito.append((producto, precio))
                self.total += precio
        self.actualizar_lista_pedido()
        self.actualizar_boton_notas()
        self.pedidos_movil_actuales = pedido_ids
        self.mesa_cuenta_actual = mesa
        self.carrito_cuenta_original = list(self.carrito)
        self.actualizar_total()
        QMessageBox.information(
            self, "Cuenta cargada",
            f"La cuenta activa de {mesa} está en caja. Puedes cobrarla o agregar "
            "productos nuevos y presionar ENVIAR A MESA / COCINA."
        )

    def mostrar_corte_caja(self):
        corte = obtener_corte_caja_hoy()

        texto = (
            "CORTE DE CAJA - HOY\n\n"
            f"Venta total: ${corte['venta_total']:.2f}\n"
            f"Tickets: {corte['tickets']}\n"
            f"Personas: {corte['personas']}\n"
            f"Ticket promedio: ${corte['ticket_promedio']:.2f}\n\n"
            "MÉTODOS DE PAGO\n"
            f"Efectivo: ${corte['efectivo']:.2f}\n"
            f"Tarjeta: ${corte['tarjeta']:.2f}\n"
            f"Transferencia: ${corte['transferencia']:.2f}\n\n"
            "GASTOS DEL DIA\n"
            f"Gastos activos: ${corte['gastos']:.2f}\n"
            f"Pagados en efectivo: ${corte['gastos_efectivo']:.2f}\n"
            f"Pagados con tarjeta: ${corte['gastos_tarjeta']:.2f}\n"
            f"Pagados por transferencia: ${corte['gastos_transferencia']:.2f}\n\n"
            "RESULTADO DEL DIA\n"
            f"Ventas menos gastos: ${corte['resultado_dia']:.2f}\n\n"
            "FLUJO DE EFECTIVO\n"
            f"Ventas en efectivo menos gastos en efectivo: "
            f"${corte['flujo_efectivo_neto']:.2f}\n\n"
            "Nota: resultado y flujo de efectivo son datos distintos.\n\n"
            "DESGLOSE\n"
        )

        for metodo, datos in corte["metodos"].items():
            if datos["tickets"] > 0:
                texto += (
                    f"• {metodo}: {datos['tickets']} ticket(s) "
                    f"- ${datos['total']:.2f}\n"
                )

        QMessageBox.information(
            self,
            "Corte de caja",
            texto
        )

    def abrir_gastos(self):
        dialogo = GastosDialog(self)
        dialogo.exec()

    def cargar_productos(self):
        self.productos = obtener_productos(solo_activos=True)

    def abrir_productos(self):
        dialogo = ProductosDialog(self)
        dialogo.exec()

        # Actualiza los botones del POS al cerrar el administrador.
        self.cargar_productos()
        self.crear_interfaz()

    def abrir_dashboard(self):
        dialogo = DashboardDialog(self)
        dialogo.exec()

    def abrir_configuracion(self):
        dialogo = ConfiguracionDialog(self)
        dialogo.exec()

    def abrir_empleados(self):
        if self.empleado_actual["rol"] != "Administrador":
            QMessageBox.warning(
                self, "Sin permiso",
                "Solo un Administrador puede gestionar empleados."
            )
            return
        dialogo = EmpleadosDialog(self.empleado_actual, self)
        dialogo.exec()
