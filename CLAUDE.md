# 말랑몰랑 (MallangMollang) — Project Instructions

## 이 프로젝트가 뭔가요?

Windows PC용 AI 하이브리드 화면 번역 유틸리티입니다. 기존 화면 번역기(MORT)의 한계를 LLM으로 극복하는 것이 목표입니다.

## 반드시 읽어야 할 문서

프로젝트의 모든 설계 결정은 아래 문서에 기록되어 있습니다. 코드를 작성하기 전에 반드시 참조하세요.

1. **`docs/PRD-MallangMollang.md`** — 기능 요구사항, 비기능 요구사항, MVP 스코프, 리스크
2. **`docs/UserFlow-MallangMollang.md`** — 시나리오별 태스크 플로우 + 전체 인터랙션 플로우
3. **`docs/SystemDesign-MallangMollang.md`** — 기술 스택, 모듈 구조, 인터페이스, 디렉토리 구조, 구현 순서
4. **`docs/HANDOFF.md`** — 기획 과정에서 내려진 핵심 결정들과 그 이유 (컨텍스트 전달용)

## 기술 스택

- Python 3.11+
- PyQt6 (GUI, 오버레이, 트레이)
- Tesseract / pytesseract (OCR)
- httpx (비동기 LLM API 호출)
- Pillow + OpenCV (이미지 처리)
- imagehash (변경 감지)

## 프로젝트 구조

```
mallangmollang/
├── core/          # 핵심 파이프라인 (capture, detector, ocr, translator, cache, pipeline, profiles)
├── providers/     # LLM 프로바이더 어댑터 (base, openai, gemini, claude, ollama)
├── display/       # 번역 표시 (overlay, panel, presets)
├── ui/            # 사용자 인터페이스 (tray, settings, onboarding, region_selector)
├── infra/         # 기반 유틸리티 (config, hotkeys, crypto)
├── main.py        # 진입점
└── requirements.txt
```

## MVP 구현 순서 (6 Units)

현재 Phase 1 (MVP) 구현 단계입니다. 아래 순서대로 진행합니다:

1. **기초 뼈대** — `infra/config.py` + `providers/base.py` + `providers/gemini.py`
2. **눈 달기** — `core/capture.py` + `core/ocr.py`
3. **뇌 달기** — `core/translator.py` + `core/pipeline.py`
4. **최적화** — `core/detector.py` + `core/cache.py`
5. **얼굴 달기** — `display/overlay.py` + `ui/region_selector.py`
6. **완성** — `ui/tray.py` + `ui/settings.py` + `main.py`

각 유닛은 독립적으로 테스트 가능해야 합니다. Unit 3까지 끝나면 콘솔에서 번역 결과를 볼 수 있고, Unit 5까지 끝나면 오버레이가 뜨고, Unit 6에서 MVP가 완성됩니다.

## 코딩 컨벤션

- 한국어 사용자를 주 대상으로 하는 프로젝트이므로, 코드 주석은 한국어로 작성합니다.
- 변수/함수/클래스명은 영어를 사용합니다.
- 각 모듈은 단일 책임 원칙을 따릅니다.
- Provider 추가 시 BaseProvider 추상 클래스를 상속받아 구현합니다.
- 설정은 모두 infra/config.py를 통해 관리합니다.

## 핵심 차별점 (MORT 대비)

이 프로젝트의 존재 이유입니다. 구현 시 이 차별점이 훼손되지 않도록 주의하세요:

1. **OCR 오류 교정 프롬프트** — 단순 번역이 아니라 "OCR 결과를 교정하고 번역해줘"
2. **문맥 기억** — 이전 3~5회 번역을 프롬프트에 포함
3. **Vision API 모드** — OCR 단계를 건너뛰고 이미지를 LLM에 직접 전달
4. **커서 추적 모드** — 웹/문서 탐색용
5. **번역 프로필** — 콘텐츠별 톤/용어/분위기 사전 정의
6. **이중 최적화** — 이미지 해시 변경 감지 + 텍스트 캐시

## 개발자 정보

- 개발 경험은 초보 수준 (Python 기초, C/Java 학교 수업 정도)
- AI 어시스턴트를 적극 활용한 바이브 코딩 방식
- 설명은 쉽고 구체적으로, 코드에는 충분한 주석을 달아주세요
