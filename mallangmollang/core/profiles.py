"""
번역 프로필 관리 모듈
콘텐츠별 장르/분위기/용어집을 사전 정의하여 번역 품질을 높입니다.

사용 흐름:
    manager = ProfileManager(provider)
    profile = await manager.auto_generate("레지던트 이블 2")
    manager.save(profile)
    hint = manager.build_hint("레지던트 이블 2")
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

from mallangmollang.providers.base import BaseProvider, TranslateParams


_PROFILES_PATH = Path(__file__).parent.parent.parent / "profiles.json"

_GENERATE_SYSTEM = (
    "당신은 번역 프로필 생성 도우미입니다.\n"
    "사용자가 입력한 키워드(콘텐츠 이름, 시리즈명 등)를 바탕으로\n"
    "번역에 도움이 되는 배경 정보를 JSON으로 생성하세요.\n\n"
    "반드시 아래 JSON 형식으로만 응답하세요 (다른 설명 없이):\n"
    '{"genre": "장르", "tone": "분위기/어조", '
    '"glossary": {"원문 용어": "번역 용어", ...}, '
    '"extra_instruction": "번역 시 참고할 추가 지시"}'
)

_GENERATE_PROMPT = (
    "다음 콘텐츠에 대한 번역 프로필을 생성해줘: {keyword}\n\n"
    "genre: 해당 콘텐츠의 장르/카테고리\n"
    "tone: 전체적인 분위기, 어조\n"
    "glossary: 주요 고유명사/용어의 한국어 번역 (10개 이내)\n"
    "extra_instruction: 번역할 때 참고해야 할 추가 사항"
)


@dataclass
class TranslationProfile:
    """번역 프로필 데이터"""
    name: str
    genre: str = ""
    tone: str = ""
    glossary: dict[str, str] = field(default_factory=dict)
    extra_instruction: str = ""


class ProfileManager:
    """번역 프로필 저장/불러오기/자동 생성을 관리합니다."""

    def __init__(self, provider: BaseProvider | None = None):
        self._provider = provider
        self._profiles: dict[str, TranslationProfile] = {}
        self._load()

    @property
    def profile_names(self) -> list[str]:
        return list(self._profiles.keys())

    def get(self, name: str) -> TranslationProfile | None:
        return self._profiles.get(name)

    def save(self, profile: TranslationProfile):
        """프로필을 메모리에 추가하고 파일에 저장합니다."""
        self._profiles[profile.name] = profile
        self._persist()

    def delete(self, name: str):
        """프로필을 삭제합니다."""
        if name in self._profiles:
            del self._profiles[name]
            self._persist()

    def build_hint(self, name: str) -> str:
        """프로필을 시스템 프롬프트에 추가할 텍스트 블록으로 변환합니다.

        프로필이 없거나 이름이 비어있으면 빈 문자열을 반환합니다.
        """
        if not name:
            return ""
        profile = self._profiles.get(name)
        if not profile:
            return ""

        parts = ["\n【번역 맥락 정보】"]
        parts.append(f"- 콘텐츠: {profile.name}")
        if profile.genre:
            parts.append(f"- 장르: {profile.genre}")
        if profile.tone:
            parts.append(f"- 분위기: {profile.tone}")
        if profile.glossary:
            terms = ", ".join(f"{k}→{v}" for k, v in profile.glossary.items())
            parts.append(f"- 용어집: {terms}")
        if profile.extra_instruction:
            parts.append(f"- 추가 지시: {profile.extra_instruction}")

        return "\n".join(parts)

    async def auto_generate(self, keyword: str) -> TranslationProfile:
        """LLM에 키워드를 보내서 프로필을 자동 생성합니다.

        번역 흐름과 완전히 분리된 별도 API 호출입니다.
        파싱 실패 시 이름만 채워진 빈 프로필을 반환합니다.
        """
        if not self._provider:
            return TranslationProfile(name=keyword)

        prompt = _GENERATE_PROMPT.format(keyword=keyword)
        params = TranslateParams(
            max_tokens=2048,
            temperature=0.7,
            system_hint=_GENERATE_SYSTEM,
        )

        try:
            result = await self._provider.translate(prompt, params)
            return self._parse_generated(keyword, result.translated)
        except Exception as e:
            print(f"[Profiles] 자동 생성 실패: {e}")
            return TranslationProfile(name=keyword)

    def _parse_generated(self, keyword: str, response: str) -> TranslationProfile:
        """LLM 응답에서 JSON을 파싱하여 프로필을 생성합니다."""
        import re
        # 코드 블록 안의 JSON 추출
        cleaned = re.sub(r"```json?\s*", "", response)
        cleaned = re.sub(r"```", "", cleaned).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # JSON 부분만 추출 시도
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    print(f"[Profiles] JSON 파싱 실패, 빈 프로필 반환")
                    return TranslationProfile(name=keyword)
            else:
                print(f"[Profiles] JSON 찾을 수 없음, 빈 프로필 반환")
                return TranslationProfile(name=keyword)

        glossary = data.get("glossary", {})
        if not isinstance(glossary, dict):
            glossary = {}

        return TranslationProfile(
            name=keyword,
            genre=str(data.get("genre", "")),
            tone=str(data.get("tone", "")),
            glossary={str(k): str(v) for k, v in glossary.items()},
            extra_instruction=str(data.get("extra_instruction", "")),
        )

    def _load(self):
        """profiles.json에서 프로필을 불러옵니다."""
        if not _PROFILES_PATH.exists():
            return
        try:
            with open(_PROFILES_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                p = TranslationProfile(
                    name=item["name"],
                    genre=item.get("genre", ""),
                    tone=item.get("tone", ""),
                    glossary=item.get("glossary", {}),
                    extra_instruction=item.get("extra_instruction", ""),
                )
                self._profiles[p.name] = p
        except Exception as e:
            print(f"[Profiles] 프로필 로드 실패: {e}")

    def _persist(self):
        """현재 프로필을 profiles.json에 저장합니다."""
        data = [asdict(p) for p in self._profiles.values()]
        try:
            with open(_PROFILES_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Profiles] 프로필 저장 실패: {e}")
