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


def get_business_summary(start_date: str, end_date: str):
    """
    Get a business dashboard for a period: billed (total revenue),
    actual cash collected, and outstanding on those jobs.

    Use this when the owner asks how business was for a period —
    e.g. "this week", "last week", "last month", or any range.

    IMPORTANT: Resolve the period into exact start and end dates
    BEFORE calling this tool. Weeks run Monday to Sunday. Months
    are calendar months. Both dates are inclusive.

    The three money numbers mean different things:
    - total_revenue   = what was billed (drop-offs in the period)
    - total_collected = what was actually paid (payments received
                        in the period, regardless of when the job
                        was dropped off)
    - total_outstanding = what is still owed on jobs from this
                        period (current unpaid balance)

    Args:
        start_date: First day of the period, exact YYYY-MM-DD.
        end_date: Last day of the period, exact YYYY-MM-DD.
    """
    return record_service.get_business_summary(
        start_date=start_date,
        end_date=end_date,
    )

def record_payment(
    invoice_number: str,
    amount: float,
    method: Optional[str] = None,
    paid_on: Optional[str] = None,
):
    """
    Record a payment against an existing invoice.

    IMPORTANT: Only call this after the owner has explicitly
    confirmed the payment summary you presented. Never call this
    on the first mention of a payment — always show a summary
    first and wait for confirmation.

    IMPORTANT: The invoice_number must be an exact existing
    invoice number (e.g. "SC-20261103-001"). If the owner didn't
    provide one, use search_records first to find the right
    invoice. If multiple open invoices exist for the customer,
    ask the owner which one — never guess.

    Rejects overpayments: amount cannot exceed the invoice's
    current balance.

    Args:
        invoice_number: Exact invoice number, e.g. "SC-20261103-001".
        amount: Amount being paid now (this payment only, not the
            running total). Must be greater than zero and no more
            than the current balance.
        method: Optional payment method, e.g. "cash", "transfer".
        paid_on: Optional "YYYY-MM-DD" date the payment was made.
            Defaults to today if not given.
    """
    return record_service.record_payment(
        invoice_number=invoice_number,
        amount=amount,
        method=method,
        paid_on=paid_on,
    )


def get_payments_for_invoice(invoice_number: str):
    """
    Return all payments recorded against a single invoice, oldest
    first. Use this when the owner asks for the payment history of
    an invoice, how much has been paid so far, or how many times
    a customer has paid.

    Returns an empty list if no payments exist yet — that is not
    an error, it just means nothing has been paid on that invoice.

    Args:
        invoice_number: Exact invoice number, e.g. "SC-20261103-001".
    """
    return record_service.get_payments_for_invoice(invoice_number)


def get_outstanding_balances(customer_name: Optional[str] = None):
    """
    Return all customers who currently owe money, grouped by
    customer name, plus the grand total owed.

    Use this when the owner asks any of:
      - "Who owes me?"
      - "How much am I owed right now?"
      - "How much does Chioma owe?"
      - "Show me all outstanding balances."

    If `customer_name` is given, only that customer's open
    invoices are returned (case-insensitive, partial match). If
    not given, every customer with a balance is returned.

    Returns a dict with:
      total_outstanding: total owed across all returned customers
      customer_count: number of customers who owe
      customers: list of per-customer dicts, each with
        customer_name, invoice_count, outstanding, and invoices
        (list of {invoice_number, balance, dropoff_date}),
        sorted with the biggest debtor first.

    If nobody owes money, total_outstanding is 0.0 and
    customers is an empty list — this is not an error.

    Args:
        customer_name: optional partial name to filter by.
    """
    return record_service.get_outstanding_balances(
        customer_name=customer_name,
    )
