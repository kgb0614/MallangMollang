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
| `core/cache.py` | ✅ 완료 | LRU 텍스트 캐시 |
| `core/ocr.py` | ✅ 완료 | `extract_lines()` 문단 병합 + 목록 마커 분리 |
| `core/translator.py` | ✅ 완료 | 줄 단위 번역, 긴 문단(300자+) 개별, 프로필 hint 주입 |
| `core/pipeline.py` | ✅ 완료 | `LineTranslation` 줄 단위 흐름 + 진단 로그 + OCR 신뢰도 필터(conf<30) |
| `core/profiles.py` | ✅ 완료 | 번역 프로필 관리 (저장/불러오기/LLM 자동 생성) |

### Providers

| 모듈 | 상태 | 비고 |
|------|------|------|
| `providers/base.py` | ✅ 완료 | `BaseProvider` 추상 인터페이스 |
| `providers/gemini.py` | ✅ 완료 | AI Studio + Vertex AI, `finishReason` 로깅 |
| `providers/openai.py` | ❌ 미구현 | 설정 UI만 있음, 호출 시 에러 |
| `providers/claude.py` | ❌ 미구현 | 동일 |
| `providers/ollama.py` | ❌ 미구현 | 동일 |

### Display

| 모듈 | 상태 | 비고 |
|------|------|------|
| `display/overlay.py` | ✅ 완료 | line/block 모드, 폰트 자동 축소(최소 8pt) + 박스 확장 |
| `display/area_indicator.py` | ✅ 완료 | 펄스 애니메이션, `SetWindowDisplayAffinity` 캡처 제외 |
| `display/presets.py` | ✅ 완료 | 기본 프리셋 3종 |

### UI

| 모듈 | 상태 | 비고 |
|------|------|------|
| `ui/tray.py` | ✅ 완료 | 진단 정보 복사 메뉴 포함 |
| `ui/settings.py` | ✅ 완료 | 단축키 탭 + 번역 프로필 탭 포함 |
| `ui/region_selector.py` | ✅ 완료 | |
| `ui/toast.py` | ✅ 완료 | 에러 상세 메시지 표시 |
| `ui/onboarding.py` | ❌ 미구현 | |

### Infrastructure

| 모듈 | 상태 | 비고 |
|------|------|------|
| `infra/config.py` | ✅ 완료 | |
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
| F1-2 커서 추적 캡처 | ⚠️ 부분 | `capture.capture_around_cursor()` 존재, UI 미연결 |
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
| F7-1 오버레이 모드 | ✅ | `display/overlay.py` (line + block) |
| F8-1 글로벌 단축키 | ✅ | `infra/hotkeys.py` |
| F8-2 설정 UI | ✅ | `ui/settings.py` |
| F8-3 설정 저장 | ✅ | `infra/config.py` (JSON) |

---

## 최근 세션 작업 이력 (2026-06-11)

### 진단 도구

1. **번역 로그 파일** — OCR 입력 + 번역 출력을 `translation_log.txt`에 자동 저장
2. **진단 정보 클립보드 복사** — 트레이 메뉴 "진단 정보 복사"로 마지막 번역 정보 복사
3. **Gemini finishReason 로깅** — 토큰 한도 도달 등 모델 응답 상태를 콘솔에 출력

### OCR 개선

4. **인접 줄 자동 병합** — 같은 문단의 줄이 Tesseract에서 분리된 경우 자동 합침
5. **목록 마커 분리** — `•`, `-`, `+`, `©`(불릿 오인식) 등으로 시작하는 줄은 병합에서 제외
6. **`_split_on_list_markers()`** — Tesseract 문단 그룹 내에서도 불릿 항목 개별 분리

### 번역 엔진 개선

7. **긴 문단 개별 번역** — 300자 이상 줄은 `translate_text()`로 개별 번역 (번호 형식 회피)
8. **max_tokens 동적 계산** — 입력 길이에 비례해 토큰 한도 자동 조정 (`char_count * 8 + 512`)
9. **`_parse_line_response` 부분 매치** — LLM이 일부 줄만 반환해도 N| 마커 제거
10. **프롬프트 강화** — "긴 줄은 끝까지 완전 번역, 절대 요약 금지" 지시 추가

### 오버레이 개선

11. **폰트 자동 축소** — OCR 박스에 맞을 때까지 1pt씩 축소 (최소 8pt)
12. **박스 높이 자동 확장** — 최소 폰트에서도 안 맞으면 배경 박스를 텍스트에 맞게 늘림

### 인프라 수정

13. **mss 스레드 안전** — 매 캡처마다 `with mss.mss()` 사용 (핸들 재사용 제거)
14. **asyncio 이벤트 루프** — 스냅샷마다 pipeline 재생성으로 Event loop closed 해결

### OCR 신뢰도 필터링

15. **conf < 30 줄 스킵** — `pipeline.py`에서 번역 전 저신뢰도 OCR 결과 자동 제외

### 번역 프로필

16. **`core/profiles.py`** — `TranslationProfile` 데이터 + `ProfileManager` (저장/불러오기/LLM 자동 생성)
17. **설정 UI 프로필 탭** — 키워드 자동 생성, 수동 편집, 용어집 테이블, 저장/삭제
18. **시스템 프롬프트 주입** — `translator.py`의 3개 빌더 모두에 `【번역 맥락 정보】` 블록 추가
19. **`main.py` 연결** — `ProfileManager` 생성, 활성 프로필 적용, 설정 저장 시 재적용

---

## 알려진 문제

### 🔴 해결 필요

1. **OpenAI/Claude/Ollama 프로바이더 미구현**
   - 설정에서 선택하면 에러 발생 (현재 Gemini만 동작)

### 🟡 개선 사항

3. **커서 추적 모드 UI 미연결**
   - `capture.capture_around_cursor()` 구현됨, 트레이/단축키에서 활성화 불가

4. **온보딩 화면 미구현**
   - 최초 실행 시 API 키 입력 가이드 없음

5. **사이드 패널 모드 미구현**
   - `display/panel.py` 존재하지만 빈 파일 또는 미연결

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

## 다음 작업 우선순위

### Phase 2 — 핵심 기능

1. **사이드 패널 모드** — `display/panel.py` (오버레이 대안, 번역 히스토리 표시)

### Phase 3 — 나중에

2. **커서 추적 모드 UI 연결** — 트레이 메뉴에서 모드 전환
3. **온보딩 화면** — 최초 실행 시 프로바이더 + API 키 설정 가이드
4. **OpenAI/Claude/Ollama 프로바이더** — 현재 Gemini만으로 충분, 필요 시 추가
5. **스타일 프리셋 저장/불러오기 UI**
6. **Steam 메타데이터 연동** — 번역 프로필 2단계
7. **배포 패키징** — PyInstaller/Nuitka

---

## 다음 세션 시작 멘트

```
말랑몰랑 프로젝트 계속 진행하자. docs/SESSION_HANDOFF.md 읽어줘.
브랜치: claude/gracious-rubin-w5nsyw
```
