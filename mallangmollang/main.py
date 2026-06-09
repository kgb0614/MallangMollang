"""
말랑몰랑 (MallangMollang) 진입점
모든 컴포넌트를 조립하고 앱을 실행합니다.
"""

import asyncio
import sys
import threading

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QObject, pyqtSignal

from mallangmollang.infra.config import Config
from mallangmollang.core.pipeline import Pipeline
from mallangmollang.display.overlay import OverlayWindow
from mallangmollang.display.area_indicator import AreaIndicatorWindow
from mallangmollang.display.presets import get_preset_by_name
from mallangmollang.ui.tray import TrayIcon
from mallangmollang.ui.settings import SettingsWindow
from mallangmollang.ui.region_selector import RegionSelector
from mallangmollang.ui.control_panel import ControlPanel


class _Bridge(QObject):
    """
    asyncio 스레드 → Qt 메인 스레드로 번역 결과를 안전하게 전달하는 브리지.
    Qt 위젯은 메인 스레드에서만 접근해야 하므로, 시그널을 통해 전달합니다.
    """
    translation_ready = pyqtSignal(str, object)   # (번역 텍스트, 캡처 영역)


class App:
    """
    말랑몰랑 앱 컨트롤러.
    Qt 이벤트 루프와 asyncio 파이프라인 루프를 연결하여 전체 동작을 관리합니다.
    """

    def __init__(self, qt_app: QApplication):
        self.qt_app = qt_app
        self.config = Config.get_instance()

        # 컴포넌트 초기화
        self.overlay = OverlayWindow(
            preset=get_preset_by_name(self.config.get("display.active_preset", "기본"))
        )
        self.indicator = AreaIndicatorWindow()
        self.panel = ControlPanel()
        self.tray = TrayIcon()
        self.region_selector = RegionSelector()
        self.pipeline: Pipeline | None = None

        # asyncio 스레드 → Qt 메인 스레드 브리지
        self._bridge = _Bridge()
        self._bridge.translation_ready.connect(self._on_translation_ready)

        # 번역 루프 실행을 위한 asyncio 이벤트 루프 (별도 스레드)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        self._running = False

        self._connect_signals()

    def _connect_signals(self):
        """각 컴포넌트의 시그널을 슬롯에 연결합니다."""
        # 트레이 시그널
        self.tray.toggle_requested.connect(self._on_toggle)
        self.tray.settings_requested.connect(self._on_settings)
        self.tray.region_requested.connect(self._on_region_select)
        self.tray.panel_requested.connect(self._show_panel)
        self.tray.quit_requested.connect(self._on_quit)

        # 컨트롤 패널 시그널 (트레이와 동일한 핸들러)
        self.panel.toggle_requested.connect(self._on_toggle)
        self.panel.settings_requested.connect(self._on_settings)
        self.panel.region_requested.connect(self._on_region_select)
        self.panel.quit_requested.connect(self._on_quit)

        self.region_selector.region_selected.connect(self._on_region_selected)
        self.region_selector.selection_cancelled.connect(
            lambda: self.tray.show_message("말랑몰랑", "영역 선택이 취소되었습니다.")
        )

    def _is_provider_configured(self) -> bool:
        """현재 프로바이더가 최소한의 설정을 갖추고 있는지 확인합니다."""
        active = self.config.get("provider.active", "gemini")
        if active == "gemini":
            endpoint = self.config.get("provider.gemini.endpoint", "ai_studio")
            if endpoint == "vertex":
                return bool(self.config.get("provider.gemini.vertex.service_account", ""))
            return bool(self.config.get("provider.gemini.api_key", ""))
        if active == "openai":
            return bool(self.config.get("provider.openai.api_key", ""))
        if active == "claude":
            return bool(self.config.get("provider.claude.api_key", ""))
        if active == "ollama":
            return bool(self.config.get("provider.ollama.base_url", ""))
        return False

    def _build_pipeline(self):
        """Config를 기반으로 Pipeline을 생성합니다."""
        if not self._is_provider_configured():
            return None

        pipeline = Pipeline.from_config(self.config)

        # 번역 결과를 브리지 시그널로 메인 스레드에 전달 (스레드 안전)
        def on_result(result):
            if result.translation and result.translation.translated:
                region = self.config.get("capture.region")
                self._bridge.translation_ready.emit(
                    result.translation.translated,
                    tuple(region) if region else None,
                )

        pipeline.on_result(on_result)
        return pipeline

    def _on_translation_ready(self, text: str, region):
        """메인 스레드에서 오버레이를 업데이트합니다."""
        self.overlay.show_translation(text, region=region)

    def _start_translation(self):
        """별도 스레드에서 asyncio 번역 루프를 시작합니다."""
        if self._running:
            return

        # 영역이 지정되지 않았으면 먼저 영역 선택
        region = self.config.get("capture.region")
        if not region:
            self.tray.show_message("말랑몰랑", "번역 영역을 먼저 지정해주세요.")
            self._on_region_select()
            return

        self.pipeline = self._build_pipeline()
        if self.pipeline is None:
            self.tray.show_message(
                "말랑몰랑",
                "API 키가 설정되지 않았습니다. 설정 창에서 입력해주세요."
            )
            self._on_settings()
            return

        self._running = True
        self.tray.set_active(True)
        self.panel.set_active(True)

        # 영역 표시 창 갱신
        rx, ry, rw, rh = region
        self.indicator.set_region(rx, ry, rw, rh)
        self.indicator.set_status("idle")
        self.indicator.show()

        self.tray.show_message("말랑몰랑", "번역을 시작합니다.")

        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
        )
        self._loop_thread.start()

    def _run_loop(self):
        """asyncio 루프를 스레드에서 실행합니다."""
        asyncio.set_event_loop(self._loop)
        try:
            region = tuple(self.config.get("capture.region"))
            self._loop.run_until_complete(
                self.pipeline.run_loop(region=region)
            )
        except Exception as e:
            print(f"[App] 번역 루프 오류: {e}")
        finally:
            self._running = False

    def _stop_translation(self):
        """번역 루프를 중지합니다."""
        if not self._running:
            return

        if self.pipeline:
            self.pipeline.stop()

        self._running = False
        self.tray.set_active(False)
        self.panel.set_active(False)
        self.overlay.hide_translation()
        self.indicator.hide()
        self.tray.show_message("말랑몰랑", "번역을 중지합니다.")

    # ── 시그널 핸들러 ──

    def _on_toggle(self):
        """번역 시작/중지를 토글합니다."""
        if self._running:
            self._stop_translation()
        else:
            self._start_translation()

    def _on_settings(self):
        """설정 창을 엽니다."""
        was_running = self._running
        if was_running:
            self._stop_translation()

        win = SettingsWindow(self.config)
        saved = [False]

        def on_saved():
            saved[0] = True
            self._on_settings_saved()

        win.settings_saved.connect(on_saved)
        win.exec()

        if saved[0]:
            # 설정이 저장됐으면 항상 파이프라인 재생성 후 시작 시도
            self.pipeline = None
            self._start_translation()

    def _on_settings_saved(self):
        """설정 저장 후 오버레이 프리셋을 갱신합니다."""
        preset_name = self.config.get("display.active_preset", "기본")
        self.overlay.set_preset(get_preset_by_name(preset_name))

    def _on_region_select(self):
        """영역 선택 UI를 시작합니다."""
        if self._running:
            self._stop_translation()
        self.region_selector.start()

    def _on_region_selected(self, region: tuple):
        """영역 선택 완료 후 Config를 저장하고 번역을 시작합니다."""
        x, y, w, h = region
        self.config.set("capture.region", [x, y, w, h])
        self.tray.show_message("말랑몰랑", f"영역 설정 완료: {w}×{h}")
        # 번역 중이었다면 영역 표시 창도 즉시 이동
        if self._running:
            self.indicator.set_region(x, y, w, h)
        self._start_translation()

    def _show_panel(self):
        """컨트롤 패널을 화면에 표시합니다."""
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()

    def _init_panel_position(self):
        """컨트롤 패널을 화면 우상단에 배치합니다."""
        screen = self.qt_app.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.panel.adjustSize()
            margin = 16
            self.panel.move(
                geo.right() - self.panel.width() - margin,
                geo.top() + margin,
            )

    def _on_quit(self):
        """앱을 종료합니다."""
        self._stop_translation()

        if self.pipeline:
            # asyncio 루프가 열려있으면 close 실행
            if self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(self.pipeline.close(), self._loop)
            elif self._loop:
                self._loop.run_until_complete(self.pipeline.close())

        self.tray.hide()
        self.qt_app.quit()

    def run(self):
        """앱을 시작합니다. 최초 실행이면 설정 창을 먼저 엽니다."""
        self.tray.show()
        self._init_panel_position()
        self.panel.show()

        # 최초 실행 또는 API 키 미설정이면 설정 창 표시
        first_run = self.config.get("app.first_run", True)

        if first_run or not self._is_provider_configured():
            self.config.set("app.first_run", False)
            self.tray.show_message(
                "말랑몰랑에 오신 것을 환영합니다!",
                "설정에서 API 키를 입력하고 번역 영역을 지정해주세요."
            )
            self._on_settings()
        elif not self.config.get("capture.region"):
            # 프로바이더는 설정됐지만 캡처 영역이 없으면 영역 선택 안내
            self.tray.show_message(
                "말랑몰랑",
                "트레이 아이콘을 우클릭 → '영역 재지정'으로 번역 영역을 지정해주세요."
            )

        return self.qt_app.exec()


def main():
    """말랑몰랑 진입점."""
    qt_app = QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)  # 창을 닫아도 트레이에 계속 상주

    # 시스템 트레이 지원 여부 확인
    if not QApplication.instance().platformName() == "offscreen":
        from PyQt6.QtWidgets import QSystemTrayIcon
        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(
                None,
                "트레이 미지원",
                "이 시스템은 시스템 트레이를 지원하지 않습니다.",
            )
            return 1

    try:
        app = App(qt_app)
        return app.run()
    except Exception as e:
        import traceback
        QMessageBox.critical(
            None,
            "시작 오류",
            f"앱 시작 중 오류가 발생했습니다:\n\n{traceback.format_exc()}"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
