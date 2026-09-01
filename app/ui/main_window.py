from datetime import datetime
import shutil
import io
from pathlib import Path
import qrcode

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
    QMenu,
    QFileDialog,
    QToolButton,
    QSizePolicy,
    QDateEdit,
    QTabWidget,
    QColorDialog,
)
from PySide6.QtCore import Qt, QDate, QDateTime, QTimer, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QFont

from app.database.database import (
    guardar_venta,
    obtener_ventas_hoy,
    obtener_resumen_origen_hoy,
    obtener_resumen_hoy,
    obtener_analisis_ventas,
    obtener_resumen_semana_actual,
    obtener_comparacion_semanal,
    obtener_top_productos_hoy,
    obtener_ventas_por_dia_semana_actual,
    obtener_comparativo_ventas_diarias,
    obtener_mezcla_clientes_hoy,
    obtener_productos,
    agregar_producto,
    actualizar_producto,
    obtener_imagenes_productos,
    actualizar_imagen_producto,
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
    obtener_cuentas_pedidos,
    obtener_comensales_mesa,
    registrar_pago_comensal,
    obtener_estado_pedido_movil,
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
    registrar_cliente,
    obtener_clientes,
    establecer_cliente_activo,
    guardar_ingrediente, obtener_ingredientes, establecer_ingrediente_activo,
    guardar_componente_receta, eliminar_componente_receta,
    guardar_costo_extra_receta, obtener_receta, obtener_costos_productos,
    guardar_preparacion, obtener_preparaciones, establecer_preparacion_activa,
    guardar_ingrediente_preparacion, eliminar_ingrediente_preparacion,
    obtener_preparacion, guardar_preparacion_receta,
    eliminar_preparacion_receta,
)
from app.settings import cargar_configuracion, guardar_configuracion
from app.tickets import generar_ticket_pdf, imprimir_ticket, imprimir_cuenta
from app.mobile_server import start_mobile_server, mobile_url, club_url
from app.paths import APPLICATION_FOLDER


PRODUCT_IMAGES_FOLDER = APPLICATION_FOLDER / "product_images"


def preparar_pagina_maximizada(dialogo):
    """Aplica el comportamiento común de las pantallas completas."""
    dialogo.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
    desplazables = (
        dialogo.findChildren(QScrollArea)
        + dialogo.findChildren(QTableWidget)
        + dialogo.findChildren(QListWidget)
        + dialogo.findChildren(QTextEdit)
    )
    if not desplazables and dialogo.layout() and not dialogo.property("paginaConScroll"):
        layout_original = dialogo.layout()
        contenido = QWidget()
        layout_contenido = QVBoxLayout(contenido)
        layout_contenido.setContentsMargins(4, 4, 8, 4)
        while layout_original.count():
            item = layout_original.takeAt(0)
            if item.widget():
                widget = item.widget()
                widget.setParent(contenido)
                layout_contenido.addWidget(widget)
            elif item.layout():
                layout_contenido.addLayout(item.layout())
            else:
                layout_contenido.addItem(item)
        layout_contenido.addStretch()
        scroll_pagina = QScrollArea()
        scroll_pagina.setObjectName("scrollPaginaCompleta")
        scroll_pagina.setWidgetResizable(True)
        scroll_pagina.setFrameShape(QScrollArea.NoFrame)
        scroll_pagina.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_pagina.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_pagina.setWidget(contenido)
        layout_original.addWidget(scroll_pagina)
        dialogo.setProperty("paginaConScroll", True)
    for tabla in dialogo.findChildren(QTableWidget):
        tabla.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        tabla.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    for lista in dialogo.findChildren(QListWidget):
        lista.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        lista.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    for visor in dialogo.findChildren(QTextEdit):
        visor.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        visor.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    for scroll in dialogo.findChildren(QScrollArea):
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    dialogo.setWindowState(dialogo.windowState() | Qt.WindowMaximized)


class PantallaDialog(QDialog):
    """Base para páginas del sistema; los avisos breves no la utilizan."""
    def exec(self):
        preparar_pagina_maximizada(self)
        return super().exec()


class PagoDialog(PantallaDialog):
    def __init__(self, total, parent=None):
        super().__init__(parent)
        self.total = float(total)
        self.resultado = None
        self.setWindowTitle("Forma de pago")
        self.resize(520, 480)
        principal = QVBoxLayout(self)
        principal.setContentsMargins(22, 20, 22, 20)
        principal.setSpacing(12)
        self.setStyleSheet("""
            QDialog { background-color:#f2f3ef; }
            QLabel#tituloPago { color:#6f746c;font-size:12px;font-weight:800; }
            QLabel#totalPago {
                color:white;background:#292d28;border-radius:11px;
                padding:16px;font-size:30px;font-weight:800;
            }
            QLabel#ayudaPago {
                color:#545a51;background:#fff5ce;border:1px solid #ead585;
                border-radius:8px;padding:9px 11px;
            }
            QLabel#cambioPago {
                color:#17683b;background:#e2f5e9;border:1px solid #a9dbba;
                border-radius:8px;padding:11px;font-size:18px;font-weight:800;
            }
            QComboBox, QDoubleSpinBox {
                min-height:38px;background:white;border:1px solid #cfd3cb;
                border-radius:7px;padding:3px 8px;font-size:15px;
            }
            QComboBox:focus, QDoubleSpinBox:focus { border:2px solid #e3b82d; }
            QPushButton { min-height:42px;border-radius:8px;font-weight:700; }
        """)
        titulo = QLabel("FORMA DE PAGO")
        titulo.setObjectName("tituloPago")
        titulo.setAlignment(Qt.AlignCenter)
        principal.addWidget(titulo)

        total_destacado = QLabel(f"TOTAL  ${self.total:.2f}")
        total_destacado.setObjectName("totalPago")
        total_destacado.setAlignment(Qt.AlignCenter)
        principal.addWidget(total_destacado)

        formulario = QFormLayout()
        formulario.setVerticalSpacing(10)
        formulario.setHorizontalSpacing(14)
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
        self.ayuda.setObjectName("ayudaPago")
        self.ayuda.setWordWrap(True)
        principal.addWidget(self.ayuda)
        self.label_cambio = QLabel("CAMBIO  $0.00")
        self.label_cambio.setObjectName("cambioPago")
        self.label_cambio.setAlignment(Qt.AlignCenter)
        principal.addWidget(self.label_cambio)
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.validar)
        botones.rejected.connect(self.reject)
        boton_aceptar = botones.button(QDialogButtonBox.Ok)
        boton_aceptar.setText("CONFIRMAR PAGO")
        boton_aceptar.setStyleSheet(
            "background:#27ae60;color:white;border:none;padding:6px 18px;"
        )
        boton_cancelar = botones.button(QDialogButtonBox.Cancel)
        boton_cancelar.setText("Cancelar")
        boton_cancelar.setStyleSheet(
            "background:#f4f5f2;border:1px solid #cfd3cb;padding:6px 18px;"
        )
        principal.addWidget(botones)
        self.metodo.currentTextChanged.connect(self.actualizar)
        self.efectivo.valueChanged.connect(self.ajustar_tarjeta)
        self.recibido.valueChanged.connect(self.actualizar_cambio)
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
            "En pago mixto, escribe la parte en efectivo. La parte con tarjeta "
            "se calcula automáticamente para completar el total."
        )
        self.actualizar_cambio()

    def ajustar_tarjeta(self):
        if self.metodo.currentText() == "Efectivo + Tarjeta":
            efectivo = min(self.efectivo.value(), self.total)
            self.tarjeta.blockSignals(True)
            self.tarjeta.setValue(round(self.total - efectivo, 2))
            self.tarjeta.blockSignals(False)
            if self.recibido.value() < efectivo:
                self.recibido.setValue(efectivo)
        self.actualizar_cambio()

    def actualizar_cambio(self):
        metodo = self.metodo.currentText()
        efectivo_cobrado = (
            self.total if metodo == "Efectivo"
            else self.efectivo.value() if metodo == "Efectivo + Tarjeta"
            else 0
        )
        if efectivo_cobrado:
            cambio = max(0.0, self.recibido.value() - efectivo_cobrado)
            self.label_cambio.setText(f"CAMBIO  ${cambio:.2f}")
            self.label_cambio.show()
        else:
            self.label_cambio.hide()

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


class DividirCuentaDialog(PantallaDialog):
    def __init__(self, productos, parent=None, mesa=None):
        super().__init__(parent)
        self.mesa = mesa
        self.productos = list(productos)
        self.setWindowTitle("Dividir cuenta por productos")
        self.resize(1120, 700)
        self.resultado = None
        principal = QVBoxLayout(self)
        principal.setContentsMargins(20, 18, 20, 18)
        principal.setSpacing(10)
        self.setStyleSheet("""
            QDialog { background-color:#f2f3ef; }
            QLabel#tituloDivision { color:#242722;font-size:23px;font-weight:800; }
            QLabel#instruccionDivision { color:#6f746c;font-size:13px; }
            QLabel#resumenCobro {
                color:white;background:#292d28;border-radius:9px;
                padding:11px 14px;font-size:15px;font-weight:800;
            }
            QLabel#notaDivision {
                color:#545a51;background:#fff5ce;border:1px solid #ead585;
                border-radius:8px;padding:9px 11px;
            }
            QTableWidget {
                background:white;border:1px solid #dfe2dc;border-radius:8px;
                gridline-color:#e7e9e4;alternate-background-color:#f8f9f6;
            }
            QHeaderView::section {
                background:#292d28;color:white;border:none;padding:8px;
                font-weight:700;
            }
            QScrollArea#scrollMesas { background:transparent;border:none; }
            QScrollBar:vertical {
                background:#e4e7e0;width:14px;margin:2px;border-radius:7px;
            }
            QScrollBar::handle:vertical {
                background:#9da39a;min-height:32px;border-radius:6px;
            }
            QScrollBar::handle:vertical:hover { background:#777e74; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height:0;border:none;background:none;
            }
            QSpinBox {
                min-height:34px;background:white;border:1px solid #cfd3cb;
                border-radius:6px;padding:2px 7px;font-size:15px;font-weight:700;
            }
            QPushButton { min-height:42px;border-radius:8px;font-weight:700; }
        """)
        titulo = QLabel("DIVIDIR CUENTA")
        titulo.setObjectName("tituloDivision")
        principal.addWidget(titulo)
        instruccion = QLabel(
            "Elige de 2 a 8 personas y distribuye las unidades de cada producto."
        )
        instruccion.setObjectName("instruccionDivision")
        principal.addWidget(instruccion)

        controles = QHBoxLayout()
        controles.addWidget(QLabel("Número de cuentas / personas:"))
        self.numero_cuentas = QSpinBox()
        self.numero_cuentas.setRange(2, 8)
        self.numero_cuentas.setValue(2)
        controles.addWidget(self.numero_cuentas)
        repartir = QPushButton("REPARTIR AUTOMÁTICAMENTE")
        repartir.setStyleSheet(
            "background:#e6e6e6;border:1px solid #aeb3aa;padding:6px 14px;"
        )
        repartir.clicked.connect(self.repartir_automaticamente)
        controles.addWidget(repartir)
        controles.addStretch()
        principal.addLayout(controles)

        agrupados = {}
        for nombre, precio in self.productos:
            clave = (nombre, float(precio))
            agrupados[clave] = agrupados.get(clave, 0) + 1
        self.productos_agrupados = list(agrupados.items())
        self.filas = []
        self.tabla = QTableWidget()
        self.tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.verticalHeader().setDefaultSectionSize(44)
        principal.addWidget(self.tabla)
        self.resumen = QLabel()
        self.resumen.setObjectName("resumenCobro")
        self.resumen.setWordWrap(True)
        principal.addWidget(self.resumen)
        nota = QLabel(
            "La suma distribuida de cada producto debe coincidir con su cantidad total. "
            "Puedes imprimir cada cuenta o todas antes de cobrar. "
            "Imprimir no registra ninguna venta ni modifica la mesa."
        )
        nota.setObjectName("notaDivision")
        nota.setWordWrap(True)
        principal.addWidget(nota)
        fila_impresion = QHBoxLayout()
        self.cuenta_a_imprimir = QComboBox()
        fila_impresion.addWidget(self.cuenta_a_imprimir)
        self.boton_imprimir_una = QPushButton("IMPRIMIR CUENTA SELECCIONADA")
        self.boton_imprimir_todas = QPushButton("IMPRIMIR TODAS")
        for boton in (self.boton_imprimir_una, self.boton_imprimir_todas):
            boton.setStyleSheet(
                "background:#f6b93b;color:#242722;border:none;padding:6px 12px;"
            )
            fila_impresion.addWidget(boton)
        self.boton_imprimir_una.clicked.connect(self.imprimir_seleccionada)
        self.boton_imprimir_todas.clicked.connect(self.imprimir_todas)
        principal.addLayout(fila_impresion)

        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.validar)
        botones.rejected.connect(self.reject)
        confirmar = botones.button(QDialogButtonBox.Ok)
        confirmar.setText("CONTINUAR AL COBRO")
        confirmar.setStyleSheet(
            "background:#27ae60;color:white;border:none;padding:6px 18px;"
        )
        cancelar = botones.button(QDialogButtonBox.Cancel)
        cancelar.setText("Cancelar")
        cancelar.setStyleSheet(
            "background:#f4f5f2;border:1px solid #cfd3cb;padding:6px 18px;"
        )
        principal.addWidget(botones)
        self.numero_cuentas.valueChanged.connect(self.construir_tabla)
        self.construir_tabla()

    def construir_tabla(self):
        cantidad_cuentas = self.numero_cuentas.value()
        self.tabla.clear()
        self.tabla.setRowCount(len(self.productos_agrupados))
        self.tabla.setColumnCount(3 + cantidad_cuentas)
        self.tabla.setHorizontalHeaderLabels(
            ["Producto", "Precio", "Total"]
            + [f"Cuenta {numero}" for numero in range(1, cantidad_cuentas + 1)]
        )
        self.tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for columna in range(1, 3 + cantidad_cuentas):
            self.tabla.horizontalHeader().setSectionResizeMode(
                columna, QHeaderView.ResizeToContents
            )
        self.filas = []
        for fila, ((nombre, precio), cantidad) in enumerate(self.productos_agrupados):
            self.tabla.setItem(fila, 0, QTableWidgetItem(nombre))
            self.tabla.setItem(fila, 1, QTableWidgetItem(f"${precio:.2f}"))
            self.tabla.setItem(fila, 2, QTableWidgetItem(str(cantidad)))
            selectores = []
            for indice in range(cantidad_cuentas):
                selector = QSpinBox()
                selector.setRange(0, cantidad)
                selector.valueChanged.connect(self.actualizar_resumen)
                self.tabla.setCellWidget(fila, 3 + indice, selector)
                selectores.append(selector)
            self.filas.append((nombre, precio, cantidad, selectores))
        self.cuenta_a_imprimir.clear()
        self.cuenta_a_imprimir.addItems([
            f"Cuenta {numero}" for numero in range(1, cantidad_cuentas + 1)
        ])
        self.repartir_automaticamente()

    def repartir_automaticamente(self):
        cantidad_cuentas = self.numero_cuentas.value()
        siguiente = 0
        for _nombre, _precio, cantidad, selectores in self.filas:
            valores = [0] * cantidad_cuentas
            for _unidad in range(cantidad):
                valores[siguiente % cantidad_cuentas] += 1
                siguiente += 1
            for selector, valor in zip(selectores, valores):
                selector.blockSignals(True)
                selector.setValue(valor)
                selector.blockSignals(False)
        self.actualizar_resumen()

    def actualizar_resumen(self):
        cuentas = self.separar_productos()
        textos = []
        for numero, productos in enumerate(cuentas, start=1):
            total = sum(precio for _nombre, precio in productos)
            textos.append(f"CUENTA {numero}: {len(productos)} art.  ${total:.2f}")
        self.resumen.setText("     |     ".join(textos))

    def separar_productos(self):
        cuentas = [[] for _ in range(self.numero_cuentas.value())]
        for nombre, precio, _cantidad, selectores in self.filas:
            for indice, selector in enumerate(selectores):
                cuentas[indice].extend([(nombre, precio)] * selector.value())
        return cuentas

    def separacion_valida(self):
        for nombre, _precio, cantidad, selectores in self.filas:
            asignadas = sum(selector.value() for selector in selectores)
            if asignadas != cantidad:
                QMessageBox.warning(
                    self, "División incompleta",
                    f"{nombre}: hay {cantidad} unidad(es), pero distribuiste {asignadas}."
                )
                return None
        cuentas = self.separar_productos()
        vacias = [str(i + 1) for i, cuenta in enumerate(cuentas) if not cuenta]
        if vacias:
            QMessageBox.warning(
                self, "Cuenta vacía",
                "Las siguientes cuentas no tienen productos: " + ", ".join(vacias)
                + ". Reduce el número de personas o asigna productos."
            )
            return None
        return cuentas

    def imprimir_seleccionada(self):
        separacion = self.separacion_valida()
        if not separacion:
            return
        numero = self.cuenta_a_imprimir.currentIndex() + 1
        productos = separacion[numero - 1]
        total = sum(precio for _nombre, precio in productos)
        referencia = f"{self.mesa or 'Cuenta'} - CUENTA {numero}"
        try:
            imprimir_cuenta(productos, total, referencia)
        except Exception as error:
            QMessageBox.warning(
                self, "No se pudo imprimir",
                f"No se pudo imprimir la Cuenta {numero}.\n\n{error}"
            )
            return
        QMessageBox.information(
            self, "Cuenta impresa",
            f"La Cuenta {numero} provisional se envió a la impresora."
        )

    def imprimir_todas(self):
        separacion = self.separacion_valida()
        if not separacion:
            return
        for numero, productos in enumerate(separacion, start=1):
            total = sum(precio for _nombre, precio in productos)
            referencia = f"{self.mesa or 'Cuenta'} - CUENTA {numero}"
            try:
                imprimir_cuenta(productos, total, referencia)
            except Exception as error:
                QMessageBox.warning(
                    self, "Impresión incompleta",
                    f"No se pudo imprimir la Cuenta {numero}.\n\n{error}"
                )
                return
        QMessageBox.information(
            self, "Cuentas impresas",
            f"Las {len(separacion)} cuentas provisionales se enviaron a la impresora."
        )

    def validar(self):
        separacion = self.separacion_valida()
        if not separacion:
            return
        self.resultado = separacion
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


class EmpleadosDialog(PantallaDialog):
    def __init__(self, empleado_actual, parent=None):
        super().__init__(parent)
        self.empleado_actual = empleado_actual
        self.setWindowTitle("Empleados y permisos")
        self.resize(920, 620)
        principal = QVBoxLayout(self)
        principal.setContentsMargins(24, 22, 24, 20)
        principal.setSpacing(12)
        self.setStyleSheet("""
            QDialog { background:#f2f3ef; }
            QLabel#seccionEmpleados { color:#777c73;font-size:11px;font-weight:800; }
            QLabel#tituloEmpleados { color:#292d28;font-size:25px;font-weight:800; }
            QLabel#resumenEmpleados { color:#4f554d;background:#fff9df;border:1px solid #ead585;border-radius:8px;padding:9px 12px;font-weight:700; }
            QLabel#ayudaEmpleados { color:#6d726a;font-size:12px;padding:2px; }
            QTableWidget { background:white;border:1px solid #d8dbd4;border-radius:10px;gridline-color:#eceee9;selection-background-color:#fff0b4;selection-color:#292d28;font-size:14px; }
            QTableWidget::item { padding:8px;border-bottom:1px solid #eef0eb; }
            QHeaderView::section { background:#343934;color:white;border:0;border-right:1px solid #4c514c;padding:10px 8px;font-size:12px;font-weight:800; }
            QPushButton { min-height:42px;border-radius:8px;border:1px solid #cdd1c9;background:white;color:#343934;padding:0 13px;font-weight:700; }
            QPushButton:hover { background:#f8f0cf;border-color:#dfbd45; }
            QPushButton#agregarEmpleado { background:#d8ad25;color:#242820;border-color:#c99e19; }
            QPushButton#agregarEmpleado:hover { background:#e5bc38; }
            QPushButton#cerrarEmpleados { background:#343934;color:white;border:0; }
            QPushButton#cerrarEmpleados:hover { background:#454b45; }
        """)
        encabezado = QHBoxLayout()
        textos = QVBoxLayout()
        textos.setSpacing(1)
        seccion = QLabel("ADMINISTRACION")
        seccion.setObjectName("seccionEmpleados")
        titulo = QLabel("Empleados y permisos")
        titulo.setObjectName("tituloEmpleados")
        textos.addWidget(seccion)
        textos.addWidget(titulo)
        encabezado.addLayout(textos)
        encabezado.addStretch()
        self.resumen = QLabel()
        self.resumen.setObjectName("resumenEmpleados")
        encabezado.addWidget(self.resumen)
        principal.addLayout(encabezado)
        ayuda = QLabel("Selecciona una persona para editar su acceso, cambiar el PIN o consultar movimientos.")
        ayuda.setObjectName("ayudaEmpleados")
        principal.addWidget(ayuda)
        self.tabla = QTableWidget(0, 4)
        self.tabla.setHorizontalHeaderLabels(["ID", "Empleado", "Rol", "Estado"])
        self.tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SingleSelection)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setShowGrid(False)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.verticalHeader().setDefaultSectionSize(46)
        self.tabla.horizontalHeader().setMinimumHeight(42)
        self.tabla.setColumnWidth(0, 64)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabla.setColumnWidth(2, 175)
        self.tabla.setColumnWidth(3, 125)
        principal.addWidget(self.tabla)
        botones = QHBoxLayout()
        for texto, funcion in (
            ("Agregar empleado", self.agregar),
            ("Editar rol / estado", self.editar),
            ("Cambiar PIN", self.cambiar_pin),
            ("Ver auditoría", self.ver_auditoria),
        ):
            boton = QPushButton(texto)
            if funcion == self.agregar:
                boton.setObjectName("agregarEmpleado")
            boton.clicked.connect(funcion)
            botones.addWidget(boton)
        principal.addLayout(botones)
        cerrar = QPushButton("Cerrar")
        cerrar.setObjectName("cerrarEmpleados")
        cerrar.setMinimumWidth(140)
        cerrar.clicked.connect(self.accept)
        fila_cerrar = QHBoxLayout()
        fila_cerrar.addStretch()
        fila_cerrar.addWidget(cerrar)
        principal.addLayout(fila_cerrar)
        self.recargar()

    def recargar(self):
        empleados = obtener_empleados()
        activos = sum(1 for empleado in empleados if empleado[3])
        self.resumen.setText(f"{activos} activos  ·  {len(empleados)} registrados")
        self.tabla.setRowCount(len(empleados))
        for fila, (eid, nombre, rol, activo, _creado, _actualizado) in enumerate(empleados):
            for columna, valor in enumerate((eid, nombre, rol, "Activo" if activo else "Inactivo")):
                item = QTableWidgetItem(str(valor))
                if columna in (0, 2, 3):
                    item.setTextAlignment(Qt.AlignCenter)
                if columna == 3:
                    item.setForeground(Qt.darkGreen if activo else Qt.gray)
                    fuente = item.font()
                    fuente.setBold(True)
                    item.setFont(fuente)
                self.tabla.setItem(fila, columna, item)
        if empleados:
            self.tabla.selectRow(0)

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
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(10)
        dialogo.setStyleSheet("""
            QDialog { background:#f2f3ef; }
            QLabel { color:#292d28;font-size:22px;font-weight:800; }
            QTextEdit { background:white;border:1px solid #d4d8d0;border-radius:9px;padding:12px;color:#363b35;font-family:Consolas;font-size:12px; }
            QPushButton { min-width:140px;min-height:40px;background:#343934;color:white;border:0;border-radius:8px;font-weight:700; }
        """)
        titulo = QLabel("Historial de movimientos")
        layout.addWidget(titulo)
        visor = QTextEdit()
        visor.setReadOnly(True)
        visor.setPlainText(texto)
        layout.addWidget(visor)
        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(dialogo.accept)
        fila_cerrar = QHBoxLayout()
        fila_cerrar.addStretch()
        fila_cerrar.addWidget(cerrar)
        layout.addLayout(fila_cerrar)
        preparar_pagina_maximizada(dialogo)
        dialogo.exec()


class ConfiguracionDialog(PantallaDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Configuración - La Esquina Manager")
        self.resize(720, 650)

        self.configuracion = cargar_configuracion()

        principal = QVBoxLayout(self)
        principal.setContentsMargins(26, 23, 26, 22)
        principal.setSpacing(13)
        self.setStyleSheet("""
            QDialog { background:#f2f3ef; }
            QLabel#seccionConfiguracion { color:#777c73;font-size:11px;font-weight:800; }
            QLabel#tituloConfiguracion { color:#292d28;font-size:25px;font-weight:800; }
            QLabel#descripcionConfiguracion { color:#666c63;font-size:13px; }
            QGroupBox {
                background:white;border:1px solid #d6dad2;border-radius:10px;
                margin-top:12px;padding:18px 16px 13px;font-weight:800;color:#3e443d;
            }
            QGroupBox::title { subcontrol-origin:margin;left:14px;padding:0 7px; }
            QDoubleSpinBox, QSpinBox, QLineEdit {
                min-height:40px;background:#fbfcfa;border:1px solid #cbd0c7;
                border-radius:7px;padding:2px 9px;font-size:16px;font-weight:700;
            }
            QDoubleSpinBox:focus, QSpinBox:focus, QLineEdit:focus { border:2px solid #d8ad25; }
            QLabel#notaConfiguracion {
                color:#555b52;background:#fff8d9;border:1px solid #ead585;
                border-radius:8px;padding:10px 12px;
            }
            QPushButton { min-width:130px;min-height:42px;border-radius:8px;font-weight:700; }
        """)

        seccion = QLabel("ADMINISTRACIÓN")
        seccion.setObjectName("seccionConfiguracion")
        principal.addWidget(seccion)
        titulo = QLabel("Configuración del negocio")
        titulo.setObjectName("tituloConfiguracion")
        principal.addWidget(titulo)
        descripcion = QLabel("Personaliza la identidad del sistema y define las metas gerenciales.")
        descripcion.setObjectName("descripcionConfiguracion")
        principal.addWidget(descripcion)

        grupo_metas = QGroupBox("Metas de operación")
        formulario = QFormLayout()
        formulario.setContentsMargins(5, 8, 5, 4)
        formulario.setHorizontalSpacing(18)
        formulario.setVerticalSpacing(13)

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

        grupo_metas.setLayout(formulario)

        nota = QLabel(
            "Estas metas alimentan el Dashboard y puedes cambiarlas "
            "cuando quieras sin modificar el código."
        )
        nota.setWordWrap(True)
        nota.setObjectName("notaConfiguracion")
        contenido_configuracion = QWidget()
        layout_contenido = QVBoxLayout(contenido_configuracion)
        layout_contenido.setContentsMargins(4, 4, 8, 4)
        layout_contenido.setSpacing(13)
        grupo_identidad = QGroupBox("Identidad e imagen")
        identidad = QGridLayout()
        identidad.setHorizontalSpacing(16)
        identidad.setVerticalSpacing(11)
        self.nombre_negocio = QLineEdit(str(self.configuracion["nombre_negocio"]))
        self.nombre_negocio.setMaxLength(45)
        self.subtitulo_negocio = QLineEdit(str(self.configuracion["subtitulo_negocio"]))
        self.subtitulo_negocio.setMaxLength(65)
        self.ruta_logo = QLineEdit(str(self.configuracion.get("logo_negocio", "")))
        self.ruta_logo.setReadOnly(True)
        self.ruta_logo.setPlaceholderText("Sin logotipo: se mostrarán las iniciales")
        boton_logo = QPushButton("Elegir imagen…")
        boton_logo.clicked.connect(self.elegir_logo)
        boton_quitar_logo = QPushButton("Quitar logo")
        boton_quitar_logo.clicked.connect(self.quitar_logo)
        fila_logo = QHBoxLayout()
        fila_logo.addWidget(self.ruta_logo, 1)
        fila_logo.addWidget(boton_logo)
        fila_logo.addWidget(boton_quitar_logo)
        self.color_principal = str(self.configuracion["color_principal"])
        self.color_secundario = str(self.configuracion["color_secundario"])
        self.boton_color_principal = QPushButton()
        self.boton_color_secundario = QPushButton()
        self.boton_color_principal.clicked.connect(lambda: self.elegir_color("principal"))
        self.boton_color_secundario.clicked.connect(lambda: self.elegir_color("secundario"))
        identidad.addWidget(QLabel("Nombre del negocio:"), 0, 0)
        identidad.addWidget(self.nombre_negocio, 0, 1)
        identidad.addWidget(QLabel("Texto secundario:"), 1, 0)
        identidad.addWidget(self.subtitulo_negocio, 1, 1)
        identidad.addWidget(QLabel("Logotipo:"), 2, 0)
        identidad.addLayout(fila_logo, 2, 1)
        colores = QHBoxLayout()
        colores.addWidget(QLabel("Color principal"))
        colores.addWidget(self.boton_color_principal)
        colores.addSpacing(20)
        colores.addWidget(QLabel("Fondo principal"))
        colores.addWidget(self.boton_color_secundario)
        colores.addStretch()
        identidad.addWidget(QLabel("Colores:"), 3, 0)
        identidad.addLayout(colores, 3, 1)
        grupo_identidad.setLayout(identidad)
        layout_contenido.addWidget(grupo_identidad)
        layout_contenido.addWidget(grupo_metas)
        layout_contenido.addWidget(nota)
        layout_contenido.addStretch()
        scroll_configuracion = QScrollArea()
        scroll_configuracion.setWidgetResizable(True)
        scroll_configuracion.setFrameShape(QScrollArea.NoFrame)
        scroll_configuracion.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_configuracion.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_configuracion.setWidget(contenido_configuracion)
        principal.addWidget(scroll_configuracion, 1)

        botones = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        botones.accepted.connect(self.guardar)
        botones.rejected.connect(self.reject)
        guardar = botones.button(QDialogButtonBox.Save)
        cancelar = botones.button(QDialogButtonBox.Cancel)
        guardar.setText("Guardar cambios")
        guardar.setStyleSheet("background:#d8ad25;color:#242820;border:1px solid #c99e19;")
        cancelar.setText("Cancelar")
        cancelar.setStyleSheet("background:#343934;color:white;border:0;")
        principal.addWidget(botones)
        self.actualizar_botones_color()

    def actualizar_botones_color(self):
        for boton, color in ((self.boton_color_principal, self.color_principal),
                             (self.boton_color_secundario, self.color_secundario)):
            boton.setText(color.upper())
            boton.setStyleSheet(
                f"background:{color};color:{'#fff' if QColor(color).lightness() < 135 else '#111'};"
                "border:1px solid #777;min-width:105px;"
            )

    def elegir_color(self, tipo):
        actual = self.color_principal if tipo == "principal" else self.color_secundario
        color = QColorDialog.getColor(QColor(actual), self, "Elegir color")
        if not color.isValid():
            return
        if tipo == "principal":
            self.color_principal = color.name()
        else:
            self.color_secundario = color.name()
        self.actualizar_botones_color()

    def elegir_logo(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Elegir logotipo", "", "Imágenes (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if ruta:
            self.ruta_logo.setText(ruta)

    def quitar_logo(self):
        self.ruta_logo.clear()

    def guardar(self):
        nueva_configuracion = {
            "meta_venta_diaria": self.meta_venta_diaria.value(),
            "meta_venta_semanal": self.meta_venta_semanal.value(),
            "meta_personas_dia": self.meta_personas_dia.value(),
            "nombre_negocio": self.nombre_negocio.text().strip() or "MI NEGOCIO",
            "subtitulo_negocio": self.subtitulo_negocio.text().strip() or "PUNTO DE VENTA",
            "color_principal": self.color_principal,
            "color_secundario": self.color_secundario,
        }

        ruta_logo = self.ruta_logo.text().strip()
        if ruta_logo and Path(ruta_logo).is_file():
            carpeta_marca = APPLICATION_FOLDER / "data" / "branding"
            carpeta_marca.mkdir(parents=True, exist_ok=True)
            destino_logo = carpeta_marca / ("logo" + Path(ruta_logo).suffix.lower())
            if Path(ruta_logo).resolve() != destino_logo.resolve():
                for anterior in carpeta_marca.glob("logo.*"):
                    if anterior != destino_logo:
                        anterior.unlink(missing_ok=True)
                shutil.copy2(ruta_logo, destino_logo)
            nueva_configuracion["logo_negocio"] = str(destino_logo)
        else:
            nueva_configuracion["logo_negocio"] = ""

        guardar_configuracion(nueva_configuracion)
        QMessageBox.information(
            self,
            "Configuración guardada",
            "La personalización se guardó correctamente.\n\n"
            "Cierra y vuelve a abrir el programa para ver todos los cambios."
        )
        self.accept()


class AnalisisVentasDialog(PantallaDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Análisis de ventas - La Esquina Manager")
        self.resize(1180, 780)
        principal = QVBoxLayout(self)
        principal.setContentsMargins(20, 18, 20, 18)
        principal.setSpacing(11)
        self.setStyleSheet("""
            QDialog { background:#f2f3ef; }
            QLabel#tituloAnalisis { color:#252924;font-size:26px;font-weight:800; }
            QLabel#periodoAnalisis { color:#6b7168;font-size:13px; }
            QWidget#tarjetaAnalisis { background:white;border:1px solid #d9ddd5;border-radius:10px; }
            QLabel#tituloTarjetaAnalisis { color:#777d74;font-size:11px;font-weight:800; }
            QLabel#valorTarjetaAnalisis { color:#252924;font-size:23px;font-weight:800; }
            QPushButton#periodoRapido { min-height:38px;background:white;border:1px solid #d4d8d0;border-radius:8px;padding:0 14px;font-weight:700; }
            QPushButton#periodoRapido:hover { background:#fff4c5;border-color:#deb831; }
            QPushButton#aplicarAnalisis { min-height:40px;background:#d8ad25;color:#242820;border:1px solid #c99e19;border-radius:8px;padding:0 18px;font-weight:800; }
            QDateEdit { min-height:38px;background:white;border:1px solid #cfd3cb;border-radius:7px;padding:0 8px;font-size:14px; }
            QTabWidget::pane { background:white;border:1px solid #d9ddd5;border-radius:8px; }
            QTabBar::tab { background:#e7e9e4;padding:10px 16px;margin-right:2px;font-weight:700; }
            QTabBar::tab:selected { background:#343934;color:white; }
            QTableWidget { background:white;border:0;gridline-color:#e8ebe5;alternate-background-color:#f8f9f6; }
            QHeaderView::section { background:#343934;color:white;border:0;padding:9px;font-weight:800; }
            QPushButton#cerrarAnalisis { min-width:140px;min-height:40px;background:#343934;color:white;border:0;border-radius:8px;font-weight:700; }
        """)

        cabecera = QHBoxLayout()
        textos = QVBoxLayout()
        titulo = QLabel("Análisis de ventas")
        titulo.setObjectName("tituloAnalisis")
        self.periodo = QLabel()
        self.periodo.setObjectName("periodoAnalisis")
        textos.addWidget(titulo)
        textos.addWidget(self.periodo)
        cabecera.addLayout(textos)
        cabecera.addStretch()
        principal.addLayout(cabecera)

        filtros = QHBoxLayout()
        for texto, periodo in (("Hoy", "hoy"), ("Esta semana", "semana"), ("Este mes", "mes")):
            boton = QPushButton(texto)
            boton.setObjectName("periodoRapido")
            boton.clicked.connect(lambda _=False, p=periodo: self.seleccionar_periodo(p))
            filtros.addWidget(boton)
        filtros.addSpacing(12)
        filtros.addWidget(QLabel("Desde:"))
        self.fecha_inicio = QDateEdit()
        self.fecha_inicio.setCalendarPopup(True)
        self.fecha_inicio.setDisplayFormat("dd/MM/yyyy")
        filtros.addWidget(self.fecha_inicio)
        filtros.addWidget(QLabel("Hasta:"))
        self.fecha_fin = QDateEdit()
        self.fecha_fin.setCalendarPopup(True)
        self.fecha_fin.setDisplayFormat("dd/MM/yyyy")
        filtros.addWidget(self.fecha_fin)
        aplicar = QPushButton("Aplicar rango")
        aplicar.setObjectName("aplicarAnalisis")
        aplicar.clicked.connect(self.recargar)
        filtros.addWidget(aplicar)
        filtros.addStretch()
        principal.addLayout(filtros)

        tarjetas = QHBoxLayout()
        tarjetas.setSpacing(9)
        self.valores = {}
        for clave, etiqueta in (
            ("venta_total", "VENTA TOTAL"), ("tickets", "TICKETS"),
            ("personas", "PERSONAS"), ("ticket_promedio", "TICKET PROMEDIO"),
            ("promedio_persona", "VENTA / PERSONA"), ("ticket_maximo", "TICKET MAYOR"),
        ):
            tarjeta = QWidget()
            tarjeta.setObjectName("tarjetaAnalisis")
            layout = QVBoxLayout(tarjeta)
            layout.setContentsMargins(12, 10, 12, 10)
            rotulo = QLabel(etiqueta)
            rotulo.setObjectName("tituloTarjetaAnalisis")
            valor = QLabel("—")
            valor.setObjectName("valorTarjetaAnalisis")
            layout.addWidget(rotulo)
            layout.addWidget(valor)
            self.valores[clave] = valor
            tarjetas.addWidget(tarjeta, 1)
        principal.addLayout(tarjetas)

        self.pestanas = QTabWidget()
        self.tabla_ventas = self._crear_tabla(["Folio", "Fecha", "Total", "Forma de pago", "Personas", "¿Cómo se enteró?"])
        self.tabla_productos = self._crear_tabla(["Producto", "Unidades", "Ingreso"])
        self.tabla_metodos = self._crear_tabla(["Forma de pago", "Tickets", "Importe", "% de venta"])
        self.tabla_dias = self._crear_tabla(["Fecha", "Tickets", "Venta", "Personas", "Ticket promedio"])
        self.tabla_personal = self._crear_tabla(["Empleado", "Tickets", "Venta"])
        self.tabla_origenes = self._crear_tabla(["¿Cómo se enteró?", "Personas", "% personas", "Tickets", "Venta"])
        self.pestanas.addTab(self.tabla_ventas, "Todas las ventas")
        self.pestanas.addTab(self.tabla_productos, "Productos")
        self.pestanas.addTab(self.tabla_metodos, "Formas de pago")
        self.pestanas.addTab(self.tabla_dias, "Ventas por día")
        self.pestanas.addTab(self.tabla_personal, "Ventas por empleado")
        self.pestanas.addTab(self.tabla_origenes, "¿Cómo se enteró?")
        principal.addWidget(self.pestanas, 1)

        pie = QHBoxLayout()
        self.detalle_rango = QLabel()
        self.detalle_rango.setStyleSheet("color:#6b7168;font-weight:700;")
        pie.addWidget(self.detalle_rango)
        pie.addStretch()
        cerrar = QPushButton("Cerrar")
        cerrar.setObjectName("cerrarAnalisis")
        cerrar.clicked.connect(self.accept)
        pie.addWidget(cerrar)
        principal.addLayout(pie)
        self.seleccionar_periodo("hoy")

    def _crear_tabla(self, encabezados):
        tabla = QTableWidget(0, len(encabezados))
        tabla.setHorizontalHeaderLabels(encabezados)
        tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        tabla.setAlternatingRowColors(True)
        tabla.setSelectionBehavior(QTableWidget.SelectRows)
        tabla.verticalHeader().setVisible(False)
        tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        return tabla

    def _llenar(self, tabla, filas):
        tabla.setRowCount(len(filas))
        for fila, valores in enumerate(filas):
            for columna, valor in enumerate(valores):
                item = QTableWidgetItem(str(valor))
                if columna > 0:
                    item.setTextAlignment(Qt.AlignCenter)
                tabla.setItem(fila, columna, item)

    def seleccionar_periodo(self, periodo):
        hoy = QDate.currentDate()
        if periodo == "semana":
            inicio = hoy.addDays(1 - hoy.dayOfWeek())
        elif periodo == "mes":
            inicio = QDate(hoy.year(), hoy.month(), 1)
        else:
            inicio = hoy
        self.fecha_inicio.setDate(inicio)
        self.fecha_fin.setDate(hoy)
        self.recargar()

    def recargar(self):
        inicio = self.fecha_inicio.date().toString("yyyy-MM-dd")
        fin = self.fecha_fin.date().toString("yyyy-MM-dd")
        try:
            datos = obtener_analisis_ventas(inicio, fin)
        except Exception as error:
            QMessageBox.warning(self, "Rango no válido", str(error))
            return
        self.periodo.setText(
            f"Del {self.fecha_inicio.date().toString('dd/MM/yyyy')} al "
            f"{self.fecha_fin.date().toString('dd/MM/yyyy')}"
        )
        for clave in ("venta_total", "ticket_promedio", "promedio_persona", "ticket_maximo"):
            self.valores[clave].setText(f"${datos[clave]:,.2f}")
        self.valores["tickets"].setText(str(datos["tickets"]))
        self.valores["personas"].setText(str(datos["personas"]))
        self._llenar(self.tabla_ventas, [
            (v[0], v[1], f"${v[2]:,.2f}", v[3], v[4], v[5] or "—")
            for v in datos["ventas"]
        ])
        self._llenar(self.tabla_productos, [
            (p[0], p[1], f"${p[2]:,.2f}") for p in datos["productos"]
        ])
        total = datos["venta_total"]
        self._llenar(self.tabla_metodos, [
            (m[0], m[1], f"${m[2]:,.2f}", f"{(m[2] / total * 100) if total else 0:.1f}%")
            for m in datos["metodos"]
        ])
        self._llenar(self.tabla_dias, [
            (d[0], d[1], f"${d[2]:,.2f}", d[3], f"${d[2] / d[1] if d[1] else 0:,.2f}")
            for d in datos["por_dia"]
        ])
        self._llenar(self.tabla_personal, [
            (e[0], e[1], f"${e[2]:,.2f}") for e in datos["empleados"]
        ])
        total_personas = datos["personas"]
        self._llenar(self.tabla_origenes, [
            (
                o[0], o[1],
                f"{(o[1] / total_personas * 100) if total_personas else 0:.1f}%",
                o[2], f"${o[3]:,.2f}",
            )
            for o in datos["origenes"]
        ])
        self.detalle_rango.setText(
            f"{datos['tickets']} ventas encontradas  ·  "
            f"Ticket menor ${datos['ticket_minimo']:,.2f}  ·  "
            f"Ticket mayor ${datos['ticket_maximo']:,.2f}"
        )


class GraficaComparativaVentas(QWidget):
    def __init__(self, datos, parent=None):
        super().__init__(parent)
        self.datos = datos
        self.setMinimumHeight(300)
        self.setToolTip(
            "Dorado: semana actual · Gris: semana anterior"
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        ancho, alto = self.width(), self.height()
        izquierda, derecha, arriba, abajo = 72, 22, 48, 48
        graf_ancho = max(1, ancho - izquierda - derecha)
        graf_alto = max(1, alto - arriba - abajo)
        maximo = max(
            [float(d[clave]) for d in self.datos for clave in ("actual", "anterior")]
            + [1.0]
        )

        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QPen(QColor("#d9ddd5"), 1))
        for paso in range(5):
            y = arriba + graf_alto - (graf_alto * paso / 4)
            painter.drawLine(izquierda, int(y), ancho - derecha, int(y))
            valor = maximo * paso / 4
            painter.setPen(QColor("#70766d"))
            painter.drawText(2, int(y - 9), izquierda - 8, 18, Qt.AlignRight, f"${valor:,.0f}")
            painter.setPen(QPen(QColor("#d9ddd5"), 1))

        grupo = graf_ancho / max(1, len(self.datos))
        barra = min(34.0, grupo * 0.28)
        for indice, dato in enumerate(self.datos):
            centro = izquierda + grupo * (indice + 0.5)
            for desplazamiento, clave, color in (
                (-barra, "anterior", QColor("#9ba198")),
                (0, "actual", QColor("#e0b52c")),
            ):
                valor = float(dato[clave])
                altura = graf_alto * valor / maximo
                painter.setBrush(color)
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(
                    int(centro + desplazamiento), int(arriba + graf_alto - altura),
                    max(2, int(barra - 2)), max(1, int(altura)), 3, 3
                )
            painter.setPen(QColor("#343934"))
            painter.drawText(
                int(centro - grupo / 2), alto - abajo + 8,
                int(grupo), 22, Qt.AlignCenter, dato["nombre"]
            )

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#e0b52c"))
        painter.drawRoundedRect(izquierda, 14, 14, 14, 3, 3)
        painter.setBrush(QColor("#9ba198"))
        painter.drawRoundedRect(izquierda + 150, 14, 14, 14, 3, 3)
        painter.setPen(QColor("#343934"))
        painter.drawText(izquierda + 20, 10, 125, 22, Qt.AlignVCenter, "Semana actual")
        painter.drawText(izquierda + 170, 10, 135, 22, Qt.AlignVCenter, "Semana anterior")


class DashboardDialog(PantallaDialog):
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

        caja_grafica = QGroupBox("Comparativo de ventas por día")
        layout_grafica = QVBoxLayout(caja_grafica)
        grafica = GraficaComparativaVentas(obtener_comparativo_ventas_diarias())
        layout_grafica.addWidget(grafica)
        principal.addWidget(caja_grafica)

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


class HistorialDialog(PantallaDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Historial de ventas - La Esquina Manager")
        self.resize(980, 650)

        principal = QVBoxLayout(self)
        principal.setContentsMargins(18, 16, 18, 16)
        principal.setSpacing(10)
        self.setStyleSheet("""
            QDialog { background-color:#f2f3ef; }
            QLabel#tituloHistorial { color:#242722;font-size:24px;font-weight:800; }
            QLabel#resumenHistorial {
                color:#5e645b;background:white;border:1px solid #dfe2dc;
                border-radius:13px;padding:6px 11px;font-size:12px;font-weight:700;
            }
            QLabel#seccionHistorial {
                color:#747970;font-size:11px;font-weight:800;padding:4px 2px 0 2px;
            }
            QTableWidget {
                background:white;border:1px solid #dfe2dc;border-radius:8px;
                gridline-color:#e7e9e4;alternate-background-color:#f8f9f6;
                selection-background-color:#fff0ad;selection-color:#242722;
            }
            QHeaderView::section {
                background:#292d28;color:white;border:none;padding:8px;
                font-weight:700;
            }
            QGroupBox {
                color:#62675f;font-weight:800;border:1px solid #dfe2dc;
                border-radius:9px;margin-top:10px;padding-top:10px;background:white;
            }
            QGroupBox::title { subcontrol-origin:margin;left:10px;padding:0 5px; }
        """)

        cabecera = QWidget()
        layout_cabecera = QHBoxLayout(cabecera)
        layout_cabecera.setContentsMargins(2, 0, 2, 0)
        titulo = QLabel("HISTORIAL DE VENTAS")
        titulo.setObjectName("tituloHistorial")
        self.resumen_historial = QLabel("Actualizando…")
        self.resumen_historial.setObjectName("resumenHistorial")
        layout_cabecera.addWidget(titulo)
        layout_cabecera.addStretch()
        layout_cabecera.addWidget(self.resumen_historial)
        principal.addWidget(cabecera)

        etiqueta_ventas = QLabel("VENTAS REGISTRADAS")
        etiqueta_ventas.setObjectName("seccionHistorial")
        principal.addWidget(etiqueta_ventas)

        self.tabla = QTableWidget()
        self.tabla.setColumnCount(6)
        self.tabla.setHorizontalHeaderLabels(
            ["Folio", "Fecha", "Total", "Pago", "Personas", "Origen"]
        )
        self.tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SingleSelection)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setShowGrid(False)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.verticalHeader().setDefaultSectionSize(38)
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
        self.detalle.setAlternatingRowColors(True)
        self.detalle.setShowGrid(False)
        self.detalle.verticalHeader().setVisible(False)
        self.detalle.verticalHeader().setDefaultSectionSize(34)
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
        boton_actualizar.setStyleSheet(
            "font-weight:700;background:#f4f5f2;border:1px solid #d2d5ce;"
            "border-radius:8px;"
        )
        boton_actualizar.clicked.connect(self.recargar)

        boton_reimprimir = QPushButton("Reimprimir ticket")
        boton_reimprimir.setMinimumHeight(42)
        boton_reimprimir.setStyleSheet("""
            QPushButton {
                font-size: 15px;
                font-weight: bold;
                background-color: #f2c94c;
                border:1px solid #dfb52c;
                border-radius: 8px;
            }
            QPushButton:hover { background-color:#ffda61; }
        """)
        boton_reimprimir.clicked.connect(self.reimprimir)

        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.setMinimumHeight(42)
        boton_cerrar.setStyleSheet(boton_actualizar.styleSheet())
        boton_cerrar.clicked.connect(self.accept)

        botones.addWidget(boton_actualizar)
        botones.addWidget(boton_reimprimir)
        botones.addWidget(boton_cerrar)
        principal.addLayout(botones)

        self.recargar()

    def recargar(self):
        ventas = obtener_historial_ventas()
        total_historial = sum(venta[2] for venta in ventas)
        self.resumen_historial.setText(
            f"{len(ventas)} ventas  ·  ${total_historial:,.2f}"
        )
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


class ProductosDialog(PantallaDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Administrar productos - La Esquina Manager")
        self.resize(850, 560)

        principal = QVBoxLayout(self)
        principal.setContentsMargins(18, 16, 18, 16)
        principal.setSpacing(10)
        self.setStyleSheet("""
            QDialog { background:#f2f3ef; }
            QLabel#tituloProductosAdmin { color:#242722;font-size:24px;font-weight:800; }
            QLabel#resumenProductosAdmin {
                color:#5e645b;background:white;border:1px solid #dfe2dc;
                border-radius:13px;padding:6px 11px;font-size:12px;font-weight:700;
            }
            QLabel#notaProductosAdmin {
                color:#545a51;background:#fff5ce;border:1px solid #ead585;
                border-radius:8px;padding:9px 11px;
            }
            QTableWidget {
                background:white;border:1px solid #dfe2dc;border-radius:8px;
                gridline-color:#e7e9e4;alternate-background-color:#f8f9f6;
                selection-background-color:#fff0ad;selection-color:#242722;
            }
            QHeaderView::section {
                background:#292d28;color:white;border:none;padding:8px;font-weight:700;
            }
        """)

        cabecera = QWidget()
        layout_cabecera = QHBoxLayout(cabecera)
        layout_cabecera.setContentsMargins(2, 0, 2, 0)
        titulo = QLabel("ADMINISTRAR PRODUCTOS")
        titulo.setObjectName("tituloProductosAdmin")
        self.resumen_productos = QLabel("Actualizando…")
        self.resumen_productos.setObjectName("resumenProductosAdmin")
        layout_cabecera.addWidget(titulo)
        layout_cabecera.addStretch()
        layout_cabecera.addWidget(self.resumen_productos)
        principal.addWidget(cabecera)

        nota = QLabel(
            "Los productos desactivados dejan de aparecer en el POS, "
            "pero conservan su historial de ventas."
        )
        nota.setObjectName("notaProductosAdmin")
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
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setShowGrid(False)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.verticalHeader().setDefaultSectionSize(38)
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
        boton_agregar.setStyleSheet(
            "background:#27ae60;color:white;border:none;border-radius:8px;"
            "font-weight:800;"
        )
        boton_agregar.clicked.connect(self.agregar)

        boton_editar = QPushButton("Editar / cambiar precio")
        boton_editar.setMinimumHeight(42)
        boton_editar.setStyleSheet(
            "background:#f2c94c;border:1px solid #dfb52c;border-radius:8px;"
            "font-weight:800;"
        )
        boton_editar.clicked.connect(self.editar)

        boton_foto = QPushButton("Asignar foto")
        boton_foto.setMinimumHeight(42)
        boton_foto.setStyleSheet(
            "background:#ffffff;border:1px solid #d2d5ce;border-radius:8px;"
            "font-weight:700;"
        )
        boton_foto.clicked.connect(self.asignar_foto)

        boton_estado = QPushButton("Activar / Desactivar")
        boton_estado.setMinimumHeight(42)
        boton_estado.setStyleSheet(
            "background:#f4f5f2;border:1px solid #d2d5ce;border-radius:8px;"
            "font-weight:700;"
        )
        boton_estado.clicked.connect(self.cambiar_estado)

        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.setMinimumHeight(42)
        boton_cerrar.setStyleSheet(boton_estado.styleSheet())
        boton_cerrar.clicked.connect(self.accept)

        botones.addWidget(boton_agregar)
        botones.addWidget(boton_editar)
        botones.addWidget(boton_foto)
        botones.addWidget(boton_estado)
        botones.addWidget(boton_cerrar)

        principal.addLayout(botones)
        self.recargar()

    def asignar_foto(self):
        seleccionado = self._seleccionado()
        if seleccionado is None:
            return
        producto_id, nombre, _precio, _categoria, _activo = seleccionado
        origen, _filtro = QFileDialog.getOpenFileName(
            self,
            f"Seleccionar foto para {nombre}",
            "",
            "Imágenes (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not origen:
            return
        imagen = QPixmap(origen)
        if imagen.isNull():
            QMessageBox.warning(
                self, "Imagen no válida", "No se pudo leer la foto seleccionada."
            )
            return
        try:
            PRODUCT_IMAGES_FOLDER.mkdir(parents=True, exist_ok=True)
            extension = Path(origen).suffix.lower()
            destino = PRODUCT_IMAGES_FOLDER / f"producto_{producto_id}{extension}"
            if Path(origen).resolve() != destino.resolve():
                shutil.copy2(origen, destino)
            actualizar_imagen_producto(producto_id, destino.name)
            QMessageBox.information(
                self, "Foto guardada", f"La foto de {nombre} quedó actualizada."
            )
        except Exception as error:
            QMessageBox.critical(self, "No se pudo guardar la foto", str(error))

    def recargar(self):
        productos = obtener_productos(solo_activos=False)
        activos = sum(1 for producto in productos if producto[4])
        self.resumen_productos.setText(
            f"{activos} activos  ·  {len(productos) - activos} inactivos"
        )
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
            estado = QTableWidgetItem("Activo" if activo else "Inactivo")
            self.tabla.setItem(fila, 4, estado)
            if not activo:
                for columna in range(5):
                    self.tabla.item(fila, columna).setForeground(Qt.gray)

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


class GastoEdicionDialog(PantallaDialog):
    def __init__(self, gasto=None, parent=None):
        super().__init__(parent)
        self.gasto = gasto
        self.setWindowTitle(
            "Corregir gasto" if gasto else "Registrar gasto"
        )
        self.resize(500, 390)
        principal = QVBoxLayout(self)
        principal.setContentsMargins(20, 18, 20, 18)
        principal.setSpacing(12)
        self.setStyleSheet("""
            QDialog { background:#f2f3ef; }
            QLabel#tituloGastoEdicion { color:#242722;font-size:22px;font-weight:800; }
            QLabel#notaGastoEdicion {
                color:#545a51;background:#fff5ce;border:1px solid #ead585;
                border-radius:8px;padding:9px 11px;
            }
            QLineEdit,QComboBox,QDoubleSpinBox,QDateTimeEdit,QTextEdit {
                min-height:36px;background:white;border:1px solid #cfd3cb;
                border-radius:7px;padding:3px 8px;
            }
            QPushButton { min-height:42px;border-radius:8px;font-weight:700; }
        """)
        titulo = QLabel("CORREGIR GASTO" if gasto else "REGISTRAR GASTO")
        titulo.setObjectName("tituloGastoEdicion")
        principal.addWidget(titulo)
        formulario = QFormLayout()
        formulario.setVerticalSpacing(10)

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
        nota.setObjectName("notaGastoEdicion")
        nota.setWordWrap(True)
        principal.addWidget(nota)

        botones = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        botones.accepted.connect(self.validar)
        botones.rejected.connect(self.reject)
        guardar = botones.button(QDialogButtonBox.Save)
        guardar.setText("GUARDAR GASTO")
        guardar.setStyleSheet("background:#27ae60;color:white;border:none;")
        botones.button(QDialogButtonBox.Cancel).setText("Cancelar")
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


class GastosDialog(PantallaDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gastos del dia - La Esquina Manager")
        self.resize(1050, 620)
        principal = QVBoxLayout(self)
        principal.setContentsMargins(18, 16, 18, 16)
        principal.setSpacing(10)
        self.setStyleSheet("""
            QDialog { background:#f2f3ef; }
            QLabel#tituloGastos { color:#242722;font-size:24px;font-weight:800; }
            QLabel#notaGastos {
                color:#5e645b;background:white;border:1px solid #dfe2dc;
                border-radius:8px;padding:9px 12px;
            }
            QLabel#totalGastos {
                color:white;background:#292d28;border-radius:9px;
                padding:12px 15px;font-size:19px;font-weight:800;
            }
            QTableWidget {
                background:white;border:1px solid #dfe2dc;border-radius:8px;
                gridline-color:#e7e9e4;alternate-background-color:#f8f9f6;
                selection-background-color:#fff0ad;selection-color:#242722;
            }
            QHeaderView::section {
                background:#292d28;color:white;border:none;padding:8px;font-weight:700;
            }
        """)

        titulo = QLabel("GASTOS DEL DIA")
        titulo.setObjectName("tituloGastos")
        principal.addWidget(titulo)

        nota = QLabel(
            "Los gastos anulados permanecen visibles y no se suman. "
            "Todas las correcciones quedan registradas."
        )
        nota.setObjectName("notaGastos")
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
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setShowGrid(False)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.verticalHeader().setDefaultSectionSize(38)
        self.tabla.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch
        )
        principal.addWidget(self.tabla)

        self.total = QLabel()
        self.total.setObjectName("totalGastos")
        self.total.setAlignment(Qt.AlignRight)
        principal.addWidget(self.total)

        botones = QHBoxLayout()
        for indice, (texto, funcion) in enumerate((
            ("Registrar gasto", self.registrar),
            ("Corregir seleccionado", self.corregir),
            ("Anular seleccionado", self.anular),
            ("Ver auditoria", self.ver_auditoria),
        )):
            boton = QPushButton(texto)
            boton.setMinimumHeight(42)
            if indice == 0:
                boton.setStyleSheet(
                    "background:#27ae60;color:white;border:none;border-radius:8px;"
                    "font-weight:800;"
                )
            elif indice == 2:
                boton.setStyleSheet(
                    "color:#9b2f2f;background:#fff5f5;border:1px solid #efcccc;"
                    "border-radius:8px;font-weight:700;"
                )
            else:
                boton.setStyleSheet(
                    "background:#f4f5f2;border:1px solid #d2d5ce;"
                    "border-radius:8px;font-weight:700;"
                )
            boton.clicked.connect(funcion)
            botones.addWidget(boton)
        cerrar = QPushButton("Cerrar")
        cerrar.setMinimumHeight(42)
        cerrar.setStyleSheet(
            "background:#f4f5f2;border:1px solid #d2d5ce;"
            "border-radius:8px;font-weight:700;"
        )
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


class PedidosMovilDialog(PantallaDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pedidos de meseros")
        self.resize(1050, 650)
        self.pedido_cargado = None
        principal = QVBoxLayout(self)
        principal.setContentsMargins(18, 16, 18, 16)
        principal.setSpacing(10)
        self.setStyleSheet("""
            QDialog { background-color:#f2f3ef; }
            QLabel#tituloPedidos { color:#242722;font-size:24px;font-weight:800; }
            QLabel#contadorPedidos {
                color:#165b78;background:#dff2fb;border:1px solid #acd8ea;
                border-radius:13px;padding:6px 11px;font-size:12px;font-weight:700;
            }
            QLabel#conexionMeseros {
                color:#454a43;background:white;border:1px solid #dfe2dc;
                border-radius:9px;padding:10px 13px;font-weight:600;
            }
            QLabel#seccionPedidos {
                color:#747970;font-size:11px;font-weight:800;padding:4px 2px 0 2px;
            }
            QTableWidget {
                background:white;border:1px solid #dfe2dc;border-radius:8px;
                gridline-color:#e7e9e4;alternate-background-color:#f8f9f6;
                selection-background-color:#dff2fb;selection-color:#242722;
            }
            QHeaderView::section {
                background:#292d28;color:white;border:none;padding:8px;
                font-weight:700;
            }
        """)

        cabecera = QWidget()
        layout_cabecera = QHBoxLayout(cabecera)
        layout_cabecera.setContentsMargins(2, 0, 2, 0)
        titulo = QLabel("PEDIDOS DE CELULARES Y TABLETAS")
        titulo.setObjectName("tituloPedidos")
        self.contador_pedidos = QLabel("Actualizando…")
        self.contador_pedidos.setObjectName("contadorPedidos")
        layout_cabecera.addWidget(titulo)
        layout_cabecera.addStretch()
        layout_cabecera.addWidget(self.contador_pedidos)
        principal.addWidget(cabecera)

        direccion = QLabel(
            f"Acceso para meseros:  {mobile_url()}\n"
            "Abre esta dirección desde un celular conectado al mismo Wi-Fi."
        )
        direccion.setObjectName("conexionMeseros")
        direccion.setTextInteractionFlags(Qt.TextSelectableByMouse)
        direccion.setWordWrap(True)
        principal.addWidget(direccion)

        etiqueta_pendientes = QLabel("PEDIDOS PENDIENTES Y EN CAJA")
        etiqueta_pendientes.setObjectName("seccionPedidos")
        principal.addWidget(etiqueta_pendientes)

        self.tabla = QTableWidget(0, 7)
        self.tabla.setHorizontalHeaderLabels([
            "Pedido", "Hora", "Mesa", "Mesero", "Notas", "Total", "Estado"
        ])
        self.tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SingleSelection)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setShowGrid(False)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.verticalHeader().setDefaultSectionSize(38)
        self.tabla.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        principal.addWidget(self.tabla)

        etiqueta_detalle = QLabel("DETALLE DEL PEDIDO SELECCIONADO")
        etiqueta_detalle.setObjectName("seccionPedidos")
        principal.addWidget(etiqueta_detalle)

        self.detalle = QTableWidget(0, 4)
        self.detalle.setHorizontalHeaderLabels([
            "Producto", "Cantidad", "Precio", "Importe"
        ])
        self.detalle.setEditTriggers(QTableWidget.NoEditTriggers)
        self.detalle.setAlternatingRowColors(True)
        self.detalle.setShowGrid(False)
        self.detalle.verticalHeader().setVisible(False)
        self.detalle.verticalHeader().setDefaultSectionSize(34)
        self.detalle.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.detalle.setMaximumHeight(210)
        principal.addWidget(self.detalle)
        self.tabla.itemSelectionChanged.connect(self.mostrar_detalle)

        botones = QHBoxLayout()
        cargar = QPushButton("Cargar pedido en caja")
        cargar.setMinimumHeight(45)
        cargar.setStyleSheet("""
            QPushButton {
                font-weight:800;background:#27ae60;color:white;border:none;
                border-radius:8px;padding:8px 16px;
            }
            QPushButton:hover { background:#219150; }
        """)
        cargar.clicked.connect(self.cargar)
        cancelar = QPushButton("Cancelar pedido")
        cancelar.setMinimumHeight(45)
        cancelar.setStyleSheet(
            "color:#9b2f2f;background:#fff5f5;border:1px solid #efcccc;"
            "border-radius:8px;font-weight:700;"
        )
        cancelar.clicked.connect(self.cancelar)
        actualizar = QPushButton("Actualizar")
        actualizar.setMinimumHeight(45)
        actualizar.setStyleSheet(
            "font-weight:700;background:#f4f5f2;border:1px solid #d2d5ce;"
            "border-radius:8px;"
        )
        actualizar.clicked.connect(self.recargar)
        cerrar = QPushButton("Cerrar")
        cerrar.setMinimumHeight(45)
        cerrar.setStyleSheet(actualizar.styleSheet())
        cerrar.clicked.connect(self.reject)
        for boton in (cargar, cancelar, actualizar, cerrar):
            botones.addWidget(boton)
        principal.addLayout(botones)
        self.recargar()

    def recargar(self):
        pedido_actual = None
        fila_actual = self.tabla.currentRow()
        if fila_actual >= 0 and self.tabla.item(fila_actual, 0):
            pedido_actual = int(self.tabla.item(fila_actual, 0).text())
        pedidos = obtener_pedidos_movil()
        pendientes = sum(1 for pedido in pedidos if pedido[6] == "Pendiente")
        en_caja = len(pedidos) - pendientes
        self.contador_pedidos.setText(
            f"{pendientes} pendientes  ·  {en_caja} en caja"
        )
        self.tabla.setRowCount(len(pedidos))
        fila_a_seleccionar = None
        for fila, pedido in enumerate(pedidos):
            pedido_id, fecha, mesa, mesero, notas, total, estado, _venta_id = pedido
            valores = (
                pedido_id, fecha[11:16], mesa, mesero, notas,
                f"${total:.2f}", estado,
            )
            for columna, valor in enumerate(valores):
                self.tabla.setItem(fila, columna, QTableWidgetItem(str(valor)))
            if pedido_id == pedido_actual:
                fila_a_seleccionar = fila
        self.detalle.setRowCount(0)
        if fila_a_seleccionar is not None:
            self.tabla.selectRow(fila_a_seleccionar)
        elif pedidos:
            fila_pendiente = next(
                (i for i, pedido in enumerate(pedidos) if pedido[6] == "Pendiente"),
                0,
            )
            self.tabla.selectRow(fila_pendiente)

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
        estado = self.tabla.item(self.tabla.currentRow(), 6).text()
        if estado == "Pendiente":
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


class MesasDialog(PantallaDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mapa de mesas")
        self.resize(1050, 720)
        self.mesa_seleccionada = None
        self.carga_mesa = None
        self.botones_mesas = {}
        principal = QVBoxLayout(self)
        principal.setContentsMargins(18, 16, 18, 16)
        principal.setSpacing(10)
        self.setStyleSheet("""
            QDialog { background-color:#f2f3ef; }
            QLabel#tituloMesas { color:#242722;font-size:24px;font-weight:800; }
            QLabel#estadoMesas {
                color:#5e645b;background:white;border:1px solid #dfe2dc;
                border-radius:14px;padding:7px 13px;font-weight:600;
            }
            QLabel#detalleMesa {
                color:#343832;background:white;border:1px solid #dfe2dc;
                border-radius:8px;padding:10px 12px;font-size:14px;font-weight:700;
            }
            QTableWidget {
                background:white;border:1px solid #dfe2dc;border-radius:8px;
                gridline-color:#e7e9e4;alternate-background-color:#f8f9f6;
            }
            QHeaderView::section {
                background:#292d28;color:white;border:none;padding:8px;
                font-weight:700;
            }
        """)

        cabecera = QWidget()
        layout_cabecera = QHBoxLayout(cabecera)
        layout_cabecera.setContentsMargins(2, 0, 2, 0)
        titulo = QLabel("MESAS Y BARRA")
        titulo.setObjectName("tituloMesas")
        self.estado_mesas = QLabel("Actualizando ocupación…")
        self.estado_mesas.setObjectName("estadoMesas")
        layout_cabecera.addWidget(titulo)
        layout_cabecera.addStretch()
        layout_cabecera.addWidget(self.estado_mesas)
        principal.addWidget(cabecera)

        leyenda = QLabel("● Libre     ● Ocupada     ·     Selecciona una mesa para consultar su cuenta")
        leyenda.setStyleSheet("color:#73786f;padding:0 3px 3px 3px;")
        principal.addWidget(leyenda)

        self.panel_mesas = QWidget()
        self.panel_mesas.setStyleSheet(
            "background:white;border:1px solid #dfe2dc;border-radius:10px;"
        )
        self.grid_mesas = QGridLayout(self.panel_mesas)
        self.grid_mesas.setContentsMargins(12, 12, 12, 12)
        self.grid_mesas.setSpacing(9)
        self.scroll_mesas = QScrollArea()
        self.scroll_mesas.setObjectName("scrollMesas")
        self.scroll_mesas.setWidgetResizable(True)
        self.scroll_mesas.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_mesas.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_mesas.setMinimumHeight(215)
        self.scroll_mesas.setMaximumHeight(405)
        self.scroll_mesas.setWidget(self.panel_mesas)
        principal.addWidget(self.scroll_mesas)

        self.resumen = QLabel("Selecciona una mesa ocupada para ver su cuenta.")
        self.resumen.setObjectName("detalleMesa")
        principal.addWidget(self.resumen)

        self.detalle = QTableWidget(0, 5)
        self.detalle.setHorizontalHeaderLabels([
            "Pedido", "Producto", "Cantidad", "Precio", "Importe"
        ])
        self.detalle.setEditTriggers(QTableWidget.NoEditTriggers)
        self.detalle.setAlternatingRowColors(True)
        self.detalle.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        principal.addWidget(self.detalle)

        botones = QHBoxLayout()
        cargar = QPushButton("Cargar cuenta completa en caja")
        cargar.setMinimumHeight(48)
        cargar.setStyleSheet(
            "font-weight:800;background:#27ae60;color:white;border:none;"
            "border-radius:8px;padding:8px 16px;"
        )
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
        self.botones_mesas = {}
        resumen_mesas = obtener_resumen_mesas()
        ocupadas = sum(1 for datos in resumen_mesas if datos["ocupada"])
        libres = len(resumen_mesas) - ocupadas
        self.estado_mesas.setText(f"{ocupadas} ocupadas  ·  {libres} libres")
        for indice, datos in enumerate(resumen_mesas):
            mesa = datos["mesa"]
            if datos["ocupada"]:
                texto = f"{mesa}\n${datos['total']:.2f}  ·  {datos['pedidos']} pedido(s)"
            else:
                texto = f"{mesa}\nLIBRE"
            boton = QPushButton(texto)
            boton.setMinimumSize(150, 78)
            boton.setCursor(Qt.PointingHandCursor)
            boton.setProperty("ocupada", datos["ocupada"])
            boton.setStyleSheet(self._estilo_boton_mesa(datos["ocupada"], False))
            boton.clicked.connect(
                lambda checked=False, nombre=mesa: self.seleccionar_mesa(nombre)
            )
            self.botones_mesas[mesa] = boton
            self.grid_mesas.addWidget(boton, indice // 5, indice % 5)
        if self.mesa_seleccionada:
            self.seleccionar_mesa(self.mesa_seleccionada)
        else:
            primera_ocupada = next(
                (datos["mesa"] for datos in resumen_mesas if datos["ocupada"]),
                None,
            )
            if primera_ocupada:
                self.seleccionar_mesa(primera_ocupada)

    def seleccionar_mesa(self, mesa):
        self.mesa_seleccionada = mesa
        for nombre, boton in self.botones_mesas.items():
            boton.setStyleSheet(self._estilo_boton_mesa(
                bool(boton.property("ocupada")), nombre == mesa
            ))
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
            comensales = obtener_comensales_mesa(mesa)
            detalle_comensales = " · ".join(
                f"C{c['numero']} {c['estado']} ${c['total']:.2f}"
                for c in comensales
            )
            if detalle_comensales:
                extra += f"   ·   {detalle_comensales}"
            self.resumen.setText(
                f"{mesa}: {len(pedidos)} pedido(s) · Total ${total:.2f}{extra}"
            )
        else:
            self.resumen.setText(f"{mesa}: LIBRE")

    @staticmethod
    def _estilo_boton_mesa(ocupada, seleccionada):
        fondo = "#f5b544" if ocupada else "#72d19a"
        borde = "#242722" if seleccionada else ("#dc9321" if ocupada else "#45af70")
        grosor = 3 if seleccionada else 1
        return f"""
            QPushButton {{
                color:#20231f;background:{fondo};border:{grosor}px solid {borde};
                border-radius:9px;font-size:14px;font-weight:800;padding:7px;
            }}
            QPushButton:hover {{ border:3px solid #5b6158; }}
        """

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
            if pedido[6] == "Pendiente":
                actualizar_estado_pedido_movil(pedido_id, "En caja")
        self.carga_mesa = (self.mesa_seleccionada, pedido_ids, detalles)
        self.accept()


class CuentasActivasDialog(PantallaDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cuentas activas")
        self.resize(1050, 680)
        self.cuenta_cargada = None
        principal = QVBoxLayout(self)
        principal.setContentsMargins(18, 16, 18, 16)
        principal.setSpacing(10)
        self.setStyleSheet("""
            QDialog { background-color:#f2f3ef; }
            QLabel#tituloCuentas { color:#242722;font-size:24px;font-weight:800; }
            QLabel#actualizacionCuentas {
                color:#6f746c;background:white;border:1px solid #dfe2dc;
                border-radius:13px;padding:6px 11px;font-size:12px;font-weight:600;
            }
            QLabel#resumenCuentas {
                color:#242722;background:#fff0ad;border:1px solid #e6cb64;
                border-radius:9px;padding:11px 14px;font-size:15px;font-weight:800;
            }
            QLabel#seccionCuentas {
                color:#747970;font-size:11px;font-weight:800;padding:4px 2px 0 2px;
            }
            QLabel#notasCuenta {
                color:#4b5048;background:white;border:1px solid #dfe2dc;
                border-radius:8px;padding:9px 11px;font-weight:600;
            }
            QTableWidget {
                background:white;border:1px solid #dfe2dc;border-radius:8px;
                gridline-color:#e7e9e4;alternate-background-color:#f8f9f6;
                selection-background-color:#fff0ad;selection-color:#242722;
            }
            QHeaderView::section {
                background:#292d28;color:white;border:none;padding:8px;
                font-weight:700;
            }
        """)

        cabecera = QWidget()
        layout_cabecera = QHBoxLayout(cabecera)
        layout_cabecera.setContentsMargins(2, 0, 2, 0)
        titulo = QLabel("CUENTAS ACTIVAS")
        titulo.setObjectName("tituloCuentas")
        actualizacion = QLabel("Actualización automática  ·  5 s")
        actualizacion.setObjectName("actualizacionCuentas")
        layout_cabecera.addWidget(titulo)
        layout_cabecera.addStretch()
        layout_cabecera.addWidget(actualizacion)
        principal.addWidget(cabecera)

        self.resumen_general = QLabel()
        self.resumen_general.setObjectName("resumenCuentas")
        principal.addWidget(self.resumen_general)

        etiqueta_abiertas = QLabel("CUENTAS ABIERTAS")
        etiqueta_abiertas.setObjectName("seccionCuentas")
        principal.addWidget(etiqueta_abiertas)

        self.tabla = QTableWidget(0, 7)
        self.tabla.setHorizontalHeaderLabels([
            "Mesa / Barra", "Abierta", "Tiempo", "Mesero(s)",
            "Pedidos", "Cocina", "Total",
        ])
        self.tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla.setSelectionMode(QTableWidget.SingleSelection)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setShowGrid(False)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.verticalHeader().setDefaultSectionSize(38)
        self.tabla.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tabla.itemSelectionChanged.connect(self.mostrar_detalle)
        principal.addWidget(self.tabla)

        etiqueta_detalle = QLabel("DETALLE DE LA CUENTA SELECCIONADA")
        etiqueta_detalle.setObjectName("seccionCuentas")
        principal.addWidget(etiqueta_detalle)

        self.detalle = QTableWidget(0, 5)
        self.detalle.setHorizontalHeaderLabels([
            "Pedido", "Producto", "Cantidad", "Precio", "Importe"
        ])
        self.detalle.setEditTriggers(QTableWidget.NoEditTriggers)
        self.detalle.setAlternatingRowColors(True)
        self.detalle.setShowGrid(False)
        self.detalle.verticalHeader().setVisible(False)
        self.detalle.verticalHeader().setDefaultSectionSize(34)
        self.detalle.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.detalle.setMaximumHeight(220)
        principal.addWidget(self.detalle)

        self.notas = QLabel("Selecciona una cuenta para ver sus productos y notas.")
        self.notas.setWordWrap(True)
        self.notas.setObjectName("notasCuenta")
        principal.addWidget(self.notas)

        botones = QHBoxLayout()
        cargar = QPushButton("Cargar cuenta en caja")
        cargar.setMinimumHeight(48)
        cargar.setStyleSheet("""
            QPushButton {
                font-weight:800;background:#27ae60;color:white;border:none;
                border-radius:8px;padding:8px 16px;
            }
            QPushButton:hover { background:#219150; }
        """)
        cargar.clicked.connect(self.cargar)
        actualizar = QPushButton("Actualizar")
        actualizar.setMinimumHeight(48)
        actualizar.setStyleSheet(
            "font-weight:700;background:#f4f5f2;border:1px solid #d2d5ce;"
            "border-radius:8px;"
        )
        actualizar.clicked.connect(self.recargar)
        cerrar = QPushButton("Cerrar")
        cerrar.setMinimumHeight(48)
        cerrar.setStyleSheet(actualizar.styleSheet())
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
        elif cuentas:
            self.tabla.selectRow(0)
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
        comensales = obtener_comensales_mesa(mesa)
        resumen = " · ".join(
            f"C{c['numero']} {c['estado']} ${c['total']:.2f}"
            for c in comensales
        )
        self.notas.setText(
            ("Comensales: " + resumen + "\n" if resumen else "")
            + "Notas: " + (" | ".join(notas) if notas else "Sin notas")
        )

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
            if pedido[6] == "Pendiente":
                actualizar_estado_pedido_movil(pedido_id, "En caja")
        self.cuenta_cargada = (mesa, pedido_ids, detalles)
        self.accept()


class RecetasCostosDialog(PantallaDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recetas y costos - La Esquina Manager")
        self.resize(1100, 720)
        raiz = QVBoxLayout(self)
        titulo = QLabel("RECETAS Y COSTOS")
        titulo.setStyleSheet("font-size:26px;font-weight:800;")
        raiz.addWidget(titulo)
        nota = QLabel(
            "Registra cómo compras cada ingrediente y cuánto usa una porción. "
            "El costo incluye merma y otros costos opcionales."
        )
        nota.setWordWrap(True); raiz.addWidget(nota)
        tabs = QTabWidget(); raiz.addWidget(tabs, 1)

        # Ingredientes
        pagina_i = QWidget(); li = QVBoxLayout(pagina_i)
        self.tabla_ingredientes = QTableWidget(0, 8)
        self.tabla_ingredientes.setHorizontalHeaderLabels(
            ["ID", "Ingrediente", "Unidad", "Cantidad compra", "Costo compra",
             "Merma", "Costo por unidad", "Estado"]
        )
        self.tabla_ingredientes.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabla_ingredientes.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla_ingredientes.setEditTriggers(QTableWidget.NoEditTriggers)
        li.addWidget(self.tabla_ingredientes)
        bi = QHBoxLayout()
        for texto, funcion in (("Agregar ingrediente", self.agregar_ingrediente),
                               ("Editar costo / compra", self.editar_ingrediente),
                               ("Activar / Desactivar", self.estado_ingrediente)):
            boton = QPushButton(texto); boton.clicked.connect(funcion); bi.addWidget(boton)
        li.addLayout(bi); tabs.addTab(pagina_i, "Ingredientes y compras")

        # Preparaciones base: salsas, frijoles, aderezos, etc.
        pagina_p = QWidget(); lp = QVBoxLayout(pagina_p)
        fila_p = QHBoxLayout(); fila_p.addWidget(QLabel("Preparación:"))
        self.preparacion_combo = QComboBox(); fila_p.addWidget(self.preparacion_combo, 1)
        self.preparacion_combo.currentIndexChanged.connect(self.cargar_preparacion)
        nuevo_p = QPushButton("Nueva preparación"); nuevo_p.clicked.connect(self.nueva_preparacion); fila_p.addWidget(nuevo_p)
        editar_p = QPushButton("Editar rendimiento / costo"); editar_p.clicked.connect(self.editar_preparacion); fila_p.addWidget(editar_p)
        estado_p = QPushButton("Activar / Desactivar"); estado_p.clicked.connect(self.estado_preparacion); fila_p.addWidget(estado_p)
        lp.addLayout(fila_p)
        self.tabla_preparacion = QTableWidget(0, 5)
        self.tabla_preparacion.setHorizontalHeaderLabels(["ID", "Ingrediente", "Unidad", "Cantidad", "Costo"])
        self.tabla_preparacion.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabla_preparacion.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla_preparacion.setEditTriggers(QTableWidget.NoEditTriggers); lp.addWidget(self.tabla_preparacion)
        fp = QHBoxLayout(); fp.addWidget(QLabel("Ingrediente:"))
        self.ingrediente_preparacion = QComboBox(); fp.addWidget(self.ingrediente_preparacion, 1)
        fp.addWidget(QLabel("Cantidad:")); self.cantidad_preparacion = QDoubleSpinBox()
        self.cantidad_preparacion.setRange(.001, 10000000); self.cantidad_preparacion.setDecimals(3); fp.addWidget(self.cantidad_preparacion)
        api = QPushButton("Agregar / Actualizar"); api.clicked.connect(self.agregar_ingrediente_preparacion); fp.addWidget(api)
        qpi = QPushButton("Quitar seleccionado"); qpi.clicked.connect(self.quitar_ingrediente_preparacion); fp.addWidget(qpi)
        lp.addLayout(fp)
        self.resumen_preparacion = QLabel(); self.resumen_preparacion.setStyleSheet("font-size:16px;font-weight:bold;")
        lp.addWidget(self.resumen_preparacion); tabs.addTab(pagina_p, "Preparaciones base")

        # Receta por producto
        pagina_r = QWidget(); lr = QVBoxLayout(pagina_r)
        fila_producto = QHBoxLayout(); fila_producto.addWidget(QLabel("Producto:"))
        self.producto_receta = QComboBox(); fila_producto.addWidget(self.producto_receta, 1)
        self.producto_receta.currentIndexChanged.connect(self.cargar_receta)
        lr.addLayout(fila_producto)
        self.tabla_receta = QTableWidget(0, 5)
        self.tabla_receta.setHorizontalHeaderLabels(
            ["ID", "Ingrediente", "Unidad", "Cantidad usada", "Costo"]
        )
        self.tabla_receta.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabla_receta.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla_receta.setEditTriggers(QTableWidget.NoEditTriggers)
        lr.addWidget(self.tabla_receta)
        agregar = QHBoxLayout(); agregar.addWidget(QLabel("Ingrediente:"))
        self.ingrediente_receta = QComboBox(); agregar.addWidget(self.ingrediente_receta, 1)
        agregar.addWidget(QLabel("Cantidad usada:"))
        self.cantidad_receta = QDoubleSpinBox(); self.cantidad_receta.setRange(.001, 1000000)
        self.cantidad_receta.setDecimals(3); agregar.addWidget(self.cantidad_receta)
        ba = QPushButton("Agregar / Actualizar"); ba.clicked.connect(self.agregar_componente); agregar.addWidget(ba)
        br = QPushButton("Quitar seleccionado"); br.clicked.connect(self.quitar_componente); agregar.addWidget(br)
        lr.addLayout(agregar)
        etiqueta_prep = QLabel("PREPARACIONES BASE USADAS EN EL PLATILLO")
        etiqueta_prep.setStyleSheet("font-weight:bold;"); lr.addWidget(etiqueta_prep)
        self.tabla_receta_preparaciones = QTableWidget(0, 5)
        self.tabla_receta_preparaciones.setHorizontalHeaderLabels(
            ["ID", "Preparación", "Unidad", "Cantidad usada", "Costo"])
        self.tabla_receta_preparaciones.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabla_receta_preparaciones.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla_receta_preparaciones.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_receta_preparaciones.setMaximumHeight(150); lr.addWidget(self.tabla_receta_preparaciones)
        frp = QHBoxLayout(); frp.addWidget(QLabel("Preparación:"))
        self.preparacion_receta = QComboBox(); frp.addWidget(self.preparacion_receta, 1)
        frp.addWidget(QLabel("Cantidad usada:")); self.cantidad_preparacion_receta = QDoubleSpinBox()
        self.cantidad_preparacion_receta.setRange(.001, 1000000); self.cantidad_preparacion_receta.setDecimals(3)
        frp.addWidget(self.cantidad_preparacion_receta)
        apr = QPushButton("Agregar / Actualizar"); apr.clicked.connect(self.agregar_preparacion_receta); frp.addWidget(apr)
        qpr = QPushButton("Quitar preparación"); qpr.clicked.connect(self.quitar_preparacion_receta); frp.addWidget(qpr)
        lr.addLayout(frp)
        extras = QHBoxLayout(); extras.addWidget(QLabel("Otros costos por porción: $"))
        self.costo_extra = QDoubleSpinBox(); self.costo_extra.setRange(0, 100000); self.costo_extra.setDecimals(2)
        extras.addWidget(self.costo_extra)
        be = QPushButton("Guardar otros costos"); be.clicked.connect(self.guardar_extra); extras.addWidget(be)
        extras.addStretch(); self.resumen_receta = QLabel(); self.resumen_receta.setStyleSheet("font-size:16px;font-weight:bold;")
        extras.addWidget(self.resumen_receta); lr.addLayout(extras)
        tabs.addTab(pagina_r, "Receta por platillo")

        # Resumen general
        pagina_c = QWidget(); lc = QVBoxLayout(pagina_c)
        self.tabla_costos = QTableWidget(0, 6)
        self.tabla_costos.setHorizontalHeaderLabels(
            ["ID", "Producto", "Precio", "Costo", "Ganancia bruta", "% costo"]
        )
        self.tabla_costos.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabla_costos.setEditTriggers(QTableWidget.NoEditTriggers); lc.addWidget(self.tabla_costos)
        actualizar = QPushButton("Actualizar resumen"); actualizar.clicked.connect(self.cargar_costos); lc.addWidget(actualizar)
        tabs.addTab(pagina_c, "Resumen de costos")
        cerrar = QPushButton("Cerrar"); cerrar.clicked.connect(self.accept); raiz.addWidget(cerrar)
        self.ingredientes = []; self.productos_receta = []; self.preparaciones = []
        self.recargar_todo()

    def recargar_todo(self):
        self.ingredientes = obtener_ingredientes(False)
        self.tabla_ingredientes.setRowCount(len(self.ingredientes))
        for f, i in enumerate(self.ingredientes):
            vals = (i["id"], i["nombre"], i["unidad"], i["cantidad_compra"],
                    f"${i['costo_compra']:.2f}", f"{i['merma_pct']:.1f}%",
                    f"${i['costo_unitario']:.4f}", "Activo" if i["activo"] else "Inactivo")
            for col, val in enumerate(vals): self.tabla_ingredientes.setItem(f, col, QTableWidgetItem(str(val)))
        self.ingrediente_receta.clear()
        self.ingrediente_preparacion.clear()
        for i in self.ingredientes:
            if i["activo"]:
                self.ingrediente_receta.addItem(f"{i['nombre']} ({i['unidad']})", i["id"])
                self.ingrediente_preparacion.addItem(f"{i['nombre']} ({i['unidad']})", i["id"])
        prep_actual = self.preparacion_combo.currentData()
        self.preparaciones = obtener_preparaciones(False)
        self.preparacion_combo.blockSignals(True); self.preparacion_combo.clear()
        self.preparacion_receta.clear()
        for p in self.preparaciones:
            self.preparacion_combo.addItem(p["nombre"] + ("" if p["activo"] else " (Inactiva)"), p["id"])
            if p["activo"]: self.preparacion_receta.addItem(f"{p['nombre']} ({p['unidad']})", p["id"])
        if prep_actual:
            idx = self.preparacion_combo.findData(prep_actual)
            if idx >= 0: self.preparacion_combo.setCurrentIndex(idx)
        self.preparacion_combo.blockSignals(False)
        actual = self.producto_receta.currentData()
        self.productos_receta = obtener_productos(False); self.producto_receta.blockSignals(True); self.producto_receta.clear()
        for p in self.productos_receta: self.producto_receta.addItem(f"{p[1]} - ${p[2]:.2f}", p[0])
        if actual:
            idx = self.producto_receta.findData(actual)
            if idx >= 0: self.producto_receta.setCurrentIndex(idx)
        self.producto_receta.blockSignals(False); self.cargar_preparacion(); self.cargar_receta(); self.cargar_costos()

    def _ingrediente_actual(self):
        f = self.tabla_ingredientes.currentRow()
        return self.ingredientes[f] if 0 <= f < len(self.ingredientes) else None

    def _capturar_ingrediente(self, actual=None):
        nombre, ok = QInputDialog.getText(self, "Ingrediente", "Nombre:", text=actual["nombre"] if actual else "")
        if not ok: return None
        unidad, ok = QInputDialog.getItem(self, "Unidad", "Unidad base:", ["g", "ml", "pieza"],
                                          ["g", "ml", "pieza"].index(actual["unidad"]) if actual else 0, False)
        if not ok: return None
        cantidad, ok = QInputDialog.getDouble(self, "Compra", f"Cantidad comprada en {unidad}:",
                                               actual["cantidad_compra"] if actual else 1000, .001, 10000000, 3)
        if not ok: return None
        costo, ok = QInputDialog.getDouble(self, "Compra", "Costo total de esa compra: $",
                                            actual["costo_compra"] if actual else 0, 0, 1000000, 2)
        if not ok: return None
        merma, ok = QInputDialog.getDouble(self, "Merma", "Porcentaje de merma:",
                                            actual["merma_pct"] if actual else 0, 0, 99.99, 2)
        return (nombre, unidad, cantidad, costo, merma) if ok else None

    def agregar_ingrediente(self):
        datos = self._capturar_ingrediente()
        if datos:
            try: guardar_ingrediente(*datos); self.recargar_todo()
            except ValueError as e: QMessageBox.warning(self, "Ingrediente", str(e))

    def editar_ingrediente(self):
        i = self._ingrediente_actual()
        if not i: return
        datos = self._capturar_ingrediente(i)
        if datos:
            try: guardar_ingrediente(*datos, ingrediente_id=i["id"]); self.recargar_todo()
            except ValueError as e: QMessageBox.warning(self, "Ingrediente", str(e))

    def estado_ingrediente(self):
        i = self._ingrediente_actual()
        if i: establecer_ingrediente_activo(i["id"], not i["activo"]); self.recargar_todo()

    def _preparacion_actual(self):
        pid = self.preparacion_combo.currentData()
        return next((p for p in self.preparaciones if p["id"] == pid), None)

    def _capturar_preparacion(self, actual=None):
        nombre, ok = QInputDialog.getText(self, "Preparación base", "Nombre (ejemplo: Salsa roja):",
                                           text=actual["nombre"] if actual else "")
        if not ok: return None
        unidades = ["g", "ml", "pieza"]
        unidad, ok = QInputDialog.getItem(self, "Rendimiento", "Unidad del rendimiento:", unidades,
                                          unidades.index(actual["unidad"]) if actual else 1, False)
        if not ok: return None
        rendimiento, ok = QInputDialog.getDouble(self, "Rendimiento final",
            f"¿Cuántos {unidad} produce toda la preparación?",
            actual["rendimiento"] if actual else 1000, .001, 10000000, 3)
        if not ok: return None
        extra, ok = QInputDialog.getDouble(self, "Otros costos",
            "Gas, condimentos u otros costos de toda la preparación: $",
            actual["costo_extra"] if actual else 0, 0, 1000000, 2)
        return (nombre, unidad, rendimiento, extra) if ok else None

    def nueva_preparacion(self):
        datos = self._capturar_preparacion()
        if datos:
            try: guardar_preparacion(*datos); self.recargar_todo()
            except ValueError as e: QMessageBox.warning(self, "Preparación", str(e))

    def editar_preparacion(self):
        p = self._preparacion_actual()
        if not p: return
        datos = self._capturar_preparacion(p)
        if datos:
            try: guardar_preparacion(*datos, preparacion_id=p["id"]); self.recargar_todo()
            except ValueError as e: QMessageBox.warning(self, "Preparación", str(e))

    def estado_preparacion(self):
        p = self._preparacion_actual()
        if p: establecer_preparacion_activa(p["id"], not p["activo"]); self.recargar_todo()

    def cargar_preparacion(self):
        pid = self.preparacion_combo.currentData()
        if pid is None:
            self.tabla_preparacion.setRowCount(0); self.resumen_preparacion.setText("Crea una preparación base."); return
        p = obtener_preparacion(pid); componentes = p["componentes"]
        self.tabla_preparacion.setRowCount(len(componentes))
        for f, comp in enumerate(componentes):
            vals = (comp[0], comp[1], comp[2], comp[3], f"${comp[4]:.2f}")
            for col, val in enumerate(vals): self.tabla_preparacion.setItem(f, col, QTableWidgetItem(str(val)))
        self.resumen_preparacion.setText(
            f"Costo total: ${p['costo_total']:.2f}  |  Rendimiento: {p['rendimiento']:.3f} {p['unidad']}  |  "
            f"Costo por {p['unidad']}: ${p['costo_unitario']:.4f}")

    def agregar_ingrediente_preparacion(self):
        if self.preparacion_combo.currentData() and self.ingrediente_preparacion.currentData():
            guardar_ingrediente_preparacion(self.preparacion_combo.currentData(),
                self.ingrediente_preparacion.currentData(), self.cantidad_preparacion.value())
            self.recargar_todo()

    def quitar_ingrediente_preparacion(self):
        f = self.tabla_preparacion.currentRow()
        if f >= 0:
            eliminar_ingrediente_preparacion(self.preparacion_combo.currentData(),
                int(self.tabla_preparacion.item(f, 0).text())); self.recargar_todo()

    def cargar_receta(self):
        pid = self.producto_receta.currentData()
        if pid is None: return
        r = obtener_receta(pid); self.tabla_receta.setRowCount(len(r["componentes"]))
        for f, comp in enumerate(r["componentes"]):
            vals = (comp[0], comp[1], comp[2], comp[3], f"${comp[4]:.2f}")
            for col, val in enumerate(vals): self.tabla_receta.setItem(f, col, QTableWidgetItem(str(val)))
        self.tabla_receta_preparaciones.setRowCount(len(r["preparaciones"]))
        for f, comp in enumerate(r["preparaciones"]):
            vals = (comp[0], comp[1], comp[2], comp[3], f"${comp[4]:.2f}")
            for col, val in enumerate(vals): self.tabla_receta_preparaciones.setItem(f, col, QTableWidgetItem(str(val)))
        self.costo_extra.setValue(r["costo_extra"])
        precio = next((p[2] for p in self.productos_receta if p[0] == pid), 0)
        pct = r["costo_total"] / precio * 100 if precio else 0
        self.resumen_receta.setText(f"Costo: ${r['costo_total']:.2f}  |  Margen: ${precio-r['costo_total']:.2f}  |  Costo: {pct:.1f}%")

    def agregar_componente(self):
        if self.producto_receta.currentData() and self.ingrediente_receta.currentData():
            guardar_componente_receta(self.producto_receta.currentData(), self.ingrediente_receta.currentData(), self.cantidad_receta.value()); self.cargar_receta(); self.cargar_costos()

    def quitar_componente(self):
        f = self.tabla_receta.currentRow()
        if f >= 0:
            eliminar_componente_receta(self.producto_receta.currentData(), int(self.tabla_receta.item(f, 0).text())); self.cargar_receta(); self.cargar_costos()

    def guardar_extra(self):
        guardar_costo_extra_receta(self.producto_receta.currentData(), self.costo_extra.value()); self.cargar_receta(); self.cargar_costos()

    def agregar_preparacion_receta(self):
        if self.producto_receta.currentData() and self.preparacion_receta.currentData():
            guardar_preparacion_receta(self.producto_receta.currentData(),
                self.preparacion_receta.currentData(), self.cantidad_preparacion_receta.value())
            self.cargar_receta(); self.cargar_costos()

    def quitar_preparacion_receta(self):
        f = self.tabla_receta_preparaciones.currentRow()
        if f >= 0:
            eliminar_preparacion_receta(self.producto_receta.currentData(),
                int(self.tabla_receta_preparaciones.item(f, 0).text()))
            self.cargar_receta(); self.cargar_costos()

    def cargar_costos(self):
        filas = obtener_costos_productos(); self.tabla_costos.setRowCount(len(filas))
        for f, x in enumerate(filas):
            vals = (x[0], x[1], f"${x[2]:.2f}", f"${x[3]:.2f}", f"${x[4]:.2f}", f"{x[5]:.1f}%")
            for col, val in enumerate(vals): self.tabla_costos.setItem(f, col, QTableWidgetItem(str(val)))


class ClientesDialog(PantallaDialog):
    def __init__(self, seleccionar=False, parent=None):
        super().__init__(parent)
        self.seleccionar = seleccionar
        self.cliente_seleccionado = None
        self.setWindowTitle("Club La Esquina - Clientes")
        self.resize(1050, 680)
        layout = QVBoxLayout(self)
        titulo = QLabel("CLUB LA ESQUINA")
        titulo.setStyleSheet("font-size:24px;font-weight:bold;")
        layout.addWidget(titulo)
        acceso = QHBoxLayout()
        self.qr = QLabel()
        self.qr.setFixedSize(150, 150)
        self.qr.setAlignment(Qt.AlignCenter)
        try:
            imagen = qrcode.make(club_url())
            memoria = io.BytesIO(); imagen.save(memoria, format="PNG")
            pixmap = QPixmap(); pixmap.loadFromData(memoria.getvalue(), "PNG")
            self.qr.setPixmap(pixmap.scaled(145, 145, Qt.KeepAspectRatio,
                                            Qt.SmoothTransformation))
        except Exception:
            self.qr.setText("QR no disponible")
        acceso.addWidget(self.qr)
        texto = QLabel(
            f"REGISTRO DESDE EL CELULAR\n\n{club_url()}\n\n"
            "El celular debe estar conectado al mismo Wi-Fi que esta computadora.\n"
            "Regla actual: 1 punto por cada $10 de compra.\n"
            "Cada punto acumulado vale $0.50 para pagar."
        )
        texto.setTextInteractionFlags(Qt.TextSelectableByMouse)
        texto.setWordWrap(True)
        acceso.addWidget(texto, 1)
        layout.addLayout(acceso)
        self.buscar = QLineEdit()
        self.buscar.setPlaceholderText("Buscar por nombre o celular")
        self.buscar.textChanged.connect(self.cargar)
        layout.addWidget(self.buscar)
        self.tabla = QTableWidget(0, 8)
        self.tabla.setHorizontalHeaderLabels(
            ["ID", "Nombre", "Celular", "Puntos", "Saldo", "Visitas", "Compras", "Promociones"]
        )
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.doubleClicked.connect(self.aceptar_cliente)
        layout.addWidget(self.tabla, 1)
        botones = QHBoxLayout()
        agregar = QPushButton("Registrar cliente manualmente")
        agregar.clicked.connect(self.agregar)
        botones.addWidget(agregar)
        desactivar = QPushButton("Activar / Desactivar")
        desactivar.clicked.connect(self.cambiar_estado)
        botones.addWidget(desactivar)
        if seleccionar:
            omitir = QPushButton("Continuar sin cliente")
            omitir.clicked.connect(self.reject)
            botones.addWidget(omitir)
            elegir = QPushButton("USAR CLIENTE SELECCIONADO")
            elegir.clicked.connect(self.aceptar_cliente)
            botones.addWidget(elegir)
        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(self.reject)
        botones.addWidget(cerrar)
        layout.addLayout(botones)
        self.clientes = []
        self.cargar()

    def cargar(self):
        self.clientes = obtener_clientes(self.buscar.text(), solo_activos=self.seleccionar)
        self.tabla.setRowCount(len(self.clientes))
        for fila, c in enumerate(self.clientes):
            valores = (c["id"], c["nombre"], c["telefono"], c["puntos"],
                       f"${c['puntos'] * 0.50:.2f}", c["visitas"],
                       f"${c['total_compras']:.2f}",
                       "Sí" if c["acepta_promociones"] else "No")
            for columna, valor in enumerate(valores):
                self.tabla.setItem(fila, columna, QTableWidgetItem(str(valor)))
            if not c["activo"]:
                for columna in range(self.tabla.columnCount()):
                    self.tabla.item(fila, columna).setForeground(QColor("#999999"))

    def agregar(self):
        nombre, ok = QInputDialog.getText(self, "Cliente", "Nombre:")
        if not ok: return
        telefono, ok = QInputDialog.getText(self, "Cliente", "Celular (10 dígitos):")
        if not ok: return
        try:
            registrar_cliente(nombre, telefono)
            self.cargar()
        except ValueError as error:
            QMessageBox.warning(self, "Datos incorrectos", str(error))

    def _actual(self):
        fila = self.tabla.currentRow()
        return self.clientes[fila] if 0 <= fila < len(self.clientes) else None

    def aceptar_cliente(self, *_args):
        cliente = self._actual()
        if cliente is None:
            QMessageBox.warning(self, "Cliente", "Selecciona un cliente.")
            return
        self.cliente_seleccionado = cliente
        self.accept()

    def cambiar_estado(self):
        cliente = self._actual()
        if cliente is None: return
        establecer_cliente_activo(cliente["id"], not cliente["activo"])
        self.cargar()


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
        self.configuracion_negocio = cargar_configuracion()
        registrar_auditoria(
            self.empleado_actual, "Iniciar sesión", "Sistema", None,
            self.empleado_actual["rol"],
        )

        self.setWindowTitle(
            f"{self.configuracion_negocio['nombre_negocio']} - {self.empleado_actual['nombre']} "
            f"({self.empleado_actual['rol']})"
        )
        self.resize(1200, 750)

        self.carrito = []
        self.total = 0.0
        self.notas_rapidas = []
        self.renglones_pedido = []
        self.pedidos_movil_actuales = []
        self.mesa_cuenta_actual = None
        self.destino_para_llevar = None
        self.carrito_cuenta_original = []
        self.carrito_restante_division = []
        self.cuentas_divididas_pendientes = []
        self.numero_cuenta_division_actual = 0
        self.total_cuentas_division = 0
        self.comensal_cuenta_actual = None
        self.servidor_movil_url = None
        self.servidor_movil_error = None
        self.filtro_categoria = "Todos"
        self.texto_busqueda_producto = ""

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
        nombre_negocio = str(self.configuracion_negocio.get("nombre_negocio", "LA ESQUINA"))
        subtitulo_negocio = str(self.configuracion_negocio.get("subtitulo_negocio", "PUNTO DE VENTA"))
        color_principal = str(self.configuracion_negocio.get("color_principal", "#d8ad25"))
        color_secundario = str(self.configuracion_negocio.get("color_secundario", "#101119"))
        principal = QWidget()
        self.setCentralWidget(principal)

        layout_raiz = QVBoxLayout(principal)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        layout_raiz.setSpacing(0)

        encabezado = QWidget()
        encabezado.setObjectName("encabezadoPrincipal")
        encabezado.setFixedHeight(72)
        encabezado.setStyleSheet("""
            QWidget#encabezadoPrincipal {
                background-color: __COLOR_SECUNDARIO__;
                border-bottom: 3px solid __COLOR_PRINCIPAL__;
            }
            QLabel#marcaPrincipal {
                color: white;
                font-size: 24px;
                font-weight: 800;
            }
            QLabel#subtituloPrincipal {
                color: #c9ad58;
                font-size: 12px;
            }
            QLabel#sesionPrincipal {
                color: #f4ecd4;
                background-color: #20222d;
                border: 1px solid #3a3d4b;
                border-radius: 15px;
                padding: 7px 13px;
                font-weight: 600;
            }
            QPushButton#botonAdministracion {
                color: #171717;
                background-color: __COLOR_PRINCIPAL__;
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 13px;
                font-weight: 800;
            }
            QPushButton#botonAdministracion:hover {
                background-color: #edc54a;
            }
            QPushButton#botonAdministracion::menu-indicator {
                width: 0px;
            }
            QPushButton#navPrincipal {
                color:#ded9cc;background:#1d1f29;border:1px solid #303340;
                border-radius:9px;padding:8px 11px;font-size:12px;font-weight:800;
            }
            QPushButton#navPrincipal:hover {
                color:#171717;background:__COLOR_PRINCIPAL__;border-color:#edc54a;
            }
            QMenu {
                color:#f5f1e6;
                background-color: #20222d;
                border: 1px solid #454858;
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item {
                padding: 9px 28px 9px 12px;
                border-radius: 5px;
            }
            QMenu::item:selected { color:#171717;background-color:__COLOR_PRINCIPAL__; }
            QMenu::item:disabled { color: #a8aaa7; }
        """.replace("__COLOR_PRINCIPAL__", color_principal)
           .replace("__COLOR_SECUNDARIO__", color_secundario))
        layout_encabezado = QHBoxLayout(encabezado)
        layout_encabezado.setContentsMargins(18, 7, 18, 7)

        iniciales = "".join(palabra[0] for palabra in nombre_negocio.split() if palabra)[:2].upper() or "MN"
        logo = QLabel(iniciales)
        logo.setObjectName("monogramaPrincipal")
        logo.setFixedSize(52, 52)
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet(f"""
            QLabel#monogramaPrincipal {{
                color:{color_principal};background:#171821;border:2px solid {color_principal};
                border-radius:26px;font-size:18px;font-weight:900;
            }}
        """)
        ruta_logo = str(self.configuracion_negocio.get("logo_negocio", ""))
        if ruta_logo and Path(ruta_logo).is_file():
            pixmap_logo = QPixmap(ruta_logo)
            if not pixmap_logo.isNull():
                logo.setText("")
                logo.setPixmap(pixmap_logo.scaled(46, 46, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        bloque_marca = QWidget()
        layout_marca = QVBoxLayout(bloque_marca)
        layout_marca.setContentsMargins(0, 0, 0, 0)
        layout_marca.setSpacing(1)
        marca = QLabel(nombre_negocio.upper())
        marca.setObjectName("marcaPrincipal")
        subtitulo = QLabel(subtitulo_negocio.upper())
        subtitulo.setObjectName("subtituloPrincipal")
        layout_marca.addWidget(marca)
        layout_marca.addWidget(subtitulo)

        sesion = QLabel(
            f"{self.empleado_actual['nombre']}  ·  "
            f"{self.empleado_actual['rol']}"
        )
        sesion.setObjectName("sesionPrincipal")

        navegacion = QWidget()
        layout_navegacion = QHBoxLayout(navegacion)
        layout_navegacion.setContentsMargins(0, 0, 0, 0)
        layout_navegacion.setSpacing(6)
        boton_inicio = QPushButton("▦  INICIO")
        boton_mesas_nav = QPushButton("♨  MESAS")
        boton_pedidos_nav = QPushButton("▣  PEDIDOS")
        boton_cuentas_nav = QPushButton("▤  CUENTAS")
        boton_llevar_nav = QPushButton("▱  PARA LLEVAR")
        boton_cobro_nav = QPushButton("⚡  COBRO")
        for boton_nav in (
            boton_inicio, boton_mesas_nav, boton_pedidos_nav,
            boton_cuentas_nav, boton_llevar_nav, boton_cobro_nav,
        ):
            boton_nav.setObjectName("navPrincipal")
            boton_nav.setMinimumHeight(38)
            layout_navegacion.addWidget(boton_nav)
        boton_inicio.clicked.connect(lambda: self.scroll_productos.verticalScrollBar().setValue(0))
        boton_mesas_nav.clicked.connect(self.abrir_mesas)
        boton_pedidos_nav.clicked.connect(self.abrir_pedidos_movil)
        boton_cuentas_nav.clicked.connect(self.abrir_cuentas_activas)
        boton_llevar_nav.clicked.connect(self.iniciar_pedido_para_llevar)
        boton_cobro_nav.clicked.connect(self.cobrar)

        self.boton_administracion = QPushButton("ADMINISTRACIÓN  ▾")
        self.boton_administracion.setObjectName("botonAdministracion")
        self.boton_administracion.setMinimumHeight(42)
        menu_administracion = QMenu(self.boton_administracion)
        accion_corte = menu_administracion.addAction("Corte de caja")
        accion_corte.triggered.connect(self.mostrar_corte_caja)
        accion_analisis = menu_administracion.addAction("Análisis de ventas")
        accion_analisis.triggered.connect(self.abrir_analisis_ventas)
        accion_dashboard = menu_administracion.addAction("Dashboard y gráficas")
        accion_dashboard.triggered.connect(self.abrir_dashboard)
        accion_gastos = menu_administracion.addAction("Gastos")
        accion_gastos.triggered.connect(self.abrir_gastos)
        accion_clientes = menu_administracion.addAction("Club La Esquina / Clientes")
        accion_clientes.triggered.connect(self.abrir_clientes)
        menu_administracion.addSeparator()
        accion_productos = menu_administracion.addAction("Productos y precios")
        accion_productos.triggered.connect(self.abrir_productos)
        accion_recetas = menu_administracion.addAction("Recetas y costos")
        accion_recetas.triggered.connect(self.abrir_recetas_costos)
        accion_config = menu_administracion.addAction("Configuración del negocio")
        accion_config.triggered.connect(self.abrir_configuracion)
        accion_empleados = menu_administracion.addAction("Empleados y usuarios")
        accion_empleados.triggered.connect(self.abrir_empleados)
        self.boton_administracion.setMenu(menu_administracion)

        rol = self.empleado_actual["rol"]
        es_admin = rol == "Administrador"
        es_caja = rol in ("Administrador", "Caja")
        accion_corte.setEnabled(es_caja)
        accion_analisis.setEnabled(es_admin)
        accion_dashboard.setEnabled(es_admin)
        accion_gastos.setEnabled(es_admin)
        accion_clientes.setEnabled(es_caja)
        accion_productos.setEnabled(es_admin)
        accion_recetas.setEnabled(es_admin)
        accion_config.setEnabled(es_admin)
        accion_empleados.setEnabled(es_admin)
        self.boton_administracion.setEnabled(es_admin or es_caja)
        boton_cobro_nav.setEnabled(es_caja)
        boton_mesas_nav.setEnabled(rol != "Cocina")
        boton_cuentas_nav.setEnabled(rol != "Cocina")
        boton_llevar_nav.setEnabled(rol in ("Administrador", "Caja", "Mesero"))

        layout_encabezado.addWidget(logo)
        layout_encabezado.addSpacing(8)
        layout_encabezado.addWidget(bloque_marca)
        layout_encabezado.addSpacing(24)
        layout_encabezado.addWidget(navegacion)
        layout_encabezado.addStretch()
        layout_encabezado.addWidget(sesion)
        layout_encabezado.addSpacing(10)
        layout_encabezado.addWidget(self.boton_administracion)
        layout_raiz.addWidget(encabezado)

        contenido_principal = QWidget()
        contenido_principal.setObjectName("contenidoPrincipal")
        contenido_principal.setStyleSheet("""
            QWidget#contenidoPrincipal { background-color: #101119; }
        """)
        layout_principal = QHBoxLayout(contenido_principal)
        layout_principal.setContentsMargins(12, 12, 12, 12)
        layout_principal.setSpacing(12)
        layout_raiz.addWidget(contenido_principal, 1)

        panel_productos = QWidget()
        panel_productos.setObjectName("panelProductos")
        panel_productos.setStyleSheet("""
            QWidget#panelProductos {
                background-color: #181a24;
                border: 1px solid #303342;
                border-radius: 12px;
            }
            QLabel#tituloProductos {
                color: #f5f1e6;
                font-size: 21px;
                font-weight: 800;
            }
            QLabel#resumenProductos {
                color: #d9bd69;
                background-color: #242631;
                border-radius: 12px;
                padding: 5px 10px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#filtroCategoria {
                min-height:38px;background:#242631;color:#e8e4da;
                border:1px solid #383b49;border-radius:8px;padding:0 13px;
                font-size:12px;font-weight:800;
            }
            QPushButton#filtroCategoria:checked {
                background:#d8ad25;color:#151515;border-color:#edc54a;
            }
            QLineEdit#busquedaProductos {
                min-height:40px;background:#242631;color:#f5f1e6;
                border:1px solid #3b3e4d;border-radius:8px;padding:0 12px;font-size:14px;
            }
            QLineEdit#busquedaProductos:focus { border:2px solid #d8ad25; }
        """)
        layout_productos = QVBoxLayout(panel_productos)
        layout_productos.setContentsMargins(16, 14, 14, 14)
        layout_productos.setSpacing(10)

        barra_productos = QWidget()
        layout_barra_productos = QHBoxLayout(barra_productos)
        layout_barra_productos.setContentsMargins(2, 0, 4, 0)
        titulo_productos = QLabel("MENÚ DE PRODUCTOS")
        titulo_productos.setObjectName("tituloProductos")
        categorias = {
            categoria for _id, _nombre, _precio, categoria, _activo, _orden
            in self.productos
        }
        resumen_productos = QLabel(
            f"{len(self.productos)} productos  ·  {len(categorias)} categorías"
        )
        resumen_productos.setObjectName("resumenProductos")
        layout_barra_productos.addWidget(titulo_productos)
        layout_barra_productos.addStretch()
        layout_barra_productos.addWidget(resumen_productos)
        layout_productos.addWidget(barra_productos)

        filtros = QHBoxLayout()
        filtros.setSpacing(7)
        self.botones_categoria = {}
        categorias_ordenadas = ["Todos"] + sorted(
            categoria or "General" for categoria in categorias
        )
        if self.filtro_categoria not in categorias_ordenadas:
            self.filtro_categoria = "Todos"
        for categoria in categorias_ordenadas:
            boton_categoria = QPushButton(categoria.upper())
            boton_categoria.setObjectName("filtroCategoria")
            boton_categoria.setCheckable(True)
            boton_categoria.setChecked(categoria == self.filtro_categoria)
            boton_categoria.clicked.connect(
                lambda checked=False, c=categoria: self.filtrar_categoria(c)
            )
            self.botones_categoria[categoria] = boton_categoria
            filtros.addWidget(boton_categoria)
        filtros.addStretch()
        self.busqueda_productos = QLineEdit()
        self.busqueda_productos.setObjectName("busquedaProductos")
        self.busqueda_productos.setPlaceholderText("Buscar producto…")
        self.busqueda_productos.setClearButtonEnabled(True)
        self.busqueda_productos.setText(self.texto_busqueda_producto)
        self.busqueda_productos.setMinimumWidth(210)
        self.busqueda_productos.textChanged.connect(self.buscar_productos)
        filtros.addWidget(self.busqueda_productos)
        layout_productos.addLayout(filtros)

        # Area desplazable: permite ver todos los productos incluso en
        # pantallas pequenas o cuando el menu crezca.
        self.scroll_productos = QScrollArea()
        self.scroll_productos.setWidgetResizable(True)
        self.scroll_productos.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )
        self.scroll_productos.setFrameShape(QScrollArea.NoFrame)
        self.scroll_productos.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: #20222d;
                width: 9px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #d8ad25;
                min-height: 28px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { height: 0px; }
        """)

        self.contenido_productos = QWidget()
        self.contenido_productos.setStyleSheet("background: transparent;")
        self.grid_productos = QGridLayout(self.contenido_productos)
        self.grid_productos.setHorizontalSpacing(2)
        self.grid_productos.setVerticalSpacing(8)
        self.grid_productos.setContentsMargins(0, 4, 2, 4)
        self.scroll_productos.setWidget(self.contenido_productos)
        layout_productos.addWidget(self.scroll_productos)
        self.actualizar_grid_productos()

        panel_pedido = QWidget()
        panel_pedido.setObjectName("panelPedido")
        panel_pedido.setMinimumWidth(390)
        panel_pedido.setStyleSheet("""
            QWidget#panelPedido {
                background-color: #1b1d27;
                border: 1px solid #343746;
                border-radius: 12px;
            }
            QLabel#tituloPedido {
                color: #f5f1e6;
                font-size: 20px;
                font-weight: 800;
            }
            QLabel#resumenPedido {
                color: #d7bd6d;
                background-color: #292b37;
                border-radius: 12px;
                padding: 5px 10px;
                font-size: 12px;
                font-weight: 600;
            }
            QListWidget#listaPedido {
                color:#f4efe2;background-color: #252735;
                border: 1px solid #3b3e4d;
                border-radius: 9px;
                padding: 5px;
                outline: none;
            }
            QListWidget#listaPedido::item {
                border-bottom: 1px solid #3a3d4b;
                padding: 9px 7px;
            }
            QListWidget#listaPedido::item:selected {
                color: #171717;
                background-color: #d8ad25;
                border-radius: 5px;
            }
            QLabel#totalPedido {
                color: #171717;
                background-color: #d8ad25;
                border-radius: 9px;
                padding: 13px 15px;
                font-size: 25px;
                font-weight: 800;
            }
        """)
        layout_pedido = QVBoxLayout(panel_pedido)
        layout_pedido.setContentsMargins(14, 14, 14, 14)
        layout_pedido.setSpacing(8)

        barra_pedido = QWidget()
        layout_barra_pedido = QHBoxLayout(barra_pedido)
        layout_barra_pedido.setContentsMargins(2, 0, 2, 0)
        titulo_pedido = QLabel("PEDIDO ACTUAL")
        titulo_pedido.setObjectName("tituloPedido")
        self.label_resumen_pedido = QLabel("0 artículos")
        self.label_resumen_pedido.setObjectName("resumenPedido")
        layout_barra_pedido.addWidget(titulo_pedido)
        layout_barra_pedido.addStretch()
        layout_barra_pedido.addWidget(self.label_resumen_pedido)

        self.lista_pedido = QListWidget()
        self.lista_pedido.setObjectName("listaPedido")
        self.lista_pedido.setStyleSheet("font-size: 15px;")

        self.aviso_cuenta_activa = QLabel()
        self.aviso_cuenta_activa.setWordWrap(True)
        self.aviso_cuenta_activa.setStyleSheet("""
            color:#165b78;background:#dff2fb;border:1px solid #acd8ea;
            border-radius:8px;padding:9px 11px;font-weight:700;
        """)
        self.aviso_cuenta_activa.hide()

        self.label_total = QLabel("TOTAL: $0.00")
        self.label_total.setObjectName("totalPedido")
        self.label_total.setAlignment(Qt.AlignRight)

        boton_quitar = QPushButton("Quitar producto")
        boton_quitar.setObjectName("accionSecundaria")
        boton_quitar.setMinimumHeight(35)
        boton_quitar.setStyleSheet("""
            QPushButton#accionSecundaria {
                color: #4f554d;
                background-color: #f4f5f2;
                border: 1px solid #d6d9d2;
                border-radius: 7px;
                font-weight: 600;
            }
            QPushButton#accionSecundaria:hover { background-color: #e9ebe6; }
        """)
        boton_quitar.clicked.connect(self.quitar_producto)

        controles_cantidad = QWidget()
        layout_cantidad = QHBoxLayout(controles_cantidad)
        layout_cantidad.setContentsMargins(0, 0, 0, 0)
        boton_menos = QPushButton("− 1")
        boton_menos.setMinimumHeight(35)
        boton_menos.setStyleSheet("font-size:18px;font-weight:bold;border-radius:7px;")
        boton_menos.clicked.connect(self.quitar_producto)
        boton_mas = QPushButton("+ 1")
        boton_mas.setMinimumHeight(35)
        boton_mas.setStyleSheet("font-size:18px;font-weight:bold;border-radius:7px;")
        boton_mas.clicked.connect(self.aumentar_producto)
        layout_cantidad.addWidget(boton_menos)
        layout_cantidad.addWidget(boton_mas)

        self.boton_notas = QPushButton("Notas rápidas / Modificadores")
        self.boton_notas.setMinimumHeight(35)
        self.boton_notas.setStyleSheet(
            "font-weight:600;background:#fff5ce;border:1px solid #ead585;"
            "border-radius:7px;"
        )
        self.boton_notas.clicked.connect(self.agregar_nota_rapida)
        self.actualizar_boton_notas()

        boton_cancelar = QPushButton("Cancelar pedido")
        boton_cancelar.setMinimumHeight(35)
        boton_cancelar.setStyleSheet(
            "color:#9b2f2f;background:#fff5f5;border:1px solid #efcccc;"
            "border-radius:7px;font-weight:600;"
        )
        boton_cancelar.clicked.connect(self.cancelar_pedido)

        boton_ventas = QPushButton("Ventas del día")
        boton_ventas.setMinimumHeight(35)
        boton_ventas.setStyleSheet("""
            QPushButton {
                color:#454a43;background:#f4f5f2;border:1px solid #d6d9d2;
                border-radius:7px;font-weight:600;
            }
            QPushButton:hover { background:#e9ebe6; }
        """)
        boton_ventas.clicked.connect(self.mostrar_ventas_hoy)

        boton_historial = QPushButton("Historial / Reimprimir")
        boton_historial.setMinimumHeight(35)
        boton_historial.setStyleSheet(boton_ventas.styleSheet())
        boton_historial.clicked.connect(self.abrir_historial)

        self.boton_pedidos = QPushButton("Pedidos de meseros")
        self.boton_pedidos.setMinimumHeight(39)
        self.boton_pedidos.setStyleSheet("""
            QPushButton {
                font-size: 14px;
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
        boton_mesas.setMinimumHeight(37)
        boton_mesas.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                background-color: #6fcf97;
                border-radius: 6px;
            }
        """)
        boton_mesas.clicked.connect(self.abrir_mesas)

        boton_cuentas = QPushButton("Cuentas activas")
        boton_cuentas.setMinimumHeight(37)
        boton_cuentas.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                background-color: #f6b93b;
                border-radius: 6px;
            }
        """)
        boton_cuentas.clicked.connect(self.abrir_cuentas_activas)

        boton_cobrar = QPushButton("COBRAR")
        boton_cobrar.setFixedHeight(52)
        boton_cobrar.setStyleSheet("""
            QPushButton {
                font-size: 19px;
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
        boton_dividir.setFixedHeight(38)
        boton_dividir.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                background-color: #f6b93b;
                border-radius: 8px;
            }
        """)
        boton_dividir.clicked.connect(self.dividir_cuenta)

        self.boton_enviar_mesa = QPushButton("ENVIAR A MESA / COCINA")
        self.boton_enviar_mesa.setFixedHeight(44)
        self.boton_enviar_mesa.setStyleSheet("""
            QPushButton {
                font-size: 15px;
                font-weight: bold;
                background-color: #3498db;
                color: white;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        self.boton_enviar_mesa.clicked.connect(self.enviar_a_mesa_cocina)

        boton_imprimir_cuenta = QPushButton("IMPRIMIR CUENTA")
        boton_imprimir_cuenta.setFixedHeight(38)
        boton_imprimir_cuenta.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                background-color: #e6e6e6;
                border: 1px solid #999999;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #d5d5d5; }
        """)
        boton_imprimir_cuenta.clicked.connect(self.imprimir_cuenta_previa)

        boton_historial.setEnabled(es_caja)
        boton_cobrar.setEnabled(es_caja)
        boton_dividir.setEnabled(es_caja)
        self.boton_enviar_mesa.setEnabled(rol in ("Administrador", "Caja", "Mesero"))
        boton_imprimir_cuenta.setEnabled(rol != "Cocina")
        boton_mesas.setEnabled(rol != "Cocina")
        boton_cuentas.setEnabled(rol != "Cocina")

        scroll_menu = QScrollArea()
        scroll_menu.setWidgetResizable(True)
        scroll_menu.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_menu.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_menu.setFrameShape(QScrollArea.NoFrame)
        scroll_menu.setStyleSheet("""
            QScrollArea { border:none;background:transparent; }
            QScrollBar:vertical { background:#242631;width:8px; }
            QScrollBar::handle:vertical {
                background:#d8ad25;min-height:26px;border-radius:4px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { height:0px; }
        """)

        contenido_menu = QWidget()
        contenido_menu.setStyleSheet("background:transparent;")
        layout_menu = QVBoxLayout(contenido_menu)
        layout_menu.setContentsMargins(0, 0, 6, 0)
        layout_menu.setSpacing(7)

        def etiqueta_seccion(texto):
            etiqueta = QLabel(texto)
            etiqueta.setStyleSheet("""
                color:#d7bd6d;font-size:11px;font-weight:800;
                padding:4px 2px 1px 2px;
            """)
            return etiqueta

        fila_edicion = QWidget()
        layout_edicion = QHBoxLayout(fila_edicion)
        layout_edicion.setContentsMargins(0, 0, 0, 0)
        layout_edicion.setSpacing(6)
        layout_edicion.addWidget(boton_quitar)
        layout_edicion.addWidget(self.boton_notas)

        fila_consultas = QWidget()
        layout_consultas = QHBoxLayout(fila_consultas)
        layout_consultas.setContentsMargins(0, 0, 0, 0)
        layout_consultas.setSpacing(7)
        layout_consultas.addWidget(boton_ventas)
        layout_consultas.addWidget(boton_historial)

        fila_mesas = QWidget()
        layout_mesas = QHBoxLayout(fila_mesas)
        layout_mesas.setContentsMargins(0, 0, 0, 0)
        layout_mesas.setSpacing(7)
        layout_mesas.addWidget(boton_mesas)
        layout_mesas.addWidget(boton_cuentas)

        layout_menu.addWidget(etiqueta_seccion("EDITAR PEDIDO"))
        layout_menu.addWidget(controles_cantidad)
        layout_menu.addWidget(fila_edicion)
        layout_menu.addWidget(boton_cancelar)
        layout_menu.addWidget(etiqueta_seccion("OPERACIÓN DE MESAS"))
        layout_menu.addWidget(self.boton_pedidos)
        layout_menu.addWidget(fila_mesas)
        layout_menu.addWidget(etiqueta_seccion("CONSULTAS RÁPIDAS"))
        layout_menu.addWidget(fila_consultas)

        # Conserva la altura natural de los botones para que el area use
        # desplazamiento vertical en lugar de comprimirlos.
        contenido_menu.setMinimumHeight(layout_menu.sizeHint().height())

        scroll_menu.setWidget(contenido_menu)

        etiqueta_finalizar = QLabel("FINALIZAR PEDIDO")
        etiqueta_finalizar.setStyleSheet("""
            color:#d7bd6d;font-size:11px;font-weight:800;
            padding:3px 2px 0 2px;
        """)

        boton_mas_opciones = QPushButton("☰  HERRAMIENTAS DEL PEDIDO")
        boton_mas_opciones.setCheckable(True)
        boton_mas_opciones.setMinimumHeight(33)
        boton_mas_opciones.setStyleSheet("""
            QPushButton {
                color:#e8e2d3;background:#292b37;border:1px solid #414453;
                border-radius:7px;font-size:12px;font-weight:800;
            }
            QPushButton:checked {
                color:#171717;background:#d8ad25;border-color:#d8ad25;
            }
        """)
        scroll_menu.hide()

        def alternar_opciones(visible):
            scroll_menu.setVisible(visible)
            scroll_menu.setMinimumHeight(185 if visible else 0)
            scroll_menu.setMaximumHeight(220 if visible else 0)
            boton_mas_opciones.setText(
                "▲  OCULTAR HERRAMIENTAS" if visible
                else "☰  HERRAMIENTAS DEL PEDIDO"
            )

        boton_mas_opciones.toggled.connect(alternar_opciones)

        fila_documentos = QWidget()
        layout_documentos = QHBoxLayout(fila_documentos)
        layout_documentos.setContentsMargins(0, 0, 0, 0)
        layout_documentos.setSpacing(7)
        layout_documentos.addWidget(boton_imprimir_cuenta)
        layout_documentos.addWidget(boton_dividir)

        layout_pedido.addWidget(barra_pedido)
        layout_pedido.addWidget(self.aviso_cuenta_activa)
        layout_pedido.addWidget(self.lista_pedido)
        layout_pedido.addWidget(self.label_total)
        layout_pedido.addWidget(boton_mas_opciones)
        layout_pedido.addWidget(scroll_menu)
        layout_pedido.addWidget(etiqueta_finalizar)
        layout_pedido.addWidget(fila_documentos)
        layout_pedido.addWidget(self.boton_enviar_mesa)
        layout_pedido.addWidget(boton_cobrar)

        layout_principal.addWidget(panel_productos, 3)
        layout_principal.addWidget(panel_pedido, 1)
        self.actualizar_lista_pedido()
        self.actualizar_total()
        self.actualizar_contexto_cuenta()

    def filtrar_categoria(self, categoria):
        self.filtro_categoria = categoria
        for nombre, boton in self.botones_categoria.items():
            boton.setChecked(nombre == categoria)
        self.actualizar_grid_productos()

    def buscar_productos(self, texto):
        self.texto_busqueda_producto = texto.strip()
        self.actualizar_grid_productos()

    def actualizar_grid_productos(self):
        columnas = 6
        while self.grid_productos.count():
            item = self.grid_productos.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        consulta = self.texto_busqueda_producto.casefold()
        productos = [
            producto for producto in self.productos
            if (
                self.filtro_categoria == "Todos"
                or (producto[3] or "General") == self.filtro_categoria
            )
            and consulta in producto[1].casefold()
        ]
        imagenes_productos = obtener_imagenes_productos()
        if not productos:
            vacio = QLabel("No se encontraron productos con esos filtros.")
            vacio.setAlignment(Qt.AlignCenter)
            vacio.setStyleSheet(
                "color:#c9c5bb;background:#22242f;border:1px dashed #4a4d5c;"
                "border-radius:10px;padding:28px;font-size:14px;"
            )
            self.grid_productos.addWidget(vacio, 0, 0, 1, columnas)
            return

        for indice, producto in enumerate(productos):
            producto_id, nombre, precio, _categoria, _activo, _orden = producto
            boton = QToolButton()
            boton.setText(f"{nombre}\n${precio:.0f}")
            boton.setObjectName("tarjetaProducto")
            boton.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            boton.setMinimumSize(100, 142)
            boton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            boton.setCursor(Qt.PointingHandCursor)
            archivo_imagen = imagenes_productos.get(producto_id, "")
            ruta_imagen = PRODUCT_IMAGES_FOLDER / archivo_imagen
            if archivo_imagen and ruta_imagen.is_file():
                boton.setIcon(QIcon(str(ruta_imagen)))
                boton.setIconSize(QSize(122, 82))
            boton.setStyleSheet("""
                QToolButton#tarjetaProducto {
                    color:#f6f1e5;font-size:13px;font-weight:800;
                    background:#252735;border:1px solid #3a3d4c;
                    border-radius:9px;padding:5px;
                }
                QToolButton#tarjetaProducto:hover {
                    color:#fff;background:#303241;border:2px solid #d8ad25;
                }
                QToolButton#tarjetaProducto:pressed {
                    color:#171717;background:#d8ad25;
                }
                QToolButton#tarjetaProducto:disabled {
                    color:#777986;background:#20222b;border-color:#30323d;
                }
            """)
            boton.clicked.connect(
                lambda checked=False, n=nombre, p=precio:
                self.agregar_producto(n, p)
            )
            if self.empleado_actual["rol"] == "Cocina":
                boton.setEnabled(False)
            self.grid_productos.addWidget(
                boton, indice // columnas, indice % columnas
            )

        for columna in range(columnas):
            self.grid_productos.setColumnStretch(columna, 1)
        self.grid_productos.setRowStretch(
            (len(productos) + columnas - 1) // columnas, 1
        )

    def agregar_producto(self, nombre, precio):
        clave = (nombre, precio)
        self.carrito.append((nombre, precio))
        self.total += precio
        self.actualizar_lista_pedido(clave)
        self.actualizar_total()
        self.actualizar_contexto_cuenta()

    def actualizar_contexto_cuenta(self):
        if not hasattr(self, "aviso_cuenta_activa"):
            return
        if self.destino_para_llevar:
            self.aviso_cuenta_activa.setText(
                f"PEDIDO PARA LLEVAR  ·  {self.destino_para_llevar}\n"
                "Agrega los productos y envíalos a cocina. La cuenta quedará pendiente de cobro."
            )
            self.aviso_cuenta_activa.show()
            self.boton_enviar_mesa.setText("ENVIAR PEDIDO PARA LLEVAR")
            return
        if self.numero_cuenta_division_actual:
            self.aviso_cuenta_activa.setText(
                f"COBRANDO CUENTA {self.numero_cuenta_division_actual} "
                f"DE {self.total_cuentas_division}  ·  {self.mesa_cuenta_actual}\n"
                "Al terminar, la siguiente cuenta se cargará automáticamente."
            )
            self.aviso_cuenta_activa.show()
            self.boton_enviar_mesa.setText("CUENTA DIVIDIDA - NO ENVIAR A COCINA")
            return
        if self.comensal_cuenta_actual and self.mesa_cuenta_actual:
            nuevos = max(0, len(self.carrito) - len(self.carrito_cuenta_original))
            self.aviso_cuenta_activa.setText(
                f"{self.mesa_cuenta_actual}  ·  COMENSAL {self.comensal_cuenta_actual}\n"
                f"Cuenta individual seleccionada · {nuevos} producto(s) nuevo(s). "
                "Solo esta cuenta se cobrará."
            )
            self.aviso_cuenta_activa.show()
            self.boton_enviar_mesa.setText(
                f"AGREGAR A COMENSAL {self.comensal_cuenta_actual}"
            )
            return
        if self.mesa_cuenta_actual and self.pedidos_movil_actuales:
            nuevos = max(0, len(self.carrito) - len(self.carrito_cuenta_original))
            self.aviso_cuenta_activa.setText(
                f"AGREGANDO A {self.mesa_cuenta_actual}  ·  "
                f"{nuevos} producto(s) nuevo(s)\n"
                "Los productos anteriores se conservan; solo los nuevos se enviarán a cocina."
            )
            self.aviso_cuenta_activa.show()
            self.boton_enviar_mesa.setText("AGREGAR PRODUCTOS A LA CUENTA")
        else:
            self.aviso_cuenta_activa.hide()
            self.boton_enviar_mesa.setText("ENVIAR A MESA / COCINA")

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
        if hasattr(self, "label_resumen_pedido"):
            cantidad_articulos = len(self.carrito)
            texto_articulos = (
                "1 artículo" if cantidad_articulos == 1
                else f"{cantidad_articulos} artículos"
            )
            self.label_resumen_pedido.setText(texto_articulos)
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
        self.destino_para_llevar = None
        self.carrito_cuenta_original = []
        self.carrito_restante_division = []
        self.cuentas_divididas_pendientes = []
        self.numero_cuenta_division_actual = 0
        self.total_cuentas_division = 0
        self.comensal_cuenta_actual = None
        self.carrito.clear()
        self.notas_rapidas.clear()
        self.total = 0.0
        self.actualizar_lista_pedido()
        self.actualizar_boton_notas()
        self.actualizar_total()
        self.actualizar_contexto_cuenta()

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
        dialogo = DividirCuentaDialog(
            list(self.carrito), self, mesa=self.mesa_cuenta_actual
        )
        if dialogo.exec() != QDialog.Accepted or not dialogo.resultado:
            return
        cuentas = dialogo.resultado
        self.carrito = list(cuentas[0])
        self.cuentas_divididas_pendientes = [list(cuenta) for cuenta in cuentas[1:]]
        self.carrito_restante_division = [
            producto
            for cuenta in self.cuentas_divididas_pendientes
            for producto in cuenta
        ]
        self.numero_cuenta_division_actual = 1
        self.total_cuentas_division = len(cuentas)
        self.total = sum(precio for _nombre, precio in self.carrito)
        self.actualizar_lista_pedido()
        self.actualizar_total()
        self.actualizar_contexto_cuenta()
        QMessageBox.information(
            self, "Cuenta dividida",
            f"Se prepararon {len(cuentas)} cuentas.\n\n"
            f"Ahora se cobrará la Cuenta 1 por ${self.total:.2f}.\n"
            "Después de cada cobro se cargará automáticamente la siguiente."
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

        cliente = None
        identificar = QMessageBox.question(
            self, "Club La Esquina",
            "¿El cliente está registrado en Club La Esquina?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if identificar == QMessageBox.Yes:
            selector_cliente = ClientesDialog(seleccionar=True, parent=self)
            if selector_cliente.exec() == QDialog.Accepted:
                cliente = selector_cliente.cliente_seleccionado

        puntos_usados = 0
        valor_puntos = 0.0
        if cliente and cliente["puntos"] > 0:
            maximo_puntos = min(cliente["puntos"], int(self.total / 0.50))
            puntos_usados, ok = QInputDialog.getInt(
                self, "Pagar con puntos",
                f"{cliente['nombre']} tiene {cliente['puntos']} puntos.\n"
                f"Saldo disponible: ${cliente['puntos'] * 0.50:.2f}\n\n"
                "Cada punto vale $0.50.\n"
                "¿Cuántos puntos desea utilizar en esta compra?",
                value=0, minValue=0, maxValue=maximo_puntos, step=1,
            )
            if not ok:
                return
            valor_puntos = round(puntos_usados * 0.50, 2)

        restante_pago = round(self.total - valor_puntos, 2)
        if restante_pago > 0:
            dialogo_pago = PagoDialog(restante_pago, self)
            if dialogo_pago.exec() != QDialog.Accepted or not dialogo_pago.resultado:
                return
            pago = dialogo_pago.resultado
            if puntos_usados:
                pago["pagos"].append(("Puntos", valor_puntos))
                pago["metodo_db"] = "Mixto"
                pago["descripcion"] += (
                    f" + {puntos_usados} puntos (${valor_puntos:.2f})"
                )
        else:
            pago = {
                "metodo_db": "Puntos",
                "descripcion": f"{puntos_usados} puntos (${valor_puntos:.2f})",
                "pagos": [("Puntos", valor_puntos)],
                "recibido": None,
                "cambio": None,
            }
        metodo = pago["metodo_db"]
        metodo_ticket = pago["descripcion"]
        recibido = pago["recibido"]
        cambio = pago["cambio"]

        total_venta = self.total
        productos_ticket = list(self.carrito)

        # Si caja agregó algo al comensal seleccionado y cobra de inmediato,
        # se crea primero su comanda. Así el producto llega a cocina y también
        # queda ligado a la cuenta individual que se está pagando.
        if (self.comensal_cuenta_actual and self.mesa_cuenta_actual
                and self.pedidos_movil_actuales):
            originales = list(self.carrito_cuenta_original)
            nuevos = []
            for producto in self.carrito:
                if producto in originales:
                    originales.remove(producto)
                else:
                    nuevos.append(producto)
            if nuevos:
                pedido_nuevo, total_nuevo = crear_pedido_desde_pc(
                    self.mesa_cuenta_actual,
                    self.empleado_actual["nombre"],
                    nuevos,
                    "\n".join(self.notas_rapidas),
                    self.empleado_actual["id"],
                    self.comensal_cuenta_actual,
                )
                actualizar_estado_pedido_movil(pedido_nuevo, "En caja")
                self.pedidos_movil_actuales.append(pedido_nuevo)
                registrar_auditoria(
                    self.empleado_actual, "Enviar y cobrar", "Pedido",
                    pedido_nuevo,
                    f"{self.mesa_cuenta_actual} · Comensal "
                    f"{self.comensal_cuenta_actual} · ${total_nuevo:.2f}",
                )

        venta_id = guardar_venta(
            self.carrito,
            total_venta,
            metodo,
            personas,
            origen,
            self.empleado_actual["id"],
            pago["pagos"],
            cliente["id"] if cliente else None,
            puntos_usados,
        )
        registrar_auditoria(
            self.empleado_actual, "Cobrar", "Venta", venta_id,
            f"${total_venta:.2f} - {metodo_ticket}",
        )

        saldo_division = None
        if self.carrito_restante_division:
            saldo_division = crear_saldo_cuenta(
                self.mesa_cuenta_actual,
                self.empleado_actual,
                self.carrito_restante_division,
            )

        if (self.pedidos_movil_actuales and self.mesa_cuenta_actual
                and self.comensal_cuenta_actual):
            registrar_pago_comensal(
                self.mesa_cuenta_actual, self.comensal_cuenta_actual,
                venta_id, self.pedidos_movil_actuales,
            )
            self.pedidos_movil_actuales = []
        elif self.pedidos_movil_actuales:
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
                mesa=(
                    f"{self.mesa_cuenta_actual} · Comensal "
                    f"{self.comensal_cuenta_actual}"
                    if self.comensal_cuenta_actual else self.mesa_cuenta_actual
                ),
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

        if cliente:
            puntos_ganados = int(restante_pago // 10)
            saldo_final = cliente["puntos"] - puntos_usados + puntos_ganados
            mensaje += (
                f"\n\nClub La Esquina: {cliente['nombre']}\n"
                f"Puntos utilizados: {puntos_usados} (${valor_puntos:.2f})\n"
                f"Puntos ganados: {puntos_ganados}\n"
                f"Nuevo saldo: {saldo_final} puntos (${saldo_final * 0.50:.2f})"
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

        mesa_division = self.mesa_cuenta_actual
        cuentas_pendientes = [
            list(cuenta) for cuenta in self.cuentas_divididas_pendientes
        ]
        numero_siguiente = self.numero_cuenta_division_actual + 1
        total_cuentas = self.total_cuentas_division
        self.cancelar_pedido()

        if cuentas_pendientes and saldo_division:
            pedido_saldo_id, _total_saldo = saldo_division
            self.carrito = cuentas_pendientes[0]
            self.cuentas_divididas_pendientes = cuentas_pendientes[1:]
            self.carrito_restante_division = [
                producto
                for cuenta in self.cuentas_divididas_pendientes
                for producto in cuenta
            ]
            self.numero_cuenta_division_actual = numero_siguiente
            self.total_cuentas_division = total_cuentas
            self.mesa_cuenta_actual = mesa_division
            self.pedidos_movil_actuales = [pedido_saldo_id]
            self.carrito_cuenta_original = list(self.carrito)
            self.total = sum(precio for _nombre, precio in self.carrito)
            self.actualizar_lista_pedido()
            self.actualizar_total()
            self.actualizar_contexto_cuenta()
            QMessageBox.information(
                self, "Siguiente cuenta preparada",
                f"Cuenta {numero_siguiente} de {total_cuentas}\n"
                f"Total: ${self.total:.2f}"
            )

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

    def iniciar_pedido_para_llevar(self):
        """Prepara el carrito actual como pedido para recoger en mostrador."""
        if self.pedidos_movil_actuales or self.mesa_cuenta_actual:
            QMessageBox.information(
                self, "Cuenta ya cargada",
                "Termina o cancela la cuenta actual antes de iniciar otro pedido para llevar."
            )
            return
        cliente, ok = QInputDialog.getText(
            self, "Pedido para llevar",
            "Nombre del cliente o referencia del pedido:"
        )
        cliente = " ".join(cliente.strip().split()) if ok else ""
        if not ok:
            return
        if not cliente:
            QMessageBox.warning(
                self, "Falta la referencia",
                "Escribe el nombre del cliente para identificar el pedido."
            )
            return
        folio = datetime.now().strftime("%H%M")
        self.destino_para_llevar = f"Para llevar #{folio} · {cliente[:40]}"
        self.actualizar_contexto_cuenta()
        QMessageBox.information(
            self, "Pedido para llevar preparado",
            f"Pedido de {cliente}.\n\n"
            "Agrega los productos y presiona ENVIAR PEDIDO PARA LLEVAR."
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
        elif self.destino_para_llevar:
            mesa = self.destino_para_llevar
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
                self.comensal_cuenta_actual or 1,
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
                if obtener_estado_pedido_movil(pedido_anterior_id)[4] == "En caja":
                    actualizar_estado_pedido_movil(
                        pedido_anterior_id, "Pendiente"
                    )

        self.pedidos_movil_actuales = []
        self.mesa_cuenta_actual = None
        era_para_llevar = bool(self.destino_para_llevar)
        self.destino_para_llevar = None
        self.carrito_cuenta_original = []
        self.carrito.clear()
        self.notas_rapidas.clear()
        self.total = 0.0
        self.actualizar_lista_pedido()
        self.actualizar_boton_notas()
        self.actualizar_total()
        self.actualizar_contexto_cuenta()
        self.actualizar_contador_pedidos()
        if agregando_a_cuenta:
            mensaje = (
                f"Los productos nuevos se agregaron a {mesa}.\n"
                f"Comanda #{pedido_id} enviada a cocina por ${total:.2f}."
            )
        elif era_para_llevar:
            mensaje = (
                f"Pedido #{pedido_id} enviado a cocina.\n"
                f"{mesa}\nTotal pendiente: ${total:.2f}\n\n"
                "Aparecerá en Cuentas activas para cobrarlo al entregar."
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

    def ejecutar_pagina_administracion(self, dialogo):
        """Abre una página administrativa maximizada y con scroll utilizable."""
        preparar_pagina_maximizada(dialogo)
        return dialogo.exec()

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
        estado_pedido = obtener_estado_pedido_movil(pedido_id)
        self.mesa_cuenta_actual = estado_pedido[1] if estado_pedido else None
        self.carrito_cuenta_original = list(self.carrito)
        self.aplicar_cuentas_capturadas([pedido_id])
        self.actualizar_total()
        self.actualizar_contexto_cuenta()
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
        self.mesa_cuenta_actual = mesa
        self.carrito_cuenta_original = list(self.carrito)
        self.aplicar_cuentas_capturadas(pedido_ids)
        if not self.carrito:
            return
        self.actualizar_total()
        self.actualizar_contexto_cuenta()
        QMessageBox.information(
            self, "Cuenta cargada",
            f"La cuenta completa de {mesa} está en caja. Puedes cobrarla o "
            "agregar productos nuevos a la cuenta."
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
        self.aplicar_cuentas_capturadas(pedido_ids)
        if not self.carrito:
            return
        self.actualizar_total()
        self.actualizar_contexto_cuenta()
        QMessageBox.information(
            self, "Cuenta cargada",
            f"La cuenta activa de {mesa} está en caja. Puedes cobrarla o agregar "
            "productos nuevos y presionar ENVIAR A MESA / COCINA."
        )

    def aplicar_cuentas_capturadas(self, pedido_ids):
        if not self.mesa_cuenta_actual:
            return False
        comensales = [
            cuenta for cuenta in obtener_comensales_mesa(self.mesa_cuenta_actual)
            if cuenta["estado"] == "ABIERTO" and cuenta["productos"]
        ]
        if not comensales:
            return False
        opciones = [
            f"Comensal {c['numero']} · ${c['total']:.2f} · "
            f"{len(c['productos'])} producto(s)"
            for c in comensales
        ]
        seleccion, ok = QInputDialog.getItem(
            self, "Seleccionar comensal",
            "Elige la cuenta que deseas ver, agregar productos o cobrar:",
            opciones, 0, False,
        )
        if not ok:
            self.cancelar_pedido()
            return False
        cuenta = comensales[opciones.index(seleccion)]
        self.carrito = list(cuenta["productos"])
        self.comensal_cuenta_actual = cuenta["numero"]
        self.cuentas_divididas_pendientes = []
        self.carrito_restante_division = []
        self.numero_cuenta_division_actual = 0
        self.total_cuentas_division = len(comensales)
        self.carrito_cuenta_original = list(self.carrito)
        self.total = sum(precio for _nombre, precio in self.carrito)
        self.actualizar_lista_pedido()
        self.actualizar_contexto_cuenta()
        return True

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
            f"Transferencia: ${corte['transferencia']:.2f}\n"
            f"Saldo pagado con puntos: ${corte['puntos']:.2f}\n\n"
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

        dialogo = QDialog(self)
        dialogo.setWindowTitle("Corte de caja - La Esquina Manager")
        layout = QVBoxLayout(dialogo)
        layout.setContentsMargins(24, 20, 24, 20)
        titulo = QLabel("CORTE DE CAJA")
        titulo.setStyleSheet("font-size:26px;font-weight:800;color:#292d28;")
        layout.addWidget(titulo)
        visor = QTextEdit()
        visor.setReadOnly(True)
        visor.setPlainText(texto)
        visor.setStyleSheet(
            "background:white;border:1px solid #d5d9d1;border-radius:10px;"
            "padding:16px;font-size:15px;color:#30352f;"
        )
        layout.addWidget(visor, 1)
        cerrar = QPushButton("Cerrar")
        cerrar.setMinimumSize(150, 42)
        cerrar.setStyleSheet(
            "background:#343934;color:white;border:0;border-radius:8px;font-weight:700;"
        )
        cerrar.clicked.connect(dialogo.accept)
        pie = QHBoxLayout()
        pie.addStretch()
        pie.addWidget(cerrar)
        layout.addLayout(pie)
        dialogo.setStyleSheet("QDialog{background:#f2f3ef;}")
        self.ejecutar_pagina_administracion(dialogo)

    def abrir_gastos(self):
        dialogo = GastosDialog(self)
        self.ejecutar_pagina_administracion(dialogo)

    def cargar_productos(self):
        self.productos = obtener_productos(solo_activos=True)

    def abrir_productos(self):
        dialogo = ProductosDialog(self)
        self.ejecutar_pagina_administracion(dialogo)

        # Actualiza los botones del POS al cerrar el administrador.
        self.cargar_productos()
        self.crear_interfaz()

    def abrir_clientes(self):
        dialogo = ClientesDialog(parent=self)
        self.ejecutar_pagina_administracion(dialogo)

    def abrir_recetas_costos(self):
        dialogo = RecetasCostosDialog(self)
        self.ejecutar_pagina_administracion(dialogo)

    def abrir_dashboard(self):
        dialogo = DashboardDialog(self)
        self.ejecutar_pagina_administracion(dialogo)

    def abrir_analisis_ventas(self):
        dialogo = AnalisisVentasDialog(self)
        self.ejecutar_pagina_administracion(dialogo)

    def abrir_configuracion(self):
        dialogo = ConfiguracionDialog(self)
        self.ejecutar_pagina_administracion(dialogo)

    def abrir_empleados(self):
        if self.empleado_actual["rol"] != "Administrador":
            QMessageBox.warning(
                self, "Sin permiso",
                "Solo un Administrador puede gestionar empleados."
            )
            return
        dialogo = EmpleadosDialog(self.empleado_actual, self)
        self.ejecutar_pagina_administracion(dialogo)
