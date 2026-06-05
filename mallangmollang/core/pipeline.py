"""
파이프라인 오케스트레이터 모듈
캡처 → 감지 → OCR → 캐시 → 번역 → 표시 흐름을 조립합니다.
"""

import asyncio
from dataclasses import dataclass
from typing import Callable

from PIL import Image

from mallangmollang.core.capture import ScreenCapture, CaptureResult
from mallangmollang.core.detector import ChangeDetector
from mallangmollang.core.cache import TranslationCache
from mallangmollang.core.ocr import OcrEngine, OcrResult
from mallangmollang.core.translator import Translator
from mallangmollang.infra.config import Config
from mallangmollang.providers.base import TranslationResult


@dataclass
class PipelineResult:
    """한 사이클의 파이프라인 실행 결과"""
    capture: CaptureResult                     # 캡처 결과
    ocr: OcrResult | None                      # OCR 결과 (Vision 모드에서는 None)
    translation: TranslationResult | None      # 번역 결과 (스킵 시 None)
    skipped: bool = False                      # 변경 감지에서 스킵되었는지
    cached: bool = False                       # 캐시 히트인지


# 파이프라인 이벤트 콜백 타입
OnResultCallback = Callable[[PipelineResult], None]


class Pipeline:
    """
    번역 파이프라인 오케스트레이터.

    컴포넌트를 조립하고, 한 사이클 또는 반복 루프를 실행합니다.
    Detector와 Cache는 Unit 4에서 추가됩니다.

    사용 예시:
        pipeline = Pipeline.from_config(config)
        result = await pipeline.run_once()
        print(result.translation.translated)
    """

    def __init__(
        self,
        capture: ScreenCapture,
        ocr: OcrEngine,
        translator: Translator,
        config: Config,
        detector: ChangeDetector | None = None,
        cache: TranslationCache | None = None,
    ):
        self.capture = capture
        self.ocr = ocr
        self.translator = translator
        self.config = config
        self.detector = detector
        self.cache = cache

        self._running = False
        self._on_result: OnResultCallback | None = None

    @classmethod
    def from_config(cls, config: Config) -> "Pipeline":
        """Config 설정으로 파이프라인을 구성합니다."""
        from mallangmollang.providers import create_provider

        provider = create_provider(config)
        translator = Translator(
            provider=provider,
            source_lang=config.get("language.source", "auto"),
            target_lang=config.get("language.target", "ko"),
            context_count=config.get("translation.context_count", 3),
        )

        return cls(
            capture=ScreenCapture(),
            ocr=OcrEngine(),
            translator=translator,
            config=config,
            detector=ChangeDetector(
                threshold=config.get("detector.hash_threshold", 5)
            ),
            cache=TranslationCache(
                max_size=config.get("cache.max_size", 100)
            ),
        )

    def on_result(self, callback: OnResultCallback):
        """번역 결과를 받을 콜백을 등록합니다 (Display 연결용)."""
        self._on_result = callback

    async def run_once(self, region: tuple[int, int, int, int] | None = None) -> PipelineResult:
        """
        한 번의 캡처-번역 사이클을 실행합니다.

        Args:
            region: 캡처 영역 (None이면 Config에서 가져옴)

        Returns:
            PipelineResult
        """
        # 1. 캡처
        if region is None:
            region = tuple(self.config.get("capture.region", [0, 0, 800, 600]))

        capture_result = self.capture.capture_region(region)

        # 2. 변경 감지 — 변경 없으면 이후 파이프라인 전체 스킵 (PRD F2-1)
        if self.detector:
            det = self.detector.detect(capture_result)
            if not det.changed:
                return PipelineResult(
                    capture=capture_result,
                    ocr=None,
                    translation=None,
                    skipped=True,
                )

        # 3. 번역 경로 분기
        vision_mode = self.config.get("translation.vision_mode", False)

        if vision_mode:
            # 경로 B: Vision — OCR 건너뛰고 이미지 직접 전달 (PRD F5-5)
            translation = await self.translator.translate_vision(capture_result.image)
            pipeline_result = PipelineResult(
                capture=capture_result,
                ocr=None,
                translation=translation,
            )
        else:
            # 경로 A: OCR + LLM
            ocr_lang = self.config.get("language.ocr_lang", "eng")
            ocr_result = self.ocr.extract_text(capture_result.image, lang=ocr_lang)

            # OCR 텍스트가 비어있으면 번역 스킵
            if not ocr_result.text.strip():
                return PipelineResult(
                    capture=capture_result,
                    ocr=ocr_result,
                    translation=None,
                    skipped=True,
                )

            # 4. 캐시 확인 — 동일 텍스트면 API 호출 없이 즉시 반환 (PRD F4-1)
            if self.cache:
                cache_result = self.cache.lookup(ocr_result.text)
                if cache_result.hit:
                    from mallangmollang.providers.base import TranslationResult as TR
                    cached_translation = TR(translated=cache_result.translated)
                    pipeline_result = PipelineResult(
                        capture=capture_result,
                        ocr=ocr_result,
                        translation=cached_translation,
                        cached=True,
                    )
                    if self._on_result:
                        self._on_result(pipeline_result)
                    return pipeline_result

            # 5. LLM 번역
            translation = await self.translator.translate_text(ocr_result.text)

            # 번역 결과를 캐시에 저장 (PRD F4-1)
            if self.cache:
                self.cache.store(ocr_result.text, translation.translated)

            pipeline_result = PipelineResult(
                capture=capture_result,
                ocr=ocr_result,
                translation=translation,
            )

        # 6. 결과 콜백 (Display 연결용)
        if self._on_result:
            self._on_result(pipeline_result)

        return pipeline_result

    async def run_loop(
        self,
        region: tuple[int, int, int, int] | None = None,
        interval_ms: int | None = None,
    ):
        """
        주기적으로 캡처-번역을 반복합니다.

        Args:
            region: 캡처 영역
            interval_ms: 캡처 주기 (None이면 Config에서 가져옴)
        """
        if interval_ms is None:
            interval_ms = self.config.get("capture.interval_ms", 1500)

        self._running = True

        while self._running:
            try:
                await self.run_once(region)
            except Exception as e:
                print(f"[Pipeline] 사이클 에러: {e}")
            await asyncio.sleep(interval_ms / 1000.0)

    def stop(self):
        """반복 루프를 중지합니다."""
        self._running = False

    async def close(self):
        """모든 리소스를 정리합니다."""
        self.stop()
        self.capture.close()
        await self.translator.provider.close()
