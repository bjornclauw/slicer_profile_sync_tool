#!/usr/bin/env python3
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

"""
profilesync GUI — native Windows desktop launcher.

Double-click this file (or run `python profilesync_gui.py`) to open the
ProfileSync graphical interface. The original CLI (profilesync.py) is
unaffected and continues to work exactly as before.
"""

import sys


def main() -> None:
    # Friendly error if dependencies are missing
    try:
        import customtkinter  # noqa: F401
    except ImportError:
        print(
            "Missing GUI dependency: customtkinter\n"
            "Install it with:  pip install customtkinter Pillow\n"
            "Or:               pip install -r requirements.txt"
        )
        sys.exit(1)

    from profilesync.gui.app import App
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
