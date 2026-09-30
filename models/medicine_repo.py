import sqlite3
from database.db import get_connection

def get_all_medicines(search=""):
    """
    Retrieves all medicines with their aggregate stock, minimum stock alert,
    and shelf location. Supports search by brand or generic name.
    """
    conn = get_connection()
    cursor = conn.cursor()
    search_pattern = f"%{search.strip()}%" if search else "%"
    
    query = """
        SELECT 
            m.id,
            m.name,
            m.generic_name,
            m.company,
            m.category,
            m.shelf_location,
            m.min_stock_alert,
            COALESCE(SUM(CASE WHEN b.expiry_date >= DATE('now') THEN b.current_qty ELSE 0 END), 0) as total_valid_stock,
            COALESCE(SUM(CASE WHEN b.expiry_date < DATE('now') THEN b.current_qty ELSE 0 END), 0) as total_expired_stock,
            COUNT(b.id) as batch_count
        FROM medicines m
        LEFT JOIN batches b ON m.id = b.medicine_id
        WHERE m.name LIKE ? OR m.generic_name LIKE ? OR m.company LIKE ?
        GROUP BY m.id
        ORDER BY m.name ASC;
    """
    cursor.execute(query, (search_pattern, search_pattern, search_pattern))
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results

def get_medicine_by_id(med_id):
    """Fetches single medicine record."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM medicines WHERE id = ?", (med_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def add_medicine(name, generic_name, company, category="Tablet", shelf_location="", min_stock_alert=10):
    """Creates a new medicine master record."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO medicines (name, generic_name, company, category, shelf_location, min_stock_alert)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name.strip(), generic_name.strip(), company.strip(), category.strip(), shelf_location.strip(), int(min_stock_alert)))
        conn.commit()
        new_id = cursor.lastrowid
        return new_id, None
    except sqlite3.IntegrityError:
        return None, f"Medicine '{name}' by '{company}' already exists."
    except Exception as e:
        return None, str(e)
    finally:
        conn.close()

def update_medicine(med_id, name, generic_name, company, category, shelf_location, min_stock_alert):
    """Updates medicine master record."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE medicines
            SET name = ?, generic_name = ?, company = ?, category = ?, shelf_location = ?, min_stock_alert = ?
            WHERE id = ?
        """, (name.strip(), generic_name.strip(), company.strip(), category.strip(), shelf_location.strip(), int(min_stock_alert), med_id))
        conn.commit()
        return True, None
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def delete_medicine(med_id):
    """Deletes medicine and its associated batches."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM medicines WHERE id = ?", (med_id,))
        conn.commit()
        return True, None
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def get_batches_for_medicine(med_id):
    """Retrieves all batches for a specific medicine, including supplier name."""
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT 
            b.*,
            COALESCE(s.name, 'Unknown / Direct') as supplier_name,
            CASE 
                WHEN b.expiry_date < DATE('now') THEN 'Expired'
                WHEN b.expiry_date <= DATE('now', '+30 days') THEN 'Expiring Soon'
                ELSE 'Valid'
            END as expiry_status
        FROM batches b
        LEFT JOIN suppliers s ON b.supplier_id = s.id
        WHERE b.medicine_id = ?
        ORDER BY b.expiry_date ASC;
    """
    cursor.execute(query, (med_id,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def add_batch(medicine_id, supplier_id, batch_number, purchase_price, selling_price, expiry_date, quantity, notes=""):
    """
    Adds a new batch for a medicine.
    Supports varying purchase cost, selling price, and source supplier.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO batches (medicine_id, supplier_id, batch_number, purchase_price, selling_price,
                                 expiry_date, initial_qty, current_qty, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (medicine_id, supplier_id, batch_number.strip(), float(purchase_price), float(selling_price),
              expiry_date, int(quantity), int(quantity), notes.strip()))
        conn.commit()
        return cursor.lastrowid, None
    except Exception as e:
        return None, str(e)
    finally:
        conn.close()

def get_active_batches_fefo(medicine_id):
    """
    Gets batches with positive stock, ordered by expiry date (First-Expired, First-Out).
    Skips already expired batches to protect patient safety.
    """
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT 
            b.id,
            b.batch_number,
            b.current_qty,
            b.selling_price,
            b.purchase_price,
            b.expiry_date,
            COALESCE(s.name, 'N/A') as supplier_name
        FROM batches b
        LEFT JOIN suppliers s ON b.supplier_id = s.id
        WHERE b.medicine_id = ? AND b.current_qty > 0 AND b.expiry_date >= DATE('now')
        ORDER BY b.expiry_date ASC, b.id ASC;
    """
    cursor.execute(query, (medicine_id,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_all_suppliers():
    """Fetches all suppliers."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM suppliers ORDER BY name ASC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_or_create_supplier(name, phone="", address=""):
    """Finds existing supplier or creates a new one."""
    conn = get_connection()
    cursor = conn.cursor()
    name = name.strip()
    cursor.execute("SELECT id FROM suppliers WHERE name = ?", (name,))
    row = cursor.fetchone()
    if row:
        supplier_id = row["id"]
    else:
        cursor.execute("INSERT INTO suppliers (name, phone, address) VALUES (?, ?, ?)", (name, phone, address))
        conn.commit()
        supplier_id = cursor.lastrowid
    conn.close()
    return supplier_id
