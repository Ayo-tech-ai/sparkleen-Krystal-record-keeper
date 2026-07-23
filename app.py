import streamlit as st
import pandas as pd
import asyncio
import os
from datetime import date

from core.database import init_db
from core.service import record_service
from agent.agent_setup import create_runner

# ---------------- SETUP ----------------

st.set_page_config(page_title="Sparkleen Krystal Record Keeper", page_icon="🧺", layout="centered")

if "GOOGLE_API_KEY" not in os.environ:
    try:
        os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
    except Exception:
        st.error(
            "GOOGLE_API_KEY not found. Add it to .streamlit/secrets.toml "
            "locally, or to your Streamlit Cloud app's Secrets settings."
        )
        st.stop()

init_db()

if "runner" not in st.session_state:
    runner, session_service = create_runner()
    st.session_state.runner = runner
    st.session_state.session_service = session_service
    st.session_state.session = session_service.create_session_sync(
        app_name="sparkling_crystal_app",
        user_id="owner"
    )
    st.session_state.chat_history = []

# ---------------- SIDEBAR ----------------

with st.sidebar:
    st.title("🧺 Sparkleen Krystal")
    st.caption("AI Record Keeper")

    st.divider()

    all_records = record_service.get_all_records()
    st.metric("Total Records", len(all_records))

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
                use_container_width=True
            )
        else:
            st.info("No records yet.")

# ---------------- MAIN CHAT ----------------

st.title("🧺 Sparkleen Krystal Record Keeper")

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
                    key=f"chat_receipt_{i}"
                )

user_input = st.chat_input("Describe a drop-off, search records, or ask a question...")

if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    async def get_response():
        events = await st.session_state.runner.run_debug(
            user_input,
            user_id="owner",
            session_id=st.session_state.session.id,
            quiet=True,
            verbose=False
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
                        key="latest_receipt"
                    )

    st.session_state.chat_history.append({
        "role": "assistant",
        "content": response_text,
        "receipt_path": receipt_path
    })
