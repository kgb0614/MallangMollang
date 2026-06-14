"""
사용자 번역 사전 모듈
원문→번역 쌍을 관리합니다. LLM 호출 전 완전 일치 시 즉시 치환,
부분 일치 시 프롬프트에 강제 용어로 포함합니다.
"""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DictEntry:
    """사전 항목"""
    original: str
    translated: str


class UserDictionary:
    """
    사용자 번역 사전.

    사용 예시:
        udict = UserDictionary()
        udict.load(Path("user_dict.json"))
        udict.add("HP", "체력")

        # 정확히 일치하는 줄은 LLM 없이 바로 치환
        exact = udict.lookup_exact("HP")  # "체력"

        # 부분 일치하는 용어는 프롬프트에 강제 주입
        terms = udict.lookup_partial("HP가 부족합니다")  # [("HP", "체력")]
    """

    def __init__(self):
        self._entries: list[DictEntry] = []
        self._path: Path | None = None

    def load(self, path: Path):
        """JSON 파일에서 사전을 로드합니다."""
        self._path = path
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._entries = [
                DictEntry(original=e["original"], translated=e["translated"])
                for e in data if e.get("original") and e.get("translated")
            ]
            print(f"[UserDict] {len(self._entries)}개 항목 로드됨")
        except Exception as e:
            print(f"[UserDict] 로드 실패: {e}")

    def save(self, path: Path | None = None):
        """사전을 JSON 파일에 저장합니다."""
        save_path = path or self._path
        if save_path is None:
            return
        try:
            data = [
                {"original": e.original, "translated": e.translated}
                for e in self._entries
            ]
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[UserDict] {len(self._entries)}개 항목 저장됨")
        except Exception as e:
            print(f"[UserDict] 저장 실패: {e}")

    def add(self, original: str, translated: str):
        """항목을 추가합니다. 이미 있으면 번역을 갱신합니다."""
        for entry in self._entries:
            if entry.original == original:
                entry.translated = translated
                return
        self._entries.append(DictEntry(original=original, translated=translated))

    def remove(self, original: str):
        """항목을 삭제합니다."""
        self._entries = [e for e in self._entries if e.original != original]

    def get_all(self) -> list[tuple[str, str]]:
        """모든 항목을 (원문, 번역) 튜플 목록으로 반환합니다."""
        return [(e.original, e.translated) for e in self._entries]

    def set_all(self, entries: list[tuple[str, str]]):
        """모든 항목을 한 번에 교체합니다."""
        self._entries = [
            DictEntry(original=orig, translated=trans)
            for orig, trans in entries if orig and trans
        ]

    @property
    def count(self) -> int:
        return len(self._entries)

    def lookup_exact(self, text: str) -> str | None:
        """정확히 일치하는 항목의 번역을 반환합니다."""
        stripped = text.strip()
        for entry in self._entries:
            if entry.original == stripped:
                return entry.translated
        return None

    def lookup_partial(self, text: str) -> list[tuple[str, str]]:
        """텍스트에 포함된 모든 사전 항목을 찾아 반환합니다."""
        matches = []
        for entry in self._entries:
            if entry.original in text:
                matches.append((entry.original, entry.translated))
        return matches

    def apply_to_lines(
        self, lines: list[str],
    ) -> tuple[dict[int, str], dict[str, str]]:
        """
        OCR 줄 목록에 사전을 적용합니다.

        Returns:
            (exact_map, partial_terms)
            - exact_map: {줄 인덱스: 번역} — 완전 일치한 줄 (LLM 스킵)
            - partial_terms: {원문: 번역} — 부분 일치 용어 (프롬프트에 강제 주입)
        """
        exact_map: dict[int, str] = {}
        partial_terms: dict[str, str] = {}

        for i, line in enumerate(lines):
            exact = self.lookup_exact(line)
            if exact is not None:
                exact_map[i] = exact
            else:
                for orig, trans in self.lookup_partial(line):
                    partial_terms[orig] = trans

        return exact_map, partial_terms
