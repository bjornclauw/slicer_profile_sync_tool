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

"""Overview view — Browse all local files, compare with server, per-file push/pull."""

from __future__ import annotations

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
    action_button,
    secondary_button,
    show_toast,
    SpinnerOverlay,
)
from ..sync import (
    SLICER_DISPLAY_NAMES,
    export_selected_to_repo,
    import_selected_profiles,
)
from ..git import (
    REPO_PROFILES_DIR,
    run as git_run,
    git_commit_if_needed,
    get_computer_id,
    git_push,
    git_has_commits,
    git_pull_rebase,
)

class OverviewView(ctk.CTkFrame):
    """
    Overview screen:
    Top: summary of local vs server status.
    Left panel: file tree with all local profiles.
    Right panel: side-by-side diff viewer for the selected profile, with Push/Pull/Open actions.
    """

    def __init__(self, parent: tk.Widget, app_ref) -> None:
        super().__init__(parent, fg_color="transparent")
        self._app = app_ref
        self._cfg = None
        self._all_groups: dict[str, list[FileTreeItem]] = {}
        self._current_file_item: FileTreeItem | None = None
        self._busy = False
        self._build_ui()
        self._spinner = SpinnerOverlay(self)

    # ─── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        # ── Title + summary bar ──
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=T.PAD_LG, pady=(T.PAD_LG, 4))
        top.columnconfigure(1, weight=1)

        ctk.CTkLabel(top, text="📊  Overview",
                     text_color=T.TEXT_PRIMARY,
                     font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
                     anchor="w").grid(row=0, column=0, sticky="w")

        # Summary box
        self._summary_frame = ctk.CTkFrame(top, fg_color=T.BG_INPUT,
                                           corner_radius=T.CORNER_RADIUS)
        self._summary_frame.grid(row=0, column=1, sticky="e", padx=(T.PAD_LG, 0))
        self._summary_lbl = ctk.CTkLabel(self._summary_frame, text="Loading summary...",
                                         text_color=T.TEXT_SECONDARY,
                                         font=ctk.CTkFont(family="Segoe UI", size=12),
                                         justify="left", anchor="w")
        self._summary_lbl.pack(padx=T.PAD, pady=T.PAD_SM)

        # ── Main split: tree (left) + diff (right) ──
        split = ctk.CTkFrame(self, fg_color="transparent")
        split.grid(row=1, column=0, sticky="nsew",
                   padx=T.PAD_LG, pady=(0, T.PAD_LG))
        split.rowconfigure(0, weight=1)
        split.columnconfigure(0, weight=2)
        split.columnconfigure(1, weight=3)

        # File tree
        tree_wrap = ctk.CTkFrame(split, fg_color=T.BG_CARD,
                                 corner_radius=T.CORNER_RADIUS)
        tree_wrap.grid(row=0, column=0, sticky="nsew", padx=(0, T.PAD_SM))
        tree_wrap.rowconfigure(1, weight=1)
        tree_wrap.columnconfigure(0, weight=1)
        tree_hdr = ctk.CTkFrame(tree_wrap, fg_color="transparent")
        tree_hdr.grid(row=0, column=0, sticky="ew", padx=T.PAD, pady=(T.PAD_SM, 0))
        self._tree_title = ctk.CTkLabel(tree_hdr, text="Local Profiles",
                                        text_color=T.TEXT_SECONDARY,
                                        font=ctk.CTkFont(family="Segoe UI",
                                                         size=12, weight="bold"),
                                        anchor="w")
        self._tree_title.pack(side="left")

        self._slicer_filter_var = ctk.StringVar(value="All Slicers")
        self._slicer_filter = ctk.CTkOptionMenu(
            tree_hdr,
            values=["All Slicers"],
            variable=self._slicer_filter_var,
            command=self._on_filter_change,
            width=120,
            height=24,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=T.BG_INPUT,
            button_color=T.BG_INPUT,
            button_hover_color=T.BG_HOVER
        )
        self._slicer_filter.pack(side="right")

        self._tree = CheckboxFileTree(
            tree_wrap,
            on_click=self._on_file_click,
            show_checkboxes=False
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
        self._pull_file_btn = action_button(diff_hdr, "Pull File",
                                               self._on_pull_file,
                                               color=T.SUCCESS, width=90, icon="↓")
        self._pull_file_btn.pack(side="right", padx=(0, T.PAD_SM))
        self._push_file_btn = action_button(diff_hdr, "Push File",
                                               self._on_push_file,
                                               color=T.ACCENT, width=90, icon="↑")
        self._push_file_btn.pack(side="right", padx=(0, T.PAD_SM))

        self._diff = DiffViewer(diff_wrap)
        self._diff.grid(row=1, column=0, sticky="nsew",
                        padx=T.PAD_SM, pady=T.PAD_SM)
        
        self._update_button_states()

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _set_busy(self, busy: bool, label: str = "Working…") -> None:
        self._busy = busy
        if busy:
            self._spinner.start()
            self._spinner.place(relx=0.5, rely=0.5, anchor="center")
            self._push_file_btn.configure(state="disabled")
            self._pull_file_btn.configure(state="disabled")
            self._open_file_btn.configure(state="disabled")
        else:
            self._spinner.stop()
            self._update_button_states()

    def _update_button_states(self) -> None:
        if not self._current_file_item:
            self._push_file_btn.configure(state="disabled")
            self._pull_file_btn.configure(state="disabled")
            self._open_file_btn.configure(state="disabled")
            return
            
        self._open_file_btn.configure(state="normal")
        if self._current_file_item.tag != "same":
            self._push_file_btn.configure(state="normal")
            self._pull_file_btn.configure(state="normal")
        else:
            self._push_file_btn.configure(state="disabled")
            self._pull_file_btn.configure(state="disabled")

    def _update_summary(self, summary_text: str) -> None:
        self.after(0, lambda: self._summary_lbl.configure(text=summary_text))

    def _load_data(self) -> None:
        self._set_busy(True, "Loading overview…")

        def _run():
            try:
                from ..sync import export_from_slicers_to_repo, rebuild_exported_from_git, collect_server_profiles
                cfg = self._cfg
                
                # Fetch server profiles state
                git_run(["git", "fetch", "origin"], cwd=cfg.repo_dir, check=False)
                
                # We need all local files. We can get them by traversing enabled slicers.
                # Find committed files
                result = git_run(
                    ["git", "ls-tree", "-r", "--name-only", "HEAD", "--",
                     str(REPO_PROFILES_DIR)],
                    cwd=cfg.repo_dir, check=False,
                )
                committed = set(result.stdout.splitlines()) if result.returncode == 0 else set()
                
                # We also want to know which files differ from server
                export_from_slicers_to_repo(cfg)
                exported = rebuild_exported_from_git(cfg)
                exported_dst = {dst for src, dst in exported if src is not None}
                
                groups: dict[str, list[FileTreeItem]] = {}
                summary_lines = []
                
                for slicer in cfg.enabled_slicers:
                    root = cfg.repo_dir / REPO_PROFILES_DIR / slicer
                    if not root.exists():
                        continue
                    
                    files_by_type: dict[str, int] = {}
                    
                    # Also find files in the user's actual slicer directories to map src <-> dst
                    # But for simplicity, we can just use the repo's copy as dst, and map back to src.
                    from ..slicers import get_slicer_by_key
                    slicer_def = get_slicer_by_key(slicer)
                    
                    for json_file in root.rglob("*.json"):
                        dst = json_file
                        try:
                            rel = json_file.relative_to(root)
                            ptype = rel.parts[0].capitalize() if rel.parts else "Other"
                        except (ValueError, IndexError):
                            ptype = "Other"
                            
                        files_by_type[ptype] = files_by_type.get(ptype, 0) + 1
                        
                        disp = SLICER_DISPLAY_NAMES.get(slicer, slicer.capitalize())
                        group_name = f"{disp}  ›  {ptype}"
                        
                        # Find src corresponding to this dst
                        src = None
                        if slicer_def and slicer in cfg.slicer_profile_dirs and cfg.slicer_profile_dirs[slicer]:
                            local_dir = Path(cfg.slicer_profile_dirs[slicer][0])
                            # Reconstruct src path
                            src_rel = dst.relative_to(cfg.repo_dir / REPO_PROFILES_DIR / slicer)
                            # Convert back to slicer's layout if needed, though they usually match.
                            src = local_dir / src_rel
                        
                        try:
                            rel_repo = str(dst.relative_to(cfg.repo_dir))
                        except ValueError:
                            rel_repo = ""
                            
                        if dst in exported_dst:
                            tag = "new" if rel_repo not in committed else "modified"
                        else:
                            tag = "same"
                            
                        lbl = f"{dst.name}"
                        item = FileTreeItem(lbl, dst, tag=tag, extra=(src, dst))
                        groups.setdefault(group_name, []).append(item)
                
                    if files_by_type:
                        display_name = SLICER_DISPLAY_NAMES.get(slicer, slicer.capitalize())
                        total = sum(files_by_type.values())
                        type_str = "  ".join(f"{t}: {c}" for t, c in sorted(files_by_type.items()))
                        summary_lines.append(f"{display_name} ({total} files)")
                        summary_lines.append(f"  {type_str}")
                
                # Check for deleted files (in exported but dst doesn't exist locally)
                for src, dst in exported:
                    if src is None: # deleted locally
                        try:
                            rel = dst.relative_to(cfg.repo_dir / REPO_PROFILES_DIR)
                            slicer_key = rel.parts[0]
                            disp = SLICER_DISPLAY_NAMES.get(slicer_key, slicer_key.capitalize())
                            try:
                                rel_slicer = dst.relative_to(cfg.repo_dir / REPO_PROFILES_DIR / slicer_key)
                                ptype = rel_slicer.parts[0].capitalize() if rel_slicer.parts else "Other"
                            except ValueError:
                                ptype = "Other"
                            group_name = f"{disp}  ›  {ptype}"
                        except ValueError:
                            group_name = "Other"
                            slicer_key = "other"
                            
                        tag = "deleted"
                        lbl = f"🗑  {dst.name}"
                        item = FileTreeItem(lbl, dst, tag=tag, extra=(src, dst))
                        groups.setdefault(group_name, []).append(item)

                if not summary_lines:
                    summary_text = "No profiles found."
                else:
                    summary_text = "\n".join(summary_lines)
                    if exported:
                        summary_text += f"\n\n⚠ {len(exported)} file(s) differ from server"
                    else:
                        summary_text += "\n\n✓ Local profiles match server"

                slicers = ["All Slicers"] + [SLICER_DISPLAY_NAMES.get(s, s.capitalize()) for s in cfg.enabled_slicers]
                
                def _update_ui():
                    self._summary_lbl.configure(text=summary_text)
                    self._slicer_filter.configure(values=slicers)
                    if self._slicer_filter_var.get() not in slicers:
                        self._slicer_filter_var.set("All Slicers")
                    self._all_groups = groups
                    self._apply_filter()
                    self._set_busy(False)
                    
                self.after(0, _update_ui)

            except Exception as e:
                self.after(0, lambda: self._set_busy(False))
                show_toast(self, f"Error loading overview: {e}", "error")

        threading.Thread(target=_run, daemon=True).start()

    def _on_filter_change(self, value: str) -> None:
        self._apply_filter()

    def _apply_filter(self) -> None:
        selected = self._slicer_filter_var.get()
        if selected == "All Slicers":
            filtered = self._all_groups
        else:
            filtered = {k: v for k, v in self._all_groups.items() if k.startswith(selected)}
        self._tree.load(filtered, default_checked=False)

    # ─── Event handlers ───────────────────────────────────────────────────────

    def _on_file_click(self, item: FileTreeItem) -> None:
        """Show diff for the clicked file."""
        cfg = self._cfg
        if not cfg:
            return
            
        self._current_file_item = item
        self._update_button_states()
        
        if item.extra is None:
            return
            
        src, dst = item.extra
        
        if src is None:
            self._diff.clear()
            self._diff_title.configure(text=f"File deleted: {dst.name}")
            return
            
        try:
            new_text = src.read_text(encoding="utf-8", errors="replace")
        except OSError:
            new_text = ""
            
        try:
            rel = dst.relative_to(cfg.repo_dir)
            result = git_run(
                ["git", "show", f"HEAD:{rel.as_posix()}"],
                cwd=cfg.repo_dir, check=False)
            old_text = result.stdout if result.returncode == 0 else ""
        except Exception:
            old_text = ""
            
        self._diff.load(old_text, new_text, "Server (current)", "Local (new)", show_full=True)
        self._diff_title.configure(text=f"Diff — {dst.name}")

    def _on_open_file(self) -> None:
        if not self._current_file_item or not self._current_file_item.extra:
            show_toast(self, "No file selected", "warning")
            return
        src, _ = self._current_file_item.extra
        if not src or not src.exists():
            show_toast(self, "File missing or deleted locally", "warning")
            return
            
        cfg = self._cfg
        if not cfg or not cfg.editor_cmd:
            show_toast(self, "Editor not configured in Settings", "warning")
            return
            
        try:
            import subprocess
            cmd_str = f'{cfg.editor_cmd} "{src}"'
            subprocess.Popen(cmd_str, shell=True)
        except Exception as e:
            show_toast(self, f"Could not launch editor: {e}", "error")

    def _on_push_file(self) -> None:
        if not self._current_file_item or not self._current_file_item.extra:
            show_toast(self, "No file selected", "warning")
            return
        
        self._set_busy(True, "Pushing file…")
        
        def _run():
            try:
                cfg = self._cfg
                # We need a list of tuple[Path, Path] for export_selected_to_repo
                selected_pairs = [self._current_file_item.extra]
                
                # Clear uncommitted changes in repo
                if git_has_commits(cfg.repo_dir):
                    git_run(["git", "checkout", "HEAD", "--", "."],
                            cwd=cfg.repo_dir, check=False)
                git_run(["git", "clean", "-fd"], cwd=cfg.repo_dir, check=False)
                
                # Export the specific file
                export_selected_to_repo(cfg, selected_pairs)
                
                # Commit
                git_commit_if_needed(cfg.repo_dir, get_computer_id())
                
                # Push
                git_push(cfg.repo_dir)
                
                self.after(0, lambda: show_toast(self, "File pushed successfully!", "success"))
                self.after(0, self._load_data)
            except Exception as e:
                self.after(0, lambda: show_toast(self, f"Push failed: {e}", "error"))
                self.after(0, lambda: self._set_busy(False))
                
        threading.Thread(target=_run, daemon=True).start()

    def _on_pull_file(self) -> None:
        if not self._current_file_item or not self._current_file_item.extra:
            show_toast(self, "No file selected", "warning")
            return
            
        self._set_busy(True, "Pulling file…")
        
        def _run():
            try:
                cfg = self._cfg
                # Update the local repository from the server first
                git_pull_rebase(cfg.repo_dir)

                src, dst = self._current_file_item.extra
                
                # Build the profile dict format expected by import_selected_profiles
                try:
                    rel_prof = dst.relative_to(cfg.repo_dir / REPO_PROFILES_DIR)
                    slicer_key = rel_prof.parts[0]
                    rel = dst.relative_to(cfg.repo_dir / REPO_PROFILES_DIR / slicer_key)
                    profile_type = rel.parts[0].capitalize() if rel.parts else "Other"
                except ValueError:
                    slicer_key = "other"
                    profile_type = "Other"
                    rel = Path(dst.name)
                
                profile = {
                    "slicer_key": slicer_key,
                    "profile_type": profile_type,
                    "filename": dst.name,
                    "repo_path": dst,
                    "local_path": src,
                    "rel": rel
                }
                
                copied = import_selected_profiles(cfg, [profile])
                
                if copied:
                    self.after(0, lambda: show_toast(self, "File pulled and updated!", "success"))
                else:
                    self.after(0, lambda: show_toast(self, "File is already up to date.", "info"))
                self.after(0, self._load_data)
            except Exception as e:
                self.after(0, lambda: show_toast(self, f"Pull failed: {e}", "error"))
                self.after(0, lambda: self._set_busy(False))
                
        threading.Thread(target=_run, daemon=True).start()

    # ─── Public ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Called when this tab becomes active."""
        try:
            from ..config import Config
            self._cfg = Config.load()
            self._current_file_item = None
            self._diff.clear()
            self._update_button_states()
            self._load_data()
        except FileNotFoundError:
            self._update_summary("Not configured — run Setup first")
        except Exception as e:
            self._update_summary(f"Error loading config: {e}")
