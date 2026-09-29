"""Text normalisation shared by the grounding guard, search and comparisons (plan §21.4).

Phase 0 showed LLMs emit typographic characters — `INV‑1042` with U+2011, `67 %` with U+202F —
so exact comparisons against tool output fail unless both sides are normalised.
"""

from __future__ import annotations

import re

# Code points written explicitly so reviewers can see exactly what is mapped.
_HYPHENS = (0x2010, 0x2011, 0x2012)  # hyphen, non-breaking hyphen, figure dash
_SPACES = (0x00A0, 0x2007, 0x2009, 0x202F)  # no-break, figure, thin, narrow no-break space
_TYPOGRAPHY = str.maketrans({**{chr(c): "-" for c in _HYPHENS}, **{chr(c): " " for c in _SPACES}})
_SPACE_BEFORE_PERCENT = re.compile(r"(\d) %")


def normalise_typography(text: str) -> str:
    """Map typographic hyphens/spaces to ASCII and join `67 %` → `67%`. U+2212 minus is kept."""
    return _SPACE_BEFORE_PERCENT.sub(r"\1%", text.translate(_TYPOGRAPHY))
