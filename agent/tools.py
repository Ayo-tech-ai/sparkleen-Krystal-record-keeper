from typing import Optional, List, Dict, Any
from core.helpers import _to_float
from core.service import record_service
from core.receipt import generate_receipt


def record_dropoff(
    customer_name: str,
    items: List[Dict[str, Any]],
    amount_paid: Optional[str] = None,
    service_type: Optional[str] = None,
    collection_date: Optional[str] = None,
):
    """
    Save a CONFIRMED drop-off record to the database and generate a
    PDF receipt.

    IMPORTANT: Only call this after the owner has explicitly
    confirmed the intake summary you presented. Never call this on
    the first mention of a drop-off — always show a structured
    summary first and wait for confirmation.

    Args:
        customer_name: Name of the customer dropping off items.
        items: List of items, each a dict with keys "name" (str),
            "qty" (int), and "amount" (number, the price for that
            item line, not per-unit).
        amount_paid: How much the customer paid at drop-off. If not
            mentioned, treat as 0 (no payment).
        service_type: e.g. "Wash & Iron", "Wash Only", "Iron Only".
        collection_date: Agreed pick-up date, converted to exact
            YYYY-MM-DD before calling this tool. Omit if not
            discussed.
    """
    parsed_paid = _to_float(amount_paid, "amount_paid") or 0

    result = record_service.create_dropoff_record(
        customer_name=customer_name,
        items=items,
        amount_paid=parsed_paid,
        service_type=service_type,
        collection_date=collection_date,
    )

    pdf_path = generate_receipt(result)
    result["receipt_file"] = pdf_path

    return result


def search_records(
    customer_name: Optional[str] = None,
    invoice_number: Optional[str] = None,
    dropoff_date: Optional[str] = None,
    payment_status: Optional[str] = None,
):
    """
    Search past drop-off records by customer name, invoice number,
    date, or payment status. At least one filter should be given.

    Args:
        customer_name: Partial or full customer name to search for.
        invoice_number: Exact invoice number, e.g. "SC-20260723-001".
        dropoff_date: Exact date, YYYY-MM-DD. Convert relative
            references ("today", "yesterday") before calling.
        payment_status: One of "full", "partial", "none".
    """
    results = record_service.search_records(
        customer_name=customer_name,
        invoice_number=invoice_number,
        dropoff_date=dropoff_date,
        payment_status=payment_status,
    )
    return {"count": len(results), "records": results}


def get_receipt_for_invoice(invoice_number: str):
    """
    Re-generate the PDF receipt for an existing invoice, e.g. if the
    owner needs to resend or reprint it.

    Args:
        invoice_number: Exact invoice number, e.g. "SC-20260723-001".
    """
    record = record_service.get_record_by_invoice(invoice_number)

    if not record:
        return {"success": False, "message": f"No record found for invoice {invoice_number}."}

    pdf_path = generate_receipt(record)
    return {"success": True, "invoice_number": invoice_number, "receipt_file": pdf_path}
