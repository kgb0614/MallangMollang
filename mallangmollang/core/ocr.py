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

# OCR이 불릿/목록 마커를 읽을 때 흔히 나오는 문자들
_LIST_MARKERS = set("••-*=·▪►▶○●◆◇✓✗☐☑+>»~")


def _starts_with_list_marker(text: str) -> bool:
    """텍스트가 목록 항목(불릿, 번호 등)으로 시작하는지 확인합니다."""
    s = text.strip()
    if not s:
        return False
    if s[0] in _LIST_MARKERS:
        return True
    # 번호 매기기: "1.", "2)", "3]" 등
    if re.match(r"^\d+[.)\]]", s):
        return True
    # 괄호 시작: "(Optional)" 등
    if s.startswith("("):
        return True
    return False


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
class LineBox:
    """줄 단위 텍스트 영역 — 오버레이 덮어쓰기에 사용"""
    text: str
    x: int
    y: int
    width: int
    height: int
    confidence: float    # 평균 신뢰도
    font_pt: int         # 줄 높이 기반 폰트 크기 추정값


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

    def extract_lines(
        self,
        image: Image.Image,
        lang: str = "auto",
        preprocess: bool = True,
    ) -> list[LineBox]:
        """
        이미지에서 문단 인식 기반 바운딩 박스를 추출합니다.
        같은 문단(block+paragraph)에 속하는 줄은 하나로 합쳐서 반환합니다.
        → 목록은 줄 단위 유지, 줄글(문단)은 하나의 블록으로 처리.

        Args:
            image: 캡처된 PIL 이미지
            lang: Tesseract 언어 코드. "auto"면 OSD 자동 감지.
            preprocess: 전처리 적용 여부

        Returns:
            LineBox 리스트 (문단 내 줄이 합쳐진 상태)
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

        data = pytesseract.image_to_data(
            processed,
            lang=lang,
            output_type=pytesseract.Output.DICT,
        )

        n = len(data["text"])

        # Tesseract level: 1=page, 2=block, 3=paragraph, 4=line, 5=word
        # 줄(level==4) 데이터를 문단(block_num+par_num) 기준으로 그룹화
        para_groups: dict[tuple[int, int], list[dict]] = {}

        line_indices = [i for i in range(n) if data["level"][i] == 4]

        for li, line_idx in enumerate(line_indices):
            blk = data["block_num"][line_idx]
            par = data["par_num"][line_idx]
            ln = data["line_num"][line_idx]

            end = line_indices[li + 1] if li + 1 < len(line_indices) else n

            words = []
            confs = []
            for wi in range(line_idx + 1, end):
                if data["level"][wi] != 5:
                    continue
                if (data["block_num"][wi] != blk
                        or data["par_num"][wi] != par
                        or data["line_num"][wi] != ln):
                    continue
                word = data["text"][wi].strip()
                conf = float(data["conf"][wi])
                if word and conf >= 0:
                    words.append(word)
                    confs.append(conf)

            if not words:
                continue

            key = (blk, par)
            if key not in para_groups:
                para_groups[key] = []

            para_groups[key].append({
                "text": " ".join(words),
                "x": int(data["left"][line_idx]),
                "y": int(data["top"][line_idx]),
                "w": int(data["width"][line_idx]),
                "h": int(data["height"][line_idx]),
                "conf": sum(confs) / len(confs),
            })

        # 각 문단 그룹을 LineBox로 변환
        results: list[LineBox] = []

        for (blk, par), group_lines in para_groups.items():
            # 문단 내에서도 목록 마커로 시작하는 줄은 별도 항목으로 분리
            sub_groups = self._split_on_list_markers(group_lines)

            for sub in sub_groups:
                if len(sub) == 1:
                    gl = sub[0]
                    font_pt = max(1, round(gl["h"] * 72 / 96 / 1.2))
                    results.append(LineBox(
                        text=gl["text"],
                        x=gl["x"], y=gl["y"],
                        width=gl["w"], height=gl["h"],
                        confidence=gl["conf"],
                        font_pt=font_pt,
                    ))
                    continue

                merged_text = " ".join(gl["text"] for gl in sub)
                min_x = min(gl["x"] for gl in sub)
                min_y = min(gl["y"] for gl in sub)
                max_right = max(gl["x"] + gl["w"] for gl in sub)
                max_bottom = max(gl["y"] + gl["h"] for gl in sub)
                avg_conf = sum(gl["conf"] for gl in sub) / len(sub)

                merged_w = max_right - min_x
                merged_h = max_bottom - min_y

                avg_line_h = sum(gl["h"] for gl in sub) / len(sub)
                font_pt = max(1, round(avg_line_h * 72 / 96 / 1.2))

                results.append(LineBox(
                    text=merged_text,
                    x=min_x, y=min_y,
                    width=merged_w, height=merged_h,
                    confidence=avg_conf,
                    font_pt=font_pt,
                ))

        # y 좌표 기준 정렬 → 겹침 병합 → 인접 줄 병합
        results.sort(key=lambda lb: lb.y)
        results = self._merge_overlapping_lines(results)
        return self._merge_adjacent_lines(results)

    @staticmethod
    def _split_on_list_markers(group_lines: list[dict]) -> list[list[dict]]:
        """문단 내 줄들을 목록 마커 기준으로 분리합니다.

        마커로 시작하는 줄을 만나면 새 그룹을 시작합니다.
        마커가 아닌 줄은 이전 그룹에 합쳐집니다.
        """
        if len(group_lines) <= 1:
            return [group_lines]

        sub_groups: list[list[dict]] = [[group_lines[0]]]
        for gl in group_lines[1:]:
            if _starts_with_list_marker(gl["text"]):
                sub_groups.append([gl])
            else:
                sub_groups[-1].append(gl)
        return sub_groups

    def _merge_overlapping_lines(self, lines: list[LineBox]) -> list[LineBox]:
        """
        수직으로 겹치고 수평으로 가까운 줄들을 하나로 병합합니다.

        병합 조건:
          - 수직 겹침이 더 짧은 줄 높이의 50% 초과
          - 수평 간격이 20px 미만

        Args:
            lines: 정렬되지 않은 LineBox 리스트

        Returns:
            병합된 LineBox 리스트
        """
        if not lines:
            return []

        # y 좌표 기준 정렬
        sorted_lines = sorted(lines, key=lambda lb: lb.y)

        merged: list[LineBox] = [sorted_lines[0]]

        for current in sorted_lines[1:]:
            last = merged[-1]

            # 수직 겹침 계산
            overlap_top = max(last.y, current.y)
            overlap_bot = min(last.y + last.height, current.y + current.height)
            vertical_overlap = max(0, overlap_bot - overlap_top)

            shorter_height = min(last.height, current.height)

            # 수평 간격 계산
            last_right = last.x + last.width
            current_right = current.x + current.width
            horizontal_gap = max(0, max(last.x, current.x) - min(last_right, current_right))

            # 병합 조건: 수직 겹침 > 50% AND 수평 간격 < 20px
            if shorter_height > 0 and vertical_overlap > shorter_height * 0.5 and horizontal_gap < 20:
                # 병합: 두 줄을 모두 포함하는 바운딩 박스
                new_x = min(last.x, current.x)
                new_y = min(last.y, current.y)
                new_right = max(last_right, current_right)
                new_bot = max(last.y + last.height, current.y + current.height)
                new_w = new_right - new_x
                new_h = new_bot - new_y

                # 신뢰도: 두 줄의 평균
                new_conf = (last.confidence + current.confidence) / 2.0

                # 폰트 크기: 병합 후 높이 기준으로 재계산
                new_font_pt = max(1, round(new_h * 72 / 96 / 1.2))

                merged[-1] = LineBox(
                    text=last.text + " " + current.text,
                    x=new_x,
                    y=new_y,
                    width=new_w,
                    height=new_h,
                    confidence=new_conf,
                    font_pt=new_font_pt,
                )
            else:
                merged.append(current)

        return merged

    def _merge_adjacent_lines(self, lines: list[LineBox]) -> list[LineBox]:
        """
        수직으로 인접하고 수평 정렬이 비슷한 줄을 하나로 합칩니다.
        Tesseract가 같은 문단을 여러 block으로 분리한 경우를 처리합니다.

        병합 조건:
          - 두 줄 사이 수직 간격이 폰트 크기(px) 이내
          - 왼쪽 가장자리 차이가 50px 미만
          - 다음 줄이 목록 마커로 시작하지 않음
        """
        if len(lines) <= 1:
            return lines

        sorted_lines = sorted(lines, key=lambda lb: lb.y)
        merged: list[LineBox] = [sorted_lines[0]]

        for current in sorted_lines[1:]:
            last = merged[-1]

            gap = current.y - (last.y + last.height)
            line_px = last.font_pt * 96 / 72
            x_diff = abs(last.x - current.x)

            if gap < line_px and x_diff < 50 and not _starts_with_list_marker(current.text):
                new_x = min(last.x, current.x)
                new_y = last.y
                new_right = max(last.x + last.width, current.x + current.width)
                new_bottom = current.y + current.height
                avg_conf = (last.confidence + current.confidence) / 2.0
                merged[-1] = LineBox(
                    text=last.text + " " + current.text,
                    x=new_x, y=new_y,
                    width=new_right - new_x,
                    height=new_bottom - new_y,
                    confidence=avg_conf,
                    font_pt=last.font_pt,
                )
            else:
                merged.append(current)

        return merged

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
