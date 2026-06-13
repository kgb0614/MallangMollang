"""
설정 창 모듈
API 키, 언어, 캡처, 표시, 번역 설정을 탭 구조로 제공합니다.
"""

from PyQt6.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QComboBox, QSpinBox, QCheckBox,
    QPushButton, QGroupBox, QFormLayout,
    QMessageBox, QStackedWidget, QTextEdit, QFileDialog, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
)
from PyQt6.QtCore import pyqtSignal

from mallangmollang.infra.config import Config
from mallangmollang.core.profiles import ProfileManager, TranslationProfile


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

    def __init__(self, config: Config, profile_manager: ProfileManager | None = None, parent=None):
        super().__init__(parent)
        self.config = config
        self._profile_manager = profile_manager or ProfileManager()
        self.setWindowTitle("말랑몰랑 설정")
        self.setMinimumWidth(520)
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
        self._tabs.addTab(self._build_profile_tab(), "번역 프로필")
        self._tabs.addTab(self._build_hotkeys_tab(), "단축키")
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

        # 활성 프로바이더 선택
        top_group = QGroupBox("LLM 프로바이더")
        top_form = QFormLayout(top_group)
        self._provider_combo = QComboBox()
        self._provider_combo.addItems(["gemini", "openai", "claude", "ollama"])
        top_form.addRow("프로바이더:", self._provider_combo)
        layout.addWidget(top_group)

        # 프로바이더별 설정 패널 (QStackedWidget)
        self._provider_stack = QStackedWidget()
        self._provider_stack.addWidget(self._build_gemini_panel())   # 0: gemini
        self._provider_stack.addWidget(self._build_openai_panel())   # 1: openai
        self._provider_stack.addWidget(self._build_claude_panel())   # 2: claude
        self._provider_stack.addWidget(self._build_ollama_panel())   # 3: ollama
        layout.addWidget(self._provider_stack)

        layout.addStretch()

        # 프로바이더 변경 시 스택 페이지 전환
        self._provider_combo.currentIndexChanged.connect(
            self._provider_stack.setCurrentIndex
        )

        return widget

    def _build_gemini_panel(self) -> QWidget:
        """Gemini 설정 패널 — AI Studio / Vertex AI 모드 전환 지원"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Gemini 설정")
        form = QFormLayout(group)

        self._gemini_model = QComboBox()
        self._gemini_model.setEditable(True)
        self._gemini_model.setToolTip(
            "AI Studio와 Vertex AI는 모델 ID가 다를 수 있습니다.\n"
            "목록에 없으면 직접 입력하세요."
        )
        form.addRow("모델:", self._gemini_model)

        self._gemini_endpoint = QComboBox()
        self._gemini_endpoint.addItems(["ai_studio", "vertex"])
        form.addRow("엔드포인트:", self._gemini_endpoint)

        # 엔드포인트에 따라 모델 목록을 교체
        self._gemini_endpoint.currentTextChanged.connect(self._update_gemini_model_list)

        layout.addWidget(group)

        # AI Studio 전용 패널
        self._gemini_ais_widget = QWidget()
        ais_form = QFormLayout(self._gemini_ais_widget)
        ais_form.setContentsMargins(0, 0, 0, 0)
        ais_group = QGroupBox("AI Studio 인증")
        ais_inner = QFormLayout(ais_group)
        self._gemini_key = QLineEdit()
        self._gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._gemini_key.setPlaceholderText("AI Studio API 키를 입력하세요")
        ais_inner.addRow("API 키:", self._gemini_key)
        ais_form.addRow(ais_group)
        layout.addWidget(self._gemini_ais_widget)

        # Vertex AI 전용 패널
        self._gemini_vertex_widget = QWidget()
        vtx_layout = QVBoxLayout(self._gemini_vertex_widget)
        vtx_layout.setContentsMargins(0, 0, 0, 0)
        vtx_group = QGroupBox("Vertex AI 인증")
        vtx_form = QFormLayout(vtx_group)

        self._vertex_region = QComboBox()
        self._vertex_region.addItems([
            "global",
            "us-central1",
            "us-east1",
            "us-east4",
            "us-west1",
            "us-west4",
            "europe-west1",
            "europe-west2",
            "europe-west4",
            "asia-northeast1",
            "asia-northeast3",
            "asia-southeast1",
        ])
        self._vertex_region.setEditable(True)
        self._vertex_region.setToolTip("global: 일부 신규 모델 전용 / 특정 리전: 데이터 레지던시 필요 시")
        vtx_form.addRow("리전:", self._vertex_region)

        # 서비스 계정 JSON — 파일 선택 버튼
        # project_id 등 나머지 정보는 JSON에서 자동 추출됩니다
        sa_label = QLabel("서비스 계정 JSON을 붙여넣거나 파일을 선택하세요\n(project_id, client_email, private_key 등은 JSON에서 자동 추출됩니다)")
        vtx_form.addRow(sa_label)

        self._vertex_sa_json = QTextEdit()
        self._vertex_sa_json.setPlaceholderText('{"type": "service_account", "project_id": "...", ...}')
        self._vertex_sa_json.setMinimumHeight(140)
        vtx_form.addRow(self._vertex_sa_json)

        sa_browse_btn = QPushButton("JSON 파일 선택...")
        sa_browse_btn.clicked.connect(self._browse_service_account)
        vtx_form.addRow("", sa_browse_btn)

        vtx_layout.addWidget(vtx_group)
        layout.addWidget(self._gemini_vertex_widget)

        # 연결 테스트 버튼
        test_btn = QPushButton("연결 테스트")
        test_btn.clicked.connect(self._test_connection)
        layout.addWidget(test_btn)

        # 엔드포인트 변경 시 인증 패널 전환
        self._gemini_endpoint.currentTextChanged.connect(self._on_gemini_endpoint_changed)
        self._gemini_vertex_widget.setVisible(False)  # 초기값: AI Studio

        return widget

    def _build_openai_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("OpenAI 설정")
        form = QFormLayout(group)

        self._openai_key = QLineEdit()
        self._openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._openai_key.setPlaceholderText("sk-...")
        form.addRow("API 키:", self._openai_key)

        self._openai_model = QComboBox()
        self._openai_model.addItems(["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"])
        self._openai_model.setEditable(True)
        form.addRow("모델:", self._openai_model)

        layout.addWidget(group)
        layout.addStretch()
        return widget

    def _build_claude_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Claude 설정")
        form = QFormLayout(group)

        self._claude_key = QLineEdit()
        self._claude_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._claude_key.setPlaceholderText("sk-ant-...")
        form.addRow("API 키:", self._claude_key)

        self._claude_model = QComboBox()
        self._claude_model.addItems([
            "claude-opus-4-8",
            "claude-sonnet-4-6",
            "claude-haiku-4-5-20251001",
            "claude-3-5-sonnet-20241022",
        ])
        self._claude_model.setEditable(True)
        form.addRow("모델:", self._claude_model)

        layout.addWidget(group)
        layout.addStretch()
        return widget

    def _build_ollama_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Ollama 설정")
        form = QFormLayout(group)

        self._ollama_url = QLineEdit()
        self._ollama_url.setPlaceholderText("http://localhost:11434")
        form.addRow("서버 주소:", self._ollama_url)

        self._ollama_model = QLineEdit()
        self._ollama_model.setPlaceholderText("예: llama3, gemma2")
        form.addRow("모델명:", self._ollama_model)

        layout.addWidget(group)
        layout.addStretch()
        return widget

    # AI Studio 모델 ID 목록
    _GEMINI_AIS_MODELS = [
        "gemini-3.5-flash",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    ]

    # Vertex AI 모델 ID 목록 (버텍스는 모델명 형식이 다를 수 있음)
    _GEMINI_VERTEX_MODELS = [
        "gemini-3.1-pro-preview",
        "gemini-3.5-flash-preview",
        "gemini-3.5-flash",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    ]

    def _update_gemini_model_list(self, endpoint: str):
        """엔드포인트에 맞는 모델 목록으로 교체합니다."""
        current = self._gemini_model.currentText()
        self._gemini_model.blockSignals(True)
        self._gemini_model.clear()
        models = self._GEMINI_VERTEX_MODELS if endpoint == "vertex" else self._GEMINI_AIS_MODELS
        self._gemini_model.addItems(models)
        # 기존 선택값 유지 (목록에 없으면 직접 입력값으로)
        idx = self._gemini_model.findText(current)
        if idx >= 0:
            self._gemini_model.setCurrentIndex(idx)
        else:
            self._gemini_model.setCurrentText(current)
        self._gemini_model.blockSignals(False)

    def _on_gemini_endpoint_changed(self, endpoint: str):
        """Gemini 엔드포인트 변경 시 인증 패널을 전환합니다."""
        is_vertex = (endpoint == "vertex")
        self._gemini_ais_widget.setVisible(not is_vertex)
        self._gemini_vertex_widget.setVisible(is_vertex)

    def _browse_service_account(self):
        """JSON 파일을 선택해 텍스트 에디터에 내용을 로드합니다."""
        path, _ = QFileDialog.getOpenFileName(
            self, "서비스 계정 JSON 선택", "", "JSON 파일 (*.json)"
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._vertex_sa_json.setPlainText(f.read())
            except Exception as e:
                QMessageBox.warning(self, "파일 읽기 오류", f"파일을 읽을 수 없습니다:\n{e}")

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
        self._ocr_lang.addItem("자동 감지", "auto")
        self._ocr_lang.addItem("영어 (eng)", "eng")
        self._ocr_lang.addItem("일본어 (jpn)", "jpn")
        self._ocr_lang.addItem("한국어 (kor)", "kor")
        self._ocr_lang.addItem("중국어 간체 (chi_sim)", "chi_sim")
        self._ocr_lang.addItem("중국어 번체 (chi_tra)", "chi_tra")
        self._ocr_lang.addItem("영어+일본어 (eng+jpn)", "eng+jpn")
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

        self._run_mode = QComboBox()
        self._run_mode.addItem("실시간 (자동 반복)", "realtime")
        self._run_mode.addItem("스냅샷 (한 번만)", "snapshot")
        form.addRow("번역 모드:", self._run_mode)

        self._context_count = QSpinBox()
        self._context_count.setRange(0, 10)
        self._context_count.setSuffix(" 회")
        form.addRow("문맥 기억 수:", self._context_count)

        self._vision_mode = QCheckBox("Vision API 모드 (OCR 단계 건너뜀)")
        form.addRow("", self._vision_mode)

        self._auto_clipboard = QCheckBox("번역 결과를 클립보드에 자동 복사")
        form.addRow("", self._auto_clipboard)

        self._cache_max_size = QSpinBox()
        self._cache_max_size.setRange(10, 1000)
        form.addRow("캐시 최대 항목:", self._cache_max_size)

        layout.addWidget(group)
        layout.addStretch()
        return widget

    def _build_hotkeys_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("전역 단축키")
        form = QFormLayout(group)

        self._hotkey_toggle = QLineEdit()
        self._hotkey_toggle.setPlaceholderText("<ctrl>+<shift>+t")
        self._hotkey_toggle.setToolTip(
            "pynput 형식으로 입력하세요.\n"
            "예: <ctrl>+<shift>+t  /  <alt>+t\n"
            "특수 키: <ctrl> <shift> <alt> <cmd> <f1>~<f12>"
        )
        form.addRow("번역 시작/중지:", self._hotkey_toggle)

        self._hotkey_region = QLineEdit()
        self._hotkey_region.setPlaceholderText("<ctrl>+<shift>+r")
        self._hotkey_region.setToolTip(self._hotkey_toggle.toolTip())
        form.addRow("영역 선택:", self._hotkey_region)

        notice = QLabel("※ 변경 후 저장하면 즉시 적용됩니다.")
        notice.setStyleSheet("color: gray; font-size: 11px;")

        layout.addWidget(group)
        layout.addWidget(notice)
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

        # Gemini
        # 엔드포인트 먼저 설정 → 모델 목록 교체 → 모델 선택
        endpoint = c.get("provider.gemini.endpoint", "ai_studio")
        eidx = self._gemini_endpoint.findText(endpoint)
        if eidx >= 0:
            self._gemini_endpoint.setCurrentIndex(eidx)
        self._update_gemini_model_list(endpoint)

        model = c.get("provider.gemini.model", "gemini-3.5-flash")
        midx = self._gemini_model.findText(model)
        if midx >= 0:
            self._gemini_model.setCurrentIndex(midx)
        else:
            self._gemini_model.setCurrentText(model)

        self._gemini_key.setText(c.get("provider.gemini.api_key", ""))

        # Vertex AI
        region = c.get("provider.gemini.vertex.region", "global")
        ridx = self._vertex_region.findText(region)
        if ridx >= 0:
            self._vertex_region.setCurrentIndex(ridx)
        else:
            self._vertex_region.setCurrentText(region)
        self._vertex_sa_json.setPlainText(c.get("provider.gemini.vertex.service_account", ""))

        # OpenAI
        self._openai_key.setText(c.get("provider.openai.api_key", ""))
        oai_model = c.get("provider.openai.model", "gpt-4o")
        oai_idx = self._openai_model.findText(oai_model)
        if oai_idx >= 0:
            self._openai_model.setCurrentIndex(oai_idx)
        else:
            self._openai_model.setCurrentText(oai_model)

        # Claude
        self._claude_key.setText(c.get("provider.claude.api_key", ""))
        cl_model = c.get("provider.claude.model", "claude-sonnet-4-6")
        cl_idx = self._claude_model.findText(cl_model)
        if cl_idx >= 0:
            self._claude_model.setCurrentIndex(cl_idx)
        else:
            self._claude_model.setCurrentText(cl_model)

        # Ollama
        self._ollama_url.setText(c.get("provider.ollama.base_url", "http://localhost:11434"))
        self._ollama_model.setText(c.get("provider.ollama.model", ""))

        # 언어 탭
        src = c.get("language.source", "auto")
        sidx = self._source_lang.findText(src)
        if sidx >= 0:
            self._source_lang.setCurrentIndex(sidx)

        tgt = c.get("language.target", "ko")
        tidx = self._target_lang.findText(tgt)
        if tidx >= 0:
            self._target_lang.setCurrentIndex(tidx)

        ocr = c.get("language.ocr_lang", "auto")
        oidx = self._ocr_lang.findData(ocr)
        if oidx >= 0:
            self._ocr_lang.setCurrentIndex(oidx)
        else:
            self._ocr_lang.setCurrentText(ocr)

        # 캡처 탭
        self._interval_ms.setValue(c.get("capture.interval_ms", 1500))
        self._hash_threshold.setValue(c.get("detector.hash_threshold", 5))

        # 번역 탭
        run_mode = c.get("translation.run_mode", "realtime")
        rmidx = self._run_mode.findData(run_mode)
        if rmidx >= 0:
            self._run_mode.setCurrentIndex(rmidx)

        self._context_count.setValue(c.get("translation.context_count", 3))
        self._vision_mode.setChecked(c.get("translation.vision_mode", False))
        self._auto_clipboard.setChecked(c.get("translation.auto_clipboard", False))
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

        # 단축키 탭
        self._hotkey_toggle.setText(c.get("hotkeys.toggle_translation", "<ctrl>+<shift>+t"))
        self._hotkey_region.setText(c.get("hotkeys.select_region", "<ctrl>+<shift>+r"))

    def _save(self):
        """UI 값을 Config에 저장하고 창을 닫습니다."""
        c = self.config

        # 프로바이더
        c.set("provider.active", self._provider_combo.currentText())

        # Gemini
        c.set("provider.gemini.model", self._gemini_model.currentText())
        c.set("provider.gemini.endpoint", self._gemini_endpoint.currentText())
        c.set("provider.gemini.api_key", self._gemini_key.text())
        c.set("provider.gemini.vertex.region", self._vertex_region.currentText())
        c.set("provider.gemini.vertex.service_account", self._vertex_sa_json.toPlainText())

        # OpenAI
        c.set("provider.openai.api_key", self._openai_key.text())
        c.set("provider.openai.model", self._openai_model.currentText())

        # Claude
        c.set("provider.claude.api_key", self._claude_key.text())
        c.set("provider.claude.model", self._claude_model.currentText())

        # Ollama
        c.set("provider.ollama.base_url", self._ollama_url.text())
        c.set("provider.ollama.model", self._ollama_model.text())

        # 언어
        c.set("language.source", self._source_lang.currentText())
        c.set("language.target", self._target_lang.currentText())
        ocr_data = self._ocr_lang.currentData()
        c.set("language.ocr_lang", ocr_data if ocr_data else self._ocr_lang.currentText())

        # 캡처
        c.set("capture.interval_ms", self._interval_ms.value())
        c.set("detector.hash_threshold", self._hash_threshold.value())

        # 번역
        c.set("translation.run_mode", self._run_mode.currentData())
        c.set("translation.context_count", self._context_count.value())
        c.set("translation.vision_mode", self._vision_mode.isChecked())
        c.set("translation.auto_clipboard", self._auto_clipboard.isChecked())
        c.set("cache.max_size", self._cache_max_size.value())

        # 표시
        c.set("display.mode", self._display_mode.currentText())
        c.set("display.active_preset", self._active_preset.currentText())

        # 단축키
        toggle_key = self._hotkey_toggle.text().strip() or "<ctrl>+<shift>+t"
        region_key = self._hotkey_region.text().strip() or "<ctrl>+<shift>+r"
        c.set("hotkeys.toggle_translation", toggle_key)
        c.set("hotkeys.select_region", region_key)

        # 번역 프로필: 활성 프로필 이름 저장
        active_profile = self._profile_select.currentText()
        c.set("translation.active_profile", active_profile if active_profile != "(없음)" else "")

        c.save()
        self.settings_saved.emit()
        self.accept()

    # ── 번역 프로필 탭 ──

    def _build_profile_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 프로필 선택 영역
        select_group = QGroupBox("프로필 선택")
        select_layout = QHBoxLayout(select_group)
        self._profile_select = QComboBox()
        self._profile_select.currentTextChanged.connect(self._on_profile_selected)
        select_layout.addWidget(self._profile_select)

        delete_btn = QPushButton("삭제")
        delete_btn.clicked.connect(self._delete_profile)
        select_layout.addWidget(delete_btn)
        layout.addWidget(select_group)

        # 자동 생성 영역
        gen_group = QGroupBox("새 프로필 생성")
        gen_layout = QHBoxLayout(gen_group)
        self._profile_keyword = QLineEdit()
        self._profile_keyword.setPlaceholderText("콘텐츠 이름 입력 (예: 레지던트 이블 2)")
        gen_layout.addWidget(self._profile_keyword)

        self._generate_btn = QPushButton("자동 생성")
        self._generate_btn.clicked.connect(self._generate_profile)
        gen_layout.addWidget(self._generate_btn)
        layout.addWidget(gen_group)

        # 프로필 편집 영역
        edit_group = QGroupBox("프로필 내용")
        edit_form = QFormLayout(edit_group)

        self._profile_name = QLineEdit()
        self._profile_name.setPlaceholderText("프로필 이름")
        edit_form.addRow("이름:", self._profile_name)

        self._profile_genre = QLineEdit()
        self._profile_genre.setPlaceholderText("서바이벌 호러, 3인칭 액션")
        edit_form.addRow("장르:", self._profile_genre)

        self._profile_tone = QLineEdit()
        self._profile_tone.setPlaceholderText("긴박한, 어두운, 공포")
        edit_form.addRow("분위기:", self._profile_tone)

        # 용어집 테이블
        self._glossary_table = QTableWidget(0, 2)
        self._glossary_table.setHorizontalHeaderLabels(["원문", "번역"])
        self._glossary_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._glossary_table.setMinimumHeight(120)
        edit_form.addRow("용어집:", self._glossary_table)

        glossary_btns = QHBoxLayout()
        add_term_btn = QPushButton("+ 추가")
        add_term_btn.clicked.connect(self._add_glossary_row)
        del_term_btn = QPushButton("- 삭제")
        del_term_btn.clicked.connect(self._del_glossary_row)
        glossary_btns.addWidget(add_term_btn)
        glossary_btns.addWidget(del_term_btn)
        glossary_btns.addStretch()
        edit_form.addRow("", glossary_btns)

        self._profile_extra = QTextEdit()
        self._profile_extra.setPlaceholderText("캐릭터 대사는 반말, 시스템 메시지는 경어체")
        self._profile_extra.setMaximumHeight(60)
        edit_form.addRow("추가 지시:", self._profile_extra)

        layout.addWidget(edit_group)

        # 프로필 저장 버튼
        save_profile_btn = QPushButton("프로필 저장")
        save_profile_btn.clicked.connect(self._save_profile)
        layout.addWidget(save_profile_btn)

        layout.addStretch()

        # 프로필 목록 채우기
        self._refresh_profile_list()

        return tab

    def _refresh_profile_list(self):
        self._profile_select.blockSignals(True)
        self._profile_select.clear()
        self._profile_select.addItem("(없음)")
        for name in self._profile_manager.profile_names:
            self._profile_select.addItem(name)
        active = self.config.get("translation.active_profile", "")
        if active:
            idx = self._profile_select.findText(active)
            if idx >= 0:
                self._profile_select.setCurrentIndex(idx)
        self._profile_select.blockSignals(False)
        self._on_profile_selected(self._profile_select.currentText())

    def _on_profile_selected(self, name: str):
        if name == "(없음)" or not name:
            self._profile_name.clear()
            self._profile_genre.clear()
            self._profile_tone.clear()
            self._glossary_table.setRowCount(0)
            self._profile_extra.clear()
            return
        profile = self._profile_manager.get(name)
        if not profile:
            return
        self._profile_name.setText(profile.name)
        self._profile_genre.setText(profile.genre)
        self._profile_tone.setText(profile.tone)
        self._profile_extra.setPlainText(profile.extra_instruction)
        self._glossary_table.setRowCount(0)
        for src, dst in profile.glossary.items():
            row = self._glossary_table.rowCount()
            self._glossary_table.insertRow(row)
            self._glossary_table.setItem(row, 0, QTableWidgetItem(src))
            self._glossary_table.setItem(row, 1, QTableWidgetItem(dst))

    def _add_glossary_row(self):
        row = self._glossary_table.rowCount()
        self._glossary_table.insertRow(row)
        self._glossary_table.setItem(row, 0, QTableWidgetItem(""))
        self._glossary_table.setItem(row, 1, QTableWidgetItem(""))

    def _del_glossary_row(self):
        row = self._glossary_table.currentRow()
        if row >= 0:
            self._glossary_table.removeRow(row)

    def _get_glossary_from_table(self) -> dict[str, str]:
        glossary = {}
        for row in range(self._glossary_table.rowCount()):
            src_item = self._glossary_table.item(row, 0)
            dst_item = self._glossary_table.item(row, 1)
            src = src_item.text().strip() if src_item else ""
            dst = dst_item.text().strip() if dst_item else ""
            if src and dst:
                glossary[src] = dst
        return glossary

    def _save_profile(self):
        name = self._profile_name.text().strip()
        if not name:
            QMessageBox.warning(self, "프로필 저장", "프로필 이름을 입력하세요.")
            return
        profile = TranslationProfile(
            name=name,
            genre=self._profile_genre.text().strip(),
            tone=self._profile_tone.text().strip(),
            glossary=self._get_glossary_from_table(),
            extra_instruction=self._profile_extra.toPlainText().strip(),
        )
        self._profile_manager.save(profile)
        self._refresh_profile_list()
        self._profile_select.setCurrentText(name)
        QMessageBox.information(self, "프로필 저장", f"'{name}' 프로필이 저장되었습니다.")

    def _delete_profile(self):
        name = self._profile_select.currentText()
        if name == "(없음)" or not name:
            return
        reply = QMessageBox.question(
            self, "프로필 삭제", f"'{name}' 프로필을 삭제하시겠습니까?",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._profile_manager.delete(name)
            self._refresh_profile_list()

    def _generate_profile(self):
        keyword = self._profile_keyword.text().strip()
        if not keyword:
            QMessageBox.warning(self, "자동 생성", "키워드를 입력하세요.")
            return

        import asyncio

        self._generate_btn.setEnabled(False)
        self._generate_btn.setText("생성 중...")

        try:
            loop = asyncio.new_event_loop()
            profile = loop.run_until_complete(
                self._profile_manager.auto_generate(keyword)
            )
            loop.close()

            self._profile_name.setText(profile.name)
            self._profile_genre.setText(profile.genre)
            self._profile_tone.setText(profile.tone)
            self._profile_extra.setPlainText(profile.extra_instruction)
            self._glossary_table.setRowCount(0)
            for src, dst in profile.glossary.items():
                row = self._glossary_table.rowCount()
                self._glossary_table.insertRow(row)
                self._glossary_table.setItem(row, 0, QTableWidgetItem(src))
                self._glossary_table.setItem(row, 1, QTableWidgetItem(dst))

            QMessageBox.information(self, "자동 생성", "프로필이 생성되었습니다. 확인 후 [프로필 저장]을 눌러주세요.")
        except Exception as e:
            QMessageBox.critical(self, "자동 생성 실패", f"프로필 생성 중 오류: {e}")
        finally:
            self._generate_btn.setEnabled(True)
            self._generate_btn.setText("자동 생성")

    def _test_connection(self):
        """현재 선택된 프로바이더로 연결을 테스트합니다."""
        import asyncio

        provider_name = self._provider_combo.currentText()

        try:
            provider = self._create_test_provider(provider_name)
        except ValueError as e:
            QMessageBox.warning(self, "연결 테스트", str(e))
            return

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(provider.test_connection())
            QMessageBox.information(self, "연결 테스트", "연결에 성공했습니다! ✓")
        except Exception as e:
            QMessageBox.critical(self, "연결 실패", f"연결 중 오류가 발생했습니다:\n\n{e}")
        finally:
            loop.run_until_complete(provider.close())
            loop.close()

    def _create_test_provider(self, provider_name: str):
        """테스트용 프로바이더 인스턴스를 생성합니다."""
        if provider_name == "gemini":
            from mallangmollang.providers.gemini import GeminiProvider
            endpoint = self._gemini_endpoint.currentText()
            if endpoint == "vertex":
                sa_json = self._vertex_sa_json.toPlainText().strip()
                if not sa_json:
                    raise ValueError("서비스 계정 JSON을 입력해주세요.")
                return GeminiProvider(
                    api_key="",
                    model=self._gemini_model.currentText(),
                    endpoint="vertex",
                    vertex_region=self._vertex_region.currentText() or "us-central1",
                    service_account=sa_json,  # project_id는 JSON에서 자동 추출
                )
            else:
                api_key = self._gemini_key.text().strip()
                if not api_key:
                    raise ValueError("API 키를 먼저 입력해주세요.")
                return GeminiProvider(
                    api_key=api_key,
                    model=self._gemini_model.currentText(),
                    endpoint="ai_studio",
                )

        elif provider_name == "openai":
            api_key = self._openai_key.text().strip()
            if not api_key:
                raise ValueError("OpenAI API 키를 입력해주세요.")
            # OpenAI 프로바이더가 구현되면 교체 — 현재 stub
            raise ValueError("OpenAI 프로바이더는 아직 구현 중입니다.")

        elif provider_name == "claude":
            api_key = self._claude_key.text().strip()
            if not api_key:
                raise ValueError("Claude API 키를 입력해주세요.")
            raise ValueError("Claude 프로바이더는 아직 구현 중입니다.")

        elif provider_name == "ollama":
            base_url = self._ollama_url.text().strip() or "http://localhost:11434"
            raise ValueError("Ollama 프로바이더는 아직 구현 중입니다.")

        else:
            raise ValueError(f"알 수 없는 프로바이더: {provider_name}")
