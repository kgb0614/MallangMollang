"""
파이프라인 오케스트레이터 모듈
캡처 → 감지 → OCR → 캐시 → 번역 → 표시 흐름을 조립합니다.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from PIL import Image

from mallangmollang.core.capture import ScreenCapture, CaptureResult
from mallangmollang.core.detector import ChangeDetector
from mallangmollang.core.cache import TranslationCache
from mallangmollang.core.ocr import OcrEngine, OcrResult, LineBox
from mallangmollang.core.translator import Translator
from mallangmollang.infra.config import Config
from mallangmollang.providers.base import TranslationResult

# 번역 로그 파일 경로 (프로젝트 루트/translation_log.txt)
_LOG_PATH = Path(__file__).parent.parent.parent / "translation_log.txt"


@dataclass
class LineTranslation:
    """줄 단위 번역 결과 — 오버레이 덮어쓰기에 사용"""
    line_box: LineBox        # OCR에서 추출한 줄 위치/크기
    translated: str          # 해당 줄의 번역 텍스트


@dataclass
class ParagraphTranslation:
    """문단 단위 번역 결과 — 오버레이에 자연스러운 텍스트 흐름으로 표시"""
    translated: str          # 문단 전체의 번역 텍스트
    x: int                   # 문단 시작 x (줄들의 최소 x)
    y: int                   # 문단 시작 y (첫 줄의 y)
    width: int               # 문단 너비 (줄들의 최대 너비)
    height: int              # 원문 문단의 총 높이
    font_pt: int             # 대표 폰트 크기 (줄들의 중앙값)


def _group_lines_into_paragraphs(line_boxes: list[LineBox]) -> list[list[LineBox]]:
    """수직 간격 기준으로 인접한 줄들을 문단으로 그룹핑합니다."""
    if not line_boxes:
        return []

    sorted_lines = sorted(line_boxes, key=lambda lb: (lb.y, lb.x))
    groups: list[list[LineBox]] = [[sorted_lines[0]]]

    for line in sorted_lines[1:]:
        prev = groups[-1][-1]
        gap = line.y - (prev.y + prev.height)
        # 간격이 이전 줄 높이의 0.8배 이하이면 같은 문단
        threshold = prev.height * 0.8
        if gap <= threshold:
            groups[-1].append(line)
        else:
            groups.append([line])

    return groups


def _build_paragraph_translations(
    groups: list[list[LineBox]],
    translated_lines: list[str],
) -> list[ParagraphTranslation]:
    """문단 그룹과 줄 번역을 합쳐 ParagraphTranslation 리스트를 생성합니다."""
    result: list[ParagraphTranslation] = []
    line_idx = 0
    for group in groups:
        parts = []
        for _ in group:
            if line_idx < len(translated_lines):
                t = translated_lines[line_idx].strip()
                if t:
                    parts.append(t)
            line_idx += 1

        para_text = " ".join(parts)
        if not para_text.strip():
            continue

        min_x = min(lb.x for lb in group)
        min_y = group[0].y
        max_right = max(lb.x + lb.width for lb in group)
        last_bottom = group[-1].y + group[-1].height
        font_pts = sorted(lb.font_pt for lb in group)
        median_font = font_pts[len(font_pts) // 2]

        result.append(ParagraphTranslation(
            translated=para_text,
            x=min_x,
            y=min_y,
            width=max_right - min_x,
            height=last_bottom - min_y,
            font_pt=median_font,
        ))
    return result


@dataclass
class PipelineResult:
    """한 사이클의 파이프라인 실행 결과"""
    capture: CaptureResult                     # 캡처 결과
    ocr: OcrResult | None                      # OCR 결과 (Vision 모드에서는 None)
    translation: TranslationResult | None      # 번역 결과 (스킵 시 None)
    line_translations: list[LineTranslation] | None = None  # 줄 단위 번역 결과
    paragraph_translations: list[ParagraphTranslation] | None = None  # 문단 단위 번역 결과
    skipped: bool = False                      # 변경 감지에서 스킵되었는지
    cached: bool = False                       # 캐시 히트인지
    region_id: int = 0                         # 다중 영역용 영역 ID


# 파이프라인 이벤트 콜백 타입
OnResultCallback = Callable[[PipelineResult], None]
OnStatusCallback = Callable[[str], None]    # "idle" | "translating" | "error"
OnErrorCallback = Callable[[str], None]     # 에러 상세 메시지


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
        self._on_status: OnStatusCallback | None = None
        self._on_error: OnErrorCallback | None = None
        self._last_debug_info: str = ""

    @property
    def last_debug_info(self) -> str:
        """마지막 번역 사이클의 진단 정보를 반환합니다."""
        return self._last_debug_info

    @classmethod
    def from_config(
        cls,
        config: Config,
        cache: TranslationCache | None = None,
    ) -> "Pipeline":
        """Config 설정으로 파이프라인을 구성합니다.

        Args:
            config: 설정 객체
            cache: 외부에서 주입할 캐시. None이면 새로 생성.
        """
        from mallangmollang.providers import create_provider

        provider = create_provider(config)
        translator = Translator(
            provider=provider,
            source_lang=config.get("language.source", "auto"),
            target_lang=config.get("language.target", "ko"),
            context_count=config.get("translation.context_count", 3),
        )

        if cache is None:
            cache = TranslationCache(
                max_size=config.get("cache.max_size", 100)
            )

        return cls(
            capture=ScreenCapture(),
            ocr=OcrEngine(),
            translator=translator,
            config=config,
            detector=ChangeDetector(
                threshold=config.get("detector.hash_threshold", 5)
            ),
            cache=cache,
        )

    def on_result(self, callback: OnResultCallback):
        """번역 결과를 받을 콜백을 등록합니다 (Display 연결용)."""
        self._on_result = callback

    def on_status(self, callback: OnStatusCallback):
        """파이프라인 상태 변화를 받을 콜백을 등록합니다 (AreaIndicator 연결용)."""
        self._on_status = callback

    def on_error(self, callback: OnErrorCallback):
        """에러 상세 메시지를 받을 콜백을 등록합니다."""
        self._on_error = callback

    async def run_once(
        self,
        region: tuple[int, int, int, int] | None = None,
        region_id: int = 0,
        exclude_zones: list[list[int]] | None = None,
    ) -> PipelineResult:
        """
        한 번의 캡처-번역 사이클을 실행합니다.

        Args:
            region: 캡처 영역 (None이면 Config에서 가져옴)
            region_id: 다중 영역용 영역 ID
            exclude_zones: OCR 제외 영역 [[rx, ry, rw, rh], ...]

        Returns:
            PipelineResult
        """
        # 1. 캡처
        if region is None:
            region = tuple(self.config.get("capture.region", [0, 0, 800, 600]))

        target_mode = self.config.get("capture.target_mode", "screen")
        if target_mode == "window":
            title = self.config.get("capture.window_title", "")
            capture_result = self.capture.capture_window(title, region)
            if capture_result is None:
                return PipelineResult(
                    capture=self.capture.capture_region(region),
                    ocr=None,
                    translation=None,
                    skipped=True,
                    region_id=region_id,
                )
        else:
            capture_result = self.capture.capture_region(region)

        # 제외 영역 마스킹
        if exclude_zones:
            from mallangmollang.core.capture import ScreenCapture
            capture_result.image = ScreenCapture.mask_exclude_zones(
                capture_result.image, exclude_zones,
            )

        # 2. 변경 감지 — 변경 없으면 이후 파이프라인 전체 스킵 (PRD F2-1)
        if self.detector:
            if region_id > 0:
                changed = self.detector.has_changed(capture_result.image, region_id)
            else:
                det = self.detector.detect(capture_result)
                changed = det.changed
            if not changed:
                return PipelineResult(
                    capture=capture_result,
                    ocr=None,
                    translation=None,
                    skipped=True,
                    region_id=region_id,
                )

        # 3. 변경 감지 통과 — 실제 처리 시작
        if self._on_status:
            self._on_status("translating")

        vision_mode = self.config.get("translation.vision_mode", False)

        if vision_mode:
            # 경로 B: Vision — OCR 건너뛰고 이미지 직접 전달 (PRD F5-5)
            translation = await self.translator.translate_vision(capture_result.image)
            pipeline_result = PipelineResult(
                capture=capture_result,
                ocr=None,
                translation=translation,
                region_id=region_id,
            )
        else:
            # 경로 A: OCR + LLM (줄 단위)
            ocr_lang = self.config.get("language.ocr_lang", "auto")
            line_boxes = self.ocr.extract_lines(capture_result.image, lang=ocr_lang)

            # OCR 신뢰도 필터링 — 노이즈(배경 패턴, 아이콘 등) 제거
            before = len(line_boxes)
            line_boxes = [lb for lb in line_boxes if lb.confidence >= 30.0]
            if before != len(line_boxes):
                print(f"[Pipeline] OCR 신뢰도 필터: {before}줄 → {len(line_boxes)}줄 (conf<30 제외)")

            if not line_boxes:
                return PipelineResult(
                    capture=capture_result,
                    ocr=None,
                    translation=None,
                    skipped=True,
                    region_id=region_id,
                )

            # 진단: 콘솔에 간략 출력
            print(f"[Pipeline] OCR {len(line_boxes)}줄 인식 → 번역 시작")

            # 줄 텍스트 합쳐서 캐시 키로 사용
            combined_text = "\n".join(lb.text for lb in line_boxes)

            # 4. 캐시 확인
            if self.cache:
                cache_result = self.cache.lookup(combined_text)
                if cache_result.hit:
                    from mallangmollang.providers.base import TranslationResult as TR
                    cached_lines = cache_result.translated.split("\n")
                    while len(cached_lines) < len(line_boxes):
                        cached_lines.append(cached_lines[-1] if cached_lines else "")
                    line_trans = [
                        LineTranslation(line_box=lb, translated=t)
                        for lb, t in zip(line_boxes, cached_lines)
                    ]
                    # 캐시에서도 문단 그룹핑 적용
                    groups = _group_lines_into_paragraphs(line_boxes)
                    para_trans = _build_paragraph_translations(groups, cached_lines)
                    cached_translation = TR(translated=cache_result.translated)
                    pipeline_result = PipelineResult(
                        capture=capture_result,
                        ocr=None,
                        translation=cached_translation,
                        line_translations=line_trans,
                        paragraph_translations=para_trans,
                        cached=True,
                        region_id=region_id,
                    )
                    if self._on_result:
                        self._on_result(pipeline_result)
                    return pipeline_result

            # 5. LLM 줄 단위 번역
            line_texts = [lb.text for lb in line_boxes]
            translated_lines = await self.translator.translate_lines(line_texts)

            # 진단 정보 조립 (전체 텍스트, 잘림 없음)
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            parts = [f"{'='*60}", f"[{ts}]"]
            parts.append(f"\n▶ OCR 인식 ({len(line_boxes)}줄)")
            for i, lb in enumerate(line_boxes):
                parts.append(f"  [{i+1}] pos=({lb.x},{lb.y}) size={lb.width}x{lb.height} font={lb.font_pt}pt conf={lb.confidence:.0f}")
                parts.append(f"      {lb.text}")
            parts.append(f"\n▶ 번역 결과 ({len(translated_lines)}줄)")
            for i, t in enumerate(translated_lines):
                parts.append(f"  [{i+1}] {t}")
            entry = "\n".join(parts) + "\n"

            # 메모리 저장 (클립보드 복사용)
            self._last_debug_info = entry

            # 파일에 추가 저장
            try:
                with open(_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(entry)
                print(f"[Pipeline] 번역 완료 → {_LOG_PATH.name} 저장됨")
            except Exception as e:
                print(f"[Pipeline] 로그 저장 실패: {e}")

            # 문단 그룹핑 — 인접한 줄을 묶어 자연스러운 텍스트 흐름 생성
            groups = _group_lines_into_paragraphs(line_boxes)
            para_translations = _build_paragraph_translations(groups, translated_lines)
            print(f"[Pipeline] {len(line_boxes)}줄 → {len(para_translations)}문단 그룹핑")

            combined_translated = "\n".join(translated_lines)
            if self.cache:
                self.cache.store(combined_text, combined_translated)

            # line_translations도 유지 (패널 모드 등에서 사용)
            line_trans = [
                LineTranslation(line_box=lb, translated=t)
                for lb, t in zip(line_boxes, translated_lines)
            ]
            pipeline_result = PipelineResult(
                capture=capture_result,
                ocr=None,
                translation=TranslationResult(translated=combined_translated),
                line_translations=line_trans,
                paragraph_translations=para_translations,
                region_id=region_id,
            )

        # 6. 결과 콜백 (Display 연결용)
        if self._on_result:
            self._on_result(pipeline_result)

        return pipeline_result

    async def run_loop(
        self,
        region: tuple[int, int, int, int] | None = None,
        regions: list[dict] | None = None,
        interval_ms: int | None = None,
    ):
        """
        주기적으로 캡처-번역을 반복합니다.

        Args:
            region: 단일 영역 (하위호환)
            regions: 다중 영역 목록 [{"id": ..., "rect": [...], "enabled": True}, ...]
            interval_ms: 캡처 주기 (None이면 Config에서 가져옴)
        """
        if interval_ms is None:
            interval_ms = self.config.get("capture.interval_ms", 1500)

        self._running = True

        while self._running:
            try:
                if regions:
                    for r in regions:
                        if not self._running:
                            break
                        if not r.get("enabled", True):
                            continue
                        await self.run_once(
                            region=tuple(r["rect"]),
                            region_id=r["id"],
                            exclude_zones=r.get("exclude_zones"),
                        )
                else:
                    await self.run_once(region)
                if self._on_status:
                    self._on_status("idle")
            except Exception as e:
                print(f"[Pipeline] 사이클 에러: {e}")
                if self._on_error:
                    self._on_error(str(e))
                if self._on_status:
                    self._on_status("error")
            await asyncio.sleep(interval_ms / 1000.0)

    def stop(self):
        """반복 루프를 중지합니다."""
        self._running = False

    async def close(self):
        """모든 리소스를 정리합니다."""
        self.stop()
        self.capture.close()
        await self.translator.provider.close()
