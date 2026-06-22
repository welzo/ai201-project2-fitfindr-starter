"""
tests/test_tools.py

Tests for each FitFindr tool, focused on failure modes and core behavior.
Run with: pytest tests/
"""

import pytest
from tools import search_listings, create_fit_card


# ── search_listings tests ─────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []   # empty list, no exception


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_search_size_filter_case_insensitive():
    # "m" should match listings with size "M" or "S/M" or "M/L"
    results = search_listings("top", size="m", max_price=None)
    for item in results:
        assert "m" in item["size"].lower()


def test_search_result_fields():
    results = search_listings("jeans", size=None, max_price=None)
    assert len(results) > 0
    item = results[0]
    # check all expected fields are present
    for field in ("id", "title", "description", "category", "style_tags",
                  "size", "condition", "price", "colors", "platform"):
        assert field in item, f"Missing field: {field}"


def test_search_returns_list_not_exception():
    # completely nonsense query should return [] without raising
    try:
        results = search_listings("xyzzy foobarbaz", size="ZZZZZ", max_price=0.01)
        assert results == []
    except Exception as e:
        pytest.fail(f"search_listings raised an exception: {e}")


# ── create_fit_card tests ─────────────────────────────────────────────────────

def test_fit_card_empty_outfit_returns_error_string():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    result = create_fit_card("", results[0])
    assert isinstance(result, str)
    assert len(result) > 0
    # should be an error message, not raise


def test_fit_card_whitespace_outfit_returns_error_string():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    result = create_fit_card("   ", results[0])
    assert isinstance(result, str)
    assert "empty" in result.lower() or "couldn't" in result.lower()


def test_fit_card_no_exception_on_valid_input():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert len(results) > 0
    # with a valid outfit string it should return something without crashing
    try:
        result = create_fit_card("Pair with baggy jeans and chunky sneakers.", results[0])
        assert isinstance(result, str)
        assert len(result) > 0
    except Exception as e:
        pytest.fail(f"create_fit_card raised an exception: {e}")
