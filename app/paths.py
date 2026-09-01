"""Rutas estables para datos del negocio y recursos empaquetados."""
import os
import sys
from pathlib import Path


def application_folder():
    """Carpeta persistente, independiente del directorio de inicio."""
    override = os.environ.get("LA_ESQUINA_HOME")
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_folder():
    """Carpeta de recursos; PyInstaller los extrae temporalmente al ejecutar."""
    bundle = getattr(sys, "_MEIPASS", None)
    return Path(bundle).resolve() if bundle else application_folder()


APPLICATION_FOLDER = application_folder()
RESOURCE_FOLDER = resource_folder()
