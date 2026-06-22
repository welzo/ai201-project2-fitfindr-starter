# FitFindr

A multi-tool AI agent that helps you find secondhand pieces and figure out how to style them. Describe what you're looking for, and FitFindr searches the listings, builds a complete outfit around your existing wardrobe, and writes a shareable caption for the look.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate      # Mac/Linux
pip install -r requirements.txt
```

Create a `.env` file in the project root with your Groq API key (free at [console.groq.com](https://console.groq.com)):

```
GROQ_API_KEY=your_key_here
```

Run the app:

```bash
python app.py
```

Then open the URL shown in your terminal (usually http://localhost:7860).

---

## Tool Inventory

### `search_listings(description, size, max_price)`

**Purpose:** Searches the mock listings dataset for items matching the user's keywords, optional size, and optional price ceiling.

**Parameters:**
- `description` (str) — keyword description of what the user wants (e.g., "vintage graphic tee"). Scored by substring match against each listing's title, description, style_tags, and category.
- `size` (str or None) — size string to filter by (e.g., "M"). Case-insensitive substring match against each listing's size field. Pass `None` to skip.
- `max_price` (float or None) — maximum price in dollars, inclusive. Pass `None` to skip.

**Returns:** `list[dict]` — matching listing dicts sorted by relevance score (most keyword matches first). Each dict contains: `id`, `title`, `description`, `category`, `style_tags` (list), `size`, `condition`, `price` (float), `colors` (list), `brand` (str or None), `platform`. Returns `[]` if nothing matches — never raises an exception.

---

### `suggest_outfit(new_item, wardrobe)`

**Purpose:** Given the thrifted item the user is considering and their existing wardrobe, asks the LLM to suggest 1–2 specific outfit combinations using named pieces from the wardrobe. Handles an empty wardrobe gracefully.

**Parameters:**
- `new_item` (dict) — a listing dict as returned by `search_listings`
- `wardrobe` (dict) — a wardrobe dict with an `items` key containing a list of wardrobe item dicts. May be empty.

**Returns:** `str` — a non-empty string with outfit suggestions. If the wardrobe is empty, returns general styling advice instead of outfit pairings.

---

### `create_fit_card(outfit, new_item)`

**Purpose:** Generates a short, casual Instagram/TikTok-style caption for the thrifted find and outfit. Uses a higher LLM temperature (1.1) so the output sounds different for different inputs.

**Parameters:**
- `outfit` (str) — the outfit suggestion string from `suggest_outfit`
- `new_item` (dict) — the listing dict for the thrifted item (provides title, price, platform, condition)

**Returns:** `str` — a 2–4 sentence first-person caption mentioning the item name, price, and platform naturally. If `outfit` is empty or whitespace, returns a descriptive error message string instead of calling the LLM.

---

## How the Planning Loop Works

The loop runs inside `run_agent()` in `agent.py`. It's a linear sequence with one branch that can terminate the session early.

1. **Parse the query.** Regex extracts a size mention ("size M", "in M") and a price ceiling ("under $30", "less than $40") from the raw query string. The remaining text becomes the description.

2. **Call `search_listings`.** If it returns an empty list, the agent sets `session["error"]` with a message that restates the search parameters and suggests loosening filters, then returns immediately — it does **not** proceed to `suggest_outfit` with empty input.

3. **Select the top result.** `session["selected_item"]` = `results[0]` (the highest-scoring match).

4. **Call `suggest_outfit`.** Always proceeds if step 2 found results. The wardrobe is passed in unchanged from the user's selection.

5. **Call `create_fit_card`.** Uses the string returned by `suggest_outfit` and the selected listing.

6. **Return the session.** All three output fields are populated.

The only decision point is at step 2: if `search_listings` returns nothing, the agent exits early and communicates what failed. Every other step runs unconditionally once search results exist.

---

## State Management

All state lives in a single `session` dict created fresh for each call to `run_agent()`. Nothing is shared between sessions. Each tool's output is stored in the session dict immediately after the call, and then passed directly as an argument to the next tool — tools do not read from the session dict themselves.

```
session["parsed"]           → fed into search_listings() as arguments
session["search_results"]   → top item stored as session["selected_item"]
session["selected_item"]    → passed as new_item to suggest_outfit()
session["wardrobe"]         → passed as wardrobe to suggest_outfit()
session["outfit_suggestion"] → passed as outfit to create_fit_card()
session["fit_card"]         → shown in the fit card panel
session["error"]            → shown in the listing panel if set; other panels empty
```

---

## Error Handling

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No listings match the query, size, and price filters | Sets `session["error"]` to: `No listings found for "[description]" ([filters]). Try broader search terms, remove the size filter, or raise your budget.` Returns early — `suggest_outfit` and `create_fit_card` are never called. |
| `suggest_outfit` | Wardrobe `items` list is empty | Calls the LLM with a general styling prompt instead of a wardrobe-specific one. Never returns an empty string. If the API call fails, returns a fallback message string. |
| `create_fit_card` | `outfit` argument is empty or whitespace | Returns `"Couldn't generate a fit card — the outfit suggestion was empty. Try running the search again."` without calling the LLM. |

**Concrete example from testing:**

Running `search_listings("designer ballgown", size="XXS", max_price=5)` returns `[]`. The agent's error response: *"No listings found for 'designer ballgown' (size XXS, under $5). Try broader search terms, remove the size filter, or raise your budget."* The app displays this in the listing panel and leaves the outfit and fit card panels blank.

Running `create_fit_card("", results[0])` returns `"Couldn't generate a fit card — the outfit suggestion was empty. Try running the search again."` without making any API call.

---

## Interaction Walkthrough

**User query:** `"looking for a vintage graphic tee under $30"`

**Step 1 — Tool called: `search_listings`**
- Input: `description="looking for a vintage graphic tee"`, `size=None`, `max_price=30.0`
- Why this tool: it's always the first step — we need to find a real listing before we can suggest anything
- Output: list of ~5 listings with keyword overlap to "vintage graphic tee", all priced ≤ $30. Top result: "Y2K Baby Tee — Butterfly Print, $18, depop, size S/M, condition: excellent"

**Step 2 — Tool called: `suggest_outfit`**
- Input: `new_item=<Y2K Baby Tee dict>`, `wardrobe=<example wardrobe with 10 items>`
- Why this tool: we have a selected item; now pair it with the user's actual wardrobe
- Output: "Pair this with your Baggy straight-leg jeans, dark wash and Chunky white sneakers for a casual streetwear look. Layer the Vintage black denim jacket over it for an edgy touch."

**Step 3 — Tool called: `create_fit_card`**
- Input: `outfit=<suggestion from step 2>`, `new_item=<Y2K Baby Tee dict>`
- Why this tool: we have a complete outfit; now write the shareable caption
- Output: "found this Y2K Baby Tee on depop for $18 and i literally can't stop wearing it with my baggy jeans. the butterfly print adds just enough chaos to the whole fit 🦋 chunky sneakers seal the deal."

**Final output to user:**
- **Top listing panel:** title, price, platform, size, condition, colors, description
- **Outfit idea panel:** the LLM's styling suggestions referencing wardrobe pieces by name
- **Fit card panel:** the casual caption ready to copy and post

---

## Spec Reflection

**One way planning.md helped during implementation:**

Writing out the conditional logic for the planning loop before touching any code made the branching crystal clear. Specifically, knowing that "if `search_listings` returns `[]`, return early — do NOT call `suggest_outfit`" in planning.md meant I wrote that check on the first pass and never had to debug a case where `suggest_outfit` received `None` as input. The diagram also made it obvious that all state needed to flow through the session dict rather than through function return values being passed around loosely.

**One divergence from the spec, and why:**

The planning.md spec described extracting the size using a pattern like "size M" or "in M", and initially I expected that to handle the query "designer ballgown size XXS under $5" cleanly. In practice, "XXS" wasn't in my original `valid_sizes` set, so it ended up staying in the description string instead of being parsed as a size filter. This meant the error message read "No listings found for 'designer ballgown size XXS'" rather than "No listings found for 'designer ballgown' (size XXS)". I fixed it by adding XXS to the valid sizes set, but it was a reminder that spec-writing is easier than anticipating every real query pattern.

---

## AI Usage

**Instance 1 — `search_listings` implementation:**

I gave Claude the Tool 1 spec from planning.md — specifically the parameter descriptions (description as keyword string, size as case-insensitive substring match, max_price as inclusive ceiling) and the return value description (list of dicts sorted by keyword overlap score, empty list on no match). I asked it to implement the function using `load_listings()` and to drop items with a score of 0. Before using the output I verified that: (1) the price and size filters ran before scoring so we weren't scoring items we'd discard anyway, (2) `size.lower() not in item["size"].lower()` was the correct direction for the substring match, and (3) the empty-list case returned `[]` and didn't raise. I ended up rearranging the filter order (size/price first, then score) which Claude had done in reverse.

**Instance 2 — `suggest_outfit` prompt design:**

I gave Claude the Tool 2 spec (inputs, empty-wardrobe failure mode, return value) and the `wardrobe_schema.json` content. I asked it to write both the empty-wardrobe prompt and the wardrobe-specific prompt. The generated code had the empty-wardrobe branch returning `"No wardrobe provided"` as a hardcoded string rather than calling the LLM — which violated my spec. I revised it so both branches call the LLM, just with different prompts. I also changed the temperature from 0.7 to 0.8 after noticing the outfit suggestions were a bit formulaic on repeated runs.
