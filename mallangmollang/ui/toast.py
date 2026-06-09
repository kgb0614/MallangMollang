"""
토스트 알림 모듈
윈도우 시스템 알림 대신 앱 내부에 표시하는 소형 팝업 알림입니다.

화면 우하단에 쌓이며, 일정 시간 후 자동으로 사라집니다.
"""

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen

_BG_COLOR     = QColor(32, 32, 40, 235)
_BORDER_COLOR = QColor(70, 70, 90, 200)
_CORNER       = 8
_MARGIN       = 14     # 화면 가장자리 여백
_GAP          = 8      # 토스트 간 간격
_WIDTH        = 260

# 레벨별 도트 색상
_LEVEL_COLORS = {
    "info":    QColor(90,  190, 255),
    "success": QColor(60,  200, 100),
    "warning": QColor(255, 200, 50),
    "error":   QColor(220, 60,  60),
}


class _Toast(QWidget):
    """단일 토스트 팝업 위젯."""

    def __init__(self, text: str, level: str = "info", duration_ms: int = 3000, parent=None):
        super().__init__(parent)
        self._opacity_value = 1.0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedWidth(_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)

        dot_color = _LEVEL_COLORS.get(level, _LEVEL_COLORS["info"])
        r, g, b = dot_color.red(), dot_color.green(), dot_color.blue()

        lbl = QLabel(f'<span style="color:rgb({r},{g},{b});">●</span>  {text}')
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: rgba(220,220,230,230); font-size: 11px;")
        layout.addWidget(lbl)

        self.adjustSize()

        # duration_ms 후 페이드아웃 시작
        QTimer.singleShot(duration_ms, self._start_fadeout)

    # ── 불투명도 프로퍼티 (QPropertyAnimation 연결용) ──

    def get_opacity(self) -> float:
        return self._opacity_value

    def set_opacity(self, value: float) -> None:
        self._opacity_value = value
        self.setWindowOpacity(value)

    opacity = pyqtProperty(float, fget=get_opacity, fset=set_opacity)

    def _start_fadeout(self) -> None:
        self._anim = QPropertyAnimation(self, b"opacity")
        self._anim.setDuration(400)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(self._on_fadeout_done)
        self._anim.start()

    def _on_fadeout_done(self) -> None:
        self.hide()
        self.deleteLater()
        # ToastManager에게 자신이 사라졌음을 알림
        ToastManager.get_instance()._on_toast_removed(self)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(_BG_COLOR))
        painter.setPen(QPen(_BORDER_COLOR, 1))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), _CORNER, _CORNER)


class ToastManager:
    """
    토스트 알림을 관리하는 싱글톤.

    사용 예시:
        ToastManager.get_instance().show("번역을 시작합니다.", "success")
    """

    _instance: "ToastManager | None" = None

    @classmethod
    def get_instance(cls) -> "ToastManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._active: list[_Toast] = []

    def show(self, text: str, level: str = "info", duration_ms: int = 3000) -> None:
        """
        토스트 알림을 화면 우하단에 표시합니다.

        Args:
            text: 표시할 메시지
            level: "info" | "success" | "warning" | "error"
            duration_ms: 표시 지속 시간 (페이드아웃 시작까지)
        """
        toast = _Toast(text, level, duration_ms)
        self._active.append(toast)
        self._reposition()
        toast.show()

    def _reposition(self) -> None:
        """활성 토스트들의 위치를 우하단부터 위로 쌓이도록 재배치합니다."""
        screen = QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        x = geo.right() - _WIDTH - _MARGIN

        y_bottom = geo.bottom() - _MARGIN
        for toast in reversed(self._active):
            if not toast.isVisible() and not toast.isHidden():
                continue
            y = y_bottom - toast.height()
            toast.move(x, y)
            y_bottom = y - _GAP

    def _on_toast_removed(self, toast: _Toast) -> None:
        if toast in self._active:
            self._active.remove(toast)
        self._reposition()
