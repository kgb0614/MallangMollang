"""
플로팅 컨트롤 패널 모듈
번역 시작/중지, 영역 설정, 설정 창 접근을 빠르게 할 수 있는 소형 창입니다.
트레이 아이콘을 찾아 클릭하는 번거로움을 없애줍니다.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMenu,
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen

_BG_COLOR    = QColor(28, 28, 34, 225)
_BORDER_COLOR = QColor(65, 65, 80, 200)
_PANEL_WIDTH  = 210
_CORNER_RADIUS = 10


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
        toggle_requested   — 번역 시작/중지
        region_requested   — 영역 재지정
        settings_requested — 설정 창 열기
        quit_requested     — 앱 종료 (우클릭 메뉴)

    사용 예시:
        panel = ControlPanel()
        panel.toggle_requested.connect(app.on_toggle)
        panel.show()
    """

    toggle_requested   = pyqtSignal()
    region_requested   = pyqtSignal()
    settings_requested = pyqtSignal()
    quit_requested     = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos: QPoint | None = None
        self._active = False
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

        root.addLayout(title_row)
        root.addLayout(btn_row)
        root.addWidget(self._status_lbl)

    # ── 상태 갱신 ──

    def set_active(self, active: bool) -> None:
        """번역 활성 상태에 따라 버튼과 상태 표시를 갱신합니다."""
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
