import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date
from models.medicine_repo import (
    get_all_medicines, get_medicine_by_id, add_medicine, update_medicine, delete_medicine,
    get_batches_for_medicine, add_batch, get_all_suppliers, get_or_create_supplier
)
from services.exporter import export_inventory_to_excel
import ui.theme as theme

class InventoryView(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.selected_med_id = None
        self._build_layout()
        self.refresh_table()

    def _build_layout(self):
        self.grid_rowconfigure(1, weight=3)
        self.grid_rowconfigure(3, weight=2)
        self.grid_columnconfigure(0, weight=1)

        # ---------------- TOP TOOLBAR ----------------
        toolbar = ctk.CTkFrame(self, corner_radius=10)
        toolbar.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        toolbar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(toolbar, text="📦 Inventory & Multi-Batch Management", font=theme.FONT_TITLE).grid(row=0, column=0, padx=15, pady=10, sticky="w")

        # Search box
        search_box = ctk.CTkFrame(toolbar, fg_color="transparent")
        search_box.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        search_box.grid_columnconfigure(0, weight=1)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.refresh_table())
        search_entry = ctk.CTkEntry(search_box, textvariable=self.search_var, placeholder_text="🔍 Filter by name, generic, company...", font=theme.FONT_BODY)
        search_entry.grid(row=0, column=0, padx=5, sticky="ew")

        # Action Buttons
        btn_box = ctk.CTkFrame(toolbar, fg_color="transparent")
        btn_box.grid(row=0, column=2, padx=10, pady=10, sticky="e")

        ctk.CTkButton(
            btn_box, text="+ New Medicine", 
            fg_color=theme.PRIMARY_COLOR, hover_color=theme.PRIMARY_HOVER,
            font=theme.FONT_BODY_BOLD, command=self.open_add_medicine_dialog
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btn_box, text="+ Add Batch (Stock In)", 
            fg_color=theme.ACCENT_COLOR, hover_color=theme.ACCENT_HOVER,
            font=theme.FONT_BODY_BOLD, command=self.open_add_batch_dialog
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btn_box, text="📊 Export Excel", 
            fg_color="#065F46", hover_color="#047857",
            font=theme.FONT_BODY_BOLD, command=self.export_excel
        ).pack(side="left", padx=4)

        # ---------------- MEDICINE TABLE (UPPER) ----------------
        med_frame = ctk.CTkFrame(self, corner_radius=10)
        med_frame.grid(row=1, column=0, padx=10, pady=(0, 5), sticky="nsew")
        med_frame.grid_rowconfigure(1, weight=1)
        med_frame.grid_columnconfigure(0, weight=1)

        med_header = ctk.CTkFrame(med_frame, fg_color="transparent")
        med_header.grid(row=0, column=0, padx=15, pady=(8, 4), sticky="ew")
        ctk.CTkLabel(med_header, text="Medicines Directory", font=theme.FONT_HEADING).pack(side="left")
        ctk.CTkLabel(med_header, text="(Click on a medicine to inspect its batches & purchase stores below)", font=theme.FONT_SMALL, text_color="gray60").pack(side="left", padx=10)

        cols = ("name", "generic", "company", "category", "shelf", "stock", "min_alert")
        self.med_tree = ttk.Treeview(med_frame, columns=cols, show="headings", selectmode="browse")
        self.med_tree.heading("name", text="Brand Name")
        self.med_tree.heading("generic", text="Generic Formula")
        self.med_tree.heading("company", text="Manufacturer")
        self.med_tree.heading("category", text="Category")
        self.med_tree.heading("shelf", text="Shelf Location")
        self.med_tree.heading("stock", text="In-Stock Units")
        self.med_tree.heading("min_alert", text="Low Stock Limit")

        self.med_tree.column("name", width=160, anchor="w")
        self.med_tree.column("generic", width=200, anchor="w")
        self.med_tree.column("company", width=140, anchor="w")
        self.med_tree.column("category", width=90, anchor="center")
        self.med_tree.column("shelf", width=95, anchor="center")
        self.med_tree.column("stock", width=95, anchor="center")
        self.med_tree.column("min_alert", width=90, anchor="center")

        med_scroll = ttk.Scrollbar(med_frame, orient="vertical", command=self.med_tree.yview)
        self.med_tree.configure(yscrollcommand=med_scroll.set)

        self.med_tree.grid(row=1, column=0, padx=(10, 0), pady=(0, 10), sticky="nsew")
        med_scroll.grid(row=1, column=1, padx=(0, 10), pady=(0, 10), sticky="ns")

        self.med_tree.bind("<<TreeviewSelect>>", self.on_medicine_row_selected)

        # ---------------- BATCH DETAILS TABLE (LOWER) ----------------
        batch_frame = ctk.CTkFrame(self, corner_radius=10)
        batch_frame.grid(row=3, column=0, padx=10, pady=(5, 10), sticky="nsew")
        batch_frame.grid_rowconfigure(1, weight=1)
        batch_frame.grid_columnconfigure(0, weight=1)

        self.batch_header_lbl = ctk.CTkLabel(batch_frame, text="Purchased Batches & Sources for Selected Medicine", font=theme.FONT_HEADING)
        self.batch_header_lbl.grid(row=0, column=0, padx=15, pady=(8, 4), sticky="w")

        b_cols = ("batch_no", "supplier", "purchase_date", "expiry_date", "cost_price", "mrp", "current_stock", "status")
        self.batch_tree = ttk.Treeview(batch_frame, columns=b_cols, show="headings", selectmode="browse")
        self.batch_tree.heading("batch_no", text="Batch #")
        self.batch_tree.heading("supplier", text="Purchased From (Store / Source)")
        self.batch_tree.heading("purchase_date", text="Purchase Date")
        self.batch_tree.heading("expiry_date", text="Expiry Date")
        self.batch_tree.heading("cost_price", text="Purchase Cost ($)")
        self.batch_tree.heading("mrp", text="Retail Price ($)")
        self.batch_tree.heading("current_stock", text="Remaining Stock")
        self.batch_tree.heading("status", text="Status")

        self.batch_tree.column("batch_no", width=100, anchor="center")
        self.batch_tree.column("supplier", width=180, anchor="w")
        self.batch_tree.column("purchase_date", width=95, anchor="center")
        self.batch_tree.column("expiry_date", width=95, anchor="center")
        self.batch_tree.column("cost_price", width=110, anchor="e")
        self.batch_tree.column("mrp", width=95, anchor="e")
        self.batch_tree.column("current_stock", width=105, anchor="center")
        self.batch_tree.column("status", width=95, anchor="center")

        batch_scroll = ttk.Scrollbar(batch_frame, orient="vertical", command=self.batch_tree.yview)
        self.batch_tree.configure(yscrollcommand=batch_scroll.set)

        self.batch_tree.grid(row=1, column=0, padx=(10, 0), pady=(0, 10), sticky="nsew")
        batch_scroll.grid(row=1, column=1, padx=(0, 10), pady=(0, 10), sticky="ns")

    def refresh_table(self):
        for r in self.med_tree.get_children():
            self.med_tree.delete(r)

        self.med_list = get_all_medicines(self.search_var.get())
        for m in self.med_list:
            self.med_tree.insert("", "end", iid=str(m["id"]), values=(
                m["name"],
                m["generic_name"],
                m["company"],
                m["category"],
                m["shelf_location"] or "Unassigned",
                m["total_valid_stock"],
                m["min_stock_alert"]
            ))

        # Clear batch table
        for r in self.batch_tree.get_children():
            self.batch_tree.delete(r)
        self.batch_header_lbl.configure(text="Purchased Batches & Sources for Selected Medicine")

    def on_medicine_row_selected(self, event):
        selected = self.med_tree.selection()
        if not selected:
            return
        med_id = int(selected[0])
        self.selected_med_id = med_id
        med = get_medicine_by_id(med_id)

        self.batch_header_lbl.configure(text=f"Purchased Batches for: '{med['name']}' ({med['company']})")

        for r in self.batch_tree.get_children():
            self.batch_tree.delete(r)

        batches = get_batches_for_medicine(med_id)
        for b in batches:
            self.batch_tree.insert("", "end", values=(
                b["batch_number"],
                b["supplier_name"],
                b["purchase_date"],
                b["expiry_date"],
                f"${b['purchase_price']:.2f}",
                f"${b['selling_price']:.2f}",
                b["current_qty"],
                b["expiry_status"]
            ))

    def open_add_medicine_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Add New Medicine Master")
        dialog.geometry("450x480")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Add New Medicine", font=theme.FONT_TITLE).pack(pady=(15, 10))

        form = ctk.CTkFrame(dialog, fg_color="transparent")
        form.pack(fill="x", padx=25, pady=5)
        form.grid_columnconfigure(1, weight=1)

        fields = [
            ("Brand Name *:", "e.g. Napa Extra"),
            ("Generic Name *:", "e.g. Paracetamol + Caffeine"),
            ("Manufacturer *:", "e.g. Beximco Pharma"),
            ("Category:", "Tablet"),
            ("Shelf Location:", "e.g. Rack A-1"),
            ("Low Stock Alert:", "10")
        ]

        entries = {}
        for idx, (label_txt, placeholder) in enumerate(fields):
            ctk.CTkLabel(form, text=label_txt, font=theme.FONT_BODY_BOLD).grid(row=idx, column=0, padx=5, pady=6, sticky="w")
            ent = ctk.CTkEntry(form, font=theme.FONT_BODY)
            ent.grid(row=idx, column=1, padx=5, pady=6, sticky="ew")
            if label_txt == "Category:":
                ent.insert(0, "Tablet")
            elif label_txt == "Low Stock Alert:":
                ent.insert(0, "10")
            else:
                ent.configure(placeholder_text=placeholder)
            entries[label_txt] = ent

        def save_med():
            name = entries["Brand Name *:"].get().strip()
            generic = entries["Generic Name *:"].get().strip()
            comp = entries["Manufacturer *:"].get().strip()
            cat = entries["Category:"].get().strip() or "Tablet"
            shelf = entries["Shelf Location:"].get().strip()
            alert_str = entries["Low Stock Alert:"].get().strip() or "10"

            if not name or not generic or not comp:
                messagebox.showerror("Error", "Brand name, Generic name, and Manufacturer are required.")
                return

            try:
                alert = int(alert_str)
            except ValueError:
                alert = 10

            new_id, err = add_medicine(name, generic, comp, cat, shelf, alert)
            if err:
                messagebox.showerror("Error", err)
                return

            messagebox.showinfo("Success", f"Medicine '{name}' created successfully!")
            dialog.destroy()
            self.refresh_table()

        btn_box = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_box.pack(fill="x", padx=25, pady=15)
        ctk.CTkButton(btn_box, text="Save Medicine", fg_color=theme.PRIMARY_COLOR, command=save_med).pack(side="right", padx=5)
        ctk.CTkButton(btn_box, text="Cancel", fg_color="gray50", command=dialog.destroy).pack(side="right", padx=5)

    def open_add_batch_dialog(self):
        meds = get_all_medicines()
        if not meds:
            messagebox.showwarning("Warning", "Please add at least one medicine first.")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Stock In: Add New Purchase Batch")
        dialog.geometry("520x560")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Add Purchase Batch (Multi-Source & Price)", font=theme.FONT_TITLE).pack(pady=(15, 10))

        form = ctk.CTkFrame(dialog, fg_color="transparent")
        form.pack(fill="x", padx=25, pady=5)
        form.grid_columnconfigure(1, weight=1)

        # Medicine Selector
        ctk.CTkLabel(form, text="Medicine *:", font=theme.FONT_BODY_BOLD).grid(row=0, column=0, padx=5, pady=6, sticky="w")
        med_options = [f"{m['name']} ({m['company']})" for m in meds]
        med_var = tk.StringVar(value=med_options[0])
        med_combo = ctk.CTkComboBox(form, values=med_options, variable=med_var)
        med_combo.grid(row=0, column=1, padx=5, pady=6, sticky="ew")

        # If user had a medicine selected in main table, auto-select it
        if self.selected_med_id:
            for m in meds:
                if m["id"] == self.selected_med_id:
                    med_var.set(f"{m['name']} ({m['company']})")
                    break

        # Batch Number
        ctk.CTkLabel(form, text="Batch Code *:", font=theme.FONT_BODY_BOLD).grid(row=1, column=0, padx=5, pady=6, sticky="w")
        batch_entry = ctk.CTkEntry(form, placeholder_text="e.g. LOT-2026-X1")
        batch_entry.grid(row=1, column=1, padx=5, pady=6, sticky="ew")

        # Supplier / Store Source
        ctk.CTkLabel(form, text="Store / Source *:", font=theme.FONT_BODY_BOLD).grid(row=2, column=0, padx=5, pady=6, sticky="w")
        suppliers = get_all_suppliers()
        sup_names = [s["name"] for s in suppliers]
        sup_combo = ctk.CTkComboBox(form, values=sup_names)
        if sup_names: sup_combo.set(sup_names[0])
        sup_combo.grid(row=2, column=1, padx=5, pady=6, sticky="ew")

        # Purchase Price
        ctk.CTkLabel(form, text="Purchase Cost ($) *:", font=theme.FONT_BODY_BOLD).grid(row=3, column=0, padx=5, pady=6, sticky="w")
        cost_entry = ctk.CTkEntry(form, placeholder_text="e.g. 2.15")
        cost_entry.grid(row=3, column=1, padx=5, pady=6, sticky="ew")

        # Selling Price
        ctk.CTkLabel(form, text="Selling MRP ($) *:", font=theme.FONT_BODY_BOLD).grid(row=4, column=0, padx=5, pady=6, sticky="w")
        mrp_entry = ctk.CTkEntry(form, placeholder_text="e.g. 3.00")
        mrp_entry.grid(row=4, column=1, padx=5, pady=6, sticky="ew")

        # Expiry Date
        ctk.CTkLabel(form, text="Expiry Date *:", font=theme.FONT_BODY_BOLD).grid(row=5, column=0, padx=5, pady=6, sticky="w")
        exp_entry = ctk.CTkEntry(form, placeholder_text="YYYY-MM-DD (e.g. 2027-12-31)")
        exp_entry.grid(row=5, column=1, padx=5, pady=6, sticky="ew")

        # Quantity
        ctk.CTkLabel(form, text="Quantity Received *:", font=theme.FONT_BODY_BOLD).grid(row=6, column=0, padx=5, pady=6, sticky="w")
        qty_entry = ctk.CTkEntry(form, placeholder_text="e.g. 100")
        qty_entry.grid(row=6, column=1, padx=5, pady=6, sticky="ew")

        def save_batch():
            # Validate medicine
            sel_med_text = med_var.get()
            selected_med = next((m for m in meds if f"{m['name']} ({m['company']})" == sel_med_text), None)
            if not selected_med:
                messagebox.showerror("Error", "Please select a valid medicine.")
                return

            batch_code = batch_entry.get().strip()
            sup_name = sup_combo.get().strip()
            cost_str = cost_entry.get().strip()
            mrp_str = mrp_entry.get().strip()
            exp_str = exp_entry.get().strip()
            qty_str = qty_entry.get().strip()

            if not batch_code or not sup_name or not cost_str or not mrp_str or not exp_str or not qty_str:
                messagebox.showerror("Error", "All fields are required to log a batch.")
                return

            try:
                cost = float(cost_str)
                mrp = float(mrp_str)
                qty = int(qty_str)
                if cost < 0 or mrp < 0 or qty <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Error", "Please enter valid numeric values for prices and quantity.")
                return

            # Validate date format YYYY-MM-DD
            try:
                date.fromisoformat(exp_str)
            except ValueError:
                messagebox.showerror("Error", "Expiry Date must be in YYYY-MM-DD format (e.g. 2027-12-31).")
                return

            sup_id = get_or_create_supplier(sup_name)
            batch_id, err = add_batch(selected_med["id"], sup_id, batch_code, cost, mrp, exp_str, qty)
            if err:
                messagebox.showerror("Error", err)
                return

            messagebox.showinfo("Success", f"Batch '{batch_code}' added successfully!")
            dialog.destroy()
            self.refresh_table()

        btn_box = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_box.pack(fill="x", padx=25, pady=15)
        ctk.CTkButton(btn_box, text="Save Batch", fg_color=theme.ACCENT_COLOR, command=save_batch).pack(side="right", padx=5)
        ctk.CTkButton(btn_box, text="Cancel", fg_color="gray50", command=dialog.destroy).pack(side="right", padx=5)

    def export_excel(self):
        try:
            path = export_inventory_to_excel()
            messagebox.showinfo("Export Successful", f"Full inventory exported to:\n{path}")
        except Exception as e:
            messagebox.showerror("Export Failed", str(e))
