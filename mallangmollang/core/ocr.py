"""
OCR 엔진 모듈
Tesseract를 이용한 텍스트 추출 + OpenCV 이미지 전처리를 담당합니다.
"""

import re
from dataclasses import dataclass, field

import cv2
import numpy as np
import pytesseract
from PIL import Image

# OSD 스크립트 이름 → Tesseract 언어 코드 매핑
_SCRIPT_TO_LANG: dict[str, str] = {
    "Japanese":   "jpn",
    "Hiragana":   "jpn",
    "Katakana":   "jpn",
    "Korean":     "kor",
    "Hangul":     "kor",
    "HanS":       "chi_sim",   # 간체 한자
    "HanT":       "chi_tra",   # 번체 한자
    "Han":        "chi_sim",
    "Latin":      "eng",
    "Arabic":     "ara",
    "Cyrillic":   "rus",
    "Thai":       "tha",
}

# OSD 실패 시 폴백: 게임 번역에 가장 흔한 언어들
_AUTO_FALLBACK = "jpn+eng+kor"


@dataclass
class TextRegion:
    """텍스트가 감지된 개별 영역"""
    text: str
    x: int
    y: int
    width: int
    height: int
    confidence: float    # 0.0 ~ 100.0


@dataclass
class OcrResult:
    """OCR 처리 결과"""
    text: str                                  # 전체 추출 텍스트
    confidence: float                          # 평균 신뢰도 (0.0 ~ 100.0)
    regions: list[TextRegion] = field(default_factory=list)  # 개별 텍스트 영역들


_OSD_REDETECT_INTERVAL = 10


class OcrEngine:
    """
    Tesseract OCR 엔진 래퍼.

    사용 예시:
        engine = OcrEngine()
        result = engine.extract_text(image, lang="eng")
        print(result.text, result.confidence)
    """

    def __init__(self):
        self._cached_lang: str | None = None
        self._osd_cycle_count: int = 0

    def detect_script(self, image: Image.Image) -> str:
        """
        OSD(Orientation and Script Detection)로 이미지의 문자 체계를 감지합니다.

        Returns:
            Tesseract 언어 코드 (예: "jpn", "kor"). 감지 실패 시 _AUTO_FALLBACK 반환.
        """
        try:
            osd = pytesseract.image_to_osd(image, config="--psm 0")
            # OSD 출력에서 "Script: Xxx" 추출
            match = re.search(r"Script:\s*(\S+)", osd)
            if match:
                script = match.group(1)
                return _SCRIPT_TO_LANG.get(script, _AUTO_FALLBACK)
        except pytesseract.TesseractError:
            pass
        return _AUTO_FALLBACK

    def extract_text(
        self,
        image: Image.Image,
        lang: str = "auto",
        preprocess: bool = True,
    ) -> OcrResult:
        """
        이미지에서 텍스트를 추출합니다.

        Args:
            image: 캡처된 PIL 이미지
            lang: Tesseract 언어 코드 ("eng", "jpn", "kor" 등, "+"로 조합 가능).
                  "auto"로 설정하면 OSD로 자동 감지합니다.
            preprocess: 전처리 적용 여부

        Returns:
            OcrResult
        """
        if lang == "auto":
            self._osd_cycle_count += 1
            if self._cached_lang is None or self._osd_cycle_count >= _OSD_REDETECT_INTERVAL:
                self._cached_lang = self.detect_script(image)
                self._osd_cycle_count = 0
            lang = self._cached_lang

        if preprocess:
            processed = self._preprocess(image)
        else:
            img = np.array(image)
            processed = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img

        # Tesseract data → 개별 단어 단위 바운딩 박스 + 신뢰도
        data = pytesseract.image_to_data(
            processed,
            lang=lang,
            output_type=pytesseract.Output.DICT,
        )

        regions: list[TextRegion] = []
        confidences: list[float] = []

        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            conf = float(data["conf"][i])

            # 신뢰도 -1 또는 빈 텍스트는 건너뜀
            if conf < 0 or not text:
                continue

            regions.append(TextRegion(
                text=text,
                x=data["left"][i],
                y=data["top"][i],
                width=data["width"][i],
                height=data["height"][i],
                confidence=conf,
            ))
            confidences.append(conf)

        full_text = " ".join(r.text for r in regions)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return OcrResult(
            text=full_text,
            confidence=avg_confidence,
            regions=regions,
        )

    def _preprocess(self, image: Image.Image) -> np.ndarray:
        """
        OCR 정확도를 높이기 위한 이미지 전처리를 수행합니다.

        처리 순서:
          1. 그레이스케일 변환
          2. 노이즈 제거 (가우시안 블러)
          3. 대비 보정 (CLAHE)
          4. 이진화 (Otsu's method)
        """
        img = np.array(image)

        # 1. 그레이스케일
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img

        # 2. 노이즈 제거
        denoised = cv2.GaussianBlur(gray, (3, 3), 0)

        # 3. 대비 보정 (CLAHE: 지역 적응형 히스토그램 평활화)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)

        # 4. 이진화 (Otsu's method로 자동 임계값)
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        return binary
