"""
번역 캐시 모듈
OCR 텍스트 해시를 키로, 번역 결과를 값으로 저장하는 LRU 캐시입니다.
동일 텍스트가 재등장하면 API 호출 없이 즉시 반환합니다.
디스크에 저장/로드하여 앱 재시작 후에도 캐시를 유지합니다.
"""

import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CacheResult:
    """캐시 조회 결과"""
    hit: bool              # True=캐시 히트, False=미스
    translated: str = ""   # 히트 시 저장된 번역 결과


class TranslationCache:
    """
    텍스트 해시 기반 LRU 번역 캐시.

    OrderedDict를 사용한 LRU 구현으로,
    max_size 초과 시 가장 오래 사용되지 않은 항목을 제거합니다.

    사용 예시:
        cache = TranslationCache(max_size=100)
        result = cache.lookup('Hello World')
        if not result.hit:
            translation = await translator.translate_text('Hello World')
            cache.store('Hello World', translation.translated)
    """

    def __init__(self, max_size: int = 100):
        """
        Args:
            max_size: 캐시 최대 항목 수. 초과 시 LRU 항목 제거.
        """
        self.max_size = max_size
        self._store: OrderedDict[str, str] = OrderedDict()

    def lookup(self, text: str) -> CacheResult:
        """
        텍스트에 대한 번역 캐시를 조회합니다.

        Args:
            text: OCR로 추출된 원문 텍스트

        Returns:
            CacheResult (hit=True면 translated에 번역 결과)
        """
        key = _hash_text(text)

        if key not in self._store:
            return CacheResult(hit=False)

        # 히트: 최근 사용으로 순서 갱신 (LRU)
        self._store.move_to_end(key)
        return CacheResult(hit=True, translated=self._store[key])

    def store(self, text: str, translated: str):
        """
        번역 결과를 캐시에 저장합니다.

        Args:
            text: OCR 원문 텍스트 (키 생성에 사용)
            translated: 저장할 번역 결과
        """
        key = _hash_text(text)

        if key in self._store:
            self._store[key] = translated
            self._store.move_to_end(key)
        else:
            if len(self._store) >= self.max_size:
                # LRU: 가장 오래된 항목 제거
                self._store.popitem(last=False)
            self._store[key] = translated

    def save(self, path: Path) -> None:
        """캐시를 JSON 파일로 저장합니다."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = list(self._store.items())
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            print(f"[Cache] 캐시 저장 완료: {self.size}개 항목 → {path.name}")
        except Exception as e:
            print(f"[Cache] 캐시 저장 실패: {e}")

    def load(self, path: Path) -> None:
        """JSON 파일에서 캐시를 불러옵니다. 파일이 없으면 무시합니다."""
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                print("[Cache] 캐시 파일 형식 오류 — 무시합니다.")
                return
            # max_size 초과 시 뒤쪽(최신) 항목만 로드
            if len(data) > self.max_size:
                data = data[-self.max_size:]
            self._store = OrderedDict(data)
            print(f"[Cache] 캐시 로드 완료: {self.size}개 항목 ← {path.name}")
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[Cache] 캐시 파일 손상 — 빈 캐시로 시작합니다: {e}")

    def clear(self):
        """캐시를 전체 초기화합니다 (PRD F4-3: 수동 초기화)."""
        self._store.clear()

    @property
    def size(self) -> int:
        """현재 캐시에 저장된 항목 수."""
        return len(self._store)


def _hash_text(text: str) -> str:
    """텍스트를 SHA-256 해시로 변환합니다."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
