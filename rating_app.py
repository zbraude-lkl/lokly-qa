"""
Lokaly.ai — QA Rating App
Collects human ratings for bootstrap weight calibration.

Flow:
  1. Rater enters full name
  2. Searches for a restaurant — Hebrew OR English
  3. Confirms visited in last 6 months
  4. Rates food quality, experience, overall (1-10)
  5. Submits → saved to qa_ratings table
  6. Loop — rate as many as they like

Hebrew search: build_he_index.py generates he_names.json (run once).
  The app loads it at startup and searches across both English and Hebrew names.
"""

import os
import json
from pathlib import Path
import streamlit as st
from supabase import create_client
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

# ── Config — supports both local .env and Streamlit Cloud secrets ─────────────
SUPABASE_URL = st.secrets.get("SUPABASE_URL") if hasattr(st, "secrets") else None
SUPABASE_URL = SUPABASE_URL or os.environ.get("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY") if hasattr(st, "secrets") else None
SUPABASE_KEY = SUPABASE_KEY or os.environ.get("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Missing SUPABASE_URL or SUPABASE_KEY — check secrets or .env")
    st.stop()
HE_NAMES_PATH = Path(__file__).parent / "he_names.json"

st.set_page_config(page_title="Lokly — דירוג מסעדות", page_icon="🍽️", layout="centered")

@st.cache_resource
def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

@st.cache_data(ttl=300)
def load_restaurants():
    sb = get_supabase()
    places = []
    offset = 0
    while True:
        page = sb.table("places").select("id,name,neighborhood,cuisine,venue_tier") \
            .eq("city", "Tel Aviv").neq("venue_tier", "cafe") \
            .order("name").limit(1000).offset(offset).execute().data
        if not page:
            break
        places.extend(page)
        if len(page) < 1000:
            break
        offset += 1000
    return places

@st.cache_data
def load_he_index():
    """Hebrew name index: { "Basta": "בסטה", ... } — built by build_he_index.py."""
    if HE_NAMES_PATH.exists():
        with open(HE_NAMES_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}

sb = get_supabase()

# ── Session state ─────────────────────────────────────────────────────────────
if "rater_name" not in st.session_state:
    st.session_state.rater_name = None
if "rated_count" not in st.session_state:
    st.session_state.rated_count = 0
if "rated_place_ids" not in st.session_state:
    st.session_state.rated_place_ids = set()   # dedup guard
if "search_key" not in st.session_state:
    st.session_state.search_key = 0
if "activity_log" not in st.session_state:
    st.session_state.activity_log = []         # list of dicts: {name, q1, q2, q3, time}

# ── Landing page ──────────────────────────────────────────────────────────────
if not st.session_state.rater_name:
    st.title("🍽️ Lokly — דירוג מסעדות")
    st.markdown("#### עוזרים לנו לבנות את המדד הטוב ביותר למסעדות בתל אביב")
    st.markdown("---")
    st.markdown("דרגו מסעדות שאכלתם בהן ב**6 החודשים האחרונים**. כל דירוג עוזר.")
    st.markdown("")

    name = st.text_input("השם המלא שלכם", placeholder="ישראל ישראלי")
    if st.button("בואו נתחיל ←", type="primary"):
        if name.strip():
            st.session_state.rater_name = name.strip()
            st.rerun()
        else:
            st.error("נא להזין שם מלא")
    st.stop()

# ── Main rating page ──────────────────────────────────────────────────────────
st.title("🍽️ Lokly — דירוג מסעדות")
st.markdown(f"שלום **{st.session_state.rater_name}** · דורגו עד כה: **{st.session_state.rated_count}** מסעדות")
st.markdown("---")

# Load restaurants — filter out already-rated ones for this session
restaurants = load_restaurants()
he_index = load_he_index()  # { "Basta": "בסטה", ... }

name_to_place = {
    p["name"]: p for p in restaurants
    if p["id"] not in st.session_state.rated_place_ids
}
names = sorted(name_to_place.keys())

# ── Search ────────────────────────────────────────────────────────────────────
st.markdown("### חפשו מסעדה שאכלתם בה")
he_ready = HE_NAMES_PATH.exists()
if he_ready:
    st.caption("חפשו בעברית או באנגלית — למשל: בסטה, מיזנון, Cafe Noir, Manta Ray")
else:
    st.caption("שמות המסעדות באנגלית — למשל: Basta, Miznon, Cafe Noir, Manta Ray")

search = st.text_input(
    "שם המסעדה",
    placeholder="בסטה / Basta, מיזנון / Miznon..." if he_ready else "e.g. Basta, Miznon, Taizu...",
    key=f"search_{st.session_state.search_key}"
)

selected_name = None
if search:
    q = search.strip().lower()
    if len(q) < 2:
        st.caption("המשיכו להקליד...")
    else:
        # Match against English names AND Hebrew names simultaneously
        def matches_query(en_name: str) -> bool:
            if q in en_name.lower():
                return True
            he_name = he_index.get(en_name, "")
            if he_name and q in he_name.lower():
                return True
            return False

        matches = [n for n in names if matches_query(n)][:8]

        # Check if query matches a venue the rater already rated this session
        all_names = sorted({p["name"] for p in restaurants})
        already_rated_matches = [
            n for n in all_names
            if matches_query(n) and name_to_place.get(n) is None
        ]

        if matches:
            # Show Hebrew name alongside English where available
            def display_label(en_name: str) -> str:
                he = he_index.get(en_name, "")
                return f"{he}  ({en_name})" if he else en_name

            display_to_en = {display_label(n): n for n in matches}
            selected_display = st.radio("בחרו מסעדה", list(display_to_en.keys()), index=None)
            if selected_display:
                selected_name = display_to_en[selected_display]
        elif already_rated_matches:
            he = he_index.get(already_rated_matches[0], "")
            display = f"{he} ({already_rated_matches[0]})" if he else already_rated_matches[0]
            st.warning(f"כבר דרגתם את **{display}** בסשן זה. בחרו מסעדה אחרת.")
        else:
            st.info("לא נמצאו מסעדות. נסו שם אחר.")

# ── Rating form ───────────────────────────────────────────────────────────────
LABELS = ['','גרוע','מתחת לממוצע','ממוצע','טוב','טוב מאוד','מצוין','יוצא דופן','יוצא מן הכלל','ברמה עולמית','מושלם']

if selected_name:
    place = name_to_place[selected_name]
    place_id = place["id"]

    # Session-level dedup guard (belt + suspenders on top of DB unique constraint)
    if place_id in st.session_state.rated_place_ids:
        st.warning(f"כבר דרגתם את {place['name']} בסשן זה. בחרו מסעדה אחרת.")
    else:
        st.markdown("---")

        # Show restaurant info
        cuisine = place.get("cuisine") or []
        if isinstance(cuisine, list):
            cuisine = ", ".join(cuisine)
        neighborhood = place.get("neighborhood") or ""
        col1, col2 = st.columns(2)
        with col1:
            he_name = he_index.get(place["name"], "")
            display_name = f"{he_name}  ({place['name']})" if he_name else place["name"]
            st.markdown(f"### {display_name}")
            if neighborhood:
                st.markdown(f"📍 {neighborhood}")
        with col2:
            if cuisine:
                st.markdown(f"🍴 {cuisine}")

        st.markdown("")

        # Recency gate
        visited = st.radio(
            "ביקרתם במסעדה זו ב-6 החודשים האחרונים?",
            ["כן", "לא"],
            index=None,
            horizontal=True
        )

        if visited == "לא":
            st.warning("תודה! דלגו למסעדה אחרת שביקרתם בה לאחרונה.")

        elif visited == "כן":
            st.markdown("---")
            st.markdown("#### שלוש שאלות — 2 דקות")

            q1 = st.select_slider(
                "1. איכות האוכל — חומרי גלם, בישול, ביצוע",
                options=list(range(1, 11)),
                value=5,
                format_func=lambda x: f"{x} — {LABELS[x]}"
            )

            q2 = st.select_slider(
                "2. חוויה ואווירה — ויב, שירות, אנרגיה, עיצוב",
                options=list(range(1, 11)),
                value=5,
                format_func=lambda x: f"{x} — {LABELS[x]}"
            )

            q3 = st.select_slider(
                "3. כולל הכול — עד כמה המסעדה טובה, נקודה?",
                options=list(range(1, 11)),
                value=5,
                format_func=lambda x: f"{x} — {LABELS[x]}"
            )

            st.markdown("")
            if st.button("שלחו דירוג ←", type="primary"):
                try:
                    sb.table("qa_ratings").insert({
                        "rater_name":         st.session_state.rater_name,
                        "place_id":           place_id,
                        "place_name":         place["name"],
                        "food_quality_score": q1,
                        "experience_score":   q2,
                        "overall_score":      q3,
                    }).execute()

                    import datetime
                    st.session_state.rated_count += 1
                    st.session_state.rated_place_ids.add(place_id)
                    st.session_state.search_key += 1
                    st.session_state.activity_log.append({
                        "name":  place["name"],
                        "q1":    q1,
                        "q2":    q2,
                        "q3":    q3,
                        "time":  datetime.datetime.now().strftime("%H:%M:%S"),
                    })
                    st.success(f"✅ {place['name']} — נשמר! המשיכו למסעדה הבאה.")
                    st.balloons()
                    st.rerun()

                except Exception as e:
                    err = str(e)
                    if "duplicate" in err.lower() or "unique" in err.lower():
                        st.session_state.rated_place_ids.add(place_id)
                        st.warning(f"כבר דרגתם את {place['name']} קודם לכן. בחרו מסעדה אחרת.")
                        st.rerun()
                    else:
                        st.error(f"שגיאה בשמירה: {e}")

st.markdown("---")
st.markdown(
    "<div style='text-align:center; color:gray; font-size:13px'>Lokly.ai — טעם מקומי, מדד אמיתי</div>",
    unsafe_allow_html=True
)

# ── Sidebar activity log ──────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📋 Activity Log")

    # DB totals — refreshes on every rerun
    try:
        all_ratings = sb.table("qa_ratings").select("rater_name, place_name, food_quality_score, experience_score, overall_score, created_at").order("created_at", desc=True).limit(50).execute().data
        total = len(sb.table("qa_ratings").select("id", count="exact").execute().data)
        unique_raters = len({r["rater_name"] for r in all_ratings})
        unique_places = len({r["place_name"] for r in all_ratings})

        st.metric("Total ratings in DB", total)
        col1, col2 = st.columns(2)
        col1.metric("Raters", unique_raters)
        col2.metric("Venues rated", unique_places)
        st.markdown("---")

        # This session
        if st.session_state.activity_log:
            st.markdown(f"**This session** ({st.session_state.rater_name or '—'})")
            for entry in reversed(st.session_state.activity_log):
                he = load_he_index().get(entry["name"], "")
                display = he if he else entry["name"]
                st.markdown(
                    f"**{display}** `{entry['time']}`  \n"
                    f"🍽️ {entry['q1']}  ✨ {entry['q2']}  ⭐ {entry['q3']}"
                )
            st.markdown("---")

        # Recent DB activity (all raters)
        if all_ratings:
            st.markdown("**Recent submissions**")
            for r in all_ratings[:10]:
                ts = r["created_at"][11:16]  # HH:MM
                st.markdown(
                    f"`{ts}` **{r['place_name']}**  \n"
                    f"_{r['rater_name']}_ — {r['food_quality_score']}/{r['experience_score']}/{r['overall_score']}"
                )
    except Exception as e:
        st.warning(f"Log error: {e}")
