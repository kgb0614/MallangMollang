"""
OCR 바운딩 박스 진단 도구

사용법:
    # 이미지 파일로 확인
    python tools/ocr_inspect.py --image screenshot.png

    # 스크린샷 직접 촬영 (3초 후 캡처)
    python tools/ocr_inspect.py --region 100 100 800 400

    # 언어 지정
    python tools/ocr_inspect.py --image screenshot.png --lang jpn

출력:
    - ocr_inspect_result.png  : 바운딩 박스가 그려진 시각화 이미지
    - 콘솔에 줄 단위 텍스트, 위치, 폰트 크기 추정값 출력
"""

import argparse
import sys
import time
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageDraw, ImageFont


def capture_region(x: int, y: int, w: int, h: int) -> Image.Image:
    import mss
    with mss.mss() as sct:
        monitor = {"left": x, "top": y, "width": w, "height": h}
        raw = sct.grab(monitor)
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def get_line_boxes(image: Image.Image, lang: str) -> list[dict]:
    """
    Tesseract image_to_data()에서 줄(line) 단위 바운딩 박스를 추출합니다.

    Tesseract level 계층:
        1=page  2=block  3=para  4=line  5=word
    level=4 행에 줄 전체의 바운딩 박스가 들어있습니다.
    """
    img_array = np.array(image)
    if len(img_array.shape) == 3:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_array

    # 전처리
    denoised = cv2.GaussianBlur(gray, (3, 3), 0)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)
    _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    data = pytesseract.image_to_data(
        binary,
        lang=lang,
        output_type=pytesseract.Output.DICT,
    )

    lines = []
    n = len(data["level"])

    for i in range(n):
        # level 4 = line
        if data["level"][i] != 4:
            continue

        # 해당 줄에 속한 단어들을 모아 텍스트 조합
        blk = data["block_num"][i]
        par = data["par_num"][i]
        ln  = data["line_num"][i]

        words = []
        confs = []
        for j in range(n):
            if (
                data["level"][j] == 5
                and data["block_num"][j] == blk
                and data["par_num"][j] == par
                and data["line_num"][j] == ln
            ):
                word = data["text"][j].strip()
                conf = float(data["conf"][j])
                if word and conf >= 0:
                    words.append(word)
                    confs.append(conf)

        if not words:
            continue

        x = data["left"][i]
        y = data["top"][i]
        w = data["width"][i]
        h = data["height"][i]

        # 폰트 크기 추정: 줄 높이(px) ≈ 글자 크기(pt) × 1.2배 정도
        # 96 DPI 기준으로 역산: pt = px * 72 / 96
        estimated_pt = round(h * 72 / 96 / 1.2)

        lines.append({
            "text":    " ".join(words),
            "x": x, "y": y, "w": w, "h": h,
            "conf":    sum(confs) / len(confs) if confs else 0.0,
            "font_pt": estimated_pt,
        })

    return lines


def visualize(image: Image.Image, lines: list[dict], output_path: str):
    """바운딩 박스와 메타데이터를 이미지에 그려서 저장합니다."""
    vis = image.convert("RGB").copy()
    draw = ImageDraw.Draw(vis)

    colors = [
        (255, 80,  80),   # 빨강
        (80,  200, 80),   # 초록
        (80,  120, 255),  # 파랑
        (255, 200, 50),   # 노랑
        (200, 80,  255),  # 보라
    ]

    for idx, line in enumerate(lines):
        color = colors[idx % len(colors)]
        x, y, w, h = line["x"], line["y"], line["w"], line["h"]

        # 바운딩 박스
        draw.rectangle([x, y, x + w, y + h], outline=color, width=2)

        # 레이블 (줄 번호 + 폰트 크기 추정)
        label = f"#{idx+1} ~{line['font_pt']}pt"
        draw.rectangle([x, y - 14, x + len(label) * 7, y], fill=color)
        draw.text((x + 2, y - 13), label, fill=(0, 0, 0))

    vis.save(output_path)
    print(f"\n[저장됨] {output_path}\n")


def main():
    parser = argparse.ArgumentParser(description="OCR 바운딩 박스 진단 도구")
    parser.add_argument("--image",  type=str, help="분석할 이미지 파일 경로")
    parser.add_argument("--region", type=int, nargs=4,
                        metavar=("X", "Y", "W", "H"),
                        help="화면 캡처 영역 (예: --region 100 100 800 400)")
    parser.add_argument("--lang",   type=str, default="jpn+eng+kor",
                        help="Tesseract 언어 코드 (기본: jpn+eng+kor)")
    parser.add_argument("--delay",  type=int, default=3,
                        help="--region 사용 시 캡처 전 대기 시간(초) (기본: 3)")
    parser.add_argument("--output", type=str, default="ocr_inspect_result.png",
                        help="결과 이미지 저장 경로 (기본: ocr_inspect_result.png)")
    args = parser.parse_args()

    # 이미지 로드
    if args.image:
        print(f"[이미지 로드] {args.image}")
        image = Image.open(args.image).convert("RGB")
    elif args.region:
        x, y, w, h = args.region
        print(f"[캡처 대기] {args.delay}초 후 ({x}, {y}, {w}×{h}) 영역을 캡처합니다...")
        print("  → 캡처할 화면으로 이동하세요!")
        time.sleep(args.delay)
        image = capture_region(x, y, w, h)
        print("[캡처 완료]")
    else:
        parser.print_help()
        print("\n오류: --image 또는 --region 중 하나를 지정해야 합니다.")
        sys.exit(1)

    # OCR 실행
    print(f"\n[OCR 실행] 언어: {args.lang}")
    lines = get_line_boxes(image, args.lang)

    if not lines:
        print("텍스트를 감지하지 못했습니다. 언어 설정이나 이미지를 확인하세요.")
        sys.exit(0)

    # 결과 출력
    print(f"\n감지된 줄: {len(lines)}개\n")
    print(f"{'#':<4} {'위치(x,y)':<16} {'크기(w×h)':<14} {'신뢰도':>6} {'폰트추정':>8}  텍스트")
    print("-" * 80)
    for i, line in enumerate(lines):
        pos  = f"({line['x']}, {line['y']})"
        size = f"{line['w']}×{line['h']}"
        conf = f"{line['conf']:.1f}%"
        fpt  = f"~{line['font_pt']}pt"
        print(f"{i+1:<4} {pos:<16} {size:<14} {conf:>6} {fpt:>8}  {line['text']}")

    # 시각화 저장
    visualize(image, lines, args.output)


if __name__ == "__main__":
    main()
