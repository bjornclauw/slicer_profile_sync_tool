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

"""Shared reusable GUI widgets."""

from __future__ import annotations

import difflib
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Callable, Optional

import customtkinter as ctk

from . import theme as T


def _blend_color(hex_color: str, alpha: float = 0.18,
                 bg: str = T.BG_INPUT) -> str:
    """
    Blend hex_color over bg at the given opacity (0-1) and return a
    solid 6-digit #RRGGBB string that Tkinter/CustomTkinter can accept.
    This replaces the broken 8-char hex-with-alpha pattern (#rrggbbAA)
    that Tkinter does not support.
    """
    def _parse(h: str):
        h = h.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    fr, fg_c, fb = _parse(hex_color)
    br, bg_g, bb = _parse(bg)
    rr = int(fr * alpha + br * (1 - alpha))
    rg = int(fg_c * alpha + bg_g * (1 - alpha))
    rb = int(fb * alpha + bb * (1 - alpha))
    return f"#{rr:02x}{rg:02x}{rb:02x}"


# ── Toast notification ─────────────────────────────────────────────────────────

class Toast:
    """Temporary overlay notification that auto-dismisses."""

    def __init__(self, parent: tk.Widget, message: str, kind: str = "info",
                 duration_ms: int = 3000) -> None:
        color = {"info": T.INFO, "success": T.SUCCESS,
                 "error": T.ERROR, "warning": T.WARNING}.get(kind, T.INFO)

        self._win = ctk.CTkToplevel(parent)
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)
        self._win.configure(fg_color=T.BG_CARD)

        frame = ctk.CTkFrame(self._win, fg_color=T.BG_CARD,
                             border_color=color, border_width=1,
                             corner_radius=T.CORNER_RADIUS)
        frame.pack(fill="both", expand=True, padx=1, pady=1)

        dot = ctk.CTkLabel(frame, text="●", text_color=color,
                           font=ctk.CTkFont(size=12))
        dot.pack(side="left", padx=(T.PAD, 4), pady=T.PAD_SM)

        lbl = ctk.CTkLabel(frame, text=message, text_color=T.TEXT_PRIMARY,
                           font=ctk.CTkFont(family="Segoe UI", size=13),
                           wraplength=320, justify="left")
        lbl.pack(side="left", padx=(0, T.PAD), pady=T.PAD_SM)

        self._win.update_idletasks()
        # Position bottom-right of parent window
        try:
            root = parent.winfo_toplevel()
            rx = root.winfo_x() + root.winfo_width() - self._win.winfo_reqwidth() - 20
            ry = root.winfo_y() + root.winfo_height() - self._win.winfo_reqheight() - 48
            self._win.geometry(f"+{rx}+{ry}")
        except Exception:
            pass

        parent.after(duration_ms, self._dismiss)

    def _dismiss(self) -> None:
        try:
            self._win.destroy()
        except Exception:
            pass


def show_toast(parent: tk.Widget, message: str, kind: str = "info",
               duration_ms: int = 3000) -> None:
    Toast(parent, message, kind, duration_ms)


# ── Spinner overlay ────────────────────────────────────────────────────────────

class SpinnerOverlay(ctk.CTkFrame):
    """Spinning indicator that overlays the parent widget."""

    _CHARS = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

    def __init__(self, parent: tk.Widget, label: str = "Working…") -> None:
        super().__init__(parent, fg_color=T.BG_DARK,
                         corner_radius=0)
        self._idx = 0
        self._running = False

        inner = ctk.CTkFrame(self, fg_color=T.BG_CARD,
                             corner_radius=T.CORNER_RADIUS)
        inner.place(relx=0.5, rely=0.5, anchor="center")

        self._spin_lbl = ctk.CTkLabel(inner, text=self._CHARS[0],
                                      text_color=T.ACCENT,
                                      font=ctk.CTkFont(size=26))
        self._spin_lbl.pack(side="left", padx=(T.PAD_LG, T.PAD_SM),
                            pady=T.PAD_LG)

        ctk.CTkLabel(inner, text=label, text_color=T.TEXT_PRIMARY,
                     font=ctk.CTkFont(family="Segoe UI", size=14)).pack(
            side="left", padx=(0, T.PAD_LG), pady=T.PAD_LG)

    def start(self) -> None:
        self._running = True
        self._tick()

    def stop(self) -> None:
        self._running = False
        try:
            self.place_forget()
        except Exception:
            pass

    def _tick(self) -> None:
        if not self._running:
            return
        self._idx = (self._idx + 1) % len(self._CHARS)
        try:
            self._spin_lbl.configure(text=self._CHARS[self._idx])
            self.after(80, self._tick)
        except Exception:
            pass


# ── Section header ─────────────────────────────────────────────────────────────

class SectionHeader(ctk.CTkLabel):
    """Bold section header label."""

    def __init__(self, parent: tk.Widget, text: str, **kwargs) -> None:
        super().__init__(parent, text=text,
                         font=ctk.CTkFont(family="Segoe UI", size=13,
                                          weight="bold"),
                         text_color=T.TEXT_SECONDARY,
                         anchor="w",
                         **kwargs)


# ── Log Panel ──────────────────────────────────────────────────────────────────

class LogPanel(ctk.CTkFrame):
    """Scrollable monospace log text area."""

    def __init__(self, parent: tk.Widget, height: int = 140, **kwargs) -> None:
        super().__init__(parent, fg_color=T.BG_INPUT,
                         corner_radius=T.CORNER_RADIUS, **kwargs)
        self._text = tk.Text(
            self,
            bg=T.BG_INPUT,
            fg=T.TEXT_SECONDARY,
            font=T.FONT_MONO,
            relief="flat",
            bd=0,
            padx=T.PAD_SM,
            pady=T.PAD_SM,
            wrap="word",
            state="disabled",
            width=1,
            height=height // 16,
            selectbackground=T.BG_HOVER,
            insertbackground=T.TEXT_PRIMARY,
        )
        scroll = ctk.CTkScrollbar(self, command=self._text.yview)
        self._text.configure(yscrollcommand=scroll.set)

        self._text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # Color tags
        self._text.tag_configure("ok",    foreground=T.SUCCESS)
        self._text.tag_configure("error", foreground=T.ERROR)
        self._text.tag_configure("warn",  foreground=T.WARNING)
        self._text.tag_configure("info",  foreground=T.INFO)
        self._text.tag_configure("dim",   foreground=T.TEXT_DIM)

    def append(self, text: str, tag: str = "") -> None:
        self._text.configure(state="normal")
        if tag:
            self._text.insert("end", text, tag)
        else:
            self._text.insert("end", text)
        self._text.see("end")
        self._text.configure(state="disabled")

    def clear(self) -> None:
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")


# ── Diff Viewer ────────────────────────────────────────────────────────────────

class DiffViewer(ctk.CTkFrame):
    """Side-by-side diff panel (read-only)."""

    CONTEXT = 4

    def __init__(self, parent: tk.Widget, **kwargs) -> None:
        super().__init__(parent, fg_color=T.BG_CARD,
                         corner_radius=T.CORNER_RADIUS, **kwargs)

        # Header row
        hdr = ctk.CTkFrame(self, fg_color=T.BG_INPUT,
                           corner_radius=T.CORNER_RADIUS)
        hdr.pack(fill="x", padx=T.PAD_SM, pady=(T.PAD_SM, 0))
        self._left_hdr = ctk.CTkLabel(hdr, text="Local",
                                      text_color=T.TEXT_SECONDARY,
                                      font=ctk.CTkFont(family="Segoe UI",
                                                       size=12, weight="bold"),
                                      anchor="w")
        self._left_hdr.pack(side="left", fill="x", expand=True,
                            padx=T.PAD_SM, pady=T.PAD_SM)
        self._right_hdr = ctk.CTkLabel(hdr, text="Server",
                                       text_color=T.TEXT_SECONDARY,
                                       font=ctk.CTkFont(family="Segoe UI",
                                                        size=12, weight="bold"),
                                       anchor="w")
        self._right_hdr.pack(side="right", fill="x", expand=True,
                             padx=T.PAD_SM, pady=T.PAD_SM)

        # Pane container
        pane = ctk.CTkFrame(self, fg_color="transparent")
        pane.pack(fill="both", expand=True,
                  padx=T.PAD_SM, pady=T.PAD_SM)
        pane.columnconfigure(0, weight=1)
        pane.columnconfigure(1, weight=1)
        pane.rowconfigure(0, weight=1)

        self._left_txt = self._make_pane(pane)
        self._left_txt.grid(row=0, column=0, sticky="nsew", padx=(0, 2))
        self._right_txt = self._make_pane(pane)
        self._right_txt.grid(row=0, column=1, sticky="nsew", padx=(2, 0))

        # Synchronize scrolling between left and right panes
        def sync_left(first, last):
            self._left_txt._sb.set(first, last)
            if not getattr(self, "_syncing", False):
                self._syncing = True
                self._right_txt.yview_moveto(first)
                self._syncing = False

        def sync_right(first, last):
            self._right_txt._sb.set(first, last)
            if not getattr(self, "_syncing", False):
                self._syncing = True
                self._left_txt.yview_moveto(first)
                self._syncing = False

        def scroll_both(*args):
            self._left_txt.yview(*args)
            self._right_txt.yview(*args)

        self._left_txt.configure(yscrollcommand=sync_left)
        self._right_txt.configure(yscrollcommand=sync_right)
        self._left_txt._sb.configure(command=scroll_both)
        self._right_txt._sb.configure(command=scroll_both)

        # Tags
        for t in (self._left_txt, self._right_txt):
            t.tag_configure("add",    background=T.DIFF_ADD_BG,
                            foreground=T.DIFF_ADD_FG)
            t.tag_configure("del",    background=T.DIFF_DEL_BG,
                            foreground=T.DIFF_DEL_FG)
            t.tag_configure("lnum",   foreground=T.TEXT_DIM)
            t.tag_configure("sep",    foreground=T.TEXT_DIM,
                            font=T.FONT_MONO_SM)
            t.tag_configure("same",   foreground=T.DIFF_SAME_FG)

    def _make_pane(self, parent: tk.Widget) -> tk.Text:
        t = tk.Text(
            parent,
            bg=T.BG_INPUT,
            fg=T.TEXT_SECONDARY,
            font=T.FONT_MONO,
            relief="flat", bd=0,
            padx=6, pady=4,
            wrap="none",
            state="disabled",
            width=1,
            height=1,
            selectbackground=T.BG_HOVER,
        )
        sb = ctk.CTkScrollbar(parent, command=t.yview)
        t.configure(yscrollcommand=sb.set)
        # Pack inside a sub-frame so scrollbar stays attached
        f = ctk.CTkFrame(parent, fg_color=T.BG_INPUT,
                         corner_radius=4)
        t.pack(in_=f, side="left", fill="both", expand=True)
        sb.pack(in_=f, side="right", fill="y")
        # Place f in the grid instead of t
        t._container = f  # type: ignore[attr-defined]
        t._sb = sb
        return t

    def load(self, left_text: str, right_text: str,
             left_label: str = "Local", right_label: str = "Server",
             show_full: bool = True) -> None:
        self._left_hdr.configure(text=left_label)
        self._right_hdr.configure(text=right_label)

        left_lines  = left_text.splitlines()
        right_lines = right_text.splitlines()
        sm = difflib.SequenceMatcher(None, left_lines, right_lines)
        opcodes = sm.get_opcodes()

        self._render(self._left_txt, self._right_txt,
                     opcodes, left_lines, right_lines, show_full)

    def _render(self, lt: tk.Text, rt: tk.Text,
                opcodes, left_lines, right_lines, show_full: bool) -> None:
        ctx = self.CONTEXT

        def _ins(widget: tk.Text, text: str, *tags) -> None:
            widget.configure(state="normal")
            widget.insert("end", text, tags)
            widget.configure(state="disabled")

        def _clear(w: tk.Text) -> None:
            w.configure(state="normal")
            w.delete("1.0", "end")
            w.configure(state="disabled")

        _clear(lt)
        _clear(rt)

        if left_lines == right_lines:
            _ins(lt, "  (files are identical)", "sep")
            _ins(rt, "  (files are identical)", "sep")
            return

        # Build row list
        rows = []  # (tag, ln, ll, rn, rl)
        ln = rn = 0
        for tag, i1, i2, j1, j2 in opcodes:
            if tag == "equal":
                for k in range(i2 - i1):
                    ln += 1; rn += 1
                    rows.append(("equal", ln, left_lines[i1+k], rn, right_lines[j1+k]))
            elif tag == "replace":
                ml = max(i2-i1, j2-j1)
                for k in range(ml):
                    cl = cr = 0; ll = rl = ""
                    if i1+k < i2: ln += 1; cl = ln; ll = left_lines[i1+k]
                    if j1+k < j2: rn += 1; cr = rn; rl = right_lines[j1+k]
                    rows.append(("replace", cl, ll, cr, rl))
            elif tag == "delete":
                for k in range(i2-i1):
                    ln += 1
                    rows.append(("delete", ln, left_lines[i1+k], 0, ""))
            elif tag == "insert":
                for k in range(j2-j1):
                    rn += 1
                    rows.append(("insert", 0, "", rn, right_lines[j1+k]))

        # Determine visible rows
        if show_full:
            visible = [True] * len(rows)
        else:
            visible = [False] * len(rows)
            for i, (t, *_) in enumerate(rows):
                if t != "equal":
                    for j in range(max(0, i-ctx), min(len(rows), i+ctx+1)):
                        visible[j] = True

        last = -1
        for i, (tag, cl, ll, cr, rl) in enumerate(rows):
            if not visible[i]:
                continue
            if last >= 0 and i - last > 1:
                _ins(lt, "   ···\n", "sep")
                _ins(rt, "   ···\n", "sep")
            last = i

            if tag == "equal":
                _ins(lt, f"{cl:4d} ", "lnum"); _ins(lt, ll + "\n", "same")
                _ins(rt, f"{cr:4d} ", "lnum"); _ins(rt, rl + "\n", "same")
            elif tag == "replace":
                if cl: _ins(lt, f"{cl:4d} ", "lnum"); _ins(lt, ll + "\n", "del")
                else:  _ins(lt, "     \n", "lnum")
                if cr: _ins(rt, f"{cr:4d} ", "lnum"); _ins(rt, rl + "\n", "add")
                else:  _ins(rt, "     \n", "lnum")
            elif tag == "delete":
                _ins(lt, f"{cl:4d} ", "lnum"); _ins(lt, ll + "\n", "del")
                _ins(rt, "     \n", "lnum")
            elif tag == "insert":
                _ins(lt, "     \n", "lnum")
                _ins(rt, f"{cr:4d} ", "lnum"); _ins(rt, rl + "\n", "add")

    def clear(self) -> None:
        for t in (self._left_txt, self._right_txt):
            t.configure(state="normal")
            t.delete("1.0", "end")
            t.configure(state="disabled")


# ── Styled button helpers ──────────────────────────────────────────────────────

def action_button(parent: tk.Widget, text: str, command: Callable,
                  color: str = T.ACCENT, width: int = 130,
                  icon: str = "") -> ctk.CTkButton:
    return ctk.CTkButton(
        parent,
        text=f"{icon}  {text}" if icon else text,
        command=command,
        fg_color=color,
        hover_color=T.ACCENT_HOVER if color == T.ACCENT else color,
        text_color=T.BG_DARK,
        font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
        corner_radius=T.CORNER_RADIUS,
        width=width,
        height=40,
    )


def secondary_button(parent: tk.Widget, text: str, command: Callable,
                     width: int = 110) -> ctk.CTkButton:
    return ctk.CTkButton(
        parent,
        text=text,
        command=command,
        fg_color=T.BG_INPUT,
        hover_color=T.BG_HOVER,
        text_color=T.TEXT_PRIMARY,
        border_color=T.BORDER,
        border_width=1,
        font=ctk.CTkFont(family="Segoe UI", size=13),
        corner_radius=T.CORNER_RADIUS,
        width=width,
        height=38,
    )


# ── File tree with checkboxes ──────────────────────────────────────────────────

class FileTreeItem:
    """Data holder for a single file entry in the tree."""

    def __init__(self, label: str, path: Optional[Path],
                 tag: str = "", extra: object = None) -> None:
        self.label = label
        self.path = path
        self.tag = tag        # "new" | "modified" | "deleted" | "same"
        self.extra = extra    # arbitrary payload for callers
        self.var = tk.BooleanVar(value=True)


class CheckboxFileTree(ctk.CTkScrollableFrame):
    """
    A scrollable, checkbox-based file list grouped by headers.
    Groups are plain labels; files are CTkCheckBox rows.
    """

    def __init__(self, parent: tk.Widget, on_select: Optional[Callable] = None,
                 on_click: Optional[Callable] = None, **kwargs) -> None:
        super().__init__(parent, fg_color=T.BG_INPUT,
                         corner_radius=T.CORNER_RADIUS,
                         scrollbar_button_color=T.BG_HOVER,
                         **kwargs)
        self._on_select = on_select  # called when a checkbox changes
        self._on_click  = on_click   # called when a row is clicked (for diff)
        self._items: list[FileTreeItem] = []
        self._rows: list[ctk.CTkFrame] = []
        self._selected_row: Optional[int] = None

    def load(self, groups: dict[str, list[FileTreeItem]],
             default_checked: bool = True) -> None:
        """Load grouped items. groups = {group_name: [FileTreeItem, ...]}"""
        # Clear existing
        for w in self.winfo_children():
            w.destroy()
        self._items = []
        self._rows = []
        self._selected_row = None

        for group_name, items in groups.items():
            if not items:
                continue
            # Group header
            hdr = ctk.CTkLabel(self, text=f"  {group_name}",
                               text_color=T.TEXT_SECONDARY,
                               font=ctk.CTkFont(family="Segoe UI", size=12,
                                                weight="bold"),
                               fg_color="transparent",
                               anchor="w")
            hdr.pack(fill="x", pady=(T.PAD_SM, 2), padx=4)

            for item in items:
                item.var.set(default_checked)
                row_idx = len(self._items)
                self._items.append(item)

                row = ctk.CTkFrame(self, fg_color="transparent",
                                   corner_radius=4)
                row.pack(fill="x", padx=4, pady=1)
                self._rows.append(row)

                tag_color = {
                    "new":      T.SUCCESS,
                    "modified": T.WARNING,
                    "deleted":  T.ERROR,
                    "same":     T.TEXT_DIM,
                }.get(item.tag, T.TEXT_PRIMARY)

                cb = ctk.CTkCheckBox(
                    row,
                    text="",
                    width=16,
                    variable=item.var,
                    command=self._on_change,
                    checkbox_width=16,
                    checkbox_height=16,
                    corner_radius=3,
                    fg_color=T.ACCENT,
                    hover_color=T.ACCENT_HOVER,
                )
                cb.pack(side="left", padx=(T.PAD_SM, 4), pady=2)

                lbl = ctk.CTkLabel(
                    row,
                    text=item.label,
                    text_color=tag_color,
                    font=ctk.CTkFont(family="Segoe UI", size=12),
                )
                lbl.pack(side="left", padx=(0, 4), pady=2)

                # Tag badge
                if item.tag in ("new", "deleted", "modified"):
                    badge_text = {"new": "NEW", "deleted": "DEL",
                                  "modified": "MOD"}.get(item.tag, "")
                    badge_bg = _blend_color(tag_color, alpha=0.22)
                    badge = ctk.CTkLabel(row, text=badge_text,
                                        fg_color=badge_bg,
                                        text_color=tag_color,
                                        corner_radius=3,
                                        font=ctk.CTkFont(family="Segoe UI",
                                                         size=10, weight="bold"),
                                        width=32, height=16)
                    badge.pack(side="left", padx=(0, 4))

                # Click to select row (for diff)
                if self._on_click:
                    _ri = row_idx
                    row.bind("<Button-1>", lambda e, i=_ri: self._row_clicked(i))
                    lbl.bind("<Button-1>", lambda e, i=_ri: self._row_clicked(i))

    def _on_change(self) -> None:
        if self._on_select:
            self._on_select(self.get_selected())

    def _row_clicked(self, idx: int) -> None:
        # Highlight selected row
        if self._selected_row is not None and self._selected_row < len(self._rows):
            self._rows[self._selected_row].configure(fg_color="transparent")
        if idx < len(self._rows):
            self._rows[idx].configure(fg_color=T.BG_HOVER)
        self._selected_row = idx
        if self._on_click and idx < len(self._items):
            self._on_click(self._items[idx])

    def get_selected(self) -> list[FileTreeItem]:
        return [item for item in self._items if item.var.get()]

    def select_all(self) -> None:
        for item in self._items:
            item.var.set(True)
        self._on_change()

    def select_none(self) -> None:
        for item in self._items:
            item.var.set(False)
        self._on_change()

    def invert(self) -> None:
        for item in self._items:
            item.var.set(not item.var.get())
        self._on_change()

    def count(self) -> tuple[int, int]:
        """Return (selected, total)."""
        total = len(self._items)
        sel = sum(1 for i in self._items if i.var.get())
        return sel, total
