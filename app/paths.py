"""Rutas estables para datos del negocio y recursos empaquetados."""
import os
import sys
from pathlib import Path


def application_folder():
    """Carpeta persistente compartida por desarrollo y ejecutable."""
    override = os.environ.get("LA_ESQUINA_HOME")
    if override:
        return Path(override).expanduser().resolve()

    # Usar una ubicacion estable evita que cada EXE compilado termine
    # leyendo una base distinta dentro de dist. Tanto VS Code como el
    # ejecutable comparten los mismos datos del negocio.
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return (Path(local_app_data) / "LaEsquinaManager").resolve()

    return (Path.home() / ".la_esquina_manager").resolve()


def resource_folder():
    """Carpeta de recursos; PyInstaller los extrae temporalmente al ejecutar."""
    bundle = getattr(sys, "_MEIPASS", None)
    return Path(bundle).resolve() if bundle else application_folder()


APPLICATION_FOLDER = application_folder()
RESOURCE_FOLDER = resource_folder()
