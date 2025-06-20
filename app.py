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

if barcode_input:
    if user_tab is None:
        st.warning("⚠️ Invalid user selection.")
    elif participants_df.empty:
        st.error("Participants sheet is empty or failed to load.")
    else:
        match = participants_df[participants_df['Barcode'].astype(str).str.strip() == pure_barcode]
        if not match.empty:
            row = match.iloc[0]
            name = row.get('Name', '').strip()
            arn = row.get('ARN Code', '').strip()
            mobile = row.get('Mobile', '').strip()
            email = row.get('Email', '').strip()
            city = row.get('City', '').strip()

            st.success(f"✅ Found: {name}")
            cols = st.columns(3)
            if email: cols[0].markdown(f"**Email:** [{email}](mailto:{email})")
            if mobile: cols[1].markdown(f"**Phone:** {mobile}")
            if city: cols[2].markdown(f"**City:** {city}")

            st.write("### Select Event to Mark")
            event_cols = st.columns(len(EVENTS))

            for i, event in enumerate(EVENTS):
                # Check if already checked in for this event
                existing_data = pd.DataFrame(sheet.worksheet(user_tab).get_all_records())
                duplicate = (
                    not existing_data.empty and
                    (existing_data['Barcode'] == pure_barcode) & (existing_data['Event'] == event)
                ).any()

                if duplicate:
                    event_cols[i].button(f"✅ {event}", key=f"{event}_done", disabled=True)
                else:
                    if event_cols[i].button(event, key=f"{event}_btn"):
                        try:
                            ws = sheet.worksheet(user_tab)
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            ws.append_row([pure_barcode, arn, name, mobile, event, timestamp, selected_email])
                            st.success(f"{event} recorded for {name} in {user_tab}")
                            st.experimental_rerun()
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
    st.markdown("#### 🧮 User-wise Check-in Summary")
    st.dataframe(df_summary.pivot(index="User", columns="Event", values="Check-ins").fillna(0), use_container_width=True)

    st.markdown("#### 📈 Event Scan Summary (All Participants)")
    total_event_summary = df_summary.groupby("Event")["Check-ins"].sum().reset_index()
    st.dataframe(total_event_summary, use_container_width=True)

    all_logs = []
    for email, tab in EMAIL_TAB_MAP.items():
        try:
            df = pd.DataFrame(sheet.worksheet(tab).get_all_records())
            df['User'] = email
            all_logs.append(df)
        except:
            continue

    if all_logs:
        merged_logs = pd.concat(all_logs, ignore_index=True)
        csv = merged_logs.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download All Check-ins (CSV)", csv, "all_checkins.csv", "text/csv")
