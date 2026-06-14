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

"""Setup / Init view — configure Git remote, slicers, and clone repo."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from . import theme as T
from .widgets import LogPanel, SpinnerOverlay, action_button, secondary_button


class SetupView(ctk.CTkFrame):
    """
    Guided first-time setup:
      1. Enter Git remote URL
      2. Choose local repo directory
      3. Select which slicers to enable
      4. Confirm profile paths
      5. Initialize (clone repo)
    """

    def __init__(self, parent: tk.Widget, app_ref) -> None:
        super().__init__(parent, fg_color="transparent")
        self._app = app_ref  # reference to App for callbacks
        self._slicer_vars: dict[str, tk.BooleanVar] = {}
        self._path_vars:   dict[str, tk.StringVar]  = {}
        self._build_ui()

    # ─── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        # ── Title ──
        title_f = ctk.CTkFrame(self, fg_color="transparent")
        title_f.grid(row=0, column=0, sticky="ew", padx=T.PAD_LG, pady=(T.PAD_LG, 4))
        ctk.CTkLabel(title_f, text="⚙  Setup",
                     text_color=T.TEXT_PRIMARY,
                     font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
                     anchor="w").pack(side="left")
        ctk.CTkLabel(title_f,
                     text="Connect to your Git repository and select slicers to sync",
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
        self._populate_form()

        # ── Action log ──
        self._log = LogPanel(self, height=130)
        self._log.grid(row=2, column=0, sticky="ew",
                       padx=T.PAD_LG, pady=(0, T.PAD_SM))

        # ── Bottom buttons ──
        btn_f = ctk.CTkFrame(self, fg_color="transparent")
        btn_f.grid(row=3, column=0, sticky="ew", padx=T.PAD_LG, pady=(0, T.PAD_LG))
        self._init_btn = action_button(btn_f, "Initialize", self._on_init,
                                       width=150, icon="🚀")
        self._init_btn.pack(side="left")
        secondary_button(btn_f, "Load Existing Config",
                         self._on_load_config, width=180).pack(
            side="left", padx=(T.PAD_SM, 0))
        self._status_lbl = ctk.CTkLabel(btn_f, text="",
                                        text_color=T.TEXT_SECONDARY,
                                        font=ctk.CTkFont(family="Segoe UI",
                                                         size=10))
        self._status_lbl.pack(side="right")

    def _populate_form(self) -> None:
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
        remote_f = ctk.CTkFrame(f, fg_color="transparent")
        remote_f.grid(row=row, column=0, sticky="ew")
        remote_f.columnconfigure(0, weight=1)
        row += 1
        self._remote_var = tk.StringVar()
        remote_entry = ctk.CTkEntry(remote_f, textvariable=self._remote_var,
                                    fg_color=T.BG_INPUT,
                                    border_color=T.BORDER,
                                    text_color=T.TEXT_PRIMARY,
                                    font=ctk.CTkFont(family="Consolas", size=10),
                                    height=34,
                                    placeholder_text="git@github.com:you/slicer-profiles.git")
        remote_entry.grid(row=0, column=0, sticky="ew", padx=(0, T.PAD_SM))
        self._test_btn = secondary_button(remote_f, "Test", self._test_remote,
                                          width=70)
        self._test_btn.grid(row=0, column=1)
        self._remote_status = ctk.CTkLabel(remote_f, text="",
                                           text_color=T.TEXT_DIM,
                                           font=ctk.CTkFont(family="Segoe UI",
                                                            size=10))
        self._remote_status.grid(row=1, column=0, columnspan=2, sticky="w",
                                 pady=(2, 0))

        sep()

        # ── Local Repo Dir ──
        label("LOCAL CLONE DIRECTORY")
        dir_f = ctk.CTkFrame(f, fg_color="transparent")
        dir_f.grid(row=row, column=0, sticky="ew")
        dir_f.columnconfigure(0, weight=1)
        row += 1
        self._repo_dir_var = tk.StringVar()
        ctk.CTkEntry(dir_f, textvariable=self._repo_dir_var,
                     fg_color=T.BG_INPUT,
                     border_color=T.BORDER,
                     text_color=T.TEXT_PRIMARY,
                     font=ctk.CTkFont(family="Consolas", size=10),
                     height=34,
                     placeholder_text="(auto-detected from remote URL)").grid(
            row=0, column=0, sticky="ew", padx=(0, T.PAD_SM))
        secondary_button(dir_f, "Browse…", self._browse_repo_dir,
                         width=80).grid(row=0, column=1)

        sep()

        # ── Slicer Selection ──
        label("SLICERS TO SYNC")
        self._slicer_frame = ctk.CTkFrame(f, fg_color="transparent")
        self._slicer_frame.grid(row=row, column=0, sticky="ew")
        row += 1
        self._build_slicer_checkboxes()

        sep()

        # ── Slicer Paths ──
        label("SLICER PROFILE PATHS")
        ctk.CTkLabel(f,
                     text="Click 'Detect' to auto-fill, or enter custom paths:",
                     text_color=T.TEXT_DIM,
                     font=ctk.CTkFont(family="Segoe UI", size=10),
                     anchor="w").grid(row=row, column=0, sticky="w", pady=(0, T.PAD_SM))
        row += 1
        self._paths_frame = ctk.CTkFrame(f, fg_color="transparent")
        self._paths_frame.grid(row=row, column=0, sticky="ew")
        self._paths_frame.columnconfigure(0, weight=1)
        row += 1
        self._build_path_rows()

        sep()

        # ── Editor ──
        label("CONFLICT EDITOR  (launched for merge conflicts)")
        editor_f = ctk.CTkFrame(f, fg_color="transparent")
        editor_f.grid(row=row, column=0, sticky="ew")
        editor_f.columnconfigure(0, weight=1)
        row += 1
        self._editor_var = tk.StringVar(value="code --wait")
        ctk.CTkEntry(editor_f, textvariable=self._editor_var,
                     fg_color=T.BG_INPUT,
                     border_color=T.BORDER,
                     text_color=T.TEXT_PRIMARY,
                     font=ctk.CTkFont(family="Consolas", size=10),
                     height=34,
                     placeholder_text="code --wait").grid(
            row=0, column=0, sticky="ew")
        ctk.CTkLabel(editor_f,
                     text="  e.g.  code --wait   vim   subl -w   notepad",
                     text_color=T.TEXT_DIM,
                     font=ctk.CTkFont(family="Segoe UI", size=9)).grid(
            row=1, column=0, sticky="w", pady=(2, 0))

    def _build_slicer_checkboxes(self) -> None:
        from ..slicers import get_default_slicers
        for w in self._slicer_frame.winfo_children():
            w.destroy()
        self._slicer_vars.clear()

        slicers = get_default_slicers()
        cols = 2
        for idx, s in enumerate(slicers):
            col = idx % cols
            row_ = idx // cols
            var = tk.BooleanVar(value=False)
            self._slicer_vars[s.key] = var

            # Check if detected
            detected = any(p.exists() for p in s.default_profile_dirs)
            color = T.SUCCESS if detected else T.TEXT_DIM
            badge = "✓" if detected else "○"

            cb = ctk.CTkCheckBox(
                self._slicer_frame,
                text=f"{badge}  {s.display}",
                variable=var,
                command=self._on_slicer_toggle,
                text_color=color,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                checkbox_width=16, checkbox_height=16, corner_radius=3,
                fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
            )
            cb.grid(row=row_, column=col, sticky="w",
                    padx=(0, T.PAD_LG), pady=3)

            # Auto-check if detected
            if detected:
                var.set(True)

    def _build_path_rows(self) -> None:
        from ..slicers import get_default_slicers
        for w in self._paths_frame.winfo_children():
            w.destroy()
        self._path_vars.clear()

        slicers = get_default_slicers()
        enabled_keys = [k for k, v in self._slicer_vars.items() if v.get()]
        slicer_map = {s.key: s for s in slicers}

        for idx, key in enumerate(enabled_keys):
            s = slicer_map.get(key)
            if not s:
                continue

            row_f = ctk.CTkFrame(self._paths_frame, fg_color="transparent")
            row_f.grid(row=idx, column=0, sticky="ew", pady=2)
            row_f.columnconfigure(1, weight=1)

            color = T.SLICER_COLORS.get(key, T.TEXT_SECONDARY)
            ctk.CTkLabel(row_f, text=s.display, text_color=color,
                         font=ctk.CTkFont(family="Segoe UI", size=10,
                                          weight="bold"),
                         width=140, anchor="w").grid(row=0, column=0,
                                                     padx=(0, T.PAD_SM))

            var = tk.StringVar()
            self._path_vars[key] = var

            # Fill default if exists
            default = s.default_profile_dirs[0] if s.default_profile_dirs else None
            if default:
                var.set(str(default))

            entry = ctk.CTkEntry(row_f, textvariable=var,
                                 fg_color=T.BG_INPUT, border_color=T.BORDER,
                                 text_color=T.TEXT_PRIMARY,
                                 font=ctk.CTkFont(family="Consolas", size=9),
                                 height=30)
            entry.grid(row=0, column=1, sticky="ew", padx=(0, T.PAD_SM))

            _key = key
            secondary_button(row_f, "…", lambda k=_key: self._browse_slicer_path(k),
                             width=36).grid(row=0, column=2)

        if not enabled_keys:
            ctk.CTkLabel(self._paths_frame,
                         text="Select at least one slicer above",
                         text_color=T.TEXT_DIM,
                         font=ctk.CTkFont(family="Segoe UI", size=10)).grid(
                row=0, column=0, sticky="w", pady=T.PAD_SM)

    def _on_slicer_toggle(self) -> None:
        self._build_path_rows()

    # ─── Event handlers ───────────────────────────────────────────────────────

    def _test_remote(self) -> None:
        remote = self._remote_var.get().strip()
        if not remote:
            self._remote_status.configure(text="⚠ Enter a remote URL first",
                                          text_color=T.WARNING)
            return
        self._test_btn.configure(state="disabled", text="Testing…")
        self._remote_status.configure(text="Checking access…",
                                      text_color=T.TEXT_DIM)

        def _run():
            from ..git import validate_git_remote, suggest_repo_dir_from_remote
            ok, msg = validate_git_remote(remote)
            if ok and not self._repo_dir_var.get().strip():
                suggested = suggest_repo_dir_from_remote(remote)
                self.after(0, lambda: self._repo_dir_var.set(str(suggested)))

            def _update():
                self._test_btn.configure(state="normal", text="Test")
                if ok:
                    self._remote_status.configure(
                        text="✓ Repository accessible",
                        text_color=T.SUCCESS)
                else:
                    self._remote_status.configure(
                        text=f"✗ {msg.splitlines()[0]}",
                        text_color=T.ERROR)
            self.after(0, _update)

        threading.Thread(target=_run, daemon=True).start()

    def _browse_repo_dir(self) -> None:
        path = filedialog.askdirectory(title="Choose local clone directory")
        if path:
            self._repo_dir_var.set(path)

    def _browse_slicer_path(self, key: str) -> None:
        path = filedialog.askdirectory(title="Choose slicer profile directory")
        if path and key in self._path_vars:
            self._path_vars[key].set(path)

    def _on_load_config(self) -> None:
        """Load an existing config.json and populate form fields."""
        try:
            from ..config import Config
            cfg = Config.load()
            self._remote_var.set(cfg.github_remote)
            self._repo_dir_var.set(str(cfg.repo_dir))
            for key, var in self._slicer_vars.items():
                var.set(key in cfg.enabled_slicers)
            self._on_slicer_toggle()
            for key, paths in cfg.slicer_profile_dirs.items():
                if key in self._path_vars and paths:
                    self._path_vars[key].set(paths[0])
            if cfg.editor_cmd:
                self._editor_var.set(cfg.editor_cmd)
            self._log.append("Loaded existing config\n", "ok")
        except FileNotFoundError:
            self._log.append("No config.json found — fill in the form manually\n", "warn")
        except Exception as e:
            self._log.append(f"Error loading config: {e}\n", "error")

    def _on_init(self) -> None:
        remote   = self._remote_var.get().strip()
        repo_dir = self._repo_dir_var.get().strip()
        enabled  = [k for k, v in self._slicer_vars.items() if v.get()]
        editor   = self._editor_var.get().strip() or None

        if not remote:
            self._log.append("⚠ Enter a Git remote URL\n", "warn"); return
        if not enabled:
            self._log.append("⚠ Select at least one slicer\n", "warn"); return

        paths: dict[str, list[str]] = {}
        for key in enabled:
            raw = self._path_vars.get(key, tk.StringVar()).get().strip()
            paths[key] = [raw] if raw else []

        self._init_btn.configure(state="disabled", text="Initializing…")
        self._log.clear()
        self._log.append("Starting initialization…\n", "info")

        def _run():
            try:
                from ..git import (
                    ensure_git_available, validate_git_remote,
                    suggest_repo_dir_from_remote, guard_not_dev_repo,
                    clone_or_open_repo,
                )
                from ..config import Config

                ensure_git_available()
                self.after(0, lambda: self._log.append("Git available ✓\n", "ok"))

                ok, err_msg = validate_git_remote(remote)
                if not ok:
                    raise RuntimeError(err_msg)
                self.after(0, lambda: self._log.append("Remote accessible ✓\n", "ok"))

                rdir = Path(repo_dir) if repo_dir else suggest_repo_dir_from_remote(remote)
                guard_not_dev_repo(rdir)

                self.after(0, lambda: self._log.append(f"Cloning to {rdir}…\n", "info"))
                clone_or_open_repo(rdir, remote)
                self.after(0, lambda: self._log.append("Repository ready ✓\n", "ok"))

                cfg = Config(
                    github_remote=remote,
                    repo_dir=rdir,
                    enabled_slicers=enabled,
                    slicer_profile_dirs=paths,
                    editor_cmd=editor,
                )
                cfg.save()
                self.after(0, lambda: self._log.append(
                    f"Config saved to {Config.path()} ✓\n", "ok"))
                self.after(0, lambda: self._finish_init(True))

            except Exception as e:
                msg = str(e)
                self.after(0, lambda: self._log.append(f"\n✗ Error: {msg}\n", "error"))
                self.after(0, lambda: self._finish_init(False))

        threading.Thread(target=_run, daemon=True).start()

    def _finish_init(self, ok: bool) -> None:
        self._init_btn.configure(state="normal", text="Initialize")
        if ok:
            self._log.append("\n✓ Setup complete! Switch to the Sync tab.\n", "ok")
            from .widgets import show_toast
            show_toast(self, "Setup complete — ready to sync!", "success")
            # Notify app to refresh
            if hasattr(self._app, "on_setup_complete"):
                self._app.on_setup_complete()

    # ─── Public ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Reload slicer detection (called when view becomes active)."""
        self._build_slicer_checkboxes()
        self._build_path_rows()
        self._on_load_config()
