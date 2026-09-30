import sqlite3
from database.db import get_connection

def get_expiry_alerts():
    """
    Finds all non-zero stock batches that are either already expired
    or will expire within the next 90 days.
    """
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT 
            b.id as batch_id,
            b.batch_number,
            b.expiry_date,
            b.current_qty,
            b.purchase_price,
            b.selling_price,
            (b.current_qty * b.purchase_price) as cost_value,
            m.id as medicine_id,
            m.name as medicine_name,
            m.generic_name,
            m.company,
            m.shelf_location,
            COALESCE(s.name, 'N/A') as supplier_name,
            CASE 
                WHEN b.expiry_date < DATE('now') THEN 'Expired'
                WHEN b.expiry_date <= DATE('now', '+30 days') THEN 'Critical (<30 Days)'
                WHEN b.expiry_date <= DATE('now', '+60 days') THEN 'Warning (<60 Days)'
                ELSE 'Notice (<90 Days)'
            END as alert_level,
            CAST(JULIANDAY(b.expiry_date) - JULIANDAY('now') AS INTEGER) as days_remaining
        FROM batches b
        JOIN medicines m ON b.medicine_id = m.id
        LEFT JOIN suppliers s ON b.supplier_id = s.id
        WHERE b.current_qty > 0 AND b.expiry_date <= DATE('now', '+90 days')
        ORDER BY b.expiry_date ASC;
    """
    cursor.execute(query)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_low_stock_alerts():
    """
    Finds medicines where total valid (non-expired) stock is less than or equal
    to the configured min_stock_alert threshold.
    """
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT 
            m.id,
            m.name,
            m.generic_name,
            m.company,
            m.category,
            m.shelf_location,
            m.min_stock_alert,
            COALESCE(SUM(CASE WHEN b.expiry_date >= DATE('now') THEN b.current_qty ELSE 0 END), 0) as valid_stock
        FROM medicines m
        LEFT JOIN batches b ON m.id = b.medicine_id
        GROUP BY m.id
        HAVING valid_stock <= m.min_stock_alert
        ORDER BY valid_stock ASC;
    """
    cursor.execute(query)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_inventory_valuation():
    """Returns overall summary metrics of the pharmacy inventory."""
    conn = get_connection()
    cursor = conn.cursor()

    # Total distinct medicines
    cursor.execute("SELECT COUNT(*) FROM medicines;")
    total_medicines = cursor.fetchone()[0]

    # Batch totals
    cursor.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN expiry_date >= DATE('now') THEN current_qty ELSE 0 END), 0) as valid_units,
            COALESCE(SUM(CASE WHEN expiry_date < DATE('now') THEN current_qty ELSE 0 END), 0) as expired_units,
            COALESCE(SUM(CASE WHEN expiry_date >= DATE('now') THEN current_qty * purchase_price ELSE 0 END), 0) as total_cost_value,
            COALESCE(SUM(CASE WHEN expiry_date >= DATE('now') THEN current_qty * selling_price ELSE 0 END), 0) as total_retail_value
        FROM batches;
    """)
    totals = dict(cursor.fetchone())
    conn.close()

    totals["total_medicines"] = total_medicines
    totals["potential_profit"] = totals["total_retail_value"] - totals["total_cost_value"]
    return totals
