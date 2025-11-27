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

# --- UNIVERSAL RESOURCE HELPER ---
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# --- CONFIGURATION ---
MACRO_PATH = Path(resource_path("mosaic_batch.ijm"))
SETTINGS_FILE = Path.home() / ".mosaic_automation_settings.json"

FIJI_CANDIDATES = [
    Path("/Applications/Fiji/fiji"),
    Path("/Applications/Fiji.app/Contents/MacOS/ImageJ-macosx"),
    Path(str(Path.home() / "Applications/Fiji.app/Contents/MacOS/ImageJ-macosx"))
]

def find_fiji():
    for p in FIJI_CANDIDATES:
        if p.exists(): return p
    return None

# ---------------- GUI CLASS ----------------
class MosaicApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mosaic Automation 2.0")
        self.geometry("700x600")
        
        self.settings = self._load_settings()
        last_folder = self.settings.get("last_folder", "")
        last_workers = self.settings.get("worker_count", "3")
        self.fiji_path = self.settings.get("fiji_path", "")
        
        self.folder_path = tk.StringVar(value=last_folder)
        self.worker_count_var = tk.StringVar(value=last_workers)
        self.status_var = tk.StringVar(value="Ready")
        self.is_running = False
        self.stop_event = threading.Event()
        self.active_procs = []
        self.fiji_exe = self._locate_fiji()
        
        self._ui()
        
        if last_folder:
            self.after(500, lambda: self._scan_folder(Path(last_folder)))

    def _load_settings(self):
        if SETTINGS_FILE.exists():
            try: return json.loads(SETTINGS_FILE.read_text())
            except: return {}
        return {}

    def _save_setting(self, key, value):
        self.settings[key] = value
        try: SETTINGS_FILE.write_text(json.dumps(self.settings, indent=2))
        except: pass

    def _locate_fiji(self):
        if self.fiji_path and Path(self.fiji_path).exists():
            return Path(self.fiji_path)
        auto = find_fiji()
        if auto: return auto
        return None

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
        ttk.Button(setting_frame, text="Locate Fiji App", command=self._ask_fiji).pack(side="right")

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

    def _ask_fiji(self):
        path = filedialog.askopenfilename(title="Select Fiji Executable")
        if path:
            self.fiji_exe = Path(path)
            self._save_setting("fiji_path", path)
            messagebox.showinfo("Success", "Fiji path updated.")

    def _browse(self):
        start_dir = self.folder_path.get() if os.path.exists(self.folder_path.get()) else str(Path.home())
        p = filedialog.askdirectory(initialdir=start_dir)
        if p:
            self.folder_path.set(p)
            self._save_setting("last_folder", p)
            self._scan_folder(Path(p))

    def _scan_folder(self, folder):
        if not folder.exists(): return
        # Use strict counting logic here too
        done, total = self._check_progress(folder)
        self.status_var.set(f"Found {total} .oir files ({done} already processed).")
        self._log(f"📂 Ready: {total} files found.")

    def _log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"{msg}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _start_run(self):
        target = self.folder_path.get()
        if not target: return
        if not self.fiji_exe or not self.fiji_exe.exists():
            self.fiji_exe = self._locate_fiji()
            if not self.fiji_exe:
                messagebox.showerror("Error", "Fiji not found.")
                return

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
            self._log("🛑 Stopping...")

    def _manager_lifecycle(self, folder):
        num_workers = int(self.worker_count_var.get())
        
        # Validate file count first
        done, total = self._check_progress(folder)
        if total == 0:
            self.after(0, lambda: self._log("⚠️ No .oir files found in this folder!"))
            self.after(0, self._reset_ui)
            return
        
        if done == total:
             self.after(0, lambda: self._log("✨ All files already processed!"))
             self.after(0, self._reset_ui)
             return

        # --- PHASE 1 ---
        self.after(0, lambda: self._log(f"🚀 Phase 1: Processing ({num_workers} workers)..."))
        self._run_worker_group(folder, num_workers)
        self._kill_all()

        if self.stop_event.is_set():
            self.after(0, self._reset_ui)
            return

        # --- CHECK & RETRY ---
        done, total = self._check_progress(folder)
        failed_count = total - done
        
        if failed_count > 0:
            self.after(0, lambda: self._log(f"⚠️ Found {failed_count} missing files. Retrying..."))
            self._run_worker_group(folder, num_workers)
            self._kill_all()
            
            final_done, final_total = self._check_progress(folder)
            final_fail = final_total - final_done
            
            if final_fail > 0:
                self.after(0, lambda: self._log(f"❌ Finished with {final_fail} errors."))
            else:
                self.after(0, lambda: self._log(f"✅ All files processed successfully."))
        else:
            self.after(0, lambda: self._log(f"✨ Success! 100% Complete."))

        self.after(0, self._reset_ui)

    def _run_worker_group(self, folder, num_workers):
        self.active_procs = []
        threads = []

        for i in range(num_workers):
            t = threading.Thread(target=self._worker_subprocess, args=(folder, i))
            t.start()
            threads.append(t)

        # Monitor loop
        complete_cycles = 0
        while any(t.is_alive() for t in threads):
            if self.stop_event.is_set():
                self._kill_all()
                break
            
            if int(time.time() * 10) % 20 == 0: 
                done, total = self._check_progress(folder)
                
                # AUTO-SHUTDOWN LOGIC
                if total > 0 and done == total:
                    complete_cycles += 1
                    if complete_cycles >= 3: # Wait ~6s to be sure
                        self.after(0, lambda: self._log("✅ 100% Detected. Cleaning up..."))
                        self._kill_all()
                        break
                else:
                    complete_cycles = 0

            time.sleep(0.5)
        
        self._check_progress(folder)

    def _worker_subprocess(self, folder, worker_id):
        seed = int(time.time() + worker_id * 1000)
        arg_string = f"{folder.resolve()}|{seed}"
        cmd = [str(self.fiji_exe), "-macro", str(MACRO_PATH), arg_string]

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, preexec_fn=os.setsid)
            self.active_procs.append(proc)
            while True:
                line = proc.stdout.readline()
                if not line and proc.poll() is not None: break
                if line and ">>>" in line:
                    clean = line.strip().split(">>>")[1].strip()
                    if "Processing" in clean: msg = f"🔹 [W{worker_id+1}] {clean}"
                    elif "Done" in clean: msg = f"✅ [W{worker_id+1}] {clean}"
                    elif "Error" in clean: msg = f"❌ [W{worker_id+1}] {clean}"
                    else: msg = f"ℹ️ [W{worker_id+1}] {clean}"
                    if "Skipped" not in clean: self.after(0, lambda m=msg: self._log(m))
        except Exception: pass 

    def _kill_all(self):
        for proc in self.active_procs:
            if proc.poll() is None:
                try: os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except: pass

    def _check_progress(self, folder):
        # STRICT CHECK: Only count done if the specific CSV exists for the OIR
        files = [p for p in folder.rglob("*") if p.suffix.lower() == ".oir"]
        total = len(files)
        done = 0
        for f in files:
            # Check for matching CSV (with same basename)
            target_csv = f.with_suffix(".csv")
            if target_csv.exists():
                done += 1
        
        self.after(0, lambda: self._update_progress_gui(done, total))
        return done, total

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