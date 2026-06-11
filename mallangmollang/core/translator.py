"""
번역 엔진 모듈
OCR 교정 프롬프트 조립 + 문맥 기억 + LLM 호출을 담당합니다.
이 모듈이 MORT 대비 핵심 차별점(OCR 교정, 문맥 기억)을 구현합니다.
"""

import re
from collections import deque
from dataclasses import dataclass

from PIL import Image

from mallangmollang.providers.base import BaseProvider, TranslateParams, TranslationResult


# 언어 코드 → 자연어 이름 매핑
_LANG_NAMES: dict[str, str] = {
    "ko": "한국어",
    "en": "English",
    "ja": "日本語",
    "zh": "中文",
    "zh-CN": "简体中文",
    "zh-TW": "繁體中文",
    "fr": "Français",
    "de": "Deutsch",
    "es": "Español",
    "auto": "자동 감지",
}


@dataclass
class ContextEntry:
    """문맥 기억용 번역 기록"""
    source: str        # 원문 (교정 후)
    translated: str    # 번역된 텍스트


class Translator:
    """
    번역 엔진.
    OCR 결과를 교정하고, 문맥을 유지하며, LLM을 통해 자연스러운 번역을 생성합니다.

    사용 예시:
        translator = Translator(provider, target_lang="ko")
        result = await translator.translate_text("Helo Wrold")
        print(result.translated)       # "안녕 세상"
        print(result.corrected_source) # "Hello World"
    """

    def __init__(
        self,
        provider: BaseProvider,
        source_lang: str = "auto",
        target_lang: str = "ko",
        context_count: int = 3,
    ):
        self.provider = provider
        self.source_lang = source_lang
        self.target_lang = target_lang
        self._context: deque[ContextEntry] = deque(maxlen=context_count)

    async def translate_text(
        self,
        ocr_text: str,
        params: TranslateParams | None = None,
    ) -> TranslationResult:
        """
        OCR 텍스트를 교정하고 번역합니다 (경로 A: OCR + LLM).

        Args:
            ocr_text: OCR로 추출된 원문 텍스트
            params: 번역 파라미터 (None이면 기본값)

        Returns:
            TranslationResult (번역 텍스트 + 교정된 원문)
        """
        if params is None:
            params = TranslateParams()

        system_hint = self._build_system_hint(params.system_hint)
        prompt = self._build_text_prompt(ocr_text)

        result = await self.provider.translate(
            prompt,
            TranslateParams(
                temperature=params.temperature,
                max_tokens=params.max_tokens,
                system_hint=system_hint,
            ),
        )

        corrected, translated = _parse_response(result.translated, ocr_text)
        self._context.append(ContextEntry(source=corrected or ocr_text, translated=translated))

        return TranslationResult(
            translated=translated,
            corrected_source=corrected,
            tokens_used=result.tokens_used,
            provider=result.provider,
        )

    async def translate_vision(
        self,
        image: Image.Image,
        params: TranslateParams | None = None,
    ) -> TranslationResult:
        """
        이미지를 Vision LLM에 직접 전달하여 번역합니다 (경로 B: Vision).

        Args:
            image: 캡처된 화면 이미지
            params: 번역 파라미터

        Returns:
            TranslationResult
        """
        if params is None:
            params = TranslateParams()

        system_hint = self._build_vision_system_hint(params.system_hint)
        prompt = self._build_vision_prompt()

        result = await self.provider.translate_vision(
            prompt,
            image,
            TranslateParams(
                temperature=params.temperature,
                max_tokens=params.max_tokens,
                system_hint=system_hint,
            ),
        )

        corrected, translated = _parse_response(result.translated)
        self._context.append(ContextEntry(source=corrected, translated=translated))

        return TranslationResult(
            translated=translated,
            corrected_source=corrected,
            tokens_used=result.tokens_used,
            provider=result.provider,
        )

    def clear_context(self):
        """문맥 기억을 초기화합니다."""
        self._context.clear()

    @property
    def context_entries(self) -> list[ContextEntry]:
        """현재 저장된 문맥 기록을 반환합니다."""
        return list(self._context)

    async def translate_lines(
        self,
        lines: list[str],
        params: TranslateParams | None = None,
    ) -> list[str]:
        """OCR 텍스트를 줄 단위로 번역합니다 (오버레이 1:1 매핑용)."""
        if params is None:
            params = TranslateParams()

        system_hint = self._build_line_system_hint(params.system_hint)
        prompt = self._build_line_prompt(lines)

        # 입력 텍스트 길이에 비례해 출력 토큰 여유를 줌
        total_chars = sum(len(l) for l in lines)
        max_tokens = max(params.max_tokens, len(lines) * 80 + 256, total_chars * 3 + 256)

        result = await self.provider.translate(
            prompt,
            TranslateParams(
                temperature=params.temperature,
                max_tokens=max_tokens,
                system_hint=system_hint,
            ),
        )

        translated_lines = self._parse_line_response(result.translated, len(lines))

        if len(set(translated_lines)) == 1 and len(translated_lines) > 1:
            print(f"[Translator] 경고: 모든 줄이 동일한 번역 — 파싱 실패 가능성")

        # 문맥에 원문/번역을 합쳐서 저장
        joined_source = "\n".join(lines)
        joined_translated = "\n".join(translated_lines)
        self._context.append(ContextEntry(source=joined_source, translated=joined_translated))

        return translated_lines

    # ── 프롬프트 조립 ──

    def _build_system_hint(self, extra_hint: str = "") -> str:
        """OCR+LLM 경로용 시스템 프롬프트를 조립합니다."""
        target_name = _LANG_NAMES.get(self.target_lang, self.target_lang)

        hint = (
            "당신은 화면 번역 도우미입니다.\n"
            "아래 텍스트는 OCR(광학 문자 인식)로 추출한 것이라 오타나 오인식이 있을 수 있습니다.\n\n"
            "작업:\n"
            "1. 원문의 OCR 오류를 문맥에 맞게 교정하세요 (예: 'rn'→'m', 'l'→'I', 누락된 글자 복원 등).\n"
            f"2. 교정된 원문을 {target_name}(으)로 자연스럽게 번역하세요.\n\n"
            "반드시 아래 형식으로만 응답하세요 (다른 설명이나 부연 없이):\n"
            "[corrected]: 교정된 원문\n"
            "[translated]: 번역 결과"
        )

        if extra_hint:
            hint += f"\n\n추가 지시: {extra_hint}"

        return hint

    def _build_vision_system_hint(self, extra_hint: str = "") -> str:
        """Vision 경로용 시스템 프롬프트를 조립합니다."""
        target_name = _LANG_NAMES.get(self.target_lang, self.target_lang)

        hint = (
            "당신은 화면 번역 도우미입니다.\n"
            "이미지에 포함된 텍스트를 읽고 번역하세요.\n\n"
            "작업:\n"
            "1. 이미지에서 텍스트를 정확히 읽어내세요.\n"
            f"2. 읽어낸 텍스트를 {target_name}(으)로 자연스럽게 번역하세요.\n\n"
            "반드시 아래 형식으로만 응답하세요 (다른 설명이나 부연 없이):\n"
            "[corrected]: 이미지에서 읽은 원문\n"
            "[translated]: 번역 결과"
        )

        if extra_hint:
            hint += f"\n\n추가 지시: {extra_hint}"

        return hint

    def _build_text_prompt(self, ocr_text: str) -> str:
        """OCR 텍스트 + 문맥을 포함한 사용자 프롬프트를 조립합니다."""
        parts: list[str] = []

        # 이전 문맥이 있으면 포함
        if self._context:
            parts.append("이전 대화 맥락:")
            for entry in self._context:
                parts.append(f"- 원문: {entry.source}")
                parts.append(f"  번역: {entry.translated}")
            parts.append("")

        parts.append(f"현재 텍스트:\n{ocr_text}")

        return "\n".join(parts)

    def _build_vision_prompt(self) -> str:
        """Vision 모드용 사용자 프롬프트를 조립합니다."""
        parts: list[str] = []

        if self._context:
            parts.append("이전 대화 맥락:")
            for entry in self._context:
                parts.append(f"- 원문: {entry.source}")
                parts.append(f"  번역: {entry.translated}")
            parts.append("")

        parts.append("이 이미지에 포함된 텍스트를 번역해 주세요.")

        return "\n".join(parts)

    def _build_line_system_hint(self, extra_hint: str = "") -> str:
        """줄 단위 번역용 시스템 프롬프트를 조립합니다."""
        target_name = _LANG_NAMES.get(self.target_lang, self.target_lang)

        hint = (
            "당신은 화면 번역 도우미입니다.\n"
            "아래 텍스트는 OCR(광학 문자 인식)로 추출한 것이라 오타나 오인식이 있을 수 있습니다.\n\n"
            "작업:\n"
            "1. 각 줄의 OCR 오류를 문맥에 맞게 교정하세요.\n"
            f"2. 교정된 원문을 {target_name}(으)로 자연스럽게 번역하세요.\n"
            "3. 반드시 입력과 동일한 줄 수만큼, 동일한 번호 형식으로만 응답하세요.\n\n"
            "【출력 형식】 — 이 형식 외에는 절대 쓰지 마세요:\n"
            "1| (첫 번째 줄 번역)\n"
            "2| (두 번째 줄 번역)\n"
            "3| (세 번째 줄 번역)\n\n"
            "【예시】\n"
            "입력:\n"
            "1| Hello World\n"
            "2| How are you\n"
            "출력:\n"
            f"1| 안녕하세요\n"
            f"2| 잘 지내시나요\n\n"
            "주의: 설명, 부연, 마크다운 없이 번호|번역 형식만 출력하세요.\n"
            "입력이 N줄이면 출력도 반드시 N줄이어야 합니다."
        )

        if extra_hint:
            hint += f"\n\n추가 지시: {extra_hint}"

        return hint

    def _build_line_prompt(self, lines: list[str]) -> str:
        """줄 번호를 붙인 사용자 프롬프트를 조립합니다."""
        parts: list[str] = []

        # 이전 문맥이 있으면 포함
        if self._context:
            parts.append("이전 대화 맥락:")
            for entry in self._context:
                parts.append(f"- 원문: {entry.source}")
                parts.append(f"  번역: {entry.translated}")
            parts.append("")

        # 각 줄에 번호 부여
        numbered = "\n".join(f"{i + 1}| {line}" for i, line in enumerate(lines))
        parts.append(f"현재 텍스트:\n{numbered}")

        return "\n".join(parts)

    def _parse_line_response(self, response: str, expected_count: int) -> list[str]:
        """LLM 응답에서 번호별 번역 결과를 파싱합니다."""
        cleaned = re.sub(r"```[^\n]*\n?", "", response).strip()

        # 줄이 1개일 때는 전체 응답을 그대로 사용 (정규식으로 자르지 않음)
        # LLM이 긴 번역을 여러 줄로 나눠 반환해도 전부 보존
        if expected_count == 1:
            # "1| 텍스트" 접두사만 제거하고 나머지 전부 반환
            stripped = re.sub(r"^\d+[|.:)]\s*", "", cleaned, count=1).strip()
            return [stripped or cleaned]

        # 여러 줄: 번호 구분자로 각 항목 추출
        # "N| 다음 번호 전까지 전부" 방식으로 다중 줄 번역도 캡처
        for sep in (r"\|", r"\.", r"\)", r":"):
            # 각 번호 항목의 시작 위치를 찾아 슬라이싱
            pattern = rf"^\d+{sep}\s*"
            positions = [(m.start(), m.end()) for m in re.finditer(pattern, cleaned, re.MULTILINE)]
            if len(positions) >= expected_count:
                results = []
                for i, (_, content_start) in enumerate(positions[:expected_count]):
                    end = positions[i + 1][0] if i + 1 < len(positions) else len(cleaned)
                    results.append(cleaned[content_start:end].strip())
                while len(results) < expected_count:
                    results.append("")
                return results

        # 구분자 없는 경우: 비어있지 않은 줄로 분할
        nonempty = [line.strip() for line in cleaned.splitlines() if line.strip()]
        if nonempty:
            while len(nonempty) < expected_count:
                nonempty.append("")
            return nonempty[:expected_count]

        return [cleaned] + [""] * (expected_count - 1)


def _parse_response(response: str, fallback_source: str = "") -> tuple[str, str]:
    """
    LLM 응답에서 교정된 원문과 번역 결과를 추출합니다.

    지원 형식:
        [corrected]: 교정된 원문
        [translated]: 번역 결과

    파싱 실패 시 전체 응답을 번역 결과로 사용합니다.

    Returns:
        (교정된 원문, 번역 결과)
    """
    corrected = ""
    translated = ""

    # [corrected]: ... 패턴 매칭 (대소문자 무관, 이후 줄도 다음 태그 전까지 포함)
    match_c = re.search(r"\[corrected\]\s*:\s*(.+?)(?=\[translated\]|\Z)", response, re.IGNORECASE | re.DOTALL)
    if match_c:
        corrected = match_c.group(1).strip()

    # [translated]: ... 패턴 매칭 (대소문자 무관, 끝까지 전부 포함)
    match_t = re.search(r"\[translated\]\s*:\s*(.+)", response, re.IGNORECASE | re.DOTALL)
    if match_t:
        translated = match_t.group(1).strip()

    # translated가 비어있으면 전체 응답을 번역 결과로 사용
    if not translated:
        translated = response.strip()

    if not corrected:
        corrected = fallback_source

    return corrected, translated
