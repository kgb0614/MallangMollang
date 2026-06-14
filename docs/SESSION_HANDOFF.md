# 말랑몰랑 — 세션 핸드오프 문서

> 최종 업데이트: 2026-06-14
> 현재 브랜치: main

---

## 현재 구현 상태

### Core Pipeline

| 모듈 | 상태 | 비고 |
|------|------|------|
| `core/capture.py` | ✅ 완료 | 영역/윈도우 캡처, 제외 영역 마스킹, `get_window_rect()` |
| `core/detector.py` | ✅ 완료 | 이미지 해시 기반 변경 감지, 영역별 독립 해시 추적 |
| `core/cache.py` | ✅ 완료 | LRU 텍스트 캐시 + 디스크 영속 저장 (`save()`/`load()`) |
| `core/ocr.py` | ✅ 완료 | `extract_lines()` 문단 병합 + `preview_preprocess()` 미리보기 |
| `core/translator.py` | ✅ 완료 | 줄 단위 번역, 긴 문단(300자+) 개별, 프로필 hint 주입 |
| `core/pipeline.py` | ✅ 완료 | 다중 영역 순회, 줄 매핑 품질 검사, 진단 로그 |
| `core/profiles.py` | ✅ 완료 | 번역 프로필 관리 (저장/불러오기/LLM 자동 생성) |

### Providers

| 모듈 | 상태 | 비고 |
|------|------|------|
| `providers/base.py` | ✅ 완료 | `BaseProvider` 추상 인터페이스 |
| `providers/gemini.py` | ✅ 완료 | AI Studio + Vertex AI |
| `providers/openai.py` | ❌ 미구현 | 설정 UI만 있음 |
| `providers/claude.py` | ❌ 미구현 | 설정 UI만 있음 |
| `providers/ollama.py` | ❌ 미구현 | 설정 UI만 있음 |

### Display

| 모듈 | 상태 | 비고 |
|------|------|------|
| `display/overlay.py` | ✅ 완료 | QPainterPath 이중 외곽선, 자동 색상 지원, 스냅샷 모드 |
| `display/panel.py` | ✅ 완료 | QTextBrowser 히스토리 + 내보내기(txt/csv) |
| `display/area_indicator.py` | ✅ 완료 | 펄스 애니메이션, 캡처 제외 |
| `display/auto_color.py` | ✅ 완료 | 이미지 휘도 분석 → 대비 색상 반환 |
| `display/presets.py` | ✅ 완료 | 기본 프리셋 3종 |

### UI

| 모듈 | 상태 | 비고 |
|------|------|------|
| `ui/tray.py` | ✅ 완료 | 진단 복사, OCR 미리보기 메뉴 |
| `ui/settings.py` | ✅ 완료 | 7탭 + 자동 색상 체크박스 + 윈도우 선택 |
| `ui/control_panel.py` | ✅ 완료 | 플로팅 패널 (시작/중지/영역/설정) |
| `ui/region_selector.py` | ✅ 완료 | |
| `ui/region_editor.py` | ✅ 완료 | 리사이즈/이동/삭제/개별 번역 핸들 |
| `ui/ocr_preview.py` | ✅ 완료 | 3장 이미지 + OCR 텍스트 |
| `ui/toast.py` | ✅ 완료 | 4단계 레벨 |

### Infrastructure

| 모듈 | 상태 | 비고 |
|------|------|------|
| `infra/config.py` | ✅ 완료 | 싱글톤, 점 경로, 다중 영역, 레거시 마이그레이션 |
| `infra/hotkeys.py` | ✅ 완료 | 글로벌 단축키, 재로드 지원 |
| `infra/crypto.py` | ✅ 완료 | Fernet 암호화, 머신 고유 키, 자동 마이그레이션 |

---

## 사용자 결정사항 (반드시 기억할 것)

### 폐기/스킵 결정

| 항목 | 결정 | 사유 |
|------|------|------|
| 커서 추적 모드 | ❌ 폐기 | 실용성 부족, 버그 우려 |
| 번역 결과 스트리밍 | ❌ 스킵 | "통짜 번역을 원하지 한줄씩 원하는 경우는 거의 없다" |
| OCR 언어 프로필 연동 | ❌ 스킵 | 필요성 낮음 |
| LLM 추론 파라미터 설정 | ❌ 스킵 | 현재 추론 모델 비활성화 불가 |
| OpenAI/Claude/Ollama | ⏭ 나중에 | "버텍스만 쓸 거라서. 배포할 때나" |
| 온보딩 화면 | ⏭ 나중에 | "나만 쓴다는 가정하에선 쓸모 없다" |

### 개발 원칙

- **문서화 먼저**: 세부사항 문서화 후 작업
- **작동하면 건드리지 않기**: 잘 동작하면 리팩토링하지 않음
- **메인 브랜치에 합치기**: feature branch → main 머지 → main 푸시
- **한 번에 하나씩**: 기능 구현은 step by step
- **코드 주석 한국어** (CLAUDE.md 참조)

---

## 다음 작업 계획

### Phase 3 — 마무리 기능 (2개)

1. **사용자 번역 DB**: 원문→번역 쌍 등록 → LLM 전 완전 일치 치환 + 부분 일치 프롬프트 강제
2. **OCR 이미지 전처리 옵션**: 밝기/대비/그레이스케일 슬라이더 (설정 > 캡처 탭)

이후 기능 구현은 마무리하고, UI/UX 개편 및 안정화에 집중할 예정.

---

## 이후 과제 (UI/UX 개편 시)

- 트레이/설정/컨트롤 패널 간 기능 배치 재정비
- 스타일 프리셋 커스텀 저장 UI
- 번역 패널 등 각 화면에 부가 설정 접근성 추가

---

## 프로젝트 문서 목록

| 문서 | 용도 |
|------|------|
| `docs/PRD-MallangMollang.md` | 기능 요구사항, 비기능 요구사항, MVP 스코프 |
| `docs/UserFlow-MallangMollang.md` | 시나리오별 태스크 플로우 (일부 구식) |
| `docs/SystemDesign-MallangMollang.md` | 기술 스택, 모듈 구조, 디렉토리 구조 |
| `docs/HANDOFF.md` | 기획 과정의 핵심 결정들과 이유 |
| `docs/ROADMAP.md` | 개발 로드맵, 완료/예정 작업 목록 |
| `docs/Phase2-Spec.md` | Phase 2 상세 구현 스펙 (역사 문서) |
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
