import json
import urllib.request
from datetime import date, timedelta
import streamlit as st

# --- 1. Catalogue Data (edit prices in one place) ---
MODEL = "gemini-3.5-flash-lite"  # Free-tier Gemini model
EXPRESS_PRICE = 40
PRICES = {
    "Non-Peak": {"Children": 30, "Adult": 50, "Senior Citizen": 35},
    "Peak": {"Children": 40, "Adult": 65, "Senior Citizen": 45},
}

# --- 2. Population Database (TP-POP-DB) ---
POP_DB = {}
week_pattern = [300, 260, 280, 340, 480, 880, 820]  # Mon (0) to Sun (6)
start_day = date.today() - timedelta(days=7)
for i in range(42):
    d = start_day + timedelta(days=i)
    POP_DB[str(d)] = week_pattern[d.weekday()] + (i // 7) * 20


# --- 3. API Plugin Function (Secondary Deliverable) ---
def get_express_suggestions(api_key, prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
    )
    with urllib.request.urlopen(req) as res:
        data = json.loads(res.read().decode("utf-8"))
    reply_text = data["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(reply_text).get("suggestions", [])


# --- 4. Main Ticketing App (Primary Deliverable) ---
st.title("Theme Park Ticketing App")
st.write("Welcome, how are you?")

# Sidebar: Catalogue & Gemini API Key
st.sidebar.header("Ticket Catalogue")
st.sidebar.write("Non-Peak (Mon-Fri):", PRICES["Non-Peak"])
st.sidebar.write("Peak (Sat-Sun):", PRICES["Peak"])
st.sidebar.write(f"Express Base Price: ${EXPRESS_PRICE} / person")
api_key = st.sidebar.text_input("Gemini API Key (API Plugin)", type="password")

if "confirmed" not in st.session_state:
    st.session_state["confirmed"] = False
if "suggestions" not in st.session_state:
    st.session_state["suggestions"] = []

# User Inputs
visitors = {}
for group in ["Children", "Adult", "Senior Citizen"]:
    visitors[group] = st.number_input(group, min_value=0, value=1 if group == "Adult" else 0, step=1)

preferred_date = st.date_input(
    "Preferred Date", value=date.today(), min_value=date.today(), max_value=date.today() + timedelta(days=14)
)

is_weekend = preferred_date.weekday() >= 5
day_type = "Peak" if is_weekend else "Non-Peak"
day_pop = POP_DB.get(str(preferred_date), 500)
total_people = sum(visitors.values())
st.info(f"Category: **{day_type}** | Expected Population: **{day_pop}**")

# Confirm Yes / No
col1, col2 = st.columns(2)
if col1.button("Confirm (Yes)"):
    if total_people == 0:
        st.warning("Enter at least 1 visitor.")
    else:
        st.session_state["confirmed"] = True
        st.session_state["suggestions"] = []
if col2.button("Edit Details (No)"):
    st.session_state["confirmed"] = False
    st.session_state["suggestions"] = []

# Calculate Price & Run API Plugin
if st.session_state["confirmed"]:
    base_price = sum(visitors[g] * PRICES[day_type][g] for g in visitors)
    st.success(f"Base Total Price = **${base_price:.2f}**")

    # Build alternative dates (weekends -> both weeks' weekdays + weekends; weekdays -> both weeks' weekdays)
    week_start = preferred_date - timedelta(days=preferred_date.weekday())
    offsets = range(0, 14) if is_weekend else [0, 1, 2, 3, 4, 7, 8, 9, 10, 11]
    candidates = []
    for offset in offsets:
        alt = week_start + timedelta(days=offset)
        if alt >= date.today():
            candidates.append({
                "date": str(alt),
                "day_type": "Weekend" if alt.weekday() >= 5 else "Weekday",
                "population": POP_DB.get(str(alt), 500),
            })

    st.subheader("Express Ticket Suggestions (API Plugin)")
    if not api_key:
        st.warning("Paste your Gemini API key in the sidebar to see Express Ticket discounts.")
    elif not st.session_state["suggestions"]:
        prompt = (
            f"Preferred date: {preferred_date} ({day_type}, pop: {day_pop}). "
            f"Express base price: ${EXPRESS_PRICE}. Candidate dates: {json.dumps(candidates)}. "
            "Suggest 3 dates to spread crowds: 1) prioritise user's preferred date/type, "
            "2) higher population = lower discount, lower population = higher discount (5% to 50%), "
            "3) include the highest discount. Return JSON with key 'suggestions' containing objects with: "
            "date, day_type, discount_percent, express_price_per_person, reason."
        )
        try:
            st.session_state["suggestions"] = get_express_suggestions(api_key, prompt)
        except Exception as e:
            st.error(f"API Plugin error: {e}")

    # Express Ticket Selection & Final Price
    options = ["Opt for no express ticket"]
    for i, item in enumerate(st.session_state["suggestions"]):
        options.append(
            f"Option {i + 1}: {item['date']} ({item['day_type']}) — "
            f"{item['discount_percent']}% OFF (${item['express_price_per_person']:.2f}/person) | {item['reason']}"
        )

    choice = st.radio("Choose an option:", options)
    if choice == "Opt for no express ticket":
        final_price = base_price
    else:
        chosen = st.session_state["suggestions"][options.index(choice) - 1]
        final_price = base_price + (chosen["express_price_per_person"] * total_people)

    st.subheader(f"Final Price = **${final_price:.2f}**")