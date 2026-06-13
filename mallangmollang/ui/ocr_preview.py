"""
OCR 전처리 미리보기 창
원본 / 전처리 결과 / 바운딩 박스 이미지를 탭으로 표시합니다.
마우스 휠로 확대/축소, 드래그로 이동 가능합니다.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QTabWidget, QWidget, QScrollArea, QSizePolicy, QSlider,
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPixmap, QImage, QWheelEvent, QMouseEvent
from PIL import Image
import numpy as np


def _pil_to_pixmap(image: Image.Image) -> QPixmap:
    """PIL Image를 QPixmap으로 변환합니다 (원본 크기 유지)."""
    img = image.convert("RGB")
    data = np.array(img)
    h, w, ch = data.shape
    qimg = QImage(data.data, w, h, ch * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg)


class ZoomableImageWidget(QWidget):
    """마우스 휠 확대/축소 + 드래그 이동이 가능한 이미지 위젯."""

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._pixmap = pixmap
        self._scale = 1.0
        self._min_scale = 0.2
        self._max_scale = 5.0
        self._drag_start: QPoint | None = None
        self._offset = QPoint(0, 0)

        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._update_size()

    def _update_size(self):
        w = int(self._pixmap.width() * self._scale)
        h = int(self._pixmap.height() * self._scale)
        self.setMinimumSize(w, h)
        self.resize(w, h)
        self.update()

    def set_scale(self, scale: float):
        self._scale = max(self._min_scale, min(self._max_scale, scale))
        self._update_size()

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else 1 / 1.15
        self.set_scale(self._scale * factor)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_start is not None:
            scroll_area = self.parent()
            if scroll_area and hasattr(scroll_area, 'parent'):
                sa = self._find_scroll_area()
                if sa:
                    delta = event.pos() - self._drag_start
                    sa.horizontalScrollBar().setValue(
                        sa.horizontalScrollBar().value() - delta.x()
                    )
                    sa.verticalScrollBar().setValue(
                        sa.verticalScrollBar().value() - delta.y()
                    )

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)

    def _find_scroll_area(self) -> QScrollArea | None:
        widget = self.parent()
        while widget is not None:
            if isinstance(widget, QScrollArea):
                return widget
            widget = widget.parent()
        return None

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter
        painter = QPainter(self)
        scaled = self._pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)


def _make_image_tab(pixmap: QPixmap) -> QWidget:
    """확대/축소 가능한 이미지 탭을 생성합니다."""
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)

    scroll = QScrollArea()
    scroll.setWidgetResizable(False)
    scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
    scroll.setStyleSheet("QScrollArea { background: #1a1a1a; border: none; }")

    img_widget = ZoomableImageWidget(pixmap)
    scroll.setWidget(img_widget)

    # 휠 이벤트를 이미지 위젯에 전달
    scroll.wheelEvent = lambda e: img_widget.wheelEvent(e)

    hint = QLabel("마우스 휠: 확대/축소 | 드래그: 이동")
    hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
    hint.setStyleSheet("color: #888; font-size: 10px; padding: 2px;")

    layout.addWidget(scroll, stretch=1)
    layout.addWidget(hint)
    return container


class OcrPreviewDialog(QDialog):
    """OCR 전처리 미리보기 창 — 탭 전환 + 확대/축소"""

    def __init__(
        self,
        original: Image.Image,
        preprocessed: Image.Image,
        bbox_overlay: Image.Image,
        ocr_text: str,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("OCR 전처리 미리보기")
        self.setMinimumSize(800, 500)
        self.resize(1000, 650)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        layout = QVBoxLayout(self)

        # 이미지 탭
        tabs = QTabWidget()
        for title, img in [
            ("원본", original),
            ("전처리 (이진화)", preprocessed),
            ("바운딩 박스", bbox_overlay),
        ]:
            pixmap = _pil_to_pixmap(img)
            tab = _make_image_tab(pixmap)
            tabs.addTab(tab, title)

        layout.addWidget(tabs, stretch=4)

        # OCR 텍스트 (복사 가능)
        text_label = QLabel("OCR 추출 텍스트:")
        text_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(text_label)

        text_edit = QTextEdit()
        text_edit.setPlainText(ocr_text if ocr_text else "(텍스트 없음)")
        text_edit.setReadOnly(True)
        text_edit.setMaximumHeight(120)
        layout.addWidget(text_edit, stretch=1)
