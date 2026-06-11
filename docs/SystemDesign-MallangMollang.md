# 말랑몰랑 (MallangMollang) — System Design Spec

**작성일:** 2026-06-01 (최종 수정: 2026-06-11)
**상태:** 승인됨 (구현 반영 업데이트)
**관련 문서:** PRD-MallangMollang.md, UserFlow-MallangMollang.md

---

## 1. 기술 스택

| 항목 | 선택 | 근거 |
|------|------|------|
| 언어 | Python 3.11+ | 낮은 진입장벽, 풍부한 라이브러리, AI 코드 생성 품질 |
| GUI | PyQt6 | 오버레이(투명 창), 트레이 아이콘, 크로스 모니터 지원 |
| OCR | Tesseract (pytesseract) | 오픈소스, 다국어, 검증된 안정성 |
| 이미지 처리 | Pillow, OpenCV | 캡처 이미지 전처리 |
| HTTP 클라이언트 | httpx (비동기) | 비동기 API 호출로 UI 블로킹 방지 |
| 배포 | PyInstaller 또는 Nuitka | 단일 실행 파일 패키징 |

---

## 2. 모듈 아키텍처

프로그램은 5개 모듈 그룹으로 구성된다.

### 2.1 Core Pipeline

파이프라인 순서대로 데이터를 처리하는 핵심 모듈.

**Capture** — 화면 캡처
- 영역 지정 모드: 사용자가 지정한 직사각형 영역을 주기적으로 캡처
- 커서 추적 모드: 마우스 커서 주변 영역을 자동 캡처
- 입력: 캡처 모드 (region/cursor), 영역 좌표 또는 커서 위치
- 출력: CaptureResult (PIL Image, 타임스탬프, 영역 좌표)

**Detector** — 변경 감지
- 이전 캡처와 현재 캡처의 이미지 해시(pHash)를 비교
- 입력: 현재 CaptureResult, 이전 CaptureResult
- 출력: bool (True=변경됨, False=변경 없음→스킵)
- 민감도 임계값은 Config에서 설정

**OCR Engine** — 텍스트 추출
- Tesseract를 통해 이미지에서 텍스트를 추출
- 추출 전 이미지 전처리(이진화, 노이즈 제거, 대비 보정) 수행
- `extract_text()`: 단어 단위 추출 → 전체 텍스트 결합
- `extract_lines()`: Tesseract level-4 줄 데이터를 `(block_num, par_num)` 기준으로 문단 병합. 목록 마커(`•`, `-`, `+`, `©` 등)로 시작하는 줄은 병합에서 제외
- OSD(Orientation and Script Detection)로 언어 자동 감지, 10회마다 재감지
- 입력: 캡처 이미지 (PIL Image), 인식 대상 언어
- 출력: `OcrResult` (전체 텍스트, 신뢰도) 또는 `list[LineBox]` (줄 단위 위치/크기/폰트)
- Vision API 모드에서는 이 모듈을 건너뜀

**Translator** — 번역 엔진
- 경로 A (OCR+LLM): OCR 텍스트 + 문맥을 프롬프트로 구성하여 LLM에 전달
- 경로 B (Vision): 캡처 이미지 + 문맥을 Vision LLM에 직접 전달
- `translate_text()`: 단일 텍스트 번역 (`[corrected]/[translated]` 형식)
- `translate_lines()`: 줄 단위 번역 (`N|` 번호 형식). 300자 이상 줄은 자동으로 `translate_text()`로 개별 번역
- `translate_vision()`: 이미지 직접 번역
- 이전 3~5회 번역 결과를 내부 큐(deque)로 관리하여 문맥 기억
- max_tokens를 입력 텍스트 길이에 비례해 동적 계산
- 입력: 텍스트 또는 이미지, 이전 문맥, 번역 설정
- 출력: TranslationResult (번역 텍스트, 교정된 원문, 사용 토큰 수)

**Cache** — 번역 캐시
- 텍스트 해시를 키로, 번역 결과를 값으로 저장하는 LRU 캐시
- 입력: 텍스트 해시 키
- 출력: CacheResult (히트 여부, 히트 시 번역 텍스트)

**Pipeline** — 오케스트레이터
- 위 모듈들을 순서대로 호출하는 메인 루프
- 캡처 → 감지 → (OCR →) 캐시 → 번역 → 표시
- 번역 경로 (OCR+LLM / Vision) 분기 처리
- 비동기 실행으로 UI 스레드 블로킹 방지
- `LineTranslation` 리스트 생성: 각 OCR 줄에 번역 텍스트 매핑
- 줄 매핑 품질 검사: 50% 이상 빈 줄이면 블록 모드로 폴백
- 진단 로그를 `translation_log.txt` 파일에 자동 저장

### 2.2 Providers

LLM 프로바이더별 어댑터. 모두 동일한 추상 인터페이스를 구현한다.

**추상 인터페이스 (BaseProvider)**
- `translate(prompt, model, params) → str` : 텍스트 프롬프트 → 번역 결과
- `translate_vision(prompt, image, model, params) → str` : 이미지 포함 프롬프트 → 번역 결과
- `test_connection() → bool` : 연결 테스트
- `supports_vision() → bool` : Vision 지원 여부

**구현체**
- OpenAIProvider: OpenAI API (GPT-4o, GPT-4o-mini 등)
- GeminiProvider: Google Gemini API (Flash, Pro 등)
- ClaudeProvider: Anthropic Claude API (Haiku, Sonnet 등)
- OllamaProvider: Ollama 로컬 API (localhost:11434)

새 프로바이더 추가 시 BaseProvider를 상속받아 구현하면 자동으로 사용 가능.

### 2.3 Display

번역 결과를 화면에 표시하는 모듈.

**Overlay** — 오버레이 창
- PyQt6 투명 윈도우 (FramelessWindowHint + WA_TranslucentBackground)
- 항상 최상위 (WindowStaysOnTopHint)
- 마우스 클릭 투과 (WA_TransparentForMouseEvents)
- `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` — mss 캡처에서 자동 제외 (피드백 루프 방지)
- 두 가지 표시 모드:
  - **line 모드**: 각 OCR 줄 위치에 불투명 배경 + 번역 텍스트 덮어씌우기 (MORT 스타일). 폰트 자동 축소(최소 8pt) + 박스 높이 자동 확장
  - **block 모드**: 캡처 영역 전체에 반투명 배경 + 번역 텍스트 (폴백)

**AreaIndicator** — 캡처 영역 표시
- 캡처 영역 테두리를 실선으로 표시
- 번역 중 펄스 애니메이션 (투명도 1.0↔0.3, 800ms 주기)

**Panel** — 사이드 패널 (미구현)
- 화면 한쪽에 고정되는 독립 창
- 위치(좌/우/상/하)와 크기 조절 가능
- 번역 히스토리를 스크롤 형태로 표시

**Presets** — 스타일 프리셋 관리
- 프리셋 데이터: 폰트 종류, 크기, 색상, 배경 색상, 투명도, 외곽선
- JSON 파일로 저장/불러오기
- 기본 프리셋 3종 내장 (밝은 배경용, 어두운 배경용, 고대비)

### 2.4 UI

사용자 인터페이스 컴포넌트.

**Tray** — 시스템 트레이 아이콘
- 우클릭 메뉴: 설정, 번역 시작/중지, 모드 전환, 진단 정보 복사, 종료
- 상태 표시: 아이콘 색상으로 번역 활성/비활성 구분

**Settings** — 설정 창
- 탭 구조: 프로바이더, 언어, 캡처, 표시, 단축키, 번역, 번역 프로필
- 각 탭이 Config 모듈을 통해 설정을 읽고 저장
- 번역 프로필 탭: 키워드 자동 생성, 수동 편집 (이름/장르/분위기/용어집/추가지시), 저장/삭제

**Toast** — 알림 토스트
- 에러 상세 메시지를 화면에 일시적으로 표시
- 레벨별 색상 구분 (error, info)

**Onboarding** — 온보딩 화면 (미구현)
- 최초 실행 시 표시
- 3단계: 소개 → 프로바이더 설정 → 언어 설정

**RegionSelector** — 영역 선택 UI
- 전체 화면 반투명 오버레이
- 마우스 드래그로 직사각형 영역 지정
- 복수 영역 지정 지원

### 2.5 Infrastructure

공통 기반 모듈.

**Config** — 설정 관리
- 모든 설정을 config.json에 저장/로드
- 기본값 정의, 유효성 검증
- 설정 변경 시 관련 모듈에 알림 (시그널/콜백)

**Hotkeys** — 글로벌 단축키
- pynput 또는 keyboard 라이브러리로 시스템 전역 단축키 등록
- 다른 프로그램 위에서도 동작

**Crypto** — API 키 암호화 (미구현)
- API 키를 로컬에 암호화하여 저장
- 평문 노출 방지

### 2.6 Profiles

번역 대상 콘텐츠의 배경 정보를 사전 정의하여 번역 품질을 높이는 모듈.

**Profiles** — 번역 프로필 관리 (`core/profiles.py`)
- `TranslationProfile` 데이터 구조: 이름, 장르, 분위기, 용어집, 추가 지시
- `profiles.json`으로 저장/불러오기 (여러 프로필 관리)
- LLM 자동 생성: 키워드 → Gemini API 호출(번역과 별도) → JSON 응답 파싱 → 프로필 필드 채움
- 번역 시 선택된 프로필을 `system_hint`에 텍스트 블록으로 주입
- 프로필 없이도 기존과 동일하게 동작

---

## 3. 데이터 흐름

### 3.1 기본 흐름 (OCR + LLM, 줄 단위)

```
Capture → Detector → OCR(extract_lines) → Cache → Translator(translate_lines) → Display(line모드)
            │ (변경없음)                     │ (히트)        │
            └→ SKIP                          └→ 캐시 표시    ├─ 짧은 줄: N| 번호 형식 일괄 번역
                                                              └─ 긴 줄(300자+): translate_text 개별 번역
```

줄 매핑 품질 검사: 번역 결과의 50% 이상이 빈 줄이면 block 모드로 폴백.

### 3.2 Vision API 흐름

```
Capture → Detector → Cache → Translator(Vision) → Display
            │ (변경없음)  │ (히트)
            └→ SKIP       └→ 캐시 번역 표시
```

Vision 모드에서는 OCR 단계를 건너뛰고, Translator가 캡처 이미지를 직접 Vision LLM에 전달한다. 캐시는 이미지 해시를 키로 사용한다.

### 3.3 문맥 기억 흐름

```
번역 결과 → Translator 내부 큐 (deque, maxlen=5)
           → 다음 번역 요청 시 프롬프트에 포함
```

---

## 4. 프로젝트 디렉토리 구조

```
mallangmollang/
├── core/                     # 핵심 파이프라인
│   ├── capture.py            # 화면 캡처 (영역/커서), mss 사용
│   ├── detector.py           # 변경 감지 (이미지 해시)
│   ├── ocr.py                # OCR 엔진 (extract_text, extract_lines, 문단 병합, 목록 분리)
│   ├── translator.py         # 번역 엔진 (줄 단위/개별/Vision, 문맥 기억)
│   ├── profiles.py           # 번역 프로필 관리 (LLM 자동 생성, JSON 저장/불러오기)
│   ├── cache.py              # 번역 캐시 (LRU)
│   └── pipeline.py           # 파이프라인 오케스트레이터 (LineTranslation, 진단 로그)
│
├── providers/                # LLM 프로바이더 어댑터
│   ├── base.py               # 추상 인터페이스 (BaseProvider)
│   ├── openai.py             # (미구현)
│   ├── gemini.py             # ✅ AI Studio + Vertex AI
│   ├── claude.py             # (미구현)
│   └── ollama.py             # (미구현)
│
├── display/                  # 번역 결과 표시
│   ├── overlay.py            # 오버레이 (line/block 모드, 폰트 자동 축소)
│   ├── area_indicator.py     # 캡처 영역 테두리 + 펄스 애니메이션
│   ├── panel.py              # 사이드 패널 (미구현)
│   └── presets.py            # 스타일 프리셋 관리
│
├── ui/                       # 사용자 인터페이스
│   ├── tray.py               # 시스템 트레이 (진단 복사 포함)
│   ├── settings.py           # 설정 창 (단축키 탭 포함)
│   ├── toast.py              # 에러/상태 토스트 알림
│   ├── onboarding.py         # 온보딩 화면 (미구현)
│   └── region_selector.py    # 영역 선택 드래그 UI
│
├── infra/                    # 기반 유틸리티
│   ├── config.py             # 설정 저장/로드 (JSON)
│   ├── hotkeys.py            # 글로벌 단축키 (pynput, 재로드 지원)
│   └── crypto.py             # API 키 암호화 (미구현)
│
├── config.json               # 사용자 설정 (자동 생성)
├── main.py                   # 진입점 (--debug 플래그)
└── requirements.txt          # 의존성

tools/                        # 개발/진단 도구 (패키지 외부)
└── ocr_inspect.py            # OCR 바운딩 박스 시각화
```

---

## 5. 핵심 의존성

```
PyQt6>=6.6          # GUI 프레임워크
pytesseract>=0.3    # Tesseract OCR 래퍼
Pillow>=10.0        # 이미지 처리
opencv-python>=4.8  # 이미지 전처리
httpx>=0.25         # 비동기 HTTP 클라이언트
imagehash>=4.3      # 이미지 해시 (변경 감지)
pynput>=1.7         # 글로벌 단축키
cryptography>=41.0  # API 키 암호화
```

---

## 6. MVP 구현 순서

Phase 1 (MVP) 범위 내에서의 구현 우선순위:

1. **infra/config.py** — 설정 관리 (모든 모듈의 기초)
2. **providers/base.py + providers/gemini.py** — 프로바이더 인터페이스 + 첫 번째 구현체
3. **core/capture.py** — 영역 지정 캡처
4. **core/ocr.py** — Tesseract OCR 래퍼
5. **core/translator.py** — LLM 번역 엔진 (프롬프트 설계)
6. **core/detector.py** — 변경 감지
7. **core/pipeline.py** — 파이프라인 조립
8. **display/overlay.py** — 오버레이 표시
9. **ui/region_selector.py** — 영역 선택 UI
10. **ui/tray.py** — 트레이 아이콘
11. **ui/settings.py** — 기본 설정 창
12. **main.py** — 전체 조립 및 실행

---

## 7. MORT 대비 차별화 요약

| 차별점 | 설명 |
|--------|------|
| OCR 오류 교정 프롬프트 | MORT는 OCR→번역 단순 전달. 말랑몰랑은 "OCR 결과를 교정하고 번역해줘" 프롬프트 설계. |
| 문맥 기억 | MORT에 없음. 말랑몰랑은 이전 3~5회 번역을 프롬프트에 포함하여 스토리 연속성 확보. |
| Vision API 모드 | MORT에 없음. OCR 단계 자체를 건너뛰는 근본적 접근. |
| 커서 추적 모드 | MORT에 없음. 웹/문서 탐색에 최적화된 조작 방식. |
| 이미지 해시 변경 감지 + 텍스트 캐시 | MORT의 DB 매칭과 다른, 이중 최적화 구조. |
| 번역 프로필 | MORT에 없음. 콘텐츠별 톤/용어/분위기를 사전 정의하여 맥락에 맞는 번역 유도. Steam 메타데이터 자동 연동 예정. |
