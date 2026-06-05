"""
변경 감지 모듈
이전 캡처와 현재 캡처의 이미지 해시(pHash)를 비교하여
유의미한 변화가 없으면 이후 파이프라인을 건너뜁니다.
"""

from dataclasses import dataclass

import imagehash
from PIL import Image

from mallangmollang.core.capture import CaptureResult


@dataclass
class DetectorResult:
    """변경 감지 결과"""
    changed: bool          # True=변경됨, False=변경 없음
    hash_diff: int         # 현재 해시와 이전 해시의 차이값
    current_hash: str      # 현재 이미지의 해시 문자열


class ChangeDetector:
    """
    이미지 pHash 기반 변경 감지기.

    연속된 두 캡처 이미지의 해시 차이가 임계값 이하면
    변경 없음으로 판단하여 OCR·번역 단계를 스킵합니다.

    사용 예시:
        detector = ChangeDetector(threshold=5)
        result = detector.detect(current_capture)
        if result.changed:
            # OCR + 번역 진행
    """

    def __init__(self, threshold: int = 5):
        """
        Args:
            threshold: pHash 차이 임계값.
                       낮을수록 민감 (작은 변화도 감지),
                       높을수록 둔감 (큰 변화만 감지).
                       권장 범위: 3~10
        """
        self.threshold = threshold
        self._prev_hash: imagehash.ImageHash | None = None

    def detect(self, capture: CaptureResult) -> DetectorResult:
        """
        현재 캡처 이미지가 이전 캡처와 유의미하게 달라졌는지 판단합니다.

        첫 호출 시에는 항상 changed=True를 반환합니다.

        Args:
            capture: 현재 캡처 결과

        Returns:
            DetectorResult
        """
        current_hash = imagehash.phash(capture.image)
        current_hash_str = str(current_hash)

        if self._prev_hash is None:
            # 첫 캡처: 비교 대상 없으므로 변경됨으로 처리
            self._prev_hash = current_hash
            return DetectorResult(changed=True, hash_diff=0, current_hash=current_hash_str)

        diff = int(current_hash - self._prev_hash)
        changed = diff > self.threshold

        if changed:
            # 변경됐을 때만 이전 해시를 갱신
            self._prev_hash = current_hash

        return DetectorResult(changed=changed, hash_diff=diff, current_hash=current_hash_str)

    def reset(self):
        """이전 해시를 초기화합니다. 영역 변경 시 호출하세요."""
        self._prev_hash = None
