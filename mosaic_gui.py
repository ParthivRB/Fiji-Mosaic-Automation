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
        self.geometry("700x600")
        
        self.settings = self._load_settings()
        last_folder = self.settings.get("last_folder", "")
        last_workers = self.settings.get("worker_count", "3")
        
        self.folder_path = tk.StringVar(value=last_folder)
        self.worker_count_var = tk.StringVar(value=last_workers)
        self.status_var = tk.StringVar(value="Ready")
        self.is_running = False
        self.stop_event = threading.Event()
        self.active_procs = []
        
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

        # Settings
        setting_frame = ttk.LabelFrame(main_frame, text="Configuration", padding="10")
        setting_frame.pack(fill="x", pady=(0, 15))
        ttk.Label(setting_frame, text="Parallel Workers:").pack(side="left", padx=(0, 10))
        wc_combo = ttk.Combobox(setting_frame, textvariable=self.worker_count_var, values=["1", "2", "3", "4"], width=5, state="readonly")
        wc_combo.pack(side="left")
        
        # REMOVED the text label here as requested

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
        self.btn_stop = ttk.Button(btn_frame, text="STOP ALL", command=self._stop_run, state="disabled")
        self.btn_stop.pack(side="right", fill="x", expand=True, padx=(5, 0))

        # Log
        log_lbl = ttk.Label(main_frame, text="Combined Status Log:")
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
        self._save_setting("worker_count", self.worker_count_var.get())

        self.is_running = True
        self.btn_run.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.stop_event.clear()
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, "end")
        self.log_text.config(state="disabled")
        
        t = threading.Thread(target=self._manager_lifecycle, args=(Path(target),), daemon=True)
        t.start()

    def _stop_run(self):
        if self.is_running:
            self.stop_event.set()
            self._log("🛑 Stopping all workers... (Force Kill)")

    def _manager_lifecycle(self, folder):
        num_workers = int(self.worker_count_var.get())
        
        # --- PHASE 1: INITIAL RUN ---
        self.after(0, lambda: self._log(f"🚀 Starting Phase 1: Main Batch ({num_workers} workers)"))
        self._run_worker_group(folder, num_workers)
        self._kill_all()

        if self.stop_event.is_set():
            self.after(0, self._reset_ui)
            return

        # --- CHECK FAILURES ---
        failed_count = self._count_missing(folder)
        
        if failed_count > 0:
            self.after(0, lambda: self._log(f"⚠️ Phase 1 complete. Found {failed_count} failed files."))
            self.after(0, lambda: self._log(f"🔄 Starting Phase 2: Retry Queue..."))
            
            # --- PHASE 2: RETRY RUN ---
            self._run_worker_group(folder, num_workers)
            self._kill_all()
            
            final_fail = self._count_missing(folder)
            if final_fail > 0:
                self.after(0, lambda: self._log(f"❌ Finished with {final_fail} errors remaining."))
            else:
                self.after(0, lambda: self._log(f"✅ Retry successful. All files processed."))
        else:
            self.after(0, lambda: self._log(f"✨ Perfect Run. No retries needed."))

        self.after(0, self._reset_ui)

    def _count_missing(self, folder):
        oirs = list(folder.rglob("*.oir"))
        missing = 0
        for oir in oirs:
            csv = oir.with_suffix(".csv")
            if not csv.exists(): missing += 1
        return missing

    def _run_worker_group(self, folder, num_workers):
        self.active_procs = []
        threads = []

        for i in range(num_workers):
            t = threading.Thread(target=self._worker_subprocess, args=(folder, i))
            t.start()
            threads.append(t)

        while any(t.is_alive() for t in threads):
            if self.stop_event.is_set():
                self._kill_all()
                break
            if int(time.time() * 10) % 20 == 0: 
                self._check_progress(folder)
            time.sleep(0.5)
        
        self._check_progress(folder)

    def _worker_subprocess(self, folder, worker_id):
        seed = int(time.time() + worker_id * 1000)
        arg_string = f"{folder.resolve()}|{seed}"
        cmd = [str(FIJI), "-macro", str(MACRO_PATH), arg_string]

        try:
            proc = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True,
                bufsize=1,
                preexec_fn=os.setsid
            )
            self.active_procs.append(proc)
            
            while True:
                line = proc.stdout.readline()
                if not line and proc.poll() is not None: break
                
                if line and ">>>" in line:
                    clean = line.strip().split(">>>")[1].strip()
                    if "Processing" in clean:
                        msg = f"🔹 [W{worker_id+1}] {clean}"
                    elif "Done" in clean:
                        msg = f"✅ [W{worker_id+1}] {clean}"
                    elif "Error" in clean:
                        msg = f"❌ [W{worker_id+1}] {clean}"
                    else:
                        msg = f"ℹ️ [W{worker_id+1}] {clean}"
                    
                    if "Skipped" not in clean:
                        self.after(0, lambda m=msg: self._log(m))

        except Exception:
            pass 

    def _kill_all(self):
        for proc in self.active_procs:
            if proc.poll() is None:
                try: os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except: pass

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