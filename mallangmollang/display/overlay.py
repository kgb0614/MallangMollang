"""
오버레이 창 모듈
번역 결과를 화면 위에 반투명 자막 형태로 표시합니다.

특징:
- 테두리 없음 (FramelessWindowHint)
- 배경 투명 (WA_TranslucentBackground)
- 항상 최상위 (WindowStaysOnTopHint)
- 마우스 클릭 투과 (WA_TransparentForMouseInput)
"""

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect
from PyQt6.QtGui import QFont, QColor, QPainter, QBrush, QPen, QPainterPath

from mallangmollang.display.presets import OverlayPreset, PRESET_DEFAULT


class OverlayWindow(QWidget):
    """
    번역 결과를 표시하는 투명 오버레이 창.

    사용 예시:
        app = QApplication([])
        overlay = OverlayWindow()
        overlay.show_translation("번역 결과입니다", position=(100, 200))
    """

    def __init__(self, preset: OverlayPreset | None = None, parent=None):
        super().__init__(parent)
        self.preset = preset or PRESET_DEFAULT
        self._text = ""

        self._setup_window()
        self._setup_ui()

    def _setup_window(self):
        """창 속성 설정: 투명 + 항상 최상위 + 클릭 투과"""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint          # 테두리 제거
            | Qt.WindowType.WindowStaysOnTopHint       # 항상 최상위
            | Qt.WindowType.Tool                       # 작업표시줄 미표시
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)      # 배경 투명
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)   # 클릭 투과
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)      # 포커스 없이 표시

    def _setup_ui(self):
        """레이블과 레이아웃 초기화"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel(self)
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._label)

        self._apply_preset()

    def _apply_preset(self):
        """현재 프리셋을 레이블에 적용합니다."""
        p = self.preset

        font = QFont(p.font_family, p.font_size)
        font.setBold(p.font_bold)
        self._label.setFont(font)

        r, g, b, a = p.text_color
        text_rgba = f"rgba({r},{g},{b},{a/255:.2f})"

        tr, tg, tb, ta = p.bg_color
        bg_rgba = f"rgba({tr},{tg},{tb},{ta/255:.2f})"

        padding = p.padding
        radius = p.border_radius

        style = (
            f"QLabel {{"
            f"  color: {text_rgba};"
            f"  background-color: {bg_rgba};"
            f"  padding: {padding}px;"
            f"  border-radius: {radius}px;"
        )

        # 외곽선: QLabel에서는 CSS text-stroke가 없으므로 배경 대비로 처리
        if p.outline:
            or_, og, ob, oa = p.outline_color
            style += f"  border: 1px solid rgba({or_},{og},{ob},{oa/255:.2f});"

        style += "}"
        self._label.setStyleSheet(style)

    def show_translation(
        self,
        text: str,
        position: tuple[int, int] | None = None,
        region: tuple[int, int, int, int] | None = None,
    ):
        """
        번역 텍스트를 지정된 위치에 표시합니다.

        Args:
            text: 표시할 번역 텍스트
            position: (x, y) 절대 좌표. None이면 현재 위치 유지.
            region: (x, y, w, h) 캡처 영역. position 대신 사용 시 영역 아래에 표시.
        """
        self._text = text
        self._label.setText(text)
        self._label.adjustSize()
        self.adjustSize()

        if region is not None:
            x, y, w, h = region
            self.move(x, y + h + 4)   # 캡처 영역 바로 아래에 표시
        elif position is not None:
            self.move(position[0], position[1])

        if not self.isVisible():
            self.show()

    def hide_translation(self):
        """오버레이를 숨깁니다."""
        self.hide()

    def set_preset(self, preset: OverlayPreset):
        """프리셋을 변경하고 즉시 적용합니다."""
        self.preset = preset
        self._apply_preset()

    def update_position(self, x: int, y: int):
        """오버레이 위치를 변경합니다."""
        self.move(x, y)
