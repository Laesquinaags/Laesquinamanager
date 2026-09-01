import sys
import os
from pathlib import Path


# En ejecutables empaquetados, Windows debe buscar primero las DLL de Qt que
# viajan junto con la aplicación. Conservamos el identificador durante toda la
# ejecución para que el directorio permanezca registrado.
_qt_dll_directory = None
if getattr(sys, "frozen", False) and hasattr(os, "add_dll_directory"):
    _qt_folder = Path(getattr(sys, "_MEIPASS", "")) / "PySide6"
    if _qt_folder.is_dir():
        _qt_dll_directory = os.add_dll_directory(str(_qt_folder))

from PySide6.QtWidgets import QApplication

from app.database.database import crear_tablas
from app.ui.main_window import MainWindow


def main():
    crear_tablas()

    app = QApplication(sys.argv)

    ventana = MainWindow()
    ventana.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
