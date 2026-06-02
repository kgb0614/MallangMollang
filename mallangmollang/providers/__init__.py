"""
LLM 프로바이더 팩토리
Config 설정에 따라 적절한 프로바이더 인스턴스를 생성합니다.
"""

from mallangmollang.infra.config import Config
from mallangmollang.providers.base import BaseProvider
from mallangmollang.providers.gemini import GeminiProvider


def create_provider(config: Config) -> BaseProvider:
    """
    Config의 provider.active 설정에 따라 프로바이더를 생성합니다.

    현재 지원: gemini
    추후 추가: openai, claude, ollama
    """
    active = config.get_active_provider()
    provider_config = config.get_provider_config(active)

    if active == "gemini":
        return GeminiProvider(
            api_key=provider_config.get("api_key", ""),
            model=provider_config.get("model", "gemini-2.0-flash"),
            endpoint=provider_config.get("endpoint", "ai_studio"),
            vertex_project_id=provider_config.get("vertex", {}).get("project_id", ""),
            vertex_region=provider_config.get("vertex", {}).get("region", "us-central1"),
            service_account=provider_config.get("vertex", {}).get("service_account", ""),
        )

    raise ValueError(f"지원하지 않는 프로바이더: '{active}'. 사용 가능: gemini")
