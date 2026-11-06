"""
Payment receipt PDF generator for the Sparkleen Krystal Record Keeper.

Mirrors core/receipt.py in look and feel (same page size, same
header, same blue title) but generates a small slip for a single
payment event — including the full payment history on the invoice
(Option B).

Does NOT touch the database. Receives prepared data and returns a
PDF path.
"""

import os
from datetime import datetime, date
from fpdf import FPDF
from core.database import DATA_DIR


def _fmt_date(value):
    """Formats a date as DD/MM/YYYY. Accepts date objects or
    YYYY-MM-DD strings; returns 'N/A' for None."""
    if value is None:
        return "N/A"
    if not isinstance(value, str):
        value = value.isoformat()
    return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")


def generate_payment_receipt(payment, invoice, history):
    """
    Generates a payment receipt PDF for a single payment event.

    Args:
        payment: dict with payment_receipt_number, amount, paid_on,
            method (may be None), customer_name, invoice_number.
        invoice: dict with invoice_number, customer_name, total_amount.
        history: list of payment dicts for the same invoice, oldest
            first. Must include the current `payment` as one of its
            elements.

    Returns:
        Absolute file path to the generated PDF.
    """

    # Derive running totals from the history
    total_paid = sum(float(p["amount"]) for p in history)
    total_amount = float(invoice["total_amount"])
    balance = max(total_amount - total_paid, 0)
    fully_paid = balance <= 0

    pdf = FPDF(orientation="P", unit="mm", format=(105, 148))
    pdf.set_left_margin(3)
    pdf.set_right_margin(3)
    pdf.set_auto_page_break(auto=True, margin=5)
    pdf.add_page()

    # ----- HEADER (same look as the drop-off receipt) -----
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

    # ----- TITLE (blue, same as drop-off receipt) -----
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(0, 0, 180)
    pdf.cell(0, 5, "PAYMENT RECEIPT", ln=True, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(0.5)
    pdf.set_draw_color(0, 0, 180)
    pdf.line(3, pdf.get_y(), 102, pdf.get_y())
    pdf.ln(1)

    # ----- DETAILS -----
    pdf.set_font("Helvetica", "", 6)
    pdf.cell(22, 3.5, "Receipt No:")
    pdf.cell(30, 3.5, payment["payment_receipt_number"])
    pdf.cell(5, 3.5, "")
    pdf.cell(15, 3.5, "Date:")
    pdf.cell(0, 3.5, _fmt_date(payment["paid_on"]), ln=True)

    pdf.cell(22, 3.5, "Invoice:")
    pdf.cell(30, 3.5, payment["invoice_number"])
    pdf.cell(5, 3.5, "")
    pdf.cell(15, 3.5, "Method:")
    pdf.cell(0, 3.5, payment.get("method") or "Cash", ln=True)

    pdf.cell(22, 3.5, "Customer:")
    pdf.cell(0, 3.5, payment["customer_name"], ln=True)
    pdf.ln(1)

    # ----- THIS PAYMENT (highlighted) -----
    pdf.set_fill_color(220, 240, 255)
    pdf.set_draw_color(0, 120, 200)
    pdf.set_font("Helvetica", "B", 7)
    pdf.cell(0, 5, "THIS PAYMENT", border=1, fill=True, ln=True, align="L")

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(0, 0, 180)
    pdf.cell(0, 8, f"N{float(payment['amount']):,.0f}", ln=True, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1)

    # ----- PAYMENT HISTORY (Option B) -----
    pdf.set_font("Helvetica", "B", 6)
    pdf.cell(0, 4, "PAYMENT HISTORY ON THIS INVOICE", ln=True)
    pdf.set_draw_color(180, 180, 180)
    pdf.line(3, pdf.get_y(), 102, pdf.get_y())
    pdf.ln(0.5)

    pdf.set_font("Helvetica", "", 6)
    for p in history:
        is_current = (
            p["payment_receipt_number"] == payment["payment_receipt_number"]
        )
        pdf.cell(30, 3.5, _fmt_date(p["paid_on"]))
        pdf.cell(25, 3.5, f"N{float(p['amount']):,.0f}")
        pdf.cell(30, 3.5, p["payment_receipt_number"])
        if is_current:
            pdf.set_font("Helvetica", "B", 6)
            pdf.set_text_color(0, 0, 180)
            pdf.cell(0, 3.5, "< this payment", ln=True)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Helvetica", "", 6)
        else:
            pdf.ln()

    pdf.ln(0.5)
    pdf.set_draw_color(180, 180, 180)
    pdf.line(3, pdf.get_y(), 102, pdf.get_y())
    pdf.ln(0.5)

    # ----- RUNNING TOTALS -----
    pdf.set_font("Helvetica", "B", 6)
    pdf.cell(0, 3.5, "RUNNING TOTALS", ln=True)

    pdf.set_font("Helvetica", "", 6)
    pdf.cell(55, 3.5, "Total billed:")
    pdf.cell(0, 3.5, f"N{total_amount:,.0f}", ln=True, align="R")

    pdf.cell(55, 3.5, "Total paid so far:")
    pdf.cell(0, 3.5, f"N{total_paid:,.0f}", ln=True, align="R")

    pdf.set_font("Helvetica", "B", 7)
    pdf.cell(55, 4, "Remaining balance:")
    pdf.cell(0, 4, f"N{balance:,.0f}", ln=True, align="R")

    # ----- STATUS -----
    pdf.ln(1)
    if fully_paid:
        pdf.set_fill_color(200, 245, 210)
        pdf.set_text_color(0, 100, 0)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(0, 6, "FULLY PAID  -  BALANCE CLEARED",
                 border=1, fill=True, ln=True, align="C")
    else:
        pdf.set_fill_color(255, 240, 200)
        pdf.set_text_color(140, 90, 0)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(0, 6, "PARTIAL PAYMENT",
                 border=1, fill=True, ln=True, align="C")
    pdf.set_text_color(0, 0, 0)

    # ----- FOOTER -----
    pdf.ln(1)
    pdf.set_draw_color(180, 180, 180)
    pdf.line(3, pdf.get_y(), 102, pdf.get_y())
    pdf.ln(1)

    pdf.set_font("Helvetica", "B", 6)
    pdf.set_text_color(0, 100, 0)
    pdf.cell(0, 3.5, "Thank you for choosing Sparkleen Krystal!",
             ln=True, align="C")

    pdf.set_font("Helvetica", "I", 4.5)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 3, "Keep this receipt for your records.",
             ln=True, align="C")

    pdf.ln(1)
    pdf.set_font("Helvetica", "I", 3.5)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 2.5, "Generated by SPARKLEEN AI Record Keeper",
             ln=True, align="C")
    pdf.set_text_color(0, 0, 0)

    # ----- SAVE -----
    receipts_dir = os.path.join(os.path.dirname(DATA_DIR), "receipts")
    os.makedirs(receipts_dir, exist_ok=True)
    filename = os.path.join(
        receipts_dir,
        f"payment_{payment['payment_receipt_number']}.pdf"
    )
    pdf.output(filename)

    return filename
