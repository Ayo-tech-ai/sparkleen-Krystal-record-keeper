from datetime import datetime
from fpdf import FPDF
import os
from core.database import DATA_DIR


def generate_receipt(record, late_fee_percent=0.15):
    """
    Generates a professional PDF receipt for a dropoff record
    and returns the file path.
    """

    items = record["items"]
    total_units = record["total_units"]
    total_amount = record["total_amount"]
    payment_status = record["payment_status"]
    amount_paid = record["amount_paid"]
    balance = record["balance"]
    collection_date = record.get("collection_date")

    pdf = FPDF(orientation="P", unit="mm", format=(105, 148))
    pdf.set_left_margin(3)
    pdf.set_right_margin(3)
    pdf.set_auto_page_break(auto=True, margin=5)
    pdf.add_page()

    # ----- HEADER -----
    pdf.set_draw_color(200, 200, 200)
    pdf.set_fill_color(240, 240, 240)
    pdf.rect(3, 3, 99, 20, "DF")

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(0, 100, 0)
    pdf.cell(0, 6, "SPARKLEEN KRYSTAL", ln=True, align="C")

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 4, "DRY CLEANING SHOP", ln=True, align="C")

    pdf.set_font("Helvetica", "", 6)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 3.5, "Warri, Delta State", ln=True, align="C")

    pdf.set_text_color(0, 0, 0)

    # ----- RECEIPT TITLE -----
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 5, "RECEIPT", ln=True, align="C")
    pdf.ln(0.5)
    pdf.set_draw_color(180, 180, 180)
    pdf.line(3, pdf.get_y(), 102, pdf.get_y())
    pdf.ln(1)

    # ----- RECEIPT DETAILS -----
    dropoff_display = datetime.strptime(record["dropoff_date"], "%Y-%m-%d").strftime("%d/%m/%Y")

    pdf.set_font("Helvetica", "", 6)
    pdf.cell(22, 3.5, "Invoice:")
    pdf.cell(30, 3.5, record["invoice_number"])
    pdf.cell(5, 3.5, "")
    pdf.cell(15, 3.5, "Date:")
    pdf.cell(0, 3.5, dropoff_display, ln=True)

    pdf.cell(22, 3.5, "Customer:")
    pdf.cell(30, 3.5, record["customer_name"])
    pdf.cell(5, 3.5, "")
    pdf.cell(15, 3.5, "Service:")
    pdf.cell(0, 3.5, record.get("service_type") or "N/A", ln=True)
    pdf.ln(0.5)

    # ----- ITEMS TABLE -----
    col_item = 50
    col_qty = 20
    col_amount = 25

    pdf.set_font("Helvetica", "B", 6)
    pdf.set_fill_color(200, 200, 200)
    pdf.cell(col_item, 4.5, "Item", border=1, fill=True)
    pdf.cell(col_qty, 4.5, "Qty", border=1, align="C", fill=True)
    pdf.cell(col_amount, 4.5, "Amount", border=1, align="R", fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 6)
    for i, item in enumerate(items):
        pdf.set_fill_color(248, 248, 248) if i % 2 == 0 else pdf.set_fill_color(255, 255, 255)
        pdf.cell(col_item, 4, item["name"], border=1, fill=True)
        pdf.cell(col_qty, 4, str(item["qty"]), border=1, align="C", fill=True)
        pdf.cell(col_amount, 4, f"N{item['amount']:,}", border=1, align="R", fill=True)
        pdf.ln()

    pdf.set_font("Helvetica", "B", 6)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(col_item, 4.5, "TOTAL", border=1, align="R", fill=True)
    pdf.cell(col_qty, 4.5, str(total_units), border=1, align="C", fill=True)
    pdf.cell(col_amount, 4.5, f"N{total_amount:,.0f}", border=1, align="R", fill=True)
    pdf.ln()

    # ----- PAYMENT SUMMARY -----
    pdf.ln(0.5)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(3, pdf.get_y(), 102, pdf.get_y())
    pdf.ln(0.5)

    status_display = {
        "full": f"Full Payment (N{amount_paid:,.0f} paid)",
        "partial": f"Partial Payment (N{amount_paid:,.0f} paid)",
        "none": "No Payment"
    }[payment_status]

    pdf.set_font("Helvetica", "B", 6)
    pdf.cell(0, 3.5, "PAYMENT SUMMARY", ln=True)

    pdf.set_font("Helvetica", "", 6)
    pdf.cell(0, 3.5, f"Status: {status_display} | Balance: N{balance:,.0f}", ln=True)

    # ----- COLLECTION DETAILS -----
    if collection_date:
        pdf.ln(0.5)
        pdf.set_font("Helvetica", "B", 6)
        pdf.cell(0, 3.5, "COLLECTION DETAILS", ln=True)

        collection_display = datetime.strptime(collection_date, "%Y-%m-%d").strftime("%d/%m/%Y")

        pdf.set_font("Helvetica", "", 6)
        pdf.cell(0, 3.5, f"Collection Date: {collection_display}", ln=True)

        if balance > 0:
            pdf.ln(0.5)
            late_fee = balance * late_fee_percent
            total_with_late_fee = balance + late_fee
            rounded_total = round(total_with_late_fee / 100) * 100

            pdf.set_font("Helvetica", "I", 5)
            pdf.set_text_color(180, 0, 0)
            pdf.cell(0, 3, "If not collected by the above date:", ln=True)

            pdf.set_font("Helvetica", "B", 7)
            pdf.cell(0, 4, f"Amount due becomes: N{rounded_total:,.0f}", ln=True)
            pdf.set_text_color(0, 0, 0)

    # ----- FOOTER -----
    pdf.ln(0.5)
    pdf.set_draw_color(180, 180, 180)
    pdf.line(3, pdf.get_y(), 102, pdf.get_y())
    pdf.ln(0.5)

    pdf.set_font("Helvetica", "B", 5)
    pdf.set_text_color(180, 0, 0)
    pdf.multi_cell(
        0, 3,
        "IMPORTANT: Verify quantity on collection.\n"
        "Once delivered, no claims for missing items will be accepted.",
        align="L"
    )
    pdf.set_text_color(0, 0, 0)
    pdf.ln(0.5)

    pdf.set_font("Helvetica", "B", 6)
    pdf.set_text_color(0, 100, 0)
    pdf.cell(0, 3.5, "Thank you for choosing Sparkleen Krystal!", ln=True, align="C")

    pdf.set_font("Helvetica", "I", 4.5)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 3, "We value your trust.", ln=True, align="C")

    pdf.ln(1)
    pdf.set_font("Helvetica", "I", 3.5)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 2.5, "Generated by AI Record Keeper", ln=True, align="C")
    pdf.set_text_color(0, 0, 0)

    receipts_dir = os.path.join(os.path.dirname(DATA_DIR), "receipts")
    os.makedirs(receipts_dir, exist_ok=True)
    filename = os.path.join(receipts_dir, f"receipt_{record['invoice_number']}.pdf")
    pdf.output(filename)

    return filename
