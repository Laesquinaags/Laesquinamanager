import json
from pathlib import Path

from app.paths import APPLICATION_FOLDER


SETTINGS_FOLDER = APPLICATION_FOLDER / "data"
SETTINGS_FILE = SETTINGS_FOLDER / "settings.json"

DEFAULT_SETTINGS = {
    "meta_venta_diaria": 4000.0,
    "meta_venta_semanal": 24000.0,
    "meta_personas_dia": 20,
    "nombre_negocio": "LA ESQUINA",
    "subtitulo_negocio": "MANAGER  ·  PUNTO DE VENTA",
    "logo_negocio": "",
    "color_principal": "#d8ad25",
    "color_secundario": "#101119",
}


def cargar_configuracion():
    SETTINGS_FOLDER.mkdir(parents=True, exist_ok=True)

    if not SETTINGS_FILE.exists():
        guardar_configuracion(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except (json.JSONDecodeError, OSError):
        guardar_configuracion(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()

    configuracion = DEFAULT_SETTINGS.copy()
    configuracion.update(datos)
    return configuracion


def guardar_configuracion(configuracion):
    SETTINGS_FOLDER.mkdir(parents=True, exist_ok=True)

    with open(SETTINGS_FILE, "w", encoding="utf-8") as archivo:
        json.dump(configuracion, archivo, ensure_ascii=False, indent=4)
