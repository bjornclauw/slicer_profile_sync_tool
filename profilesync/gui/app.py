# Copyright 2026 Duke
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Main application window — sidebar navigation + content area."""

from __future__ import annotations

import platform
import tkinter as tk
from pathlib import Path
from typing import Optional

import customtkinter as ctk

from . import theme as T
from .history_view  import HistoryView
from .migrate_view  import MigrateView
from .settings_view import SettingsView
from .setup_view    import SetupView
from .sync_view     import SyncView


# Configure CustomTkinter globally
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ── Nav button ────────────────────────────────────────────────────────────────

class NavButton(ctk.CTkButton):
    """Sidebar navigation pill button."""

    ACTIVE_BG   = T.ACCENT
    INACTIVE_BG = "transparent"
    ACTIVE_FG   = T.BG_DARK
    INACTIVE_FG = T.TEXT_SECONDARY

    def __init__(self, parent: tk.Widget, icon: str, text: str,
                 command, **kwargs) -> None:
        super().__init__(
            parent,
            text=f"  {icon}  {text}",
            command=command,
            fg_color=self.INACTIVE_BG,
            hover_color=T.BG_HOVER,
            text_color=self.INACTIVE_FG,
            font=ctk.CTkFont(family="Segoe UI", size=14),
            anchor="w",
            corner_radius=8,
            height=44,
            border_width=0,
            **kwargs,
        )
        self._active = False

    def set_active(self, active: bool) -> None:
        self._active = active
        if active:
            self.configure(
                fg_color=self.ACTIVE_BG,
                text_color=self.ACTIVE_FG,
                font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            )
        else:
            self.configure(
                fg_color=self.INACTIVE_BG,
                text_color=self.INACTIVE_FG,
                font=ctk.CTkFont(family="Segoe UI", size=14),
            )


# ── Status bar ────────────────────────────────────────────────────────────────

class StatusBar(ctk.CTkFrame):
    """Thin bottom status bar showing Git remote and config state."""

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent, fg_color=T.BG_DARK, height=32,
                         corner_radius=0)
        self.pack_propagate(False)

        self._left = ctk.CTkLabel(self, text="",
                                  text_color=T.TEXT_DIM,
                                  font=ctk.CTkFont(family="Segoe UI", size=11),
                                  anchor="w")
        self._left.pack(side="left", padx=T.PAD_SM)

        self._right = ctk.CTkLabel(self, text="ProfileSync",
                                   text_color=T.TEXT_DIM,
                                   font=ctk.CTkFont(family="Segoe UI", size=11),
                                   anchor="e")
        self._right.pack(side="right", padx=T.PAD_SM)

    def set_remote(self, remote: str) -> None:
        short = remote[:60] + "…" if len(remote) > 60 else remote
        self._left.configure(text=f"⎔  {short}")

    def set_right(self, text: str) -> None:
        self._right.configure(text=text)


# ── Main App Window ───────────────────────────────────────────────────────────

class App(ctk.CTk):
    """Root application window."""

    TITLE   = "Slicer Profile Sync"
    MIN_W   = 980
    MIN_H   = 660

    NAV_ITEMS = [
        ("⚙",  "Setup",    "setup"),
        ("🔄", "Sync",     "sync"),
        ("📦", "Migrate",  "migrate"),
        ("🕓", "History",  "history"),
        ("🔧", "Settings", "settings"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.title(self.TITLE)
        self.minsize(self.MIN_W, self.MIN_H)
        self.geometry(f"{self.MIN_W}x{self.MIN_H}")
        self.configure(fg_color=T.BG_DARK)

        # Windows DPI awareness
        if platform.system() == "Windows":
            try:
                from ctypes import windll
                windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                pass

        self._active_key: Optional[str] = None
        self._nav_btns: dict[str, NavButton] = {}
        self._views:    dict[str, ctk.CTkFrame] = {}

        self._build_layout()
        self._build_sidebar()
        self._build_views()
        self._build_statusbar()
        self._refresh_statusbar()

        # Navigate to first appropriate tab
        try:
            from ..config import Config
            Config.load()
            self._navigate("sync")
        except FileNotFoundError:
            self._navigate("setup")

    # ─── Layout ───────────────────────────────────────────────────────────────

    def _build_layout(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # Sidebar
        self._sidebar = ctk.CTkFrame(self, fg_color=T.BG_DARK,
                                     corner_radius=0, width=T.SIDEBAR_W)
        self._sidebar.grid(row=0, column=0, sticky="nsew")
        self._sidebar.grid_propagate(False)
        self._sidebar.rowconfigure(10, weight=1)  # push bottom items down

        # Content
        self._content = ctk.CTkFrame(self, fg_color=T.BG_CARD,
                                     corner_radius=0)
        self._content.grid(row=0, column=1, sticky="nsew")
        self._content.columnconfigure(0, weight=1)
        self._content.rowconfigure(0, weight=1)

    def _build_sidebar(self) -> None:
        sb = self._sidebar

        # Logo / branding
        logo_frame = ctk.CTkFrame(sb, fg_color="transparent")
        logo_frame.grid(row=0, column=0, sticky="ew", padx=T.PAD, pady=(T.PAD_LG, T.PAD))

        ctk.CTkLabel(logo_frame, text="🖨",
                     font=ctk.CTkFont(size=30),
                     text_color=T.ACCENT).pack(anchor="w")
        ctk.CTkLabel(logo_frame, text="ProfileSync",
                     font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
                     text_color=T.TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(logo_frame, text="Slicer profile sync tool",
                     font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color=T.TEXT_DIM).pack(anchor="w")

        # Divider
        ctk.CTkFrame(sb, fg_color=T.BORDER, height=1,
                     corner_radius=0).grid(row=1, column=0, sticky="ew",
                                           padx=T.PAD, pady=(0, T.PAD_SM))

        # Nav buttons
        for nav_row, (icon, label, key) in enumerate(self.NAV_ITEMS, start=2):
            btn = NavButton(sb, icon, label,
                            command=lambda k=key: self._navigate(k))
            btn.grid(row=nav_row, column=0, sticky="ew",
                     padx=T.PAD_SM, pady=2)
            self._nav_btns[key] = btn

        # Bottom: GitHub link hint
        ctk.CTkLabel(sb, text="github.com/duke8253\n/slicer_profile_sync_tool",
                     font=ctk.CTkFont(family="Segoe UI", size=10),
                     text_color=T.TEXT_DIM,
                     justify="center").grid(row=20, column=0,
                                            padx=T.PAD, pady=T.PAD)

    def _build_views(self) -> None:
        views = {
            "setup":    SetupView(self._content, app_ref=self),
            "sync":     SyncView(self._content, app_ref=self),
            "migrate":  MigrateView(self._content, app_ref=self),
            "history":  HistoryView(self._content, app_ref=self),
            "settings": SettingsView(self._content, app_ref=self),
        }
        for key, view in views.items():
            view.grid(row=0, column=0, sticky="nsew")
            self._views[key] = view

        # Hide all initially — grid_remove keeps layout info
        for v in self._views.values():
            v.grid_remove()

    def _build_statusbar(self) -> None:
        self._statusbar = StatusBar(self)
        self._statusbar.grid(row=1, column=0, columnspan=2, sticky="ew")

    # ─── Navigation ───────────────────────────────────────────────────────────

    def _navigate(self, key: str) -> None:
        if key == self._active_key:
            return

        # Deactivate old nav button, hide old view
        if self._active_key:
            self._nav_btns[self._active_key].set_active(False)
            self._views[self._active_key].grid_remove()

        # Activate new
        self._active_key = key
        self._nav_btns[key].set_active(True)
        self._views[key].grid()

        # Call refresh hook on the view
        view = self._views[key]
        if hasattr(view, "refresh"):
            view.refresh()

        self._refresh_statusbar()

    def _refresh_statusbar(self) -> None:
        try:
            from ..config import Config
            cfg = Config.load()
            self._statusbar.set_remote(cfg.github_remote)
            self._statusbar.set_right(
                f"Python {platform.python_version()}  •  ProfileSync GUI")
        except FileNotFoundError:
            self._statusbar.set_remote("Not configured")
        except Exception:
            pass

    # ─── Callbacks from child views ───────────────────────────────────────────

    def on_setup_complete(self) -> None:
        """Called by SetupView after successful initialization."""
        self._refresh_statusbar()
        # Automatically switch to Sync tab
        self.after(800, lambda: self._navigate("sync"))
