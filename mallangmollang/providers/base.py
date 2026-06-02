"""
LLM 프로바이더 추상 인터페이스
모든 프로바이더는 이 클래스를 상속받아 구현해야 합니다.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from PIL import Image


@dataclass
class TranslateParams:
    """번역 요청 파라미터"""
    temperature: float = 0.3       # 창의성 수준 (0.0~1.0)
    max_tokens: int = 1024         # 최대 출력 토큰 수
    # 번역 프로필에서 주입되는 추가 시스템 지시사항 (선택)
    system_hint: str = ""


@dataclass
class TranslationResult:
    """번역 결과"""
    translated: str                      # 번역된 텍스트
    corrected_source: str = ""           # LLM이 교정한 원문 (OCR 교정 결과)
    tokens_used: int = 0                 # 사용된 토큰 수 (알 수 없으면 0)
    provider: str = ""                   # 번역에 사용된 프로바이더 이름


class BaseProvider(ABC):
    """
    LLM 프로바이더 추상 기반 클래스.

    새 프로바이더를 추가하려면:
      1. 이 클래스를 상속받습니다.
      2. 아래 추상 메서드를 모두 구현합니다.
      3. providers/__init__.py에 등록합니다.
    """

    def __init__(self, api_key: str = "", model: str = ""):
        self.api_key = api_key
        self.model = model

    @abstractmethod
    async def translate(
        self,
        prompt: str,
        params: TranslateParams | None = None,
    ) -> TranslationResult:
        """
        텍스트 프롬프트를 받아 번역 결과를 반환합니다.

        Args:
            prompt: 완전히 구성된 번역 프롬프트 (Translator가 조립)
            params: 번역 파라미터 (None이면 기본값 사용)

        Returns:
            TranslationResult
        """
        ...

    @abstractmethod
    async def translate_vision(
        self,
        prompt: str,
        image: Image.Image,
        params: TranslateParams | None = None,
    ) -> TranslationResult:
        """
        이미지와 텍스트 프롬프트를 받아 번역 결과를 반환합니다 (Vision API).

        Args:
            prompt: 번역 지시 프롬프트
            image: 번역할 텍스트가 포함된 캡처 이미지
            params: 번역 파라미터

        Returns:
            TranslationResult
        """
        ...

    @abstractmethod
    async def test_connection(self) -> bool:
        """
        API 연결 상태를 확인합니다.

        Returns:
            True: 연결 성공, False: 연결 실패
        """
        ...

    @abstractmethod
    def supports_vision(self) -> bool:
        """
        이 프로바이더가 Vision API를 지원하는지 반환합니다.

        Returns:
            True: Vision 지원, False: 미지원
        """
        ...

    @property
    def name(self) -> str:
        """프로바이더 이름 (클래스명 기반 기본값, 오버라이드 가능)"""
        return self.__class__.__name__.replace("Provider", "").lower()
