"""
말랑몰랑 (MallangMollang) 진입점
모든 컴포넌트를 조립하고 앱을 실행합니다.
"""

import asyncio
import sys
import threading

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from pathlib import Path

from mallangmollang.infra.config import Config
from mallangmollang.infra.hotkeys import HotkeyManager
from mallangmollang.core.cache import TranslationCache
from mallangmollang.core.pipeline import Pipeline
from mallangmollang.display.overlay import OverlayWindow
from mallangmollang.display.area_indicator import AreaIndicatorWindow
from mallangmollang.display.panel import SidePanel
from mallangmollang.display.presets import get_preset_by_name
from mallangmollang.ui.tray import TrayIcon
from mallangmollang.ui.settings import SettingsWindow
from mallangmollang.ui.region_selector import RegionSelector
from mallangmollang.core.profiles import ProfileManager
from mallangmollang.core.user_dict import UserDictionary
from mallangmollang.ui.control_panel import ControlPanel
from mallangmollang.ui.toast import ToastManager


# 캐시 파일 경로 (config.json과 동일 위치)
_CACHE_PATH = Path(__file__).parent.parent / "translation_cache.json"
_DICT_PATH = Path(__file__).parent.parent / "user_dict.json"


class _Bridge(QObject):
    """
    asyncio 스레드 → Qt 메인 스레드로 번역 결과를 안전하게 전달하는 브리지.
    Qt 위젯은 메인 스레드에서만 접근해야 하므로, 시그널을 통해 전달합니다.
    """
    # (번역 텍스트, 캡처 영역, region_id, 캡처 이미지 or None)
    translation_ready = pyqtSignal(str, object, int, object)
    lines_ready = pyqtSignal(object, object, int, object)
    status_changed = pyqtSignal(str)                   # "idle" | "translating" | "error"
    error_detail = pyqtSignal(str)                     # 에러 상세 메시지


class App:
    """
    말랑몰랑 앱 컨트롤러.
    Qt 이벤트 루프와 asyncio 파이프라인 루프를 연결하여 전체 동작을 관리합니다.
    """

    def __init__(self, qt_app: QApplication):
        self.qt_app = qt_app
        self.config = Config.get_instance()

        # 영속 캐시: 앱 시작 시 디스크에서 로드
        self.cache = TranslationCache(
            max_size=self.config.get("cache.max_size", 100)
        )
        self.cache.load(_CACHE_PATH)

        # 사용자 번역 사전
        self.user_dict = UserDictionary()
        self.user_dict.load(_DICT_PATH)

        # 컴포넌트 초기화 — 다중 영역용 딕셔너리 (region_id → 위젯)
        self._overlays: dict[int, OverlayWindow] = {}
        self._indicators: dict[int, AreaIndicatorWindow] = {}
        # 하위호환: 단일 영역용 기본 오버레이/인디케이터
        self.overlay = OverlayWindow(
            preset=get_preset_by_name(self.config.get("display.active_preset", "기본"))
        )
        self.indicator = AreaIndicatorWindow()
        self.side_panel = SidePanel()
        self.panel = ControlPanel()
        self.tray = TrayIcon()
        self.region_selector = RegionSelector()
        self.hotkeys = HotkeyManager(self.config)
        self.toast = ToastManager.get_instance()
        self.profile_manager = ProfileManager()
        self.pipeline: Pipeline | None = None

        # asyncio 스레드 → Qt 메인 스레드 브리지
        self._bridge = _Bridge()
        self._bridge.translation_ready.connect(self._on_translation_ready)
        self._bridge.lines_ready.connect(self._on_lines_ready)
        self._bridge.status_changed.connect(self._on_status_changed)
        self._bridge.error_detail.connect(self._on_error_detail)

        # 번역 루프 실행을 위한 asyncio 이벤트 루프 (별도 스레드)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        self._running = False
        self._snapshot_running = False

        # 영역 핸들: 영역 지정 즉시 표시, 항상 편집 가능
        self._region_handles: dict[int, "RegionHandle"] = {}

        # 윈도우 추적: 윈도우 모드에서 창 위치 변화 감지
        self._window_track_timer = QTimer()
        self._window_track_timer.setInterval(300)
        self._window_track_timer.timeout.connect(self._track_window_position)
        self._last_window_pos: tuple[int, int] | None = None

        self._connect_signals()
        self._init_region_handles()
        self._start_window_tracking()

    def _connect_signals(self):
        """각 컴포넌트의 시그널을 슬롯에 연결합니다."""
        # 트레이 시그널
        self.tray.toggle_requested.connect(self._on_toggle)
        self.tray.settings_requested.connect(self._on_settings)
        self.tray.region_requested.connect(self._on_region_select)
        self.tray.panel_requested.connect(self._show_panel)
        self.tray.ocr_preview_requested.connect(self._on_ocr_preview)
        self.tray.debug_copy_requested.connect(self._copy_debug_info)
        self.tray.quit_requested.connect(self._on_quit)

        # 컨트롤 패널 시그널 (트레이와 동일한 핸들러)
        self.panel.toggle_requested.connect(self._on_toggle)
        self.panel.settings_requested.connect(self._on_settings)
        self.panel.region_requested.connect(self._on_region_select)
        self.panel.quit_requested.connect(self._on_quit)

        self.region_selector.region_selected.connect(self._on_region_selected)
        self.region_selector.selection_cancelled.connect(self._on_region_cancelled)

        # 전역 단축키
        self.hotkeys.toggle_requested.connect(self._on_toggle)
        self.hotkeys.region_requested.connect(self._on_region_select)
        self.hotkeys.dismiss_requested.connect(self._on_dismiss)

        # 오버레이 자체 닫힘 시그널 (클릭/자동 타이머)
        self.overlay.dismissed.connect(self._on_overlay_dismissed)

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

        pipeline = Pipeline.from_config(self.config, cache=self.cache, user_dict=self.user_dict)

        def on_result(result):
            region_tuple = result.capture.region
            rid = result.region_id
            img = result.capture.image

            # 줄 단위 번역 결과가 있으면 줄 모드로 전달
            if result.line_translations:
                self._bridge.lines_ready.emit(result.line_translations, region_tuple, rid, img)
            elif result.translation and result.translation.translated:
                self._bridge.translation_ready.emit(
                    result.translation.translated, region_tuple, rid, img,
                )

        pipeline.on_result(on_result)
        pipeline.on_status(lambda status: self._bridge.status_changed.emit(status))
        pipeline.on_error(lambda msg: self._bridge.error_detail.emit(msg))
        return pipeline

    def _get_overlay(self, region_id: int) -> OverlayWindow:
        """영역 ID에 대응하는 오버레이 위젯을 반환합니다 (없으면 생성)."""
        if region_id == 0:
            return self.overlay
        if region_id not in self._overlays:
            ov = OverlayWindow(
                preset=get_preset_by_name(self.config.get("display.active_preset", "기본"))
            )
            ov.dismissed.connect(lambda rid=region_id: self._on_overlay_dismissed_region(rid))
            self._overlays[region_id] = ov
        return self._overlays[region_id]

    def _get_indicator(self, region_id: int) -> AreaIndicatorWindow:
        """영역 ID에 대응하는 인디케이터를 반환합니다 (없으면 생성)."""
        if region_id == 0:
            return self.indicator
        if region_id not in self._indicators:
            self._indicators[region_id] = AreaIndicatorWindow()
        return self._indicators[region_id]

    def _on_translation_ready(self, text: str, region, region_id: int, image=None):
        """번역 결과를 표시 모드에 따라 오버레이 또는 사이드 패널에 보냅니다."""
        self.side_panel.add_entry(text)
        if self.config.get("display.mode", "overlay") != "panel":
            self._hide_indicator_for(region_id)
            ov = self._get_overlay(region_id)
            self._apply_auto_colors(ov, image)
            ov.show_translation(text, region=region)
            self._apply_snapshot_overlay_mode_for(ov)
        self._copy_to_clipboard(text)

    def _on_lines_ready(self, line_translations, region, region_id: int, image=None):
        """줄 단위 번역 결과를 표시 모드에 따라 분기합니다."""
        original = "\n".join(lt.line_box.text for lt in line_translations)
        translated = "\n".join(lt.translated for lt in line_translations)
        self.side_panel.add_entry(translated, original)
        if self.config.get("display.mode", "overlay") != "panel":
            self._hide_indicator_for(region_id)
            from mallangmollang.display.overlay import TranslatedLine
            lines = [
                TranslatedLine(
                    text=lt.translated,
                    x=lt.line_box.x,
                    y=lt.line_box.y,
                    width=lt.line_box.width,
                    height=lt.line_box.height,
                    font_pt=lt.line_box.font_pt,
                )
                for lt in line_translations
            ]
            ov = self._get_overlay(region_id)
            self._apply_auto_colors(ov, image)
            ov.show_lines(lines, region=region)
            self._apply_snapshot_overlay_mode_for(ov)
        self._copy_to_clipboard(translated)

    def _hide_indicator_for(self, region_id: int):
        """오버레이 표시 시 해당 영역의 인디케이터를 숨깁니다."""
        if region_id == 0:
            self.indicator.hide()
        elif region_id in self._indicators:
            self._indicators[region_id].hide()

    def _on_status_changed(self, status: str):
        """파이프라인 상태를 영역 표시 창과 컨트롤 패널에 반영합니다."""
        # 모든 인디케이터 상태 업데이트
        self.indicator.set_status(status)
        for ind in self._indicators.values():
            ind.set_status(status)

        if status == "translating":
            self.overlay.hide_translation()
            self.panel.set_status("● 번역 중...", "rgba(255,210,50,220)")
        elif status == "error":
            self.panel.set_status("● 오류 발생", "rgba(220,50,50,220)")
        elif status == "idle" and self._running:
            self.panel.set_status("● 대기 중", "rgba(100,200,100,220)")

        # 스냅샷 완료 후 영역 핸들 복원
        if status in ("idle", "error") and not self._running:
            self._show_region_handles()
            self.panel.set_status("● 대기", "rgba(180,180,180,220)")

    def _on_error_detail(self, message: str):
        """에러 상세 메시지를 토스트로 표시합니다."""
        short = message if len(message) <= 120 else message[:120] + "…"
        self.toast.show(f"오류: {short}", "error", 5000)

    def _copy_debug_info(self):
        """마지막 번역 사이클의 진단 정보를 클립보드에 복사합니다."""
        from mallangmollang.core.pipeline import _LOG_PATH
        if self.pipeline and self.pipeline.last_debug_info:
            QApplication.clipboard().setText(self.pipeline.last_debug_info)
            self.toast.show(
                f"클립보드에 복사됨. 전체 로그: {_LOG_PATH.name}",
                "success", 4000,
            )
        elif _LOG_PATH.exists():
            self.toast.show(
                f"로그 파일: {_LOG_PATH}",
                "info", 5000,
            )
        else:
            self.toast.show("아직 번역 결과가 없습니다.", "info")

    def _start_translation(self):
        """별도 스레드에서 asyncio 번역 루프를 시작합니다."""
        if self._running:
            return

        # 다중 영역 또는 단일 영역 확인
        regions = self.config.get_regions()
        region = self.config.get("capture.region")
        if not regions and not region:
            self.toast.show("번역 영역을 먼저 지정해주세요.", "warning")
            self._on_region_select()
            return

        self.pipeline = self._build_pipeline()
        if self.pipeline is None:
            self.toast.show("API 키가 설정되지 않았습니다.", "error")
            self._on_settings()
            return

        self._running = True
        self.tray.set_active(True)
        self.panel.set_active(True)
        self._hide_region_handles()

        # 영역별 인디케이터 표시
        if regions:
            for r in regions:
                ind = self._get_indicator(r["id"])
                sr = self._relative_to_screen(r["rect"])
                ind.set_region(sr[0], sr[1], sr[2], sr[3])
                ind.set_status("idle")
                ind.show()
        elif region:
            sr = self._relative_to_screen(list(region))
            self.indicator.set_region(sr[0], sr[1], sr[2], sr[3])
            self.indicator.set_status("idle")
            self.indicator.show()

        # 패널 모드이면 사이드 패널 표시
        if self.config.get("display.mode", "overlay") == "panel":
            self.side_panel.show()

        self.toast.show("번역을 시작합니다.", "success")

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
            regions = self.config.get_regions()
            if regions:
                self._loop.run_until_complete(
                    self.pipeline.run_loop(regions=regions)
                )
            else:
                region = tuple(self.config.get("capture.region"))
                self._loop.run_until_complete(
                    self.pipeline.run_loop(region=region)
                )
        except Exception as e:
            print(f"[App] 번역 루프 오류: {e}")
            self._bridge.error_detail.emit(str(e))
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
        for ov in self._overlays.values():
            ov.hide_translation()
        for ind in self._indicators.values():
            ind.hide()
        self._show_region_handles()
        self.toast.show("번역을 중지합니다.", "info")

    def _apply_profile(self):
        """활성 번역 프로필을 translator에 반영합니다."""
        active = self.config.get("translation.active_profile", "")
        hint = self.profile_manager.build_hint(active)
        if self.pipeline:
            self.pipeline.translator.set_profile_hint(hint)
        if active:
            print(f"[App] 번역 프로필 적용: {active}")

    def _ensure_pipeline(self) -> bool:
        """Pipeline이 없으면 생성합니다. 실패 시 False 반환."""
        if self.pipeline is None:
            self.pipeline = self._build_pipeline()
            self._apply_profile()
        if self.pipeline is None:
            self.toast.show("API 키가 설정되지 않았습니다.", "error")
            self._on_settings()
            return False
        return True

    def _run_snapshot(self):
        """한 번만 캡처-번역을 실행합니다 (스냅샷 모드)."""
        if self._snapshot_running:
            return

        regions = self.config.get_regions()
        region = self.config.get("capture.region")
        if not regions and not region:
            self.toast.show("번역 영역을 먼저 지정해주세요.", "warning")
            self._on_region_select()
            return

        # 스냅샷마다 파이프라인 새로 생성 (이전 이벤트 루프 참조 방지)
        self.pipeline = None
        if not self._ensure_pipeline():
            return

        self._snapshot_running = True
        self._hide_region_handles()

        # 영역별 인디케이터 표시
        if regions:
            for r in regions:
                ind = self._get_indicator(r["id"])
                sr = self._relative_to_screen(r["rect"])
                ind.set_region(sr[0], sr[1], sr[2], sr[3])
                ind.show()
        elif region:
            sr = self._relative_to_screen(list(region))
            self.indicator.set_region(sr[0], sr[1], sr[2], sr[3])
            self.indicator.show()

        self.panel.set_status("● 번역 중...", "rgba(255,210,50,220)")

        if self.config.get("display.mode", "overlay") == "panel":
            self.side_panel.show()

        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                if regions:
                    for r in regions:
                        loop.run_until_complete(
                            self.pipeline.run_once(
                                region=tuple(r["rect"]),
                                region_id=r["id"],
                            )
                        )
                else:
                    loop.run_until_complete(
                        self.pipeline.run_once(region=tuple(region))
                    )
                self._bridge.status_changed.emit("idle")
            except Exception as e:
                print(f"[App] 스냅샷 오류: {e}")
                self._bridge.error_detail.emit(str(e))
                self._bridge.status_changed.emit("error")
            finally:
                self._snapshot_running = False
                loop.close()

        threading.Thread(target=run, daemon=True).start()

    def _copy_to_clipboard(self, text: str):
        """auto_clipboard 설정이 활성화되어 있으면 번역 결과를 클립보드에 복사합니다."""
        if self.config.get("translation.auto_clipboard", False) and text.strip():
            QApplication.clipboard().setText(text)

    def _apply_auto_colors(self, ov: OverlayWindow, image=None):
        """자동 색상 매핑이 활성화되어 있으면 캡처 이미지를 분석하여 오버레이 색상을 설정합니다."""
        if not self.config.get("display.auto_color", False) or image is None:
            ov.set_auto_colors(None, None)
            return
        from mallangmollang.display.auto_color import analyze_colors
        text_color, outline_color = analyze_colors(image)
        ov.set_auto_colors(text_color, outline_color)

    def _apply_snapshot_overlay_mode_for(self, ov: OverlayWindow):
        """스냅샷 모드일 때 오버레이에 클릭 닫기 + 자동 타이머를 설정합니다."""
        mode = self.config.get("translation.run_mode", "realtime")
        if mode == "snapshot":
            auto_ms = self.config.get("display.snapshot_auto_dismiss_ms", 0)
            ov.set_snapshot_mode(True, auto_ms)
        else:
            ov.set_snapshot_mode(False)

    def _init_region_handles(self):
        """앱 시작 시 기존 영역들의 편집 핸들을 생성합니다."""
        from mallangmollang.ui.region_editor import RegionHandle

        for r in self.config.get_all_regions():
            screen_rect = self._relative_to_screen(r["rect"])
            handle = RegionHandle(r["id"], r.get("name", ""), screen_rect)
            handle.region_changed.connect(self._on_region_handle_changed)
            handle.region_deleted.connect(self._on_region_handle_deleted)
            handle.translate_requested.connect(self._on_region_translate)
            handle.show()
            self._region_handles[r["id"]] = handle

    def _create_region_handle(self, region_id: int, name: str, rect: list[int]):
        """새 영역에 대한 편집 핸들을 생성하고 표시합니다."""
        from mallangmollang.ui.region_editor import RegionHandle

        handle = RegionHandle(region_id, name, rect)
        handle.region_changed.connect(self._on_region_handle_changed)
        handle.region_deleted.connect(self._on_region_handle_deleted)
        handle.translate_requested.connect(self._on_region_translate)
        handle.show()
        self._region_handles[region_id] = handle

    def _show_region_handles(self):
        """모든 영역 핸들을 표시합니다."""
        for handle in self._region_handles.values():
            handle.show()

    def _hide_region_handles(self):
        """모든 영역 핸들을 숨깁니다 (번역 중에는 방해되지 않도록)."""
        for handle in self._region_handles.values():
            handle.hide()

    # ── 윈도우 추적 ──

    def _is_window_mode(self) -> bool:
        return self.config.get("capture.target_mode", "screen") == "window"

    def _get_window_origin(self) -> tuple[int, int] | None:
        """현재 대상 윈도우의 좌상단 좌표를 반환합니다."""
        if not self._is_window_mode():
            return None
        title = self.config.get("capture.window_title", "")
        if not title:
            return None
        from mallangmollang.core.capture import ScreenCapture
        rect = ScreenCapture.get_window_rect(title)
        if rect is None:
            return None
        return (rect[0], rect[1])

    def _screen_to_relative(self, abs_rect: list[int]) -> list[int]:
        """절대 화면 좌표 → 윈도우 기준 상대 좌표. 윈도우 모드가 아니면 그대로 반환."""
        origin = self._get_window_origin()
        if origin is None:
            return abs_rect
        wx, wy = origin
        return [abs_rect[0] - wx, abs_rect[1] - wy, abs_rect[2], abs_rect[3]]

    def _relative_to_screen(self, rel_rect: list[int]) -> list[int]:
        """윈도우 기준 상대 좌표 → 절대 화면 좌표. 윈도우 모드가 아니면 그대로 반환."""
        origin = self._get_window_origin()
        if origin is None:
            return rel_rect
        wx, wy = origin
        return [rel_rect[0] + wx, rel_rect[1] + wy, rel_rect[2], rel_rect[3]]

    def _start_window_tracking(self):
        """윈도우 모드이면 위치 추적 타이머를 시작합니다."""
        if self._is_window_mode():
            self._last_window_pos = self._get_window_origin()
            self._window_track_timer.start()
        else:
            self._window_track_timer.stop()

    def _track_window_position(self):
        """윈도우 위치가 변했으면 핸들들을 이동시킵니다."""
        if not self._is_window_mode():
            self._window_track_timer.stop()
            return
        current = self._get_window_origin()
        if current is None or current == self._last_window_pos:
            return
        self._last_window_pos = current
        self._update_handle_positions()

    def _update_handle_positions(self):
        """저장된 상대 좌표를 현재 윈도우 위치로 변환하여 핸들을 이동합니다."""
        for r in self.config.get_all_regions():
            handle = self._region_handles.get(r["id"])
            if handle:
                screen_rect = self._relative_to_screen(r["rect"])
                handle.update_rect(screen_rect)

    def _on_dismiss(self):
        """ESC 키로 모든 오버레이를 숨깁니다. 영역 핸들은 유지됩니다."""
        self.overlay.hide_translation()
        self.indicator.hide()
        for ov in self._overlays.values():
            ov.hide_translation()
        for ind in self._indicators.values():
            ind.hide()

    def _on_overlay_dismissed(self):
        """기본 오버레이가 닫혔을 때 기본 영역 표시도 숨깁니다."""
        self.indicator.hide()

    def _on_overlay_dismissed_region(self, region_id: int):
        """특정 영역의 오버레이가 닫혔을 때 해당 인디케이터도 숨깁니다."""
        if region_id in self._indicators:
            self._indicators[region_id].hide()

    def _on_region_handle_changed(self, region_id: int, rect: list[int]):
        """편집 핸들에서 영역 위치/크기가 변경되었을 때."""
        store_rect = self._screen_to_relative(rect)
        self.config.update_region(region_id, rect=store_rect)

    def _on_region_handle_deleted(self, region_id: int):
        """편집 핸들에서 영역 삭제가 요청되었을 때."""
        self.config.remove_region(region_id)
        # 해당 핸들 제거 및 정리
        handle = self._region_handles.pop(region_id, None)
        if handle:
            handle.hide()
            handle.deleteLater()
        if region_id in self._overlays:
            self._overlays.pop(region_id).deleteLater()
        if region_id in self._indicators:
            self._indicators.pop(region_id).deleteLater()
        self.toast.show("영역 삭제됨", "info")

    def _on_region_translate(self, region_id: int):
        """영역 핸들의 ▶ 버튼 — 해당 영역만 스냅샷 번역합니다."""
        if self._snapshot_running or self._running:
            return

        region_data = None
        for r in self.config.get_all_regions():
            if r["id"] == region_id:
                region_data = r
                break
        if not region_data:
            return

        self.pipeline = None
        if not self._ensure_pipeline():
            return

        self._snapshot_running = True

        if self.config.get("display.mode", "overlay") == "panel":
            self.side_panel.show()

        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    self.pipeline.run_once(
                        region=tuple(region_data["rect"]),
                        region_id=region_data["id"],
                    )
                )
                self._bridge.status_changed.emit("idle")
            except Exception as e:
                print(f"[App] 영역 {region_id} 스냅샷 오류: {e}")
                self._bridge.error_detail.emit(str(e))
                self._bridge.status_changed.emit("error")
            finally:
                self._snapshot_running = False
                loop.close()

        threading.Thread(target=run, daemon=True).start()

    def _on_ocr_preview(self):
        """현재 캡처 영역의 OCR 전처리 결과를 미리보기 창에 표시합니다."""
        region = self.config.get("capture.region")
        if not region:
            self.toast.show("영역을 먼저 지정해주세요.", "warning")
            return

        from mallangmollang.core.capture import ScreenCapture
        from mallangmollang.core.ocr import OcrEngine
        from mallangmollang.ui.ocr_preview import OcrPreviewDialog

        capture = ScreenCapture()
        capture_result = capture.capture_region(tuple(region))
        if capture_result is None:
            self.toast.show("캡처 실패", "error")
            return

        ocr = OcrEngine()
        lang = self.config.get("language.ocr_lang", "auto")
        original, preprocessed, bbox_overlay, ocr_text = ocr.preview_preprocess(
            capture_result.image, lang,
        )

        dialog = OcrPreviewDialog(original, preprocessed, bbox_overlay, ocr_text)
        dialog.exec()

    # ── 시그널 핸들러 ──

    def _on_toggle(self):
        """번역 시작/중지를 토글합니다. 모드에 따라 동작이 다릅니다."""
        mode = self.config.get("translation.run_mode", "realtime")
        if mode == "snapshot":
            self._run_snapshot()
        else:
            if self._running:
                self._stop_translation()
            else:
                self._start_translation()

    def _on_settings(self):
        """설정 창을 엽니다."""
        was_running = self._running
        if was_running:
            self._stop_translation()

        # 프로필 자동 생성용 provider 연결
        if self._is_provider_configured():
            try:
                from mallangmollang.providers import create_provider
                self.profile_manager._provider = create_provider(self.config)
            except Exception:
                pass

        win = SettingsWindow(self.config, profile_manager=self.profile_manager,
                             user_dict=self.user_dict)
        saved = [False]

        def on_saved():
            saved[0] = True
            self._on_settings_saved()

        win.settings_saved.connect(on_saved)
        win.exec()

        if saved[0]:
            self.pipeline = None
            mode = self.config.get("translation.run_mode", "realtime")
            if mode == "realtime":
                self._start_translation()
            # snapshot 모드에서는 자동 시작하지 않음 — 사용자가 직접 클릭

    def _on_settings_saved(self):
        """설정 저장 후 오버레이 프리셋, 패널 모드, 단축키, 번역 프로필을 갱신합니다."""
        preset_name = self.config.get("display.active_preset", "기본")
        preset = get_preset_by_name(preset_name)
        self.overlay.set_preset(preset)
        for ov in self._overlays.values():
            ov.set_preset(preset)
        mode = self.config.get("translation.run_mode", "realtime")
        self.panel.set_mode(mode)
        self.hotkeys.reload()
        self._apply_profile()

        # 표시 모드 전환 반영
        display_mode = self.config.get("display.mode", "overlay")
        if display_mode == "panel":
            self.overlay.hide_translation()
            self.side_panel.show()
        else:
            self.side_panel.hide()

        # 윈도우 추적 재시작 (설정 변경 반영)
        self._start_window_tracking()
        if self._is_window_mode():
            self._update_handle_positions()

    def _on_region_select(self):
        """영역 선택 UI를 시작합니다. 패널을 숨겨서 간섭을 방지합니다."""
        if self._running:
            self._stop_translation()
        self.panel.hide()
        self.region_selector.start()

    def _on_region_selected(self, region: tuple):
        """영역 선택 완료 후 Config에 추가하고 편집 핸들을 즉시 표시합니다."""
        x, y, w, h = region
        regions = self.config.get_all_regions()
        if len(regions) >= 5:
            self.toast.show("영역은 최대 5개까지 지정할 수 있습니다.", "warning")
            self.panel.show()
            return

        # 윈도우 모드: 절대 좌표를 윈도우 기준 상대 좌표로 변환하여 저장
        store_rect = self._screen_to_relative([x, y, w, h])
        new_region = self.config.add_region(store_rect)
        if new_region:
            # 핸들은 절대 좌표로 표시
            self._create_region_handle(
                new_region["id"], new_region["name"], [x, y, w, h],
            )
            self.toast.show(f"영역 추가: {new_region['name']} ({w}×{h})", "success")
        self.panel.show()

    def _on_region_cancelled(self):
        """영역 선택이 취소되면 패널을 복원합니다."""
        self.panel.show()
        self.toast.show("영역 선택이 취소되었습니다.", "info")

    def _show_panel(self):
        """컨트롤 패널을 화면에 표시합니다."""
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()

    def _init_panel_position(self):
        """컨트롤 패널과 사이드 패널을 화면 우측에 배치합니다."""
        screen = self.qt_app.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.panel.adjustSize()
            margin = 16

            # 사이드 패널: 우측, 컨트롤 패널 아래
            self.side_panel.move(
                geo.right() - self.side_panel.width() - margin,
                geo.top() + margin + self.panel.height() + 8,
            )
            self.panel.move(
                geo.right() - self.panel.width() - margin,
                geo.top() + margin,
            )

    def _on_quit(self):
        """앱을 종료합니다."""
        self._stop_translation()

        # 영속 캐시: 디스크에 저장
        self.cache.save(_CACHE_PATH)

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
        mode = self.config.get("translation.run_mode", "realtime")
        self.panel.set_mode(mode)
        self.panel.show()
        self.hotkeys.start()

        # 최초 실행 또는 API 키 미설정이면 설정 창 표시
        first_run = self.config.get("app.first_run", True)

        if first_run or not self._is_provider_configured():
            self.config.set("app.first_run", False)
            self.toast.show("API 키를 설정하고 번역 영역을 지정해주세요.", "info", 5000)
            self._on_settings()
        elif not self.config.get("capture.region"):
            self.toast.show("영역 버튼을 눌러 번역 영역을 지정해주세요.", "info", 5000)

        return self.qt_app.exec()


def main():
    """말랑몰랑 진입점."""
    # --debug 플래그: 오버레이가 스크린샷에 잡히도록 허용
    if "--debug" in sys.argv:
        from mallangmollang.display.area_indicator import set_debug_capture
        set_debug_capture(True)
        sys.argv.remove("--debug")
        print("[DEBUG] 디버그 모드 활성화 — 오버레이가 스크린샷에 표시됩니다.")
        print("[DEBUG] ⚠ 실시간 모드에서는 오버레이가 재캡처되어 피드백 루프가 발생합니다.")
        print("[DEBUG]   → 스냅샷 모드 사용을 권장합니다.")

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
