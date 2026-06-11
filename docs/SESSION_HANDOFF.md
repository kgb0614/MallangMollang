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

## Phase 2 작업 이력 (2026-06-11)

### 완료

20. **API 키 암호화** — `infra/crypto.py` Fernet 대칭 암호화, PBKDF2 키 유도, ENC: 접두어
21. **Config 암호화 연동** — `config.py` save/load 시 자동 암호화/복호화, 평문 자동 마이그레이션
22. **커서 추적 모드** — 구현 후 테스트, 실용성 부족으로 `git revert`로 폐기
23. **사이드 패널** — `display/panel.py` QTextBrowser 기반 번역 히스토리, 표시 모드 전환 UI
24. **사이드 패널 표시 버그 수정** — `_on_settings_saved()`에서 `_running` 조건 제거
25. **사이드 패널 텍스트 잘림 수정** — QLabel → QTextBrowser 교체, `_fit_height()` 높이 계산

### 이전 작업 (Phase 1)

1~19번 항목은 Phase 1에서 완료. 진단 도구, OCR 개선, 번역 엔진 개선, 오버레이 개선, 인프라 수정, 번역 프로필 등.

---

## 알려진 문제

### 🟡 개선 사항

1. **스냅샷 후 오버레이 잔류** — 스냅샷 번역 후 결과가 화면에 계속 남음 (P2-2에서 해결 예정)
2. **단일 OCR 영역 제한** — 1개 영역만 지정 가능 (P2-4에서 해결 예정)
3. **좌표 기반 캡처만 지원** — 창 이동 시 영역 어긋남 (P2-6에서 해결 예정)

### ⚪ 의도적 미구현 (현재 불필요)

4. **OpenAI/Claude/Ollama 프로바이더** — 개인 사용 시 Gemini Vertex로 충분
5. **온보딩 화면** — 개인 사용 목적
6. **커서 추적 모드** — 폐기 (실용성 부족)

---

## 다음 작업 우선순위

> 상세 스펙: `docs/Phase2-Spec.md` 참조

### Phase 2 — 실사용 편의성

| 순서 | ID | 기능 | 난이도 | 예상 시간 |
|------|----|------|--------|-----------|
| 1 | P2-1 | 영속 캐시 (디스크 저장) | 하 | 1~2시간 |
| 2 | P2-2 | 스냅샷 오버레이 정리 | 하 | 1시간 |
| 3 | P2-3 | OCR 전처리 미리보기 | 하 | 2~3시간 |
| 4 | P2-4 | 다중 OCR 영역 | 중상 | 6~8시간 |
| 5 | P2-5 | 영역 크기 조정·삭제 UI | 중 | 3~4시간 |
| 6 | P2-6 | 윈도우 지정 캡처 + 제외 영역 | 중 | 4~5시간 |
| 7 | P2-7 | 클립보드 자동 복사 | 하 | 30분 |

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
말랑몰랑 프로젝트 계속 진행하자. docs/SESSION_HANDOFF.md 읽어줘.
브랜치: claude/gracious-rubin-w5nsyw
다음 작업: docs/Phase2-Spec.md의 P2-1 (영속 캐시)부터 진행.
```
