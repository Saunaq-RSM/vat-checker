import streamlit as st
from vat_utils import check_vat

st.set_page_config(page_title="EU VAT Batch Checker (VIES)", layout="centered")
st.title("EU VAT Batch Checker (VIES)")

vat_input = st.text_area(
    "Enter one VAT number per line (e.g. DE123456789):",
    placeholder="DE123456789\nFR12345678901\nBE02831130808",
    height=150
)

if st.button("Check VAT numbers"):
    lines = [line.strip() for line in vat_input.splitlines() if line.strip()]
    if not lines:
        st.warning("Please paste at least one VAT number.")
    else:
        # Prepare table data
        rows = []
        with st.spinner("Checking…"):
            for vat in lines:
                country = vat[:2].upper()
                number = vat[2:].replace(" ", "")
                try:
                    result = check_vat(country, number)
                    rows.append({
                        "Country": country,
                        "VAT Number": number,
                        "Status": result['status'],
                        "Name / Address": result['details']
                    })
                except Exception as e:
                    rows.append({
                        "Country": country,
                        "VAT Number": number,
                        "Status": "Error",
                        "Name / Address": str(e)
                    })
        st.table(rows)
