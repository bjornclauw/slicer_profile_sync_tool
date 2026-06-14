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

"""Settings view — edit configuration without touching config.json manually."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from . import theme as T
from .widgets import LogPanel, action_button, secondary_button, show_toast


class SettingsView(ctk.CTkFrame):
    """
    Edit the current config.json:
      - Git remote
      - Local repo directory
      - Per-slicer enable / disable + path
      - Editor command
    """

    def __init__(self, parent: tk.Widget, app_ref) -> None:
        super().__init__(parent, fg_color="transparent")
        self._app = app_ref
        self._slicer_enabled: dict[str, tk.BooleanVar] = {}
        self._slicer_paths:   dict[str, tk.StringVar]  = {}
        self._build_ui()

    # ─── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        # ── Title ──
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=T.PAD_LG,
                 pady=(T.PAD_LG, 4))
        ctk.CTkLabel(top, text="🔧  Settings",
                     text_color=T.TEXT_PRIMARY,
                     font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
                     anchor="w").pack(side="left")
        ctk.CTkLabel(top,
                     text="Edit your sync configuration",
                     text_color=T.TEXT_SECONDARY,
                     font=ctk.CTkFont(family="Segoe UI", size=11),
                     anchor="w").pack(side="left", padx=(T.PAD, 0), pady=(4, 0))

        # ── Scrollable form ──
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                        scrollbar_button_color=T.BG_HOVER)
        scroll.grid(row=1, column=0, sticky="nsew",
                    padx=T.PAD_LG, pady=(0, T.PAD_SM))
        scroll.columnconfigure(0, weight=1)
        self._form = scroll
        self._build_form()

        # ── Bottom bar ──
        bot = ctk.CTkFrame(self, fg_color="transparent")
        bot.grid(row=2, column=0, sticky="ew", padx=T.PAD_LG, pady=T.PAD_SM)
        action_button(bot, "Save Settings", self._on_save,
                      width=160, icon="💾").pack(side="left")
        secondary_button(bot, "⟳  Reload", self._reload_from_disk,
                         width=110).pack(side="left", padx=(T.PAD_SM, 0))

        self._log = LogPanel(self, height=90)
        self._log.grid(row=3, column=0, sticky="ew",
                       padx=T.PAD_LG, pady=(0, T.PAD_LG))

    def _build_form(self) -> None:
        f = self._form
        row = 0

        def sep() -> None:
            nonlocal row
            ctk.CTkFrame(f, fg_color=T.BORDER, height=1,
                         corner_radius=0).grid(
                row=row, column=0, sticky="ew", pady=(T.PAD, T.PAD_SM))
            row += 1

        def label(text: str) -> None:
            nonlocal row
            ctk.CTkLabel(f, text=text, text_color=T.TEXT_SECONDARY,
                         font=ctk.CTkFont(family="Segoe UI", size=10,
                                          weight="bold"),
                         anchor="w").grid(row=row, column=0, sticky="w",
                                          pady=(T.PAD_SM, 2))
            row += 1

        # ── Git Remote ──
        label("GIT REMOTE URL")
        self._remote_var = tk.StringVar()
        ctk.CTkEntry(f, textvariable=self._remote_var,
                     fg_color=T.BG_INPUT, border_color=T.BORDER,
                     text_color=T.TEXT_PRIMARY,
                     font=ctk.CTkFont(family="Consolas", size=10),
                     height=34).grid(row=row, column=0, sticky="ew")
        row += 1

        sep()

        # ── Repo Dir ──
        label("LOCAL CLONE DIRECTORY")
        dir_f = ctk.CTkFrame(f, fg_color="transparent")
        dir_f.grid(row=row, column=0, sticky="ew")
        dir_f.columnconfigure(0, weight=1)
        row += 1
        self._repo_dir_var = tk.StringVar()
        ctk.CTkEntry(dir_f, textvariable=self._repo_dir_var,
                     fg_color=T.BG_INPUT, border_color=T.BORDER,
                     text_color=T.TEXT_PRIMARY,
                     font=ctk.CTkFont(family="Consolas", size=10),
                     height=34).grid(row=0, column=0, sticky="ew",
                                     padx=(0, T.PAD_SM))
        secondary_button(dir_f, "Browse…",
                         self._browse_repo_dir, width=80).grid(row=0, column=1)

        sep()

        # ── Slicer toggles + paths ──
        label("SLICER PROFILES")
        self._slicers_frame = ctk.CTkFrame(f, fg_color="transparent")
        self._slicers_frame.grid(row=row, column=0, sticky="ew")
        self._slicers_frame.columnconfigure(0, weight=1)
        row += 1

        sep()

        # ── Editor ──
        label("CONFLICT EDITOR")
        self._editor_var = tk.StringVar(value="code --wait")
        ctk.CTkEntry(f, textvariable=self._editor_var,
                     fg_color=T.BG_INPUT, border_color=T.BORDER,
                     text_color=T.TEXT_PRIMARY,
                     font=ctk.CTkFont(family="Consolas", size=10),
                     height=34).grid(row=row, column=0, sticky="ew")
        row += 1
        ctk.CTkLabel(f,
                     text="  e.g.  code --wait   vim   subl -w   notepad",
                     text_color=T.TEXT_DIM,
                     font=ctk.CTkFont(family="Segoe UI", size=9),
                     anchor="w").grid(row=row, column=0, sticky="w",
                                      pady=(2, 0))
        row += 1

    def _populate_slicer_rows(self, cfg) -> None:
        """Build per-slicer enable+path rows from loaded config."""
        from ..slicers import get_default_slicers
        for w in self._slicers_frame.winfo_children():
            w.destroy()
        self._slicer_enabled.clear()
        self._slicer_paths.clear()

        slicers = get_default_slicers()
        for idx, s in enumerate(slicers):
            row_f = ctk.CTkFrame(self._slicers_frame, fg_color="transparent")
            row_f.grid(row=idx, column=0, sticky="ew", pady=3)
            row_f.columnconfigure(2, weight=1)

            en_var = tk.BooleanVar(value=s.key in (cfg.enabled_slicers if cfg else []))
            self._slicer_enabled[s.key] = en_var

            cb = ctk.CTkCheckBox(
                row_f,
                text=s.display,
                variable=en_var,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=T.SLICER_COLORS.get(s.key, T.TEXT_PRIMARY),
                checkbox_width=16, checkbox_height=16, corner_radius=3,
                fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                width=160,
            )
            cb.grid(row=0, column=0, sticky="w", padx=(0, T.PAD_SM))

            path_var = tk.StringVar()
            self._slicer_paths[s.key] = path_var
            existing = cfg.slicer_profile_dirs.get(s.key, []) if cfg else []
            if existing:
                path_var.set(existing[0])
            elif s.default_profile_dirs:
                path_var.set(str(s.default_profile_dirs[0]))

            path_entry = ctk.CTkEntry(
                row_f, textvariable=path_var,
                fg_color=T.BG_INPUT, border_color=T.BORDER,
                text_color=T.TEXT_PRIMARY,
                font=ctk.CTkFont(family="Consolas", size=9),
                height=30,
            )
            path_entry.grid(row=0, column=2, sticky="ew", padx=(0, T.PAD_SM))

            _key = s.key
            secondary_button(row_f, "…",
                             lambda k=_key: self._browse_slicer(k),
                             width=36).grid(row=0, column=3)

    def _browse_repo_dir(self) -> None:
        p = filedialog.askdirectory(title="Choose local clone directory")
        if p:
            self._repo_dir_var.set(p)

    def _browse_slicer(self, key: str) -> None:
        p = filedialog.askdirectory(title="Choose slicer profile directory")
        if p and key in self._slicer_paths:
            self._slicer_paths[key].set(p)

    # ─── Save / Load ──────────────────────────────────────────────────────────

    def _on_save(self) -> None:
        from ..config import Config
        try:
            remote   = self._remote_var.get().strip()
            repo_dir = Path(self._repo_dir_var.get().strip())
            editor   = self._editor_var.get().strip() or None
            enabled  = [k for k, v in self._slicer_enabled.items() if v.get()]
            paths    = {
                k: [self._slicer_paths[k].get().strip()]
                for k in enabled
                if k in self._slicer_paths and self._slicer_paths[k].get().strip()
            }

            if not remote:
                self._log.append("⚠ Remote URL is required\n", "warn"); return
            if not enabled:
                self._log.append("⚠ Enable at least one slicer\n", "warn"); return

            cfg = Config(
                github_remote=remote,
                repo_dir=repo_dir,
                enabled_slicers=enabled,
                slicer_profile_dirs=paths,
                editor_cmd=editor,
            )
            cfg.save()
            self._log.append(f"✓ Settings saved to {Config.path()}\n", "ok")
            show_toast(self, "Settings saved!", "success")

        except Exception as e:
            self._log.append(f"✗ Save failed: {e}\n", "error")

    def _reload_from_disk(self) -> None:
        self.refresh()

    # ─── Public ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        try:
            from ..config import Config
            cfg = Config.load()
            self._remote_var.set(cfg.github_remote)
            self._repo_dir_var.set(str(cfg.repo_dir))
            self._editor_var.set(cfg.editor_cmd or "code --wait")
            self._populate_slicer_rows(cfg)
            self._log.clear()
            self._log.append("Config loaded from disk\n", "ok")
        except FileNotFoundError:
            self._populate_slicer_rows(None)
            self._log.clear()
            self._log.append("⚠ No config.json yet — use Setup to initialize\n",
                             "warn")
        except Exception as e:
            self._log.clear()
            self._log.append(f"Error loading config: {e}\n", "error")
