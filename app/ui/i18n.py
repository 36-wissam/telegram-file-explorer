"""Internationalization helper for instantaneous in-place string translation."""

from typing import Dict

STRINGS: Dict[str, Dict[str, str]] = {
    "settings_title": {"en": "Settings", "ar": "الإعدادات"},
    "account_section": {"en": "Account", "ar": "الحساب"},
    "connected_status": {"en": "Connected", "ar": "متصل"},
    "connected_mtproto": {"en": "Connected via MTProto", "ar": "متصل عبر MTProto"},
    "sign_out": {"en": "Sign Out", "ar": "تسجيل الخروج"},
    "theme_section": {"en": "Theme", "ar": "المظهر"},
    "theme_system": {"en": "System", "ar": "النظام"},
    "theme_light": {"en": "Light", "ar": "فاتح"},
    "theme_dark": {"en": "Dark", "ar": "غامق"},
    "download_location": {"en": "Download Location", "ar": "مكان التحميل"},
    "cache_section": {"en": "Cache", "ar": "الذاكرة المؤقتة"},
    "clear_cache": {"en": "Clear Cache", "ar": "مسح الذاكرة المؤقتة"},
    "concurrent_downloads": {"en": "Concurrent Downloads", "ar": "التحميلات المتزامنة"},
    "language_section": {"en": "Language", "ar": "اللغة"},
    "tools_section": {"en": "Tools", "ar": "الأدوات"},
    "indexing_manager": {"en": "Indexing Manager", "ar": "إدارة الفهرسة"},
    "reindex_dialogues": {"en": "Re-Index Dialogues", "ar": "إعادة فهرسة المحادثات"},
    "about_section": {"en": "About", "ar": "حول التطبيق"},
    "about_desc": {
        "en": "Local-first Telegram MTProto desktop file explorer.",
        "ar": "مستكشف ملفات سطح المكتب لتيليجرام بنظام محلي أولاً.",
    },
    "apply_button": {"en": "Apply", "ar": "تطبيق"},
    "applied_feedback": {"en": "Applied", "ar": "تم التطبيق"},
    "search_chats": {"en": "Search chats...", "ar": "بحث في المحادثات..."},
    "select_chat": {"en": "Select a chat to view files", "ar": "اختر محادثة لعرض الملفات"},
}


def tr(key: str, lang: str = "en") -> str:
    """Retrieve translated string for the specified language."""
    entry = STRINGS.get(key)
    if not entry:
        return key
    return entry.get(lang, entry.get("en", key))
