# -*- coding: utf-8 -*-
"""AS Screener - display language helper (v1.0.3)

The screen and messages default to English; Korean is available ("ko").
Each message is written in both languages right where it is used: tr(lang, "한국어", "English").
Python standard library only.
"""
from __future__ import annotations

LANGS = ("en", "ko")
DEFAULT = "en"


def norm(lang) -> str:
    """Any value → 'ko' or 'en' (default English)."""
    return "ko" if str(lang or "").strip().lower().startswith("ko") else DEFAULT


def tr(lang, ko: str, en: str) -> str:
    """Pick the Korean or English text for this display language."""
    return ko if norm(lang) == "ko" else en


class BilingualError(Exception):
    """An error shown to the user. Keeps both languages; str() is English."""

    def __init__(self, ko: str, en: str | None = None):
        self.ko, self.en = ko, (en if en is not None else ko)
        super().__init__(self.en)

    def text(self, lang) -> str:
        return tr(lang, self.ko, self.en)
