"""
영역 선택 UI 모듈
전체 화면 반투명 오버레이에서 마우스 드래그로 캡처 영역을 선택합니다.
"""

from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QScreen


class RegionSelector(QWidget):
    """
    전체 화면 반투명 오버레이 위에서 마우스 드래그로 영역을 선택하는 위젯.

    선택 완료 시 region_selected 시그널로 (x, y, w, h) 튜플을 전달합니다.
    ESC 키 또는 우클릭으로 취소합니다.

    사용 예시:
        selector = RegionSelector()
        selector.region_selected.connect(lambda r: print(f"선택된 영역: {r}"))
        selector.start()
    """

    # 선택 완료 시그널: (x, y, width, height)
    region_selected = pyqtSignal(tuple)
    # 취소 시그널
    selection_cancelled = pyqtSignal()

    def __init__(self, screen: QScreen | None = None, parent=None):
        super().__init__(parent)

        self._start_point: QPoint | None = None
        self._current_point: QPoint | None = None
        self._is_drawing = False

        self._setup_window(screen)

    def _setup_window(self, screen: QScreen | None):
        """전체 화면 반투명 창으로 설정합니다."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)

        # 대상 화면 전체를 덮도록 크기 설정
        if screen is None:
            screen = QApplication.primaryScreen()

        if screen:
            geo = screen.geometry()
            self.setGeometry(geo)

    def start(self):
        """영역 선택 UI를 시작합니다."""
        self._start_point = None
        self._current_point = None
        self._is_drawing = False
        self.show()
        self.activateWindow()
        self.raise_()

    def paintEvent(self, event):
        """반투명 어두운 배경 + 선택 영역 강조 + 안내 텍스트를 그립니다."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 전체 반투명 검정 오버레이
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        if self._is_drawing and self._start_point and self._current_point:
            selection = self._get_selection_rect()

            # 선택 영역을 투명하게 뚫어서 원래 화면이 보이게
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(selection, QColor(0, 0, 0, 0))

            # 선택 영역 테두리
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            pen = QPen(QColor(0, 180, 255, 220), 2)
            painter.setPen(pen)
            painter.drawRect(selection)

            # 크기 정보 텍스트
            w = selection.width()
            h = selection.height()
            size_text = f"{w} × {h}"
            font = QFont("맑은 고딕", 11)
            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255, 220))

            text_x = selection.x()
            text_y = selection.y() - 22
            if text_y < 10:
                text_y = selection.y() + 6
            painter.drawText(text_x + 4, text_y + 16, size_text)

        else:
            # 드래그 전 안내 텍스트
            painter.setPen(QColor(255, 255, 255, 200))
            font = QFont("맑은 고딕", 14)
            painter.setFont(font)
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "드래그하여 번역 영역을 선택하세요\n(ESC 또는 우클릭으로 취소)"
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_point = event.pos()
            self._current_point = event.pos()
            self._is_drawing = True
        elif event.button() == Qt.MouseButton.RightButton:
            self._cancel()

    def mouseMoveEvent(self, event):
        if self._is_drawing:
            self._current_point = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._is_drawing:
            self._is_drawing = False
            rect = self._get_selection_rect()

            # 너무 작은 영역은 무시 (실수 클릭 방지)
            if rect.width() < 10 or rect.height() < 10:
                self._cancel()
                return

            self.hide()

            # 창 좌표를 화면 절대 좌표로 변환
            global_pos = self.mapToGlobal(rect.topLeft())
            result = (global_pos.x(), global_pos.y(), rect.width(), rect.height())
            self.region_selected.emit(result)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()

    def _get_selection_rect(self) -> QRect:
        """시작점과 현재점으로 정규화된 사각형을 반환합니다."""
        if self._start_point is None or self._current_point is None:
            return QRect()
        return QRect(self._start_point, self._current_point).normalized()

    def _cancel(self):
        """선택을 취소하고 창을 닫습니다."""
        self.hide()
        self.selection_cancelled.emit()
