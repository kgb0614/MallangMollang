"""
영역 편집 모듈
지정된 OCR 영역을 드래그로 이동/리사이즈하고 삭제할 수 있는 편집 핸들입니다.
레이블과 버튼은 영역 위쪽 바깥에 배치되어 OCR에 영향을 주지 않습니다.
"""

from PyQt6.QtWidgets import QWidget, QLabel, QPushButton
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen

_MIN_SIZE = 50
_EDGE_MARGIN = 6
_TOOLBAR_H = 26


class RegionHandle(QWidget):
    """
    하나의 OCR 영역을 편집할 수 있는 핸들 위젯.

    위젯 구조:
        ┌─ 툴바 (영역 바깥, _TOOLBAR_H 높이) ─┐
        │  [번호]              [▶] [✕]        │
        ├─ 영역 테두리 ────────────────────────┤
        │                                      │
        │         실제 OCR 캡처 영역            │
        │                                      │
        └──────────────────────────────────────┘
    """

    region_changed = pyqtSignal(int, list)     # (region_id, [x, y, w, h])
    region_deleted = pyqtSignal(int)           # region_id
    translate_requested = pyqtSignal(int)      # region_id — 이 영역만 번역

    def __init__(self, region_id: int, name: str, rect: list[int], parent=None):
        super().__init__(parent)
        self.region_id = region_id
        self._name = name
        self._drag_start: QPoint | None = None
        self._resize_edge: str = ""

        self._setup_window()

        # 위젯은 영역 위로 _TOOLBAR_H만큼 확장
        x, y, w, h = rect
        self.setGeometry(x, y - _TOOLBAR_H, w, h + _TOOLBAR_H)

        # 번호 레이블 (툴바 영역, 영역 바깥)
        self._label = QLabel(name, self)
        self._label.setStyleSheet(
            "background: rgba(0,100,200,200); color: white; "
            "font-size: 11px; padding: 2px 6px; border-radius: 2px;"
        )
        self._label.move(0, 2)
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # 번역 버튼 (툴바 영역)
        self._translate_btn = QPushButton("▶", self)
        self._translate_btn.setFixedSize(22, 22)
        self._translate_btn.setStyleSheet(
            "QPushButton { background: rgba(30,100,180,200); color: white; "
            "border: none; border-radius: 3px; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background: rgba(40,130,220,240); }"
        )
        self._translate_btn.clicked.connect(
            lambda: self.translate_requested.emit(self.region_id)
        )

        # 삭제 버튼 (툴바 영역)
        self._close_btn = QPushButton("✕", self)
        self._close_btn.setFixedSize(22, 22)
        self._close_btn.setStyleSheet(
            "QPushButton { background: rgba(200,50,50,200); color: white; "
            "border: none; border-radius: 3px; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background: rgba(220,30,30,240); }"
        )
        self._close_btn.clicked.connect(lambda: self.region_deleted.emit(self.region_id))
        self._update_btn_positions()

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.setMinimumSize(_MIN_SIZE, _MIN_SIZE + _TOOLBAR_H)

    def _update_btn_positions(self):
        """버튼들을 툴바 영역 오른쪽에 배치합니다."""
        self._close_btn.move(self.width() - 24, 2)
        self._translate_btn.move(self.width() - 50, 2)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_btn_positions()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 영역 테두리 + 반투명 배경 (_TOOLBAR_H 아래부터)
        region_y = _TOOLBAR_H
        region_h = self.height() - _TOOLBAR_H

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 100, 200, 30)))
        painter.drawRect(0, region_y, self.width(), region_h)

        pen = QPen(QColor(0, 140, 255, 200), 2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(1, region_y + 1, self.width() - 2, region_h - 2)

        painter.end()

    def _region_rect(self) -> tuple[int, int, int, int]:
        """실제 OCR 영역의 절대 좌표 (x, y, w, h)를 반환합니다."""
        geo = self.geometry()
        return (geo.x(), geo.y() + _TOOLBAR_H, geo.width(), geo.height() - _TOOLBAR_H)

    def _detect_edge(self, pos: QPoint) -> str:
        """마우스 위치에서 리사이즈 방향을 감지합니다. 영역 테두리 기준."""
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()

        # 툴바 영역은 리사이즈 대상이 아님
        if y < _TOOLBAR_H:
            return ""

        edge = ""
        if y < _TOOLBAR_H + _EDGE_MARGIN:
            edge += "top"
        elif y > h - _EDGE_MARGIN:
            edge += "bottom"
        if x < _EDGE_MARGIN:
            edge += "left"
        elif x > w - _EDGE_MARGIN:
            edge += "right"
        return edge

    def mouseMoveEvent(self, event):
        if self._drag_start is not None:
            if self._resize_edge:
                self._do_resize(event.globalPosition().toPoint())
            else:
                self._do_move(event.globalPosition().toPoint())
        else:
            edge = self._detect_edge(event.pos())
            self._set_cursor_for_edge(edge)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._resize_edge = self._detect_edge(event.pos())
            self._drag_start = event.globalPosition().toPoint()
            self._drag_geo = self.geometry()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drag_start:
            self._drag_start = None
            self._resize_edge = ""
            self._emit_changed()

    def _do_move(self, global_pos: QPoint):
        delta = global_pos - self._drag_start
        geo = self._drag_geo
        self.move(geo.x() + delta.x(), geo.y() + delta.y())

    def _do_resize(self, global_pos: QPoint):
        delta = global_pos - self._drag_start
        geo = self._drag_geo
        x, y, w, h = geo.x(), geo.y(), geo.width(), geo.height()
        # 영역의 실제 높이 (툴바 제외)
        region_h = h - _TOOLBAR_H

        if "left" in self._resize_edge:
            new_w = w - delta.x()
            if new_w >= _MIN_SIZE:
                x = x + delta.x()
                w = new_w
        if "right" in self._resize_edge:
            new_w = w + delta.x()
            if new_w >= _MIN_SIZE:
                w = new_w
        if "top" in self._resize_edge:
            # 영역 상단을 움직임 — 툴바는 따라서 올라감
            new_region_h = region_h - delta.y()
            if new_region_h >= _MIN_SIZE:
                y = y + delta.y()
                h = h - delta.y()
        if "bottom" in self._resize_edge:
            new_region_h = region_h + delta.y()
            if new_region_h >= _MIN_SIZE:
                h = h + delta.y()

        self.setGeometry(x, y, w, h)

    def _emit_changed(self):
        """영역 좌표를 config에 반영합니다 (툴바 영역 제외)."""
        rx, ry, rw, rh = self._region_rect()
        self.region_changed.emit(self.region_id, [rx, ry, rw, rh])

    def _set_cursor_for_edge(self, edge: str):
        cursors = {
            "topleft": Qt.CursorShape.SizeFDiagCursor,
            "bottomright": Qt.CursorShape.SizeFDiagCursor,
            "topright": Qt.CursorShape.SizeBDiagCursor,
            "bottomleft": Qt.CursorShape.SizeBDiagCursor,
            "top": Qt.CursorShape.SizeVerCursor,
            "bottom": Qt.CursorShape.SizeVerCursor,
            "left": Qt.CursorShape.SizeHorCursor,
            "right": Qt.CursorShape.SizeHorCursor,
        }
        cursor = cursors.get(edge, Qt.CursorShape.SizeAllCursor)
        self.setCursor(cursor)
