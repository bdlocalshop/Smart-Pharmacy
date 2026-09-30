import sqlite3
import os
from datetime import datetime, date

DB_FILENAME = "smart_pharmacy.db"

def get_db_path():
    """Returns absolute path to SQLite database."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, DB_FILENAME)

def get_connection():
    """Establishes connection to SQLite with WAL mode and foreign keys enabled."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def init_db():
    """Initializes tables, indices, and default seed data if needed."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Suppliers / Stores (Where medicine was purchased from)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            phone TEXT,
            address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 2. Medicine Master (Brand name, generic, company, shelf location)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            generic_name TEXT NOT NULL,
            company TEXT NOT NULL,
            category TEXT DEFAULT 'Tablet',
            shelf_location TEXT,
            min_stock_alert INTEGER DEFAULT 10,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(name, company)
        );
    """)

    # 3. Batches (Multi-source, varying purchase/selling prices, expiry dates)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_id INTEGER NOT NULL,
            supplier_id INTEGER,
            batch_number TEXT NOT NULL,
            purchase_price REAL NOT NULL,
            selling_price REAL NOT NULL,
            expiry_date DATE NOT NULL,
            purchase_date DATE DEFAULT (DATE('now')),
            initial_qty INTEGER NOT NULL,
            current_qty INTEGER NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL
        );
    """)

    # 4. Sales / Invoices
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT NOT NULL UNIQUE,
            sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            customer_name TEXT DEFAULT 'Walk-in Customer',
            customer_phone TEXT,
            subtotal REAL NOT NULL,
            discount REAL DEFAULT 0,
            grand_total REAL NOT NULL,
            payment_method TEXT DEFAULT 'Cash',
            notes TEXT
        );
    """)

    # 5. Sale Items (Deducted from specific batch)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            batch_id INTEGER NOT NULL,
            medicine_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            total_price REAL NOT NULL,
            unit_cost REAL NOT NULL,
            FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
            FOREIGN KEY (batch_id) REFERENCES batches(id) ON DELETE RESTRICT,
            FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE RESTRICT
        );
    """)

    # Indices for blazing fast search & POS lookup
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_med_name ON medicines(name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_med_generic ON medicines(generic_name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_batches_med ON batches(medicine_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_batches_expiry ON batches(expiry_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(sale_date);")

    conn.commit()

    # Check if empty, populate initial starter sample dataset
    cursor.execute("SELECT COUNT(*) FROM medicines;")
    if cursor.fetchone()[0] == 0:
        _seed_starter_data(cursor)
        conn.commit()

    conn.close()

def _seed_starter_data(cursor):
    """Seeds typical pharmacy items and multi-batch purchases for quick testing."""
    # Seed Suppliers
    suppliers = [
        ("Central Pharma Distributors", "+8801711000001", "Dhaka Depot"),
        ("Square Pharma Agency", "+8801811000002", "Chittagong Hub"),
        ("Beximco Logistics", "+8801911000003", "Tejgaon Industrial Area"),
        ("Meditech Wholesale Store", "+8801611000004", "Local Wholesale Market")
    ]
    cursor.executemany("INSERT INTO suppliers (name, phone, address) VALUES (?, ?, ?)", suppliers)
    
    # Seed Medicines
    meds = [
        ("Napa Extra", "Paracetamol 500mg + Caffeine 65mg", "Beximco Pharma", "Tablet", "Rack A-1", 30),
        ("Ace Plus", "Paracetamol 500mg + Caffeine 65mg", "Square Pharmaceuticals", "Tablet", "Rack A-2", 30),
        ("Seclo 20", "Omeprazole 20mg", "Square Pharmaceuticals", "Capsule", "Rack B-1", 20),
        ("Sergel 20", "Esomeprazole 20mg", "Healthcare Pharmaceuticals", "Capsule", "Rack B-2", 20),
        ("Moxacil 500", "Amoxicillin 500mg", "Square Pharmaceuticals", "Capsule", "Rack C-1", 15),
        ("Tofen 100ml", "Ketotifen 1mg/5ml", "Beximco Pharma", "Syrup", "Shelf S-3", 10),
        ("Almex 400", "Albendazole 400mg", "Square Pharmaceuticals", "Chewable Tablet", "Rack D-1", 10),
        ("Fexo 120", "Fexofenadine 120mg", "Square Pharmaceuticals", "Tablet", "Rack E-2", 25)
    ]
    for med in meds:
        cursor.execute("""
            INSERT INTO medicines (name, generic_name, company, category, shelf_location, min_stock_alert)
            VALUES (?, ?, ?, ?, ?, ?)
        """, med)

    # Fetch IDs
    cursor.execute("SELECT id, name FROM medicines")
    med_map = {row["name"]: row["id"] for row in cursor.fetchall()}
    cursor.execute("SELECT id, name FROM suppliers")
    sup_map = {row["name"]: row["id"] for row in cursor.fetchall()}

    # Multi-batch examples demonstrating varying prices and different suppliers for Napa Extra:
    # Napa Extra Batch 1: from Central Pharma, bought at 2.10, sells at 3.00, expires in 25 days (Near Expiry demo!)
    # Napa Extra Batch 2: from Beximco Logistics, bought at 2.25, sells at 3.00, expires in 1.5 years
    today = date.today()
    from datetime import timedelta

    batches = [
        # Napa Extra: Batch 1 (Near expiry alert demo)
        (med_map["Napa Extra"], sup_map["Central Pharma Distributors"], "BEX-NX-01", 2.10, 3.00,
         (today + timedelta(days=20)).isoformat(), (today - timedelta(days=60)).isoformat(), 100, 25, "Older stock"),
        # Napa Extra: Batch 2 (Fresh stock, different purchase price from different source)
        (med_map["Napa Extra"], sup_map["Beximco Logistics"], "BEX-NX-02", 2.25, 3.00,
         (today + timedelta(days=500)).isoformat(), today.isoformat(), 200, 180, "Fresh batch"),
        
        # Ace Plus
        (med_map["Ace Plus"], sup_map["Square Pharma Agency"], "SQ-AP-101", 2.20, 3.00,
         (today + timedelta(days=400)).isoformat(), today.isoformat(), 150, 120, "Standard lot"),
        
        # Seclo 20
        (med_map["Seclo 20"], sup_map["Square Pharma Agency"], "SQ-SEC-99", 5.20, 7.00,
         (today + timedelta(days=360)).isoformat(), today.isoformat(), 80, 65, ""),
        
        # Sergel 20 (Low stock demo: only 8 remaining when alert threshold is 20)
        (med_map["Sergel 20"], sup_map["Meditech Wholesale Store"], "HCP-SER-12", 6.80, 9.00,
         (today + timedelta(days=250)).isoformat(), today.isoformat(), 50, 8, "Low stock demo"),

        # Moxacil 500 (Expired demo: expired 5 days ago to test expiry alert filter!)
        (med_map["Moxacil 500"], sup_map["Square Pharma Agency"], "SQ-MOX-08", 7.50, 11.00,
         (today - timedelta(days=5)).isoformat(), (today - timedelta(days=365)).isoformat(), 50, 15, "Expired stock"),

        # Tofen Syrup
        (med_map["Tofen 100ml"], sup_map["Central Pharma Distributors"], "BEX-TOF-03", 45.00, 60.00,
         (today + timedelta(days=300)).isoformat(), today.isoformat(), 30, 22, ""),

        # Fexo 120
        (med_map["Fexo 120"], sup_map["Square Pharma Agency"], "SQ-FEX-77", 7.00, 9.50,
         (today + timedelta(days=420)).isoformat(), today.isoformat(), 100, 90, "")
    ]

    cursor.executemany("""
        INSERT INTO batches (medicine_id, supplier_id, batch_number, purchase_price, selling_price,
                             expiry_date, purchase_date, initial_qty, current_qty, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, batches)
