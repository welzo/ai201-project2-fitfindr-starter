"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


def _parse_query(query: str) -> dict:
    """
    Extract description, size, and max_price from the user's natural language query.

    Uses regex patterns to find size (e.g., "size M", "in M") and price
    (e.g., "under $30", "less than $40") mentions, then treats what remains
    as the description keywords.
    """
    text = query.strip()

    # extract max_price: "under $30", "less than $40", "$30 or less", "max $25"
    price_match = re.search(
        r"(?:under|less than|below|max|at most|for)\s*\$?(\d+(?:\.\d+)?)"
        r"|\$?(\d+(?:\.\d+)?)\s*(?:or less|max|top)",
        text,
        re.IGNORECASE,
    )
    max_price = None
    if price_match:
        raw = price_match.group(1) or price_match.group(2)
        max_price = float(raw)
        text = text[:price_match.start()] + text[price_match.end():]

    # extract size: "size M", "in size M", "in M", "(size XL)", "size XS/S"
    size_match = re.search(
        r"(?:size\s+|in\s+size\s+|in\s+)([A-Za-z0-9]{1,6}(?:/[A-Za-z0-9]{1,4})?)\b",
        text,
        re.IGNORECASE,
    )
    size = None
    if size_match:
        candidate = size_match.group(1).upper()
        # only treat it as a size if it looks like a clothing size
        valid_sizes = {"XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL", "S/M", "M/L", "L/XL", "L/XL"}
        if candidate in valid_sizes or re.match(r"^W\d{2}$", candidate):
            size = candidate
            text = text[:size_match.start()] + text[size_match.end():]

    # what's left becomes the description — strip common filler words
    description = re.sub(r"\b(looking for|i want|i need|find me|i'm after|get me)\b", "", text, flags=re.IGNORECASE)
    description = re.sub(r"\s+", " ", description).strip(" ,.")

    return {
        "description": description or query,
        "size": size,
        "max_price": max_price,
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.
    """
    # Step 1: initialize session
    session = _new_session(query, wardrobe)

    # Step 2: parse the query into structured parameters
    parsed = _parse_query(query)
    session["parsed"] = parsed

    description = parsed["description"]
    size = parsed["size"]
    max_price = parsed["max_price"]

    # Step 3: search for listings
    results = search_listings(description, size=size, max_price=max_price)
    session["search_results"] = results

    if not results:
        # build a helpful error message that reflects which filters were active
        filters_used = []
        if size:
            filters_used.append(f"size {size}")
        if max_price is not None:
            filters_used.append(f"under ${max_price:.0f}")

        filter_str = f" ({', '.join(filters_used)})" if filters_used else ""
        session["error"] = (
            f"No listings found for \"{description}\"{filter_str}. "
            "Try broader search terms, remove the size filter, or raise your budget."
        )
        return session

    # Step 4: select the top result
    session["selected_item"] = results[0]

    # Step 5: get outfit suggestions
    outfit = suggest_outfit(session["selected_item"], wardrobe)
    session["outfit_suggestion"] = outfit

    # Step 6: generate the fit card
    fit_card = create_fit_card(outfit, session["selected_item"])
    session["fit_card"] = fit_card

    # Step 7: return the completed session
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
