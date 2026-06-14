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

"""Migrate view — copy profiles directly from one slicer to another."""

from __future__ import annotations

import shutil
import threading
import tkinter as tk
from pathlib import Path

import customtkinter as ctk

from . import theme as T
from .widgets import (
    CheckboxFileTree,
    FileTreeItem,
    LogPanel,
    action_button,
    secondary_button,
    show_toast,
)
from ..sync import SLICER_DISPLAY_NAMES


class MigrateView(ctk.CTkFrame):
    """
    Migrate profiles between slicers on the same machine.
    No Git involved — direct file copy from source slicer folder → destination.
    """

    def __init__(self, parent: tk.Widget, app_ref) -> None:
        super().__init__(parent, fg_color="transparent")
        self._app = app_ref
        self._slicers = []
        self._src_files: list[tuple[Path, str, str]] = []  # (path, type, name)
        self._build_ui()

    # ─── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

        # ── Title ──
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=T.PAD_LG, pady=(T.PAD_LG, 4))
        ctk.CTkLabel(top, text="📦  Migrate",
                     text_color=T.TEXT_PRIMARY,
                     font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
                     anchor="w").pack(side="left")
        ctk.CTkLabel(top,
                     text="Copy profiles from one slicer to another (no Git required)",
                     text_color=T.TEXT_SECONDARY,
                     font=ctk.CTkFont(family="Segoe UI", size=13),
                     anchor="w").pack(side="left", padx=(T.PAD, 0), pady=(4, 0))

        # ── Source / Destination controls ──
        ctrl = ctk.CTkFrame(self, fg_color=T.BG_CARD,
                            corner_radius=T.CORNER_RADIUS)
        ctrl.grid(row=1, column=0, sticky="ew", padx=T.PAD_LG, pady=(0, T.PAD_SM))
        ctrl.columnconfigure(1, weight=1)
        ctrl.columnconfigure(4, weight=1)

        # Source
        ctk.CTkLabel(ctrl, text="FROM",
                     text_color=T.TEXT_SECONDARY,
                     font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                     width=50).grid(row=0, column=0, padx=(T.PAD, T.PAD_SM),
                                    pady=T.PAD, sticky="w")
        self._src_var = tk.StringVar()
        self._src_menu = ctk.CTkOptionMenu(
            ctrl,
            variable=self._src_var,
            values=["Loading…"],
            command=self._on_src_changed,
            fg_color=T.BG_INPUT,
            button_color=T.ACCENT,
            button_hover_color=T.ACCENT_HOVER,
            text_color=T.TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            height=38,
        )
        self._src_menu.grid(row=0, column=1, sticky="ew", padx=(0, T.PAD_SM),
                            pady=T.PAD)

        # Arrow
        ctk.CTkLabel(ctrl, text="→",
                     text_color=T.ACCENT,
                     font=ctk.CTkFont(size=20)).grid(row=0, column=2,
                                                     padx=T.PAD_SM)

        # Destination
        ctk.CTkLabel(ctrl, text="TO",
                     text_color=T.TEXT_SECONDARY,
                     font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                     width=30).grid(row=0, column=3, padx=(T.PAD_SM, T.PAD_SM),
                                    pady=T.PAD, sticky="w")
        self._dst_var = tk.StringVar()
        self._dst_menu = ctk.CTkOptionMenu(
            ctrl,
            variable=self._dst_var,
            values=["Loading…"],
            command=self._on_dst_changed,
            fg_color=T.BG_INPUT,
            button_color=T.SUCCESS,
            button_hover_color=T.SUCCESS,
            text_color=T.TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            height=38,
        )
        self._dst_menu.grid(row=0, column=4, sticky="ew", padx=(0, T.PAD_SM),
                            pady=T.PAD)

        # Path info row
        self._src_path_lbl = ctk.CTkLabel(ctrl, text="",
                                          text_color=T.TEXT_DIM,
                                          font=ctk.CTkFont(family="Consolas",
                                                           size=11),
                                          anchor="w")
        self._src_path_lbl.grid(row=1, column=0, columnspan=3, sticky="w",
                                padx=(T.PAD, T.PAD_SM), pady=(0, T.PAD_SM))
        self._dst_path_lbl = ctk.CTkLabel(ctrl, text="",
                                          text_color=T.TEXT_DIM,
                                          font=ctk.CTkFont(family="Consolas",
                                                           size=11),
                                          anchor="w")
        self._dst_path_lbl.grid(row=1, column=3, columnspan=2, sticky="w",
                                padx=(T.PAD_SM, T.PAD), pady=(0, T.PAD_SM))

        # ── File tree + buttons ──
        mid = ctk.CTkFrame(self, fg_color="transparent")
        mid.grid(row=2, column=0, sticky="nsew", padx=T.PAD_LG)
        mid.rowconfigure(0, weight=1)
        mid.columnconfigure(0, weight=1)

        tree_wrap = ctk.CTkFrame(mid, fg_color=T.BG_CARD,
                                 corner_radius=T.CORNER_RADIUS)
        tree_wrap.grid(row=0, column=0, sticky="nsew")
        tree_wrap.rowconfigure(1, weight=1)
        tree_wrap.columnconfigure(0, weight=1)

        tree_hdr = ctk.CTkFrame(tree_wrap, fg_color="transparent")
        tree_hdr.grid(row=0, column=0, sticky="ew", padx=T.PAD, pady=(T.PAD_SM, 0))
        self._tree_lbl = ctk.CTkLabel(tree_hdr, text="Select profiles to copy",
                                      text_color=T.TEXT_SECONDARY,
                                      font=ctk.CTkFont(family="Segoe UI",
                                                       size=12, weight="bold"),
                                      anchor="w")
        self._tree_lbl.pack(side="left")
        secondary_button(tree_hdr, "All",
                         lambda: self._tree.select_all(), width=60).pack(
            side="right", padx=(T.PAD_SM, 0))
        secondary_button(tree_hdr, "None",
                         lambda: self._tree.select_none(), width=60).pack(
            side="right", padx=(T.PAD_SM, 0))

        self._tree = CheckboxFileTree(tree_wrap)
        self._tree.grid(row=1, column=0, sticky="nsew",
                        padx=T.PAD_SM, pady=T.PAD_SM)

        # ── Bottom ──
        bot = ctk.CTkFrame(self, fg_color="transparent")
        bot.grid(row=3, column=0, sticky="ew", padx=T.PAD_LG, pady=T.PAD_SM)

        self._migrate_btn = action_button(bot, "Migrate Selected",
                                          self._on_migrate,
                                          color=T.ACCENT, width=180, icon="📋")
        self._migrate_btn.pack(side="left")

        self._count_lbl = ctk.CTkLabel(bot, text="",
                                       text_color=T.TEXT_SECONDARY,
                                       font=ctk.CTkFont(family="Segoe UI",
                                                        size=12))
        self._count_lbl.pack(side="left", padx=(T.PAD, 0))

        self._log = LogPanel(self, height=110)
        self._log.grid(row=4, column=0, sticky="ew",
                       padx=T.PAD_LG, pady=(0, T.PAD_LG))

    # ─── Slicer helpers ───────────────────────────────────────────────────────

    def _get_slicer_dir(self, display_name: str) -> Path | None:
        for s in self._slicers:
            if s.display == display_name:
                dirs = s.default_profile_dirs
                return dirs[0] if dirs else None
        return None

    def _populate_menus(self) -> None:
        from ..slicers import get_default_slicers
        self._slicers = get_default_slicers()
        names = [s.display for s in self._slicers]
        if not names:
            names = ["No slicers detected"]

        self._src_menu.configure(values=names)
        self._dst_menu.configure(values=names)
        if len(names) >= 1:
            self._src_var.set(names[0])
            self._on_src_changed(names[0])
        if len(names) >= 2:
            self._dst_var.set(names[1])
            self._on_dst_changed(names[1])

    def _on_src_changed(self, value: str) -> None:
        d = self._get_slicer_dir(value)
        if d:
            self._src_path_lbl.configure(text=str(d))
            self._load_src_files(d)
        else:
            self._src_path_lbl.configure(text="(not detected)")
            self._tree.load({})

    def _on_dst_changed(self, value: str) -> None:
        d = self._get_slicer_dir(value)
        self._dst_path_lbl.configure(text=str(d) if d else "(not detected)")

    def _load_src_files(self, src_dir: Path) -> None:
        """Scan source slicer directory and populate tree."""
        groups: dict[str, list[FileTreeItem]] = {}
        if not src_dir.exists():
            self._tree.load({})
            self._tree_lbl.configure(text="Source directory not found")
            self._count_lbl.configure(text="")
            return

        total = 0
        for json_file in sorted(src_dir.rglob("*.json")):
            rel = json_file.relative_to(src_dir)
            ptype = rel.parts[0].capitalize() if rel.parts else "Other"
            item = FileTreeItem(f"  {json_file.name}", json_file,
                                tag="modified", extra={"src": json_file,
                                                       "rel": rel})
            groups.setdefault(ptype, []).append(item)
            total += 1

        self._tree.load(groups, default_checked=True)
        self._tree_lbl.configure(text=f"Source profiles  ({total} files)")
        self._count_lbl.configure(text=f"{total} / {total} selected")
        self._tree._on_select = self._on_sel_changed
        self._src_files = []

    def _on_sel_changed(self, selected) -> None:
        sel, total = self._tree.count()
        self._count_lbl.configure(text=f"{sel} / {total} selected")

    # ─── Migration ────────────────────────────────────────────────────────────

    def _on_migrate(self) -> None:
        selected = self._tree.get_selected()
        if not selected:
            show_toast(self, "Select files to migrate", "warning"); return

        src_name = self._src_var.get()
        dst_name = self._dst_var.get()
        if src_name == dst_name:
            show_toast(self, "Source and destination must be different", "warning")
            return

        dst_dir = self._get_slicer_dir(dst_name)
        if not dst_dir:
            show_toast(self, "Destination slicer path not found", "error"); return

        self._migrate_btn.configure(state="disabled", text="Migrating…")
        self._log.clear()
        self._log.append(f"Migrating {len(selected)} profile(s):\n"
                         f"  {src_name} → {dst_name}\n", "info")

        def _run():
            ok = 0
            errs = 0
            for item in selected:
                if not item.extra:
                    continue
                src_file: Path = item.extra["src"]
                rel: Path = item.extra["rel"]
                dst_file = dst_dir / rel
                try:
                    dst_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, dst_file)
                    self.after(0, lambda n=src_file.name:
                    self._log.append(f"  ✓ {n}\n", "ok"))
                    ok += 1
                except Exception as e:
                    self.after(0, lambda n=src_file.name, err=str(e):
                    self._log.append(f"  ✗ {n}: {err}\n", "error"))
                    errs += 1

            def _done():
                self._migrate_btn.configure(state="normal",
                                             text="Migrate Selected")
                if errs:
                    self._log.append(
                        f"\n⚠ Done with errors — {ok} copied, {errs} failed\n",
                        "warn")
                    show_toast(self, f"Done: {ok} copied, {errs} errors", "warning")
                else:
                    self._log.append(
                        f"\n✓ Migration complete — {ok} file(s) copied "
                        f"to {dst_name}\n", "ok")
                    show_toast(self, f"Migrated {ok} profile(s)!", "success")

            self.after(0, _done)

        threading.Thread(target=_run, daemon=True).start()

    # ─── Public ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        self._populate_menus()
