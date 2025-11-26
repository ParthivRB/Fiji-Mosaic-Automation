#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import threading
import time
from pathlib import Path
import sys
import os
import json
import signal

# ---------------- CONFIGURATION ----------------
if getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(sys.executable).parent
else:
    PROJECT_ROOT = Path(__file__).parent.resolve()

MACRO_PATH = PROJECT_ROOT / "mosaic_batch.ijm"
SETTINGS_FILE = PROJECT_ROOT / "settings.json"

FIJI_CANDIDATES = [
    Path("/Applications/Fiji/fiji"),
    Path("/Applications/Fiji.app/Contents/MacOS/ImageJ-macosx"),
]

def find_fiji():
    for p in FIJI_CANDIDATES:
        if p.exists(): return p
    return None

FIJI = find_fiji()

# ---------------- GUI CLASS ----------------
class MosaicApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mosaic Automation 2.0")
        self.geometry("700x550")
        
        self.settings = self._load_settings()
        last_folder = self.settings.get("last_folder", "")
        
        self.folder_path = tk.StringVar(value=last_folder)
        self.status_var = tk.StringVar(value="Ready")
        self.is_running = False
        self.stop_event = threading.Event()
        
        self._ui()
        
        if last_folder:
            self.after(500, lambda: self._scan_folder(Path(last_folder)))
        
        if not FIJI:
            messagebox.showwarning("Fiji Missing", "Could not find Fiji in /Applications.")

    def _load_settings(self):
        if SETTINGS_FILE.exists():
            try: return json.loads(SETTINGS_FILE.read_text())
            except: return {}
        return {}

    def _save_setting(self, key, value):
        self.settings[key] = value
        try: SETTINGS_FILE.write_text(json.dumps(self.settings, indent=2))
        except: pass

    def _ui(self):
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill="both", expand=True)

        # Input
        input_frame = ttk.LabelFrame(main_frame, text="Target Folder", padding="10")
        input_frame.pack(fill="x", pady=(0, 15))
        ttk.Entry(input_frame, textvariable=self.folder_path).pack(side="left", fill="x", expand=True, padx=(0, 10))
        ttk.Button(input_frame, text="Browse...", command=self._browse).pack(side="right")

        # Progress
        prog_frame = ttk.LabelFrame(main_frame, text="Progress", padding="10")
        prog_frame.pack(fill="x", pady=(0, 15))
        self.progress = ttk.Progressbar(prog_frame, orient="horizontal", length=100, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 5))
        self.lbl_status = ttk.Label(prog_frame, textvariable=self.status_var, foreground="gray")
        self.lbl_status.pack(anchor="w")

        # Controls
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=10)
        self.btn_run = ttk.Button(btn_frame, text="RUN BATCH", command=self._start_run)
        self.btn_run.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.btn_stop = ttk.Button(btn_frame, text="STOP", command=self._stop_run, state="disabled")
        self.btn_stop.pack(side="right", fill="x", expand=True, padx=(5, 0))

        # Log
        log_lbl = ttk.Label(main_frame, text="Status Log:")
        log_lbl.pack(anchor="w")
        log_frame = ttk.Frame(main_frame)
        log_frame.pack(fill="both", expand=True, pady=(5, 0))
        scrollbar = ttk.Scrollbar(log_frame)
        scrollbar.pack(side="right", fill="y")
        self.log_text = tk.Text(log_frame, height=10, state="disabled", font=("Menlo", 12), yscrollcommand=scrollbar.set)
        self.log_text.pack(fill="both", expand=True)
        scrollbar.config(command=self.log_text.yview)

    def _browse(self):
        start_dir = self.folder_path.get() if os.path.exists(self.folder_path.get()) else "/"
        p = filedialog.askdirectory(initialdir=start_dir)
        if p:
            self.folder_path.set(p)
            self._save_setting("last_folder", p)
            self._scan_folder(Path(p))

    def _scan_folder(self, folder):
        if not folder.exists(): return
        oirs = list(folder.rglob("*.oir"))
        csvs = list(folder.rglob("*.csv"))
        self.status_var.set(f"Found {len(oirs)} .oir files ({len(csvs)} already processed).")
        self._log(f"📂 Ready: {len(oirs)} files found.")

    def _log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"{msg}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _start_run(self):
        target = self.folder_path.get()
        if not target or not FIJI: return
        self._save_setting("last_folder", target)

        self.is_running = True
        self.btn_run.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.stop_event.clear()
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, "end")
        self.log_text.config(state="disabled")
        
        t = threading.Thread(target=self._worker, args=(Path(target),), daemon=True)
        t.start()

    def _stop_run(self):
        if self.is_running:
            self.stop_event.set()
            self._log("🛑 Stopping... (Force Killing Fiji)")

    def _worker(self, folder):
        cmd = [str(FIJI), "-macro", str(MACRO_PATH), str(folder.resolve())]
        self.after(0, lambda: self._log(f"🚀 Launching Fiji..."))

        try:
            proc = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True,
                bufsize=1,
                preexec_fn=os.setsid
            )
            
            while True:
                if self.stop_event.is_set():
                    try: os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    except: pass
                    break

                line = proc.stdout.readline()
                if not line and proc.poll() is not None: break
                
                if line:
                    clean = line.strip()
                    # Emoji Filter
                    if ">>>" in clean:
                        clean_msg = clean.split(">>>")[1].strip()
                        if "Processing" in clean_msg:
                            clean_msg = "🔹 " + clean_msg
                        elif "Done" in clean_msg:
                            clean_msg = "✅ " + clean_msg
                        elif "Error" in clean_msg:
                            clean_msg = "❌ " + clean_msg
                        elif "Skipped" in clean_msg:
                            clean_msg = "⏭️ " + clean_msg
                        self.after(0, lambda msg=clean_msg: self._log(msg))

                if int(time.time() * 10) % 20 == 0: self._check_progress(folder)

            self.after(0, lambda: self._log("🏁 Batch Finished."))
            self._check_progress(folder)

        except Exception as e:
            self.after(0, lambda: self._log(f"❌ CRITICAL ERROR: {e}"))

        finally:
            self.after(0, self._reset_ui)

    def _check_progress(self, folder):
        oirs = list(folder.rglob("*.oir"))
        csvs = list(folder.rglob("*.csv"))
        total = len(oirs)
        done = len(csvs)
        self.after(0, lambda: self._update_progress_gui(done, total))

    def _update_progress_gui(self, done, total):
        if total > 0:
            pct = (done / total) * 100
            self.progress['value'] = pct
            self.status_var.set(f"Processed: {done} / {total} ({int(pct)}%)")

    def _reset_ui(self):
        self.is_running = False
        self.btn_run.config(state="normal")
        self.btn_stop.config(state="disabled")

if __name__ == "__main__":
    app = MosaicApp()
    app.mainloop()