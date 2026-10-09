"""
Verification & Test Suite for Smart Pharmacy
Tests database models, multi-batch logic, FEFO stock deduction, alerts, and backup/restore.
"""

import os
import unittest
from datetime import date, timedelta
from database.db import init_db, get_connection
from database.backup_manager import create_automated_backup, create_manual_backup, list_existing_backups
from models.medicine_repo import (
    get_all_medicines, get_medicine_by_id, add_medicine,
    get_batches_for_medicine, add_batch, get_active_batches_fefo,
    get_or_create_supplier
)
from models.sales_repo import (
    checkout_sale, get_daily_sales_summary, get_sales_summary, get_top_selling_medicines, get_sales_history, get_sale_details
)
from models.reports_repo import (
    get_expiry_alerts, get_low_stock_alerts, get_inventory_valuation
)
from services.exporter import (
    export_inventory_to_excel, export_sales_to_excel, export_expiry_to_excel, generate_thermal_receipt_text,
    generate_sales_text_report, export_sales_reports
)

class TestSmartPharmacy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_01_medicines_and_multi_batches(self):
        # Verify starter medicines exist
        meds = get_all_medicines()
        self.assertGreater(len(meds), 0, "Medicines should be populated.")
        
        # Verify Napa Extra has multiple batches with different sources and prices
        napa = next((m for m in meds if m["name"] == "Napa Extra"), None)
        self.assertIsNotNone(napa, "Napa Extra should exist.")
        self.assertGreaterEqual(napa["batch_count"], 2, "Napa Extra should have multiple batches.")

        batches = get_batches_for_medicine(napa["id"])
        self.assertGreaterEqual(len(batches), 2)
        # Verify batches have varying purchase prices
        prices = [b["purchase_price"] for b in batches]
        self.assertNotEqual(prices[0], prices[1], "Batches should demonstrate varying purchase prices.")

    def test_02_fefo_allocation(self):
        # Fetch Napa Extra batches ordered by FEFO
        meds = get_all_medicines()
        napa = next(m for m in meds if m["name"] == "Napa Extra")
        fefo_batches = get_active_batches_fefo(napa["id"])
        
        self.assertGreater(len(fefo_batches), 0)
        # Verify earliest expiry date comes first
        if len(fefo_batches) > 1:
            self.assertLessEqual(fefo_batches[0]["expiry_date"], fefo_batches[1]["expiry_date"])

    def test_03_sales_checkout_and_stock_deduction(self):
        # Add a fresh test medicine and batch to test exact deduction
        import time
        unique_name = f"Test-Amox-{int(time.time()*1000)}"
        sup_id = get_or_create_supplier("Test Supplier Direct")
        med_id, err = add_medicine(unique_name, "Amoxicillin", "Test Labs", "Capsule", "Shelf T-1", 5)
        self.assertIsNotNone(med_id, f"Failed to add test medicine: {err}")
        
        today = date.today()
        exp_date = (today + timedelta(days=200)).isoformat()
        batch_id, b_err = add_batch(med_id, sup_id, f"TB-{int(time.time())}", 10.0, 15.0, exp_date, 50)
        self.assertIsNotNone(batch_id, f"Failed to add test batch: {b_err}")

        # Checkout 5 units
        cart = [{
            "medicine_id": med_id,
            "batch_id": batch_id,
            "quantity": 5,
            "unit_price": 15.0,
            "unit_cost": 10.0
        }]
        
        success, msg, inv_no = checkout_sale(
            cart_items=cart,
            customer_name="John Doe",
            customer_phone="01700000000",
            discount=5.0,
            payment_method="Cash"
        )
        self.assertTrue(success, msg)
        self.assertTrue(inv_no.startswith("INV-"))

        # Verify stock was deducted: 50 - 5 = 45
        batches = get_batches_for_medicine(med_id)
        test_batch = next(b for b in batches if b["id"] == batch_id)
        self.assertEqual(test_batch["current_qty"], 45)

        # Verify invoice details & receipt generator
        details = get_sale_details(inv_no)
        self.assertEqual(details["grand_total"], 70.0) # (5 * 15) - 5 = 70
        receipt = generate_thermal_receipt_text(details)
        self.assertIn("John Doe", receipt)
        self.assertIn("GRAND TOTAL:", receipt)

    def test_04_alerts_and_expiry_radar(self):
        expiry_alerts = get_expiry_alerts()
        self.assertIsInstance(expiry_alerts, list)
        
        # Verify expired items are detected (e.g. Moxacil demo batch)
        has_expired = any(a["alert_level"] == "Expired" for a in expiry_alerts)
        self.assertTrue(has_expired, "Should identify expired batches.")

        low_stock = get_low_stock_alerts()
        self.assertIsInstance(low_stock, list)

    def test_05_daily_sales_summary(self):
        # Test today's summary
        today_str = date.today().isoformat()
        today_summary = get_sales_summary(start_date=today_str, end_date=today_str)
        self.assertIn("total_invoices", today_summary)
        self.assertIn("total_revenue", today_summary)
        self.assertIn("estimated_gross_profit", today_summary)
        self.assertIn("total_items_sold", today_summary)

        # Test all-time summary
        all_summary = get_sales_summary(start_date=None, end_date=None)
        self.assertGreaterEqual(all_summary["total_invoices"], today_summary["total_invoices"])

        # Test top selling medicines
        top_meds = get_top_selling_medicines(limit=5)
        self.assertIsInstance(top_meds, list)

    def test_06_exports(self):
        inv_path = export_inventory_to_excel()
        self.assertTrue(os.path.exists(inv_path))

        exp_path = export_expiry_to_excel()
        self.assertTrue(os.path.exists(exp_path))

        # Test Dual Sales Reports Export (Excel + Text report)
        excel_path, txt_path = export_sales_reports(period_label="Today")
        self.assertTrue(os.path.exists(excel_path), "Excel report must be created.")
        self.assertTrue(os.path.exists(txt_path), "Text report must be created.")

        # Verify Text Report contents
        with open(txt_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("SMART PHARMACY MANAGEMENT SYSTEM", content)
        self.assertIn("Report Period", content)
        self.assertIn("Total Invoices Issued", content)
        self.assertIn("Total Units Sold", content)
        self.assertIn("Gross Sales", content)
        self.assertIn("Estimated Gross Profit", content)
        self.assertIn("PAYMENT METHOD BREAKDOWN", content)

    def test_07_backup_manager(self):
        auto_path = create_automated_backup()
        self.assertIsNotNone(auto_path)
        self.assertTrue(os.path.exists(auto_path))

        backups = list_existing_backups()
        self.assertGreater(len(backups), 0)

if __name__ == "__main__":
    unittest.main()
