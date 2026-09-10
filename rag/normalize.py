"""Text repair for academic PDFs.

Slide decks and problem sets exported from LaTeX/PowerPoint arrive with broken
ligatures and duplicated math glyphs. Left alone they poison retrieval: the
word "efficient" is stored as "e¢ cient" and never matches a query for
"efficiency". Every mapping here was derived by inspecting the actual course
files rather than guessed from a general ligature table.
"""

from __future__ import annotations

import re
import unicodedata

# TeX Type-1 ligature slots that survive extraction as stray Latin-1 bytes.
# Evidence: "A \x85 rm produces Q" -> "A firm produces Q";
#           "an e¢ cient outcome" -> "an efficient outcome";
#           "payo⁄ s" -> "payoffs", "di⁄ erence" -> "difference".
# The ligature glyph is followed by a spurious space that must be swallowed.
_LIGATURES = (
    ("\x85", "fi"),
    ("\xa2", "ffi"),   # ¢
    ("⁄", "ff"),  # ⁄
    ("\x0c", "fi"),
    ("\x0b", "ff"),
    ("\x0e", "ffi"),
)

# cp1252 punctuation that leaked through as raw control bytes.
_PUNCT = {
    "\x91": "‘",
    "\x92": "’",
    "\x93": "“",
    "\x94": "”",
    "\x96": "–",
    "\x97": "—",
    "": " → ",  # Wingdings arrow used for "implies" throughout
    "": " ",         # Symbol-font bullet
    "": "-",
}

# Math alphanumeric block: PowerPoint equation export doubles every glyph,
# so "V ln G" comes out as "\U0001d449\U0001d449 ln \U0001d43a\U0001d43a".
# A broken ligature is always followed by a stray space, but that space is only
# spurious when the ligature sits mid-word. "e¢ cient" must close up into
# "efficient", while "payo⁄ of" must stay two words. The tail tells us which:
# a real English word after the gap means the ligature ended the previous word.
_REAL_WORDS = frozenset("""
a an and are as at be been but by can could do does for from had has have he
her his how if in into is it its may more most no not of on one or our she so
such than that the their them then there these they this to two up was we were
what when where which who will with would you your
""".split())


def _rejoin(tail: str) -> str:
    """Return the text that follows a repaired ligature, with or without a gap."""
    if not tail:
        return ""
    if tail.lower() in _REAL_WORDS:
        return " " + tail
    return tail


_MATH_RUN = re.compile(r"[\U0001D400-\U0001D7FF]+")
_DOUBLED = re.compile(r"(.)\1")


def _undouble_math(match: re.Match[str]) -> str:
    return _DOUBLED.sub(r"\1", match.group(0))


def repair(text: str) -> str:
    """Undo extraction damage. Safe to run on already-clean text."""
    if not text:
        return ""

    for glyph, replacement in _LIGATURES:
        text = re.sub(
            re.escape(glyph) + r"\s*(\w*)",
            lambda m, r=replacement: r + _rejoin(m.group(1)),
            text,
        )

    for glyph, replacement in _PUNCT.items():
        text = text.replace(glyph, replacement)

    text = _MATH_RUN.sub(_undouble_math, text)

    # NFKC folds mathematical italics down to ASCII (V, G, p) and ½ to 1/2,
    # which is what a student actually types into a search box.
    text = unicodedata.normalize("NFKC", text)

    text = text.replace("⁄", "/").replace("\xa0", " ")
    return text


_HARD_WRAP = re.compile(r"(?<=[a-z,;])\n(?=[a-z])")
_BULLET = re.compile(r"^[\s]*[•●▪–—o]\s+", re.MULTILINE)
_MANY_BLANKS = re.compile(r"\n{3,}")
_TRAILING_WS = re.compile(r"[ \t]+(?=\n)")
_MANY_SPACES = re.compile(r"[ \t]{2,}")


def tidy(text: str) -> str:
    """Normalise whitespace without destroying paragraph or bullet structure."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _HARD_WRAP.sub(" ", text)      # rejoin mid-sentence line breaks
    text = _BULLET.sub("- ", text)        # uniform bullets
    text = _MANY_SPACES.sub(" ", text)
    text = _TRAILING_WS.sub("", text)
    text = _MANY_BLANKS.sub("\n\n", text)
    # The broken apostrophe glyph leaves "Anne’ s" / "market’for"; fix both sides.
    text = re.sub(r"’\s+(s|t|re|ve|ll|d)\b", r"’\1", text)
    text = re.sub(r"(?<=[a-z])’(?=[a-z]{2,})", "’ ", text)
    return text.strip()


def clean(text: str) -> str:
    """Full pipeline: repair extraction damage, then normalise whitespace."""
    return tidy(repair(text))
