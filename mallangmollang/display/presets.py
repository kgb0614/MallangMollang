"""
스타일 프리셋 관리 모듈
오버레이 창의 폰트, 색상, 배경 투명도 등 시각적 설정을 관리합니다.
"""

from dataclasses import dataclass, field
from typing import Tuple


# 색상 타입 (R, G, B, A) — 각 값 0~255
RGBA = Tuple[int, int, int, int]


@dataclass
class OverlayPreset:
    """오버레이 스타일 프리셋"""
    name: str                          # 프리셋 이름
    font_family: str = "맑은 고딕"     # 폰트 종류
    font_size: int = 16                # 폰트 크기 (pt)
    font_bold: bool = False            # 굵게
    text_color: RGBA = field(default_factory=lambda: (255, 255, 255, 255))   # 흰색
    bg_color: RGBA = field(default_factory=lambda: (0, 0, 0, 160))          # 반투명 검정
    outline: bool = True               # 텍스트 외곽선
    outline_color: RGBA = field(default_factory=lambda: (0, 0, 0, 200))     # 외곽선 색상
    padding: int = 8                   # 내부 여백 (px)
    border_radius: int = 6             # 모서리 둥글기 (px)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "font_family": self.font_family,
            "font_size": self.font_size,
            "font_bold": self.font_bold,
            "text_color": list(self.text_color),
            "bg_color": list(self.bg_color),
            "outline": self.outline,
            "outline_color": list(self.outline_color),
            "padding": self.padding,
            "border_radius": self.border_radius,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OverlayPreset":
        return cls(
            name=data["name"],
            font_family=data.get("font_family", "맑은 고딕"),
            font_size=data.get("font_size", 16),
            font_bold=data.get("font_bold", False),
            text_color=tuple(data.get("text_color", [255, 255, 255, 255])),
            bg_color=tuple(data.get("bg_color", [0, 0, 0, 160])),
            outline=data.get("outline", True),
            outline_color=tuple(data.get("outline_color", [0, 0, 0, 200])),
            padding=data.get("padding", 8),
            border_radius=data.get("border_radius", 6),
        )


# ── 기본 내장 프리셋 3종 ──

PRESET_DEFAULT = OverlayPreset(
    name="기본",
    font_family="맑은 고딕",
    font_size=16,
    text_color=(255, 255, 255, 255),
    bg_color=(0, 0, 0, 160),
)

PRESET_DARK_GAME = OverlayPreset(
    name="어두운 게임용",
    font_family="맑은 고딕",
    font_size=16,
    font_bold=True,
    text_color=(255, 255, 180, 255),    # 연한 노란색
    bg_color=(0, 0, 0, 200),            # 더 불투명한 검정
    outline=True,
)

PRESET_LIGHT_BG = OverlayPreset(
    name="밝은 배경용",
    font_family="맑은 고딕",
    font_size=16,
    text_color=(30, 30, 30, 255),       # 거의 검정
    bg_color=(255, 255, 255, 180),      # 반투명 흰색
    outline=False,
)

BUILTIN_PRESETS: list[OverlayPreset] = [PRESET_DEFAULT, PRESET_DARK_GAME, PRESET_LIGHT_BG]


def get_preset_by_name(name: str, presets: list[OverlayPreset] | None = None) -> OverlayPreset:
    """이름으로 프리셋을 찾아 반환합니다. 없으면 기본 프리셋을 반환합니다."""
    search_list = presets if presets is not None else BUILTIN_PRESETS
    for preset in search_list:
        if preset.name == name:
            return preset
    return PRESET_DEFAULT
