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
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor, QPainter, QBrush, QPen, QFontMetrics
from PyQt6.QtCore import QRect

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

    def __init__(self, preset: OverlayPreset | None = None, parent=None):
        super().__init__(parent)
        self.preset = preset or PRESET_DEFAULT
        self._text = ""
        self._lines: list[TranslatedLine] = []
        self._current_region: tuple[int, int, int, int] | None = None
        self._mode = "line"  # "line" | "block"

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

    def hide_translation(self):
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
        """각 줄 위치에 불투명 배경 + 번역 텍스트를 그립니다.

        폰트 자동 축소: 번역 텍스트가 OCR 원본 영역에 맞을 때까지
        폰트 크기를 1pt씩 줄임. 최소 8pt. 최소에서도 안 맞으면 박스 높이를 늘림.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        p = self.preset
        bg = QColor(*p.bg_color)
        bg_opaque = QColor(bg.red(), bg.green(), bg.blue(), max(bg.alpha(), 220))
        text_color = QColor(*p.text_color)
        text_flags = (Qt.AlignmentFlag.AlignLeft
                      | Qt.AlignmentFlag.AlignTop
                      | Qt.TextFlag.TextWordWrap)

        for line in self._lines:
            if not line.text.strip():
                continue

            pad = 3
            box_w = line.width
            box_h = line.height
            avail_w = max(1, box_w - pad * 2)
            avail_h = max(1, box_h - pad * 2)

            # OCR 폰트에서 시작, 최소 8pt까지 축소 시도
            min_font = 8
            fit_size = max(min_font, line.font_pt)
            for size in range(fit_size, min_font - 1, -1):
                test_font = QFont(p.font_family, size)
                test_font.setBold(p.font_bold)
                bound = QFontMetrics(test_font).boundingRect(
                    QRect(0, 0, avail_w, 10000), text_flags, line.text,
                )
                if bound.height() <= avail_h:
                    fit_size = size
                    break
                fit_size = size

            font = QFont(p.font_family, fit_size)
            font.setBold(p.font_bold)
            painter.setFont(font)

            # 최소 폰트에서도 안 맞으면 박스 높이를 텍스트에 맞게 늘림
            final_bound = QFontMetrics(font).boundingRect(
                QRect(0, 0, avail_w, 10000), text_flags, line.text,
            )
            needed_h = final_bound.height() + pad * 2
            if needed_h > box_h:
                box_h = needed_h
                avail_h = box_h - pad * 2

            # 배경
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(bg_opaque))
            painter.drawRoundedRect(line.x, line.y, box_w, box_h, 2, 2)

            # 텍스트 렌더링
            draw_rect = QRect(line.x + pad, line.y + pad, avail_w, avail_h)

            if p.outline:
                outline_color = QColor(*p.outline_color)
                painter.setPen(QPen(outline_color, 2))
                for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                    painter.drawText(
                        draw_rect.adjusted(dx, dy, dx, dy),
                        text_flags, line.text,
                    )

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
