import streamlit as st
import yaml
from passlib.context import CryptContext
from vat_utils import check_vat

# Password hashing setup: use PBKDF2-SHA256 (no external bcrypt dependency)
pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# Credentials file path
CRED_FILE = "credentials.yaml"

# Load credentials from YAML every time (no caching)
def load_credentials():
    try:
        with open(CRED_FILE, "r") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        data = None
    # Ensure structure
    if not isinstance(data, dict) or "credentials" not in data:
        data = {"credentials": {"users": {}}}
    elif "users" not in data["credentials"] or not isinstance(data["credentials"]["users"], dict):
        data["credentials"]["users"] = {}
    return data

# Save credentials back to YAML
def save_credentials(data):
    with open(CRED_FILE, "w") as f:
        yaml.safe_dump(data, f)

# Register new user
def register_user(users):
    st.subheader("Create a new account")
    new_username = st.text_input("Username", key="reg_username")
    new_name = st.text_input("Full Name", key="reg_name")
    new_password = st.text_input("Password", type="password", key="reg_pw")
    confirm_pw = st.text_input("Confirm Password", type="password", key="reg_pw2")
    if st.button("Register", key="reg_btn"):
        if not new_username or not new_password:
            st.error("Username and password required.")
            return False
        if new_password != confirm_pw:
            st.error("Passwords do not match.")
            return False
        if new_username in users:
            st.error("Username already exists.")
            return False
        # Hash password
        hashed = pwd_ctx.hash(new_password)
        users[new_username] = {"name": new_name, "password": hashed}
        creds = {"credentials": {"users": users}}
        save_credentials(creds)
        st.success("Account created! Please login below.")
        return True
    return False

# Authenticate existing user
def authenticate(username, password, users):
    if username in users:
        stored_hash = users[username]["password"]
        if pwd_ctx.verify(password, stored_hash):
            return True
    return False

# Initialize session state for login
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["username"] = None

# Main
st.set_page_config(page_title="EU VAT Batch Checker (VIES)", layout="centered")
creds = load_credentials()
users = creds["credentials"]["users"]

# If not logged in, show login/register
if not st.session_state["logged_in"]:
    st.sidebar.title("Account")
    mode = st.sidebar.selectbox("Mode", ["Login", "Register"] )
    if mode == "Register":
        if register_user(users):
            # simply reload credentials next interaction
            pass
    else:
        st.sidebar.subheader("Login")
        username = st.sidebar.text_input("Username", key="login_user")
        password = st.sidebar.text_input("Password", type="password", key="login_pw")
        if st.sidebar.button("Login", key="login_btn"):
            if authenticate(username, password, users):
                st.session_state["logged_in"] = True
                st.session_state["username"] = username
                st.rerun()
            else:
                st.sidebar.error("Invalid username or password.")

# When logged in, hide login/register and show main app
if st.session_state["logged_in"]:
    st.sidebar.write(f"**Logged in as:** {users[st.session_state['username']]['name']} ")
    if st.sidebar.button("Logout", key="logout_btn"):
        st.session_state["logged_in"] = False
        st.session_state["username"] = None
        st.rerun()

    # VAT Checker UI
    st.title("EU VAT Batch Checker (VIES)")
    vat_input = st.text_area(
        "Enter one VAT number per line (e.g. DE123456789):",
        height=150
    )
    if st.button("Check VAT numbers", key="check_btn"):
        lines = [l.strip() for l in vat_input.splitlines() if l.strip()]
        if not lines:
            st.warning("Please paste at least one VAT number.")
        else:
            rows = []
            with st.spinner("Checking…"):
                explored = set()
                for vat in lines:
                    if vat in explored:
                        continue
                    explored.add(vat)
                    country, number = vat[:2].upper(), vat[2:].replace(" ", "")
                    try:
                        r = check_vat(country, number)
                        print(r)
                        rows.append({
                            "Country": country,
                            "VAT Number": number,
                            "Status": r['status'],
                            "Name / Address": r['details']
                        })
                    except Exception as e:
                        rows.append({
                            "Country": country,
                            "VAT Number": number,
                            "Status": "Error",
                            "Name / Address": str(e)
                        })
            st.table(rows)
