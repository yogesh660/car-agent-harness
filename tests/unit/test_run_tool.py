import sqlite3

from car_agent.tools import run_tool


def test_ok_result_is_plain_json(conn: sqlite3.Connection):
    out = run_tool("search_listings", conn, {"make": "Tesla", "limit": 2})
    assert out["total_matches"] > 0
    assert isinstance(out["listings"][0], dict)


def test_bad_args_become_error_message(conn: sqlite3.Connection):
    out = run_tool("search_listings", conn, {"fuel": "steam"})
    assert out["error"].startswith("Invalid arguments")
    assert "fuel" in out["error"]


def test_unknown_arg_is_rejected_with_its_name(conn: sqlite3.Connection):
    out = run_tool("search_listings", conn, {"year": 2020, "body": "suv"})
    assert "year" in out["error"]


def test_not_found_becomes_error_message(conn: sqlite3.Connection):
    out = run_tool("estimate_price", conn, {"listing_id": 999_999})
    assert "not found" in out["error"]


def test_unknown_tool(conn: sqlite3.Connection):
    assert "Unknown tool" in run_tool("buy_car", conn, {})["error"]
