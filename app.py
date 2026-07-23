import streamlit as st
import pandas as pd
import asyncio
from datetime import date
import os

from core.database import init_db
from core.service import record_service
from core.receipt import generate_receipt
from agent.agent_setup import create_runner

if "GOOGLE_API_KEY" not in os.environ:
    try:
        os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
    except Exception:
        st.error(
            "GOOGLE_API_KEY not found. Add it to .streamlit/secrets.toml "
            "locally, or to your Streamlit Cloud app's Secrets settings."
        )
        st.stop()

# ---------------- SETUP ----------------

st.set_page_config(page_title="Sparkleen Krystal Record Keeper", page_icon="🧺", layout="wide")

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

st.title("🧺 Sparkleen Krystal Record Keeper")

tab_form, tab_chat = st.tabs(["📋 Manual Entry & Records", "💬 Chat Assistant"])

# ---------------- TAB 1: FORM + SEARCH + CSV ----------------

with tab_form:
    st.subheader("Record a Drop-off")

    with st.form("dropoff_form", clear_on_submit=True):
        customer_name = st.text_input("Customer Name")

        st.markdown("**Items**")
        num_items = st.number_input("Number of item lines", min_value=1, max_value=10, value=1, step=1)

        items = []
        for i in range(int(num_items)):
            cols = st.columns([3, 1, 2])
            item_name = cols[0].text_input(f"Item {i+1} name", key=f"item_name_{i}")
            item_qty = cols[1].number_input(f"Qty", min_value=1, value=1, step=1, key=f"item_qty_{i}")
            item_amount = cols[2].number_input(f"Amount (₦)", min_value=0.0, value=0.0, step=100.0, key=f"item_amount_{i}")
            items.append({"name": item_name, "qty": item_qty, "amount": item_amount})

        col1, col2 = st.columns(2)
        amount_paid = col1.number_input("Amount Paid (₦)", min_value=0.0, value=0.0, step=100.0)
        service_type = col2.selectbox("Service Type", ["Wash & Iron", "Wash Only", "Iron Only"])

        collection_date = st.date_input("Collection Date (optional)", value=None)

        submitted = st.form_submit_button("Save & Generate Receipt")

        if submitted:
            valid_items = [item for item in items if item["name"].strip()]
            if not customer_name.strip():
                st.error("Customer name is required.")
            elif not valid_items:
                st.error("At least one item is required.")
            else:
                result = record_service.create_dropoff_record(
                    customer_name=customer_name.strip(),
                    items=valid_items,
                    amount_paid=amount_paid,
                    service_type=service_type,
                    collection_date=collection_date.isoformat() if collection_date else None,
                )
                pdf_path = generate_receipt(result)

                st.success(f"Saved! Invoice: {result['invoice_number']}")

                with open(pdf_path, "rb") as f:
                    st.download_button(
                        "📄 Download Receipt",
                        f,
                        file_name=f"{result['invoice_number']}.pdf",
                        mime="application/pdf"
                    )

    st.divider()
    st.subheader("Search Records")

    scol1, scol2, scol3, scol4 = st.columns(4)
    search_name = scol1.text_input("Customer Name", key="search_name")
    search_invoice = scol2.text_input("Invoice Number", key="search_invoice")
    search_date = scol3.date_input("Drop-off Date", value=None, key="search_date")
    search_status = scol4.selectbox("Payment Status", ["Any", "full", "partial", "none"], key="search_status")

    if st.button("Search"):
        records = record_service.search_records(
            customer_name=search_name or None,
            invoice_number=search_invoice or None,
            dropoff_date=search_date.isoformat() if search_date else None,
            payment_status=None if search_status == "Any" else search_status,
        )
        st.session_state.search_results = records

    if "search_results" in st.session_state:
        records = st.session_state.search_results
        st.write(f"{len(records)} record(s) found")
        for r in records:
            with st.expander(f"{r['invoice_number']} — {r['customer_name']} — ₦{r['total_amount']:,.0f}"):
                st.write(f"**Items:** {', '.join(f'{i['qty']}x {i['name']} (₦{i['amount']:,.0f})' for i in r['items'])}")
                st.write(f"**Payment:** {r['payment_status']} | Paid: ₦{r['amount_paid']:,.0f} | Balance: ₦{r['balance']:,.0f}")
                st.write(f"**Dropoff:** {r['dropoff_date']} | **Collection:** {r.get('collection_date') or 'N/A'}")
                if st.button("Reprint Receipt", key=f"reprint_{r['invoice_number']}"):
                    pdf_path = generate_receipt(r)
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            "📄 Download",
                            f,
                            file_name=f"{r['invoice_number']}.pdf",
                            mime="application/pdf",
                            key=f"dl_{r['invoice_number']}"
                        )

    st.divider()
    st.subheader("Export All Records")

    if st.button("Generate CSV"):
        all_records = record_service.get_all_records()
        if all_records:
            flat_records = []
            for r in all_records:
                flat = {k: v for k, v in r.items() if k != "items"}
                flat["items_summary"] = "; ".join(f"{i['qty']}x {i['name']} (₦{i['amount']:,.0f})" for i in r["items"])
                flat_records.append(flat)
            df = pd.DataFrame(flat_records)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download CSV", csv, file_name=f"sparkleen_krystal_records_{date.today().isoformat()}.csv", mime="text/csv")
        else:
            st.info("No records yet.")

# ---------------- TAB 2: CHAT ----------------

with tab_chat:
    st.subheader("Chat with the Record Keeper")

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

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
            if final_event.content and final_event.content.parts:
                return " ".join(part.text for part in final_event.content.parts if part.text)
            return "No response was generated."

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = asyncio.run(get_response())
                st.markdown(response)

        st.session_state.chat_history.append({"role": "assistant", "content": response})
