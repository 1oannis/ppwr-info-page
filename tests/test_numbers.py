import pytest

from ppwr.numbers import localise


@pytest.mark.parametrize(
    ("german", "english"),
    [
        ("1.714", "1,714"),
        ("ca. 1.714 g pro Verpackung", "ca. 1,714 g pro Verpackung"),
        ("1.190 x 430 x 270 mm", "1,190 x 430 x 270 mm"),
        ("1.022 x 592 x 140 mm", "1,022 x 592 x 140 mm"),
        ("2,5", "2.5"),
        ("1.714,5", "1,714.5"),
    ],
)
def test_converts_german_numeric_notation(german, english):
    assert localise(german) == english


@pytest.mark.parametrize(
    "unchanged",
    [
        "C 1-4003 b/b / VDW 1.40 C",
        "BC 2-2005 b/b / VDW 2.20 BC",
        "Wellkiste (FEFCO 0201)",
        "72805 Lichtenstein",
        "Wilhelmstr. 162",
        "170 g Kraftliner braun",
        "592 x 462 x 384 mm",
        "600x400x200",
    ],
)
def test_leaves_technical_notation_alone(unchanged):
    assert localise(unchanged) == unchanged


def test_is_idempotent_on_already_english_notation():
    assert localise("1,714") == "1,714"
