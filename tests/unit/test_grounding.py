import json

import pytest

from evals.grounding import check_grounding, extract_numbers


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("costs €15,000", [15000]),
        ("kostet 15.000 €", [15000]),
        ("15 000 km", [15000]),
        ("about 18.5k", [18500]),
        ("60k km", [60000]),
        ("listing #42", [42]),
        ("from 2019", [2019]),
        ("4.5 stars", [4.5]),
        ("1,234,567", [1234567]),
        ("no numbers here", []),
    ],
)
def test_extract_numbers(text, expected):
    assert extract_numbers(text) == expected


TOOL_OUTPUT = json.dumps(
    {
        "total_matches": 23,
        "listings": [{"id": 940, "year": 2013, "mileage_km": 248632, "price_eur": 4650}],
    }
)


def test_numbers_from_tools_are_grounded():
    answer = "The cheapest is #940, a 2013 Passat with 248,632 km for €4,650."
    result = check_grounding(answer, [TOOL_OUTPUT])
    assert result.grounded
    assert result.checked == 4


def test_made_up_price_is_caught():
    result = check_grounding("Listing #940 costs €3,990.", [TOOL_OUTPUT])
    assert result.ungrounded == [3990]


def test_rounding_and_question_numbers_are_allowed():
    answer = "Yes, under your 15,000 budget: about €4,700, with roughly 249k km."
    assert check_grounding(answer, [TOOL_OUTPUT], question="diesel under 15,000").grounded


def test_differences_between_tool_numbers_are_allowed():
    estimate = json.dumps({"estimate_eur": 14250, "asking_price_eur": 18500})
    assert check_grounding("That is €4,250 above the estimate.", [estimate]).grounded


def test_small_numbers_are_skipped():
    assert check_grounding("I found 3 options, the 2nd is best.", []).checked == 0


def test_non_json_tool_output_still_counts():
    assert check_grounding("Listing 999999 does not exist.", ["Listing 999999 not found"]).grounded
