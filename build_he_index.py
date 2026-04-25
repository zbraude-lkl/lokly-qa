"""
Build a Hebrew name index for all Tel Aviv venues (cafes excluded).
Calls Claude once per batch of 50 venues, saves result to he_names.json.
he_names.json: { "Basta": "בסטה", "Miznon": "מיזנון", ... }

Run once (or re-run when new venues are added):
  python3 qa_app/build_he_index.py
"""

import os, json, time
from pathlib import Path
from typing import List
from dotenv import load_dotenv
from supabase import create_client
import anthropic

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

OUTPUT = "/Users/zeev.braude/lokaly/qa_app/he_names.json"
BATCH  = 50

def load_existing():
    try:
        with open(OUTPUT, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def fetch_venues():
    places, offset = [], 0
    while True:
        page = sb.table("places").select("name") \
            .eq("city", "Tel Aviv").neq("venue_tier", "cafe") \
            .order("name").limit(1000).offset(offset).execute().data
        if not page: break
        places.extend(page)
        if len(page) < 1000: break
        offset += 1000
    return [p["name"] for p in places]

def translate_batch(names: List[str]) -> dict:
    """Ask Claude for Hebrew names for a batch of venue names."""
    prompt = (
        "You are a local Tel Aviv food expert. "
        "For each restaurant name below, provide the most natural Hebrew name "
        "that an Israeli person would use when searching for it. "
        "This could be a Hebrew transliteration (e.g. Basta → בסטה), "
        "the actual Hebrew name if the restaurant uses one, "
        "or a phonetic Hebrew spelling. "
        "Return ONLY a JSON object: {\"English Name\": \"שם עברי\", ...}. "
        "No explanation, no markdown, just raw JSON.\n\n"
        "Restaurants:\n" + "\n".join(f"- {n}" for n in names)
    )
    msg = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )
    text = msg.content[0].text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())

def run():
    existing = load_existing()
    all_names = fetch_venues()
    missing = [n for n in all_names if n not in existing]
    print(f"Total venues: {len(all_names)} | Already indexed: {len(existing)} | To process: {len(missing)}")

    if not missing:
        print("✅ Index is up to date.")
        return

    result = dict(existing)
    batches = [missing[i:i+BATCH] for i in range(0, len(missing), BATCH)]

    for i, batch in enumerate(batches, 1):
        print(f"  Batch {i}/{len(batches)} ({len(batch)} venues)...", end=" ", flush=True)
        try:
            translated = translate_batch(batch)
            result.update(translated)
            print(f"✓ ({len(translated)} returned)")
        except Exception as e:
            print(f"❌ {e}")
            # Save progress so far before giving up
            break
        if i < len(batches):
            time.sleep(1)  # be polite to the API

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Saved {len(result)} Hebrew names to {OUTPUT}")

if __name__ == "__main__":
    run()
