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
        """각 줄/블록 위치에 불투명 배경 + 번역 텍스트를 그립니다."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        p = self.preset
        bg = QColor(*p.bg_color)
        text_color = QColor(*p.text_color)

        for line in self._lines:
            if not line.text.strip():
                continue

            font_size = max(8, line.font_pt)
            font = QFont(p.font_family, font_size)
            font.setBold(p.font_bold)
            painter.setFont(font)

            metrics = QFontMetrics(font)
            single_line_width = metrics.horizontalAdvance(line.text)
            line_height = metrics.height()

            # OCR 박스 높이가 줄 높이의 1.3배 초과면 다중 줄 블록으로 판단
            # (번역 텍스트 길이가 아닌 원본 영역 크기 기준)
            is_multiline = line.height > line_height * 1.3

            if is_multiline:
                # 문단 블록: word wrap으로 그림
                pad = 3
                box_w = line.width

                # 번역 텍스트의 실제 높이 계산 (word wrap 적용)
                measure_rect = QRect(0, 0, box_w - pad * 2, 10000)
                text_bound = metrics.boundingRect(
                    measure_rect,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                    line.text,
                )
                needed_h = text_bound.height() + pad * 2
                box_h = max(line.height, needed_h)

                # 배경
                bg_opaque = QColor(bg.red(), bg.green(), bg.blue(), max(bg.alpha(), 220))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(bg_opaque))
                painter.drawRoundedRect(line.x, line.y, box_w, box_h, 2, 2)

                # 텍스트 (word wrap)
                draw_rect = QRect(line.x + pad, line.y + pad,
                                  box_w - pad * 2, box_h - pad * 2)
                if p.outline:
                    outline_color = QColor(*p.outline_color)
                    painter.setPen(QPen(outline_color, 2))
                    for dx, dy in [(-1,-1),(-1,1),(1,-1),(1,1)]:
                        painter.drawText(
                            draw_rect.adjusted(dx, dy, dx, dy),
                            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                            line.text,
                        )
                painter.setPen(QPen(text_color))
                painter.drawText(
                    draw_rect,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                    line.text,
                )
            else:
                # 단일 줄: 한 줄로 그림
                box_w = max(line.width, single_line_width + 6)
                box_h = max(line.height, line_height + 2)

                bg_opaque = QColor(bg.red(), bg.green(), bg.blue(), max(bg.alpha(), 220))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(bg_opaque))
                painter.drawRoundedRect(line.x, line.y, box_w, box_h, 2, 2)

                if p.outline:
                    outline_color = QColor(*p.outline_color)
                    painter.setPen(QPen(outline_color, 2))
                    for dx, dy in [(-1,-1),(-1,1),(1,-1),(1,1)]:
                        painter.drawText(
                            line.x + 3 + dx,
                            line.y + metrics.ascent() + 1 + dy,
                            line.text,
                        )

                painter.setPen(QPen(text_color))
                painter.drawText(
                    line.x + 3,
                    line.y + metrics.ascent() + 1,
                    line.text,
                )

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
