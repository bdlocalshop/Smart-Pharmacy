import customtkinter as ctk
import tkinter as tk
from datetime import datetime
from ui.pos_view import POSView
from ui.inventory_view import InventoryView
from ui.alerts_view import AlertsView
from ui.reports_view import ReportsView
from ui.backup_view import BackupView
import ui.theme as theme

class AppWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window settings
        self.title("Smart Pharmacy - Desktop Management System")
        self.geometry("1280x780")
        self.minsize(1050, 680)

        # Set appearance
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Configure Grid Layout (Sidebar + Main Area)
        self.grid_columnconfigure(0, weight=0)  # Sidebar fixed width
        self.grid_columnconfigure(1, weight=1)  # Main views dynamic
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_views()

        # Start on POS tab
        self.show_view("pos")

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(7, weight=1)

        # App Brand Header
        brand_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand_frame.grid(row=0, column=0, padx=15, pady=(20, 20), sticky="ew")

        ctk.CTkLabel(brand_frame, text="💊 SMART PHARMACY", font=theme.FONT_TITLE, text_color=theme.PRIMARY_COLOR).pack(anchor="w")
        ctk.CTkLabel(brand_frame, text="Desktop POS & Inventory", font=theme.FONT_SMALL, text_color="gray60").pack(anchor="w")

        # Nav Buttons
        self.nav_buttons = {}

        nav_items = [
            ("pos", "🛒  Point of Sale (POS)", theme.PRIMARY_COLOR),
            ("inventory", "📦  Inventory & Batches", theme.ACCENT_COLOR),
            ("alerts", "⚠️  Expiry Radar & Stock", theme.WARNING_COLOR),
            ("reports", "📊  Daily Sales & Reports", "#065F46"),
            ("backup", "💾  Backup & Database", "gray40")
        ]

        for idx, (key, label, accent_c) in enumerate(nav_items, start=1):
            btn = ctk.CTkButton(
                self.sidebar,
                text=label,
                font=theme.FONT_BODY_BOLD,
                anchor="w",
                height=42,
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray80", "gray25"),
                command=lambda k=key: self.show_view(k)
            )
            btn.grid(row=idx, column=0, padx=12, pady=4, sticky="ew")
            self.nav_buttons[key] = (btn, accent_c)

        # Bottom section: Appearance & Clock
        bottom_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom_frame.grid(row=8, column=0, padx=15, pady=15, sticky="ew")

        ctk.CTkLabel(bottom_frame, text="Appearance:", font=theme.FONT_SMALL).pack(anchor="w", pady=(0, 2))
        self.mode_menu = ctk.CTkOptionMenu(
            bottom_frame,
            values=["Dark", "Light", "System"],
            command=ctk.set_appearance_mode,
            height=28
        )
        self.mode_menu.pack(fill="x", pady=(0, 8))

        self.clock_lbl = ctk.CTkLabel(bottom_frame, text="", font=theme.FONT_SMALL, text_color="gray50")
        self.clock_lbl.pack(anchor="w")
        self._update_clock()

    def _build_views(self):
        # Container frame for views
        self.views_container = ctk.CTkFrame(self, fg_color="transparent")
        self.views_container.grid(row=0, column=1, sticky="nsew")
        self.views_container.grid_rowconfigure(0, weight=1)
        self.views_container.grid_columnconfigure(0, weight=1)

        # Instantiate view instances
        self.views = {
            "pos": POSView(self.views_container),
            "inventory": InventoryView(self.views_container),
            "alerts": AlertsView(self.views_container),
            "reports": ReportsView(self.views_container),
            "backup": BackupView(self.views_container)
        }

        for view in self.views.values():
            view.grid(row=0, column=0, sticky="nsew")
            view.grid_remove()

    def show_view(self, key):
        # Update button highlights
        for k, (btn, accent_c) in self.nav_buttons.items():
            if k == key:
                btn.configure(fg_color=accent_c, text_color="white")
            else:
                btn.configure(fg_color="transparent", text_color=("gray10", "gray90"))

        # Hide all and show target
        for k, view in self.views.items():
            if k == key:
                view.grid()
                # Trigger view-specific data refresh
                if hasattr(view, "refresh_medicines_list"):
                    view.refresh_medicines_list()
                elif hasattr(view, "refresh_table"):
                    view.refresh_table()
                elif hasattr(view, "refresh_alerts"):
                    view.refresh_alerts()
                elif hasattr(view, "load_daily_volume"):
                    view.load_daily_volume()
                elif hasattr(view, "refresh_backups_list"):
                    view.refresh_backups_list()
            else:
                view.grid_remove()

    def _update_clock(self):
        now_str = datetime.now().strftime("%Y-%m-%d  %I:%M %p")
        self.clock_lbl.configure(text=f"🕒 {now_str}")
        self.after(1000, self._update_clock)
