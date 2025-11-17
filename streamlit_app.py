import urllib.parse

import pandas as pd
import streamlit as st

from main import USE_API, generate_emails

# ----------------------------------------------------------
# STREAMLIT UI
# ----------------------------------------------------------

st.set_page_config(page_title="Customer Email Generator", layout="wide")

st.title("📧 Customer Email & Notification Generator")

if not USE_API:
    st.warning("OpenAI not available. Mock email content will be used.")

uploaded_file = st.file_uploader("Upload customer CSV", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    st.subheader("📋 Uploaded Data Preview")
    st.dataframe(df, use_container_width=True)

    if st.button("🚀 Generate emails for all customers"):
        with st.spinner("Generating..."):
            emails = generate_emails(df)

        st.session_state["emails"] = emails
        st.success("Emails generated!")

# ----------------------------------------------------------
# CUSTOMER VIEWER
# ----------------------------------------------------------

if "emails" in st.session_state:

    emails = st.session_state["emails"]
    names = [e["Customer name"] for e in emails]

    tab1, tab2 = st.tabs(["Browse", "Search"])

    # ----------------------------------------------------------
    # TAB 1: BROWSE
    # ----------------------------------------------------------
    with tab1:
        st.subheader("Browse customers")
        chosen = st.selectbox("Select customer", names)

        if chosen:
            c = next(x for x in emails if x["Customer name"] == chosen)

            st.write(f"### Customer: {c['Customer name']} ({c['City']})")
            st.write(f"**Subject:** {c['subject']}")
            st.write("**Email Body:**")
            st.write(c["body"])
            st.write("**Notification:**")
            st.write(c["notification"])

            # --- universal email sender ---
            st.markdown("---")
            st.subheader(f"✉️ Send this email to {c['Customer name']}")

            default_email = f"{c['Customer name'].split()[0].lower()}@example.com"
            email_to = st.text_input(
                f"{c['Customer name']}'s email address", value=default_email
            )

            if st.button(f"Create email link for {c['Customer name']}"):
                subject = urllib.parse.quote(c["subject"])
                body = urllib.parse.quote(c["body"])
                mailto = f"mailto:{email_to}?subject={subject}&body={body}"
                st.markdown(f"[📩 Click here to open email client]({mailto})")

    # ----------------------------------------------------------
    # TAB 2: SEARCH
    # ----------------------------------------------------------
    with tab2:
        st.subheader("Search by name")

        name_query = st.text_input("Enter name (case insensitive)")

        if st.button("Fetch"):
            results = [
                x for x in emails if x["Customer name"].lower() == name_query.lower()
            ]

            if not results:
                st.error("No customer found.")
            else:
                c = results[0]

                st.write(f"### Customer: {c['Customer name']} ({c['City']})")
                st.write(f"**Subject:** {c['subject']}")
                st.write("**Email Body:**")
                st.write(c["body"])
                st.write("**Notification:**")
                st.write(c["notification"])

                # email section
                st.markdown("---")
                st.subheader(f"✉️ Send this email to {c['Customer name']}")

                default_email = f"{c['Customer name'].split()[0].lower()}@example.com"
                email_to = st.text_input(
                    f"{c['Customer name']}'s email address",
                    value=default_email,
                    key="search_email",
                )

                if st.button(f"Create email link for {c['Customer name']} (Search)"):
                    subject = urllib.parse.quote(c["subject"])
                    body = urllib.parse.quote(c["body"])
                    mailto = f"mailto:{email_to}?subject={subject}&body={body}"
                    st.markdown(f"[📩 Click here to open email client]({mailto})")

else:
    st.info("Upload a CSV to begin.")
