"""
영역 편집 모듈
지정된 OCR 영역을 드래그로 이동/리사이즈하고 삭제할 수 있는 편집 핸들입니다.
"""

from PyQt6.QtWidgets import QWidget, QLabel, QPushButton
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QCursor

_MIN_SIZE = 50
_EDGE_MARGIN = 6


class RegionHandle(QWidget):
    """
    하나의 OCR 영역을 편집할 수 있는 핸들 위젯.
    - 내부 드래그 → 이동
    - 모서리/가장자리 드래그 → 크기 조정
    - ✕ 버튼 → 삭제
    """

    region_changed = pyqtSignal(int, list)     # (region_id, [x, y, w, h])
    region_deleted = pyqtSignal(int)           # region_id
    translate_requested = pyqtSignal(int)      # region_id — 이 영역만 번역

    def __init__(self, region_id: int, name: str, rect: list[int], parent=None):
        super().__init__(parent)
        self.region_id = region_id
        self._name = name
        self._drag_start: QPoint | None = None
        self._resize_edge: str = ""  # "", "left", "right", "top", "bottom", 조합

        self._setup_window()
        x, y, w, h = rect
        self.setGeometry(x, y, w, h)

        # 이름 레이블
        self._label = QLabel(name, self)
        self._label.setStyleSheet(
            "background: rgba(0,100,200,160); color: white; "
            "font-size: 11px; padding: 2px 6px; border-radius: 2px;"
        )
        self._label.move(4, 4)
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # 번역 버튼 (이 영역만 스냅샷 번역)
        self._translate_btn = QPushButton("▶", self)
        self._translate_btn.setFixedSize(22, 22)
        self._translate_btn.setStyleSheet(
            "QPushButton { background: rgba(30,100,180,180); color: white; "
            "border: none; border-radius: 3px; font-size: 13px; font-weight: bold; }"
            "QPushButton:hover { background: rgba(40,130,220,240); }"
        )
        self._translate_btn.clicked.connect(
            lambda: self.translate_requested.emit(self.region_id)
        )

        # 삭제 버튼
        self._close_btn = QPushButton("✕", self)
        self._close_btn.setFixedSize(22, 22)
        self._close_btn.setStyleSheet(
            "QPushButton { background: rgba(200,50,50,180); color: white; "
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
        self.setMinimumSize(_MIN_SIZE, _MIN_SIZE)

    def _update_btn_positions(self):
        self._close_btn.move(self.width() - 26, 4)
        self._translate_btn.move(self.width() - 52, 4)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_btn_positions()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 반투명 배경
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 100, 200, 40)))
        painter.drawRect(self.rect())

        # 테두리
        pen = QPen(QColor(0, 140, 255, 200), 2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(1, 1, self.width() - 2, self.height() - 2)

        painter.end()

    def _detect_edge(self, pos: QPoint) -> str:
        """마우스 위치에서 리사이즈 방향을 감지합니다."""
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        edge = ""
        if y < _EDGE_MARGIN:
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

        if "left" in self._resize_edge:
            new_x = x + delta.x()
            new_w = w - delta.x()
            if new_w >= _MIN_SIZE:
                x, w = new_x, new_w
        if "right" in self._resize_edge:
            new_w = w + delta.x()
            if new_w >= _MIN_SIZE:
                w = new_w
        if "top" in self._resize_edge:
            new_y = y + delta.y()
            new_h = h - delta.y()
            if new_h >= _MIN_SIZE:
                y, h = new_y, new_h
        if "bottom" in self._resize_edge:
            new_h = h + delta.y()
            if new_h >= _MIN_SIZE:
                h = new_h

        self.setGeometry(x, y, w, h)

    def _emit_changed(self):
        geo = self.geometry()
        self.region_changed.emit(
            self.region_id,
            [geo.x(), geo.y(), geo.width(), geo.height()],
        )

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
