# 말랑몰랑 — 세션 핸드오프 문서

> 작성일: 2026-06-09  
> 현재 브랜치: main

---

## 현재 상태 요약

Unit 1~6 구현 완료. 프로그램이 **작동은 하지만** UI/UX와 핵심 기능에 치명적인 문제가 있어 전면 개선이 필요한 상태.

### 작동 확인된 것
- Vertex AI (서비스 계정 JSON) / AI Studio (API 키) 인증
- 이미지 해시 변경 감지 → 변경 없으면 API 호출 스킵
- OCR 텍스트 캐시 → 동일 텍스트면 API 호출 스킵
- 번역 파이프라인 (캡처 → OCR → LLM → 결과 콜백)
- 설정 창 (프로바이더별 동적 UI 전환, Vertex AI JSON 입력)

---

## 알려진 버그 / 문제점

### 🔴 치명적

1. **오버레이가 진짜 오버레이가 아님**
   - 현재: 번역 결과를 별도 윈도우에 띄움 (MORT의 "Dark" 모드 수준)
   - 목표: 캡처 영역 위에 반투명 창을 정확히 겹쳐서 원문을 덮어씌우는 방식
   - 파일: `mallangmollang/display/overlay.py`

2. **선택한 번역 영역이 어디인지 표시 안 됨**
   - 영역 선택 후 어디가 번역되고 있는지 알 방법이 없음
   - 스크롤/이동하면 영역을 잃어버림
   - MORT는 `OcrAreaForm.cs`에서 파란색 테두리로 영역을 항상 표시함
   - 구현 위치: 새 모듈 `mallangmollang/display/area_indicator.py` 필요

3. **일본어 OCR 오류**
   - 설정 OCR 언어가 `eng`이면 일본어를 영어로 읽어서 쓰레기 텍스트 출력
   - 단기 해결: 설정에서 OCR 언어를 `jpn`으로 변경
   - 근본 해결: 언어 자동 감지 또는 Vision 모드 사용

### 🟡 중요

4. **`app.first_run` 저장 안 됨**
   - `run()`에서 `config.set("app.first_run", False)` 후 save() 미호출
   - 설정 저장 시 같이 저장되긴 하지만 비정상 흐름

5. **설정 저장 후 번역 자동 시작 흐름 불안정**
   - 저장 → `_start_translation()` → 영역 없으면 `_on_region_select()` 호출
   - 영역 선택 후 자동으로 번역 시작되는지 확인 필요

6. **캡처 영역이 고정 좌표**
   - 창을 이동하거나 스크롤하면 엉뚱한 곳을 번역함
   - MORT는 특정 윈도우에 attach하는 모드 있음 (Phase 2 기능)

---

## MORT 분석 결과 (레퍼런스)

GitHub: https://github.com/killkimno/mort (C# / Windows Forms)

### 참고할 핵심 아이디어

| MORT 기능 | 구현 방식 | 우리 적용 방안 |
|-----------|-----------|---------------|
| 영역 표시 | `OcrAreaForm.cs` — 파란색 테두리 창, `WDA_EXCLUDEFROMCAPTURE`로 자체 창은 캡처 제외 | `AreaIndicatorWindow` — 항상 최상위, 캡처 영역에 정확히 겹치는 테두리 창 |
| Layer 오버레이 | `UpdateLayeredWindow` API + GDI+ 비트맵 렌더링 | PyQt6 `WA_TranslucentBackground` + `WindowStaysOnTopHint` + 캡처 영역과 동일 위치/크기로 `move()` |
| Over 오버레이 | OCR 단어 위치에 맞춰 번역 덮어씌움 | Phase 2 — Vision 모드와 결합 가능 |
| 변경 감지 | OCR 텍스트 비교 (우리: 이미지 해시 + 텍스트 캐시로 더 발전) | ✅ 이미 구현됨 |
| 다중 언어 OCR | 엔진별 선택 | ✅ 설정에서 선택 가능 (jpn, chi_sim 등) |

---

## 다음 세션 작업 계획 (우선순위 순)

### Phase A — 당장 고쳐야 할 것 (1~2 세션)

#### A-1. 캡처 영역 테두리 표시 (AreaIndicator)
- `mallangmollang/display/area_indicator.py` 신규 생성
- `QWidget` + `FramelessWindowHint` + `WindowStaysOnTopHint`
- 캡처 영역과 동일한 위치/크기, 테두리만 그리고 내부는 투명
- `WA_TransparentForMouseEvents` — 클릭 투과
- `SetWindowDisplayAffinity` 또는 mss 캡처 영역 제외 처리 (자체 창이 캡처되지 않도록)
- 번역 활성 시 표시, 비활성 시 숨김

#### A-2. 진짜 오버레이 구현
- `overlay.py` 수정: 위치를 캡처 영역 위에 정확히 겹치도록 변경
- 현재: 캡처 영역 아래에 표시 (`y + h + 4`)
- 목표: 캡처 영역과 동일한 `(x, y, w, h)`에 반투명 배경으로 겹쳐서 표시
- 창 크기를 캡처 영역 크기에 맞춤 (`setFixedSize(w, h)`)
- 텍스트를 영역 안에서 `AlignLeft | AlignTop` 또는 `AlignCenter`로 렌더링

#### A-3. OCR 언어 자동 감지 or Vision 모드 기본 활성화
- 일본어 사이트용으로 Vision 모드 사용 권장
- 또는 설정 UI에서 OCR 언어 선택을 더 쉽게 (언어명으로 표시)

### Phase B — 중요한 개선 (이후 세션)

#### B-1. 번역 상태 표시
- 트레이 아이콘 색상 (현재 구현됨) 외에 영역 테두리 색상으로도 상태 표시
  - 대기 중: 파란색
  - 번역 중: 노란색 (깜빡임)
  - 오류: 빨간색

#### B-2. 설정 UX 개선
- 설정 저장 후 자동으로 영역 선택 안내 (현재 불안정)
- OCR 언어 콤보박스에 언어 이름 표시 (`jpn` → `일본어 (jpn)`)
- 캐시 최대 항목 설명 추가 ("번역 기억 항목 수, 많을수록 메모리 사용 증가")

#### B-3. 오류 처리 개선
- API 오류 시 트레이 알림으로 원인 표시 (현재 콘솔에만 출력)
- OCR 결과가 쓰레기일 때 (신뢰도 낮음) 번역 건너뜀

### Phase C — Phase 2 기능 (PRD 기준)

- 커서 추적 모드
- 번역 프로필 (게임용/문서용 톤 설정)
- 특정 창 attach 모드
- Over 모드 (OCR 위치 기반 번역 오버레이)

---

## 주요 파일 위치

```
mallangmollang/
├── main.py                    # 앱 진입점, 컴포넌트 조립
├── infra/config.py            # 설정 싱글톤, DEFAULT_CONFIG
├── core/pipeline.py           # 캡처→OCR→번역 파이프라인
├── core/capture.py            # mss 화면 캡처
├── core/detector.py           # 이미지 해시 변경 감지
├── core/cache.py              # LRU 번역 캐시
├── core/ocr.py                # Tesseract OCR
├── core/translator.py         # LLM 번역 (문맥 포함)
├── providers/gemini.py        # Gemini AI Studio + Vertex AI
├── display/overlay.py         # 번역 결과 표시 창 ← A-2 수정 대상
├── display/presets.py         # 오버레이 스타일 프리셋
├── ui/tray.py                 # 시스템 트레이 아이콘/메뉴
├── ui/settings.py             # 설정 창 (탭 구조)
└── ui/region_selector.py      # 캡처 영역 선택 UI
```

---

## 다음 세션 시작 멘트

```
말랑몰랑 프로젝트 계속 진행하자. docs/SESSION_HANDOFF.md 읽어줘.
오늘은 Phase A 작업을 진행할 거야:
1. 캡처 영역 테두리 표시 (AreaIndicator) 구현
2. 오버레이를 캡처 영역 위에 정확히 겹치도록 수정
main 브랜치에서 작업해줘.
```
