#import json
#from datetime import date, datetime
#from core.database import get_connection
#from core.helpers import now_wat_str, today_wat_date, generate_invoice_number

import json
from datetime import date, datetime
from core.database import get_connection
from core.helpers import (
    now_wat_str,
    today_wat_date,
    generate_invoice_number,
    generate_payment_receipt_number,
)
from core.payment_receipt import generate_payment_receipt


def _serialize_record(record):
    """Converts date/datetime fields to ISO strings so results are
    JSON-safe. Leaves None alone and passes strings through unchanged.

    Touches only the two date columns the dropoff_records table has.
    """
    if not record:
        return record

    for field in ("dropoff_date", "collection_date"):
        value = record.get(field)
        if isinstance(value, (date, datetime)):
            record[field] = value.isoformat()
        # None and str are left as-is
    return record


class RecordKeeperService:

    # ---------------- DROP-OFF RECORDS ----------------

    def create_dropoff_record(self, customer_name, items, amount_paid,
                               service_type=None, collection_date=None):
        """
        items: list of dicts like [{"name": ..., "qty": ..., "amount": ...}, ...]
        amount_paid: total amount the customer paid at drop-off
        """
        total_units = sum(item["qty"] for item in items)
        total_amount = sum(item["amount"] for item in items)
        balance = total_amount - amount_paid

        if amount_paid <= 0:
            payment_status = "none"
        elif balance <= 0:
            payment_status = "full"
        else:
            payment_status = "partial"

        invoice_number = generate_invoice_number()
        dropoff_date = today_wat_date()

        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO dropoff_records
                    (invoice_number, customer_name, items, total_units, total_amount,
                     payment_status, amount_paid, balance, service_type,
                     dropoff_date, collection_date, late_fee_applied, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (invoice_number, customer_name, json.dumps(items), total_units,
                     total_amount, payment_status, amount_paid, max(balance, 0),
                     service_type, dropoff_date, collection_date,
                     False, now_wat_str())
                )

        return _serialize_record({
            "success": True,
            "invoice_number": invoice_number,
            "customer_name": customer_name,
            "items": items,
            "total_units": total_units,
            "total_amount": total_amount,
            "payment_status": payment_status,
            "amount_paid": amount_paid,
            "balance": max(balance, 0),
            "service_type": service_type,
            "dropoff_date": dropoff_date,
            "collection_date": collection_date,
        })

    # ---------------- SEARCH ----------------

    def search_records(self, customer_name=None, invoice_number=None,
                        dropoff_date=None, payment_status=None):
        query = "SELECT * FROM dropoff_records WHERE 1=1"
        params = []

        if customer_name:
            query += " AND LOWER(customer_name) LIKE LOWER(%s)"
            params.append(f"%{customer_name}%")

        if invoice_number:
            query += " AND invoice_number = %s"
            params.append(invoice_number)

        if dropoff_date:
            query += " AND dropoff_date = %s"
            params.append(dropoff_date)

        if payment_status:
            query += " AND payment_status = %s"
            params.append(payment_status)

        query += " ORDER BY created_at DESC"

        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()

        results = []
        for record in rows:
            record = dict(record)
            record["items"] = json.loads(record["items"])
            results.append(_serialize_record(record))

        return results

    def get_record_by_invoice(self, invoice_number):
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM dropoff_records WHERE invoice_number = %s",
                    (invoice_number,)
                )
                record = cursor.fetchone()

        if not record:
            return None

        record = dict(record)
        record["items"] = json.loads(record["items"])
        return _serialize_record(record)

    def get_all_records(self):
        """Returns all records, most recent first — used for CSV export."""
        return self.search_records()

    # ---------------- ACCOUNTING ----------------

    def get_business_summary(self, start_date, end_date):
        """
        Returns total revenue and number of drop-offs for records
        whose dropoff_date falls between start_date and end_date
        (both inclusive).

        start_date and end_date are 'YYYY-MM-DD' strings.
        """
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        COALESCE(SUM(total_amount), 0) AS total_revenue,
                        COUNT(*) AS dropoff_count
                    FROM dropoff_records
                    WHERE dropoff_date BETWEEN %s AND %s
                    """,
                    (start_date, end_date)
                )
                row = cursor.fetchone()

        return {
            "start_date": start_date,
            "end_date": end_date,
            "total_revenue": float(row["total_revenue"]),
            "dropoff_count": int(row["dropoff_count"]),
        }

    # ---------------- PAYMENTS ----------------

    def record_payment(self, invoice_number, amount,
                        method=None, paid_on=None):
        """
        Records a payment against an existing invoice.

        - invoice_number: the invoice this payment is for.
        - amount: this payment only (not the running total).
        - method: optional ("cash", "transfer", etc.).
        - paid_on: optional "YYYY-MM-DD"; defaults to today (WAT).

        Rejects overpayments — amount cannot exceed the invoice's
        current balance. Recomputes the invoice's amount_paid and
        balance from the full payments ledger after inserting, so
        the cached values on dropoff_records are always correct.

        Returns a dict with:
          success: True/False
          message: reason if success is False
          payment: the inserted payment row (if success)
          invoice: the updated invoice snapshot (if success)
          receipt_file: path to the generated payment receipt PDF
        """
        invoice = self.get_record_by_invoice(invoice_number)
        if not invoice:
            return {
                "success": False,
                "message": f"No invoice found for {invoice_number}.",
            }

        current_balance = float(invoice["balance"] or 0)
        amount = float(amount)

        if amount <= 0:
            return {
                "success": False,
                "message": "Payment amount must be greater than zero.",
            }

        if amount > current_balance:
            return {
                "success": False,
                "message": (
                    f"Payment of ₦{amount:,.0f} exceeds the outstanding "
                    f"balance of ₦{current_balance:,.0f} on invoice "
                    f"{invoice_number}."
                ),
            }

        paid_on = paid_on or today_wat_date()

        with get_connection() as connection:
            with connection.cursor() as cursor:
                # 1. Insert the payment row
                payment_receipt_number = generate_payment_receipt_number()
                cursor.execute(
                    """
                    INSERT INTO payments
                    (payment_receipt_number, invoice_number, customer_name,
                     amount, paid_on, method)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (payment_receipt_number, invoice_number,
                     invoice["customer_name"], amount, paid_on, method)
                )

                # 2. Recompute totals from the ledger
                cursor.execute(
                    """
                    SELECT COALESCE(SUM(amount), 0) AS total_paid
                    FROM payments
                    WHERE invoice_number = %s
                    """,
                    (invoice_number,)
                )
                total_paid = float(cursor.fetchone()["total_paid"])

                total_amount = float(invoice["total_amount"])
                new_balance = max(total_amount - total_paid, 0)

                if new_balance <= 0:
                    new_status = "full"
                elif total_paid > 0:
                    new_status = "partial"
                else:
                    new_status = "none"

                # 3. Update the invoice's cached values
                cursor.execute(
                    """
                    UPDATE dropoff_records
                    SET amount_paid = %s,
                        balance = %s,
                        payment_status = %s
                    WHERE invoice_number = %s
                    """,
                    (total_paid, new_balance, new_status, invoice_number)
                )

        # 4. Build the return payload from fresh state
        payment_row = {
            "payment_receipt_number": payment_receipt_number,
            "invoice_number": invoice_number,
            "customer_name": invoice["customer_name"],
            "amount": amount,
            "paid_on": paid_on,
            "method": method,
        }
        updated_invoice = self.get_record_by_invoice(invoice_number)

        # 5. Generate the payment receipt PDF (mirrors record_dropoff)
        history = self.get_payments_for_invoice(invoice_number)
        receipt_path = generate_payment_receipt(
            payment=payment_row,
            invoice=updated_invoice,
            history=history,
        )

        return {
            "success": True,
            "payment": payment_row,
            "invoice": updated_invoice,
            "receipt_file": receipt_path,
        }

    def get_payments_for_invoice(self, invoice_number):
        """Returns all payments for an invoice, oldest first.
        Used by the payment receipt and 'how much has been paid'
        queries."""
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT payment_receipt_number, invoice_number,
                           customer_name, amount, paid_on, method, created_at
                    FROM payments
                    WHERE invoice_number = %s
                    ORDER BY paid_on ASC, created_at ASC
                    """,
                    (invoice_number,)
                )
                rows = cursor.fetchall()

        results = []
        for row in rows:
            row = dict(row)
            # paid_on is a DATE column — serialize like the rest
            if isinstance(row["paid_on"], (date, datetime)):
                row["paid_on"] = row["paid_on"].isoformat()
            results.append(row)

        return results


record_service = RecordKeeperService()
