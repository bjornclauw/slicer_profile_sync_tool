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

"""History view — browse commit log and restore previous profile versions."""

from __future__ import annotations

import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path

import customtkinter as ctk

from . import theme as T
from .widgets import LogPanel, action_button, secondary_button, show_toast


class HistoryView(ctk.CTkFrame):
    """
    Shows the Git commit history for the profiles repo.
    User can select a commit, preview which files changed, and restore.
    """

    def __init__(self, parent: tk.Widget, app_ref) -> None:
        super().__init__(parent, fg_color="transparent")
        self._app = app_ref
        self._cfg = None
        self._commits: list[str] = []  # raw commit lines
        self._selected_commit: str | None = None
        self._build_ui()

    # ─── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        # ── Title ──
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=T.PAD_LG, pady=(T.PAD_LG, 4))
        ctk.CTkLabel(top, text="🕓  History",
                     text_color=T.TEXT_PRIMARY,
                     font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
                     anchor="w").pack(side="left")
        ctk.CTkLabel(top,
                     text="Browse saved versions and restore any previous profile state",
                     text_color=T.TEXT_SECONDARY,
                     font=ctk.CTkFont(family="Segoe UI", size=11),
                     anchor="w").pack(side="left", padx=(T.PAD, 0), pady=(4, 0))

        # ── Split: commit list (left) + detail (right) ──
        split = ctk.CTkFrame(self, fg_color="transparent")
        split.grid(row=1, column=0, sticky="nsew",
                   padx=T.PAD_LG, pady=(0, T.PAD_SM))
        split.rowconfigure(0, weight=1)
        split.columnconfigure(0, weight=2)
        split.columnconfigure(1, weight=3)

        # Left: commit list
        left = ctk.CTkFrame(split, fg_color=T.BG_CARD,
                            corner_radius=T.CORNER_RADIUS)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, T.PAD_SM))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        lhdr = ctk.CTkFrame(left, fg_color="transparent")
        lhdr.grid(row=0, column=0, sticky="ew", padx=T.PAD, pady=(T.PAD_SM, 0))
        ctk.CTkLabel(lhdr, text="Saved Versions",
                     text_color=T.TEXT_SECONDARY,
                     font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                     anchor="w").pack(side="left")
        secondary_button(lhdr, "⟳", self._on_refresh_history, width=36).pack(
            side="right")

        self._commit_list = tk.Listbox(
            left,
            bg=T.BG_INPUT,
            fg=T.TEXT_PRIMARY,
            font=T.FONT_MONO_SM,
            relief="flat",
            bd=0,
            selectmode="single",
            activestyle="none",
            selectbackground=T.ACCENT,
            selectforeground=T.BG_DARK,
            highlightthickness=0,
        )
        scroll_c = ctk.CTkScrollbar(left, command=self._commit_list.yview)
        self._commit_list.configure(yscrollcommand=scroll_c.set)
        self._commit_list.grid(row=1, column=0, sticky="nsew",
                               padx=(T.PAD_SM, 0), pady=T.PAD_SM)
        scroll_c.grid(row=1, column=1, sticky="ns", pady=T.PAD_SM)
        self._commit_list.bind("<<ListboxSelect>>", self._on_commit_select)

        # Right: detail pane
        right = ctk.CTkFrame(split, fg_color=T.BG_CARD,
                             corner_radius=T.CORNER_RADIUS)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(2, weight=1)
        right.columnconfigure(0, weight=1)

        # Commit info card
        self._info_card = ctk.CTkFrame(right, fg_color=T.BG_INPUT,
                                       corner_radius=T.CORNER_RADIUS)
        self._info_card.grid(row=0, column=0, sticky="ew",
                             padx=T.PAD, pady=(T.PAD_SM, T.PAD_SM))
        self._info_card.columnconfigure(1, weight=1)

        self._commit_hash_lbl = ctk.CTkLabel(self._info_card, text="No version selected",
                                             text_color=T.TEXT_SECONDARY,
                                             font=ctk.CTkFont(family="Consolas",
                                                              size=10, weight="bold"),
                                             anchor="w")
        self._commit_hash_lbl.grid(row=0, column=0, sticky="w",
                                   padx=T.PAD, pady=(T.PAD_SM, 0))
        self._commit_date_lbl = ctk.CTkLabel(self._info_card, text="",
                                             text_color=T.TEXT_DIM,
                                             font=ctk.CTkFont(family="Segoe UI",
                                                              size=10),
                                             anchor="e")
        self._commit_date_lbl.grid(row=0, column=1, sticky="e",
                                   padx=T.PAD, pady=(T.PAD_SM, 0))
        self._commit_msg_lbl = ctk.CTkLabel(self._info_card, text="",
                                            text_color=T.TEXT_PRIMARY,
                                            font=ctk.CTkFont(family="Segoe UI",
                                                             size=11),
                                            anchor="w")
        self._commit_msg_lbl.grid(row=1, column=0, columnspan=2, sticky="w",
                                  padx=T.PAD, pady=(2, T.PAD_SM))

        # Files changed
        ctk.CTkLabel(right, text="FILES CHANGED IN THIS VERSION",
                     text_color=T.TEXT_DIM,
                     font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                     anchor="w").grid(row=1, column=0, sticky="w",
                                      padx=T.PAD, pady=(0, 2))

        self._files_list = tk.Listbox(
            right,
            bg=T.BG_INPUT,
            fg=T.TEXT_SECONDARY,
            font=T.FONT_MONO_SM,
            relief="flat",
            bd=0,
            selectmode="browse",
            activestyle="none",
            selectbackground=T.BG_HOVER,
            highlightthickness=0,
        )
        fs = ctk.CTkScrollbar(right, command=self._files_list.yview)
        self._files_list.configure(yscrollcommand=fs.set)
        self._files_list.grid(row=2, column=0, sticky="nsew",
                              padx=(T.PAD_SM, 0), pady=(0, T.PAD_SM))
        fs.grid(row=2, column=1, sticky="ns", padx=(0, T.PAD_SM),
                pady=(0, T.PAD_SM))

        # Restore button
        btn_row = ctk.CTkFrame(right, fg_color="transparent")
        btn_row.grid(row=3, column=0, columnspan=2, sticky="ew",
                     padx=T.PAD, pady=(0, T.PAD_SM))
        self._restore_btn = action_button(btn_row, "Restore This Version",
                                          self._on_restore,
                                          color=T.WARNING, width=200, icon="⏪")
        self._restore_btn.pack(side="left")
        self._restore_btn.configure(state="disabled")
        ctk.CTkLabel(btn_row,
                     text="  ⚠ Overwrites current slicer profiles",
                     text_color=T.WARNING,
                     font=ctk.CTkFont(family="Segoe UI", size=9)).pack(
            side="left", padx=(T.PAD_SM, 0))

        # Log
        self._log = LogPanel(self, height=90)
        self._log.grid(row=2, column=0, sticky="ew",
                       padx=T.PAD_LG, pady=(0, T.PAD_LG))

    # ─── Event handlers ───────────────────────────────────────────────────────

    def _on_commit_select(self, event=None) -> None:
        sel = self._commit_list.curselection()
        if not sel:
            return
        idx = sel[0]
        raw = self._commits[idx]  # "abc1234 2026-01-01T12:00:00+00:00 Message"
        parts = raw.split(" ", 2)
        sha = parts[0] if parts else raw
        date_raw = parts[1] if len(parts) > 1 else ""
        msg = parts[2] if len(parts) > 2 else ""

        self._selected_commit = sha
        self._commit_hash_lbl.configure(text=sha)
        self._commit_msg_lbl.configure(text=msg[:80])
        try:
            dt = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
            self._commit_date_lbl.configure(
                text=dt.strftime("%d %b %Y  %H:%M"))
        except Exception:
            self._commit_date_lbl.configure(text=date_raw[:16])

        self._restore_btn.configure(state="normal")
        self._load_changed_files(sha)

    def _load_changed_files(self, sha: str) -> None:
        self._files_list.delete(0, "end")
        self._files_list.insert("end", "  Loading…")

        def _run():
            try:
                from ..git import run as git_run
                r = git_run(
                    ["git", "show", "--name-status", "--pretty=format:", sha],
                    cwd=self._cfg.repo_dir, check=False,
                )
                lines = [l.strip() for l in r.stdout.splitlines() if l.strip()]
                def _upd():
                    self._files_list.delete(0, "end")
                    for line in lines or ["(no files changed)"]:
                        self._files_list.insert("end", f"  {line}")
                self.after(0, _upd)
            except Exception as e:
                self.after(0, lambda: self._files_list.delete(0, "end"))
                self.after(0, lambda: self._files_list.insert("end", f"  Error: {e}"))

        threading.Thread(target=_run, daemon=True).start()

    def _on_refresh_history(self) -> None:
        self.refresh()

    def _on_restore(self) -> None:
        if not self._selected_commit or not self._cfg:
            return
        sha = self._selected_commit

        # Confirm
        from tkinter import messagebox
        ok = messagebox.askyesno(
            "Restore Version",
            f"Restore profiles from commit:\n{sha}\n\n"
            "This will overwrite your current slicer profiles.\nContinue?",
        )
        if not ok:
            return

        self._restore_btn.configure(state="disabled", text="Restoring…")
        self._log.clear()
        self._log.append(f"Restoring from {sha}…\n", "info")

        def _run():
            try:
                from ..git import (
                    git_checkout_commit, git_checkout_branch,
                    run as git_run,
                )
                from ..sync import import_from_repo_to_slicers
                cfg = self._cfg

                # Stash any uncommitted changes first
                git_run(["git", "stash"], cwd=cfg.repo_dir, check=False)

                # Checkout the chosen commit
                git_checkout_commit(cfg.repo_dir, sha)
                self.after(0, lambda: self._log.append("Checked out commit ✓\n", "ok"))

                # Import profiles from that snapshot
                copied = import_from_repo_to_slicers(cfg)
                self.after(0, lambda: self._log.append(
                    f"Imported {len(copied)} profile(s) ✓\n", "ok"))

                # Return to main branch
                try:
                    git_checkout_branch(cfg.repo_dir, "main")
                except Exception:
                    git_checkout_branch(cfg.repo_dir, "master")

                # Restore stash
                git_run(["git", "stash", "pop"], cwd=cfg.repo_dir, check=False)

                def _done():
                    self._restore_btn.configure(state="normal",
                                                text="Restore This Version")
                    self._log.append("✓ Restore complete!\n", "ok")
                    show_toast(self, "Version restored!", "success")

                self.after(0, _done)

            except Exception as e:
                def _err():
                    self._restore_btn.configure(state="normal",
                                                text="Restore This Version")
                    self._log.append(f"\n✗ Restore failed: {e}\n", "error")

                self.after(0, _err)

        threading.Thread(target=_run, daemon=True).start()

    # ─── Public ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        try:
            from ..config import Config
            from ..git import git_list_commits
            self._cfg = Config.load()
        except FileNotFoundError:
            self._log.clear()
            self._log.append("⚠ No config found. Go to Setup first.\n", "warn")
            return
        except Exception as e:
            self._log.clear()
            self._log.append(f"Error: {e}\n", "error")
            return

        self._commit_list.delete(0, "end")
        self._commit_list.insert("end", "  Loading…")

        def _run():
            try:
                from ..git import git_list_commits
                commits = git_list_commits(self._cfg.repo_dir, limit=50)
                def _upd():
                    self._commits = commits
                    self._commit_list.delete(0, "end")
                    if not commits:
                        self._commit_list.insert("end", "  No commits yet")
                        return
                    for raw in commits:
                        parts = raw.split(" ", 2)
                        sha = parts[0][:7]
                        try:
                            dt = datetime.fromisoformat(
                                parts[1].replace("Z", "+00:00"))
                            date = dt.strftime("%d %b %Y  %H:%M")
                        except Exception:
                            date = parts[1][:16] if len(parts) > 1 else ""
                        msg = (parts[2][:40] + "…") if len(parts) > 2 and len(parts[2]) > 40 else (parts[2] if len(parts) > 2 else "")
                        self._commit_list.insert(
                            "end", f"  {sha}  {date}  {msg}")
                self.after(0, _upd)
            except Exception as e:
                self.after(0, lambda: self._commit_list.delete(0, "end"))
                self.after(0, lambda: self._commit_list.insert("end", f"  Error: {e}"))

        threading.Thread(target=_run, daemon=True).start()
