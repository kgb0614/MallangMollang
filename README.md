# 🫠 말랑몰랑 (MallangMollang)

AI 하이브리드 화면 번역 유틸리티 — Windows PC

## 뭐하는 프로그램?

화면의 텍스트를 OCR로 읽고, LLM이 오타를 교정하면서 자연스럽게 번역해주는 프로그램입니다.

## 기존 도구(MORT)와 뭐가 다른데?

- 🧠 OCR이 글자를 잘못 읽어도 LLM이 문맥으로 교정
- 📖 이전 대사를 기억해서 스토리가 이어지는 번역
- 🖱️ 마우스 커서로 웹/문서도 편하게 번역
- 👁️ Vision API로 OCR 없이 이미지 직접 번역 (선택)
- 🎮 게임별 톤과 용어를 사전 설정하는 번역 프로필

## 문서

- [PRD (기획서)](docs/PRD-MallangMollang.md)
- [User Flow](docs/UserFlow-MallangMollang.md)
- [System Design](docs/SystemDesign-MallangMollang.md)
- [Handoff (기획 맥락)](docs/HANDOFF.md)

## 기술 스택

Python 3.11+ · PyQt6 · Tesseract · httpx · Pillow · OpenCV

## 상태

🚧 Phase 1 (MVP) 개발 준비 중
