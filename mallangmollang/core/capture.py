"""
화면 캡처 모듈
영역 지정 모드와 커서 추적 모드를 지원합니다.
"""

import time
from dataclasses import dataclass

import mss
from PIL import Image


@dataclass
class CaptureResult:
    """캡처 결과"""
    image: Image.Image                         # 캡처된 이미지
    timestamp: float                           # 캡처 시각 (time.time())
    region: tuple[int, int, int, int]          # (x, y, width, height)


class ScreenCapture:
    """
    화면 캡처를 담당합니다.

    사용 예시:
        cap = ScreenCapture()
        result = cap.capture_region((100, 200, 800, 600))
        result.image.show()
    """

    def capture_region(self, region: tuple[int, int, int, int]) -> CaptureResult:
        """
        지정된 영역을 캡처합니다.

        Args:
            region: (x, y, width, height) 좌표

        Returns:
            CaptureResult
        """
        x, y, w, h = region
        monitor = {"left": x, "top": y, "width": w, "height": h}
        with mss.mss() as sct:
            screenshot = sct.grab(monitor)
            image = Image.frombytes("RGB", screenshot.size, screenshot.rgb)

        return CaptureResult(
            image=image,
            timestamp=time.time(),
            region=region,
        )

    def capture_around_cursor(self, radius: int = 200) -> CaptureResult:
        """
        마우스 커서 주변 영역을 캡처합니다.

        Args:
            radius: 커서 중심에서의 캡처 반경 (픽셀)

        Returns:
            CaptureResult
        """
        from pynput.mouse import Controller
        mouse = Controller()
        cx, cy = mouse.position

        with mss.mss() as sct:
            full = sct.monitors[0]

        screen_left = full["left"]
        screen_top = full["top"]
        screen_right = screen_left + full["width"]
        screen_bottom = screen_top + full["height"]

        x = max(screen_left, cx - radius)
        y = max(screen_top, cy - radius)
        right = min(screen_right, cx + radius)
        bottom = min(screen_bottom, cy + radius)
        w = right - x
        h = bottom - y

        if w <= 0 or h <= 0:
            raise ValueError(f"캡처 영역이 유효하지 않습니다: ({x}, {y}, {w}, {h})")

        return self.capture_region((x, y, w, h))

    def get_monitors(self) -> list[dict]:
        """
        연결된 모니터 목록을 반환합니다.

        Returns:
            [{"left": 0, "top": 0, "width": 1920, "height": 1080}, ...]
            인덱스 0은 전체 가상 영역, 1부터 개별 모니터
        """
        with mss.mss() as sct:
            return sct.monitors

    def close(self):
        """하위 호환용 — 더 이상 핸들을 보관하지 않으므로 no-op."""
        pass
