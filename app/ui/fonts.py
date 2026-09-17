"""Typography helper module for Telegram File Explorer design system.
Bundles Inter and Cairo fonts, with automatic Arabic/Latin script font selection.
"""

import re
from pathlib import Path
from PySide6.QtGui import QFont, QFontDatabase
from ..core.logger import get_logger

logger = get_logger("ui.fonts")

# Regex covering Arabic Unicode block
ARABIC_REGEX = re.compile(
    r"[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]"
)

_fonts_initialized = False
_inter_family = "Inter"
_cairo_family = "Cairo"


def init_application_fonts() -> None:
    """Load bundled Inter and Cairo TTF font files into Qt font database."""
    global _fonts_initialized, _inter_family, _cairo_family
    if _fonts_initialized:
        return

    fonts_dir = Path(__file__).resolve().parent.parent / "resources" / "fonts"
    if fonts_dir.exists():
        for ttf_path in fonts_dir.glob("*.ttf"):
            font_id = QFontDatabase.addApplicationFont(str(ttf_path))
            if font_id != -1:
                families = QFontDatabase.applicationFontFamilies(font_id)
                logger.debug("Loaded font %s: %s", ttf_path.name, families)
                for f in families:
                    if "cairo" in f.lower():
                        _cairo_family = f
                    elif "inter" in f.lower():
                        _inter_family = f
            else:
                logger.warning("Failed to register font: %s", ttf_path)

    _fonts_initialized = True


def has_arabic(text: str) -> bool:
    """Check if the given string contains Arabic characters."""
    if not text:
        return False
    return bool(ARABIC_REGEX.search(text))


def get_font_for_text(
    text: str,
    pixel_size: int = 13,
    weight: int = 400,
) -> QFont:
    """Return appropriate QFont choosing Cairo for Arabic text and Inter for Latin."""
    init_application_fonts()

    if has_arabic(text):
        font = QFont(_cairo_family)
        font.setFamilies([_cairo_family, "Segoe UI", "Arial"])
    else:
        font = QFont(_inter_family)
        font.setFamilies([_inter_family, "Segoe UI", "Arial"])

    font.setPixelSize(pixel_size)
    font.setWeight(QFont.Weight(weight))
    return font


# Preset Typography Helpers (matching specification)
def get_title_font(text: str = "") -> QFont:
    """Title 18px / 600 weight."""
    return get_font_for_text(text, pixel_size=18, weight=600)


def get_section_header_font(text: str = "") -> QFont:
    """Section header 14px / 600 weight."""
    return get_font_for_text(text, pixel_size=14, weight=600)


def get_body_font(text: str = "") -> QFont:
    """Body 13px / 400 weight."""
    return get_font_for_text(text, pixel_size=13, weight=400)


def get_secondary_font(text: str = "") -> QFont:
    """Secondary/meta text 12px / 400 weight."""
    return get_font_for_text(text, pixel_size=12, weight=400)


def get_caption_font(text: str = "") -> QFont:
    """Caption 11px / 400 weight."""
    return get_font_for_text(text, pixel_size=11, weight=400)
