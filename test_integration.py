"""
통합 테스트: Unit 1~6 전체 연결 검증

실제 API 호출 없이 파이프라인 전체 흐름과 컴포넌트 간 인터페이스를 검증합니다.
"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from PIL import Image
import numpy as np

from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)


# ─────────────────────────────────────────
# 헬퍼: 테스트용 가짜 이미지와 Config 생성
# ─────────────────────────────────────────

def _make_image(w=200, h=100, color=(255, 255, 255)):
    return Image.fromarray(np.full((h, w, 3), color, dtype=np.uint8))


def _make_config(tmp_path):
    import mallangmollang.infra.config as cfg_module
    from mallangmollang.infra.config import Config
    old_path = cfg_module._CONFIG_PATH
    cfg_module._CONFIG_PATH = tmp_path / "config.json"
    Config._instance = None
    config = Config.get_instance()
    cfg_module._CONFIG_PATH = old_path
    Config._instance = None
    return config


# ─────────────────────────────────────────
# 1. 임포트 충돌 / 순환 참조 없는지 확인
# ─────────────────────────────────────────

class TestImports:
    def test_all_modules_importable(self):
        """모든 모듈이 오류 없이 임포트되는지"""
        import mallangmollang.infra.config
        import mallangmollang.providers.base
        import mallangmollang.providers.gemini
        import mallangmollang.providers
        import mallangmollang.core.capture
        import mallangmollang.core.ocr
        import mallangmollang.core.translator
        import mallangmollang.core.cache
        import mallangmollang.core.detector
        import mallangmollang.core.pipeline
        import mallangmollang.display.presets
        import mallangmollang.display.overlay
        import mallangmollang.display
        import mallangmollang.ui.region_selector
        import mallangmollang.ui.tray
        import mallangmollang.ui.settings
        import mallangmollang.ui
        import mallangmollang.main

    def test_display_package_exports(self):
        """display 패키지가 OverlayWindow, OverlayPreset을 노출하는지"""
        from mallangmollang.display import OverlayWindow, OverlayPreset, BUILTIN_PRESETS, get_preset_by_name
        assert OverlayWindow is not None
        assert OverlayPreset is not None

    def test_ui_package_exports(self):
        """ui 패키지가 RegionSelector를 노출하는지"""
        from mallangmollang.ui import RegionSelector
        assert RegionSelector is not None


# ─────────────────────────────────────────
# 2. Config → Provider 연결
# ─────────────────────────────────────────

class TestConfigToProvider:
    def test_create_provider_from_config(self, tmp_path):
        """Config 설정으로 GeminiProvider가 생성되는지"""
        from mallangmollang.infra.config import Config
        from mallangmollang.providers import create_provider
        from mallangmollang.providers.gemini import GeminiProvider
        config = _make_config(tmp_path)
        config.set("provider.active", "gemini")
        config.set("provider.gemini.api_key", "test-key")
        config.set("provider.gemini.model", "gemini-2.0-flash")

        provider = create_provider(config)
        assert isinstance(provider, GeminiProvider)
        assert provider.api_key == "test-key"
        assert provider.model == "gemini-2.0-flash"

    def test_unknown_provider_raises(self, tmp_path):
        """지원하지 않는 프로바이더는 ValueError를 발생시키는지"""
        from mallangmollang.providers import create_provider
        config = _make_config(tmp_path)
        config.set("provider.active", "unknown_llm")
        with pytest.raises(ValueError, match="지원하지 않는 프로바이더"):
            create_provider(config)

    def test_provider_supports_vision(self, tmp_path):
        """Vision 지원 모델이 올바르게 인식되는지"""
        from mallangmollang.providers import create_provider
        config = _make_config(tmp_path)
        config.set("provider.active", "gemini")
        config.set("provider.gemini.api_key", "key")
        config.set("provider.gemini.model", "gemini-2.0-flash")
        provider = create_provider(config)
        assert provider.supports_vision() is True

    def test_provider_vertex_config(self, tmp_path):
        """Vertex AI 설정이 올바르게 전달되는지"""
        from mallangmollang.providers import create_provider
        config = _make_config(tmp_path)
        config.set("provider.active", "gemini")
        config.set("provider.gemini.endpoint", "vertex")
        config.set("provider.gemini.vertex.project_id", "my-project")
        config.set("provider.gemini.vertex.region", "asia-northeast1")
        provider = create_provider(config)
        assert provider.vertex_project_id == "my-project"
        assert provider.vertex_region == "asia-northeast1"


# ─────────────────────────────────────────
# 3. Capture → Detector 연결
# ─────────────────────────────────────────

class TestCaptureToDetector:
    def test_capture_result_passes_to_detector(self):
        """CaptureResult가 ChangeDetector.detect()에 올바르게 전달되는지"""
        import time
        from mallangmollang.core.capture import CaptureResult
        from mallangmollang.core.detector import ChangeDetector

        image = _make_image(100, 50, color=(200, 200, 200))
        capture = CaptureResult(image=image, timestamp=time.time(), region=(0, 0, 100, 50))

        detector = ChangeDetector(threshold=5)
        result = detector.detect(capture)

        # 첫 번째 호출은 항상 changed=True
        assert result.changed is True
        assert isinstance(result.hash_diff, int)
        assert isinstance(result.current_hash, str)

    def test_same_image_not_changed(self):
        """동일 이미지가 두 번 들어오면 변경 없음으로 판단하는지"""
        import time
        from mallangmollang.core.capture import CaptureResult
        from mallangmollang.core.detector import ChangeDetector

        image = _make_image(100, 50, color=(100, 150, 200))
        cap = lambda: CaptureResult(image=image, timestamp=time.time(), region=(0, 0, 100, 50))

        detector = ChangeDetector(threshold=5)
        detector.detect(cap())   # 첫 번째: always True
        result = detector.detect(cap())  # 두 번째: 동일 이미지 → False
        assert result.changed is False


# ─────────────────────────────────────────
# 4. OCR → Cache 연결
# ─────────────────────────────────────────

class TestOcrToCache:
    def test_ocr_result_text_to_cache(self):
        """OcrResult.text가 TranslationCache.lookup/store에 올바르게 사용되는지"""
        from mallangmollang.core.cache import TranslationCache, CacheResult

        cache = TranslationCache(max_size=10)

        ocr_text = "Hello World"
        # 처음엔 미스
        result = cache.lookup(ocr_text)
        assert result.hit is False

        # 저장 후 히트
        cache.store(ocr_text, "안녕 세상")
        result = cache.lookup(ocr_text)
        assert result.hit is True
        assert result.translated == "안녕 세상"

    def test_cache_result_type_matches_translation_result(self):
        """cache hit 시 만들어지는 TranslationResult 타입이 올바른지"""
        from mallangmollang.core.cache import TranslationCache
        from mallangmollang.providers.base import TranslationResult

        cache = TranslationCache()
        cache.store("test", "번역됨")
        cache_result = cache.lookup("test")

        # pipeline.py 153-154 라인과 동일한 방식으로 TranslationResult 생성
        tr = TranslationResult(translated=cache_result.translated)
        assert tr.translated == "번역됨"
        assert tr.corrected_source == ""  # 기본값
        assert tr.tokens_used == 0         # 기본값
        assert tr.provider == ""           # 기본값


# ─────────────────────────────────────────
# 5. Translator → Provider 연결 (모킹)
# ─────────────────────────────────────────

class TestTranslatorToProvider:
    def test_translator_calls_provider_translate(self):
        """Translator가 provider.translate()를 올바른 인자로 호출하는지"""
        from mallangmollang.core.translator import Translator
        from mallangmollang.providers.base import TranslationResult

        mock_provider = AsyncMock()
        mock_provider.translate.return_value = TranslationResult(
            translated="[corrected]: Hello World\n[translated]: 안녕 세상",
            provider="mock",
        )

        translator = Translator(provider=mock_provider, target_lang="ko", context_count=3)

        result = asyncio.get_event_loop().run_until_complete(
            translator.translate_text("Helo Wrold")
        )

        # provider.translate가 호출되었는지
        mock_provider.translate.assert_called_once()
        call_args = mock_provider.translate.call_args
        prompt = call_args[0][0]

        # 프롬프트에 원문이 포함되는지
        assert "Helo Wrold" in prompt
        # 결과가 올바르게 파싱되는지
        assert result.translated == "안녕 세상"
        assert result.corrected_source == "Hello World"

    def test_translator_context_passed_to_next_call(self):
        """이전 번역이 다음 프롬프트에 문맥으로 포함되는지"""
        from mallangmollang.core.translator import Translator
        from mallangmollang.providers.base import TranslationResult

        call_prompts = []

        async def fake_translate(prompt, params=None):
            call_prompts.append(prompt)
            return TranslationResult(
                translated="[corrected]: Text\n[translated]: 텍스트",
                provider="mock",
            )

        mock_provider = AsyncMock()
        mock_provider.translate.side_effect = fake_translate

        translator = Translator(provider=mock_provider, target_lang="ko", context_count=3)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(translator.translate_text("First sentence"))
        loop.run_until_complete(translator.translate_text("Second sentence"))

        # 두 번째 프롬프트에 이전 번역 문맥이 포함되어야 함
        assert len(call_prompts) == 2
        assert "이전 대화 맥락" in call_prompts[1]

    def test_translator_vision_calls_provider(self):
        """translate_vision이 provider.translate_vision()을 호출하는지"""
        from mallangmollang.core.translator import Translator
        from mallangmollang.providers.base import TranslationResult

        mock_provider = AsyncMock()
        mock_provider.translate_vision.return_value = TranslationResult(
            translated="[corrected]: Img text\n[translated]: 이미지 텍스트",
            provider="mock",
        )

        translator = Translator(provider=mock_provider, target_lang="ko")
        image = _make_image()

        result = asyncio.get_event_loop().run_until_complete(
            translator.translate_vision(image)
        )
        mock_provider.translate_vision.assert_called_once()
        assert result.translated == "이미지 텍스트"


# ─────────────────────────────────────────
# 6. Pipeline 전체 흐름 통합 (모킹)
# ─────────────────────────────────────────

class TestPipelineIntegration:
    def _make_pipeline(self, tmp_path):
        from mallangmollang.core.pipeline import Pipeline
        from mallangmollang.core.capture import ScreenCapture, CaptureResult
        from mallangmollang.core.detector import ChangeDetector
        from mallangmollang.core.cache import TranslationCache
        from mallangmollang.core.ocr import OcrEngine, OcrResult
        from mallangmollang.core.translator import Translator
        from mallangmollang.providers.base import TranslationResult

        config = _make_config(tmp_path)
        # 싱글톤 오염 방지: vision_mode 항상 False로 초기화
        config.set("translation.vision_mode", False)

        # 모킹된 컴포넌트들
        mock_capture = MagicMock(spec=ScreenCapture)
        mock_capture.capture_region.return_value = CaptureResult(
            image=_make_image(), timestamp=0.0, region=(0, 0, 200, 100)
        )
        mock_capture.close = MagicMock()

        mock_ocr = MagicMock(spec=OcrEngine)
        mock_ocr.extract_text.return_value = OcrResult(
            text="Hello World", confidence=90.0, regions=[]
        )

        mock_translator = MagicMock(spec=Translator)
        mock_translator.translate_text = AsyncMock(return_value=TranslationResult(
            translated="안녕 세상", corrected_source="Hello World", provider="mock"
        ))
        mock_translator.translate_vision = AsyncMock(return_value=TranslationResult(
            translated="비전 번역", corrected_source="", provider="mock"
        ))
        mock_translator.provider = AsyncMock()
        mock_translator.provider.close = AsyncMock()

        pipeline = Pipeline(
            capture=mock_capture,
            ocr=mock_ocr,
            translator=mock_translator,
            config=config,
            detector=ChangeDetector(threshold=5),
            cache=TranslationCache(max_size=10),
        )
        return pipeline, mock_capture, mock_ocr, mock_translator

    def test_run_once_ocr_path(self, tmp_path):
        """OCR 경로: 캡처 → 감지 → OCR → LLM → 결과"""
        pipeline, cap, ocr, trans = self._make_pipeline(tmp_path)

        result = asyncio.get_event_loop().run_until_complete(
            pipeline.run_once(region=(0, 0, 200, 100))
        )

        assert result.skipped is False
        assert result.translation is not None
        assert result.translation.translated == "안녕 세상"
        cap.capture_region.assert_called_once_with((0, 0, 200, 100))
        ocr.extract_text.assert_called_once()
        trans.translate_text.assert_called_once()

    def test_run_once_detector_skips(self, tmp_path):
        """동일 이미지 두 번 → 두 번째는 detector가 skip하는지"""
        pipeline, cap, ocr, trans = self._make_pipeline(tmp_path)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(pipeline.run_once(region=(0, 0, 200, 100)))  # 첫 번째: 통과
        result = loop.run_until_complete(pipeline.run_once(region=(0, 0, 200, 100)))  # 두 번째: skip

        assert result.skipped is True
        assert result.translation is None
        # OCR과 번역은 두 번째에 호출되지 않아야 함
        assert ocr.extract_text.call_count == 1
        assert trans.translate_text.call_count == 1

    def test_run_once_cache_hit(self, tmp_path):
        """같은 텍스트가 두 번 오면 두 번째는 캐시 히트"""
        from mallangmollang.core.capture import CaptureResult
        from mallangmollang.core.detector import ChangeDetector

        pipeline, cap, ocr, trans = self._make_pipeline(tmp_path)
        # detector를 None으로 비활성화하여 캐시 테스트에 집중
        pipeline.detector = None

        loop = asyncio.get_event_loop()
        # 첫 번째: LLM 호출
        r1 = loop.run_until_complete(pipeline.run_once(region=(0, 0, 200, 100)))
        assert r1.cached is False

        # 두 번째: 동일 텍스트 → 캐시 히트
        r2 = loop.run_until_complete(pipeline.run_once(region=(0, 0, 200, 100)))
        assert r2.cached is True
        # LLM은 첫 번째에만 호출
        assert trans.translate_text.call_count == 1

    def test_run_once_empty_ocr_skips(self, tmp_path):
        """OCR 결과가 빈 문자열이면 번역을 건너뛰는지"""
        from mallangmollang.core.ocr import OcrResult
        pipeline, cap, ocr, trans = self._make_pipeline(tmp_path)
        pipeline.detector = None
        ocr.extract_text.return_value = OcrResult(text="", confidence=0.0, regions=[])

        result = asyncio.get_event_loop().run_until_complete(
            pipeline.run_once(region=(0, 0, 200, 100))
        )
        assert result.skipped is True
        assert result.translation is None
        trans.translate_text.assert_not_called()

    def test_run_once_vision_path(self, tmp_path):
        """Vision 모드: OCR 건너뛰고 translate_vision 호출"""
        pipeline, cap, ocr, trans = self._make_pipeline(tmp_path)
        pipeline.detector = None
        pipeline.config.set("translation.vision_mode", True)

        result = asyncio.get_event_loop().run_until_complete(
            pipeline.run_once(region=(0, 0, 200, 100))
        )

        assert result.ocr is None   # OCR 건너뜀
        assert result.translation.translated == "비전 번역"
        ocr.extract_text.assert_not_called()
        trans.translate_vision.assert_called_once()

    def test_on_result_callback_receives_pipeline_result(self, tmp_path):
        """on_result 콜백이 PipelineResult를 받는지"""
        from mallangmollang.core.pipeline import PipelineResult
        pipeline, cap, ocr, trans = self._make_pipeline(tmp_path)
        pipeline.detector = None
        # 이전 테스트에서 vision_mode가 True로 오염될 수 있으므로 명시적으로 False
        pipeline.config.set("translation.vision_mode", False)

        received = []
        pipeline.on_result(lambda r: received.append(r))

        asyncio.get_event_loop().run_until_complete(
            pipeline.run_once(region=(0, 0, 200, 100))
        )

        assert len(received) == 1
        assert isinstance(received[0], PipelineResult)
        assert received[0].translation.translated == "안녕 세상"

    def test_pipeline_from_config(self, tmp_path):
        """Pipeline.from_config()이 Config로 올바르게 생성되는지"""
        from mallangmollang.core.pipeline import Pipeline
        config = _make_config(tmp_path)
        config.set("provider.active", "gemini")
        config.set("provider.gemini.api_key", "test-key")
        config.set("detector.hash_threshold", 7)
        config.set("cache.max_size", 50)

        pipeline = Pipeline.from_config(config)

        assert pipeline.detector is not None
        assert pipeline.detector.threshold == 7
        assert pipeline.cache is not None
        assert pipeline.cache.max_size == 50


# ─────────────────────────────────────────
# 7. Display 연결: Pipeline → Overlay
# ─────────────────────────────────────────

class TestDisplayIntegration:
    def test_overlay_receives_translation_text(self):
        """OverlayWindow가 번역 텍스트를 올바르게 표시하는지"""
        from mallangmollang.display.overlay import OverlayWindow
        from mallangmollang.display.presets import PRESET_DEFAULT

        overlay = OverlayWindow(preset=PRESET_DEFAULT)
        overlay.show_translation("번역 결과 테스트", position=(10, 10))

        assert overlay._label.text() == "번역 결과 테스트"
        assert overlay.isVisible()
        overlay.hide()

    def test_preset_name_from_config_loads_correctly(self):
        """Config의 프리셋 이름으로 올바른 OverlayPreset이 로드되는지"""
        from mallangmollang.display.presets import get_preset_by_name, PRESET_DARK_GAME

        preset = get_preset_by_name("어두운 게임용")
        assert preset.name == PRESET_DARK_GAME.name
        assert preset.font_bold == PRESET_DARK_GAME.font_bold

    def test_overlay_show_with_region_positions_below_capture(self):
        """region 인자로 호출 시 캡처 영역 바로 아래에 오버레이가 위치하는지"""
        from mallangmollang.display.overlay import OverlayWindow
        overlay = OverlayWindow()
        # region = (x=50, y=100, w=300, h=80) → 오버레이 y = 100 + 80 + 4 = 184
        overlay.show_translation("위치 테스트", region=(50, 100, 300, 80))
        assert overlay.y() == 184
        overlay.hide()


# ─────────────────────────────────────────
# 8. UI → Config 저장/로드 왕복
# ─────────────────────────────────────────

class TestUIToConfig:
    def test_settings_save_and_reload(self, tmp_path):
        """설정창에서 저장한 값이 Config에 저장되고 재로드 시 복원되는지"""
        import mallangmollang.infra.config as cfg_module
        from mallangmollang.infra.config import Config
        from mallangmollang.ui.settings import SettingsWindow

        cfg_module._CONFIG_PATH = tmp_path / "config.json"
        Config._instance = None
        config = Config.get_instance()

        win = SettingsWindow(config)
        win._interval_ms.setValue(3000)
        win._context_count.setValue(5)
        win._vision_mode.setChecked(True)
        win._save()

        # 새 Config 인스턴스로 다시 로드
        Config._instance = None
        config2 = Config.get_instance()

        assert config2.get("capture.interval_ms") == 3000
        assert config2.get("translation.context_count") == 5
        assert config2.get("translation.vision_mode") is True

        cfg_module._CONFIG_PATH = tmp_path / "config.json"
        Config._instance = None

    def test_region_selector_signal_to_config(self, tmp_path):
        """RegionSelector의 region_selected 시그널이 App에서 Config로 저장되는지"""
        from mallangmollang.main import App

        import mallangmollang.infra.config as cfg_module
        from mallangmollang.infra.config import Config
        cfg_module._CONFIG_PATH = tmp_path / "config.json"
        Config._instance = None

        a = App(app)
        a._start_translation = MagicMock()  # 파이프라인 시작 방지

        # 시그널 직접 emit 시뮬레이션
        a._on_region_selected((10, 20, 640, 480))

        assert a.config.get("capture.region") == [10, 20, 640, 480]

        cfg_module._CONFIG_PATH = tmp_path / "config.json"
        Config._instance = None


# ─────────────────────────────────────────
# 9. App 전체 조립 확인
# ─────────────────────────────────────────

class TestAppAssembly:
    def test_app_components_connected(self, tmp_path):
        """App 생성 시 모든 컴포넌트가 올바르게 연결되는지"""
        from mallangmollang.main import App
        from mallangmollang.display.overlay import OverlayWindow
        from mallangmollang.ui.tray import TrayIcon
        from mallangmollang.ui.region_selector import RegionSelector

        import mallangmollang.infra.config as cfg_module
        from mallangmollang.infra.config import Config
        cfg_module._CONFIG_PATH = tmp_path / "config.json"
        Config._instance = None

        a = App(app)

        assert isinstance(a.overlay, OverlayWindow)
        assert isinstance(a.tray, TrayIcon)
        assert isinstance(a.region_selector, RegionSelector)
        assert a.config is not None
        assert a._bridge is not None

        cfg_module._CONFIG_PATH = tmp_path / "config.json"
        Config._instance = None

    def test_bridge_signal_updates_overlay(self, tmp_path):
        """_Bridge 시그널이 오버레이를 메인 스레드에서 업데이트하는지"""
        from mallangmollang.main import App

        import mallangmollang.infra.config as cfg_module
        from mallangmollang.infra.config import Config
        cfg_module._CONFIG_PATH = tmp_path / "config.json"
        Config._instance = None

        a = App(app)

        # 시그널 직접 발생
        a._bridge.translation_ready.emit("브리지 테스트 번역", None)

        assert a.overlay._label.text() == "브리지 테스트 번역"
        a.overlay.hide()

        cfg_module._CONFIG_PATH = tmp_path / "config.json"
        Config._instance = None

    def test_settings_saved_updates_overlay_preset(self, tmp_path):
        """설정 저장 후 오버레이 프리셋이 즉시 교체되는지"""
        from mallangmollang.main import App

        import mallangmollang.infra.config as cfg_module
        from mallangmollang.infra.config import Config
        cfg_module._CONFIG_PATH = tmp_path / "config.json"
        Config._instance = None

        a = App(app)
        a.config.set("display.active_preset", "밝은 배경용")
        a._on_settings_saved()

        assert a.overlay.preset.name == "밝은 배경용"

        cfg_module._CONFIG_PATH = tmp_path / "config.json"
        Config._instance = None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
