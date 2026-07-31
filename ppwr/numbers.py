"""Convert German numeric notation into English convention.

Applied only when rendering English. German pages keep the spreadsheet's own
notation.
"""

from __future__ import annotations

import re

# A German number is either grouped thousands with an optional decimal comma
# (1.714, 1.714,5) or a bare decimal comma (2,5). Grouping requires exactly
# three digits after each separator, which keeps board grades such as
# "VDW 1.40" and article codes such as "C 1-4003" out of the match.
#
# The decimal branch allows at most two decimal places on purpose. Three would
# make "1,714" - already English grouping - look like a German decimal, so a
# second pass over converted text would flip it straight back.
_GERMAN_NUMBER = re.compile(r"\b\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?\b|\b\d+,\d{1,2}\b")

# str.translate swaps both separators in a single pass. Two chained str.replace
# calls would convert 1.714 to 1,714 and then straight back to 1.714.
_SWAP_SEPARATORS = str.maketrans({".": ",", ",": "."})


def localise(text: str) -> str:
    """Render any German-notation numbers in ``text`` in English convention."""
    return _GERMAN_NUMBER.sub(lambda match: match.group(0).translate(_SWAP_SEPARATORS), text)
