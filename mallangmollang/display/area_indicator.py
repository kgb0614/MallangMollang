"""
영역 표시 창 모듈
번역 중인 캡처 영역의 외곽선을 화면에 표시합니다.
번역 상태에 따라 테두리 색상이 변합니다.
"""

import sys

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QPen

_BORDER_WIDTH = 3

# 상태별 테두리 색상
_STATUS_COLORS: dict[str, QColor] = {
    "idle":        QColor(0, 140, 255, 230),   # 파랑 — 대기 중
    "translating": QColor(255, 200, 0, 230),   # 노랑 — 번역 처리 중
    "error":       QColor(220, 50, 50, 230),   # 빨강 — 오류
}


# 환경변수 MALLANG_DEBUG=1 로 실행하면 캡처 제외를 건너뛰어
# 스크린샷 도구로 오버레이를 찍을 수 있습니다 (디버그 전용)
import os
_DEBUG_CAPTURE = os.environ.get("MALLANG_DEBUG", "0") == "1"


def _exclude_from_screen_capture(win_id: int) -> None:
    """Windows에서 이 창이 mss 캡처에 잡히지 않도록 설정합니다.
    MALLANG_DEBUG=1 환경변수를 설정하면 이 동작을 건너뜁니다."""
    if _DEBUG_CAPTURE or sys.platform != "win32":
        return
    try:
        import ctypes
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
        # 펄스 애니메이션용 불투명도 값 (0.3 ~ 1.0)
        self._pulse_value: float = 1.0
        # 펄스 방향 추적: True면 밝아지는 중, False면 어두워지는 중
        self._pulse_forward: bool = True
        self._pulse_anim: QPropertyAnimation | None = None
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

    # -- 펄스 애니메이션용 커스텀 프로퍼티 ----------------------------------
    def _get_pulse(self) -> float:
        return self._pulse_value

    def _set_pulse(self, value: float) -> None:
        self._pulse_value = value
        # 펄스 값이 바뀔 때마다 테두리를 다시 그린다
        self.update()

    # QPropertyAnimation이 이 프로퍼티를 대상으로 동작한다
    pulse = pyqtProperty(float, fget=_get_pulse, fset=_set_pulse)

    # -- 펄스 애니메이션 제어 ------------------------------------------------
    def _start_pulse_animation(self) -> None:
        """번역 중 테두리가 부드럽게 깜빡이는 펄스 애니메이션을 시작합니다."""
        self._pulse_forward = True
        anim = QPropertyAnimation(self, b"pulse")
        anim.setDuration(800)
        anim.setStartValue(1.0)
        anim.setEndValue(0.3)
        anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        # 애니메이션 완료 시 방향을 반대로 바꿔서 핑-퐁 루프 구현
        anim.finished.connect(self._on_pulse_finished)
        self._pulse_anim = anim
        anim.start()

    def _on_pulse_finished(self) -> None:
        """한 방향의 펄스가 끝나면 반대 방향으로 재시작합니다."""
        if self._pulse_anim is None:
            return
        # 방향 전환: 어두워졌으면 밝아지고, 밝아졌으면 어두워진다
        self._pulse_forward = not self._pulse_forward
        if self._pulse_forward:
            self._pulse_anim.setStartValue(0.3)
            self._pulse_anim.setEndValue(1.0)
        else:
            self._pulse_anim.setStartValue(1.0)
            self._pulse_anim.setEndValue(0.3)
        self._pulse_anim.start()

    def _stop_pulse_animation(self) -> None:
        """펄스 애니메이션을 정지하고 불투명도를 원래대로 되돌립니다."""
        if self._pulse_anim is not None:
            self._pulse_anim.stop()
            self._pulse_anim = None
        self._pulse_value = 1.0

    # -- 상태 설정 -----------------------------------------------------------
    def set_status(self, status: str) -> None:
        """
        테두리 색상을 상태에 따라 변경합니다.

        Args:
            status: "idle" | "translating" | "error"
        """
        if self._status == status:
            return

        old_status = self._status
        self._status = status

        # translating 상태로 전환 → 펄스 시작
        if status == "translating":
            self._start_pulse_animation()
        # translating 상태에서 벗어남 → 펄스 정지
        elif old_status == "translating":
            self._stop_pulse_animation()

        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = QColor(_STATUS_COLORS.get(self._status, _STATUS_COLORS["idle"]))

        # 번역 중일 때 펄스 값에 따라 테두리 알파를 조절한다
        if self._status == "translating":
            color.setAlpha(int(color.alpha() * self._pulse_value))

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
