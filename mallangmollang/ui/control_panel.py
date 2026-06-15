"""
플로팅 컨트롤 패널 모듈
번역 시작/중지, 영역 설정, 설정 창 접근을 빠르게 할 수 있는 소형 창입니다.
트레이 아이콘을 찾아 클릭하는 번거로움을 없애줍니다.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMenu,
    QComboBox, QCheckBox, QFrame,
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen

_BG_COLOR    = QColor(28, 28, 34, 225)
_BORDER_COLOR = QColor(65, 65, 80, 200)
_PANEL_WIDTH  = 210
_CORNER_RADIUS = 10

_COMBO_STYLE = """
    QComboBox {
        background-color: rgba(50, 50, 65, 220);
        color: rgba(210, 210, 220, 230);
        border: 1px solid rgba(75, 75, 90, 200);
        border-radius: 4px;
        padding: 3px 6px;
        font-size: 11px;
    }
    QComboBox:hover { border-color: rgba(100, 100, 120, 220); }
    QComboBox::drop-down { border: none; width: 18px; }
    QComboBox QAbstractItemView {
        background-color: rgba(40, 40, 55, 245);
        color: rgba(210, 210, 220, 230);
        selection-background-color: rgba(30, 100, 180, 200);
        border: 1px solid rgba(75, 75, 90, 200);
    }
"""

_CHECK_STYLE = """
    QCheckBox {
        color: rgba(170, 170, 185, 200);
        font-size: 11px;
        spacing: 5px;
    }
"""

_LABEL_STYLE = "color: rgba(170,170,185,200); font-size: 11px;"


def _shift_hex(hex_color: str, delta: int) -> str:
    """hex 색상을 delta만큼 밝게(+) 또는 어둡게(-) 변환합니다."""
    h = hex_color.lstrip("#")
    r = max(0, min(255, int(h[0:2], 16) + delta))
    g = max(0, min(255, int(h[2:4], 16) + delta))
    b = max(0, min(255, int(h[4:6], 16) + delta))
    return f"rgb({r},{g},{b})"


def _btn_style(bg: str) -> str:
    hover = _shift_hex(bg, 30)
    pressed = _shift_hex(bg, -20)
    return f"""
        QPushButton {{
            background-color: {bg};
            color: rgba(225, 225, 235, 230);
            border: none;
            border-radius: 5px;
            padding: 5px 8px;
            font-size: 11px;
        }}
        QPushButton:hover  {{ background-color: {hover}; }}
        QPushButton:pressed {{ background-color: {pressed}; }}
    """


def _make_btn(text: str, bg: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(_btn_style(bg))
    return btn


def _set_btn(btn: QPushButton, text: str, bg: str) -> None:
    btn.setText(text)
    btn.setStyleSheet(_btn_style(bg))


class ControlPanel(QWidget):
    """
    화면에 상주하는 플로팅 컨트롤 패널.

    시그널:
        toggle_requested      — 번역 시작/중지
        region_requested      — 영역 재지정
        settings_requested    — 설정 창 열기
        quit_requested        — 앱 종료 (우클릭 메뉴)
        mode_changed(str)     — 번역 모드 변경 ("realtime" | "snapshot")
        display_changed(str)  — 표시 모드 변경 ("overlay" | "panel")
        clipboard_toggled(bool) — 클립보드 자동 복사 토글
        ocr_preview_requested — OCR 미리보기
    """

    toggle_requested      = pyqtSignal()
    region_requested      = pyqtSignal()
    settings_requested    = pyqtSignal()
    quit_requested        = pyqtSignal()
    mode_changed          = pyqtSignal(str)
    display_changed       = pyqtSignal(str)
    clipboard_toggled     = pyqtSignal(bool)
    ocr_preview_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos: QPoint | None = None
        self._active = False
        self._mode = "realtime"
        self._setup_window()
        self._setup_ui()

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedWidth(_PANEL_WIDTH)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 8)
        root.setSpacing(4)

        # ── 타이틀 바 (드래그 핸들) ──
        title_row = QHBoxLayout()
        title_row.setContentsMargins(2, 0, 0, 0)

        title_lbl = QLabel("말랑몰랑")
        title_lbl.setStyleSheet(
            "color: rgba(190,190,205,200); font-size: 11px; font-weight: bold;"
        )

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(18, 18)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                color: rgba(160,160,175,180);
                background: transparent;
                border: none;
                font-size: 11px;
            }
            QPushButton:hover { color: rgba(255,255,255,240); }
        """)
        close_btn.clicked.connect(self.hide)
        close_btn.setToolTip("패널 숨기기 (트레이 아이콘으로 다시 열기)")

        title_row.addWidget(title_lbl)
        title_row.addStretch()
        title_row.addWidget(close_btn)

        # ── 버튼 행 ──
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 2, 0, 0)
        btn_row.setSpacing(4)

        self._toggle_btn   = _make_btn("▶ 시작", "#1a6bbf")
        self._region_btn   = _make_btn("⊕ 영역", "#38384a")
        self._settings_btn = _make_btn("⚙ 설정", "#38384a")

        self._toggle_btn.clicked.connect(self.toggle_requested)
        self._region_btn.clicked.connect(self.region_requested)
        self._settings_btn.clicked.connect(self.settings_requested)

        btn_row.addWidget(self._toggle_btn)
        btn_row.addWidget(self._region_btn)
        btn_row.addWidget(self._settings_btn)

        # ── 상태 표시줄 ──
        self._status_lbl = QLabel("● 대기 중")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setStyleSheet(
            "color: rgba(90,190,255,200); font-size: 10px; padding-top: 2px;"
        )

        # ── 더보기 토글 ──
        self._expand_btn = QPushButton("▼ 더보기")
        self._expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._expand_btn.setStyleSheet("""
            QPushButton {
                color: rgba(120,120,140,180);
                background: transparent;
                border: none;
                font-size: 10px;
                padding: 1px 0;
            }
            QPushButton:hover { color: rgba(180,180,200,220); }
        """)
        self._expand_btn.clicked.connect(self._toggle_expand)

        # ── 빠른 설정 영역 (접힘) ──
        self._extra_widget = QWidget()
        self._extra_widget.setVisible(False)
        extra = QVBoxLayout(self._extra_widget)
        extra.setContentsMargins(2, 2, 2, 0)
        extra.setSpacing(5)

        # 구분선
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: rgba(65, 65, 80, 150);")
        extra.addWidget(line)

        # 번역 모드
        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        mode_lbl = QLabel("모드:")
        mode_lbl.setStyleSheet(_LABEL_STYLE)
        mode_lbl.setFixedWidth(34)
        self._mode_combo = QComboBox()
        self._mode_combo.addItem("실시간", "realtime")
        self._mode_combo.addItem("스냅샷", "snapshot")
        self._mode_combo.setStyleSheet(_COMBO_STYLE)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_combo_changed)
        mode_row.addWidget(mode_lbl)
        mode_row.addWidget(self._mode_combo)
        extra.addLayout(mode_row)

        # 표시 모드
        disp_row = QHBoxLayout()
        disp_row.setSpacing(6)
        disp_lbl = QLabel("표시:")
        disp_lbl.setStyleSheet(_LABEL_STYLE)
        disp_lbl.setFixedWidth(34)
        self._display_combo = QComboBox()
        self._display_combo.addItem("오버레이", "overlay")
        self._display_combo.addItem("사이드 패널", "panel")
        self._display_combo.setStyleSheet(_COMBO_STYLE)
        self._display_combo.currentIndexChanged.connect(self._on_display_combo_changed)
        disp_row.addWidget(disp_lbl)
        disp_row.addWidget(self._display_combo)
        extra.addLayout(disp_row)

        # 클립보드 자동 복사
        self._clipboard_check = QCheckBox("클립보드 자동 복사")
        self._clipboard_check.setStyleSheet(_CHECK_STYLE)
        self._clipboard_check.toggled.connect(self.clipboard_toggled)
        extra.addWidget(self._clipboard_check)

        # OCR 미리보기 버튼
        ocr_btn = _make_btn("🔍 OCR 미리보기", "#38384a")
        ocr_btn.clicked.connect(self.ocr_preview_requested)
        extra.addWidget(ocr_btn)

        # ── 루트에 조립 ──
        root.addLayout(title_row)
        root.addLayout(btn_row)
        root.addWidget(self._status_lbl)
        root.addWidget(self._expand_btn)
        root.addWidget(self._extra_widget)

    # ── 더보기 토글 ──

    def _toggle_expand(self):
        """빠른 설정 영역을 펼치거나 접습니다."""
        visible = not self._extra_widget.isVisible()
        self._extra_widget.setVisible(visible)
        self._expand_btn.setText("▲ 접기" if visible else "▼ 더보기")
        self.adjustSize()

    def _on_mode_combo_changed(self, index: int):
        mode = self._mode_combo.currentData()
        if mode:
            self.mode_changed.emit(mode)

    def _on_display_combo_changed(self, index: int):
        display = self._display_combo.currentData()
        if display:
            self.display_changed.emit(display)

    # ── 상태 갱신 ──

    def set_mode(self, mode: str) -> None:
        """번역 모드를 변경하고 버튼 표시를 갱신합니다."""
        self._mode = mode
        self._active = False
        if mode == "snapshot":
            _set_btn(self._toggle_btn, "📷 번역", "#1a6bbf")
        else:
            _set_btn(self._toggle_btn, "▶ 시작", "#1a6bbf")
        self._status_lbl.setText("● 대기 중")
        self._status_lbl.setStyleSheet(
            "color: rgba(90,190,255,200); font-size: 10px; padding-top: 2px;"
        )

    def set_active(self, active: bool) -> None:
        """번역 활성 상태에 따라 버튼과 상태 표시를 갱신합니다. 실시간 모드 전용."""
        if self._mode == "snapshot":
            return
        self._active = active
        if active:
            _set_btn(self._toggle_btn, "⏹ 중지", "#b03030")
            self._status_lbl.setText("● 번역 중")
            self._status_lbl.setStyleSheet(
                "color: rgba(255,210,50,220); font-size: 10px; padding-top: 2px;"
            )
        else:
            _set_btn(self._toggle_btn, "▶ 시작", "#1a6bbf")
            self._status_lbl.setText("● 대기 중")
            self._status_lbl.setStyleSheet(
                "color: rgba(90,190,255,200); font-size: 10px; padding-top: 2px;"
            )

    def set_status(self, text: str, color: str = "rgba(90,190,255,200)") -> None:
        """상태 표시줄 텍스트와 색상을 직접 지정합니다."""
        self._status_lbl.setText(text)
        self._status_lbl.setStyleSheet(
            f"color: {color}; font-size: 10px; padding-top: 2px;"
        )

    def set_quick_settings(self, mode: str, display: str, clipboard: bool) -> None:
        """빠른 설정 값을 외부에서 동기화합니다 (설정 창 닫힌 후 등)."""
        self._mode_combo.blockSignals(True)
        idx = self._mode_combo.findData(mode)
        if idx >= 0:
            self._mode_combo.setCurrentIndex(idx)
        self._mode_combo.blockSignals(False)

        self._display_combo.blockSignals(True)
        idx = self._display_combo.findData(display)
        if idx >= 0:
            self._display_combo.setCurrentIndex(idx)
        self._display_combo.blockSignals(False)

        self._clipboard_check.blockSignals(True)
        self._clipboard_check.setChecked(clipboard)
        self._clipboard_check.blockSignals(False)

    # ── 배경 렌더링 ──

    def paintEvent(self, event) -> None:
        """둥근 반투명 배경을 직접 그립니다."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(_BG_COLOR))
        painter.setPen(QPen(_BORDER_COLOR, 1))
        painter.drawRoundedRect(
            self.rect().adjusted(0, 0, -1, -1),
            _CORNER_RADIUS, _CORNER_RADIUS,
        )

    # ── 드래그 이동 ──

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None

    # ── 우클릭 메뉴 ──

    def _show_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        quit_action = menu.addAction("앱 종료")
        quit_action.triggered.connect(self.quit_requested)
        menu.exec(self.mapToGlobal(pos))
