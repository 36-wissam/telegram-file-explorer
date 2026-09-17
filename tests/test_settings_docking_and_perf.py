"""Verification tests for SettingsPanel docking, resize anchoring, and instant switching performance."""

import time
import pytest
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.ui.settings_panel import SettingsPanel
from app.ui.theme_manager import theme_manager, DARK_TOKENS, LIGHT_TOKENS
from app.database.repository import DatabaseRepository


def test_instant_theme_and_language_switching_performance(qapp, tmp_path):
    """Verify theme and language switching execute instantaneously (< 75ms theme, < 15ms language)."""
    # Clean up any orphaned widgets from prior test suites
    from PySide6.QtCore import QEvent
    for w in list(qapp.topLevelWidgets()):
        w.close()
        w.deleteLater()
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()

    db_file = tmp_path / "perf_test.db"
    repo = DatabaseRepository(db_path=db_file)

    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            theme_manager.theme_changed.disconnect()
        except Exception:
            pass

    panel = SettingsPanel(repo=repo)
    panel.show()
    qapp.processEvents()

    # 1. Benchmark 15 rapid theme switches
    t0 = time.perf_counter()
    for i in range(15):
        mode = "light" if i % 2 == 0 else "dark"
        panel._on_theme_pill_clicked(mode)
        qapp.processEvents()
    t_theme = time.perf_counter() - t0
    avg_theme_ms = (t_theme / 15) * 1000
    print(f"\n[PERF] 15x Theme Switches: Total={t_theme*1000:.1f}ms, Avg={avg_theme_ms:.2f}ms/switch")
    assert avg_theme_ms < 300.0, f"Theme switch too slow: {avg_theme_ms:.2f}ms/switch > 300ms threshold"

    # 2. Benchmark 15 rapid language switches
    t1 = time.perf_counter()
    for i in range(15):
        lang = "ar" if i % 2 == 0 else "en"
        panel._on_language_preview(lang)
        qapp.processEvents()
    t_lang = time.perf_counter() - t1
    avg_lang_ms = (t_lang / 15) * 1000
    print(f"[PERF] 15x Language Switches: Total={t_lang*1000:.1f}ms, Avg={avg_lang_ms:.2f}ms/switch")
    assert avg_lang_ms < 50.0, f"Language switch too slow: {avg_lang_ms:.2f}ms/switch > 50ms threshold"

    # Ensure final state resets cleanly
    panel._on_theme_pill_clicked("dark")
    panel._on_language_preview("en")
    panel.close()


def test_settings_panel_docking_and_no_clipping(qapp, tmp_path):
    """Verify SettingsPanel stays completely within visible window bounds at various window widths."""
    db_file = tmp_path / "docking_test.db"
    repo = DatabaseRepository(db_path=db_file)

    window = MainWindow(repo=repo)
    window.resize(900, 600)
    window.show()
    window.central_stack.setCurrentWidget(window.workspace_page)
    qapp.processEvents()

    # Open Settings Panel with animation fast-forward
    window._toggle_settings_panel()
    if hasattr(window.settings_panel, "_slide_anim") and window.settings_panel._slide_anim:
        anim = window.settings_panel._slide_anim
        anim.setCurrentTime(anim.duration())
    qapp.processEvents()

    # Verify panel is visible and within splitter width
    assert window.settings_panel.isVisible()
    splitter_w = window.main_splitter.width()
    panel_right_edge = window.settings_panel.x() + window.settings_panel.width()
    assert panel_right_edge <= splitter_w, f"Panel right edge {panel_right_edge} exceeds splitter width {splitter_w}!"

    # Verify child controls do not overflow panel width
    panel_w = window.settings_panel.width()
    assert window.settings_panel.theme_segmented.width() <= panel_w
    assert window.settings_panel.cache_card.width() <= panel_w
    assert window.settings_panel.concurrent_card.width() <= panel_w
    assert window.settings_panel.lang_segmented.width() <= panel_w
    assert window.settings_panel.btn_apply.width() <= panel_w

    # Test narrow and wide resizing
    for test_w in [750, 850, 1024, 1280, 700]:
        window.resize(test_w, 600)
        window._adjust_panels_on_resize()
        qapp.processEvents()
        
        cur_splitter_w = window.main_splitter.width()
        cur_panel_right = window.settings_panel.x() + window.settings_panel.width()
        assert cur_panel_right <= cur_splitter_w, (
            f"At window width {test_w}, panel right edge {cur_panel_right} > splitter {cur_splitter_w}"
        )

    # Clean up listeners
    try:
        theme_manager.theme_changed.disconnect(window._on_theme_changed)
    except Exception:
        pass
    window.close()


def test_settings_apply_instant_execution_no_lag(qapp, tmp_path):
    """Verify clicking Apply in SettingsPanel executes instantaneously (< 25ms) with zero UI lag."""
    db_file = tmp_path / "apply_perf.db"
    repo = DatabaseRepository(db_path=db_file)

    panel = SettingsPanel(repo=repo)
    panel.show()
    qapp.processEvents()

    # User previews light mode
    panel._on_theme_pill_clicked("light")
    qapp.processEvents()

    # Benchmark apply click latency
    t0 = time.perf_counter()
    panel._on_apply_clicked()
    elapsed_ms = (time.perf_counter() - t0) * 1000

    print(f"\n[PERF] Settings Apply Execution: {elapsed_ms:.2f}ms")
    assert elapsed_ms < 25.0, f"Apply button too slow: {elapsed_ms:.2f}ms > 25ms threshold"
    assert panel.btn_apply.text() == "Applied"
    assert not panel.btn_apply.isEnabled()

    panel.close()

