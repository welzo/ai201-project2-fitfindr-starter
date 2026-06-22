# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock listings dataset for secondhand items that match the user's keyword description, size, and price ceiling. Returns the matching listings sorted by relevance score so the best match comes first.

**Input parameters:**
- `description` (str): Keywords describing what the user wants, e.g. "vintage graphic tee". Used for keyword overlap scoring against each listing's title, description, and style_tags.
- `size` (str | None): Size string to filter by, e.g. "M". If provided, only listings whose `size` field contains this string (case-insensitive) are kept. Pass None to skip size filtering.
- `max_price` (float | None): Price ceiling in dollars (inclusive). Only listings with `price <= max_price` are kept. Pass None to skip price filtering.

**What it returns:**
A list of listing dicts, each containing: `id` (str), `title` (str), `description` (str), `category` (str), `style_tags` (list[str]), `size` (str), `condition` (str), `price` (float), `colors` (list[str]), `brand` (str or None), `platform` (str). The list is sorted by keyword match score, highest first. Returns `[]` (empty list) if no listings match — never raises an exception.

**What happens if it fails or returns nothing:**
The agent sets `session["error"]` to a helpful message explaining what filters were used and suggests the user try broader terms, remove the size filter, or raise their budget. The agent returns early without calling `suggest_outfit` or `create_fit_card`.

---

### Tool 2: suggest_outfit

**What it does:**
Given the thrifted item the user is considering and their existing wardrobe, asks the LLM to suggest 1–2 specific outfit combinations using pieces from the wardrobe. If the wardrobe is empty, gives general styling advice for the item instead.

**Input parameters:**
- `new_item` (dict): The listing dict for the item the user found — same shape as a listing returned by `search_listings`.
- `wardrobe` (dict): A wardrobe dict with an `items` key containing a list of wardrobe item dicts (each has `name`, `category`, `colors`, `style_tags`, `notes`). The `items` list may be empty.

**What it returns:**
A non-empty string with 1–2 outfit suggestions. If the wardrobe has items, the suggestions reference specific pieces by name (e.g., "pair with your baggy straight-leg jeans"). If the wardrobe is empty, the response gives general advice about what types of pieces work well with the new item.

**What happens if it fails or returns nothing:**
If `wardrobe['items']` is empty, the LLM is still called with a general styling prompt — the function never returns an empty string in that case. If the LLM call raises an exception, the function catches it and returns a fallback string explaining that outfit suggestions are temporarily unavailable.

---

### Tool 3: create_fit_card

**What it does:**
Takes the outfit suggestion and the item details and asks the LLM to write a 2–4 sentence Instagram/TikTok-style caption for the look — casual, first-person, specific about the vibe, and mentioning the price and platform naturally.

**Input parameters:**
- `outfit` (str): The outfit suggestion string returned by `suggest_outfit`.
- `new_item` (dict): The listing dict for the thrifted item (provides title, price, platform, condition).

**What it returns:**
A 2–4 sentence string that reads like a real OOTD social post — mentions the item name, price, and platform once each, captures the outfit vibe in specific language, and sounds different for different inputs (LLM temperature set to 1.1).

**What happens if it fails or returns nothing:**
If `outfit` is an empty or whitespace-only string, the function returns a descriptive error message string without calling the LLM. If the LLM call raises an exception, the function catches it and returns an error string rather than crashing.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**

The agent runs a linear loop with explicit branching at each step. Here's the conditional logic:

1. Parse the query with a regex pass: extract a size (look for patterns like "size M", "in M", "size XL") and a max price (look for patterns like "under $30", "less than $40", "$30 or less"). Everything else becomes the description.

2. Call `search_listings(description, size, max_price)` and store results in `session["search_results"]`. If the returned list is empty → set `session["error"]` with a message that repeats what was searched ("No listings found for '{description}'" plus which filters were active) and **return the session immediately**. Do not proceed.

3. If results are non-empty → set `session["selected_item"] = results[0]` (the top-scored result).

4. Call `suggest_outfit(selected_item, wardrobe)` and store the result in `session["outfit_suggestion"]`. This always returns a non-empty string (per the tool's contract), so no branch needed here.

5. Call `create_fit_card(outfit_suggestion, selected_item)` and store the result in `session["fit_card"]`.

6. Return the session. All three output fields are populated.

The only branch that changes the path is at step 2 (empty search results). Every other step runs unconditionally once step 2 passes.

---

## State Management

**How does information from one tool get passed to the next?**

All state lives in a single `session` dict created at the start of each `run_agent()` call. Nothing is stored globally or across sessions. The dict has these fields:

- `query` — the raw user query string
- `parsed` — dict with keys `description`, `size`, `max_price` extracted from the query
- `search_results` — list of listing dicts returned by `search_listings`
- `selected_item` — the first item from `search_results`, passed directly into `suggest_outfit`
- `wardrobe` — the wardrobe dict passed into `run_agent`, unchanged, passed directly into `suggest_outfit`
- `outfit_suggestion` — the string returned by `suggest_outfit`, passed directly into `create_fit_card`
- `fit_card` — the string returned by `create_fit_card`
- `error` — None on success; a descriptive string if the agent ended early

Tools receive their inputs as direct function arguments extracted from the session — no tool reads from the session dict directly. The session is only written by `run_agent` between calls.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Sets `session["error"]` to: "No listings found for '[description]'[with size filter][under $X]. Try broader search terms, remove the size filter, or raise your budget." Returns the session immediately without calling the next tools. |
| suggest_outfit | Wardrobe is empty | Calls the LLM with a general styling prompt: "The user has no existing wardrobe. Given this item, suggest general outfit directions and what types of pieces would work well with it." Returns the LLM response — never returns an empty string. |
| create_fit_card | Outfit input is missing or empty string | Returns the string "Couldn't generate a fit card — the outfit suggestion was empty. Try running the search again." without calling the LLM. |

---

## Architecture

```
User query (natural language)
        │
        ▼
  Parse query (regex)
  extract: description, size, max_price
        │
        ▼  session["parsed"]
  search_listings(description, size, max_price)
        │
        ├── results == []
        │       │
        │       ▼
        │   session["error"] = "No listings found..."
        │   return session  ◄─────────────────────── EARLY EXIT
        │
        │ results = [item, ...]
        ▼
  session["selected_item"] = results[0]
        │
        ▼  selected_item + wardrobe
  suggest_outfit(selected_item, wardrobe)
        │
        │  wardrobe empty? → general styling advice (still returns string)
        │
        ▼
  session["outfit_suggestion"] = "..."
        │
        ▼  outfit_suggestion + selected_item
  create_fit_card(outfit_suggestion, selected_item)
        │
        ▼
  session["fit_card"] = "..."
        │
        ▼
  return session (all fields populated)
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

For `search_listings`, I gave Claude the Tool 1 spec block from this file (input parameters, return value description, failure mode) and asked it to implement the function using `load_listings()` from `utils/data_loader.py`. Before running the output I checked that: (1) it filters by both `max_price` and `size` before scoring, (2) the size check is case-insensitive substring match, (3) it drops items with score 0, (4) it returns `[]` on no matches rather than raising. Then I ran 3 test queries to verify.

For `suggest_outfit`, I gave Claude the Tool 2 spec (inputs, return value, empty-wardrobe failure mode) and the wardrobe schema from `data/wardrobe_schema.json`. I asked for a Groq API call using `llama-3.3-70b-versatile`. Before using the output I confirmed: (1) it checks `wardrobe['items']` before building the prompt, (2) the empty-wardrobe prompt still calls the LLM rather than returning early, (3) exceptions are caught. Then I tested with both the example wardrobe and empty wardrobe.

For `create_fit_card`, I gave Claude the Tool 3 spec plus a note that temperature should be high (1.1) so outputs vary. I verified: (1) empty `outfit` string is caught before the LLM call, (2) the prompt asks for casual first-person language with price and platform, (3) calling it twice on the same input produced visibly different outputs.

**Milestone 4 — Planning loop and state management:**

I gave Claude the full Architecture diagram above plus the Planning Loop and State Management sections. I asked it to implement `run_agent()` in `agent.py` following the numbered steps. Before running I verified: (1) the empty-results branch returns early and does NOT call `suggest_outfit`, (2) `session["selected_item"]` is set to `results[0]` not a copy or re-query, (3) `session["outfit_suggestion"]` is exactly what gets passed into `create_fit_card`. I then ran the CLI test cases in `agent.py` to confirm both paths.

---

## A Complete Interaction (Step by Step)

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
The agent parses the query. Regex finds no explicit size. Regex finds "under $30" → `max_price = 30.0`. The remaining description is "vintage graphic tee". `session["parsed"] = {"description": "vintage graphic tee", "size": None, "max_price": 30.0}`.

**Step 2:**
`search_listings("vintage graphic tee", size=None, max_price=30.0)` is called. The function loads all 40 listings, filters to those with `price <= 30`, then scores each by keyword overlap between "vintage graphic tee" and each listing's title + description + style_tags. For example:
- `lst_033` "Vintage Band Tee — Faded Grey" ($19, L) scores high on "vintage" and "tee"
- `lst_002` "Y2K Baby Tee — Butterfly Print" ($18, S/M) scores on "tee"
- `lst_006` "Graphic Tee — 2003 Tour Bootleg Style" ($24, L) scores on "graphic" and "tee"

The top result is returned first. `session["search_results"]` = list of 3+ matching items.

**Step 3:**
`session["selected_item"]` = the top-scored listing, e.g. `lst_033` "Vintage Band Tee — Faded Grey, $19, Depop, condition: good". `suggest_outfit(selected_item, wardrobe)` is called. The wardrobe has 10 items. The LLM prompt includes the item details and the wardrobe list. The LLM responds with something like: "Pair this with your baggy straight-leg jeans (dark wash) and chunky white sneakers for a classic 90s look. Roll the sleeves once and tuck the front corner slightly for shape." `session["outfit_suggestion"]` = that string.

**Final output to user:**
`create_fit_card(outfit_suggestion, selected_item)` is called. The LLM writes a casual caption: "thrifted this faded band tee off depop for $19 and it was honestly made for my baggy jeans 🖤 the rolled sleeves hit different, full look is exactly the 90s vibe I needed". `session["fit_card"]` = that caption. The user sees: the listing details panel (title, price, platform, condition, size), the outfit suggestion panel, and the fit card panel.
