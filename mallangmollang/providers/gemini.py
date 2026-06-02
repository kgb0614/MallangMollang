"""
Google Gemini API 프로바이더
httpx를 사용한 비동기 REST 방식으로 구현합니다.
"""

import base64
import io
import json
from typing import Any

import httpx
from PIL import Image

from .base import BaseProvider, TranslateParams, TranslationResult


# Gemini REST API 기본 URL
_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Vision을 지원하는 모델 목록
_VISION_MODELS = {
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-1.0-pro-vision",
}


class GeminiProvider(BaseProvider):
    """Google Gemini API 프로바이더 구현체"""

    def __init__(self, api_key: str = "", model: str = "gemini-2.0-flash"):
        super().__init__(api_key=api_key, model=model)

    @property
    def name(self) -> str:
        return "gemini"

    def supports_vision(self) -> bool:
        """현재 선택된 모델이 Vision을 지원하는지 확인합니다."""
        return self.model in _VISION_MODELS

    async def translate(
        self,
        prompt: str,
        params: TranslateParams | None = None,
    ) -> TranslationResult:
        """텍스트 프롬프트로 번역을 요청합니다."""
        if params is None:
            params = TranslateParams()

        payload = _build_text_payload(prompt, params)
        response_text = await self._request(payload)
        return TranslationResult(
            translated=response_text,
            provider=self.name,
        )

    async def translate_vision(
        self,
        prompt: str,
        image: Image.Image,
        params: TranslateParams | None = None,
    ) -> TranslationResult:
        """이미지와 텍스트 프롬프트로 Vision 번역을 요청합니다."""
        if not self.supports_vision():
            raise ValueError(f"모델 '{self.model}'은 Vision API를 지원하지 않습니다.")

        if params is None:
            params = TranslateParams()

        image_b64 = _image_to_base64(image)
        payload = _build_vision_payload(prompt, image_b64, params)
        response_text = await self._request(payload)
        return TranslationResult(
            translated=response_text,
            provider=self.name,
        )

    async def test_connection(self) -> bool:
        """API 키가 유효한지 간단한 요청으로 확인합니다."""
        try:
            payload = _build_text_payload("안녕", TranslateParams(max_tokens=10))
            await self._request(payload)
            return True
        except Exception:
            return False

    async def _request(self, payload: dict[str, Any]) -> str:
        """
        Gemini generateContent API를 호출하고 텍스트 응답을 반환합니다.

        Raises:
            httpx.HTTPStatusError: API 오류 응답
            ValueError: 응답 파싱 실패
        """
        url = f"{_BASE_URL}/models/{self.model}:generateContent?key={self.api_key}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

        data = response.json()

        # 응답 구조: candidates[0].content.parts[0].text
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError) as e:
            raise ValueError(f"Gemini 응답 파싱 실패: {e}\n응답: {data}") from e


def _build_text_payload(prompt: str, params: TranslateParams) -> dict[str, Any]:
    """텍스트 전용 요청 페이로드를 구성합니다."""
    contents: list[dict] = [{"role": "user", "parts": [{"text": prompt}]}]

    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "temperature": params.temperature,
            "maxOutputTokens": params.max_tokens,
        },
    }

    # 시스템 지시사항이 있으면 추가
    if params.system_hint:
        payload["systemInstruction"] = {"parts": [{"text": params.system_hint}]}

    return payload


def _build_vision_payload(
    prompt: str,
    image_b64: str,
    params: TranslateParams,
) -> dict[str, Any]:
    """이미지가 포함된 Vision 요청 페이로드를 구성합니다."""
    parts: list[dict] = [
        {
            "inlineData": {
                "mimeType": "image/png",
                "data": image_b64,
            }
        },
        {"text": prompt},
    ]

    contents = [{"role": "user", "parts": parts}]

    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "temperature": params.temperature,
            "maxOutputTokens": params.max_tokens,
        },
    }

    if params.system_hint:
        payload["systemInstruction"] = {"parts": [{"text": params.system_hint}]}

    return payload


def _image_to_base64(image: Image.Image) -> str:
    """PIL Image를 PNG base64 문자열로 변환합니다."""
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")
