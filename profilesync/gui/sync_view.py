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

"""Sync view — Push / Pull / Full Sync with file tree and diff viewer."""

from __future__ import annotations

import os
import subprocess
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path

import customtkinter as ctk

from . import theme as T
from .widgets import (
    CheckboxFileTree,
    DiffViewer,
    FileTreeItem,
    LogPanel,
    action_button,
    secondary_button,
    show_toast,
)
from ..sync import SLICER_DISPLAY_NAMES


class SyncView(ctk.CTkFrame):
    """
    Main sync screen: Push / Pull / Full Sync / Refresh.
    Left panel: file tree with checkboxes.
    Right panel: side-by-side diff viewer.
    Bottom: operation log.
    """

    def __init__(self, parent: tk.Widget, app_ref) -> None:
        super().__init__(parent, fg_color="transparent")
        self._app = app_ref
        self._cfg = None
        self._exported: list[tuple[Path, Path]] = []
        self._server_profiles: list[dict] = []
        self._mode = "push"   # "push" | "pull"
        self._busy = False
        self._current_file_path: Path | None = None
        self._build_ui()

    # ─── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        # ── Title + status bar ──
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=T.PAD_LG, pady=(T.PAD_LG, 4))
        top.columnconfigure(1, weight=1)

        ctk.CTkLabel(top, text="🔄  Sync",
                     text_color=T.TEXT_PRIMARY,
                     font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
                     anchor="w").grid(row=0, column=0, sticky="w")

        # Status capsule
        status_f = ctk.CTkFrame(top, fg_color=T.BG_INPUT,
                                corner_radius=T.CORNER_RADIUS)
        status_f.grid(row=0, column=1, sticky="e")
        self._status_dot = ctk.CTkLabel(status_f, text="●",
                                        text_color=T.TEXT_DIM,
                                        font=ctk.CTkFont(size=12))
        self._status_dot.pack(side="left", padx=(T.PAD_SM, 4), pady=T.PAD_SM)
        self._status_lbl = ctk.CTkLabel(status_f, text="Not configured",
                                        text_color=T.TEXT_SECONDARY,
                                        font=ctk.CTkFont(family="Segoe UI",
                                                         size=12))
        self._status_lbl.pack(side="left", padx=(0, T.PAD_SM), pady=T.PAD_SM)

        # ── Action buttons ──
        btn_f = ctk.CTkFrame(self, fg_color="transparent")
        btn_f.grid(row=1, column=0, sticky="ew", padx=T.PAD_LG, pady=(0, T.PAD_SM))
        btn_f.columnconfigure((0, 1, 2, 3), weight=1)
        btn_f.columnconfigure(4, weight=10) # absorb extra space

        self._push_btn = action_button(btn_f, "Push", self._on_push,
                                       color=T.ACCENT, width=110, icon="↑")
        self._push_btn.grid(row=0, column=0, sticky="ew", padx=(0, T.PAD_SM))

        self._pull_btn = action_button(btn_f, "Pull", self._on_pull,
                                       color=T.SUCCESS, width=110, icon="↓")
        self._pull_btn.grid(row=0, column=1, sticky="ew", padx=(0, T.PAD_SM))

        self._full_btn = action_button(btn_f, "Full Sync", self._on_full_sync,
                                       color="#7b61ff", width=130, icon="⟳")
        self._full_btn.grid(row=0, column=2, sticky="ew", padx=(0, T.PAD_SM))

        self._refresh_btn = secondary_button(btn_f, "⟳  Refresh",
                                             self._on_refresh, width=110)
        self._refresh_btn.grid(row=0, column=3, sticky="ew", padx=(0, T.PAD_SM))



        # ── Main split: tree (left) + diff (right) ──
        split = ctk.CTkFrame(self, fg_color="transparent")
        split.grid(row=2, column=0, sticky="nsew",
                   padx=T.PAD_LG, pady=(0, T.PAD_SM))
        split.rowconfigure(0, weight=1)
        split.columnconfigure(0, weight=2)
        split.columnconfigure(1, weight=3)
        self.rowconfigure(2, weight=1)

        # File tree
        tree_wrap = ctk.CTkFrame(split, fg_color=T.BG_CARD,
                                 corner_radius=T.CORNER_RADIUS)
        tree_wrap.grid(row=0, column=0, sticky="nsew", padx=(0, T.PAD_SM))
        tree_wrap.rowconfigure(1, weight=1)
        tree_wrap.columnconfigure(0, weight=1)
        tree_hdr = ctk.CTkFrame(tree_wrap, fg_color="transparent")
        tree_hdr.grid(row=0, column=0, sticky="ew", padx=T.PAD, pady=(T.PAD_SM, 0))
        self._tree_title = ctk.CTkLabel(tree_hdr, text="Files",
                                        text_color=T.TEXT_SECONDARY,
                                        font=ctk.CTkFont(family="Segoe UI",
                                                         size=12, weight="bold"),
                                        anchor="w")
        self._tree_title.pack(side="left")

        # Select buttons and count
        self._sel_all_btn = secondary_button(tree_hdr, "All",
                                             lambda: self._tree.select_all(), width=40)
        self._sel_none_btn = secondary_button(tree_hdr, "None",
                                              lambda: self._tree.select_none(), width=40)
        self._sel_inv_btn = secondary_button(tree_hdr, "Invert",
                                             lambda: self._tree.invert(), width=48)
        self._sel_inv_btn.pack(side="right", padx=(T.PAD_SM, 0))
        self._sel_none_btn.pack(side="right", padx=(T.PAD_SM, 0))
        self._sel_all_btn.pack(side="right", padx=(T.PAD_SM, 0))

        self._count_lbl = ctk.CTkLabel(tree_hdr, text="",
                                       text_color=T.TEXT_SECONDARY,
                                       font=ctk.CTkFont(family="Segoe UI", size=11))
        self._count_lbl.pack(side="right", padx=(0, T.PAD))
        self._tree = CheckboxFileTree(
            tree_wrap,
            on_select=self._on_selection_changed,
            on_click=self._on_file_click,
        )
        self._tree.grid(row=1, column=0, sticky="nsew",
                        padx=T.PAD_SM, pady=T.PAD_SM)

        # Diff viewer
        diff_wrap = ctk.CTkFrame(split, fg_color=T.BG_CARD,
                                 corner_radius=T.CORNER_RADIUS)
        diff_wrap.grid(row=0, column=1, sticky="nsew")
        diff_wrap.rowconfigure(1, weight=1)
        diff_wrap.columnconfigure(0, weight=1)

        diff_hdr = ctk.CTkFrame(diff_wrap, fg_color="transparent")
        diff_hdr.grid(row=0, column=0, sticky="ew",
                      padx=T.PAD, pady=(T.PAD_SM, 0))
        self._diff_title = ctk.CTkLabel(diff_hdr, text="Diff",
                                        text_color=T.TEXT_SECONDARY,
                                        font=ctk.CTkFont(family="Segoe UI",
                                                         size=12, weight="bold"),
                                        anchor="w")
        self._diff_title.pack(side="left")
        self._open_file_btn = secondary_button(diff_hdr, "Open File",
                                               self._on_open_file,
                                               width=80)
        self._open_file_btn.pack(side="right")

        self._diff = DiffViewer(diff_wrap)
        self._diff.grid(row=1, column=0, sticky="nsew",
                        padx=T.PAD_SM, pady=T.PAD_SM)

        # ── Log panel ──
        self._log = LogPanel(self, height=110)
        self._log.grid(row=3, column=0, sticky="ew",
                       padx=T.PAD_LG, pady=(0, T.PAD_LG))

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _set_busy(self, busy: bool, label: str = "") -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        for btn in (self._push_btn, self._pull_btn,
                    self._full_btn, self._refresh_btn):
            btn.configure(state=state)

    def _log_line(self, text: str, tag: str = "") -> None:
        self.after(0, lambda: self._log.append(text, tag))

    def _update_status(self, text: str, color: str = T.TEXT_SECONDARY,
                       dot: str = T.TEXT_DIM) -> None:
        def _go():
            self._status_lbl.configure(text=text, text_color=color)
            self._status_dot.configure(text_color=dot)
        self.after(0, _go)

    def _build_push_tree(self) -> None:
        """Populate file tree with exported (local changes to push)."""
        from ..git import REPO_PROFILES_DIR
        cfg = self._cfg
        if not cfg:
            return

        # Reset selection state and clear diff viewer
        self._current_file_path = None
        self._diff.clear()
        self._diff_title.configure(text="Diff")

        # Find committed files
        from ..git import run as git_run
        result = git_run(
            ["git", "ls-tree", "-r", "--name-only", "HEAD", "--",
             str(REPO_PROFILES_DIR)],
            cwd=cfg.repo_dir, check=False,
        )
        committed = set(result.stdout.splitlines()) if result.returncode == 0 else set()

        groups: dict[str, list[FileTreeItem]] = {}
        for src, dst in self._exported:
            try:
                rel = dst.relative_to(cfg.repo_dir / REPO_PROFILES_DIR)
                slicer_key = rel.parts[0]
                disp = SLICER_DISPLAY_NAMES.get(slicer_key, slicer_key.capitalize())
                try:
                    rel_slicer = dst.relative_to(
                        cfg.repo_dir / REPO_PROFILES_DIR / slicer_key)
                    ptype = rel_slicer.parts[0].capitalize() if rel_slicer.parts else "Other"
                except ValueError:
                    ptype = "Other"
                group_name = f"{disp}  ›  {ptype}"
            except ValueError:
                group_name = "Other"
                slicer_key = "other"

            try:
                rel_repo = str(dst.relative_to(cfg.repo_dir))
            except ValueError:
                rel_repo = ""

            if src is None:
                tag, lbl = "deleted", f"🗑  {dst.name}"
            elif rel_repo not in committed:
                tag, lbl = "new", f"✦  {dst.name}"
            else:
                tag, lbl = "modified", f"✎  {dst.name}"

            item = FileTreeItem(lbl, dst, tag=tag, extra=(src, dst))
            groups.setdefault(group_name, []).append(item)

        self._tree.load(groups, default_checked=True)
        sel, total = self._tree.count()
        self._count_lbl.configure(text=f"{sel} / {total} selected")
        self._tree_title.configure(text=f"Local Changes  ({total} files)")
        self._mode = "push"
        
        # Ensure the push button is restored from 'Import' mode if user manually refreshed
        self._push_btn.configure(text="↑  Push", fg_color=T.ACCENT,
                                 command=self._on_push)

    def _build_pull_tree(self, profiles: list[dict]) -> None:
        """Populate file tree with server profiles to pull."""
        self._server_profiles = profiles

        # Reset selection state and clear diff viewer
        self._current_file_path = None
        self._diff.clear()
        self._diff_title.configure(text="Diff")

        groups: dict[str, list[FileTreeItem]] = {}
        for p in profiles:
            disp = SLICER_DISPLAY_NAMES.get(p["slicer_key"],
                                             p["slicer_key"].capitalize())
            group_name = f"{disp}  ›  {p['profile_type']}"
            if p["matches_local"]:
                tag, lbl = "same", f"  {p['filename']}"
            elif p["local_path"] and p["local_path"].exists():
                tag, lbl = "modified", f"✎  {p['filename']}"
            else:
                tag, lbl = "new", f"✦  {p['filename']}"

            item = FileTreeItem(lbl, p["repo_path"], tag=tag, extra=p)
            groups.setdefault(group_name, []).append(item)

        # Only pre-check changed / new files
        self._tree.load(groups, default_checked=False)
        for item in self._tree._items:
            if item.tag in ("new", "modified"):
                item.var.set(True)

        sel, total = self._tree.count()
        self._count_lbl.configure(text=f"{sel} / {total} selected")
        self._tree_title.configure(text=f"Server Profiles  ({total} files)")
        self._mode = "pull"

    def _on_selection_changed(self, selected) -> None:
        sel, total = self._tree.count()
        self._count_lbl.configure(text=f"{sel} / {total} selected")

    def _on_file_click(self, item: FileTreeItem) -> None:
        """Show diff for the clicked file."""
        cfg = self._cfg
        if not cfg:
            return

        if self._mode == "push":
            if item.extra is None:
                return
            src, dst = item.extra
            self._current_file_path = src
            if src is None:
                self._diff.clear()
                self._diff_title.configure(text="File was deleted")
                return
            try:
                new_text = src.read_text(encoding="utf-8", errors="replace")
            except OSError:
                new_text = ""
            from ..git import run as git_run, REPO_PROFILES_DIR
            try:
                rel = dst.relative_to(cfg.repo_dir)
                result = git_run(
                    ["git", "show", f"HEAD:{rel.as_posix()}"],
                    cwd=cfg.repo_dir, check=False)
                old_text = result.stdout if result.returncode == 0 else ""
            except Exception:
                old_text = ""
            self._diff.load(old_text, new_text, "Server (current)", "Local (new)")
            self._diff_title.configure(text=f"Diff — {dst.name}")

        elif self._mode == "pull":
            p = item.extra
            if not p:
                return
            self._current_file_path = p.get("local_path")
            try:
                server_text = p["repo_path"].read_text(encoding="utf-8",
                                                        errors="replace")
            except OSError:
                server_text = ""
            local_path = p.get("local_path")
            try:
                local_text = (local_path.read_text(encoding="utf-8",
                                                    errors="replace")
                              if local_path and local_path.exists() else "")
            except OSError:
                local_text = ""
            self._diff.load(local_text, server_text, "Local (current)", "Server (incoming)")
            self._diff_title.configure(text=f"Diff — {p['filename']}")

    def _on_open_file(self) -> None:
        if not self._current_file_path or not self._current_file_path.exists():
            show_toast(self, "No file selected or file missing", "warning")
            return
        cfg = self._cfg
        if not cfg or not cfg.editor_cmd:
            show_toast(self, "Editor not configured in Settings", "warning")
            return
        try:
            creationflags = 0
            if os.name == "nt":
                creationflags = subprocess.CREATE_NO_WINDOW
            cmd_str = f'{cfg.editor_cmd} "{self._current_file_path}"'
            subprocess.Popen(cmd_str, shell=True, creationflags=creationflags)
        except Exception as e:
            show_toast(self, f"Could not launch editor: {e}", "error")

    # ─── Actions ──────────────────────────────────────────────────────────────

    def _on_push(self) -> None:
        if not self._cfg:
            show_toast(self, "Run Setup first", "warning"); return
        if not self._exported:
            show_toast(self, "Nothing to push — local profiles match server",
                       "info"); return
        selected = self._tree.get_selected()
        if not selected:
            show_toast(self, "Select files to push", "warning"); return
        selected_pairs = [item.extra for item in selected
                          if item.extra is not None]
        self._execute_push(selected_pairs)

    def _on_pull(self) -> None:
        if not self._cfg:
            show_toast(self, "Run Setup first", "warning"); return
        self._start_pull(then_push=False)

    def _on_full_sync(self) -> None:
        if not self._cfg:
            show_toast(self, "Run Setup first", "warning"); return
        if self._exported:
            # Push first, then pull
            selected = self._tree.get_selected()
            if not selected:
                selected = [item for item in self._tree._items]
            pairs = [item.extra for item in selected if item.extra is not None]
            self._execute_push(pairs, then_pull=True)
        else:
            self._start_pull(then_push=False)

    def _on_refresh(self) -> None:
        if not self._cfg:
            show_toast(self, "Run Setup first", "warning"); return
        self._do_refresh()

    # ─── Background workers ───────────────────────────────────────────────────

    def _do_refresh(self) -> None:
        self._set_busy(True)
        self._log.clear()
        self._log_line("Refreshing…\n", "info")
        self._update_status("Scanning…", T.TEXT_SECONDARY, T.WARNING)

        def _run():
            try:
                from ..git import (
                    clone_or_open_repo, git_has_commits,
                    initialize_empty_repo, run as git_run,
                )
                from ..sync import export_from_slicers_to_repo, rebuild_exported_from_git
                cfg = self._cfg
                clone_or_open_repo(cfg.repo_dir, cfg.github_remote)
                if not git_has_commits(cfg.repo_dir):
                    initialize_empty_repo(cfg.repo_dir, cfg.github_remote)

                git_run(["git", "fetch", "origin"], cwd=cfg.repo_dir, check=False)
                export_from_slicers_to_repo(cfg)
                self._exported = rebuild_exported_from_git(cfg)

                self.after(0, self._after_refresh)
            except Exception as e:
                self._log_line(f"\n✗ Error: {e}\n", "error")
                self.after(0, lambda: self._set_busy(False))
                self.after(0, lambda: self._update_status(
                    "Error during refresh", T.ERROR, T.ERROR))

        threading.Thread(target=_run, daemon=True).start()

    def _after_refresh(self) -> None:
        self._set_busy(False)
        n = len(self._exported)
        if n:
            self._update_status(f"{n} file(s) differ", T.WARNING, T.WARNING)
            self._log.append(f"✓ Refresh done — {n} local change(s) detected\n", "ok")
        else:
            self._update_status("All synced ✓", T.SUCCESS, T.SUCCESS)
            self._log.append("✓ Refresh done — local profiles match server\n", "ok")
        self._build_push_tree()

    def _execute_push(self, selected_pairs: list, then_pull: bool = False) -> None:
        self._set_busy(True)
        self._log.clear()
        self._log_line("Preparing push…\n", "info")

        def _run():
            try:
                from ..git import (
                    git_commit_if_needed, git_has_commits, git_has_conflicts,
                    git_pull_rebase, git_push, get_computer_id, run as git_run,
                )
                from ..sync import export_selected_to_repo, export_from_slicers_to_repo, rebuild_exported_from_git
                cfg = self._cfg

                all_exported = self._exported
                if len(selected_pairs) < len(all_exported):
                    if git_has_commits(cfg.repo_dir):
                        git_run(["git", "checkout", "HEAD", "--", "."],
                                cwd=cfg.repo_dir, check=False)
                    git_run(["git", "clean", "-fd"], cwd=cfg.repo_dir, check=False)
                    export_selected_to_repo(cfg, selected_pairs)

                self._log_line("Committing…\n", "info")
                git_commit_if_needed(cfg.repo_dir, get_computer_id())

                # Check if push needed
                needs_push = False
                if git_has_commits(cfg.repo_dir):
                    r1 = git_run(["git", "rev-parse", "HEAD"],
                                 cwd=cfg.repo_dir, check=False)
                    r2 = git_run(["git", "rev-parse", "origin/main"],
                                 cwd=cfg.repo_dir, check=False)
                    if r2.returncode != 0 or r1.stdout.strip() != r2.stdout.strip():
                        needs_push = True

                if not needs_push:
                    self._log_line("✓ Already synced to server\n", "ok")
                    self.after(0, lambda: self._after_push_ok(then_pull))
                    return

                self._log_line("Syncing with server (fetch + rebase)…\n", "info")
                try:
                    git_pull_rebase(cfg.repo_dir)
                except subprocess.CalledProcessError:
                    if git_has_conflicts(cfg.repo_dir):
                        git_run(["git", "rebase", "--abort"],
                                cwd=cfg.repo_dir, check=False)
                        self._log_line("⚠ Conflicts detected — opening editor…\n",
                                       "warn")
                        self._open_conflict_editor()
                    else:
                        self._log_line("✗ Error syncing with server\n", "error")
                    self.after(0, lambda: self._set_busy(False))
                    return

                self._log_line("Pushing to server…\n", "info")
                r = git_run(
                    ["git", "rev-parse", "--abbrev-ref",
                     "--symbolic-full-name", "@{u}"],
                    cwd=cfg.repo_dir, check=False)
                if r.returncode != 0:
                    pr = git_run(["git", "push", "-u", "origin", "main"],
                                 cwd=cfg.repo_dir, check=False)
                    if pr.returncode != 0:
                        branch = git_run(
                            ["git", "branch", "--show-current"],
                            cwd=cfg.repo_dir, check=False).stdout.strip() or "main"
                        git_run(["git", "push", "-u", "origin", branch],
                                cwd=cfg.repo_dir)
                else:
                    git_push(cfg.repo_dir)

                n = len(selected_pairs)
                self._log_line(f"✓ Pushed {n} file(s) to server\n", "ok")

                export_from_slicers_to_repo(cfg)
                self._exported = rebuild_exported_from_git(cfg)
                self.after(0, lambda: self._after_push_ok(then_pull))

            except Exception as e:
                self._log_line(f"\n✗ Push failed: {e}\n", "error")
                self.after(0, lambda: self._set_busy(False))
                self.after(0, lambda: self._update_status("Push failed", T.ERROR, T.ERROR))

        threading.Thread(target=_run, daemon=True).start()

    def _after_push_ok(self, then_pull: bool) -> None:
        self._set_busy(False)
        n = len(self._exported)
        self._update_status("Push complete ✓", T.SUCCESS, T.SUCCESS)
        show_toast(self, "Push complete!", "success")
        self._build_push_tree()
        if then_pull:
            self._start_pull(then_push=False)

    def _start_pull(self, then_push: bool = False) -> None:
        self._set_busy(True)
        self._log.clear()
        self._log_line("Fetching from server…\n", "info")
        self._update_status("Pulling…", T.INFO, T.INFO)

        def _run():
            try:
                from ..git import (
                    git_checkout_branch, git_has_conflicts,
                    git_pull_rebase, git_status_porcelain, run as git_run,
                )
                from ..sync import collect_server_profiles
                cfg = self._cfg

                try:
                    git_checkout_branch(cfg.repo_dir, "main")
                except subprocess.CalledProcessError:
                    try:
                        git_checkout_branch(cfg.repo_dir, "master")
                    except Exception:
                        pass

                # Stash local export changes
                status = git_status_porcelain(cfg.repo_dir)
                had_stash = False
                if status.strip():
                    r = git_run(
                        ["git", "stash", "push", "-m", "profilesync-pull-temp"],
                        cwd=cfg.repo_dir, check=False)
                    had_stash = r.returncode == 0

                try:
                    git_pull_rebase(cfg.repo_dir)
                except subprocess.CalledProcessError:
                    if git_has_conflicts(cfg.repo_dir):
                        git_run(["git", "rebase", "--abort"],
                                cwd=cfg.repo_dir, check=False)
                    if had_stash:
                        git_run(["git", "stash", "pop"],
                                cwd=cfg.repo_dir, check=False)
                    self._log_line("✗ Error downloading from server\n", "error")
                    self.after(0, lambda: self._set_busy(False))
                    self.after(0, lambda: self._update_status(
                        "Pull failed", T.ERROR, T.ERROR))
                    return

                profiles = collect_server_profiles(cfg)
                self._log_line(f"✓ Fetched {len(profiles)} profiles from server\n", "ok")
                self.after(0, lambda: self._show_pull_ui(profiles, had_stash))

            except Exception as e:
                self._log_line(f"\n✗ Pull error: {e}\n", "error")
                self.after(0, lambda: self._set_busy(False))

        threading.Thread(target=_run, daemon=True).start()

    def _show_pull_ui(self, profiles: list[dict], had_stash: bool) -> None:
        self._set_busy(False)
        if not profiles:
            self._update_status("No profiles on server", T.TEXT_DIM, T.TEXT_DIM)
            show_toast(self, "No profiles found on server", "info")
            return
        self._build_pull_tree(profiles)
        self._update_status(f"{len(profiles)} server profiles", T.INFO, T.INFO)
        # Replace Push button action with "Import Selected"
        self._push_btn.configure(text="↓  Import", fg_color=T.SUCCESS,
                                 command=lambda: self._do_import(had_stash))

    def _do_import(self, had_stash: bool) -> None:
        selected = self._tree.get_selected()
        if not selected:
            show_toast(self, "Select files to import", "warning"); return
        selected_profiles = [item.extra for item in selected
                             if item.extra is not None]
        self._set_busy(True)
        self._log_line("Importing selected profiles…\n", "info")

        def _run():
            try:
                from ..sync import import_selected_profiles
                from ..git import run as git_run
                cfg = self._cfg
                copied = import_selected_profiles(cfg, selected_profiles)
                if had_stash:
                    git_run(["git", "stash", "pop"], cwd=cfg.repo_dir, check=False)
                n = len(copied)
                self._log_line(f"✓ Imported {n} profile(s) to slicer folders\n", "ok")
                self.after(0, lambda: self._after_import())
            except Exception as e:
                self._log_line(f"\n✗ Import failed: {e}\n", "error")
                self.after(0, lambda: self._set_busy(False))

        threading.Thread(target=_run, daemon=True).start()

    def _after_import(self) -> None:
        self._set_busy(False)
        self._update_status("Import complete ✓", T.SUCCESS, T.SUCCESS)
        show_toast(self, "Profiles imported!", "success")
        # Reset push button
        self._push_btn.configure(text="↑  Push", fg_color=T.ACCENT,
                                 command=self._on_push)
        self._do_refresh()

    def _open_conflict_editor(self) -> None:
        """Launch the configured editor for conflict resolution (same as CLI)."""
        cfg = self._cfg
        if not cfg or not cfg.editor_cmd:
            self._log_line("⚠ No editor configured — resolve conflicts manually\n", "warn")
            return
        from ..git import git_get_conflicted_files
        conflicted = git_get_conflicted_files(cfg.repo_dir)
        for f in conflicted:
            self._log_line(f"  Opening {f.name} in editor…\n", "info")
            try:
                import shlex
                cmd = shlex.split(cfg.editor_cmd) + [str(f)]
                subprocess.run(cmd, check=False)
            except Exception as e:
                self._log_line(f"  ✗ Could not open editor: {e}\n", "error")

    # ─── Public ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Called when this tab becomes active."""
        try:
            from ..config import Config
            self._cfg = Config.load()
            self._do_refresh()
        except FileNotFoundError:
            self._update_status("Not configured — run Setup first",
                                T.WARNING, T.WARNING)
            self._log.clear()
            self._log.append("⚠ No config found. Go to Setup first.\n", "warn")
        except Exception as e:
            self._update_status("Error loading config", T.ERROR, T.ERROR)
            self._log.clear()
            self._log.append(f"Error: {e}\n", "error")
