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

"""Shared design tokens for the GUI."""

# ── Color Palette ─────────────────────────────────────────────────────────────
# Dark mode (default)
BG_DARK        = "#0f1117"   # Deepest background (sidebar)
BG_CARD        = "#171b26"   # Card / content area background
BG_INPUT       = "#1e2332"   # Input fields / tree rows
BG_HOVER       = "#252c3e"   # Hover state
BORDER         = "#2a3147"   # Subtle borders

ACCENT         = "#4f8ef7"   # Primary blue accent
ACCENT_HOVER   = "#6aa3ff"
ACCENT_DIM     = "#2d5ab3"

SUCCESS        = "#2ecc7a"
WARNING        = "#f5a623"
ERROR          = "#e85d5d"
INFO           = "#56d4ea"

TEXT_PRIMARY   = "#e8ecf4"
TEXT_SECONDARY = "#8a95b0"
TEXT_DIM       = "#4d566e"

# Tag / badge colors per slicer
SLICER_COLORS = {
    "orcaslicer":      "#56d4ea",   # cyan
    "bambustudio":     "#4f8ef7",   # blue
    "bambustudiobeta": "#8f6cf7",   # purple
    "snapmakerorca":   "#2ecc7a",   # green
    "crealityprint":   "#f5a623",   # amber
    "elegooslicer":    "#e85d5d",   # red
}

# Diff viewer
DIFF_ADD_BG    = "#1a3a2a"
DIFF_DEL_BG    = "#3a1a1a"
DIFF_ADD_FG    = "#4caf50"
DIFF_DEL_FG    = "#f44336"
DIFF_SAME_FG   = "#8a95b0"

# Fonts
FONT_UI        = ("Segoe UI", 10)
FONT_UI_BOLD   = ("Segoe UI", 10, "bold")
FONT_HEADING   = ("Segoe UI", 12, "bold")
FONT_TITLE     = ("Segoe UI", 16, "bold")
FONT_MONO      = ("Consolas", 9)
FONT_MONO_SM   = ("Consolas", 8)

# Geometry
SIDEBAR_W      = 200
CORNER_RADIUS  = 8
PAD            = 12
PAD_SM         = 6
PAD_LG         = 20
