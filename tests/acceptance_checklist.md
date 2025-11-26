[ ] Env OK: Fiji launcher present, JDK 17 linked, Mosaic + Legacy installed.
[ ] Headless smoke: /Applications/Fiji/fiji -headless -eval 'print("OK")' returns OK.
[ ] Single file produces same-folder, same-basename .csv via Mosaic.
[ ] Batch nested: ≥3 files processed with progress; per-file SUCCESS/SKIP/ERROR visible; no text log file created.
[ ] Idempotency: re-run with existing CSVs → all skipped by default.
[ ] Cancel during run stops current job and prevents new ones from starting.
