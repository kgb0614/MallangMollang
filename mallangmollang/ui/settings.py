"""
설정 창 모듈
API 키, 언어, 캡처, 표시, 번역 설정을 탭 구조로 제공합니다.
"""

from PyQt6.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QComboBox, QSpinBox, QCheckBox,
    QPushButton, QGroupBox, QFormLayout, QSlider, QColorDialog,
    QMessageBox, QDoubleSpinBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from mallangmollang.infra.config import Config


class SettingsWindow(QDialog):
    """
    설정 창.

    탭 구성:
      - 프로바이더: API 키, 모델 선택, 연결 테스트
      - 언어: 원문/번역 언어, OCR 언어
      - 캡처: 주기, 변경 감지 민감도
      - 번역: 문맥 기억 수, Vision 모드
      - 표시: 오버레이 프리셋 선택

    설정 저장 시 settings_saved 시그널을 발생시킵니다.
    """

    settings_saved = pyqtSignal()   # 설정 저장 완료 시

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("말랑몰랑 설정")
        self.setMinimumWidth(480)
        self.setModal(True)

        self._build_ui()
        self._load_values()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_provider_tab(), "프로바이더")
        self._tabs.addTab(self._build_language_tab(), "언어")
        self._tabs.addTab(self._build_capture_tab(), "캡처")
        self._tabs.addTab(self._build_translation_tab(), "번역")
        self._tabs.addTab(self._build_display_tab(), "표시")
        layout.addWidget(self._tabs)

        # 하단 버튼
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        save_btn = QPushButton("저장")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    # ── 탭별 UI 구성 ──

    def _build_provider_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("LLM 프로바이더")
        form = QFormLayout(group)

        # 활성 프로바이더 선택
        self._provider_combo = QComboBox()
        self._provider_combo.addItems(["gemini", "openai", "claude", "ollama"])
        form.addRow("프로바이더:", self._provider_combo)

        # Gemini 설정
        gemini_group = QGroupBox("Gemini 설정")
        gemini_form = QFormLayout(gemini_group)

        self._gemini_key = QLineEdit()
        self._gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._gemini_key.setPlaceholderText("AI Studio API 키")
        gemini_form.addRow("API 키:", self._gemini_key)

        self._gemini_model = QComboBox()
        self._gemini_model.addItems([
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ])
        self._gemini_model.setEditable(True)
        gemini_form.addRow("모델:", self._gemini_model)

        self._gemini_endpoint = QComboBox()
        self._gemini_endpoint.addItems(["ai_studio", "vertex"])
        gemini_form.addRow("엔드포인트:", self._gemini_endpoint)

        # 연결 테스트 버튼
        test_btn = QPushButton("연결 테스트")
        test_btn.clicked.connect(self._test_connection)
        gemini_form.addRow("", test_btn)

        layout.addWidget(group)
        layout.addWidget(gemini_group)
        layout.addStretch()
        return widget

    def _build_language_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("언어 설정")
        form = QFormLayout(group)

        self._source_lang = QComboBox()
        self._source_lang.addItems(["auto", "en", "ja", "zh", "zh-CN", "zh-TW", "fr", "de", "es"])
        form.addRow("원문 언어:", self._source_lang)

        self._target_lang = QComboBox()
        self._target_lang.addItems(["ko", "en", "ja", "zh", "fr", "de", "es"])
        form.addRow("번역 언어:", self._target_lang)

        self._ocr_lang = QComboBox()
        self._ocr_lang.addItems(["eng", "jpn", "chi_sim", "chi_tra", "kor", "eng+jpn"])
        self._ocr_lang.setEditable(True)
        form.addRow("OCR 언어:", self._ocr_lang)

        layout.addWidget(group)
        layout.addStretch()
        return widget

    def _build_capture_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("캡처 설정")
        form = QFormLayout(group)

        self._interval_ms = QSpinBox()
        self._interval_ms.setRange(500, 10000)
        self._interval_ms.setSingleStep(100)
        self._interval_ms.setSuffix(" ms")
        form.addRow("캡처 주기:", self._interval_ms)

        self._hash_threshold = QSpinBox()
        self._hash_threshold.setRange(1, 20)
        self._hash_threshold.setSuffix(" (낮을수록 민감)")
        form.addRow("변경 감지 임계값:", self._hash_threshold)

        layout.addWidget(group)
        layout.addStretch()
        return widget

    def _build_translation_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("번역 설정")
        form = QFormLayout(group)

        self._context_count = QSpinBox()
        self._context_count.setRange(0, 10)
        self._context_count.setSuffix(" 회")
        form.addRow("문맥 기억 수:", self._context_count)

        self._vision_mode = QCheckBox("Vision API 모드 (OCR 단계 건너뜀)")
        form.addRow("", self._vision_mode)

        self._cache_max_size = QSpinBox()
        self._cache_max_size.setRange(10, 1000)
        form.addRow("캐시 최대 항목:", self._cache_max_size)

        layout.addWidget(group)
        layout.addStretch()
        return widget

    def _build_display_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("표시 설정")
        form = QFormLayout(group)

        self._display_mode = QComboBox()
        self._display_mode.addItems(["overlay", "panel"])
        form.addRow("표시 모드:", self._display_mode)

        self._active_preset = QComboBox()
        self._active_preset.addItems(["기본", "어두운 게임용", "밝은 배경용"])
        form.addRow("오버레이 프리셋:", self._active_preset)

        layout.addWidget(group)
        layout.addStretch()
        return widget

    # ── 값 로드/저장 ──

    def _load_values(self):
        """Config에서 현재 설정값을 UI에 반영합니다."""
        c = self.config

        # 프로바이더 탭
        provider = c.get("provider.active", "gemini")
        idx = self._provider_combo.findText(provider)
        if idx >= 0:
            self._provider_combo.setCurrentIndex(idx)

        self._gemini_key.setText(c.get("provider.gemini.api_key", ""))
        model = c.get("provider.gemini.model", "gemini-2.0-flash")
        midx = self._gemini_model.findText(model)
        if midx >= 0:
            self._gemini_model.setCurrentIndex(midx)
        else:
            self._gemini_model.setCurrentText(model)

        endpoint = c.get("provider.gemini.endpoint", "ai_studio")
        eidx = self._gemini_endpoint.findText(endpoint)
        if eidx >= 0:
            self._gemini_endpoint.setCurrentIndex(eidx)

        # 언어 탭
        src = c.get("language.source", "auto")
        sidx = self._source_lang.findText(src)
        if sidx >= 0:
            self._source_lang.setCurrentIndex(sidx)

        tgt = c.get("language.target", "ko")
        tidx = self._target_lang.findText(tgt)
        if tidx >= 0:
            self._target_lang.setCurrentIndex(tidx)

        ocr = c.get("language.ocr_lang", "eng")
        oidx = self._ocr_lang.findText(ocr)
        if oidx >= 0:
            self._ocr_lang.setCurrentIndex(oidx)
        else:
            self._ocr_lang.setCurrentText(ocr)

        # 캡처 탭
        self._interval_ms.setValue(c.get("capture.interval_ms", 1500))
        self._hash_threshold.setValue(c.get("detector.hash_threshold", 5))

        # 번역 탭
        self._context_count.setValue(c.get("translation.context_count", 3))
        self._vision_mode.setChecked(c.get("translation.vision_mode", False))
        self._cache_max_size.setValue(c.get("cache.max_size", 100))

        # 표시 탭
        dm = c.get("display.mode", "overlay")
        dmidx = self._display_mode.findText(dm)
        if dmidx >= 0:
            self._display_mode.setCurrentIndex(dmidx)

        preset = c.get("display.active_preset", "기본")
        pidx = self._active_preset.findText(preset)
        if pidx >= 0:
            self._active_preset.setCurrentIndex(pidx)

    def _save(self):
        """UI 값을 Config에 저장하고 창을 닫습니다."""
        c = self.config

        # 프로바이더
        c.set("provider.active", self._provider_combo.currentText())
        c.set("provider.gemini.api_key", self._gemini_key.text())
        c.set("provider.gemini.model", self._gemini_model.currentText())
        c.set("provider.gemini.endpoint", self._gemini_endpoint.currentText())

        # 언어
        c.set("language.source", self._source_lang.currentText())
        c.set("language.target", self._target_lang.currentText())
        c.set("language.ocr_lang", self._ocr_lang.currentText())

        # 캡처
        c.set("capture.interval_ms", self._interval_ms.value())
        c.set("detector.hash_threshold", self._hash_threshold.value())

        # 번역
        c.set("translation.context_count", self._context_count.value())
        c.set("translation.vision_mode", self._vision_mode.isChecked())
        c.set("cache.max_size", self._cache_max_size.value())

        # 표시
        c.set("display.mode", self._display_mode.currentText())
        c.set("display.active_preset", self._active_preset.currentText())

        self.settings_saved.emit()
        self.accept()

    def _test_connection(self):
        """현재 입력된 API 키로 연결을 테스트합니다."""
        import asyncio

        api_key = self._gemini_key.text().strip()
        if not api_key:
            QMessageBox.warning(self, "연결 테스트", "API 키를 먼저 입력해주세요.")
            return

        from mallangmollang.providers.gemini import GeminiProvider
        provider = GeminiProvider(
            api_key=api_key,
            model=self._gemini_model.currentText(),
            endpoint=self._gemini_endpoint.currentText(),
        )

        try:
            loop = asyncio.new_event_loop()
            ok = loop.run_until_complete(provider.test_connection())
            loop.run_until_complete(provider.close())
            loop.close()
        except Exception as e:
            QMessageBox.critical(self, "연결 실패", f"연결 중 오류가 발생했습니다:\n{e}")
            return

        if ok:
            QMessageBox.information(self, "연결 테스트", "연결에 성공했습니다! ✓")
        else:
            QMessageBox.warning(self, "연결 실패", "API 키 또는 설정을 확인해주세요.")
