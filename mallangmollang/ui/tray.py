"""
시스템 트레이 모듈
트레이 아이콘과 우클릭 메뉴를 제공합니다.
"""

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtGui import QIcon, QPixmap, QColor, QPainter
from PyQt6.QtCore import pyqtSignal, QObject, QTimer


def _make_tray_icon(active: bool) -> QIcon:
    """
    번역 활성/비활성 상태를 나타내는 16x16 아이콘을 생성합니다.
    활성: 초록색 원, 비활성: 회색 원
    """
    pixmap = QPixmap(16, 16)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor(0, 200, 80) if active else QColor(150, 150, 150)
    painter.setBrush(color)
    painter.setPen(QColor(0, 0, 0, 100))
    painter.drawEllipse(1, 1, 14, 14)
    painter.end()
    return QIcon(pixmap)


class TrayIcon(QObject):
    """
    시스템 트레이 아이콘 및 메뉴.

    사용 예시:
        tray = TrayIcon()
        tray.toggle_requested.connect(on_toggle)
        tray.settings_requested.connect(on_settings)
        tray.region_requested.connect(on_region)
        tray.quit_requested.connect(app.quit)
        tray.show()
    """

    toggle_requested = pyqtSignal()      # 번역 시작/중지
    settings_requested = pyqtSignal()    # 설정 창 열기
    region_requested = pyqtSignal()      # 영역 재지정
    panel_requested = pyqtSignal()       # 컨트롤 패널 표시
    quit_requested = pyqtSignal()        # 앱 종료

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active = False

        self._tray = QSystemTrayIcon()
        self._tray.setToolTip("말랑몰랑 — 화면 번역기")
        self._tray.setIcon(_make_tray_icon(False))

        # 단일클릭/더블클릭 구분용 타이머
        # Windows에서 더블클릭 시 Trigger가 먼저 발생하므로,
        # 짧은 지연 후 더블클릭이 안 오면 단일클릭으로 처리합니다.
        self._click_timer = QTimer()
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(250)
        self._click_timer.timeout.connect(self.panel_requested)

        self._build_menu()
        self._tray.activated.connect(self._on_activated)

    def _build_menu(self):
        """트레이 우클릭 메뉴를 구성합니다."""
        menu = QMenu()

        self._toggle_action = menu.addAction("번역 시작")
        self._toggle_action.triggered.connect(self.toggle_requested)

        self._region_action = menu.addAction("영역 재지정")
        self._region_action.triggered.connect(self.region_requested)

        panel_action = menu.addAction("컨트롤 패널 표시")
        panel_action.triggered.connect(self.panel_requested)

        menu.addSeparator()

        settings_action = menu.addAction("설정")
        settings_action.triggered.connect(self.settings_requested)

        menu.addSeparator()

        quit_action = menu.addAction("종료")
        quit_action.triggered.connect(self.quit_requested)

        self._tray.setContextMenu(menu)

    def show(self):
        """트레이 아이콘을 표시합니다."""
        self._tray.show()

    def hide(self):
        """트레이 아이콘을 숨깁니다."""
        self._tray.hide()

    def set_active(self, active: bool):
        """번역 활성 상태를 아이콘과 메뉴 텍스트에 반영합니다."""
        self._active = active
        self._tray.setIcon(_make_tray_icon(active))
        self._toggle_action.setText("번역 중지" if active else "번역 시작")
        status = "번역 중" if active else "대기 중"
        self._tray.setToolTip(f"말랑몰랑 — {status}")

    def show_message(self, title: str, message: str, duration_ms: int = 3000):
        """트레이 풍선 알림을 표시합니다."""
        self._tray.showMessage(
            title,
            message,
            QSystemTrayIcon.MessageIcon.Information,
            duration_ms,
        )

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason):
        """트레이 아이콘 단일클릭 → 패널 표시, 더블클릭 → 설정 창."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._click_timer.start()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._click_timer.stop()
            self.settings_requested.emit()
