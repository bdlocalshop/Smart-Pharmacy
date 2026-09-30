import os
import subprocess
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from database.backup_manager import (
    create_manual_backup, restore_database, list_existing_backups, get_backups_dir
)
from database.db import get_db_path
import ui.theme as theme

class BackupView(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._build_layout()
        self.refresh_backups_list()

    def _build_layout(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ---------------- TOP ACTIONS CARD ----------------
        top_card = ctk.CTkFrame(self, corner_radius=10)
        top_card.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        top_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(top_card, text="💾 Database Maintenance & Backup Center", font=theme.FONT_TITLE).pack(anchor="w", padx=15, pady=(15, 5))
        
        info_txt = (
            "All pharmacy data is stored safely in an offline SQLite database. "
            "Automated rolling backups are taken daily upon startup. "
            "You can extract full backups to an external USB flash drive or restore from a previous snapshot anytime."
        )
        ctk.CTkLabel(top_card, text=info_txt, font=theme.FONT_BODY, wraplength=800, justify="left", text_color="gray70").pack(anchor="w", padx=15, pady=(0, 10))

        # Action Buttons
        btn_bar = ctk.CTkFrame(top_card, fg_color="transparent")
        btn_bar.pack(fill="x", padx=15, pady=(0, 15))

        ctk.CTkButton(
            btn_bar, text="📁 Backup to External USB / Folder",
            fg_color=theme.PRIMARY_COLOR, hover_color=theme.PRIMARY_HOVER,
            font=theme.FONT_BODY_BOLD, command=self.do_manual_backup
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_bar, text="🔄 Restore Database from File...",
            fg_color=theme.WARNING_COLOR, hover_color="#B45309",
            font=theme.FONT_BODY_BOLD, command=self.do_restore_from_file
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_bar, text="📂 Open Local Backups Folder",
            fg_color="gray40", hover_color="gray50",
            font=theme.FONT_BODY, command=self.open_backups_folder
        ).pack(side="right", padx=5)

        # ---------------- BACKUPS HISTORY TABLE ----------------
        hist_frame = ctk.CTkFrame(self, corner_radius=10)
        hist_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        hist_frame.grid_rowconfigure(1, weight=1)
        hist_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(hist_frame, text="Automatic Rolling Snapshots (Kept locally)", font=theme.FONT_HEADING).grid(row=0, column=0, padx=15, pady=10, sticky="w")

        cols = ("filename", "created", "size")
        self.tree = ttk.Treeview(hist_frame, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("filename", text="Backup Snapshot File")
        self.tree.heading("created", text="Date & Time")
        self.tree.heading("size", text="Size (KB)")

        self.tree.column("filename", width=340, anchor="w")
        self.tree.column("created", width=180, anchor="center")
        self.tree.column("size", width=120, anchor="center")

        scroll = ttk.Scrollbar(hist_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)

        self.tree.grid(row=1, column=0, padx=(10, 0), pady=(0, 10), sticky="nsew")
        scroll.grid(row=1, column=1, padx=(0, 10), pady=(0, 10), sticky="ns")

        # Bottom Restore Action
        act_frame = ctk.CTkFrame(hist_frame, fg_color="transparent")
        act_frame.grid(row=2, column=0, columnspan=2, padx=15, pady=(0, 10), sticky="ew")

        ctk.CTkButton(
            act_frame, text="Restore Selected Snapshot",
            fg_color=theme.WARNING_COLOR, font=theme.FONT_BODY_BOLD,
            command=self.restore_selected_snapshot
        ).pack(side="left")

    def refresh_backups_list(self):
        for r in self.tree.get_children():
            self.tree.delete(r)

        backups = list_existing_backups()
        for b in backups:
            self.tree.insert("", "end", iid=b["path"], values=(
                b["filename"],
                b["created_at"],
                f"{b['size_kb']} KB"
            ))

    def do_manual_backup(self):
        folder = filedialog.askdirectory(title="Select Destination Folder (USB Drive or Local Folder)")
        if not folder:
            return

        try:
            dest_file = create_manual_backup(folder)
            messagebox.showinfo("Backup Successful", f"Full pharmacy database backed up successfully to:\n{dest_file}")
            self.refresh_backups_list()
        except Exception as e:
            messagebox.showerror("Backup Failed", str(e))

    def do_restore_from_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Backup File to Restore",
            filetypes=[("SQLite Database", "*.db"), ("Backup Files", "*.bak"), ("All Files", "*.*")]
        )
        if not file_path:
            return

        confirm = messagebox.askyesno(
            "Confirm Database Restore",
            "WARNING: Restoring will overwrite the current live database with data from the selected backup.\n\n"
            "An emergency safety copy of your current database will be saved automatically.\n\n"
            "Do you want to proceed?"
        )
        if not confirm:
            return

        try:
            restore_database(file_path)
            messagebox.showinfo(
                "Restore Successful",
                "Database restored successfully!\nPlease restart or switch tabs to view updated data."
            )
            self.refresh_backups_list()
        except Exception as e:
            messagebox.showerror("Restore Failed", str(e))

    def restore_selected_snapshot(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Select Snapshot", "Please select a backup file from the list first.")
            return

        backup_path = selected[0]
        confirm = messagebox.askyesno(
            "Confirm Snapshot Restore",
            f"Are you sure you want to restore the database to:\n{os.path.basename(backup_path)}?"
        )
        if not confirm:
            return

        try:
            restore_database(backup_path)
            messagebox.showinfo("Restore Successful", "Database restored successfully from snapshot!")
            self.refresh_backups_list()
        except Exception as e:
            messagebox.showerror("Restore Failed", str(e))

    def open_backups_folder(self):
        folder = get_backups_dir()
        try:
            os.startfile(folder)
        except Exception:
            subprocess.Popen(["explorer", folder])
