# 말랑몰랑 — 세션 핸드오프 문서

> 최종 업데이트: 2026-06-11
> 현재 브랜치: claude/gracious-rubin-w5nsyw

---

## 현재 구현 상태

### Core Pipeline

| 모듈 | 상태 | 비고 |
|------|------|------|
| `core/capture.py` | ✅ 완료 | 매 캡처마다 `with mss.mss()` 사용 (스레드 안전) |
| `core/detector.py` | ✅ 완료 | 이미지 해시 기반 변경 감지 |
| `core/cache.py` | ✅ 완료 | LRU 텍스트 캐시 (메모리만, 디스크 저장은 P2-1에서 추가 예정) |
| `core/ocr.py` | ✅ 완료 | `extract_lines()` 문단 병합 + 목록 마커 분리 |
| `core/translator.py` | ✅ 완료 | 줄 단위 번역, 긴 문단(300자+) 개별, 프로필 hint 주입 |
| `core/pipeline.py` | ✅ 완료 | `LineTranslation` 줄 단위 흐름 + 진단 로그 + OCR 신뢰도 필터(conf<30) |
| `core/profiles.py` | ✅ 완료 | 번역 프로필 관리 (저장/불러오기/LLM 자동 생성) |

### Providers

| 모듈 | 상태 | 비고 |
|------|------|------|
| `providers/base.py` | ✅ 완료 | `BaseProvider` 추상 인터페이스 |
| `providers/gemini.py` | ✅ 완료 | AI Studio + Vertex AI, `finishReason` 로깅 |
| `providers/openai.py` | ❌ 미구현 | 설정 UI만 있음, 호출 시 에러. Phase 3 |
| `providers/claude.py` | ❌ 미구현 | 동일. Phase 3 |
| `providers/ollama.py` | ❌ 미구현 | 동일. Phase 3 |

### Display

| 모듈 | 상태 | 비고 |
|------|------|------|
| `display/overlay.py` | ✅ 완료 | line/block 모드, 폰트 자동 축소(최소 8pt) + 박스 확장 |
| `display/panel.py` | ✅ 완료 | QTextBrowser 기반 번역 히스토리. 드래그 이동, 지우기 버튼 |
| `display/area_indicator.py` | ✅ 완료 | 펄스 애니메이션, `SetWindowDisplayAffinity` 캡처 제외 |
| `display/presets.py` | ✅ 완료 | 기본 프리셋 3종 (기본/어두운 게임용/밝은 배경용) |

### UI

| 모듈 | 상태 | 비고 |
|------|------|------|
| `ui/tray.py` | ✅ 완료 | 진단 정보 복사 메뉴 포함 |
| `ui/settings.py` | ✅ 완료 | 7탭: 프로바이더, 언어, 캡처, 번역, 표시, 프로필, 단축키 |
| `ui/region_selector.py` | ✅ 완료 | |
| `ui/control_panel.py` | ✅ 완료 | 플로팅 컨트롤 패널 (시작/중지/영역/설정) |
| `ui/toast.py` | ✅ 완료 | 에러 상세 메시지 표시, 4단계 레벨 |
| `ui/onboarding.py` | ❌ 미구현 | Phase 3 |

### Infrastructure

| 모듈 | 상태 | 비고 |
|------|------|------|
| `infra/config.py` | ✅ 완료 | 싱글톤, 점 경로 접근, 깊은 병합 |
| `infra/hotkeys.py` | ✅ 완료 | 글로벌 단축키, 재로드 지원 |
| `infra/crypto.py` | ✅ 완료 | Fernet 암호화, 머신 고유 키 유도, 자동 마이그레이션 |

### 기타

| 모듈 | 상태 | 비고 |
|------|------|------|
| `main.py` | ✅ 완료 | `--debug` 플래그, 스냅샷 모드, 에러 토스트 |
| `tools/ocr_inspect.py` | ✅ 완료 | OCR 바운딩 박스 시각화 진단 도구 |

---

## 구현 완료된 PRD 기능 매핑

| PRD 항목 | 상태 | 구현 위치 |
|----------|------|-----------|
| F1-1 영역 지정 캡처 | ✅ | `core/capture.py`, `ui/region_selector.py` |
| F1-2 커서 추적 캡처 | ❌ 폐기 | 구현 후 실용성 부족으로 revert |
| F2-1 이미지 해시 비교 | ✅ | `core/detector.py` |
| F3-1 Tesseract 연동 | ✅ | `core/ocr.py` |
| F3-2 다국어 인식 | ✅ | OSD 자동 감지 + 수동 설정 |
| F3-3 이미지 전처리 | ✅ | 그레이스케일 → 노이즈 제거 → CLAHE → Otsu 이진화 |
| F4-1 텍스트 해시 캐시 | ✅ | `core/cache.py` |
| F5-1 OCR 오류 교정 | ✅ | `translator.py` 프롬프트 설계 |
| F5-2 문맥 기억 | ✅ | `deque(maxlen=context_count)` |
| F5-3 번역 방향 설정 | ✅ | `language.source` / `language.target` 설정 |
| F5-5 Vision API 모드 | ✅ | `translator.translate_vision()` |
| F5-6 번역 프로필 | ✅ | `core/profiles.py` + `ui/settings.py` 프로필 탭 + `translator.py` hint 주입 |
| F6-1 Gemini BYOK | ✅ | `providers/gemini.py` |
| F6-4 API 키 안전 저장 | ✅ | `infra/crypto.py` Fernet 암호화 |
| F7-1 오버레이 모드 | ✅ | `display/overlay.py` (line + block) |
| F7-2 사이드 패널 모드 | ✅ | `display/panel.py` |
| F8-1 글로벌 단축키 | ✅ | `infra/hotkeys.py` |
| F8-2 설정 UI | ✅ | `ui/settings.py` |
| F8-3 설정 저장 | ✅ | `infra/config.py` (JSON) |

---

## 이번 세션 작업 내역 (2026-06-13)

### Phase 2 전체 구현 완료

| ID | 기능 | 상태 |
|----|------|------|
| P2-1 | 영속 캐시 (디스크 저장) | ✅ 완료 |
| P2-2 | 스냅샷 오버레이 정리 (ESC/클릭/타이머) | ✅ 완료 |
| P2-3 | OCR 전처리 미리보기 | ✅ 완료 |
| P2-4 | 다중 OCR 영역 (최대 5개) | ✅ 완료 |
| P2-5 | 영역 크기 조정·삭제 UI | ✅ 완료 |
| P2-6 | 윈도우 지정 캡처 + OCR 제외 영역 | ✅ 완료 |
| P2-7 | 클립보드 자동 복사 | ✅ 완료 |

### 주요 변경 사항

- `core/cache.py`: save()/load() 영속 캐시
- `display/overlay.py`: 스냅샷 모드 (클릭 닫기, 자동 타이머)
- `core/ocr.py`: preview_preprocess() 미리보기
- `ui/ocr_preview.py`: **신규** — OCR 미리보기 대화상자
- `infra/config.py`: capture.regions 다중 영역, target_mode, auto_clipboard
- `core/detector.py`: 영역별 독립 해시 추적
- `core/pipeline.py`: 다중 영역 순회, 제외 영역 마스킹, 윈도우 캡처
- `core/capture.py`: capture_window(), mask_exclude_zones()
- `ui/region_editor.py`: **신규** — 드래그 이동/리사이즈/삭제 핸들
- `main.py`: 영역별 독립 오버레이/인디케이터, 편집 모드, 클립보드 복사
- `ui/settings.py`: 클립보드 자동 복사 체크박스
- `ui/tray.py`: 영역 편집, OCR 미리보기 메뉴

---

## 이전 세션 작업 내역 (2026-06-11)

### 수행한 작업

1. **사이드 패널 텍스트 잘림 수정**
   - 문제: 사이드 패널에서 번역 텍스트가 하단이 잘려서 표시됨
   - 시도 1: `_WrapLabel` 서브클래스 — `heightForWidth()` 구현 → **실패** (stylesheet 폰트를 fontMetrics가 인식 못함)
   - 시도 2: `QSizePolicy.Minimum` + `SetMinimumSize` 레이아웃 제약 → **실패** (Qt의 wordWrap 높이 계산이 근본적으로 불안정)
   - 시도 3: `QLabel` → `QTextBrowser` 교체 + `document().size().height()`로 직접 높이 계산 → **성공**
   - 교훈: QScrollArea 안에서 QLabel + wordWrap은 높이 계산이 신뢰할 수 없음. 긴 텍스트 표시에는 QTextBrowser 사용

2. **MORT 비교 분석**
   - MORT GitHub (https://github.com/killkimno/mort) 조사
   - MallangMollang 전체 코드베이스 기능 목록 작성
   - 두 프로젝트의 기능 차이점 분석 및 참고 사항 정리

3. **Phase 2 기능 계획 수립**
   - 사용자와 대화를 통해 7개 기능 확정 (P2-1 ~ P2-7)
   - 각 기능의 구현 방식, 동작 방식, 수정 대상 파일, 엣지 케이스 상세 논의

4. **문서화**
   - `docs/Phase2-Spec.md` 신규 작성 (552줄 상세 구현 스펙)
   - `docs/ROADMAP.md` 전면 업데이트
   - `docs/SESSION_HANDOFF.md` 전면 업데이트
   - `docs/PRD-MallangMollang.md` Phase 2/3 범위 현행화

---

## 사용자 결정사항 및 요청사항 (반드시 기억할 것)

### 폐기/스킵 결정

| 항목 | 결정 | 사유 (사용자 원문) |
|------|------|---------------------|
| 커서 추적 모드 | ❌ 폐기 | "작동도 제대로 안되구 굳이 필요한가 싶어. 나중에 좋은 방법이 떠오르면 그때나 만들자" |
| OpenAI/Claude/Ollama | ⏭ 스킵 | "어차피 내가 쓰는 기준으로는 버텍스 쓸거라서 필요 없다" |
| 온보딩 화면 | ⏭ 스킵 | "나만 쓴다는 가정하에선 쓸모 없다" |
| Gemini 검열 폴백 | ⏭ 스킵 | "어차피 나는 이걸 당장 검열이 걸릴만한 컨텐츠 번역에 쓸 생각이 없어서" |

### 기능별 사용자 요청사항

**다중 OCR 영역 (P2-4)**
- "실시간으로 한다면 여러 부분을 번역해야할 수도 있으니까" 필요
- 각 영역은 **일반 윈도우처럼 크기 조정 및 개별 종료(삭제)가 가능**해야 함
  - 원문: "일반 윈도우 처럼 크기 조정 및 개별 종료가 가능하게 했으면 좋겠어"

**OCR 제외 영역 (P2-6)**
- 윈도우 지정 캡처와 함께 구현하면 좋겠다고 함
  - 원문: "이거는 mort처럼 윈도우 지정 캡쳐 방식을 도입하면서 같이 추가하면 좋을 것 같아"

**영속 캐시 (P2-1)**
- 로그 저장과 비슷한 방식으로, 입력 텍스트가 이전과 동일하면 저장된 결과를 그대로 출력
  - 원문: "그냥 결과를 저장해서 입력 텍스트가 이전과 동일하다면 그대로 결과를 출력하는 방식"

**스냅샷 오버레이 정리 (P2-2)**
- 스냅샷 후 결과가 화면에 계속 남아서 가림
  - 원문: "스냅샷 번역을 진행하면 지정된 영역과 번역 결과가 계속 남아서 화면을 좀 가리거든"

### 개발 원칙 (사용자)

- **문서화 먼저**: "세부적인 사항들도 문서화 해서 작성해두고 작업 후에 오류가 나거나 해도 버그 수정과 차후 유지보수가 간편하도록"
- **작동하면 건드리지 않기**: 사이드 패널이 처음 원한 것과 조금 다르지만 잘 동작하니 건드리지 말자고 결정
- **코드 주석은 한국어로** (CLAUDE.md 참조)
- **개발 경험 초보 수준** — 설명은 쉽고 구체적으로, 코드에는 충분한 주석

---

## 사이드 패널 구현 기록 (유지보수용)

사이드 패널은 여러 시행착오를 거쳐 완성됨. 향후 수정 시 참고:

### 최종 구현 방식 (`display/panel.py`)

- **위젯**: `QTextBrowser` (QLabel 아님)
- **각 항목**: HTML로 타임스탬프 + 원문 + 번역문 구성
- **높이 계산**: `_fit_height()` — `document().setTextWidth(w)` → `document().size().height()` → `setFixedHeight()`
- **리사이즈 대응**: `resizeEvent()`에서 모든 항목 높이 재계산

### 주의사항

- `QLabel` + `setWordWrap(True)`는 `QScrollArea` 안에서 높이 계산이 불안정 → 절대 QLabel로 되돌리지 말 것
- `_WrapLabel(heightForWidth)` 접근법도 실패함 — stylesheet 폰트를 fontMetrics가 인식 못하는 문제
- `QSizePolicy.Minimum` + `SetMinimumSize`도 실패함 — Qt 레이아웃이 wordWrap 높이를 제대로 전파하지 않음
- QTextBrowser의 `setFrameShape(NoFrame)` + 배경색 스타일시트로 QFrame처럼 보이게 함

### 사이드 패널 표시 버그

- `main.py`의 `_on_settings_saved()`에서 `if self._running:` 조건이 있으면 설정 저장 후 패널이 안 뜸
- 이유: 설정 저장 시점에는 `_running=False` (번역이 중지된 상태)
- 수정: `_running` 조건 없이 `display.mode == "panel"`이면 바로 show

---

## MORT와의 차이점 요약 (참고용)

### MallangMollang만의 차별점 (유지해야 할 것)

1. **OCR 오류 교정 프롬프트** — "OCR 결과를 교정하고 번역해줘"
2. **문맥 기억** — 이전 3회 번역을 프롬프트에 포함
3. **Vision API 모드** — OCR 건너뛰고 이미지 직접 LLM 전달
4. **번역 프로필** — 장르/분위기/용어집 LLM 자동 생성
5. **pHash 변경 감지** — 화면 안 바뀌면 전체 파이프라인 스킵

### MORT에서 참고할 기능 (Phase 2에서 선별 도입)

- 다중 OCR 영역, OCR 제외 영역, 윈도우 지정 캡처
- 번역 결과 영속 저장
- 자동 색상 매핑 (Phase 3)
- TTS, 클립보드 연동

---

## 알려진 문제

### ✅ Phase 2에서 해결됨

1. ~~스냅샷 후 오버레이 잔류~~ → P2-2 완료
2. ~~단일 OCR 영역 제한~~ → P2-4 완료
3. ~~좌표 기반 캡처만 지원~~ → P2-6 완료
4. ~~캐시 비영속~~ → P2-1 완료

### ⚪ 의도적 미구현 (사용자 결정)

5. **OpenAI/Claude/Ollama 프로바이더** — Gemini Vertex만 사용
6. **온보딩 화면** — 개인 사용 목적
7. **커서 추적 모드** — 폐기 (실용성 부족)
8. **Gemini 검열 폴백** — 현재 불필요

---

## 다음 작업 계획

Phase 2 구현 완료. 다음 단계:

1. **Windows 환경 통합 테스트** — Phase2-Spec.md 체크리스트 기반 실제 동작 확인
2. **Phase 3 기능 검토** — 번역 결과 스트리밍, OCR 언어 프로필 연동, 번역 이력 내보내기 등
3. **UI/UX 개선** — 설정 UI에 윈도우 선택 드롭다운, 제외 영역 편집 UI 추가

---

## 프로젝트 문서 목록

| 문서 | 용도 |
|------|------|
| `docs/PRD-MallangMollang.md` | 기능 요구사항, 비기능 요구사항, MVP 스코프 |
| `docs/UserFlow-MallangMollang.md` | 시나리오별 태스크 플로우 + 인터랙션 플로우 |
| `docs/SystemDesign-MallangMollang.md` | 기술 스택, 모듈 구조, 인터페이스, 디렉토리 구조 |
| `docs/HANDOFF.md` | 기획 과정의 핵심 결정들과 이유 |
| `docs/ROADMAP.md` | 개발 로드맵, 완료/예정 작업 목록 |
| `docs/Phase2-Spec.md` | **Phase 2 상세 구현 스펙** (가장 중요) |
| `docs/SESSION_HANDOFF.md` | 세션 간 컨텍스트 전달 (이 문서) |

---

## 실행 방법

```bash
# 일반 실행
python -m mallangmollang.main

# 디버그 모드 (스크린샷에 오버레이 보임 — 주의: 피드백 루프 발생 가능)
python -m mallangmollang.main --debug

# OCR 진단 도구
python tools/ocr_inspect.py --image screenshot.png --lang jpn
python tools/ocr_inspect.py --region 100 200 800 400 --delay 3
```

---

## 다음 세션 시작 멘트

```
말랑몰랑 프로젝트 계속 진행하자.
아래 문서를 순서대로 읽어줘:
1. docs/SESSION_HANDOFF.md
2. docs/Phase2-Spec.md
브랜치: claude/gracious-rubin-w5nsyw
P2-1 (영속 캐시)부터 순서대로 진행하자.
```
