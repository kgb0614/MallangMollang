"""
영역 표시 창 모듈
번역 중인 캡처 영역의 외곽선을 화면에 표시합니다.
번역 상태에 따라 테두리 색상이 변합니다.
"""

import sys

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QPen

_BORDER_WIDTH = 3

# 상태별 테두리 색상
_STATUS_COLORS: dict[str, QColor] = {
    "idle":        QColor(0, 140, 255, 230),   # 파랑 — 대기 중
    "translating": QColor(255, 200, 0, 230),   # 노랑 — 번역 처리 중
    "error":       QColor(220, 50, 50, 230),   # 빨강 — 오류
}


def _exclude_from_screen_capture(win_id: int) -> None:
    """Windows에서 이 창이 캡처 도구에 잡히지 않도록 설정합니다."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        # WDA_EXCLUDEFROMCAPTURE: Windows 10 2004(빌드 19041)+ 에서 지원
        WDA_EXCLUDEFROMCAPTURE = 0x00000011
        ctypes.windll.user32.SetWindowDisplayAffinity(win_id, WDA_EXCLUDEFROMCAPTURE)
    except Exception:
        pass


class AreaIndicatorWindow(QWidget):
    """
    캡처 영역 위에 겹쳐서 테두리만 그리는 투명 창.

    번역 활성 시 show(), 비활성 시 hide().
    번역 상태에 따라 set_status()로 테두리 색상을 바꿀 수 있습니다.

    사용 예시:
        indicator = AreaIndicatorWindow()
        indicator.set_region(100, 200, 800, 400)
        indicator.set_status("idle")
        indicator.show()
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status = "idle"
        self._setup_window()

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # 창이 실제로 표시된 후 캡처 제외 처리 (winId가 확정된 시점)
        _exclude_from_screen_capture(int(self.winId()))

    def set_region(self, x: int, y: int, w: int, h: int) -> None:
        """캡처 영역 좌표에 맞게 창 위치/크기를 조정합니다."""
        self.setGeometry(x, y, w, h)

    def set_status(self, status: str) -> None:
        """
        테두리 색상을 상태에 따라 변경합니다.

        Args:
            status: "idle" | "translating" | "error"
        """
        if self._status != status:
            self._status = status
            self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = _STATUS_COLORS.get(self._status, _STATUS_COLORS["idle"])
        pen = QPen(color, _BORDER_WIDTH)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # 테두리가 창 경계 안쪽에 그려지도록 offset 적용
        half = _BORDER_WIDTH // 2
        painter.drawRect(
            half, half,
            self.width() - _BORDER_WIDTH,
            self.height() - _BORDER_WIDTH,
        )
