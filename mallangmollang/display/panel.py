"""
사이드 패널 모듈
오버레이 대신 화면 한쪽에 번역 히스토리를 스크롤 목록으로 표시합니다.
"""

from datetime import datetime
from html import escape as html_escape

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QLabel, QFrame, QPushButton, QTextBrowser,
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen


_MAX_ENTRIES = 50

_STYLE = """
    QWidget#SidePanel {
        background-color: rgba(22, 22, 28, 235);
    }
    QScrollArea {
        border: none;
        background: transparent;
    }
    QScrollBar:vertical {
        background: rgba(40, 40, 50, 200);
        width: 8px;
        border-radius: 4px;
    }
    QScrollBar::handle:vertical {
        background: rgba(100, 100, 120, 180);
        border-radius: 4px;
        min-height: 30px;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0;
    }
"""

_ENTRY_STYLE = """
    QTextBrowser {
        background: rgba(35, 35, 48, 200);
        border-radius: 6px;
        border: none;
        padding: 8px;
    }
"""


class SidePanel(QWidget):
    """
    번역 히스토리를 표시하는 사이드 패널.

    새 번역이 들어올 때마다 맨 위에 추가되고,
    이전 번역은 스크롤해서 볼 수 있습니다.

    사용 예시:
        panel = SidePanel()
        panel.add_entry("전투가 시작된다", "The battle begins")
        panel.show()
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: list[QTextBrowser] = []
        self._drag_pos: QPoint | None = None
        self._setup_window()
        self._setup_ui()

    def _setup_window(self):
        self.setObjectName("SidePanel")
        self.setWindowTitle("말랑몰랑 — 번역 패널")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(280, 300)
        self.resize(340, 480)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 8)
        root.setSpacing(4)

        # 타이틀 바
        title_row = QHBoxLayout()
        title_row.setContentsMargins(4, 0, 0, 0)

        title = QLabel("번역 히스토리")
        title.setStyleSheet(
            "color: rgba(190,190,210,220); font-size: 12px; font-weight: bold;"
        )

        clear_btn = QPushButton("지우기")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setFixedHeight(22)
        clear_btn.setStyleSheet("""
            QPushButton {
                color: rgba(160,160,180,200);
                background: rgba(50,50,65,180);
                border: none; border-radius: 4px;
                padding: 2px 8px; font-size: 10px;
            }
            QPushButton:hover { background: rgba(70,70,90,200); }
        """)
        clear_btn.clicked.connect(self.clear)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                color: rgba(160,160,175,180);
                background: transparent; border: none; font-size: 12px;
            }
            QPushButton:hover { color: rgba(255,255,255,240); }
        """)
        close_btn.clicked.connect(self.hide)

        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(clear_btn)
        title_row.addWidget(close_btn)

        # 스크롤 영역
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setStyleSheet(_STYLE)

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._list = QVBoxLayout(self._container)
        self._list.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._list.setContentsMargins(0, 0, 0, 0)
        self._list.setSpacing(4)

        self._scroll.setWidget(self._container)

        # 빈 상태 안내
        self._empty_label = QLabel("번역 결과가 여기에 표시됩니다.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            "color: rgba(120,120,140,150); font-size: 11px; padding: 40px;"
        )
        self._list.addWidget(self._empty_label)

        root.addLayout(title_row)
        root.addWidget(self._scroll)

    def add_entry(self, translated: str, original: str = ""):
        """번역 결과를 히스토리 맨 위에 추가합니다."""
        if not translated.strip():
            return

        # 빈 상태 안내 제거
        if self._empty_label.isVisible():
            self._empty_label.hide()

        ts = datetime.now().strftime("%H:%M:%S")

        browser = QTextBrowser()
        browser.setReadOnly(True)
        browser.setFrameShape(QFrame.Shape.NoFrame)
        browser.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        browser.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        browser.setOpenLinks(False)
        browser.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        browser.setStyleSheet(_ENTRY_STYLE)

        # HTML로 타임스탬프 + 원문 + 번역문 구성
        parts = [
            '<p style="color:rgba(100,160,220,180); font-size:9px; margin:0;">'
            f'{ts}</p>'
        ]
        if original.strip():
            safe_orig = html_escape(original.strip()).replace("\n", "<br>")
            parts.append(
                '<p style="color:rgba(150,150,170,200); font-size:11px; margin:2px 0 0 0;">'
                f'{safe_orig}</p>'
            )
        safe_trans = html_escape(translated.strip()).replace("\n", "<br>")
        parts.append(
            '<p style="color:rgba(230,230,240,240); font-size:13px; margin:2px 0 0 0;">'
            f'{safe_trans}</p>'
        )
        browser.setHtml("".join(parts))

        # 텍스트 내용에 맞게 높이 고정
        self._fit_height(browser)

        self._list.insertWidget(0, browser)
        self._entries.insert(0, browser)

        # 항목 수 제한
        while len(self._entries) > _MAX_ENTRIES:
            old = self._entries.pop()
            self._list.removeWidget(old)
            old.deleteLater()

        # 맨 위로 스크롤
        self._scroll.verticalScrollBar().setValue(0)

    def _fit_height(self, browser: QTextBrowser):
        """QTextBrowser의 문서 높이를 계산하여 위젯 높이를 고정합니다."""
        w = self._scroll.viewport().width()
        if w < 50:
            w = self.width() - 24
        doc = browser.document()
        doc.setTextWidth(w - 24)
        browser.setFixedHeight(int(doc.size().height()) + 20)

    def clear(self):
        """히스토리를 모두 지웁니다."""
        for entry in self._entries:
            self._list.removeWidget(entry)
            entry.deleteLater()
        self._entries.clear()
        self._empty_label.show()

    # 패널 리사이즈 시 모든 항목 높이 재계산
    def resizeEvent(self, event):
        super().resizeEvent(event)
        for entry in self._entries:
            self._fit_height(entry)

    # 둥근 반투명 배경
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(22, 22, 28, 235)))
        painter.setPen(QPen(QColor(55, 55, 70, 200), 1))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 10, 10)

    # 드래그 이동
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
