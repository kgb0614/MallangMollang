"""
오버레이 창 모듈
번역 결과를 캡처 영역 위에 줄 단위로 덮어씌워 표시합니다.

표시 모드:
- line: 각 OCR 줄 위치에 불투명 배경 + 번역 텍스트 (기본, MORT 스타일)
- block: 캡처 영역 전체에 반투명 배경 + 번역 텍스트 (기존 방식)

특징:
- 캡처 영역과 동일한 위치/크기로 정확히 겹침
- 마우스 클릭 투과 (WA_TransparentForMouseEvents)
- SetWindowDisplayAffinity로 mss 캡처에서 제외 (피드백 루프 방지)
"""

import sys
from dataclasses import dataclass

from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QPainter, QBrush, QPen, QFontMetrics, QMouseEvent
from PyQt6.QtCore import QRect, pyqtSignal

from mallangmollang.display.presets import OverlayPreset, PRESET_DEFAULT
from mallangmollang.display.area_indicator import _exclude_from_screen_capture


@dataclass
class TranslatedLine:
    """오버레이에 표시할 번역 줄 정보"""
    text: str        # 번역된 텍스트
    x: int           # 캡처 영역 내 상대 좌표
    y: int
    width: int
    height: int
    font_pt: int     # OCR에서 추정한 폰트 크기


class OverlayWindow(QWidget):
    """
    번역 결과를 표시하는 투명 오버레이 창.

    사용 예시:
        overlay = OverlayWindow()
        overlay.show_lines(lines, region=(100, 200, 800, 400))
    """

    dismissed = pyqtSignal()

    def __init__(self, preset: OverlayPreset | None = None, parent=None):
        super().__init__(parent)
        self.preset = preset or PRESET_DEFAULT
        self._text = ""
        self._lines: list[TranslatedLine] = []
        self._current_region: tuple[int, int, int, int] | None = None
        self._mode = "line"  # "line" | "block"
        self._snapshot_mode = False

        # 스냅샷 자동 정리 타이머
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self._auto_dismiss)

        self._setup_window()

    def showEvent(self, event):
        super().showEvent(event)
        _exclude_from_screen_capture(int(self.winId()))

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

    def show_lines(
        self,
        lines: list[TranslatedLine],
        region: tuple[int, int, int, int] | None = None,
    ):
        """줄 단위 번역 결과를 각 위치에 덮어씌워 표시합니다."""
        self._lines = lines
        self._text = ""
        self._mode = "line"

        if region is not None:
            x, y, w, h = region
            self._current_region = region
            self.setFixedSize(w, h)
            self.move(x, y)

        self.update()
        if not self.isVisible():
            self.show()

    def show_translation(
        self,
        text: str,
        position: tuple[int, int] | None = None,
        region: tuple[int, int, int, int] | None = None,
    ):
        """블록 모드: 캡처 영역 전체에 번역 텍스트를 표시합니다 (기존 방식)."""
        self._text = text
        self._lines = []
        self._mode = "block"

        if region is not None:
            x, y, w, h = region
            self._current_region = region
            self.setFixedSize(w, h)
            self.move(x, y)
        elif position is not None:
            self.move(position[0], position[1])

        self.update()
        if not self.isVisible():
            self.show()

    def set_snapshot_mode(self, enabled: bool, auto_dismiss_ms: int = 0):
        """스냅샷 모드 설정. 스냅샷이면 클릭으로 닫을 수 있고, 자동 정리 타이머를 시작합니다."""
        self._snapshot_mode = enabled
        if enabled:
            # 클릭 투과 해제 — 클릭으로 오버레이를 닫을 수 있게
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            if auto_dismiss_ms > 0:
                self._dismiss_timer.start(auto_dismiss_ms)
        else:
            # 실시간 모드: 클릭 투과 복원
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self._dismiss_timer.stop()

    def mousePressEvent(self, event: QMouseEvent):
        """스냅샷 모드에서 클릭하면 오버레이를 닫습니다."""
        if self._snapshot_mode:
            self._dismiss()
        else:
            super().mousePressEvent(event)

    def _dismiss(self):
        """오버레이를 닫고 스냅샷 모드를 해제합니다."""
        self._dismiss_timer.stop()
        self._snapshot_mode = False
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.hide()
        self.dismissed.emit()

    def _auto_dismiss(self):
        """자동 정리 타이머에 의한 닫기."""
        if self._snapshot_mode:
            self._dismiss()

    def hide_translation(self):
        self._dismiss_timer.stop()
        self.hide()

    def set_preset(self, preset: OverlayPreset):
        self.preset = preset
        self.update()

    def update_position(self, x: int, y: int):
        self.move(x, y)

    def paintEvent(self, event):
        if self._mode == "line" and self._lines:
            self._paint_lines()
        elif self._mode == "block" and self._text:
            self._paint_block()

    def _paint_lines(self):
        """MORT 스타일: 각 줄 위치에 불투명 배경으로 원문을 덮고 번역을 표시합니다.

        - 폰트 크기를 원문과 동일하게 유지 (축소하지 않음)
        - 줄 폭을 영역 전체 너비로 확장
        - 번역이 길면 박스 높이를 자유롭게 늘림
        - 완전 불투명 배경 + 이중 외곽선
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        p = self.preset
        bg = QColor(*p.bg_color)
        bg_opaque = QColor(bg.red(), bg.green(), bg.blue(), 255)
        text_color = QColor(*p.text_color)
        text_flags = (Qt.AlignmentFlag.AlignLeft
                      | Qt.AlignmentFlag.AlignTop
                      | Qt.TextFlag.TextWordWrap)

        region_w = self.width()
        pad = 4

        for line in self._lines:
            if not line.text.strip():
                continue

            box_x = 0
            box_w = region_w
            avail_w = max(1, box_w - pad * 2)

            # 폰트: 원문 크기를 그대로 사용 (최소 10pt 보장)
            font_size = max(10, line.font_pt)
            font = QFont(p.font_family, font_size)
            font.setBold(p.font_bold)
            painter.setFont(font)

            # 박스 높이: 원문 높이 또는 번역 텍스트에 필요한 높이 중 큰 값
            text_bound = QFontMetrics(font).boundingRect(
                QRect(0, 0, avail_w, 10000), text_flags, line.text,
            )
            box_h = max(line.height, text_bound.height() + pad * 2)

            # 불투명 배경 — 원문을 완전히 덮음
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(bg_opaque))
            painter.drawRect(box_x, line.y, box_w, box_h)

            # 텍스트 영역
            draw_rect = QRect(box_x + pad, line.y + pad, avail_w, box_h - pad * 2)

            # 이중 외곽선 (바깥 두꺼운 선 + 안쪽 얇은 선)
            if p.outline:
                outer_color = QColor(*p.outline_color)
                # 바깥 외곽선 (두꺼움)
                painter.setPen(QPen(outer_color, 4))
                for dx, dy in [(-2, -2), (-2, 2), (2, -2), (2, 2)]:
                    painter.drawText(
                        draw_rect.adjusted(dx, dy, dx, dy),
                        text_flags, line.text,
                    )
                # 안쪽 외곽선 (얇음)
                painter.setPen(QPen(outer_color, 2))
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    painter.drawText(
                        draw_rect.adjusted(dx, dy, dx, dy),
                        text_flags, line.text,
                    )

            # 본문 텍스트
            painter.setPen(QPen(text_color))
            painter.drawText(draw_rect, text_flags, line.text)

        painter.end()

    def _paint_block(self):
        """블록 모드: 전체 영역에 반투명 배경 + 텍스트 (기존 방식)."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        p = self.preset
        bg = QColor(*p.bg_color)
        text_color = QColor(*p.text_color)
        font = QFont(p.font_family, p.font_size)
        font.setBold(p.font_bold)
        painter.setFont(font)

        # 배경
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg))
        painter.drawRoundedRect(self.rect(), p.border_radius, p.border_radius)

        # 텍스트
        painter.setPen(QPen(text_color))
        text_rect = self.rect().adjusted(p.padding, p.padding, -p.padding, -p.padding)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            self._text,
        )

        painter.end()
