import requests
from xml.etree import ElementTree as ET
import streamlit as st
import yaml
import pandas as pd
from passlib.context import CryptContext
from vat_utils import check_vat
import io
from datetime import datetime
import pytz

# Configuration
CRED_FILE = "credentials.yaml"
COST_PER_CHECK = 0.05  # € per VAT check line
INITIAL_CREDIT = 10.0  # € initial credit for new users
cet = pytz.timezone('Europe/Paris')  # CET/CEST depending on daylight saving

# Password hashing setup
pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# ------------------ Helpers for Credentials ------------------ #
def load_credentials():
    try:
        with open(CRED_FILE, "r") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        data = None

    if not isinstance(data, dict) or "credentials" not in data:
        data = {"credentials": {"users": {}}}

    if not isinstance(data["credentials"].get("users"), dict):
        data["credentials"]["users"] = {}

    return data


def save_credentials(data):
    with open(CRED_FILE, "w") as f:
        yaml.safe_dump(data, f)


# ------------------ Registration and Authentication ------------------ #
def register_user(users, creds):
    st.subheader("Create a new account")
    u = st.text_input("Username", key="reg_user")
    n = st.text_input("Full Name", key="reg_name")
    p = st.text_input("Password", type="password", key="reg_pw")
    c = st.text_input("Confirm Password", type="password", key="reg_pw2")

    if st.button("Register", key="reg_btn"):
        if not u or not p:
            st.error("Username and password required.")
            return False
        if p != c:
            st.error("Passwords do not match.")
            return False
        if u in users:
            st.error("Username already exists.")
            return False

        users[u] = {
            "name": n,
            "password": pwd_ctx.hash(p),
            "credit": INITIAL_CREDIT,
        }
        creds["credentials"]["users"] = users
        save_credentials(creds)
        st.success(f"Account created with €{INITIAL_CREDIT:.2f}. Please log in.")
        return True
    return False


def authenticate(u, p, users):
    return u in users and pwd_ctx.verify(p, users[u]["password"])


# ------------------ Session State Initialization ------------------ #
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "username": "", "credit": 0.0})

# ------------------ App Configuration ------------------ #
st.set_page_config(page_title="EU VAT Batch Checker (VIES)", layout="centered")
creds = load_credentials()
users = creds["credentials"]["users"]

# ------------------ Login / Register UI ------------------ #
if not st.session_state["logged_in"]:
    mode = st.sidebar.radio("Account", ["Login", "Register"])
    if mode == "Register":
        register_user(users, creds)
    else:
        st.sidebar.subheader("Login")
        user = st.sidebar.text_input("Username", key="login_user")
        pwd = st.sidebar.text_input("Password", type="password", key="login_pw")
        if st.sidebar.button("Login", key="login_btn"):
            if authenticate(user, pwd, users):
                st.session_state["logged_in"] = True
                st.session_state["username"] = user
                st.session_state["credit"] = users[user].get("credit", 0.0)
                st.rerun()
            else:
                st.sidebar.error("Invalid credentials.")


# ------------------ Main VAT Checker ------------------ #
def main_app():
    user = st.session_state["username"]
    sidebar = st.sidebar
    sidebar.write(f"**User:** {users[user]['name']}")
    credit_slot = sidebar.empty()
    credit_slot.write(f"**Credit:** €{st.session_state['credit']:.2f}")

    st.title("EU VAT Batch Checker (VIES)")

    # File upload or manual input
    uploaded = st.file_uploader("Upload a CSV/XLSX with VAT codes", type=["csv", "xlsx"])
    vat_list = []
    if uploaded is not None:
        try:
            if uploaded.name.lower().endswith(".csv"):
                df = pd.read_csv(uploaded)
            else:
                df = pd.read_excel(uploaded)
        except Exception as e:
            st.error(f"Failed to read file: {e}")
            return

        st.write("Columns:", list(df.columns))
        col = st.text_input("Enter column name or index for VAT codes")
        if col:
            try:
                if col.isdigit():
                    vat_list = df.iloc[:, int(col)].dropna().astype(str).tolist()
                else:
                    vat_list = df[col].dropna().astype(str).tolist()
            except Exception as e:
                st.error(f"Invalid column: {e}")
                return
    else:
        text_input = st.text_area("Or enter VAT numbers (one per line):", height=150)
        vat_list = [v.strip() for v in text_input.splitlines() if v.strip()]

    # Run VAT checks
    if st.button("Check VAT numbers"):
        if not vat_list:
            st.warning("No VAT numbers provided.")
            return

        credit = st.session_state["credit"]
        max_checks = int(credit // COST_PER_CHECK)

        if max_checks == 0:
            st.error("Insufficient credit to perform any checks.")
            return

        to_process = vat_list[:max_checks]
        skipped = vat_list[max_checks:]
        cost = COST_PER_CHECK * len(to_process)
        new_credit = round(credit - cost, 2)

        # Save updated credit to session and YAML
        st.session_state["credit"] = new_credit
        users[user]["credit"] = new_credit
        creds["credentials"]["users"] = users
        save_credentials(creds)

        credit_slot.write(f"**Credit:** €{new_credit:.2f}")
        if skipped:
            st.warning(f"Only {len(to_process)} of {len(vat_list)} processed due to credit.")

        # Progress bar + results
        progress_bar = st.progress(0)
        status_text = st.empty()
        results_df = pd.DataFrame(
            columns=["Country", "VAT Number", "Status", "Name", "Address", "Timestamp"]
        )
        table_placeholder = st.empty()
        total = len(to_process)
        explored = set()

        for i, vat in enumerate(to_process, start=1):
            if vat in explored:
                progress_bar.progress(i / total)
                status_text.text(f"Processing {i} of {total} VAT checks...")
                table_placeholder.dataframe(results_df, width=800)
                continue
            explored.add(vat)

            country, number = vat[:2].upper(), vat[2:].replace(" ", "")
            try:
                r = check_vat(country, number)
                status, name, address = r.get("status"), r.get("name"), r.get("address")
            except Exception as e:
                status, name, address = "Invalid", str(e), ""

            new_row = {
                "Country": country,
                "VAT Number": number,
                "Status": status,
                "Name": name,
                "Address": address,
                "Timestamp": datetime.now(cet).strftime("%Y-%m-%d %H:%M:%S"),
            }
            results_df = pd.concat([results_df, pd.DataFrame([new_row])], ignore_index=True)

            # Update UI
            progress_bar.progress(i / total)
            status_text.text(f"Processing {i} of {total} VAT checks...")
            table_placeholder.dataframe(results_df, width=800)

        status_text.text("Done!")
        if skipped:
            st.info(f"Skipped VATs: {', '.join(skipped)}")

        # Download results
        towrite = io.BytesIO()
        with pd.ExcelWriter(towrite, engine="openpyxl") as writer:
            results_df.to_excel(writer, index=False, sheet_name="VAT Results")
        towrite.seek(0)
        st.download_button(
            label="Download results as Excel",
            data=towrite.getvalue(),
            file_name="vat_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    if st.sidebar.button("Logout"):
        st.session_state.update({"logged_in": False, "username": "", "credit": 0.0})
        st.rerun()


# ------------------ Run App ------------------ #
if st.session_state["logged_in"]:
    main_app()
