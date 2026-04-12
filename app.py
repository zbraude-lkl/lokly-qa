"""
Lokly.ai — QA Chat Interface
Ask Claude anything about the 80 Tel Aviv restaurants.
"""

import streamlit as st
import anthropic
from supabase import create_client
import os

# ─── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL = "https://gezolttqdzlkbniztadu.supabase.co"
SUPABASE_KEY = "sb_publishable_pDyfJo1L5H7GIAfBgp3sbg_oQTtZm3J"
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "lokly2026")
ANTHROPIC_KEY = st.secrets.get("ANTHROPIC_API_KEY", "")

# ─── Password gate ──────────────────────────────────────────────────────────────
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("Lokly.ai — Restaurant QA")
        st.markdown("##### Enter password to continue")
        pwd = st.text_input("Password", type="password")
        if st.button("Enter"):
            if pwd == APP_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Wrong password")
        return False
    return True

# ─── Load restaurant DNA from Supabase ─────────────────────────────────────────
@st.cache_data(ttl=300)
def load_restaurant_context():
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    places = sb.table("places").select("*").eq("city", "Tel Aviv").order("name").execute().data

    lines = []
    for p in places:
        lines.append(f"\n{'='*50}")
        lines.append(f"RESTAURANT: {p.get('name', '')}")
        lines.append(f"{'='*50}")

        if p.get("address"):
            lines.append(f"Address: {p['address']}")
        if p.get("neighborhood"):
            lines.append(f"Neighborhood: {p['neighborhood']}")
        if p.get("cuisine"):
            lines.append(f"Cuisine: {p['cuisine']}")
        if p.get("place_category"):
            lines.append(f"Category: {p['place_category']}")
        if p.get("google_rating"):
            lines.append(f"Google Rating: {p['google_rating']} ({p.get('google_review_count', '?')} reviews)")
        if p.get("chef_name"):
            lines.append(f"Chef: {p['chef_name']}")

        # Vibe & DNA
        if p.get("vibe_summary"):
            lines.append(f"Vibe: {p['vibe_summary']}")
        if p.get("noise_level"):
            lines.append(f"Noise level: {p['noise_level']}/5")
        if p.get("energy_level"):
            lines.append(f"Energy level: {p['energy_level']}/5")
        if p.get("formality"):
            lines.append(f"Formality: {p['formality']}/5")
        if p.get("crowd_age_range"):
            lines.append(f"Crowd age: {p['crowd_age_range']}")
        if p.get("crowd_type"):
            lines.append(f"Crowd type: {p['crowd_type']}")
        if p.get("music_presence") is not None:
            lines.append(f"Music: {'Yes' if p['music_presence'] else 'No'}{' — ' + p['music_style'] if p.get('music_style') else ''}")
        if p.get("service_style"):
            lines.append(f"Service: {p['service_style']}")

        # Occasions
        occasions = []
        if p.get("first_date_safe"):
            occasions.append("first date")
        if p.get("celebration_worthy"):
            occasions.append("celebrations")
        if p.get("power_lunch"):
            occasions.append("power lunch")
        if occasions:
            lines.append(f"Good for: {', '.join(occasions)}")
        if p.get("occasion_fit"):
            lines.append(f"Occasion fit: {p['occasion_fit']}")

        # Food
        if p.get("destination_dish"):
            lines.append(f"Destination dish: {p['destination_dish']}")
        if p.get("signature_dishes"):
            lines.append(f"Signature dishes: {', '.join(p['signature_dishes'])}")
        if p.get("food_identity"):
            lines.append(f"Food identity: {', '.join(p['food_identity'])}")

        # Alcohol
        if p.get("alcohol_focus"):
            lines.append(f"Alcohol focus: {p['alcohol_focus']}")
        if p.get("wine_list_quality"):
            lines.append(f"Wine list: {p['wine_list_quality']}")
        if p.get("natural_wine"):
            lines.append(f"Natural wine: Yes")
        if p.get("cocktail_program"):
            lines.append(f"Cocktail program: Yes")
        if p.get("serves_alcohol") is False:
            lines.append(f"Alcohol: None")

        # Practical
        if p.get("seating_location"):
            lines.append(f"Seating: {', '.join(p['seating_location'])}")
        if p.get("outdoor_type"):
            lines.append(f"Outdoor type: {p['outdoor_type']}")
        if p.get("has_private_room"):
            lines.append(f"Private room: Yes")
        if p.get("reservations_required") is not None:
            lines.append(f"Reservations: {'Required' if p['reservations_required'] else 'Not required'}")
        if p.get("open_shabbat") is not None:
            lines.append(f"Open Shabbat: {'Yes' if p['open_shabbat'] else 'No'}")
        if p.get("kosher") is not None:
            lines.append(f"Kosher: {'Yes' if p['kosher'] else 'No'}")
        if p.get("happy_hour"):
            lines.append(f"Happy hour: Yes")
        if p.get("has_bar"):
            lines.append(f"Has bar: Yes")
        if p.get("parking"):
            lines.append(f"Parking: Yes")
        if p.get("valet_parking"):
            lines.append(f"Valet parking: Yes")

        # Visual DNA
        if p.get("visual_dna_style"):
            lines.append(f"Visual style: {p['visual_dna_style']}")
        if p.get("lighting_type"):
            lines.append(f"Lighting: {p['lighting_type']}")
        if p.get("dress_code_vibe"):
            lines.append(f"Dress code vibe: {p['dress_code_vibe']}")
        if p.get("instagram_worthy") is not None:
            lines.append(f"Instagram worthy: {'Yes' if p['instagram_worthy'] else 'No'}")
        if p.get("instagram_handle"):
            lines.append(f"Instagram: @{p['instagram_handle']}")

        if p.get("lokly_qualified"):
            lines.append(f"Lokly certified: ✅")

    context = "\n".join(lines)
    return context, len(places)


# ─── System prompt ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a knowledgeable restaurant expert for Lokly.ai — a curated restaurant database for Tel Aviv.

Your job is to help the user find the perfect restaurant for any occasion, mood, or need. You have detailed DNA profiles for the restaurants below — use them to give specific, confident recommendations.

Guidelines:
- Always recommend specific restaurants by name
- Explain WHY each recommendation fits (reference the DNA properties: vibe, noise, crowd, food, etc.)
- Lead with the EXPERIENCE — what it feels like, what you eat, what the vibe is. Put chef names and credentials at the end, not the beginning. Nobody wants to be educated, they want to be excited.
- If a property isn't in the data, say so honestly — don't make things up
- Be conversational and direct — no fluff
- If asked to compare restaurants, do it confidently
- You can recommend 1-3 options depending on the question
- The data quality varies: the first 24 restaurants are fully profiled, the newer ones may have less data

Here is the current database:

{context}"""


# ─── Main app ───────────────────────────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="Lokly.ai QA",
        page_icon="🍽️",
        layout="centered"
    )

    if not check_password():
        return

    st.title("🍽️ Lokly.ai — Tel Aviv")
    st.caption("Ask me anything about the 80 restaurants in our database")

    # Load context
    with st.spinner("Loading restaurant database..."):
        context, count = load_restaurant_context()

    st.success(f"✅ {count} Tel Aviv restaurants loaded")

    # Init chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("Where should I take a client for lunch? What's good for a first date?..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Build message history for Claude
        with st.chat_message("assistant"):
            client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
            system = SYSTEM_PROMPT.format(context=context)

            with st.spinner("Thinking..."):
                response = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=1024,
                    system=system,
                    messages=[
                        {"role": m["role"], "content": m["content"]}
                        for m in st.session_state.messages
                    ]
                )
                answer = response.content[0].text

            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})

    # Sidebar
    with st.sidebar:
        st.markdown("### About")
        st.markdown("This is an internal QA tool for Lokly.ai.")
        st.markdown(f"**Database:** {count} Tel Aviv restaurants")
        st.markdown("**Data quality:**")
        st.markdown("- First 24 restaurants: fully profiled ✅")
        st.markdown("- New 56: basic data, pipeline in progress 🔄")
        st.markdown("---")
        if st.button("Clear conversation"):
            st.session_state.messages = []
            st.rerun()
        st.markdown("---")
        st.caption("Lokly.ai internal tool — do not share")


if __name__ == "__main__" or True:
    main()
