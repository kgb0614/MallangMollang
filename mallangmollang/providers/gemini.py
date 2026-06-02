"""
Google Gemini API 프로바이더
AI Studio (API 키)와 Vertex AI (서비스 계정) 두 엔드포인트를 모두 지원합니다.
"""

import base64
import io
import json
import time
from pathlib import Path
from typing import Any

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from PIL import Image

from .base import BaseProvider, TranslateParams, TranslationResult


# AI Studio REST API 기본 URL
_AI_STUDIO_URL = "https://generativelanguage.googleapis.com/v1beta"

# Vision을 지원하는 모델 목록
_VISION_MODELS = {
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-1.0-pro-vision",
}


class GeminiProvider(BaseProvider):
    """
    Google Gemini API 프로바이더 구현체

    endpoint="ai_studio": API 키로 AI Studio 호출
    endpoint="vertex": 서비스 계정 JSON으로 Vertex AI 호출
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "gemini-2.0-flash",
        endpoint: str = "ai_studio",
        vertex_project_id: str = "",
        vertex_region: str = "us-central1",
        service_account: str = "",
    ):
        super().__init__(api_key=api_key, model=model)
        self.endpoint = endpoint
        self.vertex_project_id = vertex_project_id
        self.vertex_region = vertex_region
        self._client: httpx.AsyncClient | None = None

        # Vertex AI 인증 관련
        self._service_account_info: dict | None = None
        self._access_token: str = ""
        self._token_expires_at: float = 0.0

        if endpoint == "vertex" and service_account:
            self._service_account_info = _load_service_account(service_account)

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
        """API 연결이 유효한지 간단한 요청으로 확인합니다."""
        try:
            payload = _build_text_payload("안녕", TranslateParams(max_tokens=10))
            await self._request(payload)
            return True
        except Exception:
            return False

    async def _get_client(self) -> httpx.AsyncClient:
        """httpx 클라이언트를 재사용합니다 (연결 풀 유지)."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def close(self):
        """HTTP 클라이언트를 닫습니다. 앱 종료 시 호출하세요."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _request(self, payload: dict[str, Any]) -> str:
        """
        엔드포인트에 따라 AI Studio 또는 Vertex AI로 요청합니다.

        Raises:
            httpx.HTTPStatusError: API 오류 응답
            ValueError: 응답 파싱 실패 또는 설정 오류
        """
        client = await self._get_client()

        if self.endpoint == "vertex":
            url, headers = await self._build_vertex_request()
            response = await client.post(url, json=payload, headers=headers)
        else:
            url = f"{_AI_STUDIO_URL}/models/{self.model}:generateContent?key={self.api_key}"
            response = await client.post(url, json=payload)

        response.raise_for_status()
        data = response.json()

        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError) as e:
            raise ValueError(f"Gemini 응답 파싱 실패: {e}\n응답: {data}") from e

    # ── Vertex AI 인증 ──

    async def _build_vertex_request(self) -> tuple[str, dict[str, str]]:
        """Vertex AI용 URL과 인증 헤더를 구성합니다."""
        if not self._service_account_info:
            raise ValueError("Vertex AI를 사용하려면 서비스 계정 JSON이 필요합니다.")
        if not self.vertex_project_id:
            raise ValueError("Vertex AI를 사용하려면 프로젝트 ID가 필요합니다.")

        token = await self._get_access_token()
        url = (
            f"https://{self.vertex_region}-aiplatform.googleapis.com/v1"
            f"/projects/{self.vertex_project_id}"
            f"/locations/{self.vertex_region}"
            f"/publishers/google/models/{self.model}:generateContent"
        )
        headers = {"Authorization": f"Bearer {token}"}
        return url, headers

    async def _get_access_token(self) -> str:
        """OAuth2 액세스 토큰을 가져옵니다 (캐시, 만료 시 자동 갱신)."""
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token

        jwt_token = _create_signed_jwt(self._service_account_info)

        client = await self._get_client()
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": jwt_token,
            },
        )
        response.raise_for_status()
        token_data = response.json()

        self._access_token = token_data["access_token"]
        self._token_expires_at = time.time() + token_data.get("expires_in", 3600)
        return self._access_token


# ── 헬퍼 함수들 ──

def _load_service_account(source: str) -> dict:
    """
    서비스 계정 JSON을 로드합니다.
    source가 파일 경로면 파일을 읽고, JSON 문자열이면 바로 파싱합니다.
    """
    source = source.strip()

    # { 로 시작하면 JSON 내용으로 판단
    if source.startswith("{"):
        try:
            return json.loads(source)
        except json.JSONDecodeError as e:
            raise ValueError(f"서비스 계정 JSON 파싱 실패: {e}") from e

    # 아니면 파일 경로로 판단
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"서비스 계정 파일을 찾을 수 없습니다: {source}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"서비스 계정 파일 파싱 실패: {e}") from e


def _create_signed_jwt(sa_info: dict) -> str:
    """서비스 계정 정보로 서명된 JWT를 생성합니다 (OAuth2 토큰 교환용)."""
    now = int(time.time())

    header = {"alg": "RS256", "typ": "JWT"}
    claims = {
        "iss": sa_info["client_email"],
        "sub": sa_info["client_email"],
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,
        "scope": "https://www.googleapis.com/auth/cloud-platform",
    }

    # base64url 인코딩 (패딩 제거)
    segments = [
        base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"="),
        base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"="),
    ]
    signing_input = b".".join(segments)

    # RS256 서명
    private_key = serialization.load_pem_private_key(
        sa_info["private_key"].encode(),
        password=None,
    )
    signature = private_key.sign(signing_input, asym_padding.PKCS1v15(), hashes.SHA256())
    segments.append(base64.urlsafe_b64encode(signature).rstrip(b"="))

    return b".".join(segments).decode()


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
