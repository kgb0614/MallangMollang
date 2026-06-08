"""
Unit 5 테스트: display/overlay.py + display/presets.py + ui/region_selector.py

헤드리스 환경에서도 실행 가능하도록 QT_QPA_PLATFORM=offscreen을 사용합니다.
"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QPoint, QRect, Qt

# 테스트 전체에 공유되는 QApplication (PyQt6는 하나만 존재해야 함)
app = QApplication.instance() or QApplication(sys.argv)


# ─────────────────────────────────────────
# presets.py 테스트
# ─────────────────────────────────────────

class TestOverlayPreset:
    def test_default_values(self):
        """기본값이 올바르게 설정되는지"""
        from mallangmollang.display.presets import OverlayPreset
        p = OverlayPreset(name="테스트")
        assert p.font_size == 16
        assert p.text_color == (255, 255, 255, 255)
        assert p.bg_color == (0, 0, 0, 160)
        assert p.outline is True

    def test_to_dict_and_from_dict(self):
        """직렬화/역직렬화가 일치하는지"""
        from mallangmollang.display.presets import OverlayPreset
        p = OverlayPreset(
            name="왕복 테스트",
            font_size=20,
            text_color=(255, 200, 0, 255),
        )
        restored = OverlayPreset.from_dict(p.to_dict())
        assert restored.name == p.name
        assert restored.font_size == p.font_size
        assert restored.text_color == p.text_color

    def test_builtin_presets_exist(self):
        """내장 프리셋 3종이 모두 존재하는지"""
        from mallangmollang.display.presets import BUILTIN_PRESETS
        assert len(BUILTIN_PRESETS) == 3
        names = [p.name for p in BUILTIN_PRESETS]
        assert "기본" in names
        assert "어두운 게임용" in names
        assert "밝은 배경용" in names

    def test_get_preset_by_name_found(self):
        """이름으로 프리셋 조회"""
        from mallangmollang.display.presets import get_preset_by_name, BUILTIN_PRESETS
        p = get_preset_by_name("어두운 게임용")
        assert p.name == "어두운 게임용"

    def test_get_preset_by_name_fallback(self):
        """없는 이름 조회 시 기본 프리셋 반환"""
        from mallangmollang.display.presets import get_preset_by_name, PRESET_DEFAULT
        p = get_preset_by_name("존재하지않는프리셋")
        assert p.name == PRESET_DEFAULT.name


# ─────────────────────────────────────────
# overlay.py 테스트
# ─────────────────────────────────────────

class TestOverlayWindow:
    def test_create_overlay(self):
        """오버레이 창이 생성되는지"""
        from mallangmollang.display.overlay import OverlayWindow
        overlay = OverlayWindow()
        assert overlay is not None

    def test_window_flags(self):
        """투명 + 최상위 + 클릭투과 플래그가 설정되는지"""
        from mallangmollang.display.overlay import OverlayWindow
        overlay = OverlayWindow()
        flags = overlay.windowFlags()
        assert flags & Qt.WindowType.FramelessWindowHint
        assert flags & Qt.WindowType.WindowStaysOnTopHint

    def test_show_translation(self):
        """show_translation 호출 시 텍스트가 표시되는지"""
        from mallangmollang.display.overlay import OverlayWindow
        overlay = OverlayWindow()
        overlay.show_translation("테스트 번역", position=(100, 100))
        assert overlay._label.text() == "테스트 번역"
        assert overlay.isVisible()
        overlay.hide()

    def test_hide_translation(self):
        """hide_translation 호출 시 숨겨지는지"""
        from mallangmollang.display.overlay import OverlayWindow
        overlay = OverlayWindow()
        overlay.show_translation("숨길 텍스트", position=(50, 50))
        overlay.hide_translation()
        assert not overlay.isVisible()

    def test_set_preset(self):
        """프리셋 변경이 적용되는지"""
        from mallangmollang.display.overlay import OverlayWindow
        from mallangmollang.display.presets import PRESET_DARK_GAME, PRESET_LIGHT_BG
        overlay = OverlayWindow(preset=PRESET_DARK_GAME)
        assert overlay.preset.name == "어두운 게임용"
        overlay.set_preset(PRESET_LIGHT_BG)
        assert overlay.preset.name == "밝은 배경용"

    def test_show_translation_with_region(self):
        """region 파라미터로 위치가 설정되는지"""
        from mallangmollang.display.overlay import OverlayWindow
        overlay = OverlayWindow()
        overlay.show_translation("영역 기반 위치", region=(100, 200, 300, 50))
        # 영역 아래 (y + h + 4 = 254) 에 위치해야 함
        assert overlay.y() == 254
        overlay.hide()

    def test_update_position(self):
        """update_position으로 위치 이동"""
        from mallangmollang.display.overlay import OverlayWindow
        overlay = OverlayWindow()
        overlay.show_translation("위치 이동 테스트", position=(0, 0))
        overlay.update_position(200, 300)
        assert overlay.x() == 200
        assert overlay.y() == 300
        overlay.hide()

    def test_custom_preset_applied(self):
        """커스텀 프리셋이 레이블 스타일시트에 반영되는지"""
        from mallangmollang.display.overlay import OverlayWindow
        from mallangmollang.display.presets import OverlayPreset
        preset = OverlayPreset(
            name="커스텀",
            font_size=24,
            text_color=(255, 0, 0, 255),
            bg_color=(0, 0, 255, 100),
            outline=False,
        )
        overlay = OverlayWindow(preset=preset)
        style = overlay._label.styleSheet()
        # 빨간 텍스트 색상이 스타일시트에 포함되어야 함
        assert "255,0,0" in style


# ─────────────────────────────────────────
# region_selector.py 테스트
# ─────────────────────────────────────────

class TestRegionSelector:
    def test_create_selector(self):
        """RegionSelector가 생성되는지"""
        from mallangmollang.ui.region_selector import RegionSelector
        selector = RegionSelector()
        assert selector is not None

    def test_signals_exist(self):
        """region_selected, selection_cancelled 시그널이 존재하는지"""
        from mallangmollang.ui.region_selector import RegionSelector
        selector = RegionSelector()
        assert hasattr(selector, "region_selected")
        assert hasattr(selector, "selection_cancelled")

    def test_get_selection_rect_empty(self):
        """시작점 없을 때 빈 QRect 반환"""
        from mallangmollang.ui.region_selector import RegionSelector
        selector = RegionSelector()
        rect = selector._get_selection_rect()
        assert rect == QRect()

    def test_get_selection_rect_with_points(self):
        """시작점과 현재점으로 올바른 사각형 계산"""
        from mallangmollang.ui.region_selector import RegionSelector
        selector = RegionSelector()
        selector._start_point = QPoint(10, 20)
        selector._current_point = QPoint(110, 120)
        rect = selector._get_selection_rect()
        # PyQt6의 QRect(p1, p2)는 inclusive: width = x2-x1+1
        assert rect.width() == 101
        assert rect.height() == 101
        assert rect.x() == 10
        assert rect.y() == 20

    def test_get_selection_rect_normalized(self):
        """역방향 드래그 시에도 정규화된 사각형 반환"""
        from mallangmollang.ui.region_selector import RegionSelector
        selector = RegionSelector()
        # 오른쪽 아래에서 왼쪽 위로 드래그
        selector._start_point = QPoint(200, 200)
        selector._current_point = QPoint(50, 50)
        rect = selector._get_selection_rect()
        # normalized: 작은 좌표가 origin, inclusive size
        assert rect.x() == 51
        assert rect.y() == 51
        assert rect.width() == 149
        assert rect.height() == 149

    def test_region_selected_signal(self):
        """마우스 릴리즈 시 region_selected 시그널 발생"""
        from mallangmollang.ui.region_selector import RegionSelector
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QMouseEvent
        from PyQt6.QtCore import QPointF

        selector = RegionSelector()
        results = []
        selector.region_selected.connect(results.append)

        # 직접 내부 상태를 설정하고 마우스 릴리즈 이벤트 시뮬레이션
        selector._start_point = QPoint(0, 0)
        selector._current_point = QPoint(100, 80)
        selector._is_drawing = True

        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(100, 80),
            QPointF(100, 80),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        selector.mouseReleaseEvent(event)

        assert len(results) == 1
        x, y, w, h = results[0]
        # PyQt6 QRect(p1,p2) inclusive: w = 100+1, h = 80+1
        assert w == 101
        assert h == 81

    def test_small_region_ignored(self):
        """10px 미만 작은 영역은 무시하고 취소 시그널 발생"""
        from mallangmollang.ui.region_selector import RegionSelector
        from PyQt6.QtGui import QMouseEvent
        from PyQt6.QtCore import QPointF

        selector = RegionSelector()
        cancelled = []
        selected = []
        selector.selection_cancelled.connect(lambda: cancelled.append(True))
        selector.region_selected.connect(selected.append)

        selector._start_point = QPoint(0, 0)
        selector._current_point = QPoint(5, 5)   # 너무 작음
        selector._is_drawing = True

        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPointF(5, 5),
            QPointF(5, 5),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        selector.mouseReleaseEvent(event)

        assert len(selected) == 0
        assert len(cancelled) == 1

    def test_cancel_on_right_click(self):
        """우클릭 시 취소 시그널 발생"""
        from mallangmollang.ui.region_selector import RegionSelector
        from PyQt6.QtGui import QMouseEvent
        from PyQt6.QtCore import QPointF

        selector = RegionSelector()
        cancelled = []
        selector.selection_cancelled.connect(lambda: cancelled.append(True))

        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(50, 50),
            QPointF(50, 50),
            Qt.MouseButton.RightButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        selector.mousePressEvent(event)
        assert len(cancelled) == 1

    def test_cancel_on_esc(self):
        """ESC 키 시 취소 시그널 발생"""
        from mallangmollang.ui.region_selector import RegionSelector
        from PyQt6.QtGui import QKeyEvent

        selector = RegionSelector()
        cancelled = []
        selector.selection_cancelled.connect(lambda: cancelled.append(True))

        event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Escape,
            Qt.KeyboardModifier.NoModifier,
        )
        selector.keyPressEvent(event)
        assert len(cancelled) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
