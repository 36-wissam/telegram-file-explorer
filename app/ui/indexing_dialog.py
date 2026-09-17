"""Dialog providing comprehensive controls and real-time feedback for chat indexing."""

from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core.logger import get_logger
from ..services.indexing_manager import IndexingManager, IndexingProgress, IndexingStatus
from ..telegram.chats import TelegramChat
from .icons import get_icon

logger = get_logger("ui.indexing_dialog")


class IndexingDialog(QDialog):
    """Modern dialog for managing indexing operations: start, pause, resume, cancel, and live progress."""

    def __init__(
        self,
        manager: IndexingManager,
        available_chats: List[TelegramChat],
        preselected_chat_id: Optional[int] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.manager = manager
        self.available_chats = available_chats
        self.preselected_chat_id = preselected_chat_id

        self.setWindowTitle("Telegram Media Indexing Manager")
        self.setMinimumSize(620, 560)
        self.resize(680, 600)
        self._init_ui()
        self._connect_signals()
        self._update_controls_state()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        # Header with Title and Status Badge
        header_layout = QHBoxLayout()
        title_label = QLabel("Media Indexing Controls")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #ffffff;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        self.badge_status = QLabel("IDLE")
        self.badge_status.setStyleSheet(
            """
            QLabel {
                background-color: #2b2d31;
                color: #949ba4;
                border-radius: 6px;
                padding: 4px 12px;
                font-weight: bold;
                font-size: 11px;
            }
            """
        )
        header_layout.addWidget(self.badge_status)
        layout.addLayout(header_layout)

        # 1. Scope & Options Card
        opts_card = QFrame()
        opts_card.setStyleSheet(
            """
            QFrame {
                background-color: #1e1f22;
                border: 1px solid #2b2d31;
                border-radius: 8px;
                padding: 12px;
            }
            """
        )
        opts_layout = QVBoxLayout(opts_card)
        opts_layout.setSpacing(10)

        opts_title = QLabel("<b>Indexing Scope & Limits</b>")
        opts_title.setStyleSheet("color: #dbdee1; font-size: 12px;")
        opts_layout.addWidget(opts_title)

        # Radio Buttons
        self.scope_group = QButtonGroup(self)
        self.radio_all = QRadioButton(f"Index all accessible chats ({len(self.available_chats)} chats)")
        self.radio_selected = QRadioButton("Index single selected chat:")
        self.scope_group.addButton(self.radio_all)
        self.scope_group.addButton(self.radio_selected)

        opts_layout.addWidget(self.radio_all)

        # Chat combo layout
        chat_combo_layout = QHBoxLayout()
        chat_combo_layout.setContentsMargins(20, 0, 0, 0)
        chat_combo_layout.addWidget(self.radio_selected)

        self.combo_chats = QComboBox()
        for chat in self.available_chats:
            self.combo_chats.addItem(chat.title, chat.id)
        chat_combo_layout.addWidget(self.combo_chats, 1)
        opts_layout.addLayout(chat_combo_layout)

        # Preselect if specified
        if self.preselected_chat_id is not None:
            idx = self.combo_chats.findData(self.preselected_chat_id)
            if idx >= 0:
                self.combo_chats.setCurrentIndex(idx)
                self.radio_selected.setChecked(True)
            else:
                self.radio_all.setChecked(True)
        else:
            self.radio_all.setChecked(True)

        self.radio_all.toggled.connect(self._on_scope_toggled)

        # Limit & Options row
        settings_row = QHBoxLayout()
        settings_row.addWidget(QLabel("Scan limit per chat:"))
        self.spin_limit = QSpinBox()
        self.spin_limit.setRange(20, 50000)
        self.spin_limit.setSingleStep(100)
        self.spin_limit.setValue(500)
        settings_row.addWidget(self.spin_limit)

        settings_row.addSpacing(16)

        self.chk_reindex = QCheckBox("Force re-index (scan from beginning)")
        self.chk_reindex.setToolTip("Ignores saved checkpoints and scans chat messages again.")
        settings_row.addWidget(self.chk_reindex)
        settings_row.addStretch()

        opts_layout.addLayout(settings_row)
        layout.addWidget(opts_card)

        # 2. Real-Time Progress Card
        prog_card = QFrame()
        prog_card.setStyleSheet(
            """
            QFrame {
                background-color: #1e1f22;
                border: 1px solid #2b2d31;
                border-radius: 8px;
                padding: 12px;
            }
            """
        )
        prog_layout = QVBoxLayout(prog_card)
        prog_layout.setSpacing(8)

        self.lbl_status_msg = QLabel("Ready to index media.")
        self.lbl_status_msg.setStyleSheet("color: #dbdee1; font-size: 12px;")
        prog_layout.addWidget(self.lbl_status_msg)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                background-color: #2b2d31;
                border: none;
                border-radius: 4px;
                text-align: center;
                color: #ffffff;
                font-weight: bold;
                height: 18px;
            }
            QProgressBar::chunk {
                background-color: #00aff4;
                border-radius: 4px;
            }
            """
        )
        prog_layout.addWidget(self.progress_bar)

        # Stats summary row
        stats_layout = QHBoxLayout()
        self.lbl_chat_stat = QLabel("Chat: -")
        self.lbl_chat_stat.setStyleSheet("color: #949ba4; font-size: 11px;")
        stats_layout.addWidget(self.lbl_chat_stat)

        stats_layout.addStretch()

        self.lbl_files_stat = QLabel("Files Indexed: 0")
        self.lbl_files_stat.setStyleSheet("color: #00aff4; font-size: 11px; font-weight: bold;")
        stats_layout.addWidget(self.lbl_files_stat)

        stats_layout.addSpacing(16)

        self.lbl_msgs_stat = QLabel("Messages Scanned: 0")
        self.lbl_msgs_stat.setStyleSheet("color: #949ba4; font-size: 11px;")
        stats_layout.addWidget(self.lbl_msgs_stat)

        prog_layout.addLayout(stats_layout)
        layout.addWidget(prog_card)

        # 3. Live Log Output
        log_label = QLabel("<b>Live Indexing Activity:</b>")
        log_label.setStyleSheet("color: #949ba4; font-size: 11px;")
        layout.addWidget(log_label)

        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        self.text_log.setStyleSheet(
            """
            QTextEdit {
                background-color: #111214;
                color: #dbdee1;
                border: 1px solid #2b2d31;
                border-radius: 6px;
                font-family: Consolas, monospace;
                font-size: 11px;
                padding: 6px;
            }
            """
        )
        layout.addWidget(self.text_log, 1)

        # 4. Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_start = QPushButton("Start Indexing")
        self.btn_start.setIcon(get_icon('play', color='#ffffff', size=14))
        self.btn_start.setStyleSheet(
            """
            QPushButton {
                background-color: #00aff4;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #0098d4; }
            QPushButton:disabled { background-color: #35373c; color: #80848e; }
            """
        )
        self.btn_start.clicked.connect(self._on_start_clicked)
        btn_layout.addWidget(self.btn_start)

        self.btn_pause = QPushButton("Pause")
        self.btn_pause.setIcon(get_icon('pause', color='#ffffff', size=14))
        self.btn_pause.setStyleSheet(
            """
            QPushButton {
                background-color: #35373c;
                color: #ffffff;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #404249; }
            QPushButton:disabled { background-color: #2b2d31; color: #5c5e66; }
            """
        )
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self._on_pause_clicked)
        btn_layout.addWidget(self.btn_pause)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setIcon(get_icon('square', color='#ffffff', size=14))
        self.btn_cancel.setStyleSheet(
            """
            QPushButton {
                background-color: #da373c;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #b82e33; }
            QPushButton:disabled { background-color: #2b2d31; color: #5c5e66; }
            """
        )
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        btn_layout.addWidget(self.btn_cancel)

        btn_layout.addStretch()

        self.btn_close = QPushButton("Close")
        self.btn_close.setStyleSheet("padding: 8px 16px; font-size: 12px;")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

    def _connect_signals(self):
        self.manager.status_changed.connect(self._on_manager_status_changed)
        self.manager.progress_updated.connect(self._on_manager_progress_updated)
        self.manager.log_emitted.connect(self._append_log)
        self.manager.indexing_finished.connect(self._on_manager_indexing_finished)

    def _on_scope_toggled(self):
        self.combo_chats.setEnabled(self.radio_selected.isChecked())

    def _on_start_clicked(self):
        limit = self.spin_limit.value()
        reindex = self.chk_reindex.isChecked()

        if self.radio_all.isChecked():
            target_chats = list(self.available_chats)
        else:
            selected_chat_id = self.combo_chats.currentData()
            target_chats = [c for c in self.available_chats if c.id == selected_chat_id]

        if not target_chats:
            self._append_log("[Error] No chats selected to index.")
            return

        self.manager.start_indexing(target_chats, limit_per_chat=limit, reindex=reindex)
        self._update_controls_state()

    def _on_pause_clicked(self):
        if self.manager.is_paused:
            self.manager.resume_indexing()
        else:
            self.manager.pause_indexing()
        self._update_controls_state()

    def _on_cancel_clicked(self):
        self.manager.cancel_indexing()
        self._update_controls_state()

    def _on_manager_status_changed(self, status_val: str):
        self.badge_status.setText(status_val.upper())

        colors = {
            "RUNNING": ("#23a55a", "#ffffff"),
            "PAUSED": ("#f0b232", "#000000"),
            "COMPLETED": ("#00aff4", "#ffffff"),
            "CANCELLED": ("#da373c", "#ffffff"),
            "FAILED": ("#da373c", "#ffffff"),
            "IDLE": ("#2b2d31", "#949ba4"),
        }
        bg, fg = colors.get(status_val.upper(), ("#2b2d31", "#949ba4"))
        self.badge_status.setStyleSheet(
            f"QLabel {{ background-color: {bg}; color: {fg}; border-radius: 6px; padding: 4px 12px; font-weight: bold; font-size: 11px; }}"
        )
        self._update_controls_state(status_override=status_val)

    def _on_manager_progress_updated(self, prog: IndexingProgress):
        self.lbl_status_msg.setText(prog.status_message)
        if prog.total_chats > 0:
            pct = int((prog.chat_index / prog.total_chats) * 100)
            self.progress_bar.setValue(min(100, pct))
            self.lbl_chat_stat.setText(f"Chat: {prog.current_chat_title} ({prog.chat_index}/{prog.total_chats})")
        else:
            self.lbl_chat_stat.setText(f"Chat: {prog.current_chat_title}")

        self.lbl_files_stat.setText(f"Files Indexed: {prog.total_files_indexed}")
        self.lbl_msgs_stat.setText(f"Messages Scanned: {prog.messages_scanned}")

    def _on_manager_indexing_finished(self, total_files: int, is_cancelled: bool):
        self._update_controls_state()

    def _append_log(self, text: str):
        self.text_log.append(text)
        self.text_log.verticalScrollBar().setValue(self.text_log.verticalScrollBar().maximum())

    def _update_controls_state(self, status_override: Optional[str] = None):
        if status_override is not None:
            is_running = status_override.upper() == "RUNNING"
            is_paused = status_override.upper() == "PAUSED"
        else:
            is_running = self.manager.is_running
            is_paused = self.manager.is_paused

        busy = is_running or is_paused

        self.btn_start.setEnabled(not busy)
        self.btn_pause.setEnabled(busy)
        self.btn_cancel.setEnabled(busy)

        self.radio_all.setEnabled(not busy)
        self.radio_selected.setEnabled(not busy)
        self.combo_chats.setEnabled(not busy and self.radio_selected.isChecked())
        self.spin_limit.setEnabled(not busy)
        self.chk_reindex.setEnabled(not busy)

        if is_paused:
            self.btn_pause.setText("Resume")
            self.btn_pause.setIcon(get_icon('play', color='#ffffff', size=14))
        else:
            self.btn_pause.setText("Pause")
            self.btn_pause.setIcon(get_icon('pause', color='#ffffff', size=14))
