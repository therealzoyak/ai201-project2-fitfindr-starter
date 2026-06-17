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
Searches the mock listings dataset for secondhand items matching a text description, optionally filtered by size and maximum price, and returns the matches ranked by relevance to the description.

**Input parameters:**
- `description` (str): keyword/text query describing what the user wants (e.g. "vintage graphic tee")
- `size` (str | None): size to filter by; case-insensitive, matches if it's a substring of the listing's size field (so "M" matches "S/M"); None skips size filtering
- `max_price` (float | None): inclusive price ceiling; None skips price filtering

**What it returns:**
A list of listing dicts (best matches first). Each one has `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`. If nothing matches, it just returns an empty list.

**What happens if it fails or returns nothing:**
If the list comes back empty, the agent shouldn't crash or keep going — it sets an error message telling the user to try loosening their size or price filter, and stops there. It does NOT call `suggest_outfit` with nothing to work with.

---

### Tool 2: suggest_outfit

**What it does:**
Takes a thrifted item and the user's wardrobe, and asks an LLM to suggest 1-2 complete outfits pairing the new item with pieces the user already owns. If the wardrobe is empty, it gives general styling advice for the item instead.

**Input parameters:**
- `new_item` (dict): the listing dict for the item being considered (title, category, colors, style_tags, etc.)
- `wardrobe` (dict): a dict with an `items` key containing a list of wardrobe item dicts (name, category, colors, style_tags, notes) — may be empty

**What it returns:**
A non-empty string with outfit suggestions or general styling advice.

**What happens if it fails or returns nothing:**
If the wardrobe is empty, it gives general styling tips for the new item instead of specific outfit combos. If the LLM call fails or returns nothing, the tool returns a fallback string with generic styling advice rather than an empty string or an exception.

---

### Tool 3: create_fit_card

**What it does:**
Generates a short, shareable Instagram/TikTok-style caption for the thrifted item and outfit, mentioning the item name, price, and platform naturally.

**Input parameters:**
- `outfit` (str): the outfit suggestion string returned by `suggest_outfit`
- `new_item` (dict): the listing dict for the item being featured

**What it returns:**
A 2-4 sentence caption string, written casually like a real OOTD post — not a product description. Uses a higher LLM temperature so it sounds different each time.

**What happens if it fails or returns nothing:**
If `outfit` is empty/missing, or `new_item` is missing, the tool returns a descriptive error message string instead of raising an exception or returning an empty string.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**

The agent runs a fixed sequence of steps, but each step checks the result of the previous one before continuing — it doesn't blindly run all three tools regardless of outcome.

1. Parse the user's query into `description`, `size`, and `max_price` (using simple string/keyword extraction). Store in `session["parsed"]`.
2. Call `search_listings(description, size, max_price)`.
   - If `results` is empty: set `session["error"]` to a message telling the user to try a broader description or loosen their size/price filter, and return the session immediately. Do not call `suggest_outfit` or `create_fit_card`.
   - If `results` is non-empty: set `session["selected_item"] = results[0]` and continue.
3. Call `suggest_outfit(selected_item, wardrobe)` and store the result in `session["outfit_suggestion"]`.
4. Call `create_fit_card(outfit_suggestion, selected_item)` and store the result in `session["fit_card"]`.
5. Return the session.

The branch point is step 2 — that's where the agent's behavior actually changes based on what it got back. Everything else proceeds in order because each subsequent tool depends on the previous tool's output.

---

## State Management

**How does information from one tool get passed to the next?**

The `_new_session()` dict is the single source of truth for the whole interaction. Each step writes its output into a specific field, which the next step reads from:

- `session["parsed"]` stores the extracted `description`, `size`, and `max_price` from the query — used as input to `search_listings`.
- `session["search_results"]` stores the full list returned by `search_listings`.
- `session["selected_item"]` stores `search_results[0]` — this is passed directly into both `suggest_outfit` and `create_fit_card`, so the user never has to re-specify the item.
- `session["wardrobe"]` is set once at the start (passed in by the caller) and read by `suggest_outfit`.
- `session["outfit_suggestion"]` stores the string from `suggest_outfit`, which is then passed into `create_fit_card`.
- `session["fit_card"]` stores the final caption.
- `session["error"]` stays `None` unless a tool fails or returns nothing — if set, the loop returns early and `outfit_suggestion`/`fit_card` remain `None`.

No global state is used — everything lives in this one dict for the duration of a single `run_agent()` call.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Set `session["error"]` to "No listings matched your search — try a broader description or loosen your size/price filters." Return the session immediately without calling `suggest_outfit` or `create_fit_card`. |
| suggest_outfit | Wardrobe is empty | The tool detects this and asks the LLM for general styling advice instead of outfit pairings, returning a non-empty string. The agent proceeds normally with this string. |
| create_fit_card | Outfit input is missing or incomplete | The tool returns a descriptive error message string (not an exception, not an empty string). The agent stores this in `session["fit_card"]` as-is — the user sees the error message in place of a caption. |

---

## Architecture
User query
    │  "vintage graphic tee under $30, size M..."
    ▼
Planning Loop ────────────────────────────────────────────────────────────┐
    │                                                                      │
    ├─► Parse query → description, size, max_price                        │
    │       │                                                              │
    │       ▼                                                              │
    │   Session: parsed = {description, size, max_price}                  │
    │       │                                                              │
    ├─► search_listings(description, size, max_price)                     │
    │       │                                                              │
    │       │ results = []                                                │
    │       ├──► [ERROR] "No listings matched — try a broader             │
    │       │            description or loosen size/price" → return       │
    │       │                                                              │
    │       │ results = [item, ...]                                       │
    │       ▼                                                              │
    │   Session: search_results = results                                  │
    │   Session: selected_item = results[0]                                │
    │       │                                                              │
    ├─► suggest_outfit(selected_item, wardrobe)                            │
    │       │                                                              │
    │       │ wardrobe["items"] = []                                       │
    │       │   → LLM gives general styling advice                         │
    │       │ wardrobe["items"] = [w, ...]                                 │
    │       │   → LLM suggests specific outfit combos                      │
    │       ▼                                                              │
    │   Session: outfit_suggestion = "..."                                 │
    │       │                                                              │
    └─► create_fit_card(outfit_suggestion, selected_item)                 │
            │                                                              │
            │ outfit_suggestion empty/missing                              │
            │   → return descriptive error string (no exception)          │
            │ outfit_suggestion present                                    │
            │   → LLM generates 2-4 sentence caption                       │
            ▼                                                              │
        Session: fit_card = "..."                                          │
            │                                                              │
            ▼                                                              │
        Return session ◄───────────────────────────────────────────────────
                         (error path also returns session here, with
                          session["error"] set and outfit_suggestion/
                          fit_card left as None)

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**

For `search_listings`, I'll give Claude the Tool 1 block from planning.md (inputs, return value, failure mode) and ask it to implement the function using `load_listings()` from the data loader. I'll verify the generated code filters by all three parameters and handles the empty-results case, then test it with 3 queries: one that matches, one with a price filter that returns nothing, and one without a size specified.

For `suggest_outfit`, I'll give Claude the Tool 2 block and ask it to implement the function using the Groq client. I'll verify it handles both the empty-wardrobe and populated-wardrobe cases, then test it with `get_example_wardrobe()` and `get_empty_wardrobe()`.

For `create_fit_card`, I'll give Claude the Tool 3 block and ask it to implement the function. I'll verify it guards against empty outfit input and uses a higher temperature, then run it twice with the same input to confirm the output varies.

**Milestone 4 — Planning loop and state management:**

I'll give Claude the Planning Loop, State Management, Architecture, and Error Handling sections of planning.md and ask it to implement `run_agent()` in `agent.py`. I'll verify the generated code matches the session field names exactly, handles the empty-results early return, and doesn't call downstream tools when `session["error"]` is set. I'll test using both the happy path and the no-results path already set up in the `if __name__ == "__main__"` block in `agent.py`.

---

## A Complete Interaction (Step by Step)

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
The agent parses the query and extracts `description="vintage graphic tee"`, `size=None` (no size mentioned), `max_price=30.0`. It calls `search_listings("vintage graphic tee", size=None, max_price=30.0)`. The function filters listings to those under $30, scores by keyword overlap, and returns the top matches — e.g. `[{"title": "Faded Band Tee", "price": 22.0, "platform": "depop", ...}, ...]`. The agent stores this in `session["search_results"]` and sets `session["selected_item"] = results[0]`.

**Step 2:**
The agent calls `suggest_outfit(selected_item=<Faded Band Tee dict>, wardrobe=get_example_wardrobe())`. The wardrobe is non-empty, so the LLM suggests specific outfit combos using named wardrobe pieces. Returns something like: "Pair this faded band tee with your baggy straight-leg jeans and white ribbed tank underneath for a classic 90s layered look. Add chunky sneakers and keep everything loose for that effortless streetwear vibe." Stored in `session["outfit_suggestion"]`.

**Step 3:**
The agent calls `create_fit_card(outfit=<suggestion string>, new_item=<Faded Band Tee dict>)`. The LLM generates a casual 2-4 sentence caption mentioning the item, $22 price, and depop naturally. Returns something like: "thrifted this faded band tee off depop for $22 and it just works 🖤 styled it with my baggy jeans and chunky sneakers for that easy 90s feel — full look in my stories." Stored in `session["fit_card"]`.

**Final output to user:**
The session returns with `session["error"] = None`, `session["outfit_suggestion"]` containing the styling advice, and `session["fit_card"]` containing the caption. The user sees both.
