import json
from pathlib import Path
from datetime import datetime

from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

from PIL import Image
import win32print

from app.paths import APPLICATION_FOLDER, RESOURCE_FOLDER

TICKETS_FOLDER = APPLICATION_FOLDER / "tickets"
ASSETS_FOLDER = RESOURCE_FOLDER / "app" / "assets"
LOGO_FILE = ASSETS_FOLDER / "logo_termico.png"
LOGO_EXTERNAL_FILE = APPLICATION_FOLDER / "app" / "assets" / "logo_termico.png"

PRINTER_NAME = "POS-80-Series"
LINE_WIDTH = 42


def _obtener_logo():
    """Busca un logo legible dentro del ejecutable o junto al programa."""
    for ruta in dict.fromkeys((LOGO_FILE, LOGO_EXTERNAL_FILE)):
        try:
            if ruta.is_file():
                with Image.open(ruta) as imagen:
                    imagen.verify()
                return ruta
        except Exception:
            continue
    return None


def _texto_centrado(c, texto, y, ancho, font="Helvetica", size=9):
    c.setFont(font, size)
    c.drawCentredString(ancho / 2, y, texto)


def _agrupar_productos(productos):
    agrupados = {}

    for nombre, precio in productos:
        clave = (nombre, float(precio))
        agrupados[clave] = agrupados.get(clave, 0) + 1

    return agrupados


def generar_ticket_pdf(
    venta_id,
    productos,
    total,
    metodo,
    personas=1,
    origen="No registrado",
    recibido=None,
    cambio=None,
    mesa=None,
):
    """
    Guarda una copia PDF del ticket.
    Personas y origen se conservan para datos internos, pero NO se imprimen
    en el ticket del cliente.
    """
    TICKETS_FOLDER.mkdir(parents=True, exist_ok=True)

    ancho = 80 * mm
    alto = max(175 * mm, (130 + len(productos) * 7) * mm)
    ruta = TICKETS_FOLDER / f"ticket_{venta_id}.pdf"

    c = canvas.Canvas(str(ruta), pagesize=(ancho, alto))
    y = alto - 7 * mm

    # Logo, con una copia externa de respaldo junto al programa.
    logo_file = _obtener_logo()
    if logo_file is not None:
        try:
            logo = ImageReader(str(logo_file))
            logo_w = 58 * mm
            logo_h = 29 * mm
            c.drawImage(
                logo,
                (ancho - logo_w) / 2,
                y - logo_h,
                width=logo_w,
                height=logo_h,
                preserveAspectRatio=True,
                mask="auto",
            )
            y -= 31 * mm
        except Exception:
            pass

    _texto_centrado(c, "LA ESQUINA DESAYUNOS", y, ancho, "Helvetica-Bold", 11)
    y -= 5 * mm
    _texto_centrado(c, "Av. Guadalupe Gonzalez 201, Local 9", y, ancho, "Helvetica", 7.5)
    y -= 4 * mm
    _texto_centrado(c, "Frente a la UAA", y, ancho, "Helvetica", 7.5)
    y -= 5 * mm

    c.line(5 * mm, y, ancho - 5 * mm, y)
    y -= 5 * mm

    c.setFont("Helvetica", 8)
    c.drawString(6 * mm, y, f"Ticket #{venta_id}")
    c.drawRightString(ancho - 6 * mm, y, datetime.now().strftime("%d/%m/%Y %H:%M"))
    y -= 5 * mm

    if mesa:
        c.setFont("Helvetica-Bold", 8)
        c.drawString(6 * mm, y, str(mesa)[:36])
        y -= 5 * mm

    c.line(5 * mm, y, ancho - 5 * mm, y)
    y -= 5 * mm

    # Encabezados de productos
    c.setFont("Helvetica-Bold", 7)
    c.drawString(5 * mm, y, "CANT")
    c.drawString(14 * mm, y, "PRODUCTO")
    c.drawRightString(59 * mm, y, "P.UNIT.")
    c.drawRightString(ancho - 5 * mm, y, "IMPORTE")
    y -= 4 * mm

    c.line(5 * mm, y, ancho - 5 * mm, y)
    y -= 4 * mm

    # Productos
    for (nombre, precio), cantidad in _agrupar_productos(productos).items():
        subtotal = cantidad * precio

        c.setFont("Helvetica", 7)
        c.drawRightString(11 * mm, y, str(cantidad))
        c.drawString(14 * mm, y, nombre[:20])
        c.drawRightString(59 * mm, y, f"${precio:.2f}")
        c.drawRightString(ancho - 5 * mm, y, f"${subtotal:.2f}")
        y -= 4.5 * mm

    c.line(5 * mm, y, ancho - 5 * mm, y)
    y -= 6 * mm

    c.setFont("Helvetica-Bold", 13)
    c.drawString(6 * mm, y, "TOTAL")
    c.drawRightString(ancho - 6 * mm, y, f"${total:.2f}")
    y -= 7 * mm

    c.setFont("Helvetica", 8.5)
    c.drawString(6 * mm, y, "Pago:")
    c.drawRightString(ancho - 6 * mm, y, str(metodo))
    y -= 4.5 * mm

    if metodo == "Efectivo" and recibido is not None:
        c.drawString(6 * mm, y, "Recibido:")
        c.drawRightString(ancho - 6 * mm, y, f"${recibido:.2f}")
        y -= 4.5 * mm

        c.drawString(6 * mm, y, "Cambio:")
        c.drawRightString(ancho - 6 * mm, y, f"${cambio:.2f}")
        y -= 5 * mm

    c.line(5 * mm, y, ancho - 5 * mm, y)
    y -= 7 * mm

    _texto_centrado(c, "Gracias por visitarnos!", y, ancho, "Helvetica-Bold", 10)
    y -= 5 * mm
    _texto_centrado(c, "Nos vemos en tu proximo desayuno", y, ancho, "Helvetica", 8.5)
    y -= 6 * mm
    _texto_centrado(c, "Lunes a Sabado 9:00 am - 2:30 pm", y, ancho, "Helvetica", 7.5)

    c.save()

    datos = {
        "venta_id": int(venta_id),
        "productos": [[n, float(p)] for n, p in productos],
        "total": float(total),
        "metodo": str(metodo),
        "personas": int(personas),
        "origen": str(origen),
        "recibido": None if recibido is None else float(recibido),
        "cambio": None if cambio is None else float(cambio),
        "mesa": None if mesa is None else str(mesa),
    }

    ruta_datos = TICKETS_FOLDER / f"ticket_{venta_id}.json"
    ruta_datos.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return ruta


def _linea_producto_columnas(nombre, cantidad, precio, subtotal):
    """
    Formato de 42 caracteres:
    CC PRODUCTO             P.UNIT   IMPORTE
    """
    cant = f"{cantidad:>2}"
    punit = f"{precio:>6.2f}"
    importe = f"{subtotal:>7.2f}"

    # 2 cant + 1 espacio + 17 producto + 1 + 6 unit + 1 + 7 importe = 35
    # Dejamos margen para símbolos $ y separación.
    nombre_corto = nombre[:17]

    return (
        f"{cant} "
        f"{nombre_corto:<17} "
        f"${punit} "
        f"${importe}"
    )


def _imagen_a_escpos(ruta_imagen, max_width=560):
    """
    Convierte una imagen monocromática en comando ESC/POS raster GS v 0.
    """
    img = Image.open(ruta_imagen).convert("L")

    if img.width > max_width:
        ratio = max_width / img.width
        img = img.resize(
            (max_width, max(1, int(img.height * ratio))),
            Image.LANCZOS,
        )

    img = img.point(lambda p: 0 if p < 180 else 255, mode="1")

    width = img.width
    height = img.height
    width_bytes = (width + 7) // 8

    raster = bytearray()

    for y in range(height):
        for xb in range(width_bytes):
            byte = 0

            for bit in range(8):
                x = xb * 8 + bit
                pixel_negro = x < width and img.getpixel((x, y)) == 0

                if pixel_negro:
                    byte |= 1 << (7 - bit)

            raster.append(byte)

    xL = width_bytes & 0xFF
    xH = (width_bytes >> 8) & 0xFF
    yL = height & 0xFF
    yH = (height >> 8) & 0xFF

    return b"\x1d\x76\x30\x00" + bytes([xL, xH, yL, yH]) + bytes(raster)


def _crear_ticket_escpos(datos):
    ESC = b"\x1b"
    GS = b"\x1d"

    salida = bytearray()

    # Inicializar
    salida += ESC + b"@"

    # Logo centrado
    logo_file = _obtener_logo()
    if logo_file is not None:
        salida += ESC + b"a" + b"\x01"
        salida += _imagen_a_escpos(logo_file)
        salida += b"\n"

    # Encabezado
    salida += ESC + b"a" + b"\x01"
    salida += ESC + b"E" + b"\x01"
    salida += b"LA ESQUINA DESAYUNOS\n"
    salida += ESC + b"E" + b"\x00"
    salida += b"Av. Guadalupe Gonzalez 201, Local 9\n"
    salida += b"Frente a la UAA\n"

    if datos.get("provisional"):
        salida += b"\n"
        salida += ESC + b"E" + b"\x01"
        salida += b"CUENTA PROVISIONAL - NO PAGADO\n"
        salida += ESC + b"E" + b"\x00"

    # Separador
    salida += ESC + b"a" + b"\x00"
    salida += ("-" * LINE_WIDTH + "\n").encode("ascii")

    # Folio y fecha
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    if datos.get("provisional"):
        mesa = datos.get("mesa") or "Pedido actual"
        salida += f"{mesa:<20} {fecha}\n".encode("cp850", errors="replace")
    else:
        venta_id = datos["venta_id"]
        salida += f"Ticket #{venta_id:<8} {fecha}\n".encode("cp850", errors="replace")
    salida += ("-" * LINE_WIDTH + "\n").encode("ascii")

    # Encabezado de columnas
    salida += ESC + b"E" + b"\x01"
    salida += b"CANT PRODUCTO           P.UNIT  IMPORTE\n"
    salida += ESC + b"E" + b"\x00"
    salida += ("-" * LINE_WIDTH + "\n").encode("ascii")

    # Productos
    for (nombre, precio), cantidad in _agrupar_productos(
        datos["productos"]
    ).items():
        subtotal = cantidad * precio
        linea = _linea_producto_columnas(
            nombre,
            cantidad,
            precio,
            subtotal,
        )
        salida += (linea + "\n").encode("cp850", errors="replace")

    salida += ("-" * LINE_WIDTH + "\n").encode("ascii")

    # Total grande
    salida += ESC + b"E" + b"\x01"
    salida += GS + b"!" + b"\x11"
    salida += f"TOTAL ${datos['total']:.2f}\n".encode("ascii")
    salida += GS + b"!" + b"\x00"
    salida += ESC + b"E" + b"\x00"

    salida += ("-" * LINE_WIDTH + "\n").encode("ascii")

    # Pago
    if datos.get("provisional"):
        salida += b"ESTADO: PENDIENTE DE PAGO\n"
    else:
        salida += f"Pago: {datos['metodo']}\n".encode("cp850", errors="replace")

        if datos["metodo"] == "Efectivo" and datos["recibido"] is not None:
            salida += f"Recibido: ${datos['recibido']:.2f}\n".encode("ascii")
            salida += f"Cambio:   ${datos['cambio']:.2f}\n".encode("ascii")

    salida += ("-" * LINE_WIDTH + "\n").encode("ascii")

    # Despedida
    salida += ESC + b"a" + b"\x01"
    salida += ESC + b"E" + b"\x01"
    if datos.get("provisional"):
        salida += b"Favor de presentar esta cuenta al pagar\n"
        salida += ESC + b"E" + b"\x00"
        salida += b"Este documento no comprueba pago\n"
    else:
        salida += b"Gracias por visitarnos!\n"
        salida += ESC + b"E" + b"\x00"
        salida += b"Nos vemos en tu proximo desayuno\n"
        salida += b"Lunes a Sabado 9:00 am - 2:30 pm\n"

    # Avance extra para evitar corte prematuro
    salida += b"\n\n\n\n"
    salida += ESC + b"d" + b"\x04"

    # Corte
    salida += GS + b"V" + b"\x00"

    return bytes(salida)


def _enviar_a_impresora(datos, nombre_documento):
    impresoras = [
        impresora[2]
        for impresora in win32print.EnumPrinters(2)
    ]
    if PRINTER_NAME not in impresoras:
        raise RuntimeError(
            f"No se encontro la impresora '{PRINTER_NAME}' en Windows."
        )

    impresora = win32print.OpenPrinter(PRINTER_NAME)
    try:
        win32print.StartDocPrinter(
            impresora, 1, (nombre_documento, None, "RAW")
        )
        try:
            win32print.StartPagePrinter(impresora)
            win32print.WritePrinter(impresora, _crear_ticket_escpos(datos))
            win32print.EndPagePrinter(impresora)
        finally:
            win32print.EndDocPrinter(impresora)
    finally:
        win32print.ClosePrinter(impresora)
    return True


def imprimir_cuenta(productos, total, mesa=None):
    """Imprime una cuenta provisional sin registrar ni cobrar una venta."""
    if not productos:
        raise ValueError("Agrega al menos un producto.")
    datos = {
        "venta_id": "PROVISIONAL",
        "productos": [[nombre, float(precio)] for nombre, precio in productos],
        "total": float(total),
        "metodo": "Pendiente",
        "recibido": None,
        "cambio": None,
        "mesa": mesa,
        "provisional": True,
    }
    return _enviar_a_impresora(datos, "La Esquina - Cuenta provisional")


def imprimir_ticket(ruta_pdf):
    """
    Imprime directamente en la POS-80-Series usando RAW/ESC-POS.
    """
    ruta_pdf = Path(ruta_pdf)

    venta_id = ruta_pdf.stem.replace("ticket_", "")
    ruta_datos = TICKETS_FOLDER / f"ticket_{venta_id}.json"

    if not ruta_datos.exists():
        raise FileNotFoundError(
            f"No se encontraron los datos del ticket: {ruta_datos}"
        )

    datos = json.loads(
        ruta_datos.read_text(encoding="utf-8")
    )

    impresoras = [
        impresora[2]
        for impresora in win32print.EnumPrinters(2)
    ]

    if PRINTER_NAME not in impresoras:
        raise RuntimeError(
            f"No se encontro la impresora '{PRINTER_NAME}' en Windows."
        )

    datos_raw = _crear_ticket_escpos(datos)

    impresora = win32print.OpenPrinter(PRINTER_NAME)

    try:
        win32print.StartDocPrinter(
            impresora,
            1,
            ("La Esquina Ticket", None, "RAW"),
        )

        try:
            win32print.StartPagePrinter(impresora)
            win32print.WritePrinter(impresora, datos_raw)
            win32print.EndPagePrinter(impresora)
        finally:
            win32print.EndDocPrinter(impresora)

    finally:
        win32print.ClosePrinter(impresora)

    return True
