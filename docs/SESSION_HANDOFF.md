# 말랑몰랑 — 세션 핸드오프 문서

> 작성일: 2026-06-11  
> 현재 브랜치: claude/gracious-rubin-w5nsyw

---

## 현재 구현 상태

| 모듈 | 상태 | 비고 |
|------|------|------|
| `infra/config.py` | ✅ 완료 | |
| `providers/gemini.py` | ✅ 완료 | Vertex AI + AI Studio 양쪽 지원 |
| `providers/openai.py` | ❌ 미구현 | 설정에 UI만 있음, 호출 시 에러 |
| `providers/claude.py` | ❌ 미구현 | 동일 |
| `providers/ollama.py` | ❌ 미구현 | 동일 |
| `core/capture.py` | ✅ 완료 | |
| `core/detector.py` | ✅ 완료 | 이미지 해시 기반 변경 감지 |
| `core/cache.py` | ✅ 완료 | LRU 텍스트 캐시 |
| `core/ocr.py` | ✅ 완료 | `extract_lines()` 문단 병합 포함 |
| `core/translator.py` | ✅ 완료 | 줄 단위 번역, 긴 문단 처리 포함 |
| `core/pipeline.py` | ✅ 완료 | `LineTranslation` 기반 줄 단위 흐름 |
| `display/overlay.py` | ✅ 완료 | line/block 두 가지 모드 |
| `display/area_indicator.py` | ✅ 완료 | 펄스 애니메이션 포함 |
| `ui/tray.py` | ✅ 완료 | |
| `ui/settings.py` | ✅ 완료 | 단축키 탭 추가됨 |
| `ui/region_selector.py` | ✅ 완료 | |
| `ui/toast.py` | ✅ 완료 | 에러 상세 메시지 표시 |
| `infra/hotkeys.py` | ✅ 완료 | 글로벌 단축키, 재로드 지원 |
| `main.py` | ✅ 완료 | `--debug` 플래그, 에러 토스트 |
| `tools/ocr_inspect.py` | ✅ 완료 | OCR 바운딩 박스 시각화 진단 도구 |

---

## 이번 세션에서 한 것

### 1. AreaIndicator 펄스 애니메이션
- 번역 중일 때 영역 테두리가 투명도 1.0↔0.3으로 800ms 주기로 깜빡임
- `QPropertyAnimation` + `pyqtProperty(float)` 구현
- `set_status("translating")` 호출 시 시작, 다른 상태에서 멈춤

### 2. 단축키 설정 UI
- `settings.py`에 "단축키" 탭 추가
- 저장 시 `main.py`에서 `hotkeys.reload()` 호출

### 3. 오류 토스트
- `_Bridge.error_detail` 시그널로 에러 상세 메시지 전달
- `toast.show(message[:200], level="error", duration_ms=5000)` 표시

### 4. OCR 진단 도구 (`tools/ocr_inspect.py`)
- 캡처 이미지에 OCR 바운딩 박스를 색상으로 그려서 PNG 저장
- CLI: `python tools/ocr_inspect.py --image FILE --lang jpn`

### 5. 오버레이 전면 개편 (MORT 스타일)
- `display/overlay.py` 완전 재작성
- `TranslatedLine` dataclass: 위치 + 번역 텍스트 + 폰트 크기
- `show_lines()`: 각 OCR 박스 위치에 불투명 배경 + 번역 텍스트 덮어씌우기
- `is_multiline = line.height > line_height * 1.3` 기준으로 문단/단일 줄 구분
- 문단: word wrap으로 전체 OCR 박스 채움
- 단일: 한 줄 텍스트로 baseline에 렌더링

### 6. 줄 단위 OCR + 번역 파이프라인
- `ocr.py`: `extract_lines()` — Tesseract level-4 데이터를 `(block_num, par_num)` 기준으로 문단 병합
- `translator.py`: `translate_lines()` — "1| 텍스트" 형식으로 LLM 호출
- `_parse_line_response()`: 구분자 패턴 4종 시도, `expected_count==1`이면 전체 응답 보존
- `pipeline.py`: `LineTranslation` 리스트 생성, 50% 빈 줄이면 블록 모드 폴백

### 7. `--debug` 플래그
- `python -m mallangmollang.main --debug` 실행 시 `SetWindowDisplayAffinity` 생략
- 오버레이/영역표시 창을 스크린샷으로 캡처 가능

---

## 알려진 문제 (미해결)

### 🔴 치명적

1. **긴 대화문 번역 일부만 나오는 현상**
   - 증상: 3줄짜리 대화창인데 1번째 줄만 번역되고 나머지는 원문
   - 원인: OCR이 문단 전체를 1개 LineBox로 묶어서 보내는데, LLM이 "1| ..." 형식으로 응답하면 파싱은 되지만 실제 번역 텍스트가 OCR 박스 높이보다 짧아서 잘려 보임
   - 관련 파일: `display/overlay.py:_paint_lines()` — `is_multiline` 판단 + word wrap 영역
   - **현재 상태**: 코드 수정은 완료 (b5ca888 커밋), 실제 테스트 결과 확인 필요

2. **OpenAI/Claude/Ollama 프로바이더 미구현**
   - 설정에서 선택하면 "아직 구현 중" 에러 발생

### 🟡 중요

3. **오버레이 검은 여백**
   - 번역이 짧으면 OCR 박스 아래쪽이 검은색 배경으로 채워짐
   - 해결책: 번역 텍스트 실제 높이에 맞게 배경 크기 조정

4. **OCR 신뢰도 필터링 없음**
   - 화면 일부 아무 글자나 잡아서 번역 시도함
   - 해결책: `LineBox.confidence < 30.0`이면 스킵

5. **캡처 영역 고정 좌표**
   - 창을 이동하거나 스크롤하면 엉뚱한 곳을 번역

---

## 실행 방법

```bash
# 일반 실행
python -m mallangmollang.main

# 디버그 모드 (스크린샷에 오버레이 보임)
python -m mallangmollang.main --debug

# OCR 진단 도구
python tools/ocr_inspect.py --image screenshot.png --lang jpn
python tools/ocr_inspect.py --region 100 200 800 400 --delay 3
```

---

## 주요 파일 위치

```
mallangmollang/
├── main.py                     # 앱 진입점, --debug 플래그
├── core/
│   ├── ocr.py                  # extract_lines(), LineBox, 문단 병합
│   ├── translator.py           # translate_lines(), _parse_line_response()
│   └── pipeline.py             # LineTranslation, 블록 모드 폴백
├── display/
│   ├── overlay.py              # TranslatedLine, show_lines(), _paint_lines()
│   └── area_indicator.py       # 펄스 애니메이션, set_status()
├── ui/
│   ├── settings.py             # 단축키 탭 포함
│   └── toast.py                # 에러 상세 메시지 표시
├── infra/
│   └── hotkeys.py              # GlobalHotKeys, reload()
└── tools/
    └── ocr_inspect.py          # OCR 바운딩 박스 진단
```

---

## 다음 세션 우선순위

### 즉시 해야 할 것

1. **긴 대화문 번역 테스트 확인**
   - `--debug` 모드로 실행해서 2~3줄짜리 대화창에서 오버레이 확인
   - 여전히 1줄만 보인다면 `_paint_lines()` word wrap 영역 재점검

2. **오버레이 검은 여백 제거**
   - `overlay.py:_paint_lines()` — 문단 모드에서 `box_h = line.height` 고정
   - 번역 텍스트 실제 높이로 `box_h` 재계산: `QFontMetrics.boundingRect(textRect, flags, text).height()`

3. **OCR 신뢰도 필터링**
   - `pipeline.py`: `line_boxes = [lb for lb in line_boxes if lb.confidence >= 30.0]`

### 그 다음

4. **OpenAI 프로바이더 구현** (`providers/openai.py`)
   - `BaseProvider` 상속, `translate()` + `translate_vision()` 구현
   - httpx 비동기, `Authorization: Bearer {api_key}` 헤더

5. **번역 속도 개선**
   - 변경 감지 threshold 조정 (`detector.hash_threshold`)
   - 캡처 주기 설정 노출 (`capture.interval_ms`)

---

## 다음 세션 시작 멘트

```
말랑몰랑 프로젝트 계속 진행하자. docs/SESSION_HANDOFF.md 읽어줘.

오늘은 아래 순서로 진행할 거야:
1. 오버레이 검은 여백 문제 수정 (번역 짧을 때 OCR 박스 아래 검은 배경)
2. OCR 신뢰도 낮은 줄 필터링 추가 (30% 미만 스킵)
3. [긴 대화문 번역 테스트 결과] → 문제 있으면 overlay.py word wrap 재점검

브랜치: claude/gracious-rubin-w5nsyw
```
