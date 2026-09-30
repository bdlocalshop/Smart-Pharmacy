import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
from models.reports_repo import get_expiry_alerts, get_low_stock_alerts
from services.exporter import export_expiry_to_excel
import ui.theme as theme

class AlertsView(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._build_layout()
        self.refresh_alerts()

    def _build_layout(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ---------------- TOP HEADER & KPI CARDS ----------------
        header_card = ctk.CTkFrame(self, corner_radius=10)
        header_card.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        header_card.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(header_card, text="⚠️ Expiry & Stock Radar", font=theme.FONT_TITLE).grid(row=0, column=0, columnspan=4, padx=15, pady=(10, 5), sticky="w")

        # KPI 1: Expired Items
        self.expired_card = ctk.CTkFrame(header_card, fg_color=("gray92", "#450A0A"), corner_radius=8)
        self.expired_card.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        ctk.CTkLabel(self.expired_card, text="🔴 Expired Batches", font=theme.FONT_HEADING, text_color=theme.DANGER_COLOR).pack(padx=15, pady=(8, 2))
        self.expired_val_lbl = ctk.CTkLabel(self.expired_card, text="0 batches ($0.00)", font=theme.FONT_SUBTITLE, text_color=theme.DANGER_COLOR)
        self.expired_val_lbl.pack(padx=15, pady=(0, 8))

        # KPI 2: Expiring < 30 Days
        self.crit_card = ctk.CTkFrame(header_card, fg_color=("gray92", "#451A03"), corner_radius=8)
        self.crit_card.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkLabel(self.crit_card, text="🟡 Expiring < 30 Days", font=theme.FONT_HEADING, text_color=theme.WARNING_COLOR).pack(padx=15, pady=(8, 2))
        self.crit_val_lbl = ctk.CTkLabel(self.crit_card, text="0 batches ($0.00)", font=theme.FONT_SUBTITLE, text_color=theme.WARNING_COLOR)
        self.crit_val_lbl.pack(padx=15, pady=(0, 8))

        # KPI 3: Low Stock
        self.low_stock_card = ctk.CTkFrame(header_card, fg_color=("gray92", "#1E293B"), corner_radius=8)
        self.low_stock_card.grid(row=1, column=2, padx=10, pady=10, sticky="ew")
        ctk.CTkLabel(self.low_stock_card, text="📉 Low Stock Medicines", font=theme.FONT_HEADING, text_color=theme.PRIMARY_COLOR).pack(padx=15, pady=(8, 2))
        self.low_stock_val_lbl = ctk.CTkLabel(self.low_stock_card, text="0 items below limit", font=theme.FONT_SUBTITLE, text_color=theme.PRIMARY_COLOR)
        self.low_stock_val_lbl.pack(padx=15, pady=(0, 8))

        # Action export button
        ctk.CTkButton(
            header_card, text="📥 Export Expiry for Supplier Return",
            fg_color=theme.DANGER_COLOR, hover_color="#991B1B",
            font=theme.FONT_BODY_BOLD, command=self.export_expiry_excel
        ).grid(row=1, column=3, padx=15, pady=10, sticky="e")

        # ---------------- TABVIEW: EXPIRY vs LOW STOCK ----------------
        self.tabs = ctk.CTkTabview(self, corner_radius=10)
        self.tabs.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")

        self.tab_expiry = self.tabs.add("  📅 Medicine Expiry Radar  ")
        self.tab_low_stock = self.tabs.add("  📉 Low Stock Warnings  ")

        self._build_expiry_tab()
        self._build_low_stock_tab()

    def _build_expiry_tab(self):
        self.tab_expiry.grid_rowconfigure(1, weight=1)
        self.tab_expiry.grid_columnconfigure(0, weight=1)

        # Filter bar
        filter_bar = ctk.CTkFrame(self.tab_expiry, fg_color="transparent")
        filter_bar.grid(row=0, column=0, padx=5, pady=(5, 8), sticky="ew")

        ctk.CTkLabel(filter_bar, text="Filter by Urgency:", font=theme.FONT_BODY_BOLD).pack(side="left", padx=5)
        self.urgency_filter_var = tk.StringVar(value="All Urgent (<= 90 Days)")
        self.urgency_menu = ctk.CTkOptionMenu(
            filter_bar, variable=self.urgency_filter_var,
            values=["All Urgent (<= 90 Days)", "🔴 Already Expired", "🟡 Expiring in < 30 Days", "Expiring in < 60 Days", "Expiring in < 90 Days"],
            command=lambda val: self.filter_expiry_table()
        )
        self.urgency_menu.pack(side="left", padx=5)

        ctk.CTkButton(filter_bar, text="🔄 Refresh Radar", fg_color="gray40", width=110, command=self.refresh_alerts).pack(side="right", padx=5)

        # Expiry Treeview
        exp_cols = ("status", "days", "name", "shelf", "batch", "supplier", "expiry", "qty", "cost", "value")
        self.exp_tree = ttk.Treeview(self.tab_expiry, columns=exp_cols, show="headings", selectmode="browse")
        self.exp_tree.heading("status", text="Alert Level")
        self.exp_tree.heading("days", text="Days Remaining")
        self.exp_tree.heading("name", text="Medicine Name")
        self.exp_tree.heading("shelf", text="Shelf Location")
        self.exp_tree.heading("batch", text="Batch #")
        self.exp_tree.heading("supplier", text="Purchased From (Store / Source)")
        self.exp_tree.heading("expiry", text="Expiry Date")
        self.exp_tree.heading("qty", text="Units Left")
        self.exp_tree.heading("cost", text="Cost/Unit ($)")
        self.exp_tree.heading("value", text="Cost Locked ($)")

        self.exp_tree.column("status", width=120, anchor="center")
        self.exp_tree.column("days", width=105, anchor="center")
        self.exp_tree.column("name", width=160, anchor="w")
        self.exp_tree.column("shelf", width=95, anchor="center")
        self.exp_tree.column("batch", width=95, anchor="center")
        self.exp_tree.column("supplier", width=160, anchor="w")
        self.exp_tree.column("expiry", width=95, anchor="center")
        self.exp_tree.column("qty", width=75, anchor="center")
        self.exp_tree.column("cost", width=85, anchor="e")
        self.exp_tree.column("value", width=100, anchor="e")

        exp_scroll = ttk.Scrollbar(self.tab_expiry, orient="vertical", command=self.exp_tree.yview)
        self.exp_tree.configure(yscrollcommand=exp_scroll.set)

        self.exp_tree.grid(row=1, column=0, padx=(5, 0), pady=(0, 5), sticky="nsew")
        exp_scroll.grid(row=1, column=1, padx=(0, 5), pady=(0, 5), sticky="ns")

    def _build_low_stock_tab(self):
        self.tab_low_stock.grid_rowconfigure(0, weight=1)
        self.tab_low_stock.grid_columnconfigure(0, weight=1)

        low_cols = ("name", "generic", "company", "category", "shelf", "stock", "min_limit", "deficit")
        self.low_tree = ttk.Treeview(self.tab_low_stock, columns=low_cols, show="headings", selectmode="browse")
        self.low_tree.heading("name", text="Medicine Name")
        self.low_tree.heading("generic", text="Generic Formula")
        self.low_tree.heading("company", text="Manufacturer")
        self.low_tree.heading("category", text="Category")
        self.low_tree.heading("shelf", text="Shelf Location")
        self.low_tree.heading("stock", text="Current Stock")
        self.low_tree.heading("min_limit", text="Reorder Threshold")
        self.low_tree.heading("deficit", text="Shortage")

        self.low_tree.column("name", width=160, anchor="w")
        self.low_tree.column("generic", width=190, anchor="w")
        self.low_tree.column("company", width=140, anchor="w")
        self.low_tree.column("category", width=90, anchor="center")
        self.low_tree.column("shelf", width=95, anchor="center")
        self.low_tree.column("stock", width=95, anchor="center")
        self.low_tree.column("min_limit", width=110, anchor="center")
        self.low_tree.column("deficit", width=90, anchor="center")

        low_scroll = ttk.Scrollbar(self.tab_low_stock, orient="vertical", command=self.low_tree.yview)
        self.low_tree.configure(yscrollcommand=low_scroll.set)

        self.low_tree.grid(row=0, column=0, padx=(5, 0), pady=5, sticky="nsew")
        low_scroll.grid(row=0, column=1, padx=(0, 5), pady=5, sticky="ns")

    def refresh_alerts(self):
        self.raw_expiry_alerts = get_expiry_alerts()
        self.raw_low_stock = get_low_stock_alerts()

        # Update KPI cards
        expired_count = sum(1 for a in self.raw_expiry_alerts if a["alert_level"] == "Expired")
        expired_val = sum(a["cost_value"] for a in self.raw_expiry_alerts if a["alert_level"] == "Expired")
        self.expired_val_lbl.configure(text=f"{expired_count} batches (${expired_val:.2f})")

        crit_count = sum(1 for a in self.raw_expiry_alerts if a["alert_level"] == "Critical (<30 Days)")
        crit_val = sum(a["cost_value"] for a in self.raw_expiry_alerts if a["alert_level"] == "Critical (<30 Days)")
        self.crit_val_lbl.configure(text=f"{crit_count} batches (${crit_val:.2f})")

        self.low_stock_val_lbl.configure(text=f"{len(self.raw_low_stock)} medicines below threshold")

        self.filter_expiry_table()

        # Populate low stock tree
        for r in self.low_tree.get_children():
            self.low_tree.delete(r)

        for l in self.raw_low_stock:
            deficit = max(0, l["min_stock_alert"] - l["valid_stock"])
            self.low_tree.insert("", "end", values=(
                l["name"],
                l["generic_name"],
                l["company"],
                l["category"],
                l["shelf_location"] or "Unassigned",
                l["valid_stock"],
                l["min_stock_alert"],
                f"-{deficit} units"
            ))

    def filter_expiry_table(self):
        for r in self.exp_tree.get_children():
            self.exp_tree.delete(r)

        filter_choice = self.urgency_filter_var.get()
        for a in self.raw_expiry_alerts:
            # Apply filter
            if "Expired" in filter_choice and a["alert_level"] != "Expired":
                continue
            if "< 30" in filter_choice and a["alert_level"] != "Critical (<30 Days)":
                continue
            if "< 60" in filter_choice and a["alert_level"] not in ("Critical (<30 Days)", "Warning (<60 Days)"):
                continue

            days_str = f"{a['days_remaining']} days" if a['days_remaining'] >= 0 else f"Expired {abs(a['days_remaining'])}d ago"
            self.exp_tree.insert("", "end", values=(
                a["alert_level"],
                days_str,
                a["medicine_name"],
                a["shelf_location"] or "Unassigned",
                a["batch_number"],
                a["supplier_name"],
                a["expiry_date"],
                a["current_qty"],
                f"${a['purchase_price']:.2f}",
                f"${a['cost_value']:.2f}"
            ))

    def export_expiry_excel(self):
        try:
            path = export_expiry_to_excel()
            messagebox.showinfo("Export Successful", f"Expiry radar report exported for supplier returns:\n{path}")
        except Exception as e:
            messagebox.showerror("Export Failed", str(e))
