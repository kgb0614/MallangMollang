"""
Unit 6 테스트: ui/tray.py + ui/settings.py + main.py
"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

app = QApplication.instance() or QApplication(sys.argv)


# ─────────────────────────────────────────
# tray.py 테스트
# ─────────────────────────────────────────

class TestTrayIcon:
    def test_create_tray(self):
        """TrayIcon이 생성되는지"""
        from mallangmollang.ui.tray import TrayIcon
        tray = TrayIcon()
        assert tray is not None

    def test_signals_exist(self):
        """필수 시그널 4종이 존재하는지"""
        from mallangmollang.ui.tray import TrayIcon
        tray = TrayIcon()
        assert hasattr(tray, "toggle_requested")
        assert hasattr(tray, "settings_requested")
        assert hasattr(tray, "region_requested")
        assert hasattr(tray, "quit_requested")

    def test_set_active_true(self):
        """활성 상태로 변경 시 메뉴 텍스트가 변경되는지"""
        from mallangmollang.ui.tray import TrayIcon
        tray = TrayIcon()
        tray.set_active(True)
        assert tray._active is True
        assert "중지" in tray._toggle_action.text()

    def test_set_active_false(self):
        """비활성 상태로 변경 시 메뉴 텍스트가 변경되는지"""
        from mallangmollang.ui.tray import TrayIcon
        tray = TrayIcon()
        tray.set_active(True)
        tray.set_active(False)
        assert tray._active is False
        assert "시작" in tray._toggle_action.text()

    def test_toggle_signal(self):
        """toggle_requested 시그널이 발생하는지"""
        from mallangmollang.ui.tray import TrayIcon
        tray = TrayIcon()
        received = []
        tray.toggle_requested.connect(lambda: received.append(True))
        tray._toggle_action.trigger()
        assert len(received) == 1

    def test_settings_signal(self):
        """settings_requested 시그널이 발생하는지"""
        from mallangmollang.ui.tray import TrayIcon
        tray = TrayIcon()
        received = []
        tray.settings_requested.connect(lambda: received.append(True))

        menu = tray._tray.contextMenu()
        settings_action = None
        for action in menu.actions():
            if action.text() == "설정":
                settings_action = action
                break
        assert settings_action is not None
        settings_action.trigger()
        assert len(received) == 1

    def test_quit_signal(self):
        """quit_requested 시그널이 발생하는지"""
        from mallangmollang.ui.tray import TrayIcon
        tray = TrayIcon()
        received = []
        tray.quit_requested.connect(lambda: received.append(True))

        menu = tray._tray.contextMenu()
        quit_action = None
        for action in menu.actions():
            if action.text() == "종료":
                quit_action = action
                break
        assert quit_action is not None
        quit_action.trigger()
        assert len(received) == 1

    def test_make_tray_icon(self):
        """활성/비활성 아이콘이 생성되는지"""
        from mallangmollang.ui.tray import _make_tray_icon
        icon_active = _make_tray_icon(True)
        icon_inactive = _make_tray_icon(False)
        assert not icon_active.isNull()
        assert not icon_inactive.isNull()


# ─────────────────────────────────────────
# settings.py 테스트
# ─────────────────────────────────────────

class TestSettingsWindow:
    def _make_config(self, tmp_path):
        """테스트용 임시 Config를 생성합니다."""
        import mallangmollang.infra.config as cfg_module
        from mallangmollang.infra.config import Config
        # 싱글톤 우회: 직접 인스턴스 생성 후 경로만 바꿈
        old_path = cfg_module._CONFIG_PATH
        cfg_module._CONFIG_PATH = tmp_path / "config.json"
        Config._instance = None
        config = Config.get_instance()
        cfg_module._CONFIG_PATH = old_path
        Config._instance = None
        return config

    def test_create_settings(self, tmp_path):
        """SettingsWindow가 생성되는지"""
        from mallangmollang.ui.settings import SettingsWindow
        config = self._make_config(tmp_path)
        win = SettingsWindow(config)
        assert win is not None

    def test_tabs_exist(self, tmp_path):
        """5개 탭이 모두 존재하는지"""
        from mallangmollang.ui.settings import SettingsWindow
        config = self._make_config(tmp_path)
        win = SettingsWindow(config)
        assert win._tabs.count() == 5
        tab_texts = [win._tabs.tabText(i) for i in range(win._tabs.count())]
        assert "프로바이더" in tab_texts
        assert "언어" in tab_texts
        assert "캡처" in tab_texts
        assert "번역" in tab_texts
        assert "표시" in tab_texts

    def test_load_values(self, tmp_path):
        """Config 기본값이 UI에 올바르게 로드되는지"""
        from mallangmollang.ui.settings import SettingsWindow
        config = self._make_config(tmp_path)
        win = SettingsWindow(config)
        assert win._interval_ms.value() == 1500
        assert win._hash_threshold.value() == 5
        assert win._context_count.value() == 3
        assert win._vision_mode.isChecked() is False

    def test_save_values(self, tmp_path):
        """저장 시 Config에 값이 반영되는지"""
        from mallangmollang.ui.settings import SettingsWindow
        config = self._make_config(tmp_path)
        win = SettingsWindow(config)

        win._interval_ms.setValue(2000)
        win._hash_threshold.setValue(8)
        win._context_count.setValue(5)
        win._vision_mode.setChecked(True)
        win._save()

        assert config.get("capture.interval_ms") == 2000
        assert config.get("detector.hash_threshold") == 8
        assert config.get("translation.context_count") == 5
        assert config.get("translation.vision_mode") is True

    def test_settings_saved_signal(self, tmp_path):
        """저장 시 settings_saved 시그널이 발생하는지"""
        from mallangmollang.ui.settings import SettingsWindow
        config = self._make_config(tmp_path)
        win = SettingsWindow(config)
        received = []
        win.settings_saved.connect(lambda: received.append(True))
        win._save()
        assert len(received) == 1

    def test_language_load(self, tmp_path):
        """언어 설정이 UI에 올바르게 로드되는지"""
        from mallangmollang.ui.settings import SettingsWindow
        config = self._make_config(tmp_path)
        win = SettingsWindow(config)
        assert win._source_lang.currentText() == "auto"
        assert win._target_lang.currentText() == "ko"
        assert win._ocr_lang.currentText() == "eng"

    def test_provider_load(self, tmp_path):
        """프로바이더 설정이 UI에 올바르게 로드되는지"""
        from mallangmollang.ui.settings import SettingsWindow
        config = self._make_config(tmp_path)
        win = SettingsWindow(config)
        assert win._provider_combo.currentText() == "gemini"
        assert win._gemini_model.currentText() == "gemini-2.0-flash"


# ─────────────────────────────────────────
# main.py 테스트
# ─────────────────────────────────────────

class TestApp:
    def _make_app(self, tmp_path):
        import mallangmollang.infra.config as cfg_module
        from mallangmollang.infra.config import Config
        from mallangmollang.main import App

        old_path = cfg_module._CONFIG_PATH
        cfg_module._CONFIG_PATH = tmp_path / "config.json"
        Config._instance = None
        a = App(app)
        cfg_module._CONFIG_PATH = old_path
        Config._instance = None
        return a

    def test_create_app(self, tmp_path):
        """App이 생성되는지"""
        a = self._make_app(tmp_path)
        assert a is not None
        assert a.tray is not None
        assert a.overlay is not None
        assert a.region_selector is not None

    def test_toggle_starts_without_region(self, tmp_path):
        """영역 미지정 상태에서 토글 시 영역 선택 UI로 유도되는지"""
        a = self._make_app(tmp_path)
        # 영역 없음 확인
        assert a.config.get("capture.region") is None
        # 토글 → 영역 선택 UI가 기동 시도 (region_selector.start가 불려야 함)
        selector_started = []
        a.region_selector.region_selected.connect(lambda r: selector_started.append(r))
        # 실제로 start()를 호출하는 대신 _running이 False로 유지되는지만 확인
        a._on_toggle()
        assert a._running is False

    def test_on_region_selected_saves_config(self, tmp_path):
        """영역 선택 완료 시 Config에 저장되는지 (_start_translation은 모킹)"""
        a = self._make_app(tmp_path)
        # _start_translation을 모킹하여 블로킹 방지
        started = []
        a._start_translation = lambda: started.append(True)
        a._on_region_selected((100, 200, 300, 150))
        assert a.config.get("capture.region") == [100, 200, 300, 150]

    def test_on_settings_saved_updates_preset(self, tmp_path):
        """설정 저장 후 오버레이 프리셋이 갱신되는지"""
        a = self._make_app(tmp_path)
        a.config.set("display.active_preset", "어두운 게임용")
        a._on_settings_saved()
        assert a.overlay.preset.name == "어두운 게임용"

    def test_stop_translation_when_not_running(self, tmp_path):
        """실행 중이 아닐 때 중지를 호출해도 오류가 없는지"""
        a = self._make_app(tmp_path)
        a._stop_translation()  # 오류 없이 통과해야 함

    def test_build_pipeline_without_api_key(self, tmp_path):
        """API 키 없을 때 pipeline이 None을 반환하는지"""
        a = self._make_app(tmp_path)
        a.config.set("provider.gemini.api_key", "")
        result = a._build_pipeline()
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
