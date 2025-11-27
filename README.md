# 🔬 Mosaic Automation

This repository provides a high-performance, parallelized Graphical User Interface (GUI) wrapper for the **MosaicSuite Particle Tracker** in Fiji (ImageJ).

It solves the common stability and speed issues associated with batch-processing large microscopy videos (`.oir` files) by orchestrating multiple Fiji instances in parallel, managing memory aggressively, and automatically retrying failed files.

-----

## ✨ Features

  * **🚀 Multi-Threaded Processing:** Spawns 1–4 parallel Fiji workers to maximize CPU usage (ideal for M1/M2/M3 Mac chips).
  * **🔄 Smart Auto-Retry:** Automatically detects files that failed to process (due to Bio-Formats timeouts or memory leaks) and re-runs them in a "cleanup phase" to ensure 100% completion.
  * **⚖️ Randomized Load Balancing:** Workers use a randomized queue strategy to prevent race conditions and file deadlocks without requiring complex lock files.
  * **🧹 Clean Output:** Suppresses the verbose, spammy logs from Java/ImageJ and provides a clean, emoji-coded status feed (`Processing`, `Done`, `Error`).
  * **🧠 Persistent Memory:** Remembers your last used folder and worker configuration.
  * **📁 Universal Compatibility:** Works as a raw Python script or a standalone macOS App. Auto-detects Fiji in standard locations or allows manual selection.

-----

## ⚙️ Setup and Prerequisites

### 1\. System Requirements

  * **Fiji (ImageJ):** You must have Fiji installed (usually in `/Applications/Fiji.app`).
  * **MosaicSuite Plugin:** Enable the "MOSAIC ToolSuite" update site in Fiji (`Help > Update... > Manage Update Sites`).
  * **Python 3.9+:** (Only required if running from source).

### 2\. Installation (Running from Source)

1.  **Clone or Download:** Get this repository.
2.  **Open Terminal:** Navigate to the project folder.
3.  **Create Environment:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```
4.  **Install Dependencies:**
    This project uses standard libraries + `pyinstaller` for building.
    ```bash
    pip install pyinstaller
    ```

-----

## 📦 Building for Release (Make it an App)

To distribute this tool to others so they can just double-click it (without needing Python installed), package it into a standalone App.

1.  Ensure you are in the project folder with your virtual environment active.
2.  Run this command to bundle the script and the macro together:

<!-- end list -->

```bash
pyinstaller --name "MosaicAutomation" \
            --onefile \
            --windowed \
            --add-data "mosaic_batch.ijm:." \
            mosaic_gui.py
```

3.  **Locate the App:** Look in the new `dist/` folder. You will find `MosaicAutomation.app`.
4.  **Distribute:** Zip this `.app` file and send it to users.

> **Note for Users:** When opening the app for the first time on a new Mac, they may need to Right-Click the App and select **Open** to bypass Apple's developer verification.

-----

## 🚀 Usage Guide

### 1\. Launch

  * **From Source:** `python mosaic_gui.py`
  * **From App:** Double-click `MosaicAutomation.app`

### 2\. Configure Workers

Select the number of **Parallel Workers** (1–4) from the dropdown.

  * **1 Worker:** Safe, slow (Standard usage).
  * **3 Workers:** Recommended for modern CPUs (M1/M2/M3). Maximizes speed without freezing the system.

### 3\. Select Data

Click **Browse** and select the root folder containing your `.oir` video files. The tool will recursively scan all subfolders.

### 4\. Run Batch

Click **RUN BATCH**.

The tool will perform the following lifecycle:

1.  **Phase 1 (Main Run):** Launches workers to attack the file list randomly.
2.  **Check:** Scans for missing CSV files.
3.  **Phase 2 (Auto-Retry):** If files were missed/crashed, it re-launches workers to finish the stragglers.
4.  **Cleanup:** Force-kills all background Java processes to ensure no memory leaks.

### 5\. Output

Results are saved as `.csv` files in the same folder as the input videos.

  * Input: `Experiment/Sample1/video_01.oir`
  * Output: `Experiment/Sample1/video_01.csv`

-----

## 📂 Project Structure

| File | Description |
| :--- | :--- |
| **`mosaic_gui.py`** | The Python Process Manager. Handles the GUI, threads, and lifecycle management (start, stop, retry). |
| **`mosaic_batch.ijm`** | The ImageJ Macro. Runs inside Fiji to handle Bio-Formats importing and Mosaic particle tracking. |
| **`settings.json`** | Auto-generated in the User's home folder to save paths and preferences. |
