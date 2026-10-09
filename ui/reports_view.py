import os
import subprocess
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, timedelta
from models.sales_repo import get_sales_summary, get_sales_history, get_sale_details
from services.exporter import export_sales_reports, generate_thermal_receipt_text, get_exports_dir
import ui.theme as theme

class ReportsView(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._build_layout()
        self.load_daily_volume()

    def _build_layout(self):
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ---------------- TOP TOOLBAR & DATE FILTER ----------------
        toolbar = ctk.CTkFrame(self, corner_radius=10)
        toolbar.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        toolbar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(toolbar, text="📊 Sales Volume & Performance Reports", font=theme.FONT_TITLE).grid(row=0, column=0, padx=15, pady=10, sticky="w")

        # Date Selector
        date_box = ctk.CTkFrame(toolbar, fg_color="transparent")
        date_box.grid(row=0, column=1, padx=10, pady=10, sticky="e")

        ctk.CTkLabel(date_box, text="Period:", font=theme.FONT_BODY_BOLD).pack(side="left", padx=5)
        self.period_var = tk.StringVar(value="Today")
        self.period_menu = ctk.CTkOptionMenu(
            date_box, variable=self.period_var,
            values=["Today", "Yesterday", "This Week", "This Month", "All Time"],
            command=self.on_period_change
        )
        self.period_menu.pack(side="left", padx=5)

        ctk.CTkButton(
            date_box, text="📥 Export Sales Report",
            fg_color="#065F46", hover_color="#047857",
            font=theme.FONT_BODY_BOLD, command=self.export_sales_report
        ).pack(side="left", padx=5)

        # ---------------- KPI CARDS BANNER ----------------
        kpi_frame = ctk.CTkFrame(self, corner_radius=10)
        kpi_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        for i in range(4):
            kpi_frame.grid_columnconfigure(i, weight=1)

        # KPI 1: Invoices
        c1 = ctk.CTkFrame(kpi_frame, fg_color=("gray92", "gray22"), corner_radius=8)
        c1.grid(row=0, column=0, padx=8, pady=10, sticky="ew")
        ctk.CTkLabel(c1, text="Total Invoices", font=theme.FONT_SMALL, text_color="gray60").pack(pady=(6, 0))
        self.kpi_invoices_lbl = ctk.CTkLabel(c1, text="0", font=theme.FONT_KPI_VAL, text_color=theme.PRIMARY_COLOR)
        self.kpi_invoices_lbl.pack(pady=(0, 6))

        # KPI 2: Items Sold
        c2 = ctk.CTkFrame(kpi_frame, fg_color=("gray92", "gray22"), corner_radius=8)
        c2.grid(row=0, column=1, padx=8, pady=10, sticky="ew")
        ctk.CTkLabel(c2, text="Units Sold", font=theme.FONT_SMALL, text_color="gray60").pack(pady=(6, 0))
        self.kpi_units_lbl = ctk.CTkLabel(c2, text="0", font=theme.FONT_KPI_VAL, text_color=theme.ACCENT_COLOR)
        self.kpi_units_lbl.pack(pady=(0, 6))

        # KPI 3: Revenue
        c3 = ctk.CTkFrame(kpi_frame, fg_color=("gray92", "gray22"), corner_radius=8)
        c3.grid(row=0, column=2, padx=8, pady=10, sticky="ew")
        ctk.CTkLabel(c3, text="Gross Revenue", font=theme.FONT_SMALL, text_color="gray60").pack(pady=(6, 0))
        self.kpi_rev_lbl = ctk.CTkLabel(c3, text="$0.00", font=theme.FONT_KPI_VAL, text_color=theme.SUCCESS_COLOR)
        self.kpi_rev_lbl.pack(pady=(0, 6))

        # KPI 4: Estimated Profit
        c4 = ctk.CTkFrame(kpi_frame, fg_color=("gray92", "gray22"), corner_radius=8)
        c4.grid(row=0, column=3, padx=8, pady=10, sticky="ew")
        ctk.CTkLabel(c4, text="Estimated Profit", font=theme.FONT_SMALL, text_color="gray60").pack(pady=(6, 0))
        self.kpi_profit_lbl = ctk.CTkLabel(c4, text="$0.00", font=theme.FONT_KPI_VAL, text_color="#10B981")
        self.kpi_profit_lbl.pack(pady=(0, 6))

        # ---------------- TRANSACTIONS TABLE ----------------
        table_frame = ctk.CTkFrame(self, corner_radius=10)
        table_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")
        table_frame.grid_rowconfigure(1, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Search bar
        t_header = ctk.CTkFrame(table_frame, fg_color="transparent")
        t_header.grid(row=0, column=0, padx=15, pady=8, sticky="ew")
        t_header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(t_header, text="Past Sales & Bills", font=theme.FONT_HEADING).grid(row=0, column=0, sticky="w")
        
        self.tx_search_var = tk.StringVar()
        self.tx_search_var.trace_add("write", lambda *args: self.load_sales_table())
        tx_search_ent = ctk.CTkEntry(t_header, textvariable=self.tx_search_var, placeholder_text="🔍 Search Invoice No, Patient Name or Phone...", width=280)
        tx_search_ent.grid(row=0, column=1, padx=15, sticky="w")

        ctk.CTkButton(t_header, text="🧾 Re-print Selected Receipt", font=theme.FONT_SMALL, command=self.view_selected_receipt).grid(row=0, column=2, sticky="e")

        # Treeview
        cols = ("invoice", "date", "customer", "phone", "items", "subtotal", "discount", "total", "payment", "profit")
        self.sales_tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        self.sales_tree.heading("invoice", text="Invoice #")
        self.sales_tree.heading("date", text="Date & Time")
        self.sales_tree.heading("customer", text="Patient Name")
        self.sales_tree.heading("phone", text="Phone")
        self.sales_tree.heading("items", text="Items")
        self.sales_tree.heading("subtotal", text="Subtotal ($)")
        self.sales_tree.heading("discount", text="Discount ($)")
        self.sales_tree.heading("total", text="Total Paid ($)")
        self.sales_tree.heading("payment", text="Payment")
        self.sales_tree.heading("profit", text="Profit ($)")

        self.sales_tree.column("invoice", width=120, anchor="center")
        self.sales_tree.column("date", width=135, anchor="center")
        self.sales_tree.column("customer", width=140, anchor="w")
        self.sales_tree.column("phone", width=110, anchor="center")
        self.sales_tree.column("items", width=60, anchor="center")
        self.sales_tree.column("subtotal", width=85, anchor="e")
        self.sales_tree.column("discount", width=80, anchor="e")
        self.sales_tree.column("total", width=95, anchor="e")
        self.sales_tree.column("payment", width=90, anchor="center")
        self.sales_tree.column("profit", width=85, anchor="e")

        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.sales_tree.yview)
        self.sales_tree.configure(yscrollcommand=scroll.set)

        self.sales_tree.grid(row=1, column=0, padx=(10, 0), pady=(0, 10), sticky="nsew")
        scroll.grid(row=1, column=1, padx=(0, 10), pady=(0, 10), sticky="ns")

    def on_period_change(self, choice):
        self.load_daily_volume()

    def get_selected_dates(self):
        choice = self.period_var.get()
        today = date.today()
        if choice == "Today":
            return today.isoformat(), today.isoformat()
        elif choice == "Yesterday":
            yest = (today - timedelta(days=1)).isoformat()
            return yest, yest
        elif choice == "This Week":
            start_week = (today - timedelta(days=today.weekday())).isoformat()
            return start_week, today.isoformat()
        elif choice == "This Month":
            start_month = today.replace(day=1).isoformat()
            return start_month, today.isoformat()
        else:  # All Time
            return None, None

    def load_daily_volume(self):
        start_date, end_date = self.get_selected_dates()
        
        # Summary metrics dynamically calculated for the selected period
        summary = get_sales_summary(start_date=start_date, end_date=end_date)

        self.kpi_invoices_lbl.configure(text=str(summary["total_invoices"]))
        self.kpi_units_lbl.configure(text=str(summary["total_items_sold"]))
        self.kpi_rev_lbl.configure(text=f"${summary['total_revenue']:.2f}")
        self.kpi_profit_lbl.configure(text=f"${summary['estimated_gross_profit']:.2f}")

        self.load_sales_table()

    def load_sales_table(self):
        for r in self.sales_tree.get_children():
            self.sales_tree.delete(r)

        start_date, end_date = self.get_selected_dates()
        search = self.tx_search_var.get()
        sales = get_sales_history(start_date=start_date, end_date=end_date, search=search)

        for s in sales:
            self.sales_tree.insert("", "end", iid=s["invoice_no"], values=(
                s["invoice_no"],
                s["sale_date"],
                s["customer_name"],
                s["customer_phone"] or "-",
                s["item_count"],
                f"${s['subtotal']:.2f}",
                f"${s['discount']:.2f}",
                f"${s['grand_total']:.2f}",
                s["payment_method"],
                f"${s['estimated_profit']:.2f}"
            ))

    def view_selected_receipt(self):
        selected = self.sales_tree.selection()
        if not selected:
            messagebox.showinfo("Select Invoice", "Please click on an invoice row in the table first.")
            return

        inv_no = selected[0]
        sale_details = get_sale_details(inv_no)
        if not sale_details:
            messagebox.showerror("Error", "Invoice details not found.")
            return

        receipt_text = generate_thermal_receipt_text(sale_details)

        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Receipt - {inv_no}")
        dialog.geometry("460x580")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        ctk.CTkLabel(dialog, text=f"Invoice: {inv_no}", font=theme.FONT_SUBTITLE).pack(pady=10)

        txt_box = ctk.CTkTextbox(dialog, font=("Consolas", 11), wrap="none")
        txt_box.pack(fill="both", expand=True, padx=15, pady=5)
        txt_box.insert("1.0", receipt_text)
        txt_box.configure(state="disabled")

        btn_box = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_box.pack(fill="x", padx=15, pady=10)

        def copy_to_clipboard():
            dialog.clipboard_clear()
            dialog.clipboard_append(receipt_text)
            messagebox.showinfo("Copied", "Receipt text copied to clipboard.")

        ctk.CTkButton(btn_box, text="📋 Copy Text", command=copy_to_clipboard, width=100).pack(side="left", padx=5)
        ctk.CTkButton(btn_box, text="Close", fg_color="gray50", command=dialog.destroy, width=90).pack(side="right", padx=5)

    def export_sales_report(self):
        start_date, end_date = self.get_selected_dates()
        period_label = self.period_var.get()
        try:
            excel_path, txt_path = export_sales_reports(
                start_date=start_date,
                end_date=end_date,
                period_label=period_label
            )
            self.show_export_success_dialog(period_label, excel_path, txt_path)
        except Exception as e:
            messagebox.showerror("Export Failed", str(e))

    def show_export_success_dialog(self, period_label, excel_path, txt_path):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Sales Reports Exported")
        dialog.geometry("580x370")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="✅ Sales Reports Generated Successfully!", font=theme.FONT_SUBTITLE, text_color=theme.SUCCESS_COLOR).pack(pady=(15, 6))
        ctk.CTkLabel(dialog, text=f"Period: {period_label}", font=theme.FONT_BODY_BOLD).pack(pady=(0, 10))

        content_frame = ctk.CTkFrame(dialog, fg_color=("gray92", "gray22"), corner_radius=8)
        content_frame.pack(fill="both", expand=True, padx=20, pady=5)

        # File 1: Excel
        f1_box = ctk.CTkFrame(content_frame, fg_color="transparent")
        f1_box.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(f1_box, text="📊 Excel Spreadsheet (.xlsx):", font=theme.FONT_BODY_BOLD).pack(anchor="w")
        ctk.CTkLabel(f1_box, text=os.path.basename(excel_path), font=theme.FONT_SMALL, text_color=theme.PRIMARY_COLOR).pack(anchor="w")

        # File 2: Text Report
        f2_box = ctk.CTkFrame(content_frame, fg_color="transparent")
        f2_box.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(f2_box, text="📄 Text Performance Audit Report (.txt):", font=theme.FONT_BODY_BOLD).pack(anchor="w")
        ctk.CTkLabel(f2_box, text=os.path.basename(txt_path), font=theme.FONT_SMALL, text_color=theme.PRIMARY_COLOR).pack(anchor="w")

        # Action Buttons
        btn_bar = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_bar.pack(fill="x", padx=20, pady=15)

        def open_txt():
            try:
                os.startfile(txt_path)
            except Exception:
                subprocess.Popen(["notepad.exe", txt_path])

        def open_excel():
            try:
                os.startfile(excel_path)
            except Exception:
                subprocess.Popen(["explorer", "/select,", excel_path])

        def open_folder():
            folder = get_exports_dir()
            try:
                os.startfile(folder)
            except Exception:
                subprocess.Popen(["explorer", folder])

        ctk.CTkButton(btn_bar, text="📄 View Text Report", fg_color=theme.PRIMARY_COLOR, command=open_txt, width=130).pack(side="left", padx=4)
        ctk.CTkButton(btn_bar, text="📊 Open Excel", fg_color="#065F46", hover_color="#047857", command=open_excel, width=105).pack(side="left", padx=4)
        ctk.CTkButton(btn_bar, text="📁 Open Folder", fg_color="gray40", command=open_folder, width=105).pack(side="left", padx=4)
        ctk.CTkButton(btn_bar, text="Close", fg_color="gray50", command=dialog.destroy, width=75).pack(side="right", padx=4)
