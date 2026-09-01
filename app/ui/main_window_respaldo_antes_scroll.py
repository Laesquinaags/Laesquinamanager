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
)
from PySide6.QtCore import Qt, QDateTime

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
)
from app.settings import cargar_configuracion, guardar_configuracion
from app.tickets import generar_ticket_pdf, imprimir_ticket


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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("La Esquina Manager")
        self.resize(1200, 750)

        self.carrito = []
        self.total = 0.0

        self.productos = []
        self.cargar_productos()
        self.crear_interfaz()

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

        grid = QGridLayout()

        fila = 0
        columna = 0

        for _id, nombre, precio, _categoria, _activo, _orden in self.productos:
            boton = QPushButton(f"{nombre}\n${precio:.0f}")
            boton.setMinimumSize(170, 85)
            boton.setStyleSheet("""
                QPushButton {
                    font-size: 16px;
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

            grid.addWidget(boton, fila, columna)
            columna += 1

            if columna == 3:
                columna = 0
                fila += 1

        layout_productos.addLayout(grid)
        layout_productos.addStretch()

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

        boton_cancelar = QPushButton("Cancelar pedido")
        boton_cancelar.setMinimumHeight(45)
        boton_cancelar.clicked.connect(self.cancelar_pedido)

        boton_ventas = QPushButton("Ventas del día")
        boton_ventas.setMinimumHeight(45)
        boton_ventas.clicked.connect(self.mostrar_ventas_hoy)

        boton_historial = QPushButton("Historial / Reimprimir")
        boton_historial.setMinimumHeight(45)
        boton_historial.clicked.connect(self.abrir_historial)

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

        boton_cobrar = QPushButton("COBRAR")
        boton_cobrar.setMinimumHeight(70)
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

        layout_pedido.addWidget(titulo_pedido)
        layout_pedido.addWidget(self.lista_pedido)
        layout_pedido.addWidget(self.label_total)
        layout_pedido.addWidget(boton_quitar)
        layout_pedido.addWidget(boton_cancelar)
        layout_pedido.addWidget(boton_ventas)
        layout_pedido.addWidget(boton_historial)
        layout_pedido.addWidget(boton_gastos)
        layout_pedido.addWidget(boton_corte)
        layout_pedido.addWidget(boton_dashboard)
        layout_pedido.addWidget(boton_productos)
        layout_pedido.addWidget(boton_config)
        layout_pedido.addWidget(boton_cobrar)

        layout_principal.addWidget(panel_productos, 3)
        layout_principal.addWidget(panel_pedido, 1)

    def agregar_producto(self, nombre, precio):
        self.carrito.append((nombre, precio))
        self.total += precio

        self.lista_pedido.addItem(
            f"{nombre} - ${precio:.2f}"
        )

        self.actualizar_total()

    def quitar_producto(self):
        fila = self.lista_pedido.currentRow()

        if fila < 0:
            return

        _, precio = self.carrito.pop(fila)
        self.total -= precio

        self.lista_pedido.takeItem(fila)
        self.actualizar_total()

    def cancelar_pedido(self):
        self.carrito.clear()
        self.total = 0.0
        self.lista_pedido.clear()
        self.actualizar_total()

    def actualizar_total(self):
        self.label_total.setText(
            f"TOTAL: ${self.total:.2f}"
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

        metodo, ok = QInputDialog.getItem(
            self,
            "Método de pago",
            "Selecciona el método de pago:",
            ["Efectivo", "Tarjeta", "Transferencia"],
            0,
            False,
        )

        if not ok:
            return

        recibido = None
        cambio = None

        if metodo == "Efectivo":
            recibido, ok = QInputDialog.getDouble(
                self,
                "Pago en efectivo",
                f"Total: ${self.total:.2f}\n\n¿Cuánto recibió?",
                value=self.total,
                minValue=0.0,
                maxValue=100000.0,
                decimals=2,
            )

            if not ok:
                return

            if recibido < self.total:
                faltante = self.total - recibido

                QMessageBox.warning(
                    self,
                    "Pago insuficiente",
                    f"Faltan ${faltante:.2f} para completar la venta.",
                )

                return

            cambio = recibido - self.total

        total_venta = self.total
        productos_ticket = list(self.carrito)

        venta_id = guardar_venta(
            self.carrito,
            total_venta,
            metodo,
            personas,
            origen,
        )

        # Generar ticket PDF automáticamente
        try:
            ruta_ticket = generar_ticket_pdf(
                venta_id=venta_id,
                productos=productos_ticket,
                total=total_venta,
                metodo=metodo,
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

        if metodo == "Efectivo":
            mensaje = (
                f"Venta #{venta_id}\n\n"
                f"Personas: {personas}\n"
                f"Origen: {origen}\n"
                f"Total: ${total_venta:.2f}\n"
                f"Recibido: ${recibido:.2f}\n"
                f"CAMBIO: ${cambio:.2f}\n\n"
                "Venta guardada correctamente."
            )
        else:
            mensaje = (
                f"Venta #{venta_id}\n\n"
                f"Personas: {personas}\n"
                f"Origen: {origen}\n"
                f"Total: ${total_venta:.2f}\n"
                f"Método: {metodo}\n\n"
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
