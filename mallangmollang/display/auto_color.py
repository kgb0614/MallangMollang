"""
자동 색상 매핑 모듈
캡처 이미지의 배경색을 분석하여 대비되는 텍스트/외곽선 색상을 반환합니다.
"""

from PIL import Image


def _luminance(r: int, g: int, b: int) -> float:
    """sRGB 상대 휘도 (0.0 ~ 1.0)"""
    return 0.2126 * (r / 255) + 0.7152 * (g / 255) + 0.0722 * (b / 255)


def analyze_colors(
    image: Image.Image,
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    """
    이미지의 평균 배경색을 분석하여 대비 텍스트/외곽선 색상을 반환합니다.

    Args:
        image: 캡처된 PIL 이미지

    Returns:
        (text_color_rgba, outline_color_rgba)
    """
    # 빠른 분석을 위해 축소
    thumb = image.copy()
    thumb.thumbnail((64, 64))
    pixels = list(thumb.getdata())

    if not pixels:
        return (255, 255, 255, 255), (0, 0, 0, 200)

    # 평균 색상 계산
    total_r = sum(p[0] for p in pixels)
    total_g = sum(p[1] for p in pixels)
    total_b = sum(p[2] for p in pixels)
    n = len(pixels)
    avg_r, avg_g, avg_b = total_r // n, total_g // n, total_b // n

    lum = _luminance(avg_r, avg_g, avg_b)

    if lum > 0.6:
        # 밝은 배경 → 어두운 텍스트, 밝은 외곽선
        text_color = (20, 20, 30, 255)
        outline_color = (240, 240, 240, 220)
    elif lum > 0.3:
        # 중간 밝기 → 흰 텍스트, 검은 외곽선 (최대 대비)
        text_color = (255, 255, 255, 255)
        outline_color = (0, 0, 0, 220)
    else:
        # 어두운 배경 → 밝은 텍스트, 어두운 외곽선
        text_color = (255, 255, 255, 255)
        outline_color = (0, 0, 0, 200)

    return text_color, outline_color
