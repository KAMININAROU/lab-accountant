from __future__ import annotations

import hashlib
import sys
from datetime import date
from datetime import datetime, timezone, timedelta
from pathlib import Path

from PyQt5.QtCore import QDate, QTimer, Qt
from PyQt5.QtGui import QColor, QIcon
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QInputDialog,
    QPushButton,
    QHeaderView,
    QStyle,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from lab_accounting.core.config import AppConfig
from lab_accounting.core.fiscal_year import fiscal_months, month_label
from lab_accounting.core.formatters import decimal_text, money
from lab_accounting.core.tax import calc_from_gross, calc_from_net
from lab_accounting.exporters.excel_exporter import ExcelExporter
from lab_accounting.repositories.database import Database
from lab_accounting.repositories.log_repository import LogRepository
from lab_accounting.repositories.payment_repository import PaymentRepository
from lab_accounting.repositories.person_repository import PersonRepository
from lab_accounting.repositories.record_repository import RecordRepository
from lab_accounting.services.backup_service import BackupService
from lab_accounting.services.closing_service import ClosingService
from lab_accounting.services.log_service import LogService
from lab_accounting.services.person_service import PersonService
from lab_accounting.services.record_service import RecordService
from lab_accounting.services.summary_service import SummaryService


RECORD_TYPES = {
    "繰越": "carryover",
    "給料(TA)": "salary_ta",
    "給料(Other)": "salary_other",
    "調整": "adjustment",
    "支給": "payment",
    "交通費": "transportation",
    "立替": "advance",
    "謝金": "honorarium",
    "その他": "other",
}
RECORD_TYPE_LABELS = {value: key for key, value in RECORD_TYPES.items()}
RECORD_TYPE_LABELS.update({"income": "収入"})
RESIDENT_TYPES = {"居住者": "resident", "非居住者": "nonresident"}
RESIDENT_LABELS = {value: key for key, value in RESIDENT_TYPES.items()}
MODES = {"日数": "days", "割合": "ratio", "手入力": "manual"}
JST = timezone(timedelta(hours=9))


def resource_path(relative_path: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).resolve().parents[2] / relative_path


class MainWindow(QMainWindow):
    def __init__(self, database: Database, config: AppConfig) -> None:
        super().__init__()
        self.db = database
        self.config = config
        self.setWindowTitle(config.app_name)
        icon_path = resource_path("assets/app_icon.png")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        else:
            self.setWindowIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        self.setStyleSheet(
            """
            QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {
                font-size: 13px;
                min-height: 24px;
            }
            QPushButton {
                font-size: 13px;
                min-height: 26px;
            }
            QHeaderView::section {
                font-size: 13px;
                font-weight: 600;
            }
            """
        )

        self.logs_repo = LogRepository(database)
        self.person_repo = PersonRepository(database)
        self.record_repo = RecordRepository(database)
        self.payment_repo = PaymentRepository(database)

        self.person_service = PersonService(self.person_repo, self.logs_repo)
        self.record_service = RecordService(self.record_repo, self.logs_repo, config.fiscal_year_start_month)
        self.closing_service = ClosingService(
            self.person_repo,
            self.record_repo,
            self.payment_repo,
            self.logs_repo,
            config.resident_tax_rate,
            config.nonresident_tax_rate,
        )
        self.summary_service = SummaryService(self.person_repo, self.record_repo, self.payment_repo)
        self.log_service = LogService(self.logs_repo)
        self.backup_service = BackupService(config.database_path, config.backup_path)
        self.backup_timer = QTimer(self)
        self.backup_timer.timeout.connect(self.run_auto_backup)
        self.backup_timer.start(max(1, config.auto_backup_interval_minutes) * 60 * 1000)

        root = QWidget()
        layout = QHBoxLayout(root)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        self.nav = QListWidget()
        self.nav.setFixedWidth(230)
        self.nav.setStyleSheet(
            """
            QListWidget {
                font-size: 14px;
            }
            QListWidget::item {
                min-height: 34px;
                padding: 4px 8px;
            }
            """
        )
        self.credit_label = QLabel(f"研究室報酬管理システム\nv{config.app_version}\n© 2026 Tian Lunpu")
        self.credit_label.setAlignment(Qt.AlignCenter)
        self.credit_label.setStyleSheet(
            """
            QLabel {
                color: #5d5bef;
                font-size: 11px;
                padding: 8px;
            }
            """
        )
        self.stack = QStackedWidget()
        left_layout.addWidget(self.nav, 1)
        left_layout.addWidget(self.credit_label)
        layout.addWidget(left_panel)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        self.pages: list[BasePage] = [
            PersonPage(self),
            RecordPage(self),
            PersonalDetailPage(self),
            MonthlyClosingPage(self),
            SummaryPage(self),
            TaxCalculatorPage(self),
            ExportPage(self),
            LogViewerPage(self),
            SettingsPage(self),
        ]
        japanese_names = [
            "人員管理",
            "案件入力",
            "個人明細",
            "月次精算",
            "年度集計",
            "税額計算",
            "Excel出力",
            "ログ表示",
            "設定",
        ]
        icons = [
            QStyle.SP_FileDialogDetailedView,
            QStyle.SP_FileIcon,
            QStyle.SP_DirIcon,
            QStyle.SP_DialogApplyButton,
            QStyle.SP_FileDialogInfoView,
            QStyle.SP_DialogHelpButton,
            QStyle.SP_DriveHDIcon,
            QStyle.SP_MessageBoxInformation,
            QStyle.SP_FileDialogContentsView,
        ]
        for index, (page, label) in enumerate(zip(self.pages, japanese_names)):
            item = QListWidgetItem(self.style().standardIcon(icons[index]), label)
            item.setData(Qt.UserRole, index)
            self.nav.addItem(item)
            self.stack.addWidget(page)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        self.status_indicator = QLabel()
        self.status_indicator.setFixedSize(14, 14)
        self.status_indicator.setToolTip("Application status")
        self.statusBar().addPermanentWidget(self.status_indicator)
        self.status_label = QLabel("準備完了")
        self.statusBar().addPermanentWidget(self.status_label)
        self.set_app_status("ok", "準備完了")

    def refresh_all(self) -> None:
        for page in self.pages:
            page.refresh()

    def show_error(self, message: str) -> None:
        self.set_app_status("error", message, 10000)
        QMessageBox.critical(self, "エラー", message)

    def show_info(self, message: str) -> None:
        self.set_app_status("ok", message, 7000)
        QMessageBox.information(self, "完了", message)

    def set_app_status(self, level: str, message: str, timeout: int = 0) -> None:
        colors = {
            "ok": "#60d3f3",
            "info": "#60d3f3",
            "busy": "#cbd5e1",
            "warning": "#fde047",
            "error": "#ef4444",
        }
        color = colors.get(level, "#cbd5e1")
        self.status_indicator.setStyleSheet(
            f"""
            QLabel {{
                background-color: {color};
                border-radius: 7px;
                border: 1px solid #475569;
            }}
            """
        )
        self.status_indicator.setToolTip(message)
        self.status_label.setText(message)
        self.statusBar().showMessage(message, timeout)

    def color_for_person_id(self, person_id: int | None) -> str:
        if person_id is None:
            return ""
        person = self.person_repo.get(int(person_id))
        return (person or {}).get("color") or ""

    def verify_delete_password(self) -> bool:
        password, ok = QInputDialog.getText(
            self,
            "削除パスワード",
            "削除パスワードを入力してください。",
            QLineEdit.Password,
        )
        if not ok:
            return False
        rows = self.db.query(
            "SELECT setting_value FROM app_settings WHERE setting_key = ?",
            ("delete_password_hash",),
        )
        expected = rows[0]["setting_value"] if rows else ""
        actual = hashlib.sha256(password.encode("utf-8")).hexdigest()
        if actual != expected:
            self.set_app_status("error", "削除パスワードが正しくありません。", 10000)
            QMessageBox.critical(self, "エラー", "削除パスワードが正しくありません。")
            return False
        return True

    def run_auto_backup(self) -> None:
        try:
            self.set_app_status("busy", "自動バックアップ中...")
            path = self.backup_service.create_backup("auto")
            self.logs_repo.add("INFO", "AUTO_BACKUP_CREATED", f"Auto backup created: {path}")
            self.set_app_status("ok", f"自動バックアップ完了: {path}", 7000)
        except Exception as exc:
            self.logs_repo.add("ERROR", "AUTO_BACKUP_FAILED", str(exc))
            self.set_app_status("error", f"自動バックアップ失敗: {exc}", 10000)


class BasePage(QWidget):
    def __init__(self, window: MainWindow) -> None:
        super().__init__()
        self.window = window

    def refresh(self) -> None:
        pass


class PersonPage(BasePage):
    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.selected_id: int | None = None
        layout = QVBoxLayout(self)
        form_box = QGroupBox("人員情報")
        form = QGridLayout(form_box)
        self.name = QLineEdit()
        self.display_name = QLineEdit()
        self.name_kana = QLineEdit()
        self.resident_type = QComboBox()
        self.resident_type.addItems(RESIDENT_TYPES.keys())
        self.tax_rate = QLineEdit()
        self.tax_rate.setReadOnly(True)
        self.daily_gross = QSpinBox()
        self.daily_gross.setMinimum(10000)
        self.daily_gross.setMaximum(1000000)
        self.daily_gross.setSingleStep(1000)
        self.daily_gross.setValue(max(10000, window.config.default_daily_gross_amount))
        self.daily_net = QLineEdit()
        self.daily_net.setReadOnly(True)
        self.color = QLineEdit("#dbeafe")
        self.active = QCheckBox("有効")
        self.active.setChecked(True)
        pick_color = QPushButton("色を選択")
        pick_color.clicked.connect(self.pick_color)
        self.resident_type.currentIndexChanged.connect(self.update_auto_amounts)
        self.daily_gross.valueChanged.connect(self.update_auto_amounts)

        form.addWidget(QLabel("氏名"), 0, 0)
        form.addWidget(self.name, 0, 1)
        form.addWidget(QLabel("表示名"), 0, 2)
        form.addWidget(self.display_name, 0, 3)
        form.addWidget(QLabel("カナ/備考"), 1, 0)
        form.addWidget(self.name_kana, 1, 1)
        form.addWidget(QLabel("区分"), 1, 2)
        form.addWidget(self.resident_type, 1, 3)
        form.addWidget(QLabel("税率"), 2, 0)
        form.addWidget(self.tax_rate, 2, 1)
        form.addWidget(QLabel("日額(支払総額)"), 2, 2)
        form.addWidget(self.daily_gross, 2, 3)
        form.addWidget(QLabel("日額(手取額)"), 3, 0)
        form.addWidget(self.daily_net, 3, 1)
        form.addWidget(QLabel("色"), 3, 2)
        color_row = QHBoxLayout()
        color_row.addWidget(self.color)
        color_row.addWidget(pick_color)
        form.addLayout(color_row, 3, 3)
        form.addWidget(self.active, 4, 1)

        buttons = QHBoxLayout()
        add_btn = QPushButton("新規保存")
        update_btn = QPushButton("更新")
        delete_btn = QPushButton("選択行を削除")
        clear_btn = QPushButton("入力クリア")
        add_btn.clicked.connect(self.create_person)
        update_btn.clicked.connect(self.update_person)
        delete_btn.clicked.connect(self.delete_selected_people)
        clear_btn.clicked.connect(self.clear_form)
        buttons.addWidget(add_btn)
        buttons.addWidget(update_btn)
        buttons.addWidget(delete_btn)
        buttons.addWidget(clear_btn)
        buttons.addStretch()

        self.table = make_table()
        self.table.cellClicked.connect(self.select_row)
        layout.addWidget(form_box)
        layout.addLayout(buttons)
        layout.addWidget(self.table, 1)
        self.update_auto_amounts()
        self.refresh()

    def pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(self.color.text()), self, "色を選択")
        if color.isValid():
            self.color.setText(color.name())

    def values(self) -> dict:
        daily_net = int(calc_from_gross(self.daily_gross.value(), self.current_tax_rate())["net_amount"])
        return {
            "name": self.name.text().strip(),
            "display_name": self.display_name.text().strip(),
            "name_kana": self.name_kana.text().strip(),
            "resident_type": RESIDENT_TYPES[self.resident_type.currentText()],
            "tax_rate": None,
            "daily_gross_amount": self.daily_gross.value(),
            "daily_net_amount": daily_net,
            "color": self.color.text().strip() or "#dbeafe",
            "active": self.active.isChecked(),
        }

    def current_tax_rate(self) -> float:
        if RESIDENT_TYPES[self.resident_type.currentText()] == "nonresident":
            return self.window.config.nonresident_tax_rate
        return self.window.config.resident_tax_rate

    def update_auto_amounts(self) -> None:
        tax_rate = self.current_tax_rate()
        net_amount = calc_from_gross(self.daily_gross.value(), tax_rate)["net_amount"]
        self.tax_rate.setText(f"{tax_rate:.4f}")
        self.daily_net.setText(f"{net_amount:,.0f}")

    def create_person(self) -> None:
        try:
            self.window.person_service.save(self.values())
            self.clear_form()
            self.window.refresh_all()
            self.window.set_app_status("ok", "人員情報を保存しました。", 7000)
        except Exception as exc:
            self.window.show_error(str(exc))

    def update_person(self) -> None:
        if not self.selected_id:
            self.window.show_error("更新する人員を選択してください。")
            return
        try:
            self.window.person_service.save(self.values(), self.selected_id)
            self.window.refresh_all()
            self.window.set_app_status("ok", "人員情報を更新しました。", 7000)
        except Exception as exc:
            self.window.show_error(str(exc))

    def delete_selected_people(self) -> None:
        selected_ids = []
        for index in self.table.selectionModel().selectedRows():
            item = self.table.item(index.row(), 0)
            if item:
                selected_ids.append(int(item.data(Qt.UserRole)))
        if not selected_ids and self.selected_id:
            selected_ids = [self.selected_id]
        if not selected_ids:
            self.window.show_error("削除する人員を選択してください。")
            return
        message = f"{len(selected_ids)}名を削除します。関連する案件・月次精算も削除されます。続行しますか？"
        if QMessageBox.warning(self, "確認", message, QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        if not self.window.verify_delete_password():
            return
        try:
            for person_id in selected_ids:
                self.window.person_service.delete(person_id)
            self.clear_form()
            self.window.refresh_all()
            self.window.set_app_status("ok", "選択人員を削除しました。", 7000)
        except Exception as exc:
            self.window.show_error(str(exc))

    def select_row(self, row: int, _col: int) -> None:
        item = self.table.item(row, 0)
        if not item:
            return
        self.selected_id = int(item.data(Qt.UserRole))
        person = self.window.person_repo.get(self.selected_id)
        if not person:
            return
        self.name.setText(person["name"])
        self.display_name.setText(person.get("display_name") or "")
        self.name_kana.setText(person.get("name_kana") or "")
        self.resident_type.setCurrentText(RESIDENT_LABELS.get(person["resident_type"], "居住者"))
        self.daily_gross.setValue(int(person["daily_gross_amount"]))
        self.color.setText(person.get("color") or "#dbeafe")
        self.active.setChecked(bool(person["active"]))
        self.update_auto_amounts()

    def clear_form(self) -> None:
        self.selected_id = None
        self.name.clear()
        self.display_name.clear()
        self.name_kana.clear()
        self.resident_type.setCurrentIndex(0)
        self.daily_gross.setValue(max(10000, self.window.config.default_daily_gross_amount))
        self.color.setText("#dbeafe")
        self.active.setChecked(True)
        self.update_auto_amounts()

    def refresh(self) -> None:
        rows = self.window.person_service.list(active_only=False)
        headers = ["氏名", "表示名", "区分", "税率", "日額(総額)", "日額(手取)", "色", "状態"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(rows))
        for r, person in enumerate(rows):
            values = [
                person["name"],
                person.get("display_name") or "",
                RESIDENT_LABELS.get(person["resident_type"], person["resident_type"]),
                decimal_text(self.tax_rate_for_person(person), 4),
                money(person["daily_gross_amount"]),
                money(self.daily_net_for_person(person)),
                person.get("color") or "",
                "有効" if person["active"] else "停止",
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if c == 0:
                    item.setData(Qt.UserRole, person["person_id"])
                if person.get("color"):
                    item.setBackground(QColor(person["color"]))
                self.table.setItem(r, c, item)
        finish_table(self.table)

    def tax_rate_for_person(self, person: dict) -> float:
        if person.get("resident_type") == "nonresident":
            return self.window.config.nonresident_tax_rate
        return self.window.config.resident_tax_rate

    def daily_net_for_person(self, person: dict) -> float:
        return calc_from_gross(person["daily_gross_amount"], self.tax_rate_for_person(person))["net_amount"]


class RecordPage(BasePage):
    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.displayed_rows: list[dict] = []
        layout = QVBoxLayout(self)
        input_box = QGroupBox("案件入力")
        form = QGridLayout(input_box)
        self.record_date = QDateEdit()
        self.record_date.setCalendarPopup(True)
        self.record_date.setDate(QDate.currentDate())
        self.person = QComboBox()
        self.item_name = QLineEdit()
        self.amount = QDoubleSpinBox()
        self.amount.setRange(-100000000, 100000000)
        self.amount.setDecimals(0)
        self.record_type = QComboBox()
        self.record_type.addItems(RECORD_TYPES.keys())
        self.memo = QLineEdit()
        save_btn = QPushButton("登録")
        save_btn.clicked.connect(self.create_record)

        form.addWidget(QLabel("日付"), 0, 0)
        form.addWidget(self.record_date, 0, 1)
        form.addWidget(QLabel("人"), 0, 2)
        form.addWidget(self.person, 0, 3)
        form.addWidget(QLabel("名目"), 1, 0)
        form.addWidget(self.item_name, 1, 1)
        form.addWidget(QLabel("金額"), 1, 2)
        form.addWidget(self.amount, 1, 3)
        form.addWidget(QLabel("種類"), 2, 0)
        form.addWidget(self.record_type, 2, 1)
        form.addWidget(QLabel("備考"), 2, 2)
        form.addWidget(QLabel("その他を選択する場合必ず備考を入力してください"), 3, 1)
        form.addWidget(self.memo, 2, 3)
        form.addWidget(save_btn, 3, 3)

        filter_box = QGroupBox("検索")
        filters = QHBoxLayout(filter_box)
        self.filter_year = QSpinBox()
        self.filter_year.setRange(2000, 2100)
        self.filter_year.setValue(window.config.fiscal_year)
        self.filter_month = QComboBox()
        self.filter_person = QComboBox()
        self.filter_type = QComboBox()
        self.filter_type.addItem("すべて", "")
        for label, value in RECORD_TYPES.items():
            self.filter_type.addItem(label, value)
        self.keyword = QLineEdit()
        self.keyword.setPlaceholderText("名目・備考")
        search_btn = QPushButton("検索")
        search_btn.clicked.connect(self.refresh)
        filters.addWidget(QLabel("年度"))
        filters.addWidget(self.filter_year)
        filters.addWidget(QLabel("月"))
        filters.addWidget(self.filter_month)
        filters.addWidget(QLabel("人"))
        filters.addWidget(self.filter_person)
        filters.addWidget(QLabel("種類"))
        filters.addWidget(self.filter_type)
        filters.addWidget(self.keyword)
        filters.addWidget(search_btn)

        self.table = make_table()
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_context_menu)
        layout.addWidget(input_box)
        layout.addWidget(filter_box)
        layout.addWidget(self.table, 1)
        self.refresh_people()
        self.refresh()

    def refresh_people(self) -> None:
        current = self.person.currentData()
        self.person.clear()
        self.filter_person.clear()
        self.filter_person.addItem("すべて", None)
        for person in self.window.person_service.list(active_only=False):
            label = person["name"] + ("" if person["active"] else "（停止）")
            if person["active"]:
                self.person.addItem(person["name"], person["person_id"])
            self.filter_person.addItem(label, person["person_id"])
        if current:
            idx = self.person.findData(current)
            if idx >= 0:
                self.person.setCurrentIndex(idx)
        self.filter_month.clear()
        self.filter_month.addItem("すべて", "")
        for month in fiscal_months(self.filter_year.value()):
            self.filter_month.addItem(month, month)

    def create_record(self) -> None:
        if self.person.currentData() is None:
            self.window.show_error("人員を先に登録してください。")
            return
        qdate = self.record_date.date()
        values = {
            "record_date": date(qdate.year(), qdate.month(), qdate.day()),
            "person_id": self.person.currentData(),
            "item_name": self.item_name.text().strip(),
            "amount": self.amount.value(),
            "record_type": RECORD_TYPES[self.record_type.currentText()],
            "memo": self.memo.text().strip(),
        }
        try:
            summary = f"{values['record_date']} / {self.person.currentText()} / {values['item_name']} / {money(values['amount'])}円"
            if QMessageBox.question(self, "確認", f"登録しますか？\n{summary}") != QMessageBox.Yes:
                return
            self.window.record_service.create(values)
            self.item_name.clear()
            self.amount.setValue(0)
            self.memo.clear()
            self.window.refresh_all()
            self.window.set_app_status("ok", "案件を登録しました。", 7000)
        except Exception as exc:
            self.window.show_error(str(exc))

    def refresh(self) -> None:
        self.refresh_people()
        filters = {
            "fiscal_year": self.filter_year.value(),
            "target_month": self.filter_month.currentData(),
            "person_id": self.filter_person.currentData(),
            "record_type": self.filter_type.currentData(),
            "keyword": self.keyword.text().strip(),
        }
        rows = self.window.record_service.list(filters)
        self.displayed_rows = rows
        headers = ["日付", "人", "名目", "金額", "種類", "年度", "対象月", "備考"]
        set_rows(
            self.table,
            headers,
            [
                [
                    row["record_date"],
                    row["person_name"],
                    row["item_name"],
                    money(row["amount"]),
                    RECORD_TYPE_LABELS.get(row["record_type"], row["record_type"]),
                    row["fiscal_year"],
                    row["target_month"],
                    row.get("memo") or "",
                ]
                for row in rows
            ],
            row_colors=[row.get("color") or "" for row in rows],
        )

    def open_context_menu(self, position) -> None:
        row = self.table.rowAt(position.y())
        selected_rows = {index.row() for index in self.table.selectionModel().selectedRows()}
        if row >= 0 and row not in selected_rows:
            self.table.selectRow(row)
        menu = QMenu(self)
        delete_action = menu.addAction("選択行を削除")
        action = menu.exec_(self.table.viewport().mapToGlobal(position))
        if action == delete_action:
            self.delete_selected_records()

    def delete_selected_records(self) -> None:
        selected_rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        if not selected_rows:
            self.window.show_error("削除する案件を選択してください。")
            return
        record_ids = [
            int(self.displayed_rows[row]["record_id"])
            for row in selected_rows
            if row < len(self.displayed_rows)
        ]
        if not record_ids:
            self.window.show_error("削除対象を確認できません。")
            return
        if QMessageBox.warning(self, "確認", f"{len(record_ids)}件の案件を削除しますか？", QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        if not self.window.verify_delete_password():
            return
        try:
            self.window.record_service.delete_many(record_ids)
            self.window.refresh_all()
            self.window.set_app_status("ok", "選択案件を削除しました。", 7000)
        except Exception as exc:
            self.window.show_error(str(exc))


class PersonalDetailPage(BasePage):
    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.displayed_events: list[dict] = []
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.year = QSpinBox()
        self.year.setRange(2000, 2100)
        self.year.setValue(window.config.fiscal_year)
        self.person = QComboBox()
        refresh_btn = QPushButton("表示")
        delete_btn = QPushButton("選択行を削除")
        refresh_btn.clicked.connect(self.refresh)
        delete_btn.clicked.connect(self.delete_selected_rows)
        controls.addWidget(QLabel("年度"))
        controls.addWidget(self.year)
        controls.addWidget(QLabel("人"))
        controls.addWidget(self.person)
        controls.addWidget(refresh_btn)
        controls.addWidget(delete_btn)
        controls.addStretch()
        self.summary = QLabel("")
        self.table = make_table()
        layout.addLayout(controls)
        layout.addWidget(self.summary)
        layout.addWidget(self.table, 1)
        self.refresh()

    def refresh(self) -> None:
        current = self.person.currentData()
        self.person.clear()
        for person in self.window.person_service.list(active_only=False):
            self.person.addItem(person["name"], person["person_id"])
        if current:
            idx = self.person.findData(current)
            if idx >= 0:
                self.person.setCurrentIndex(idx)
        person_id = self.person.currentData()
        if person_id is None:
            set_rows(self.table, [], [])
            self.displayed_events = []
            return
        records = self.window.record_service.list({"fiscal_year": self.year.value(), "person_id": person_id})
        payments = self.window.payment_repo.list({"fiscal_year": self.year.value(), "person_id": person_id})
        events = []
        for row in records:
            is_manual_payment = row["record_type"] in ("payment", "支給")
            events.append(
                {
                    "date": row["record_date"],
                    "item": row["item_name"],
                    "amount": 0 if is_manual_payment else row["amount"],
                    "type": RECORD_TYPE_LABELS.get(row["record_type"], row["record_type"]),
                    "days": 0,
                    "gross": 0,
                    "tax": 0,
                    "net": row["amount"] if is_manual_payment else 0,
                    "source": "record",
                    "record_id": row["record_id"],
                }
            )
        for row in payments:
            events.append(
                {
                    "date": row["target_month"],
                    "item": "月次支給",
                    "amount": 0,
                    "type": row["status"],
                    "days": row["payment_days"],
                    "gross": row["gross_amount"],
                    "tax": row["withholding_amount"],
                    "net": row["net_amount"],
                    "source": "payment",
                    "person_id": row["person_id"],
                    "fiscal_year": row["fiscal_year"],
                    "target_month": row["target_month"],
                }
            )
        events.sort(key=lambda row: row["date"])
        self.displayed_events = events
        balance = 0.0
        table_rows = []
        total_added = 0.0
        total_net = 0.0
        total_days = 0.0
        for event in events:
            balance += float(event["amount"] or 0) - float(event["net"] or 0)
            total_added += float(event["amount"] or 0)
            total_net += float(event["net"] or 0)
            total_days += float(event["days"] or 0)
            table_rows.append(
                [
                    event["date"],
                    event["item"],
                    money(event["amount"]),
                    event["type"],
                    decimal_text(event["days"], 2),
                    money(event["gross"]),
                    money(event["tax"]),
                    money(event["net"]),
                    money(balance),
                ]
            )
        self.summary.setText(
            f"累積利用額: {money(total_added)}円    累積支給日数: {decimal_text(total_days, 2)}    "
            f"累積支給額: {money(total_net)}円    現在残額: {money(balance)}円"
        )
        set_rows(
            self.table,
            ["日付/月", "名目", "金額", "種類/状態", "支給日数", "支払総額", "源泉徴収額", "手取額", "残額"],
            table_rows,
            row_colors=[self.window.color_for_person_id(person_id) for _ in table_rows],
        )

    def delete_selected_rows(self) -> None:
        selected_rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        if not selected_rows:
            self.window.show_error("削除する明細行を選択してください。")
            return
        target_events = [self.displayed_events[row] for row in selected_rows if row < len(self.displayed_events)]
        if not target_events:
            self.window.show_error("削除対象を確認できません。")
            return
        if QMessageBox.warning(self, "確認", f"{len(target_events)}行を削除しますか？", QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        if not self.window.verify_delete_password():
            return
        try:
            record_ids = [int(row["record_id"]) for row in target_events if row["source"] == "record"]
            payment_rows = [row for row in target_events if row["source"] == "payment"]
            if record_ids:
                self.window.record_service.delete_many(record_ids)
            if payment_rows:
                self.window.closing_service.delete_rows(payment_rows)
            self.window.refresh_all()
            self.window.set_app_status("ok", "選択明細を削除しました。", 7000)
        except Exception as exc:
            self.window.show_error(str(exc))


class MonthlyClosingPage(BasePage):
    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.preview_rows: list[dict] = []
        self.displayed_rows: list[dict] = []
        layout = QVBoxLayout(self)
        controls = QGridLayout()
        self.year = QSpinBox()
        self.year.setRange(2000, 2100)
        self.year.setValue(window.config.fiscal_year)
        self.month = QComboBox()
        self.mode = QComboBox()
        self.mode.addItems(MODES.keys())
        self.days = QDoubleSpinBox()
        self.days.setRange(0.5, 7)
        self.days.setSingleStep(0.5)
        self.days.setValue(0.5)
        self.ratio = QDoubleSpinBox()
        self.ratio.setRange(0, 1)
        self.ratio.setSingleStep(0.05)
        self.ratio.setValue(1)
        self.manual = QDoubleSpinBox()
        self.manual.setRange(0, 100000000)
        self.manual.setDecimals(0)
        self.persons = QListWidget()
        self.persons.setSelectionMode(QAbstractItemView.MultiSelection)
        self.persons.setMaximumHeight(120)
        preview_btn = QPushButton("計算プレビュー")
        save_btn = QPushButton("下書き保存")
        confirm_btn = QPushButton("確定")
        draft_btn = QPushButton("確定取消")
        delete_btn = QPushButton("選択行を削除")
        preview_btn.clicked.connect(self.preview)
        save_btn.clicked.connect(lambda: self.save("draft"))
        confirm_btn.clicked.connect(lambda: self.save("confirmed"))
        draft_btn.clicked.connect(self.cancel_confirm)
        delete_btn.clicked.connect(self.delete_selected_rows)

        controls.addWidget(QLabel("年度"), 0, 0)
        controls.addWidget(self.year, 0, 1)
        controls.addWidget(QLabel("対象月"), 0, 2)
        controls.addWidget(self.month, 0, 3)
        controls.addWidget(QLabel("計算モード"), 1, 0)
        controls.addWidget(self.mode, 1, 1)
        controls.addWidget(QLabel("支給日数"), 1, 2)
        controls.addWidget(self.days, 1, 3)
        controls.addWidget(QLabel("分配割合"), 2, 0)
        controls.addWidget(self.ratio, 2, 1)
        controls.addWidget(QLabel("手取額"), 2, 2)
        controls.addWidget(self.manual, 2, 3)
        controls.addWidget(QLabel("人員（未選択なら全員）"), 3, 0)
        controls.addWidget(self.persons, 3, 1, 1, 3)
        button_row = QHBoxLayout()
        for btn in [preview_btn, save_btn, confirm_btn, draft_btn, delete_btn]:
            button_row.addWidget(btn)
        button_row.addStretch()
        self.table = make_table()
        layout.addLayout(controls)
        layout.addLayout(button_row)
        layout.addWidget(self.table, 1)
        self.year.valueChanged.connect(self.refresh_months)
        self.refresh()

    def refresh_months(self) -> None:
        current = self.month.currentData()
        self.month.clear()
        for month in fiscal_months(self.year.value()):
            self.month.addItem(month, month)
        if current:
            idx = self.month.findData(current)
            if idx >= 0:
                self.month.setCurrentIndex(idx)

    def selected_person_ids(self) -> list[int]:
        return [int(item.data(Qt.UserRole)) for item in self.persons.selectedItems()]

    def preview(self) -> None:
        try:
            self.preview_rows = self.window.closing_service.preview(
                self.year.value(),
                self.month.currentData(),
                self.selected_person_ids(),
                MODES[self.mode.currentText()],
                self.days.value(),
                self.ratio.value(),
                self.manual.value(),
            )
            self.show_preview()
            if any(row["after_balance"] < 0 for row in self.preview_rows):
                self.window.set_app_status("warning", "残額がマイナスの行があります。", 10000)
            else:
                self.window.set_app_status("ok", "月次精算プレビューを作成しました。", 7000)
        except Exception as exc:
            self.window.show_error(str(exc))

    def save(self, status: str) -> None:
        if not self.preview_rows:
            self.preview()
        negative = any(row["after_balance"] < 0 for row in self.preview_rows)
        if negative:
            self.window.set_app_status("warning", "残額がマイナスの行があります。", 10000)
            if QMessageBox.warning(self, "確認", "残額がマイナスの行があります。保存しますか？", QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                return
        self.window.closing_service.save_rows(self.preview_rows, status)
        self.window.refresh_all()
        self.window.show_info("保存しました。")

    def cancel_confirm(self) -> None:
        self.window.closing_service.set_status_for_month(self.year.value(), self.month.currentData(), "draft")
        self.window.refresh_all()

    def delete_selected_rows(self) -> None:
        selected_rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        if not selected_rows:
            self.window.show_error("削除する行を選択してください。")
            return
        target_rows = [self.displayed_rows[index] for index in selected_rows if index < len(self.displayed_rows)]
        if not target_rows:
            self.window.show_error("削除対象を確認できません。")
            return
        if QMessageBox.warning(self, "確認", f"{len(target_rows)}行を削除しますか？", QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        if not self.window.verify_delete_password():
            return
        self.window.closing_service.delete_rows(target_rows)
        target_keys = {(row["person_id"], row["fiscal_year"], row["target_month"]) for row in target_rows}
        self.preview_rows = [
            row for row in self.preview_rows
            if (row["person_id"], row["fiscal_year"], row["target_month"]) not in target_keys
        ]
        if self.preview_rows:
            self.show_preview()
        else:
            self.refresh()
        self.window.set_app_status("ok", "選択行を削除しました。", 7000)

    def show_preview(self) -> None:
        rows = []
        for row in self.preview_rows:
            rows.append(
                [
                    row["person_name"],
                    money(row["previous_balance"]),
                    money(row["monthly_added_amount"]),
                    money(row["before_payment_balance"]),
                    decimal_text(row["payment_days"], 2),
                    money(row["gross_amount"]),
                    money(row["withholding_amount"]),
                    money(row["net_amount"]),
                    money(row["after_balance"]),
                    row["status"],
                ]
            )
        set_rows(
            self.table,
            ["人", "前月残額", "当月追加", "支給前残額", "支給日数", "支払総額", "源泉徴収額", "手取額", "月末残額", "状態"],
            rows,
            row_colors=[self.window.color_for_person_id(row["person_id"]) for row in self.preview_rows],
        )
        self.displayed_rows = list(self.preview_rows)
        for r, row in enumerate(self.preview_rows):
            if row["after_balance"] < 0:
                paint_row(self.table, r, QColor("#f4cccc"))

    def refresh(self) -> None:
        self.refresh_months()
        self.persons.clear()
        for person in self.window.person_service.list(active_only=True):
            item = QListWidgetItem(person["name"])
            item.setData(Qt.UserRole, person["person_id"])
            self.persons.addItem(item)
        rows = self.window.payment_repo.list({"fiscal_year": self.year.value(), "target_month": self.month.currentData()})
        rows = self.window.closing_service.recalculate_saved_rows(rows)
        self.displayed_rows = rows
        set_rows(
            self.table,
            ["人", "前月残額", "当月追加", "支給前残額", "支給日数", "支払総額", "源泉徴収額", "手取額", "月末残額", "状態"],
            [
                [
                    row["person_name"],
                    money(row["previous_balance"]),
                    money(row["monthly_added_amount"]),
                    money(row["before_payment_balance"]),
                    decimal_text(row["payment_days"], 2),
                    money(row["gross_amount"]),
                    money(row["withholding_amount"]),
                    money(row["net_amount"]),
                    money(row["after_balance"]),
                    row["status"],
                ]
                for row in rows
            ],
            row_colors=[row.get("color") or "" for row in rows],
        )


class SummaryPage(BasePage):
    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.overview_rows: list[dict] = []
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.year = QSpinBox()
        self.year.setRange(2000, 2100)
        self.year.setValue(window.config.fiscal_year)
        refresh_btn = QPushButton("更新")
        export_selected_btn = QPushButton("選択人員を出力")
        delete_selected_btn = QPushButton("選択人員を削除")
        refresh_btn.clicked.connect(self.refresh)
        export_selected_btn.clicked.connect(self.export_selected_people)
        delete_selected_btn.clicked.connect(self.delete_selected_people)
        self.people = QListWidget()
        self.people.setSelectionMode(QAbstractItemView.MultiSelection)
        self.people.setMaximumHeight(110)
        controls.addWidget(QLabel("年度"))
        controls.addWidget(self.year)
        controls.addWidget(QLabel("対象人員"))
        controls.addWidget(self.people)
        controls.addWidget(refresh_btn)
        controls.addWidget(export_selected_btn)
        controls.addWidget(delete_selected_btn)
        controls.addStretch()
        self.tabs = QTabWidget()
        self.overview = make_table()
        self.days = make_table()
        self.amounts = make_table()
        self.tabs.addTab(self.overview, "年度総覧")
        self.tabs.addTab(self.days, "月別支給日数")
        self.tabs.addTab(self.amounts, "月別支給額")
        layout.addLayout(controls)
        layout.addWidget(self.tabs, 1)
        self.refresh()

    def refresh(self) -> None:
        self.refresh_people()
        selected_ids = set(self.selected_person_ids())
        overview = self.window.summary_service.annual_overview(self.year.value())
        if selected_ids:
            overview = [row for row in overview if int(row["person_id"]) in selected_ids]
        self.overview_rows = overview
        set_rows(
            self.overview,
            ["人", "累積利用額", "累積支給日数", "累積支給額", "現在残額", "状態"],
            [
                [
                    row["person_name"],
                    money(row["total_added"]),
                    decimal_text(row["payment_days"], 2),
                    money(row["net_amount"]),
                    money(row["balance"]),
                    "有効" if row["active"] else "停止",
                ]
                for row in overview
            ],
            row_colors=[row.get("color") or "" for row in overview],
        )
        for r, row in enumerate(overview):
            if row["balance"] < 0:
                paint_row(self.overview, r, QColor("#f4cccc"))
        months, rows = self.window.summary_service.monthly_matrix(self.year.value(), "payment_days")
        if selected_ids:
            rows = [row for row in rows if int(row["person_id"]) in selected_ids]
        self._set_matrix(self.days, months, rows, is_money=False)
        months, rows = self.window.summary_service.monthly_matrix(self.year.value(), "net_amount")
        if selected_ids:
            rows = [row for row in rows if int(row["person_id"]) in selected_ids]
        self._set_matrix(self.amounts, months, rows, is_money=True)

    def refresh_people(self) -> None:
        selected = set(self.selected_person_ids())
        self.people.clear()
        for person in self.window.person_service.list(active_only=False):
            item = QListWidgetItem(person["name"] + ("" if person["active"] else "（停止）"))
            item.setData(Qt.UserRole, person["person_id"])
            self.people.addItem(item)
            if int(person["person_id"]) in selected:
                item.setSelected(True)

    def selected_person_ids(self) -> list[int]:
        return [int(item.data(Qt.UserRole)) for item in self.people.selectedItems()]

    def delete_selected_people(self) -> None:
        selected_ids = set(self.selected_person_ids())
        table_rows = {index.row() for index in self.overview.selectionModel().selectedRows()}
        for row_index in table_rows:
            if row_index < len(self.overview_rows):
                selected_ids.add(int(self.overview_rows[row_index]["person_id"]))
        if not selected_ids:
            self.window.show_error("削除する人員を選択してください。")
            return
        message = f"{len(selected_ids)}名を削除します。関連する案件・月次精算も削除されます。続行しますか？"
        if QMessageBox.warning(self, "確認", message, QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        if not self.window.verify_delete_password():
            return
        try:
            for person_id in selected_ids:
                self.window.person_service.delete(person_id)
            self.window.refresh_all()
            self.window.set_app_status("ok", "年度集計から選択人員を削除しました。", 7000)
        except Exception as exc:
            self.window.show_error(str(exc))

    def export_selected_people(self) -> None:
        selected_ids = set(self.selected_person_ids())
        if not selected_ids:
            self.window.set_app_status("warning", "出力する人員を選択してください。", 10000)
            QMessageBox.warning(self, "警告", "出力する人員を選択してください。")
            return
        default_path = str(Path(self.window.config.default_export_path) / f"summary_selected_{self.year.value()}.xlsx")
        path, _ = QFileDialog.getSaveFileName(self, "保存先", default_path, "Excel files (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            self.window.set_app_status("busy", "選択人員のExcel出力中...")
            fiscal_year = self.year.value()
            records = [
                row for row in self.window.record_service.list({"fiscal_year": fiscal_year})
                if int(row["person_id"]) in selected_ids
            ]
            overview = [
                row for row in self.window.summary_service.annual_overview(fiscal_year)
                if int(row["person_id"]) in selected_ids
            ]
            payments = [
                row for row in self.window.payment_repo.list({"fiscal_year": fiscal_year})
                if int(row["person_id"]) in selected_ids
            ]
            output = ExcelExporter().export(path, fiscal_year, records, overview, payments)
            self.window.logs_repo.add("INFO", "SELECTED_PEOPLE_EXPORTED", f"Selected people exported: {output}")
            self.window.set_app_status("ok", f"選択人員を出力しました: {output}", 7000)
        except PermissionError as exc:
            self.window.logs_repo.add("WARNING", "SELECTED_EXPORT_PERMISSION_DENIED", str(exc))
            self.window.set_app_status("warning", f"保存できません。Excelファイルが開かれている可能性があります: {exc}", 10000)
            QMessageBox.warning(self, "警告", str(exc))
        except Exception as exc:
            self.window.logs_repo.add("ERROR", "SELECTED_EXPORT_FAILED", str(exc))
            self.window.show_error(str(exc))

    def _set_matrix(self, table: QTableWidget, months: list[str], rows: list[dict], is_money: bool) -> None:
        headers = ["人"] + [month_label(month) for month in months] + ["合計"]
        data = []
        for row in rows:
            values = [money(row[m]) if is_money else decimal_text(row[m], 2) for m in months]
            total = money(row["total"]) if is_money else decimal_text(row["total"], 2)
            data.append([row["person_name"]] + values + [total])
        set_rows(table, headers, data, row_colors=[row.get("color") or "" for row in rows])


class TaxCalculatorPage(BasePage):
    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        layout = QVBoxLayout(self)
        form_box = QGroupBox("税額計算")
        form = QFormLayout(form_box)
        self.kind = QComboBox()
        self.kind.addItems(["居住者", "非居住者"])
        self.direction = QComboBox()
        self.direction.addItems(["支払総額から計算", "手取額から逆算"])
        self.amount = QDoubleSpinBox()
        self.amount.setRange(0, 100000000)
        self.amount.setDecimals(0)
        self.amount.setValue(10000)
        self.amount.setSingleStep(100)
        calc_btn = QPushButton("計算")
        calc_btn.clicked.connect(self.calculate)
        self.result = QLabel("")
        self.result.setTextFormat(Qt.RichText)
        self.result.setStyleSheet("QLabel { font-size: 18px; line-height: 1.45; }")
        form.addRow("区分", self.kind)
        form.addRow("計算方法", self.direction)
        form.addRow("金額", self.amount)
        form.addRow(calc_btn)
        form.addRow("結果", self.result)
        layout.addWidget(form_box)
        layout.addStretch()
        self.calculate()

    def calculate(self) -> None:
        rate = self.window.config.nonresident_tax_rate if self.kind.currentText() == "非居住者" else self.window.config.resident_tax_rate
        if self.direction.currentText().startswith("支払"):
            result = calc_from_gross(self.amount.value(), rate)
        else:
            result = calc_from_net(self.amount.value(), rate)
        red = "#dc2626"
        self.result.setText(
            "<div>"
            f"税率: <span style='color:{red}; font-weight:700;'>{rate:.4f}</span><br>"
            f"支払総額: <span style='color:{red}; font-weight:700;'>{money(result['gross_amount'])}円</span><br>"
            f"源泉徴収額: <span style='color:{red}; font-weight:700;'>{money(result['withholding_amount'])}円</span><br>"
            f"手取額: <span style='color:{red}; font-weight:700;'>{money(result['net_amount'])}円</span>"
            "</div>"
        )


class ExportPage(BasePage):
    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        layout = QVBoxLayout(self)
        form_box = QGroupBox("Excel出力")
        form = QGridLayout(form_box)
        self.year = QSpinBox()
        self.year.setRange(2000, 2100)
        self.year.setValue(window.config.fiscal_year)
        self.path = QLineEdit(str(Path(window.config.default_export_path) / f"lab_accounting_{window.config.fiscal_year}.xlsx"))
        browse_btn = QPushButton("保存先")
        browse_btn.clicked.connect(self.browse)
        self.include_records = QCheckBox("案件入力")
        self.include_summary = QCheckBox("Summary")
        self.include_payments = QCheckBox("個人別支給額")
        self.include_items = QCheckBox("使用費目一覧")
        self.include_tax = QCheckBox("税額計算表")
        for box in [self.include_records, self.include_summary, self.include_payments, self.include_items, self.include_tax]:
            box.setChecked(True)
        self.people = QListWidget()
        self.people.setSelectionMode(QAbstractItemView.MultiSelection)
        self.people.setMaximumHeight(130)
        export_btn = QPushButton("出力")
        export_btn.clicked.connect(self.export)
        form.addWidget(QLabel("年度"), 0, 0)
        form.addWidget(self.year, 0, 1)
        form.addWidget(QLabel("保存先"), 1, 0)
        form.addWidget(self.path, 1, 1)
        form.addWidget(browse_btn, 1, 2)
        form.addWidget(self.include_records, 2, 0)
        form.addWidget(self.include_summary, 2, 1)
        form.addWidget(self.include_payments, 2, 2)
        form.addWidget(self.include_items, 3, 0)
        form.addWidget(self.include_tax, 3, 1)
        form.addWidget(QLabel("対象人員（未選択なら全員）"), 4, 0)
        form.addWidget(self.people, 4, 1, 1, 2)
        form.addWidget(export_btn, 5, 2)
        self.message = QLabel("")
        layout.addWidget(form_box)
        layout.addWidget(self.message)
        layout.addStretch()
        self.refresh()

    def refresh(self) -> None:
        selected = set(self.selected_person_ids())
        self.people.clear()
        for person in self.window.person_service.list(active_only=False):
            item = QListWidgetItem(person["name"] + ("" if person["active"] else "（停止）"))
            item.setData(Qt.UserRole, person["person_id"])
            self.people.addItem(item)
            if int(person["person_id"]) in selected:
                item.setSelected(True)

    def selected_person_ids(self) -> list[int]:
        return [int(item.data(Qt.UserRole)) for item in self.people.selectedItems()]

    def browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "保存先", self.path.text(), "Excel files (*.xlsx)")
        if path:
            if not path.lower().endswith(".xlsx"):
                path += ".xlsx"
            self.path.setText(path)

    def export(self) -> None:
        try:
            self.window.set_app_status("busy", "Excel出力中...")
            fiscal_year = self.year.value()
            selected_ids = set(self.selected_person_ids())
            records = self.window.record_service.list({"fiscal_year": fiscal_year})
            overview = self.window.summary_service.annual_overview(fiscal_year)
            payments = self.window.payment_repo.list({"fiscal_year": fiscal_year})
            if selected_ids:
                records = [row for row in records if int(row["person_id"]) in selected_ids]
                overview = [row for row in overview if int(row["person_id"]) in selected_ids]
                payments = [row for row in payments if int(row["person_id"]) in selected_ids]
            output = ExcelExporter().export(
                self.path.text(),
                fiscal_year,
                records,
                overview,
                payments,
                self.include_records.isChecked(),
                self.include_summary.isChecked(),
                self.include_payments.isChecked(),
                self.include_items.isChecked(),
                self.include_tax.isChecked(),
            )
            self.window.logs_repo.add("INFO", "EXCEL_EXPORTED", f"Excel exported: {output}")
            self.message.setText(f"出力しました: {output}")
            self.window.refresh_all()
            self.window.set_app_status("ok", f"Excelを出力しました: {output}", 7000)
        except PermissionError as exc:
            self.window.logs_repo.add("WARNING", "EXCEL_EXPORT_PERMISSION_DENIED", str(exc))
            self.window.set_app_status(
                "warning",
                f"保存できません。Excelファイルが開かれている可能性があります: {exc}",
                10000,
            )
            QMessageBox.warning(self, "警告", str(exc))
        except Exception as exc:
            self.window.logs_repo.add("ERROR", "EXCEL_EXPORT_FAILED", str(exc))
            self.window.show_error(str(exc))


class LogViewerPage(BasePage):
    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.level = QComboBox()
        self.level.addItem("すべて", "")
        for level in ["INFO", "WARNING", "ERROR"]:
            self.level.addItem(level, level)
        self.keyword = QLineEdit()
        self.keyword.setPlaceholderText("キーワード")
        refresh_btn = QPushButton("更新")
        refresh_btn.clicked.connect(self.refresh)
        controls.addWidget(QLabel("レベル"))
        controls.addWidget(self.level)
        controls.addWidget(self.keyword)
        controls.addWidget(refresh_btn)
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        bottom_row = QHBoxLayout()
        self.time_label = QLabel("")
        bottom_row.addWidget(self.time_label)
        bottom_row.addStretch()
        self.time_timer = QTimer(self)
        self.time_timer.timeout.connect(self.update_time_label)
        self.time_timer.start(1000)
        layout.addLayout(controls)
        layout.addWidget(self.text, 1)
        layout.addLayout(bottom_row)
        self.update_time_label()
        self.refresh()

    def refresh(self) -> None:
        logs = self.window.log_service.list(self.level.currentData() or "", self.keyword.text().strip())
        lines = [
            f"{idx + 1:04d}  [{row['event_level']}] {row['event_time']}  {row['event_type']}  {row['message']}"
            for idx, row in enumerate(logs)
        ]
        self.text.setPlainText("\n".join(lines))

    def update_time_label(self) -> None:
        self.time_label.setText(datetime.now(JST).strftime("JST %Y-%m-%d %H:%M:%S"))


class SettingsPage(BasePage):
    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        layout = QVBoxLayout(self)
        info = QTextEdit()
        info.setReadOnly(True)
        info.setPlainText(
            "\n".join(
                [
                    "設定",
                    f"データベース: {window.config.database_path}",
                    f"バックアップ先: {window.config.backup_path}",
                    f"自動バックアップ間隔: {window.config.auto_backup_interval_minutes}分",
                    f"年度開始月: {window.config.fiscal_year_start_month}月",
                    f"居住者税率: {window.config.resident_tax_rate}",
                    f"非居住者税率: {window.config.nonresident_tax_rate}",
                    f"既定日額(支払総額): {window.config.default_daily_gross_amount}円",
                    "手取額: 区分と日額(支払総額)から自動計算",
                    "",
                    "このMVP版では設定ファイル config/app_config.json を編集して変更します。",
                    "Bugやシステムの不具合がありましたら、Githubでhttps://github.com/KAMININAROU/lab-accountantのIssueでご報告ください。",
                ]
            )
        )
        backup_box = QGroupBox("バックアップ")
        backup_layout = QGridLayout(backup_box)
        backup_now_btn = QPushButton("今すぐバックアップ")
        restore_btn = QPushButton("バックアップを読み込む")
        backup_hint = QLabel("自動バックアップは7分ごとに作成されます。")
        self.backup_status = QLabel("")
        backup_now_btn.clicked.connect(self.create_backup_now)
        restore_btn.clicked.connect(self.restore_backup)
        backup_layout.addWidget(backup_now_btn, 0, 0)
        backup_layout.addWidget(restore_btn, 0, 1)
        backup_layout.addWidget(backup_hint, 1, 0, 1, 2)
        backup_layout.addWidget(self.backup_status, 2, 0, 1, 2)
        layout.addWidget(info)
        layout.addWidget(backup_box)

    def create_backup_now(self) -> None:
        try:
            self.window.set_app_status("busy", "バックアップ作成中...")
            path = self.window.backup_service.create_backup("manual")
            self.window.logs_repo.add("INFO", "MANUAL_BACKUP_CREATED", f"Manual backup created: {path}")
            self.backup_status.setText(f"作成しました: {path}")
            self.window.set_app_status("ok", "バックアップを作成しました。", 7000)
        except Exception as exc:
            self.window.logs_repo.add("ERROR", "MANUAL_BACKUP_FAILED", str(exc))
            self.window.show_error(str(exc))

    def restore_backup(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "バックアップを選択",
            self.window.config.backup_path,
            "SQLite backup (*.db);;All files (*)",
        )
        if not path:
            return
        message = "選択したバックアップを読み込みます。現在のデータは読み込み前にバックアップされます。続行しますか？"
        if QMessageBox.warning(self, "確認", message, QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            self.window.set_app_status("busy", "バックアップ読込中...")
            before_restore = self.window.backup_service.restore_backup(path)
            self.window.db.initialize()
            self.window.logs_repo.add("INFO", "BACKUP_RESTORED", f"Backup restored: {path}")
            self.window.refresh_all()
            self.backup_status.setText(f"読み込みました: {path}\n復元前バックアップ: {before_restore}")
            self.window.show_info("バックアップを読み込みました。")
        except Exception as exc:
            self.window.logs_repo.add("ERROR", "BACKUP_RESTORE_FAILED", str(exc))
            self.window.show_error(str(exc))


def make_table() -> QTableWidget:
    table = QTableWidget()
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.ExtendedSelection)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    return table


def set_rows(
    table: QTableWidget,
    headers: list[str],
    rows: list[list[object]],
    row_colors: list[str] | None = None,
) -> None:
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        row_color = QColor(row_colors[r]) if row_colors and r < len(row_colors) and row_colors[r] else None
        for c, value in enumerate(row):
            item = QTableWidgetItem(str(value))
            if c > 0:
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter if is_number_text(str(value)) else Qt.AlignLeft | Qt.AlignVCenter)
            if row_color and row_color.isValid():
                item.setBackground(row_color)
            table.setItem(r, c, item)
    finish_table(table)


def finish_table(table: QTableWidget) -> None:
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    table.horizontalHeader().setMinimumSectionSize(90)
    table.resizeColumnsToContents()
    table.horizontalHeader().setStretchLastSection(False)


def paint_row(table: QTableWidget, row: int, color: QColor) -> None:
    for col in range(table.columnCount()):
        item = table.item(row, col)
        if item:
            item.setBackground(color)


def is_number_text(text: str) -> bool:
    if not text:
        return False
    return text.replace(",", "").replace(".", "").replace("-", "").isdigit()
