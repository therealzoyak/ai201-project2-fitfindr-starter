# FitFindr

FitFindr is a multi-tool AI agent that helps you find secondhand clothing and figure out how to wear it. You describe what you're looking for, and it searches mock thrift listings, suggests outfits based on your wardrobe, and generates a shareable caption — handling failures gracefully at each step.

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file in the repo root with your Groq API key (free at [console.groq.com](https://console.groq.com)): GROQ_API_KEY=your_key_here
Run the app:
```bash
python app.py
```

Open the URL shown in your terminal (usually http://localhost:7860).

## Tool Inventory

### `search_listings(description, size, max_price)`
- **Inputs:** `description` (str) — keyword query; `size` (str | None) — case-insensitive substring match against the listing's size field; `max_price` (float | None) — inclusive price ceiling
- **Output:** List of matching listing dicts sorted by relevance score, or an empty list if nothing matches
- **Purpose:** Filters and ranks the 40 mock listings against the user's query — no LLM involved, just keyword scoring

### `suggest_outfit(new_item, wardrobe)`
- **Inputs:** `new_item` (dict) — the listing being considered; `wardrobe` (dict) — a dict with an `items` key containing the user's wardrobe, may be empty
- **Output:** A non-empty string with 1-2 outfit suggestions using named wardrobe pieces, or general styling advice if the wardrobe is empty
- **Purpose:** Uses Groq's LLM to generate outfit ideas grounded in what the user already owns

### `create_fit_card(outfit, new_item)`
- **Inputs:** `outfit` (str) — the suggestion string from `suggest_outfit`; `new_item` (dict) — the listing being featured
- **Output:** A 2-4 sentence casual caption mentioning the item name, price, and platform each once — written like a real OOTD post
- **Purpose:** Uses Groq's LLM at temperature 1.0 to generate a caption that sounds like something worth posting, and varies each time

## Planning Loop

The agent runs a conditional sequence — not a fixed pipeline that blindly calls all three tools regardless of what comes back.

1. **Parse** the user's query using regex to extract `description`, `size`, and `max_price`. Store in `session["parsed"]`.
2. **Call `search_listings`** with the parsed parameters.
   - If results are empty: set `session["error"]` and return immediately — `suggest_outfit` and `create_fit_card` never get called.
   - If results are non-empty: set `session["selected_item"] = results[0]` and keep going.
3. **Call `suggest_outfit`** with the selected item and wardrobe. Store result in `session["outfit_suggestion"]`.
4. **Call `create_fit_card`** with the outfit suggestion and selected item. Store result in `session["fit_card"]`.
5. **Return the session.**

The real branch point is step 2 — that's where the agent's behavior actually changes based on what it got back. If nothing matched the search, the agent stops and tells you what to try differently rather than passing empty input downstream.

## State Management

Everything lives in a single session dict initialized at the start of each `run_agent()` call. Each tool writes its output to a specific field, which the next tool reads from:

| Field | Set by | Read by |
|-------|--------|---------|
| `session["parsed"]` | query parser | `search_listings` |
| `session["search_results"]` | `search_listings` | agent loop |
| `session["selected_item"]` | agent loop | `suggest_outfit`, `create_fit_card` |
| `session["wardrobe"]` | `_new_session()` | `suggest_outfit` |
| `session["outfit_suggestion"]` | `suggest_outfit` | `create_fit_card` |
| `session["fit_card"]` | `create_fit_card` | returned to user |
| `session["error"]` | agent loop | returned to user |

No global state, no re-prompting the user between steps. One dict, one run.

## Error Handling

| Tool | Failure mode | What happens |
|------|-------------|--------------|
| `search_listings` | No listings match | Sets `session["error"]` to a message telling the user to try a broader description or loosen their size/price filters. Returns immediately without calling the other tools. |
| `suggest_outfit` | Wardrobe is empty | Detects the empty `wardrobe["items"]` list and asks the LLM for general styling advice instead of specific combos. Returns a useful string either way — the agent keeps going normally. |
| `create_fit_card` | Outfit string is empty | Returns a descriptive error message string rather than crashing. Agent stores it in `session["fit_card"]` and returns it to the user. |

**Triggered empty wardrobe:**
```python
suggest_outfit(results[0], get_empty_wardrobe())
# → "The Y2K Baby Tee with a butterfly print is a cute and playful piece. Given its vintage
#    and cottagecore style tags, here are some styling ideas: high-waisted jeans or mom jeans
#    for a casual retro look, flowy midi skirts in pastel shades..."
```

**Triggered empty outfit guard:**
```python
create_fit_card('', results[0])
# → "Error: no outfit suggestion provided — run suggest_outfit first to generate styling ideas."
```

## Spec Reflection

The implementation followed planning.md pretty closely. The main thing that changed was query parsing — the spec said "simple string/keyword extraction" but regex ended up being the cleaner choice for reliably pulling size and price out of varied natural language input like "under $30" vs "max $30" or "size M" vs "size: M".

The empty wardrobe path also worked better than expected — the LLM gave detailed, well-organized general styling advice even without any wardrobe context, so the fallback string never needed to fire in practice.

## AI Tool Usage

**Instance 1 — `search_listings`:**
I gave Claude the Tool 1 block from planning.md — inputs, return value, and failure mode — and asked it to implement the function using `load_listings()` from the data loader. I checked that the output filtered by all three parameters and handled the empty-results case before running it, then tested it against three different queries.

**Instance 2 — `run_agent()` planning loop:**
I gave Claude the Planning Loop, State Management, Error Handling, and Architecture sections from planning.md including the full ASCII diagram. The generated code matched the session field names and conditional logic from the spec. I verified the empty-results branch worked correctly and that it wasn't calling all three tools unconditionally before trusting it.

## What's Included
ai201-project2-fitfindr-starter/

├── data/

│   ├── listings.json          # 40 mock secondhand listings

│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe

├── tests/

│   └── test_tools.py          # pytest tests for all three tools

├── utils/

│   └── data_loader.py         # Helper functions for loading the data

├── agent.py                   # Planning loop and session management

├── app.py                     # Gradio UI

├── tools.py                   # Three tool implementations

├── planning.md                # Completed planning document

└── requirements.txt           # Python dependencies
