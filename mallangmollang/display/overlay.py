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
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QBrush, QPen, QFontMetrics, QMouseEvent,
    QPainterPath, QPainterPathStroker,
)
from PyQt6.QtCore import QRect, QPointF, pyqtSignal

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
        """각 줄의 번역을 원문 위치에 배치합니다 (MORT 스타일).

        - QPainterPath 기반 이중 외곽선으로 고품질 텍스트 렌더링
        - 번역이 길어 줄바꿈되면 이후 줄들을 아래로 밀어냄 (겹침 방지)
        - 외곽선 두께를 폰트 크기에 비례하도록 조정
        - 프리셋 bg_color 알파값에 따라 배경 표시 여부 결정
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        p = self.preset
        text_color = QColor(*p.text_color)
        bg = QColor(*p.bg_color)
        use_bg = bg.alpha() > 0
        region_w = self.width()
        pad = 4

        # 누적 오프셋: 이전 줄의 번역이 원문보다 길면 아래 줄들을 밀어냄
        y_offset = 0

        for line in self._lines:
            if not line.text.strip():
                continue

            font_size = max(10, line.font_pt)
            font = QFont(p.font_family, font_size)
            font.setBold(p.font_bold)
            painter.setFont(font)

            fm = QFontMetrics(font)
            box_x = line.x
            box_w = max(line.width, region_w - line.x)
            avail_w = max(1, box_w - pad * 2)

            wrapped = self._wrap_text(fm, line.text, avail_w)

            line_h = fm.height()
            line_spacing = int(line_h * 1.2)
            total_text_h = line_spacing * len(wrapped)
            box_h = max(line.height, total_text_h + pad)

            actual_y = line.y + y_offset

            if use_bg:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(bg))
                painter.drawRect(box_x, actual_y, box_w, box_h)

            draw_x = box_x + pad
            draw_y = actual_y + fm.ascent() + (pad // 2)

            # 외곽선 두께를 폰트 크기에 비례 (MORT: 5/2px 기준 ~16pt)
            outer_w = max(2.0, font_size * 0.3)
            inner_w = max(1.0, font_size * 0.12)

            for segment in wrapped:
                path = QPainterPath()
                path.addText(QPointF(draw_x, draw_y), font, segment)

                if p.outline:
                    outline_color = QColor(*p.outline_color)

                    stroker_outer = QPainterPathStroker()
                    stroker_outer.setWidth(outer_w)
                    stroker_outer.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(outline_color))
                    painter.drawPath(stroker_outer.createStroke(path))

                    stroker_inner = QPainterPathStroker()
                    stroker_inner.setWidth(inner_w)
                    stroker_inner.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    inner_color = QColor(outline_color)
                    inner_color.setAlpha(min(255, outline_color.alpha() + 40))
                    painter.setBrush(QBrush(inner_color))
                    painter.drawPath(stroker_inner.createStroke(path))

                painter.setPen(Qt.PenStyle.NoPen)
                painter.fillPath(path, QBrush(text_color))

                draw_y += line_spacing

            # 번역이 원문 줄 높이보다 길면 차이만큼 이후 줄들을 밀어냄
            overflow = box_h - line.height
            if overflow > 0:
                y_offset += overflow

        painter.end()

    @staticmethod
    def _wrap_text(fm: QFontMetrics, text: str, max_width: int) -> list[str]:
        """텍스트를 max_width에 맞게 줄바꿈합니다 (글자 단위)."""
        if fm.horizontalAdvance(text) <= max_width:
            return [text]

        lines: list[str] = []
        current = ""
        for char in text:
            test = current + char
            if fm.horizontalAdvance(test) > max_width and current:
                lines.append(current)
                current = char
            else:
                current = test
        if current:
            lines.append(current)
        return lines

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
