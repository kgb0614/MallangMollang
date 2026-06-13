"""
전역 단축키 모듈
pynput을 이용해 앱이 포커스를 잃어도 단축키를 감지합니다.
"""

from pynput import keyboard
from PyQt6.QtCore import QObject, pyqtSignal

from mallangmollang.infra.config import Config


def _parse_hotkey(hotkey_str: str) -> str:
    """
    config 형식의 단축키 문자열을 pynput 형식으로 변환합니다.
    예: "<ctrl>+<shift>+t"  →  "<ctrl>+<shift>+t"  (그대로 사용 가능)
    """
    return hotkey_str


class HotkeyManager(QObject):
    """
    전역 단축키 리스너.

    pynput은 별도 스레드에서 실행되므로, Qt 위젯 접근은
    시그널을 통해 메인 스레드로 위임합니다.

    시그널:
        toggle_requested  — 번역 시작/중지 단축키
        region_requested  — 영역 선택 단축키

    사용 예시:
        hk = HotkeyManager(config)
        hk.toggle_requested.connect(app.on_toggle)
        hk.start()
    """

    toggle_requested = pyqtSignal()
    region_requested = pyqtSignal()
    dismiss_requested = pyqtSignal()

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self._config = config
        self._listener: keyboard.GlobalHotKeys | None = None
        self._esc_listener: keyboard.Listener | None = None

    def start(self) -> None:
        """단축키 리스닝을 시작합니다."""
        if self._listener is not None:
            return

        toggle_key = self._config.get("hotkeys.toggle_translation", "<ctrl>+<shift>+t")
        region_key = self._config.get("hotkeys.select_region", "<ctrl>+<shift>+r")

        hotkey_map = {
            toggle_key: self._on_toggle,
            region_key: self._on_region,
        }

        try:
            self._listener = keyboard.GlobalHotKeys(hotkey_map)
            self._listener.start()
        except Exception as e:
            print(f"[HotkeyManager] 단축키 리스너 시작 실패: {e}")

        # ESC 키 리스너 (단일 키이므로 별도 Listener 사용)
        try:
            self._esc_listener = keyboard.Listener(on_press=self._on_key_press)
            self._esc_listener.start()
        except Exception as e:
            print(f"[HotkeyManager] ESC 리스너 시작 실패: {e}")

    def stop(self) -> None:
        """단축키 리스닝을 중지합니다."""
        if self._listener:
            self._listener.stop()
            self._listener = None
        if self._esc_listener:
            self._esc_listener.stop()
            self._esc_listener = None

    def reload(self) -> None:
        """설정 변경 후 단축키를 재등록합니다."""
        self.stop()
        self.start()

    # pynput 스레드에서 호출됨 → 시그널로 Qt 스레드에 전달
    def _on_toggle(self) -> None:
        self.toggle_requested.emit()

    def _on_region(self) -> None:
        self.region_requested.emit()

    def _on_key_press(self, key) -> None:
        if key == keyboard.Key.esc:
            self.dismiss_requested.emit()
