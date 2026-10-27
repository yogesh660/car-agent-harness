import pytest

from evals.scoring import score_case

CASE = {
    "id": "x",
    "expected_tools": ["search_listings"],
    "expected_args": {"search_listings": {"make": "Volkswagen", "max_price_eur": 15000}},
}


def test_exact_match_passes():
    calls = [("search_listings", {"make": "Volkswagen", "max_price_eur": 15000})]
    assert score_case(CASE, calls).passed


def test_extra_args_and_aliases_are_fine():
    calls = [("search_listings", {"make": "vw", "max_price_eur": 15000.0, "limit": 10})]
    assert score_case(CASE, calls).passed


def test_one_good_call_among_several_is_enough():
    calls = [
        ("search_listings", {"make": "BMW"}),
        ("search_listings", {"make": "Volkswagen", "max_price_eur": 15000}),
    ]
    assert score_case(CASE, calls).passed


def test_wrong_value_fails():
    score = score_case(CASE, [("search_listings", {"make": "Volkswagen", "max_price_eur": 20000})])
    assert not score.passed
    assert score.tools_ok
    assert not score.args_ok


def test_missing_tool_fails():
    score = score_case(CASE, [("estimate_price", {"listing_id": 1})])
    assert score.missing_tools == ["search_listings"]
    assert not score.tools_ok


def test_omitted_arg_matches_when_expected_is_the_default():
    case = {
        "id": "d",
        "expected_tools": ["search_listings"],
        "expected_args": {"search_listings": {"fuel": "electric", "sort_by": "price_asc"}},
    }
    assert score_case(case, [("search_listings", {"fuel": "electric"})]).passed
    # but a non-default expectation still needs the arg
    case["expected_args"]["search_listings"]["sort_by"] = "year_desc"
    assert not score_case(case, [("search_listings", {"fuel": "electric"})]).passed


@pytest.mark.parametrize(
    ("expected", "actual", "ok"),
    [
        ("Octavia", "Octavia Combi", True),
        ("Octavia Combi", "octavia", True),
        ("Golf", "Passat Variant", False),
    ],
)
def test_model_names_match_by_containment(expected, actual, ok):
    case = {
        "id": "m",
        "expected_tools": ["search_listings"],
        "expected_args": {"search_listings": {"model": expected}},
    }
    assert score_case(case, [("search_listings", {"model": actual})]).passed is ok


def test_german_city_name_matches():
    case = {
        "id": "c",
        "expected_tools": ["search_listings"],
        "expected_args": {"search_listings": {"city": "Munich"}},
    }
    assert score_case(case, [("search_listings", {"city": "München"})]).passed


def test_list_order_does_not_matter():
    case = {
        "id": "c",
        "expected_tools": ["compare_listings"],
        "expected_args": {"compare_listings": {"listing_ids": [5, 6, 7]}},
    }
    assert score_case(case, [("compare_listings", {"listing_ids": [7, 5, 6]})]).passed


@pytest.mark.parametrize(
    ("answer", "ok"),
    [
        ("Listing #43 is cheaper.", True),
        ("Go for 43, it is cheaper.", True),
        ("Listing #430 is cheaper.", False),
        ("It costs 4.43k", False),
        ("No clear winner.", False),
    ],
)
def test_answer_mentions(answer, ok):
    case = {
        "id": "a",
        "expected_tools": ["compare_listings"],
        "expected_args": {},
        "answer_mentions": [43],
    }
    score = score_case(case, [("compare_listings", {"listing_ids": [42, 43]})], answer)
    assert score.passed is ok


def test_no_tool_case():
    case = {"id": "n", "expected_tools": [], "expected_args": {}}
    assert score_case(case, []).passed
    assert score_case(case, [("search_listings", {})]).unexpected_tool_use
