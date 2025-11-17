# main.py
import json
import os
import time
from typing import Dict, List

import pandas as pd

MODEL = "gpt-4o-mini"

# ----------------------------------------------------------
# 1) OPTIONAL STREAMLIT IMPORT (for st.secrets)
# ----------------------------------------------------------
try:
    import streamlit as st

    HAS_STREAMLIT = True
except ImportError:
    st = None
    HAS_STREAMLIT = False

# ----------------------------------------------------------
# 2) SAFE OPENAI IMPORT (NO CRASH IF MISSING)
# ----------------------------------------------------------
try:
    from openai import OpenAI  # new OpenAI SDK

    HAS_OPENAI = True
except Exception as e:
    print("OpenAI SDK not available:", e)
    OpenAI = None
    HAS_OPENAI = False

# ----------------------------------------------------------
# 3) GET API KEY FROM (st.secrets -> secret_key -> env)
# ----------------------------------------------------------


def get_openai_key() -> str:
    # 1. Streamlit secrets (Streamlit Cloud)
    if HAS_STREAMLIT and "OPENAI_API_KEY" in st.secrets:
        print("Using OPENAI_API_KEY from Streamlit secrets.")
        return st.secrets["OPENAI_API_KEY"].strip()

    # 2. Local secret_key.py (your local dev)
    try:
        from secret_key import openai_key as _local_key

        print("Using OPENAI API key from secret_key.py.")
        return _local_key.strip()
    except Exception:
        pass

    # 3. Environment variable (fallback)
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if key:
        print("Using OPENAI_API_KEY from environment.")
    else:
        print("No OPENAI_API_KEY found in secrets, secret_key.py, or environment.")
    return key


openai_key = get_openai_key()

# ----------------------------------------------------------
# 4) INITIALIZE CLIENT SAFELY
# ----------------------------------------------------------

client = None
USE_API = False

if not HAS_OPENAI:
    print("OpenAI SDK missing. Running in mock mode.")
else:
    if not openai_key:
        print("No API key provided. Running in mock mode.")
    else:
        try:
            client = OpenAI(api_key=openai_key)
            USE_API = True
            print("OpenAI client initialized.")
        except Exception as e:
            print("Failed to initialize OpenAI client, running in mock mode:", e)
            client = None
            USE_API = False

# ----------------------------------------------------------
# HELPER FUNCTIONS
# ----------------------------------------------------------


def extract_message_content(choice):
    """Extract AI message text safely."""
    msg = (
        getattr(choice, "message", None)
        if not isinstance(choice, dict)
        else choice.get("message")
    )

    if isinstance(msg, dict):
        return msg.get("content", "").strip()

    if msg is not None:
        for attr in ("content", "text"):
            val = getattr(msg, attr, None)
            if isinstance(val, str) and val.strip():
                return val.strip()
        return str(msg)

    if isinstance(choice, dict):
        return choice.get("text", "").strip()

    return ""


def parse_json_from_text(text: str) -> Dict[str, str]:
    """Extract {subject, body} JSON from model output."""
    if not text:
        return {"subject": "", "body": ""}

    text = text.strip()
    start, end = text.find("{"), text.rfind("}") + 1

    if start != -1 and end != -1:
        try:
            data = json.loads(text[start:end])
            return {
                "subject": str(data.get("subject", "")).strip(),
                "body": str(data.get("body", "")).strip(),
            }
        except Exception:
            pass

    # fallback for messy outputs
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    subject = lines[0] if lines else ""
    body = " ".join(lines[1:]) if len(lines) > 1 else ""
    return {"subject": subject, "body": body}


def make_prompt(row: pd.Series) -> str:
    """Prompt for generating email JSON."""
    return f"""
Create a short personalized email (JSON only) for the customer.

Customer name: {row['Customer name']}
City: {row['City']}
Gender: {row.get('Gender', '')}
Last month purchase amount: {row.get('Last month purchase amount', '')}
Last quarter purchase amount: {row.get('Last quarter', '')}
Last year purchase amount: {row.get('Last year', '')}
Products previously bought: {row.get('products bought list of items', '')}

Requirements:
- Output JSON only: {{ "subject": "...", "body": "..." }}
- Subject: 6–8 words max
- Body: max 40 words; mention one product; end with “Explore more” or “Check it out”.
""".strip()


def mock_generate(row: pd.Series) -> Dict[str, str]:
    """Fallback generator if API fails."""
    products = [
        p.strip()
        for p in str(row.get("products bought list of items", "")).split(",")
        if p.strip()
    ]
    product = products[0] if products else "our selection"

    return {
        "subject": f"{row['Customer name']}, a pick you'll love — {product}",
        "body": f"Hi {row['Customer name']}, based on your recent purchases in {row['City']}, "
        f"you may love our {product}. Check it out.",
    }


def make_notification_prompt(row: pd.Series, subject: str, body: str) -> str:
    """Prompt for push/SMS notification."""
    return f"""
Write ONE short customer notification (18–22 words).

Customer: {row['Customer name']}
Product context: {row.get('products bought list of items', '')}
Email subject: {subject}
Email body: {body}

No JSON, only plain text.
""".strip()


def mock_notification(row: pd.Series) -> str:
    return f"{row['Customer name']}, check out your personalized offers today!"


def call_openai(prompt: str) -> str:
    """OpenAI completion with retry."""
    if not USE_API or client is None:
        raise RuntimeError("OpenAI client not available.")

    backoff = 1
    for attempt in range(4):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200,
            )
            return extract_message_content(resp.choices[0])

        except Exception as e:
            if "rate" in str(e).lower() or "quota" in str(e).lower():
                time.sleep(backoff)
                backoff *= 2
                continue
            raise

    raise RuntimeError("OpenAI API failed after retries.")


# ----------------------------------------------------------
# MAIN FUNCTION CALLED BY STREAMLIT
# ----------------------------------------------------------


def generate_emails(df: pd.DataFrame) -> List[Dict]:
    """Generate emails + notification for each customer."""
    results = []

    for _, row in df.iterrows():
        # Email
        try:
            raw = call_openai(make_prompt(row)) if USE_API else None
            parsed = parse_json_from_text(raw) if raw else mock_generate(row)
            used_fallback = raw is None
        except Exception:
            parsed = mock_generate(row)
            used_fallback = True

        subject = parsed["subject"]
        body = parsed["body"]

        # Notification
        try:
            notif_raw = (
                call_openai(make_notification_prompt(row, subject, body))
                if USE_API
                else None
            )
            notification = notif_raw.strip() if notif_raw else mock_notification(row)
        except Exception:
            notification = mock_notification(row)

        results.append(
            {
                "Customer name": row["Customer name"],
                "City": row["City"],
                "subject": subject,
                "body": body,
                "notification": notification,
                "used_fallback": used_fallback,
            }
        )

    return results


if __name__ == "__main__":
    print("main.py is ready.")
