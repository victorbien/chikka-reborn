"""SMS encoding and segment estimation (FR-SMS-002).

GSM-7: 160 units in a single message, 153 per part when concatenated; extension characters cost
two units. Unicode (UCS-2/UTF-16): 70 units single, 67 per part; characters outside the Basic
Multilingual Plane (most emoji) cost two units. The frontend (src/lib/sms.ts) implements the
same rules and both are tested against the shared vectors in tests/unit/test_sms_segments.py.

This is an estimate: the carrier decides the final split. The server value is authoritative.
"""

import math
from dataclasses import dataclass
from typing import Literal

Encoding = Literal["gsm7", "ucs2"]

GSM_BASIC = frozenset(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM_EXTENDED = frozenset("^{}\\[~]|€\f")

MAX_SEGMENTS = 10


@dataclass(frozen=True)
class SegmentInfo:
    encoding: Encoding
    characters: int
    units: int
    segments: int
    per_segment: int

    @property
    def remaining_in_segment(self) -> int:
        capacity = self.segments * self.per_segment
        return max(0, capacity - self.units)


def analyse(body: str) -> SegmentInfo:
    characters = len(body)
    gsm_units = 0
    is_gsm = True
    for char in body:
        if char in GSM_BASIC:
            gsm_units += 1
        elif char in GSM_EXTENDED:
            gsm_units += 2
        else:
            is_gsm = False
            break

    if is_gsm:
        single = gsm_units <= 160
        return SegmentInfo(
            encoding="gsm7",
            characters=characters,
            units=gsm_units,
            segments=0 if gsm_units == 0 else 1 if single else math.ceil(gsm_units / 153),
            per_segment=160 if single else 153,
        )

    utf16_units = sum(2 if ord(char) > 0xFFFF else 1 for char in body)
    single = utf16_units <= 70
    return SegmentInfo(
        encoding="ucs2",
        characters=characters,
        units=utf16_units,
        segments=1 if single else math.ceil(utf16_units / 67),
        per_segment=70 if single else 67,
    )
