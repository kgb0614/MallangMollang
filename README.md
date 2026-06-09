# 말랑몰랑 (MallangMollang)

AI 하이브리드 화면 번역 유틸리티 — Windows PC

## 뭐하는 프로그램?

화면의 텍스트를 OCR로 읽고, LLM이 오타를 교정하면서 자연스럽게 번역해주는 프로그램입니다.

## 기존 도구(MORT)와 뭐가 다른데?

- OCR이 글자를 잘못 읽어도 LLM이 문맥으로 교정
- 이전 대사를 기억해서 스토리가 이어지는 번역
- Vision API로 OCR 없이 이미지 직접 번역 (선택)

## 설치 방법

### 사전 요구사항

1. **Python 3.11 이상** — https://python.org/downloads
2. **Tesseract OCR** — https://github.com/UB-Mannheim/tesseract/wiki
   - 설치 후 PATH에 추가되어 있어야 합니다
   - 영어 외 언어(일본어, 중국어 등) 필요 시 설치 시 해당 언어 데이터 선택
3. **Google Gemini API 키** — https://aistudio.google.com/apikey

### 패키지 설치

```bash
# 저장소 클론
git clone https://github.com/kgb0614/mallangmollang.git
cd mallangmollang

# 의존성 설치
pip install -r requirements.txt
```

### 실행

```bash
python -m mallangmollang
```

또는

```bash
python mallangmollang/main.py
```

## 처음 실행 시

1. 프로그램이 시작되면 시스템 트레이에 아이콘이 생깁니다
2. 설정 창이 자동으로 열립니다
3. **프로바이더 탭**에서 Gemini API 키를 입력하고 "연결 테스트"로 확인합니다
4. **언어 탭**에서 원문 언어와 OCR 언어를 설정합니다
5. 저장 후 트레이 아이콘 우클릭 → **영역 재지정**으로 번역할 영역을 드래그합니다
6. 트레이 아이콘 우클릭 → **번역 시작**

## 트레이 메뉴

| 항목 | 설명 |
|------|------|
| 번역 시작 / 번역 중지 | 번역 루프 켜기/끄기 |
| 영역 재지정 | 캡처할 화면 영역 다시 선택 |
| 설정 | 설정 창 열기 |
| 종료 | 프로그램 종료 |

## 설정 항목

| 탭 | 주요 설정 |
|----|-----------|
| 프로바이더 | API 키, 모델, AI Studio / Vertex AI 선택 |
| 언어 | 원문 언어(자동/영/일/중), 번역 언어, OCR 언어 |
| 캡처 | 캡처 주기(ms), 변경 감지 민감도 |
| 번역 | 문맥 기억 수, Vision API 모드, 캐시 크기 |
| 표시 | 오버레이 스타일 프리셋 선택 |

## 기술 스택

Python 3.11+ · PyQt6 · Tesseract · httpx · Pillow · OpenCV · imagehash

## 문서

- [PRD (기획서)](docs/PRD-MallangMollang.md)
- [User Flow](docs/UserFlow-MallangMollang.md)
- [System Design](docs/SystemDesign-MallangMollang.md)
- [Handoff (기획 맥락)](docs/HANDOFF.md)

## 상태

Phase 1 (MVP) 완성 — 영역 지정 번역, 오버레이 표시, 변경 감지, 번역 캐시, 문맥 기억, Vision API 모드
