import sys

from PyQt5.QtWidgets import QApplication

from lab_accounting.core.config import load_config
from lab_accounting.repositories.database import Database
from lab_accounting.ui.main_window import MainWindow


def main() -> int:
    config = load_config()
    app = QApplication(sys.argv)
    app.setApplicationName(config.app_name)

    database = Database(config.database_path)
    database.initialize()

    window = MainWindow(database, config)
    window.resize(1280, 780)
    window.show()
    return app.exec_()
