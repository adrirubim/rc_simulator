from __future__ import annotations

from rc_simulator.ui_qt.strings import get_ui_strings, normalize_ui_language


def test_normalize_ui_language() -> None:
    assert normalize_ui_language("en") == "en"
    assert normalize_ui_language("it") == "it"
    assert normalize_ui_language("es") == "es"
    assert normalize_ui_language("EN") == "en"
    assert normalize_ui_language("  it  ") == "it"
    assert normalize_ui_language("xx") == "en"
    assert normalize_ui_language(None) == "en"


def test_get_ui_strings_returns_distinct_localizations() -> None:
    en = get_ui_strings("en")
    it = get_ui_strings("it")
    es = get_ui_strings("es")

    # Sentinel fields: should differ across languages for a meaningful UX.
    assert en.settings_title != it.settings_title
    assert en.settings_title != es.settings_title
    assert it.settings_title != es.settings_title

    # Unknown must fall back to English.
    xx = get_ui_strings("xx")
    assert xx.settings_title == en.settings_title
