from datetime import date

import pytest

from ppwr.render import format_date


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (date(2026, 7, 31), "31.07.2026"),
        (date(2026, 1, 1), "01.01.2026"),
        (date(2026, 12, 31), "31.12.2026"),
    ],
)
def test_formats_german_dates_as_day_dot_month_dot_year(value, expected):
    assert format_date(value, "de") == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (date(2026, 7, 31), "31 July 2026"),
        (date(2026, 1, 1), "1 January 2026"),
        (date(2026, 12, 31), "31 December 2026"),
    ],
)
def test_formats_english_dates_as_day_month_name_year(value, expected):
    assert format_date(value, "en") == expected


def test_january_is_month_index_zero_not_one():
    # Regression guard for `_ENGLISH_MONTHS[value.month - 1]`: an off-by-one
    # here would silently misdate the declaration, e.g. showing "December"
    # for a January date, on a page whose date is a substantive legal claim.
    assert format_date(date(2026, 1, 15), "en").startswith("15 January")


def test_december_is_the_last_month_index_not_out_of_range():
    assert format_date(date(2026, 12, 15), "en").startswith("15 December")
