import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date
from models.medicine_repo import get_all_medicines, get_active_batches_fefo
from models.sales_repo import checkout_sale, get_sale_details
from services.exporter import generate_thermal_receipt_text
import ui.theme as theme

class POSView(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.cart = []  # list of {medicine_id, medicine_name, batch_id, batch_number, expiry_date, unit_price, unit_cost, quantity, total_price}
        self.active_batches = []
        self.selected_med = None

        self._build_layout()
        self.refresh_medicines_list()

    def _build_layout(self):
        # Two main columns: Left = Product Selection & Cart, Right = Invoice & Checkout
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        # ----------------- LEFT PANEL: SEARCH, ADD & CART -----------------
        left_panel = ctk.CTkFrame(self, corner_radius=10)
        left_panel.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="nsew")
        left_panel.grid_rowconfigure(2, weight=1)
        left_panel.grid_columnconfigure(0, weight=1)

        # Header & Search
        search_card = ctk.CTkFrame(left_panel, fg_color=("gray90", "gray20"), corner_radius=8)
        search_card.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        search_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(search_card, text="🔍 Search Medicine:", font=theme.FONT_BODY_BOLD).grid(row=0, column=0, padx=(10, 5), pady=10, sticky="w")
        
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.on_search_change())
        self.search_entry = ctk.CTkEntry(search_card, textvariable=self.search_var, placeholder_text="Type brand name (e.g. Napa) or generic (e.g. Paracetamol)...", font=theme.FONT_BODY)
        self.search_entry.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="ew")

        # Medicine & Batch Selection Card
        sel_card = ctk.CTkFrame(left_panel, fg_color=("gray92", "gray23"), corner_radius=8)
        sel_card.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        sel_card.grid_columnconfigure(1, weight=1)

        # Dropdown for matching medicines
        ctk.CTkLabel(sel_card, text="Select Medicine:", font=theme.FONT_BODY_BOLD).grid(row=0, column=0, padx=10, pady=(10, 4), sticky="w")
        self.med_combo_var = tk.StringVar()
        self.med_combo = ctk.CTkComboBox(sel_card, variable=self.med_combo_var, command=self.on_medicine_selected, font=theme.FONT_BODY, width=320)
        self.med_combo.grid(row=0, column=1, columnspan=2, padx=10, pady=(10, 4), sticky="ew")

        # Live Stock & Shelf Banner
        self.stock_info_lbl = ctk.CTkLabel(
            sel_card, 
            text="Please search and pick a medicine above to check stock.", 
            font=theme.FONT_BODY_BOLD,
            text_color=theme.PRIMARY_COLOR
        )
        self.stock_info_lbl.grid(row=1, column=0, columnspan=3, padx=10, pady=4, sticky="w")

        # Batch Selection & Qty
        ctk.CTkLabel(sel_card, text="Batch (FEFO):", font=theme.FONT_BODY_BOLD).grid(row=2, column=0, padx=10, pady=6, sticky="w")
        self.batch_combo_var = tk.StringVar()
        self.batch_combo = ctk.CTkComboBox(sel_card, variable=self.batch_combo_var, command=self.on_batch_selected, font=theme.FONT_BODY)
        self.batch_combo.grid(row=2, column=1, padx=10, pady=6, sticky="ew")

        # Qty and Add Button
        qty_box = ctk.CTkFrame(sel_card, fg_color="transparent")
        qty_box.grid(row=2, column=2, padx=10, pady=6, sticky="e")
        ctk.CTkLabel(qty_box, text="Qty:", font=theme.FONT_BODY_BOLD).pack(side="left", padx=5)
        self.qty_entry = ctk.CTkEntry(qty_box, width=65, font=theme.FONT_BODY)
        self.qty_entry.insert(0, "1")
        self.qty_entry.pack(side="left", padx=5)
        self.qty_entry.bind("<Return>", lambda event: self.add_to_cart())

        add_btn = ctk.CTkButton(qty_box, text="+ Add to Cart", fg_color=theme.PRIMARY_COLOR, hover_color=theme.PRIMARY_HOVER, font=theme.FONT_BODY_BOLD, command=self.add_to_cart)
        add_btn.pack(side="left", padx=5)

        # Cart Table
        cart_frame = ctk.CTkFrame(left_panel, corner_radius=8)
        cart_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")
        cart_frame.grid_rowconfigure(1, weight=1)
        cart_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(cart_frame, text="🛒 Items in Current Sale", font=theme.FONT_HEADING).grid(row=0, column=0, padx=10, pady=8, sticky="w")

        # Treeview for Cart
        columns = ("name", "batch", "expiry", "price", "qty", "total")
        self.cart_tree = ttk.Treeview(cart_frame, columns=columns, show="headings", height=8, selectmode="browse")
        self.cart_tree.heading("name", text="Medicine")
        self.cart_tree.heading("batch", text="Batch #")
        self.cart_tree.heading("expiry", text="Expiry")
        self.cart_tree.heading("price", text="Price")
        self.cart_tree.heading("qty", text="Qty")
        self.cart_tree.heading("total", text="Total")

        self.cart_tree.column("name", width=180, anchor="w")
        self.cart_tree.column("batch", width=90, anchor="center")
        self.cart_tree.column("expiry", width=85, anchor="center")
        self.cart_tree.column("price", width=70, anchor="e")
        self.cart_tree.column("qty", width=50, anchor="center")
        self.cart_tree.column("total", width=80, anchor="e")

        cart_scroll = ttk.Scrollbar(cart_frame, orient="vertical", command=self.cart_tree.yview)
        self.cart_tree.configure(yscrollcommand=cart_scroll.set)

        self.cart_tree.grid(row=1, column=0, padx=(10, 0), pady=(0, 10), sticky="nsew")
        cart_scroll.grid(row=1, column=1, padx=(0, 10), pady=(0, 10), sticky="ns")

        cart_act_bar = ctk.CTkFrame(cart_frame, fg_color="transparent")
        cart_act_bar.grid(row=2, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")
        
        remove_btn = ctk.CTkButton(cart_act_bar, text="Remove Selected Item", fg_color=theme.DANGER_COLOR, font=theme.FONT_SMALL, command=self.remove_from_cart)
        remove_btn.pack(side="left")

        clear_btn = ctk.CTkButton(cart_act_bar, text="Clear Cart", fg_color="gray50", font=theme.FONT_SMALL, command=self.clear_cart)
        clear_btn.pack(side="right")

        # ----------------- RIGHT PANEL: INVOICE & CHECKOUT -----------------
        right_panel = ctk.CTkFrame(self, corner_radius=10)
        right_panel.grid(row=0, column=1, padx=(5, 10), pady=10, sticky="nsew")
        right_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right_panel, text="💳 Checkout & Billing", font=theme.FONT_TITLE).pack(padx=15, pady=(15, 10), anchor="w")

        # Customer Info
        cust_frame = ctk.CTkFrame(right_panel, fg_color=("gray92", "gray23"), corner_radius=8)
        cust_frame.pack(fill="x", padx=15, pady=5)
        cust_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(cust_frame, text="Patient Name:", font=theme.FONT_BODY).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.cust_name_entry = ctk.CTkEntry(cust_frame, font=theme.FONT_BODY)
        self.cust_name_entry.insert(0, "Walk-in Customer")
        self.cust_name_entry.grid(row=0, column=1, padx=10, pady=5, sticky="ew")

        ctk.CTkLabel(cust_frame, text="Phone No:", font=theme.FONT_BODY).grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.cust_phone_entry = ctk.CTkEntry(cust_frame, font=theme.FONT_BODY, placeholder_text="Optional mobile number")
        self.cust_phone_entry.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        # Payment details
        bill_frame = ctk.CTkFrame(right_panel, fg_color=("gray90", "gray20"), corner_radius=8)
        bill_frame.pack(fill="x", padx=15, pady=10)
        bill_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(bill_frame, text="Subtotal:", font=theme.FONT_HEADING).grid(row=0, column=0, padx=10, pady=8, sticky="w")
        self.subtotal_lbl = ctk.CTkLabel(bill_frame, text="$0.00", font=theme.FONT_HEADING)
        self.subtotal_lbl.grid(row=0, column=1, padx=10, pady=8, sticky="e")

        ctk.CTkLabel(bill_frame, text="Discount ($):", font=theme.FONT_BODY).grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.discount_var = tk.StringVar(value="0")
        self.discount_var.trace_add("write", lambda *args: self.calculate_totals())
        self.discount_entry = ctk.CTkEntry(bill_frame, textvariable=self.discount_var, width=80, font=theme.FONT_BODY)
        self.discount_entry.grid(row=1, column=1, padx=10, pady=5, sticky="e")

        ctk.CTkLabel(bill_frame, text="GRAND TOTAL:", font=theme.FONT_TITLE, text_color=theme.SUCCESS_COLOR).grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.grand_total_lbl = ctk.CTkLabel(bill_frame, text="$0.00", font=theme.FONT_KPI_VAL, text_color=theme.SUCCESS_COLOR)
        self.grand_total_lbl.grid(row=2, column=1, padx=10, pady=10, sticky="e")

        # Payment method
        pm_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        pm_frame.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(pm_frame, text="Payment Method:", font=theme.FONT_BODY_BOLD).pack(side="left", padx=5)
        self.pay_method_var = tk.StringVar(value="Cash")
        self.pm_menu = ctk.CTkOptionMenu(pm_frame, variable=self.pay_method_var, values=["Cash", "Card", "Mobile Banking / bKash", "Other"])
        self.pm_menu.pack(side="right", padx=5)

        # Paid & Change calculator
        calc_frame = ctk.CTkFrame(right_panel, fg_color=("gray92", "gray23"), corner_radius=8)
        calc_frame.pack(fill="x", padx=15, pady=10)
        calc_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(calc_frame, text="Cash Tendered:", font=theme.FONT_BODY).grid(row=0, column=0, padx=10, pady=6, sticky="w")
        self.tendered_var = tk.StringVar()
        self.tendered_var.trace_add("write", lambda *args: self.calculate_change())
        self.tendered_entry = ctk.CTkEntry(calc_frame, textvariable=self.tendered_var, width=90, font=theme.FONT_BODY)
        self.tendered_entry.grid(row=0, column=1, padx=10, pady=6, sticky="e")

        ctk.CTkLabel(calc_frame, text="Change Due:", font=theme.FONT_HEADING).grid(row=1, column=0, padx=10, pady=6, sticky="w")
        self.change_lbl = ctk.CTkLabel(calc_frame, text="$0.00", font=theme.FONT_HEADING, text_color=theme.PRIMARY_COLOR)
        self.change_lbl.grid(row=1, column=1, padx=10, pady=6, sticky="e")

        # Checkout Button
        self.checkout_btn = ctk.CTkButton(
            right_panel, 
            text="✅ Complete Sale & Print Bill", 
            fg_color=theme.SUCCESS_COLOR, 
            hover_color="#15803D",
            font=theme.FONT_TITLE,
            height=48,
            command=self.execute_checkout
        )
        self.checkout_btn.pack(fill="x", padx=15, pady=(20, 15))

    def refresh_medicines_list(self):
        """Loads medicines into combobox based on search query."""
        search = self.search_var.get()
        self.med_records = get_all_medicines(search)
        
        options = []
        for m in self.med_records:
            stock = m["total_valid_stock"]
            options.append(f"{m['name']} ({m['company']}) - {m['generic_name']} [Stock: {stock}]")

        self.med_combo.configure(values=options)
        if options:
            self.med_combo.set(options[0])
            self.on_medicine_selected(options[0])
        else:
            self.med_combo.set("No medicines found")
            self.stock_info_lbl.configure(text="No matching medicine found in inventory.", text_color=theme.DANGER_COLOR)
            self.batch_combo.configure(values=[])
            self.batch_combo.set("")

    def on_search_change(self):
        self.refresh_medicines_list()

    def on_medicine_selected(self, choice):
        # Find selected medicine
        for m in self.med_records:
            match_str = f"{m['name']} ({m['company']}) - {m['generic_name']} [Stock: {m['total_valid_stock']}]"
            if match_str == choice or m["name"] in choice:
                self.selected_med = m
                break

        if not self.selected_med:
            return

        stock = self.selected_med["total_valid_stock"]
        shelf = self.selected_med["shelf_location"] or "Unassigned"
        color = theme.SUCCESS_COLOR if stock > 10 else (theme.WARNING_COLOR if stock > 0 else theme.DANGER_COLOR)
        
        self.stock_info_lbl.configure(
            text=f"📦 In Stock: {stock} units | 📍 Shelf Location: {shelf} | Generic: {self.selected_med['generic_name']}",
            text_color=color
        )

        # Load batches using FEFO (First Expired, First Out)
        self.active_batches = get_active_batches_fefo(self.selected_med["id"])
        batch_options = []
        for b in self.active_batches:
            batch_options.append(f"Batch {b['batch_number']} | Exp: {b['expiry_date']} | Price: ${b['selling_price']:.2f} | Left: {b['current_qty']}")

        self.batch_combo.configure(values=batch_options)
        if batch_options:
            self.batch_combo.set(batch_options[0])
        else:
            self.batch_combo.set("No valid non-expired batch")

    def on_batch_selected(self, choice):
        pass

    def add_to_cart(self):
        if not self.selected_med or not self.active_batches:
            messagebox.showwarning("Warning", "Please select a valid medicine and batch.")
            return

        # Find selected batch
        sel_batch_idx = self.batch_combo.cget("values").index(self.batch_combo.get()) if self.batch_combo.get() in self.batch_combo.cget("values") else 0
        if sel_batch_idx >= len(self.active_batches):
            messagebox.showwarning("Warning", "Invalid batch selected.")
            return

        batch = self.active_batches[sel_batch_idx]

        try:
            qty = int(self.qty_entry.get().strip())
            if qty <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid positive integer for quantity.")
            return

        # Check existing cart quantity for this batch
        cart_existing_qty = sum(item["quantity"] for item in self.cart if item["batch_id"] == batch["id"])
        if (cart_existing_qty + qty) > batch["current_qty"]:
            messagebox.showerror(
                "Insufficient Stock",
                f"Cannot add {qty} units.\nAvailable in Batch '{batch['batch_number']}': {batch['current_qty']}\nAlready in cart: {cart_existing_qty}"
            )
            return

        # Check if already in cart, update quantity
        for item in self.cart:
            if item["batch_id"] == batch["id"]:
                item["quantity"] += qty
                item["total_price"] = item["quantity"] * item["unit_price"]
                self.update_cart_display()
                return

        # Add new entry
        self.cart.append({
            "medicine_id": self.selected_med["id"],
            "medicine_name": self.selected_med["name"],
            "batch_id": batch["id"],
            "batch_number": batch["batch_number"],
            "expiry_date": batch["expiry_date"],
            "unit_price": batch["selling_price"],
            "unit_cost": batch["purchase_price"],
            "quantity": qty,
            "total_price": qty * batch["selling_price"]
        })

        self.update_cart_display()
        self.qty_entry.delete(0, tk.END)
        self.qty_entry.insert(0, "1")

    def update_cart_display(self):
        # Clear treeview
        for row in self.cart_tree.get_children():
            self.cart_tree.delete(row)

        for idx, item in enumerate(self.cart):
            self.cart_tree.insert("", "end", iid=str(idx), values=(
                item["medicine_name"],
                item["batch_number"],
                item["expiry_date"],
                f"${item['unit_price']:.2f}",
                item["quantity"],
                f"${item['total_price']:.2f}"
            ))

        self.calculate_totals()

    def remove_from_cart(self):
        selected = self.cart_tree.selection()
        if not selected:
            return
        idx = int(selected[0])
        del self.cart[idx]
        self.update_cart_display()

    def clear_cart(self):
        self.cart.clear()
        self.update_cart_display()

    def calculate_totals(self):
        subtotal = sum(item["total_price"] for item in self.cart)
        try:
            discount = float(self.discount_var.get().strip() or 0)
        except ValueError:
            discount = 0.0

        grand_total = max(0.0, subtotal - discount)
        self.subtotal_lbl.configure(text=f"${subtotal:.2f}")
        self.grand_total_lbl.configure(text=f"${grand_total:.2f}")
        self.calculate_change()

    def calculate_change(self):
        try:
            grand_total_text = self.grand_total_lbl.cget("text").replace("$", "")
            grand_total = float(grand_total_text)
            tendered = float(self.tendered_var.get().strip() or 0)
            change = tendered - grand_total
            if change >= 0:
                self.change_lbl.configure(text=f"${change:.2f}", text_color=theme.SUCCESS_COLOR)
            else:
                self.change_lbl.configure(text=f"-${abs(change):.2f}", text_color=theme.DANGER_COLOR)
        except:
            self.change_lbl.configure(text="$0.00", text_color=theme.PRIMARY_COLOR)

    def execute_checkout(self):
        if not self.cart:
            messagebox.showwarning("Empty Cart", "No items have been added to the sale.")
            return

        try:
            discount = float(self.discount_var.get().strip() or 0)
        except ValueError:
            discount = 0.0

        success, msg, invoice_no = checkout_sale(
            cart_items=self.cart,
            customer_name=self.cust_name_entry.get(),
            customer_phone=self.cust_phone_entry.get(),
            discount=discount,
            payment_method=self.pay_method_var.get()
        )

        if not success:
            messagebox.showerror("Checkout Error", f"Failed to complete sale: {msg}")
            return

        # Fetch sale details for thermal receipt preview
        sale_details = get_sale_details(invoice_no)
        receipt_text = generate_thermal_receipt_text(sale_details)

        # Clear cart and refresh
        self.clear_cart()
        self.refresh_medicines_list()
        self.tendered_var.set("")

        # Show Receipt Modal
        self.show_receipt_dialog(invoice_no, receipt_text)

    def show_receipt_dialog(self, invoice_no, receipt_text):
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Receipt - {invoice_no}")
        dialog.geometry("460x580")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        ctk.CTkLabel(dialog, text=f"Sale Completed: {invoice_no}", font=theme.FONT_SUBTITLE, text_color=theme.SUCCESS_COLOR).pack(pady=10)

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
