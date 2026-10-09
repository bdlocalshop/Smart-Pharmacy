# 💊 Smart Pharmacy - Desktop POS & Inventory Management System

A high-performance, offline-first Windows desktop application built specifically for retail pharmacies, medicine shops, and dispensaries.

---

## 🌟 Key Capabilities

### 1. Multi-Source & Multi-Price Batch Management
- **Varying Purchase Prices & Suppliers**: Buy the same medicine (e.g. *Napa Extra* or *Amoxicillin*) from different distributors or local stores over time at varying purchase costs. The application tracks every batch separately.
- **Master vs. Batch**: Medicine master details (Brand Name, Generic Formula, Manufacturer, Category, Shelf/Rack Location) are decoupled from purchase batches (Batch #, Purchase Cost, Selling MRP, Expiry Date, Supplier Store, Remaining Units).

### 2. Point of Sale (POS) & Billing
- **Real-Time Stock Display**: As soon as a salesman selects or types a medicine, the application displays remaining stock across all non-expired batches along with its physical shelf location (e.g. `Rack A-1`).
- **Smart FEFO Allocation**: Recommends and selects the batch closest to expiry date (**First Expired, First Out**) so older stock is sold before newer stock.
- **Rapid Cart & Checkout**: Full keyboard shortcuts, discount calculation, cash tendered with instant change calculation.
- **Thermal Receipt Generator**: Generates 80mm standard printable receipt slips with invoice number, itemized batch numbers, and expiry dates.

### 3. Expiry Radar & Stock Alerts
- **Expiry Radar**: Color-coded urgency tracking:
  - 🔴 **Expired Stock**: Batches whose expiry date has passed. Blocked from selling to protect patients; flagged for return to pharmaceutical representatives.
  - 🟡 **Expiring in < 30 Days**: Critical alert for priority sale or supplier return.
  - **Expiring in < 60 & < 90 Days**: Early warning notifications.
- **Low Stock Warnings**: Automatically flags any medicine where total valid stock falls below the configured reorder threshold.

### 4. Sales Volume & Performance Reports
- **Dynamic Period Filtering & Custom Date Range**: Switch seamlessly between **Today**, **Yesterday**, **This Week**, **This Month**, and **Custom Date**. Selecting **Custom Date** opens an interactive dialog to pick any specific date range (with quick presets like *Last 7 Days*, *Last 30 Days*, *This Year*). All four KPI metric counters (*Total Invoices*, *Units Sold*, *Gross Revenue*, and *Estimated Profit*) automatically recalculate on the fly for the selected period.
- **Real Profit Calculation**: Accurately computes gross profit based on the actual purchase cost of each deducted batch:
  $$\text{Profit} = (\text{Selling Price} - \text{Batch Purchase Cost}) \times \text{Quantity} - \text{Discount}$$
- **Dual Sales Report Export**: Clicking **"Export Sales Report"** simultaneously generates:
  1. A formatted **Excel spreadsheet (`.xlsx`)** with complete transaction records.
  2. A clean, executive **Text audit report (`.txt`)** with period date ranges, KPIs, payment method breakdown, top-selling medicines, and transaction logs.
- **Invoice Archive**: Search past bills by invoice number, customer name, or phone number, and re-print receipts at any time.

### 5. Data Storage, Maintenance & Backup Center
- **Zero-Setup Local SQLite Engine (`smart_pharmacy.db`)**: Self-contained, zero-configuration database running locally with Write-Ahead Logging (WAL) for speed and crash resistance.
- **Automated Rolling Backups**: Automatically creates a timestamped backup in the `backups/` directory on application startup, safely pruning snapshots older than 14 days.
- **One-Click USB / External Export**: Allows the pharmacy owner to backup the live database directly to a USB flash drive or cloud-synced folder (Google Drive, OneDrive).
- **One-Click Database Restore**: Easily recover data from any previous snapshot or migration file with safety backups taken before replacement.
- **Excel, Text & CSV Export Center**: Export Inventory reports, Sales history, Text audit reports, and Expiry lists with one click.

---

## 🚀 How to Run the Application

### Option A: Double-Click Launcher (Easiest)
Simply double-click the **`run_app.bat`** file located in this directory.

### Option B: From Terminal / PowerShell
```powershell
# Navigate to the workspace directory
cd d:\anti_gravity_workspace\Smart-Pharmacy

# Run using Python 3.12
python main.py
```

---

## 📂 Project Structure

```
Smart-Pharmacy/
├── main.py                     # Main application entry point
├── run_app.bat                 # Easy Windows desktop launcher
├── smart_pharmacy.db           # Live SQLite database file (created automatically)
├── database/
│   ├── db.py                   # Schema definition, WAL mode, starter seed data
│   └── backup_manager.py       # Auto daily backups, USB export, safe restore
├── models/
│   ├── medicine_repo.py        # Medicine master, multi-batch, FEFO queries
│   ├── sales_repo.py           # Atomic checkout, stock deduction, invoices
│   └── reports_repo.py         # Expiry radar, low stock, inventory valuation
├── services/
│   └── exporter.py             # Excel generation, thermal receipt text
├── ui/
│   ├── theme.py                # Styling, colors (Teal/Emerald/Navy), fonts
│   ├── app_window.py           # Main window shell & sidebar navigation
│   ├── pos_view.py             # Fast billing & POS checkout view
│   ├── inventory_view.py       # Medicine and batch management view
│   ├── alerts_view.py          # Expiry radar & low stock view
│   ├── reports_view.py         # Daily volume & sales history view
│   └── backup_view.py          # Backup, restore & data extraction view
├── backups/                    # Auto-generated daily backup snapshots
├── exports/                    # Generated Excel & CSV reports
└── test_pharmacy.py            # Comprehensive unit test suite
```

---

## 🧪 Running Automated Tests
```powershell
python test_pharmacy.py
```
All core workflows (multi-batch pricing, atomic stock deductions, FEFO ordering, alerts, exports, and backups) are verified by automated tests.
