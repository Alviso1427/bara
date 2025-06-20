import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
import base64
import os
from google.oauth2.service_account import Credentials

# CONFIG
GOOGLE_SHEET_NAME = "EventCheckins"
EVENTS = ["Entry_Register", "Breakfast", "Lunch", "Photo", "Gift"]

EMAIL_TAB_MAP = {
    "chotturedplanet@gmail.com": "User1",
    "vandhanaredplanet@gmail.com": "User2",
    "jesintharaniredplanet@gmail.com": "User3",
    "jayanthiredplanet@gmail.com": "User4",
    "ranjithkumar.redplanet@gmail.com": "User5",
    "kokilavenkatesanofficial@gmail.com": "User6",
}

# STREAMLIT SECRETS USAGE
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)
sheet = client.open(GOOGLE_SHEET_NAME)

# STREAMLIT UI SETUP
st.set_page_config(page_title="RP Event Participation Tracker", layout="wide")
st.title("🎟️ RP Event Participation Tracker")

# Load logo if exists
logo_path = "logo.png"
def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

if os.path.exists(logo_path):
    logo_base64 = get_base64_image(logo_path)
    st.markdown(f"""
        <style>
        .logo-container {{
            position: absolute;
            top: 15px;
            right: 25px;
            z-index: 100;
        }}
        </style>
        <div class="logo-container">
            <img src="data:image/png;base64,{logo_base64}" width="160">
        </div>
    """, unsafe_allow_html=True)

# Load participant list
@st.cache_data(ttl=60)
def load_participant_data():
    try:
        participants = sheet.worksheet("Participants").get_all_records()
        return pd.DataFrame(participants)
    except Exception as e:
        st.error(f"Error reading Participants sheet: {e}")
        return pd.DataFrame()

participants_df = load_participant_data()

# User selection
st.subheader("👤 Select Your Email")
selected_email = st.selectbox("Choose your user email", list(EMAIL_TAB_MAP.keys()))
user_tab = EMAIL_TAB_MAP.get(selected_email)

# Barcode input
st.subheader("📥 Scan or Enter Barcode")
barcode_input = st.text_input("Scan or Enter Barcode", key="barcode_input", max_chars=25)
pure_barcode = barcode_input.strip()

if st.button("🧹 Clear Barcode"):
    st.session_state.barcode_input = ""
    st.rerun()

if barcode_input:
    if user_tab is None:
        st.warning("⚠️ Invalid user selection.")
    elif participants_df.empty:
        st.error("Participants sheet is empty or failed to load.")
    else:
        match = participants_df[participants_df['Barcode'].astype(str).str.strip() == pure_barcode]
        if not match.empty:
            row = match.iloc[0]
            arn = str(row['ARN Code']).strip() if 'ARN Code' in row else ''
            name = str(row['Name']).strip() if 'Name' in row else ''
            mobile = str(row['Mobile']).strip() if 'Mobile' in row else ''
            email = str(row['Email']).strip() if 'Email' in row else ''
            city = str(row['City']).strip() if 'City' in row else ''

            st.success(f"✅ Found: {name}")
            cols = st.columns(3)
            if email: cols[0].markdown(f"**Email:** [{email}](mailto:{email})")
            if mobile: cols[1].markdown(f"**Phone:** {mobile}")
            if city: cols[2].markdown(f"**City:** {city}")

            st.write("### Select Event to Mark")
            event_cols = st.columns(len(EVENTS))

            for i, event in enumerate(EVENTS):
                try:
                    existing_data = pd.DataFrame(sheet.worksheet(user_tab).get_all_records())
                except Exception as e:
                    st.error(f"Failed to read data from sheet: {e}")
                    existing_data = pd.DataFrame()

                duplicate = (
                    not existing_data.empty and
                    ((existing_data['Barcode'] == pure_barcode) & (existing_data['Event'] == event)).any()
                )

                if duplicate:
                    event_cols[i].button(f"✅ {event}", key=f"{event}_done", disabled=True)
                else:
                    if event_cols[i].button(event, key=f"{event}_btn"):
                        try:
                            ws = sheet.worksheet(user_tab)
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            ws.append_row([pure_barcode, arn, name, mobile, event, timestamp, selected_email])
                            st.success(f"{event} recorded for {name} in {user_tab}")
                            st.rerun()  # replaces experimental_rerun
                        except Exception as e:
                            st.error(f"❌ Failed to write to Google Sheet: {e}")
        else:
            st.warning("⚠️ No participant found for this barcode.")

# Show recent check-ins
st.markdown("---")
st.subheader("🕒 Recent Check-ins")
if user_tab:
    try:
        recent_data = sheet.worksheet(user_tab).get_all_records()
        recent_df = pd.DataFrame(recent_data)
        if not recent_df.empty:
            st.dataframe(recent_df.sort_values("Timestamp", ascending=False).head(20), use_container_width=True)
        else:
            st.info("No check-ins yet for this user.")
    except Exception as e:
        st.error(f"Error loading {user_tab} sheet: {e}")

# Admin dashboard
st.markdown("---")
st.subheader("📊 Admin: Summary Dashboard")

summary = []
for email, tab in EMAIL_TAB_MAP.items():
    try:
        data = pd.DataFrame(sheet.worksheet(tab).get_all_records())
        if not data.empty:
            for event in EVENTS:
                count = data[data['Event'] == event].shape[0]
                summary.append({"User": email, "Event": event, "Check-ins": count})
    except:
        continue

if summary:
    df_summary = pd.DataFrame(summary)
    try:
        dashboard_ws = sheet.worksheet("Dashboard")
        dashboard_ws.clear()
    except:
        dashboard_ws = sheet.add_worksheet(title="Dashboard", rows="100", cols="20")

    dashboard_data = df_summary.pivot(index="User", columns="Event", values="Check-ins").fillna(0).reset_index()
    dashboard_ws.update([dashboard_data.columns.values.tolist()] + dashboard_data.values.tolist())
    st.markdown("#### 📈 Event Scan Summary (All Participants)")
