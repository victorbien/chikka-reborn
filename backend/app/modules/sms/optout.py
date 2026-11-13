"""Opt-out and opt-in keywords (FR-SMSRECV-012, FR-PRIVACY-008).

A keyword counts only when it is the whole message (trimmed, case-folded). "please stop by
later" is a normal message. Local-language equivalents are configuration to be confirmed with
native speakers before launch in the Philippines; they are not guessed here.
"""

from typing import Literal

OPT_OUT_KEYWORDS = frozenset({"stop", "stopall", "unsubscribe", "cancel", "end", "quit"})
# "YES" is deliberately not an opt-in keyword: it is an ordinary reply.
OPT_IN_KEYWORDS = frozenset({"start", "unstop"})

Keyword = Literal["opt_out", "opt_in"]


def classify_keyword(body: str) -> tuple[Keyword, str] | None:
    word = body.strip().casefold()
    if word in OPT_OUT_KEYWORDS:
        return "opt_out", word
    if word in OPT_IN_KEYWORDS:
        return "opt_in", word
    return None
