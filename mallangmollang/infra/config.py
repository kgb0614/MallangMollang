"""
설정 관리 모듈
모든 설정을 config.json에 저장하고 불러옵니다.
모든 모듈은 이 모듈을 통해 설정에 접근해야 합니다.
"""

import copy
import json
from pathlib import Path
from typing import Any

from mallangmollang.infra.crypto import SECRET_PATHS, encrypt, decrypt


# 설정 파일 경로 (mallangmollang 패키지 루트 기준)
_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.json"

# 기본 설정값 정의
DEFAULT_CONFIG: dict[str, Any] = {
    # 프로바이더 설정
    "provider": {
        "active": "gemini",          # 현재 활성화된 LLM 프로바이더
        "gemini": {
            "api_key": "",
            "model": "gemini-3.5-flash",
            "endpoint": "ai_studio",      # "ai_studio" 또는 "vertex"
            "vertex": {
                "project_id": "",
                "region": "global",
                # 서비스 계정 JSON 내용(문자열) 또는 .json 파일 경로
                "service_account": "",
            },
        },
        "openai": {
            "api_key": "",
            "model": "gpt-4o-mini",
        },
        "claude": {
            "api_key": "",
            "model": "claude-haiku-4-5-20251001",
        },
        "ollama": {
            "base_url": "http://localhost:11434",
            "model": "gemma3:latest",
        },
    },

    # 언어 설정
    "language": {
        "source": "auto",   # 번역 원본 언어 (auto = 자동 감지)
        "target": "ko",     # 번역 대상 언어
        "ocr_lang": "auto",  # Tesseract OCR 언어 코드 ("auto" = OSD 자동 감지)
    },

    # 캡처 설정
    "capture": {
        "mode": "region",         # 캡처 모드: "region" | "cursor"
        "interval_ms": 1500,      # 캡처 주기 (밀리초)
        "region": None,           # 하위호환용 단일 영역 (regions[0]과 동기화)
        "regions": [],            # 다중 영역 [{"id": 1, "name": "...", "rect": [...], "enabled": True}, ...]
        "cursor_radius": 200,     # 커서 추적 모드에서 캡처 반경 (픽셀)
        "target_mode": "screen",  # "screen" (화면 좌표) | "window" (윈도우 기준)
        "window_title": "",       # 윈도우 캡처 대상 창 타이틀
    },

    # 번역 설정
    "translation": {
        "run_mode": "realtime",   # "realtime" (자동 반복) | "snapshot" (한 번만)
        "vision_mode": False,     # Vision API 모드 사용 여부
        "context_count": 3,       # 문맥 기억 개수 (이전 N회 번역 포함)
        "active_profile": None,   # 활성 번역 프로필 이름
        "auto_clipboard": False,  # 번역 결과 클립보드 자동 복사
    },

    # 변경 감지 설정
    "detector": {
        "hash_threshold": 5,      # pHash 차이 임계값 (낮을수록 민감)
    },

    # 캐시 설정
    "cache": {
        "max_size": 100,          # LRU 캐시 최대 항목 수
    },

    # 표시 설정
    "display": {
        "mode": "overlay",                # 표시 모드: "overlay" | "panel"
        "active_preset": "dark",          # 활성 스타일 프리셋
        "snapshot_auto_dismiss_ms": 0,    # 스냅샷 자동 정리 (밀리초, 0=비활성)
    },

    # 단축키 설정
    "hotkeys": {
        "toggle_translation": "<ctrl>+<shift>+t",  # 번역 켜기/끄기
        "select_region": "<ctrl>+<shift>+r",        # 영역 선택
    },

    # 앱 설정
    "app": {
        "first_run": True,        # 최초 실행 여부 (온보딩 표시 여부)
        "auto_start": False,      # Windows 시작 시 자동 실행
    },
}


class Config:
    """
    설정을 관리하는 싱글톤 클래스입니다.

    사용 예시:
        config = Config.get_instance()
        api_key = config.get("provider.gemini.api_key")
        config.set("provider.active", "openai")
    """

    _instance: "Config | None" = None

    def __init__(self):
        self._data: dict[str, Any] = {}
        self._load()

    @classmethod
    def get_instance(cls) -> "Config":
        """싱글톤 인스턴스를 반환합니다."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load(self):
        """config.json을 읽어 설정을 불러옵니다. 파일이 없으면 기본값을 사용합니다."""
        if _CONFIG_PATH.exists():
            try:
                with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._data = _deep_merge(DEFAULT_CONFIG, saved)
            except (json.JSONDecodeError, OSError) as e:
                print(f"[Config] 설정 파일 읽기 실패, 기본값 사용: {e}")
                self._data = _deep_merge(DEFAULT_CONFIG, {})
        else:
            self._data = _deep_merge(DEFAULT_CONFIG, {})
            self.save()
            return

        # 기존 단일 region → regions 마이그레이션
        self._migrate_region_to_regions()

        # 디스크에서 읽은 암호화된 API 키를 복호화 (메모리에는 평문 유지)
        self._decrypt_secrets()

    def save(self):
        """현재 설정을 config.json에 저장합니다. API 키는 암호화되어 저장됩니다."""
        try:
            _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = self._encrypt_data_copy()
            with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            print(f"[Config] 설정 파일 저장 실패: {e}")

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        점(.) 구분 경로로 설정값을 읽습니다.

        예시: config.get("provider.gemini.api_key")
        """
        keys = key_path.split(".")
        node = self._data
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node

    def set(self, key_path: str, value: Any):
        """
        점(.) 구분 경로로 설정값을 쓰고 저장합니다.

        예시: config.set("provider.active", "openai")
        """
        keys = key_path.split(".")
        node = self._data
        for k in keys[:-1]:
            if k not in node or not isinstance(node[k], dict):
                node[k] = {}
            node = node[k]
        node[keys[-1]] = value
        self.save()

    def _decrypt_secrets(self):
        """디스크에서 읽은 암호화된 API 키를 메모리상 평문으로 변환합니다."""
        for path in SECRET_PATHS:
            val = self.get(path, "")
            if val:
                self._set_no_save(path, decrypt(val))

    def _encrypt_data_copy(self) -> dict:
        """저장용으로 _data를 깊은 복사하고 API 키를 암호화합니다."""
        data = copy.deepcopy(self._data)
        for path in SECRET_PATHS:
            keys = path.split(".")
            node = data
            for k in keys[:-1]:
                if not isinstance(node, dict) or k not in node:
                    node = None
                    break
                node = node[k]
            if node and isinstance(node, dict) and keys[-1] in node:
                val = node[keys[-1]]
                if val:
                    node[keys[-1]] = encrypt(val)
        return data

    def _set_no_save(self, key_path: str, value: Any):
        """설정값을 메모리에만 쓰고 파일에 저장하지 않습니다."""
        keys = key_path.split(".")
        node = self._data
        for k in keys[:-1]:
            if k not in node or not isinstance(node[k], dict):
                node[k] = {}
            node = node[k]
        node[keys[-1]] = value

    def _migrate_region_to_regions(self):
        """기존 capture.region만 있는 config를 capture.regions로 자동 변환합니다."""
        regions = self.get("capture.regions", [])
        region = self.get("capture.region")
        if region and not regions:
            self._set_no_save("capture.regions", [
                {"id": 1, "name": "영역 1", "rect": region, "enabled": True},
            ])

    def get_regions(self) -> list[dict]:
        """활성화된 캡처 영역 목록을 반환합니다."""
        return [r for r in self.get("capture.regions", []) if r.get("enabled", True)]

    def get_all_regions(self) -> list[dict]:
        """모든 캡처 영역을 반환합니다 (비활성 포함)."""
        return self.get("capture.regions", [])

    def add_region(self, rect: list[int], name: str | None = None) -> dict:
        """새 영역을 추가합니다. 최대 5개 제한."""
        regions = self.get("capture.regions", [])
        if len(regions) >= 5:
            return {}
        next_id = max((r["id"] for r in regions), default=0) + 1
        if name is None:
            name = f"영역 {next_id}"
        new_region = {"id": next_id, "name": name, "rect": rect, "enabled": True}
        regions.append(new_region)
        self.set("capture.regions", regions)
        # 하위호환: 첫 번째 영역을 capture.region에도 동기화
        self._sync_region_compat()
        return new_region

    def remove_region(self, region_id: int):
        """영역을 삭제합니다."""
        regions = [r for r in self.get("capture.regions", []) if r["id"] != region_id]
        self.set("capture.regions", regions)
        self._sync_region_compat()

    def update_region(self, region_id: int, **kwargs):
        """영역 속성을 수정합니다 (rect, name, enabled)."""
        regions = self.get("capture.regions", [])
        for r in regions:
            if r["id"] == region_id:
                r.update(kwargs)
                break
        self.set("capture.regions", regions)
        self._sync_region_compat()

    def _sync_region_compat(self):
        """regions[0]의 rect를 capture.region에 동기화합니다 (하위호환)."""
        regions = self.get("capture.regions", [])
        if regions:
            self._set_no_save("capture.region", regions[0]["rect"])
        else:
            self._set_no_save("capture.region", None)

    def get_provider_config(self, provider_name: str) -> dict:
        """특정 프로바이더의 설정 딕셔너리를 반환합니다."""
        return self.get(f"provider.{provider_name}", {})

    def get_active_provider(self) -> str:
        """현재 활성화된 프로바이더 이름을 반환합니다."""
        return self.get("provider.active", "gemini")


def _deep_merge(base: dict, override: dict) -> dict:
    """
    base 딕셔너리에 override 딕셔너리를 깊은 병합합니다.
    override에 없는 base의 기본값은 유지됩니다.
    """
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result
