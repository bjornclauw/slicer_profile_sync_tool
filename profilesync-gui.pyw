"""
GUI Launcher for ProfileSync (Windows)
Runs the application without opening a command prompt window.
"""
import os
import sys
from pathlib import Path

# Ensure the application can find the profilesync package
root_dir = Path(__file__).parent.resolve()
sys.path.insert(0, str(root_dir))
os.chdir(root_dir)

try:
    from profilesync.gui.app import App
    
    if __name__ == "__main__":
        app = App()
        app.mainloop()
except Exception as e:
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("ProfileSync Startup Error", f"Could not start the application:\n\n{e}")