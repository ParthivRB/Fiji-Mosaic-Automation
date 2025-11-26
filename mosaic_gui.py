#!/usr/bin/env python3
"""
Mosaic 2D Batch Runner — minimal GUI to batch-run MosaicSuite Particle Tracker 2D
on Olympus .oir files via Fiji (headless).

- Recursively scans for *.oir
- For each file, runs macros/mosaic_2d_tracker.ijm with:
    input='.../file.oir', output='.../file.csv'
- Skips files that already have CSVs (default)
- Shows progress + minimal in-window logs only (NO files written)
- Supports Cancel
"""

from pathlib import Path
import json
import threading
import time
import subprocess
import PySimpleGUI as sg

# ----------------------------- Constants & Paths -----------------------------

PROJECT_ROOT = Path("/Users/Parthiv/Automation/Mosaic Automated/2.0").resolve()
MACRO_PATH   = PROJECT_ROOT / "macros" / "mosaic_2d_tracker.ijm"
CONFIG_PATH  = PROJECT_ROOT / "run_config.json"

# Fiji launchers we accept (first existing wins)
FIJI_CANDIDATES = [
    Path("/Applications/Fiji/fiji"),
    Path("/Applications/Fiji.app/Contents/MacOS/ImageJ-macosx"),
    Path("/Applications/Fiji.app/ImageJ-macosx"),
]

def find_fiji():
    for p in FIJI_CANDIDATES:
        if p.exists():
            return p
    return None

FIJI = find_fiji()

# Best-effort Mosaic presence (for env check message)
MOSAIC_CANDIDATES = [
    Path("/Applications/Fiji/plugins/Mosaic_ToolSuite"),
    Path("/Applications/Fiji.app/plugins/Mosaic_ToolSuite"),
]
def has_mosaic():
    return any(p.exists() for p in MOSAIC_CANDIDATES)

# ----------------------------- Helpers -----------------------------

def load_config():
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    return {"last_input": str(PROJECT_ROOT)}

def save_config(cfg: dict):
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
    except Exception:
        pass

def find_oir_files(root: Path):
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() == ".oir":
            yield p

def env_check():
    if not FIJI or not FIJI.exists():
        return False, (
            "Fiji launcher not found. Expected one of:\n"
            "  - /Applications/Fiji/fiji\n"
            "  - /Applications/Fiji.app/Contents/MacOS/ImageJ-macosx"
        )
    if not has_mosaic():
        return False, (
            "MosaicSuite not found. Open Fiji → Help → Update… → Manage update sites… → "
            "enable MOSAIC and Legacy/ImageJ → Apply & Restart."
        )
    return True, "OK"

# ----------------------------- Runner -----------------------------

class Runner:
    def __init__(self, files, log, set_prog, done, cancel_event, skip_existing=True):
        self.files = files
        self.log = log
        self.set_prog = set_prog
        self.done = done
        self.cancel = cancel_event      # <-- consistent name
        self.skip_existing = skip_existing

    def _run_one(self, oir: Path, idx: int, total: int):
        if self.cancel.is_set():
            return False

        out_csv = oir.with_suffix(".csv")
        if self.skip_existing and out_csv.exists():
            self.log(f"[{idx}/{total}] SKIP (exists): {oir.name}")
            self.set_prog(idx, total)
            return True

        # Use -macro (not -batch) so the macro controls timing and cleanup
        arg = f"input='{oir.as_posix()}', output='{out_csv.as_posix()}'"
        cmd = [str(FIJI), "-headless", "-batch", str(MACRO_PATH), arg]


        self.log(f"[{idx}/{total}] RUN: {oir.name}")
        self.log("CMD: " + " ".join(cmd))

        try:
            # Run Fiji silently; discard all output
            proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True
            )
            # Wait for Fiji to finish (with cancel support)
            while proc.poll() is None:
                if self.cancel.is_set():
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    break
                time.sleep(0.1)

            if self.cancel.is_set():
                self.log("Cancelled.")
                return False

            # Filesystems (esp. OneDrive) can lag—poll briefly for the CSV to appear
            if not out_csv.exists():
                deadline = time.time() + 3.0  # up to ~3s settle time
                while time.time() < deadline and not out_csv.exists():
                    time.sleep(0.15)

            # Success = CSV exists
            if out_csv.exists():
                self.log(f"SUCCESS → {out_csv.name}")
            else:
                rc = proc.returncode
                self.log(f"ERROR (rc={rc}) → no CSV for {oir.name}")

            self.set_prog(idx, total)
            return True

        except Exception as e:
            self.log(f"EXCEPTION: {e}")
            self.set_prog(idx, total)
            return True


    def run_all(self):
        total = len(self.files)
        for i, f in enumerate(self.files, 1):
            if self.cancel.is_set():
                break
            self._run_one(f, i, total)
        self.done()

# ----------------------------- GUI -----------------------------

def main():
    cfg = load_config()

    sg.theme("SystemDefault")
    layout = [
        [sg.Text("Input folder"),
         sg.Input(cfg.get("last_input", ""), key="-IN-", expand_x=True),
         sg.FolderBrowse("Browse")],
        [sg.Button("Scan for .oir", key="-SCAN-"),
         sg.Button("Run", key="-RUN-", disabled=True),
         sg.Button("Cancel", key="-CANCEL-", visible=False)],
        [sg.ProgressBar(100, orientation="h", size=(40, 20), key="-PROG-")],
        [sg.Multiline("", key="-LOG-", size=(100, 24), autoscroll=True, disabled=True)],
    ]

    win = sg.Window("Mosaic 2D Batch Runner", layout, finalize=True, resizable=True)

    files = []
    cancel_event = threading.Event()

    def log(msg: str):
        win["-LOG-"].update(value=str(msg) + "\n", append=True)

    def set_prog(i, total):
        pct = int(100 * i / max(1, total))
        win["-PROG-"].update(pct)

    def on_done():
        win["-SCAN-"].update(disabled=False)
        win["-RUN-"].update(disabled=False)
        win["-CANCEL-"].update(visible=False)
        log("Batch complete.")

    def start_run():
        win["-SCAN-"].update(disabled=True)
        win["-RUN-"].update(disabled=True)
        win["-CANCEL-"].update(visible=True)
        cancel_event.clear()
        threading.Thread(
            target=Runner(files, log, set_prog, on_done, cancel_event, skip_existing=True).run_all,
            daemon=True,
        ).start()

    ok, msg = env_check()
    if not ok:
        sg.popup_error("Environment problem:\n\n" + msg)

    while True:
        ev, vals = win.read(timeout=200)
        if ev in (sg.WIN_CLOSED, None):
            cancel_event.set()
            break

        if ev == "-SCAN-":
            p = Path(vals["-IN-"]).expanduser()
            if not p.exists():
                sg.popup_error("Folder does not exist.")
                continue
            cfg["last_input"] = str(p)
            save_config(cfg)
            files = sorted(set(find_oir_files(p)))
            log(f"Found {len(files)} .oir file(s).")
            set_prog(0, max(1, len(files)))
            win["-RUN-"].update(disabled=(len(files) == 0))

        if ev == "-RUN-":
            if not files:
                sg.popup("Nothing to run. Click Scan first.")
                continue
            ok, msg = env_check()
            if not ok:
                sg.popup_error("Environment not ready:\n\n" + msg)
                continue
            start_run()

        if ev == "-CANCEL-":
            cancel_event.set()
            log("Cancellation requested…")

    win.close()

if __name__ == "__main__":
    main()
