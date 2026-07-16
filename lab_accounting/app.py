from __future__ import annotations

import sys
from pathlib import Path

from PyQt5.QtCore import QRect, Qt
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import QApplication, QMessageBox, QSplashScreen
from PyQt5.QtCore import QElapsedTimer, QEventLoop, QRect, QTimer, Qt
from lab_accounting.core.config import AppConfig, load_config


def resource_path(relative_path: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).resolve().parents[1] / relative_path


def create_splash(config: AppConfig) -> QSplashScreen:
    canvas = QPixmap(620, 310)
    canvas.fill(QColor("#c0d6ec"))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.Antialiasing)
    icon = QPixmap(str(resource_path("assets/app_icon.png")))
    if not icon.isNull():
        scaled = icon.scaled(112, 112, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        painter.drawPixmap((canvas.width() - scaled.width()) // 2, 28, scaled)
    painter.setPen(QColor("#111827"))
    title_font = QFont()
    title_font.setPointSize(18)
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.drawText(QRect(30, 148, 560, 34), Qt.AlignCenter, config.app_name)
    painter.setPen(QColor("#07080A"))
    body_font = QFont()
    body_font.setPointSize(11)
    painter.setFont(body_font)
    painter.drawText(QRect(45, 186, 530, 52), Qt.AlignCenter | Qt.TextWordWrap, config.app_description)
    painter.drawText(QRect(30, 238, 560, 24), Qt.AlignCenter, f"Version {config.app_version}")
    painter.end()
    return QSplashScreen(canvas, Qt.WindowStaysOnTopHint)


def main() -> int:
    config = load_config()
    app = QApplication(sys.argv)
    app.setApplicationName(config.app_name)

    icon_path = resource_path("assets/app_icon.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    splash = create_splash(config)
    splash.show()
    splash.showMessage(
        "データベースを確認しています…",
        Qt.AlignBottom | Qt.AlignHCenter,
        QColor("#334155"),
    )
    app.processEvents()

    # 从开屏页面显示时开始计时
    splash_timer = QElapsedTimer()
    splash_timer.start()

    try:
        from lab_accounting.repositories.database import Database

        database = Database(config.database_path)
        database.initialize()

        splash.showMessage(
            "画面を準備しています…",
            Qt.AlignBottom | Qt.AlignHCenter,
            QColor("#07090C"),
        )
        app.processEvents()

        from lab_accounting.ui.main_window import MainWindow

        window = MainWindow(database, config)
        window.resize(1280, 780)

        # 确保开屏页面至少显示 1500 ms
        remaining_ms = max(0, 1500 - splash_timer.elapsed())
        if remaining_ms > 0:
            wait_loop = QEventLoop()
            QTimer.singleShot(remaining_ms, wait_loop.quit)
            wait_loop.exec_()

        window.show()
        splash.finish(window)

        return app.exec_()

    except Exception as exc:
        splash.close()
        QMessageBox.critical(
            None,
            "起動エラー",
            f"アプリケーションを起動できませんでした。\n{exc}",
        )
        return 1
