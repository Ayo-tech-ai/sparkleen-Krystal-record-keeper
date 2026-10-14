import streamlit as st
import pandas as pd
import asyncio
import os
from datetime import date

from core.database import init_db
from core.service import record_service
from agent.agent_setup import create_runner

# ---------------- SETUP ----------------

st.set_page_config(
    page_title="Sparkleen Krystal Record Keeper",
    page_icon="🧺",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ---------- CUSTOM BRAND CSS ----------
st.markdown(
    """
    <style>
    /* ---- Fonts ---- */
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', 'Poppins', sans-serif;
    }

    /* ---- App background: soft laundry-day gradient ---- */
    .stApp {
        background:
            radial-gradient(circle at 0% 0%, #e8f4ff 0%, transparent 45%),
            radial-gradient(circle at 100% 100%, #e6fbf7 0%, transparent 45%),
            linear-gradient(180deg, #fbfdff 0%, #f4f8fc 100%);
    }

    /* ---- Hide default Streamlit chrome ---- */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* ---- Hero banner ---- */
    .hero-banner {
        background: linear-gradient(120deg, #0a84ff 0%, #23c4c9 100%);
        border-radius: 20px;
        padding: 26px 32px;
        color: white;
        margin-bottom: 22px;
        box-shadow: 0 10px 30px rgba(10, 132, 255, 0.25);
        position: relative;
        overflow: hidden;
    }
    .hero-banner::after {
        content: "🧺  ✨  🫧";
        position: absolute;
        right: 24px;
        top: 50%;
        transform: translateY(-50%);
        font-size: 44px;
        opacity: 0.28;
        letter-spacing: 8px;
    }
    .hero-banner h1 {
        font-family: 'Poppins', sans-serif;
        font-size: 30px;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.4px;
        color: #ffffff !important;
    }
    .hero-banner p {
        margin: 6px 0 0 0;
        font-size: 15px;
        opacity: 0.95;
        color: #eaf6ff !important;
    }

    /* ---- Sidebar ---- */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #ffffff 0%, #f4f9ff 100%);
        border-right: 1px solid #e3edf7;
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 1.4rem;
    }

    /* Sidebar brand title */
    .sidebar-brand {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 4px;
    }
    .sidebar-brand .logo {
        width: 44px;
        height: 44px;
        border-radius: 12px;
        background: linear-gradient(135deg, #0a84ff, #23c4c9);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 22px;
        box-shadow: 0 6px 16px rgba(10, 132, 255, 0.28);
    }
    .sidebar-brand h2 {
        font-family: 'Poppins', sans-serif;
        font-size: 19px;
        font-weight: 700;
        margin: 0;
        color: #0a2540;
    }
    .sidebar-brand span {
        font-size: 12px;
        color: #6b7f92;
        letter-spacing: 0.4px;
        text-transform: uppercase;
        font-weight: 500;
    }

    /* ---- Metric card ---- */
    .metric-card {
        background: linear-gradient(135deg, #ffffff, #f0f9ff);
        border: 1px solid #d6eafb;
        border-radius: 16px;
        padding: 18px 20px;
        text-align: center;
        box-shadow: 0 4px 14px rgba(10, 132, 255, 0.08);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 22px rgba(10, 132, 255, 0.15);
    }
    .metric-card .metric-label {
        font-size: 12px;
        color: #5c7488;
        text-transform: uppercase;
        letter-spacing: 0.9px;
        font-weight: 600;
    }
    .metric-card .metric-value {
        font-family: 'Poppins', sans-serif;
        font-size: 34px;
        font-weight: 700;
        color: #0a84ff;
        line-height: 1.1;
        margin-top: 4px;
    }

    /* ---- Buttons ---- */
    .stButton > button, .stDownloadButton > button {
        border-radius: 12px !important;
        border: none !important;
        background: linear-gradient(135deg, #0a84ff 0%, #23c4c9 100%) !important;
        color: white !important;
        font-weight: 600 !important;
        font-family: 'Poppins', sans-serif !important;
        padding: 10px 14px !important;
        transition: transform 0.15s ease, box-shadow 0.15s ease !important;
        box-shadow: 0 4px 12px rgba(10, 132, 255, 0.22) !important;
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 20px rgba(10, 132, 255, 0.32) !important;
        color: white !important;
    }

    /* ---- Chat messages ---- */
    div[data-testid="stChatMessage"] {
        background: #ffffff;
        border-radius: 16px;
        padding: 14px 18px;
        margin-bottom: 10px;
        border: 1px solid #e8f0f7;
        box-shadow: 0 2px 8px rgba(10, 132, 255, 0.05);
    }
    /* User messages — subtle blue tint */
    div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {
        background: linear-gradient(135deg, #eaf5ff 0%, #f4fbff 100%);
        border-color: #cfe6fb;
    }

    /* ---- Chat input ---- */
    div[data-testid="stChatInput"] textarea {
        border-radius: 14px !important;
        border: 1.5px solid #cfe6fb !important;
        background: #ffffff !important;
        font-size: 15px !important;
        box-shadow: 0 2px 10px rgba(10, 132, 255, 0.06) !important;
    }
    div[data-testid="stChatInput"] textarea:focus {
        border-color: #0a84ff !important;
        box-shadow: 0 0 0 3px rgba(10, 132, 255, 0.14) !important;
    }

    /* ---- Divider tint ---- */
    hr {
        border-color: #e3edf7 !important;
    }

    /* ---- Spinner color ---- */
    .stSpinner > div > div {
        border-top-color: #0a84ff !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Load secrets from Streamlit secrets.toml / Cloud Secrets into os.environ
# BEFORE core modules read them (core.database reads SUPABASE_DB_URL at import).
for key in ("GOOGLE_API_KEY", "SUPABASE_DB_URL"):
    if key not in os.environ:
        try:
            os.environ[key] = st.secrets[key]
        except Exception:
            st.error(
                f"{key} not found. Add it to .streamlit/secrets.toml "
                "locally, or to your Streamlit Cloud app's Secrets settings."
            )
            st.stop()

init_db()

# Fixed session ID: one persistent web session shared across page loads,
# stored in Supabase (get-or-create, so refresh doesn't accumulate sessions).
WEB_USER_ID = "owner"
WEB_SESSION_ID = "web_owner"


async def _get_or_create_web_session(session_service):
    try:
        return await session_service.get_session(
            app_name="sparkling_crystal_app",
            user_id=WEB_USER_ID,
            session_id=WEB_SESSION_ID,
        )
    except Exception:
        return await session_service.create_session(
            app_name="sparkling_crystal_app",
            user_id=WEB_USER_ID,
            session_id=WEB_SESSION_ID,
        )


if "runner" not in st.session_state:
    runner, session_service = create_runner()
    st.session_state.runner = runner
    # DatabaseSessionService exposes async APIs — run via asyncio.run
    st.session_state.session = asyncio.run(_get_or_create_web_session(session_service))
    st.session_state.chat_history = []

# ---------------- SIDEBAR ----------------

with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
            <div class="logo">🧺</div>
            <div>
                <h2>Sparkleen Krystal</h2>
                <span>AI Record Keeper</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    all_records = record_service.get_all_records()
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">📋 Total Records</div>
            <div class="metric-value">{len(all_records):,}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    if st.button("📊 Export All Records (CSV)", use_container_width=True):
        if all_records:
            flat_records = []
            for r in all_records:
                flat = {k: v for k, v in r.items() if k != "items"}
                flat["items_summary"] = "; ".join(
                    f"{i['qty']}x {i['name']} (₦{i['amount']:,.0f})" for i in r["items"]
                )
                flat_records.append(flat)
            df = pd.DataFrame(flat_records)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download CSV",
                csv,
                file_name=f"sparkleen_krystal_records_{date.today().isoformat()}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.info("No records yet.")

    st.markdown(
        """
        <div style="position:absolute;bottom:20px;left:0;right:0;
                    text-align:center;font-size:11px;color:#93a6b8;">
            Fresh • Clean • Precise ✨
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------------- MAIN CHAT ----------------

st.markdown(
    """
    <div class="hero-banner">
        <h1>🧺 Sparkleen Krystal Record Keeper</h1>
        <p>Log drop-offs, search past orders, and ask questions — all in one place.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

for i, msg in enumerate(st.session_state.chat_history):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("receipt_path"):
            with open(msg["receipt_path"], "rb") as f:
                st.download_button(
                    "📄 Download Receipt",
                    f,
                    file_name=os.path.basename(msg["receipt_path"]),
                    mime="application/pdf",
                    key=f"chat_receipt_{i}",
                )

user_input = st.chat_input("Describe a drop-off, search records, or ask a question...")

if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    async def get_response():
        events = await st.session_state.runner.run_debug(
            user_input,
            user_id=WEB_USER_ID,
            session_id=WEB_SESSION_ID,
            quiet=True,
            verbose=False,
        )
        final_event = events[-1]

        receipt_path = None
        for event in events:
            if event.get_function_responses():
                for fr in event.get_function_responses():
                    response_data = fr.response
                    if isinstance(response_data, dict) and response_data.get("receipt_file"):
                        receipt_path = response_data["receipt_file"]

        if final_event.content and final_event.content.parts:
            text = " ".join(part.text for part in final_event.content.parts if part.text)
        else:
            text = "No response was generated."

        return text, receipt_path

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response_text, receipt_path = asyncio.run(get_response())
            except Exception as e:
                error_str = str(e).lower()
                if "resourceexhausted" in error_str or "quota" in error_str or "rate" in error_str:
                    response_text = (
                        "I'm a bit busy right now (API limit reached). "
                        "Please wait a moment and try again."
                    )
                else:
                    response_text = (
                        "Something went wrong on my end. Please try that again."
                    )
                receipt_path = None

            st.markdown(response_text)
            if receipt_path:
                with open(receipt_path, "rb") as f:
                    st.download_button(
                        "📄 Download Receipt",
                        f,
                        file_name=os.path.basename(receipt_path),
                        mime="application/pdf",
                        key="latest_receipt",
                    )

    st.session_state.chat_history.append({
        "role": "assistant",
        "content": response_text,
        "receipt_path": receipt_path,
    })
