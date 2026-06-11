"""
API 키 암호화 모듈
config.json에 저장되는 API 키를 Fernet 대칭 암호화로 보호합니다.

암호화 키는 머신 고유 정보(MAC 주소 + 사용자명)에서 유도되므로
이 PC에서만 복호화가 가능합니다.

암호화된 값은 "ENC:" 접두어로 구분됩니다.
평문 값은 접두어가 없으므로, 기존 config.json의 평문 키는
다음 저장 시 자동으로 암호화됩니다.
"""

import base64
import getpass
import hashlib
import uuid

from cryptography.fernet import Fernet, InvalidToken


_SALT = b"mallangmollang-crypto-v1"
_ENC_PREFIX = "ENC:"

# Config에서 암호화 대상인 설정 경로 목록
SECRET_PATHS = [
    "provider.gemini.api_key",
    "provider.openai.api_key",
    "provider.claude.api_key",
    "provider.gemini.vertex.service_account",
]

# Fernet 인스턴스 캐시 (PBKDF2 반복 계산 방지)
_fernet_cache: Fernet | None = None


def _derive_key() -> bytes:
    """머신 고유 정보(MAC + 사용자명)에서 Fernet 키를 유도합니다."""
    mac = str(uuid.getnode())
    try:
        user = getpass.getuser()
    except Exception:
        user = "default"

    raw = f"{mac}:{user}".encode()
    dk = hashlib.pbkdf2_hmac("sha256", raw, _SALT, iterations=100_000)
    return base64.urlsafe_b64encode(dk)


def _get_fernet() -> Fernet:
    """캐시된 Fernet 인스턴스를 반환합니다."""
    global _fernet_cache
    if _fernet_cache is None:
        _fernet_cache = Fernet(_derive_key())
    return _fernet_cache


def encrypt(plaintext: str) -> str:
    """평문을 암호화합니다. 빈 문자열이나 이미 암호화된 값은 그대로 반환합니다."""
    if not plaintext or plaintext.startswith(_ENC_PREFIX):
        return plaintext
    token = _get_fernet().encrypt(plaintext.encode("utf-8"))
    return _ENC_PREFIX + token.decode("ascii")


def decrypt(ciphertext: str) -> str:
    """암호화된 텍스트를 복호화합니다. ENC: 접두어가 없으면 평문으로 간주합니다."""
    if not ciphertext or not ciphertext.startswith(_ENC_PREFIX):
        return ciphertext
    token = ciphertext[len(_ENC_PREFIX):]
    try:
        return _get_fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        print("[Crypto] 복호화 실패 — 다른 PC에서 암호화된 키이거나 손상됨. API 키를 다시 입력하세요.")
        return ""


def is_encrypted(value: str) -> bool:
    """값이 암호화된 상태인지 확인합니다."""
    return isinstance(value, str) and value.startswith(_ENC_PREFIX)
