import json
import sqlite3
from core.database import get_connection
from core.helpers import now_wat_str, today_wat_date, generate_invoice_number


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

        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO dropoff_records
            (invoice_number, customer_name, items, total_units, total_amount,
             payment_status, amount_paid, balance, service_type,
             dropoff_date, collection_date, late_fee_applied, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (invoice_number, customer_name, json.dumps(items), total_units,
             total_amount, payment_status, amount_paid, max(balance, 0),
             service_type, dropoff_date, collection_date,
             False, now_wat_str())
        )
        connection.commit()
        connection.close()

        return {
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
        }

    # ---------------- SEARCH ----------------

    def search_records(self, customer_name=None, invoice_number=None,
                        dropoff_date=None, payment_status=None):
        connection = get_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()

        query = "SELECT * FROM dropoff_records WHERE 1=1"
        params = []

        if customer_name:
            query += " AND LOWER(customer_name) LIKE LOWER(?)"
            params.append(f"%{customer_name}%")

        if invoice_number:
            query += " AND invoice_number = ?"
            params.append(invoice_number)

        if dropoff_date:
            query += " AND dropoff_date = ?"
            params.append(dropoff_date)

        if payment_status:
            query += " AND payment_status = ?"
            params.append(payment_status)

        query += " ORDER BY created_at DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        connection.close()

        results = []
        for row in rows:
            record = dict(row)
            record["items"] = json.loads(record["items"])
            results.append(record)

        return results

    def get_record_by_invoice(self, invoice_number):
        connection = get_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()

        cursor.execute(
            "SELECT * FROM dropoff_records WHERE invoice_number = ?",
            (invoice_number,)
        )
        row = cursor.fetchone()
        connection.close()

        if not row:
            return None

        record = dict(row)
        record["items"] = json.loads(record["items"])
        return record

    def get_all_records(self):
        """Returns all records, most recent first — used for CSV export."""
        return self.search_records()


record_service = RecordKeeperService()
