
import json
def safe_json_loads(data):
    if isinstance(data, (dict, list)): return data
    if isinstance(data, str):
        try: return safe_json_loads(data)
        except: return None
    return data
import streamlit as st
import os
import re
import tempfile
import json
import hashlib
import uuid
import datetime
from services.llm_parser import parse_with_llm
from services.pdf_service import extract_pages

from services.identifier_service import (
    reduce_text,
    find_existing_identifier,
    classify_document_llm,
    save_new_statement_format
)
from services.extraction_service import (
    generate_extraction_logic_llm,
    extract_transactions_using_logic
)
from db.connection import get_connection, get_cursor, execute_insert



# ================= UI ENHANCEMENT CONFIG =================

st.set_page_config(
    page_title="UVE PRODUCT",
    layout="wide",
    initial_sidebar_state="collapsed"
)


if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "modal_action" not in st.session_state:
    st.session_state.modal_action = None

# ---- Custom CSS ----
st.markdown("""
<style>
    /* ── Base Theme ── */
    .stApp {
        background: linear-gradient(135deg, #0f172a, #1e293b, #0f172a);
        color: #e2e8f0;
    }
    h1, h2, h3 { color: #f8fafc; font-weight: 700; letter-spacing: 0.5px; }

    /* ── Buttons ── */
    .stButton>button {
        border-radius: 12px;
        background: linear-gradient(135deg, #2563eb, #7c3aed);
        color: white; font-weight: 600;
        padding: 0.55em 1.4em; border: none;
        transition: all 0.3s ease-in-out;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        background: linear-gradient(135deg, #7c3aed, #2563eb);
        box-shadow: 0 6px 20px rgba(124, 58, 237, 0.45);
    }

    /* ── Glass Card ── */
    .custom-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(148, 163, 184, 0.12);
        padding: 24px; border-radius: 18px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.35);
        margin-bottom: 22px;
    }

    /* ── Admin Header ── */
    .admin-header {
        background: linear-gradient(135deg, rgba(37,99,235,0.25), rgba(124,58,237,0.2));
        backdrop-filter: blur(16px);
        border: 1px solid rgba(99,102,241,0.2);
        border-radius: 20px; padding: 28px 32px;
        margin-bottom: 28px;
        position: relative; overflow: hidden;
    }
    .admin-header::before {
        content: ''; position: absolute; top: 0; left: 0; right: 0;
        height: 3px;
        background: linear-gradient(90deg, #2563eb, #7c3aed, #ec4899);
    }
    .admin-header h2 { margin: 0 0 4px 0; font-size: 26px; }
    .admin-header p { margin: 0; opacity: 0.7; font-size: 14px; }
    .admin-badge {
        display: inline-block; background: linear-gradient(135deg, #7c3aed, #6366f1);
        padding: 3px 14px; border-radius: 20px; font-size: 11px;
        font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase;
        margin-bottom: 8px;
    }

    /* ── KPI Metric Card ── */
    .kpi-card {
        background: rgba(30, 41, 59, 0.6);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(148,163,184,0.1);
        border-radius: 16px; padding: 20px 22px;
        text-align: center;
        transition: transform 0.25s, box-shadow 0.25s;
    }
    .kpi-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.3);
    }
    .kpi-number { font-size: 32px; font-weight: 800; margin: 6px 0 2px 0; }
    .kpi-label { font-size: 12px; opacity: 0.6; text-transform: uppercase; letter-spacing: 1px; }
    .kpi-total .kpi-number { color: #60a5fa; }
    .kpi-active .kpi-number { color: #34d399; }
    .kpi-review .kpi-number { color: #fbbf24; }
    .kpi-disabled .kpi-number { color: #f87171; }

    /* ── Status Badges ── */
    .status-badge {
        display: inline-block; padding: 4px 14px; border-radius: 20px;
        font-size: 11px; font-weight: 700; letter-spacing: 0.8px;
    }
    .status-active { background: rgba(52,211,153,0.15); color: #34d399; border: 1px solid rgba(52,211,153,0.3); }
    .status-review { background: rgba(251,191,36,0.15); color: #fbbf24; border: 1px solid rgba(251,191,36,0.3); }
    .status-disabled { background: rgba(248,113,113,0.15); color: #f87171; border: 1px solid rgba(248,113,113,0.3); }
    .status-experimental { background: rgba(167,139,250,0.15); color: #a78bfa; border: 1px solid rgba(167,139,250,0.3); }

    /* ── Section Card ── */
    .section-card {
        background: rgba(30, 41, 59, 0.55);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(148,163,184,0.08);
        border-radius: 16px; padding: 24px;
        margin: 16px 0;
    }
    .section-title {
        font-size: 18px; font-weight: 700; color: #f1f5f9;
        margin: 0 0 16px 0; display: flex; align-items: center; gap: 10px;
    }

    /* ── Gradient Divider ── */
    .gradient-divider {
        height: 1px; border: none; margin: 28px 0;
        background: linear-gradient(90deg, transparent, rgba(99,102,241,0.4), transparent);
    }

    /* ── Selected Doc Banner ── */
    .selected-banner {
        background: linear-gradient(135deg, rgba(37,99,235,0.12), rgba(124,58,237,0.1));
        border: 1px solid rgba(99,102,241,0.2);
        border-radius: 14px; padding: 16px 20px;
        margin: 12px 0 16px 0;
    }
    .selected-banner .doc-name { font-weight: 700; font-size: 15px; color: #f1f5f9; }
    .selected-banner .doc-meta { font-size: 12px; opacity: 0.6; margin-top: 4px; }

    /* ── Comparison Cards ── */
    .comparison-card {
        background: rgba(30, 41, 59, 0.5);
        border: 1px solid rgba(148,163,184,0.08);
        border-radius: 14px; padding: 16px;
    }
    .txn-badge {
        display: inline-block; background: rgba(99,102,241,0.2);
        color: #a5b4fc; padding: 2px 12px; border-radius: 12px;
        font-size: 11px; font-weight: 700; margin-bottom: 8px;
    }

    /* ── Similarity Gauge ── */
    .sim-gauge {
        text-align: center; padding: 20px;
        background: rgba(30, 41, 59, 0.5);
        border-radius: 16px; border: 1px solid rgba(148,163,184,0.08);
    }
    .sim-value { font-size: 48px; font-weight: 800; }
    .sim-high { color: #34d399; }
    .sim-mid { color: #fbbf24; }
    .sim-low { color: #f87171; }
</style>
""", unsafe_allow_html=True)



# ================= SIDEBAR =================

with st.sidebar:
    st.markdown("## User Info")
    st.markdown("---")
    if st.session_state.user_id:
        st.success(" Logged In")
    else:
        st.warning(" Not Logged In")

    st.markdown("---")
    st.markdown("### Version")
    st.caption("v1.0 AI Extraction Engine")













 
# ================= AUTH =================
 

 
# def hash_password(password: str):
#     return hashlib.sha256(password.encode()).hexdigest()
def hash_password(password: str):
    return hashlib.sha256(password.strip().encode()).hexdigest()
 
def create_session(user_id):
    conn = get_connection()
    cursor = get_cursor(conn)
    token = str(uuid.uuid4())
    expires_at = datetime.datetime.now() + datetime.timedelta(hours=12)
 
    cursor.execute("""
        INSERT INTO user_sessions (user_id, token, expires_at)
        VALUES (%s, %s, %s)
        """, (user_id, token, expires_at))
 
    conn.commit()
    cursor.close()
    conn.close()
 
    st.session_state.user_id = user_id

def update_document_status(document_id, new_status):
    conn = get_connection()
    cursor = get_cursor(conn)

    cursor.execute(
        "UPDATE documents SET status=%s WHERE document_id=%s",
        (new_status, document_id)
    )

    conn.commit()
    cursor.close()
    conn.close()

    st.success(f"Status updated to {new_status}")
    


# ================= SIMILARITY HELPERS =================

def normalize_date(date_str):
    if not date_str:
        return None
    return date_str.replace("-", "/").strip()


def normalize_text(text):
    """Collapse all whitespace, dashes, and special chars for fuzzy matching."""
    if not text:
        return ""
    text = str(text).strip().lower()
    # Replace dashes, em-dashes, en-dashes with space
    text = re.sub(r'[\u2014\u2013\-]+', ' ', text)
    # Collapse all whitespace to single space
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def normalize_number(val):
    """Cast to float for numeric comparison."""
    if val is None:
        return None
    try:
        return round(float(val), 2)
    except (ValueError, TypeError):
        return None


def text_similarity(a, b):
    """Return similarity ratio 0-1 using SequenceMatcher."""
    from difflib import SequenceMatcher
    a_norm = normalize_text(a)
    b_norm = normalize_text(b)
    if not a_norm and not b_norm:
        return 1.0
    if not a_norm or not b_norm:
        return 0.0
    return SequenceMatcher(None, a_norm, b_norm).ratio()


def field_match(a, b):
    return 1 if a == b else 0


def transaction_similarity(txn1, txn2):
    if not txn1 or not txn2:
        return 0.0

    score = 0
    total_fields = 5  # date, debit, credit, balance, details

    # Date comparison (exact after normalization)
    score += field_match(
        normalize_date(txn1.get("date")),
        normalize_date(txn2.get("date"))
    )

    # Numeric comparisons (cast to float)
    score += field_match(normalize_number(txn1.get("debit")), normalize_number(txn2.get("debit")))
    score += field_match(normalize_number(txn1.get("credit")), normalize_number(txn2.get("credit")))
    score += field_match(normalize_number(txn1.get("balance")), normalize_number(txn2.get("balance")))

    # Text comparison (fuzzy)
    score += text_similarity(txn1.get("details"), txn2.get("details"))

    return (score / total_fields) * 100


def calculate_similarity(code_txns, llm_txns):

    if not code_txns or not llm_txns:
        return [], 0.0

    max_len = max(len(code_txns), len(llm_txns))
    similarities = []

    for i in range(max_len):
        txn1 = code_txns[i] if i < len(code_txns) else None
        txn2 = llm_txns[i] if i < len(llm_txns) else None

        sim = transaction_similarity(txn1, txn2)
        similarities.append(sim)

    overall = round(sum(similarities) / len(similarities), 2)

    return similarities, overall
 

if st.session_state.user_id is None:

    # ── Premium Login Page CSS ──
    st.markdown("""
    <style>
        /* Hide sidebar & header on login */
        [data-testid="stSidebar"] { display: none; }

        /* Login wrapper */
        .login-wrapper {
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 70vh;
            padding: 20px;
        }
        .login-card {
            background: rgba(15, 23, 42, 0.85);
            backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
            border: 1px solid rgba(99, 102, 241, 0.2);
            border-radius: 24px;
            padding: 48px 40px 40px 40px;
            width: 100%;
            max-width: 420px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5),
                        0 0 80px rgba(99, 102, 241, 0.08);
            position: relative;
            overflow: hidden;
        }
        .login-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 4px;
            background: linear-gradient(90deg, #2563eb, #7c3aed, #ec4899, #f59e0b);
        }
        .login-logo {
            text-align: center;
            margin-bottom: 8px;
        }
        .login-logo .logo-icon {
            font-size: 48px;
            display: block;
            margin-bottom: 8px;
            animation: pulse-glow 3s ease-in-out infinite;
        }
        .login-logo h1 {
            font-size: 28px;
            font-weight: 800;
            background: linear-gradient(135deg, #60a5fa, #a78bfa, #f472b6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin: 0;
            letter-spacing: 1px;
        }
        .login-logo .tagline {
            font-size: 13px;
            color: rgba(148, 163, 184, 0.7);
            margin-top: 6px;
            letter-spacing: 0.5px;
        }
        .login-divider {
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(99,102,241,0.35), transparent);
            margin: 24px 0;
            border: none;
        }
        @keyframes pulse-glow {
            0%, 100% { filter: drop-shadow(0 0 6px rgba(99,102,241,0.3)); }
            50% { filter: drop-shadow(0 0 18px rgba(99,102,241,0.6)); }
        }
    </style>
    """, unsafe_allow_html=True)

    # ── Centered Login Card ──
    st.markdown("""
    <div class='login-wrapper'>
        <div class='login-card'>
            <div class='login-logo'>
                <span class='logo-icon'>⚡</span>
                <h1>UVE PRODUCT</h1>
                <p class='tagline'>AI-Powered Financial Document Engine</p>
            </div>
            <div class='login-divider'></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Use columns to center the Streamlit inputs
    spacer_l, login_col, spacer_r = st.columns([1.5, 2, 1.5])
    with login_col:
        email = st.text_input(" Email", placeholder="you@company.com")
        password = st.text_input("  Password", type="password", placeholder="Enter your password")

        st.markdown("<div style='height: 8px'></div>", unsafe_allow_html=True)

        if st.button(" Sign In", use_container_width=True, key="login_btn"):

            conn = get_connection()
            cursor = get_cursor(conn)

            cursor.execute(
                "SELECT * FROM users WHERE email=%s AND status='ACTIVE'",
                (email,)
            )

            user = cursor.fetchone()
            cursor.close()
            conn.close()

            if not user:
                st.error(" User not found. Please check your email.")

            else:
                entered_hash = hash_password(password.strip())
                db_hash = user["password_hash"]

                if entered_hash != db_hash:
                    st.error(" Invalid password. Please try again.")
                else:
                    create_session(user["user_id"])
                    st.session_state.role = user["role"]
                    st.success(" Welcome back!")
                    st.rerun()

        st.markdown("<p style='text-align:center; font-size:12px; opacity:0.4; margin-top:16px;'>Secured with SHA-256 encryption</p>", unsafe_allow_html=True)

    st.stop()
 # ================= ROLE CHECK =================

if st.session_state.user_id is not None:
    if st.session_state.get("role") in ["ADMIN", "admin"]:
        st.info('Admin Panel has been moved to the new React Web App')

        st.stop()





# ================= MAIN =================
 
# ================= PREMIUM HEADER =================

st.markdown("""
<div class="custom-card">
    <h1 style='font-size:40px;'>A UVE PRODUCT</h1>
    <p style='font-size:18px; opacity:0.8;'>
        Identifier and Extraction Engine
    </p>
</div>
""", unsafe_allow_html=True)
 

st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
st.subheader(" Upload Financial Statement")

uploaded_file = st.file_uploader("Upload Financial Statement PDF", type=["pdf"])
st.markdown("</div>", unsafe_allow_html=True)


if uploaded_file:
 
    password = st.text_input("Enter PDF Password (if any)", type="password")
 
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.read())
        file_path = tmp.name
    conn = get_connection()
    cursor = get_cursor(conn)
    insert_query = """
                   INSERT INTO documents (user_id, file_name, file_path, is_password_protected, status)
                   VALUES (%s, %s, %s, %s, 'UPLOADED')
                """
    document_id = execute_insert(conn, cursor, insert_query, (
                    st.session_state.user_id,
                    uploaded_file.name, file_path,
                    bool(password)
    ))
 
    if password:
        cursor.execute("""
        INSERT INTO document_password (document_id, encrypted_password)
        VALUES (%s, %s)
        """, (document_id, password))
    conn.commit()
    cursor.close()
    conn.close()
    if st.button("Run Processing"):
        st.subheader("Extracting PDF Content")
        pages = extract_pages(file_path, password)
 
        if not pages:
            st.error("No extractable text found.")
            st.stop()

 
        full_text = "\n".join(pages)
        reduced = reduce_text(pages)
        st.success("PDF extracted successfully")
        st.subheader("Checking Existing Formats")
        matched, existing_category = find_existing_identifier(full_text)
 
        if matched:
            st.success("Existing Identifier Matched")
            identity_json = existing_category["statement_identifier"]
            extraction_code = existing_category["extraction_logic"]
            st.json(identity_json)
            if not extraction_code:
                st.warning("No extraction logic found in DB. Generating via LLM...")
                text_sample = full_text[:5000]
                extraction_code = generate_extraction_logic_llm(
                    identifier_json=identity_json,
                    text_sample=text_sample
                )
            else:
                st.success("Existing extraction logic found in DB")
            with st.expander("View Extraction Code"):
                st.code(extraction_code, language="python")
            st.subheader("Executing Extraction Code...")
            try:
                code_transactions = extract_transactions_using_logic(
                    full_text,
                    extraction_code
                )
 
                st.success("Code-Based Transactions Extracted")
 
                if isinstance(code_transactions, list):
                     st.info(f"Total Code Transactions: {len(code_transactions)}")
                     st.dataframe(code_transactions, use_container_width=True)
                else:
                     st.warning("Code output is not a list.")
                     st.json(code_transactions)
            except Exception as e:
                st.error(f"Code execution failed: {e}")
            # st.subheader("Extracting Transactions via LLM...")
            # transactions_json = parse_with_llm(full_text, identity_json)
            # st.success("LLM Transactions Extracted")
            # if isinstance(transactions_json, str):
            #     try:
            #         transactions_json = safe_json_loads(transactions_json)
            #     except:
            #         st.error("Failed to parse LLM transactions JSON")
            #         st.text(transactions_json)
            #         st.stop()
            # if isinstance(transactions_json,list):
            #     st.info(f"Total Transactions Extracted: {len(transactions_json)}")
            #     st.dataframe(transactions_json,use_container_width=True)
            # else:
            #     st.warning("Transactions output is not a list.")
            #     st.json(transactions_json)
        else:
 
            st.warning("No Existing Identifier Found")
            st.info("Generating New Identifier via LLM...")
 
            identifier_json = classify_document_llm(reduced)
 
            st.success("New Identifier Generated")
            st.json(identifier_json)
            st.subheader("Generating Deterministic Extraction Code...")
 
            identity = identifier_json
            text_sample = full_text[:5000]
            try:
                extraction_code = generate_extraction_logic_llm(
                       identifier_json=identity,
                       text_sample=text_sample
                )
 
                st.success("Extraction Code Generated")
 
                with st.expander("View Generated Code"):
                    st.code(extraction_code, language="python")
 
            except Exception as e:
                st.error(f"Code generation failed: {e}")
                st.stop()
 
            save_new_statement_format(
                format_name=identifier_json["id"],
                bank_code=None,
                identifier_json=identifier_json,
                extraction_logic=extraction_code,
                threshold=65.0
            )
            st.subheader("Executing Generated Extraction Code...")
 
            try:
                code_transactions = extract_transactions_using_logic(
                full_text,
                extraction_code)
 
                st.success("Code-Based Transactions Extracted")
 
                if isinstance(code_transactions, list):
                     st.info(f"Total Code Transactions: {len(code_transactions)}")
                     st.dataframe(code_transactions, use_container_width=True)
                else:
                     st.warning("Code output is not a list.")
                     st.json(code_transactions)
 
            except Exception as e:
                st.error(f"Code execution failed: {e}")
           
            # st.subheader("Extracting Transactions via LLM...")
            # transactions_json = parse_with_llm(full_text, identifier_json)
            # st.success("LLM Transactions Extracted")
            # if isinstance(transactions_json, str):
            #     try:
            #         transactions_json = safe_json_loads(transactions_json)
            #     except:
            #         st.error("Failed to parse LLM transactions JSON")
            #         st.text(transactions_json)
            #         st.stop()
            # if isinstance(transactions_json,list):
            #     st.info(f"Total Transactions Extracted: {len(transactions_json)}")
            #     st.dataframe(transactions_json,use_container_width=True)
            # else:
            #     st.warning("Transactions output is not a list.")
            #     st.json(transactions_json)
