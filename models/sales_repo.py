import sqlite3
from datetime import datetime, date
from database.db import get_connection

def generate_invoice_number():
    """Generates unique invoice number like INV-20260930-001."""
    conn = get_connection()
    cursor = conn.cursor()
    today_str = datetime.now().strftime("%Y%m%d")
    prefix = f"INV-{today_str}-"
    cursor.execute("SELECT COUNT(*) FROM sales WHERE invoice_no LIKE ?", (f"{prefix}%",))
    count = cursor.fetchone()[0] + 1
    conn.close()
    return f"{prefix}{count:04d}"

def checkout_sale(cart_items, customer_name="Walk-in Customer", customer_phone="", discount=0.0, payment_method="Cash", notes=""):
    """
    Executes atomic checkout transaction.
    cart_items: list of dicts:
       [
         {"medicine_id": int, "batch_id": int, "quantity": int, "unit_price": float, "unit_cost": float}
       ]
    """
    if not cart_items:
        return False, "Cart is empty.", None

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Calculate subtotal
        subtotal = sum(item["quantity"] * item["unit_price"] for item in cart_items)
        discount = float(discount) if discount else 0.0
        grand_total = max(0.0, subtotal - discount)
        invoice_no = generate_invoice_number()

        # Begin transaction
        conn.execute("BEGIN TRANSACTION;")

        # Insert Sale
        cursor.execute("""
            INSERT INTO sales (invoice_no, customer_name, customer_phone, subtotal, discount, grand_total, payment_method, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (invoice_no, customer_name.strip() or "Walk-in Customer", customer_phone.strip(),
              subtotal, discount, grand_total, payment_method, notes))
        sale_id = cursor.lastrowid

        # Insert Sale Items & Deduct Stock from respective Batches
        for item in cart_items:
            batch_id = item["batch_id"]
            qty_to_sell = item["quantity"]
            unit_price = item["unit_price"]
            unit_cost = item.get("unit_cost", 0.0)
            total_price = qty_to_sell * unit_price
            medicine_id = item["medicine_id"]

            # Verify batch has enough stock and is not expired
            cursor.execute("""
                SELECT current_qty, expiry_date FROM batches WHERE id = ?
            """, (batch_id,))
            batch_row = cursor.fetchone()
            if not batch_row:
                raise ValueError(f"Batch ID {batch_id} not found.")

            current_qty = batch_row["current_qty"]
            expiry_date = batch_row["expiry_date"]

            if expiry_date < date.today().isoformat():
                raise ValueError(f"Batch {batch_id} has expired ({expiry_date}) and cannot be sold.")

            if current_qty < qty_to_sell:
                raise ValueError(f"Insufficient stock for batch {batch_id}. Requested: {qty_to_sell}, Available: {current_qty}.")

            # Deduct stock
            cursor.execute("""
                UPDATE batches
                SET current_qty = current_qty - ?
                WHERE id = ? AND current_qty >= ?
            """, (qty_to_sell, batch_id, qty_to_sell))

            # Insert line item
            cursor.execute("""
                INSERT INTO sale_items (sale_id, batch_id, medicine_id, quantity, unit_price, total_price, unit_cost)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (sale_id, batch_id, medicine_id, qty_to_sell, unit_price, total_price, unit_cost))

        conn.commit()
        return True, "Sale completed successfully.", invoice_no
    except Exception as e:
        conn.rollback()
        return False, str(e), None
    finally:
        conn.close()

def get_daily_sales_summary(target_date=None):
    """
    Retrieves daily volume: total sales count, total items sold, gross revenue,
    and estimated profit for the given date (default today).
    """
    if not target_date:
        target_date = date.today().isoformat()

    conn = get_connection()
    cursor = conn.cursor()

    # Query daily aggregates
    cursor.execute("""
        SELECT 
            COUNT(DISTINCT s.id) as total_invoices,
            COALESCE(SUM(s.grand_total), 0) as total_revenue,
            COALESCE(SUM(s.discount), 0) as total_discount,
            COALESCE(SUM(si.quantity), 0) as total_items_sold,
            COALESCE(SUM(si.quantity * (si.unit_price - si.unit_cost)), 0) - COALESCE(SUM(DISTINCT s.discount), 0) as estimated_gross_profit
        FROM sales s
        LEFT JOIN sale_items si ON s.id = si.sale_id
        WHERE DATE(s.sale_date) = DATE(?);
    """, (target_date,))
    summary = dict(cursor.fetchone())

    # Payment breakdown
    cursor.execute("""
        SELECT payment_method, COUNT(*) as count, SUM(grand_total) as amount
        FROM sales
        WHERE DATE(sale_date) = DATE(?)
        GROUP BY payment_method;
    """, (target_date,))
    payment_breakdown = [dict(row) for row in cursor.fetchall()]

    conn.close()
    summary["payment_breakdown"] = payment_breakdown
    return summary

def get_sales_history(start_date=None, end_date=None, search=None, limit=200):
    """Retrieves list of past sales/invoices."""
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT 
            s.id,
            s.invoice_no,
            s.sale_date,
            s.customer_name,
            s.customer_phone,
            s.subtotal,
            s.discount,
            s.grand_total,
            s.payment_method,
            COUNT(si.id) as item_count,
            COALESCE(SUM(si.quantity * (si.unit_price - si.unit_cost)), 0) - s.discount as estimated_profit
        FROM sales s
        LEFT JOIN sale_items si ON s.id = si.sale_id
        WHERE 1=1
    """
    params = []
    if start_date:
        query += " AND DATE(s.sale_date) >= DATE(?)"
        params.append(start_date)
    if end_date:
        query += " AND DATE(s.sale_date) <= DATE(?)"
        params.append(end_date)
    if search:
        query += " AND (s.invoice_no LIKE ? OR s.customer_name LIKE ? OR s.customer_phone LIKE ?)"
        pattern = f"%{search.strip()}%"
        params.extend([pattern, pattern, pattern])

    query += " GROUP BY s.id ORDER BY s.sale_date DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, tuple(params))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_sale_details(sale_id_or_invoice):
    """Fetches complete invoice with items for printing or viewing."""
    conn = get_connection()
    cursor = conn.cursor()

    if isinstance(sale_id_or_invoice, int):
        cursor.execute("SELECT * FROM sales WHERE id = ?", (sale_id_or_invoice,))
    else:
        cursor.execute("SELECT * FROM sales WHERE invoice_no = ?", (sale_id_or_invoice,))
    sale = cursor.fetchone()
    if not sale:
        conn.close()
        return None

    sale_dict = dict(sale)
    cursor.execute("""
        SELECT 
            si.*,
            m.name as medicine_name,
            m.generic_name,
            m.category,
            b.batch_number,
            b.expiry_date
        FROM sale_items si
        JOIN medicines m ON si.medicine_id = m.id
        JOIN batches b ON si.batch_id = b.id
        WHERE si.sale_id = ?;
    """, (sale_dict["id"],))
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    sale_dict["items"] = items
    return sale_dict
