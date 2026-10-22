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
    assert score.arg_mismatches


def test_missing_tool_fails():
    score = score_case(CASE, [("estimate_price", {"listing_id": 1})])
    assert score.missing_tools == ["search_listings"]


def test_list_order_does_not_matter():
    case = {
        "id": "c",
        "expected_tools": ["compare_listings"],
        "expected_args": {"compare_listings": {"listing_ids": [5, 6, 7]}},
    }
    assert score_case(case, [("compare_listings", {"listing_ids": [7, 5, 6]})]).passed


def test_no_tool_case():
    case = {"id": "n", "expected_tools": [], "expected_args": {}}
    assert score_case(case, []).passed
    assert score_case(case, [("search_listings", {})]).unexpected_tool_use
