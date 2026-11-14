"""Languages the assistant offers for translation and composition.

Support depends on the configured model, so quality for regional languages (ceb, ilo, hil)
should be verified when the production model is chosen (docs/api/ai-api.md).
"""

LANGUAGES: dict[str, str] = {
    "en": "English",
    "fil": "Filipino (Tagalog)",
    "es": "Spanish",
    "ceb": "Cebuano",
    "ilo": "Ilocano",
    "hil": "Hiligaynon",
    "ja": "Japanese",
    "zh": "Chinese",
    "ko": "Korean",
    "fr": "French",
}
