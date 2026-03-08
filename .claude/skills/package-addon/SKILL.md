---
name: package-addon
description: Package the Anki addon and upload it to Google Drive
disable-model-invocation: true
argument-hint: ""
allowed-tools: Bash(bash addon/package_addon.sh*), Bash(rclone copy*), Bash(rclone lsf*)
---

Package the MvJ Anki addon and upload to Google Drive.

## Steps

1. Run `bash addon/package_addon.sh` from the repo root to create the `.ankiaddon` file
2. Check for existing files with the same base name on Google Drive:
   ```
   rclone lsf "work-drive:MvJ Drive/Add-ons/" --include "<base-name>*"
   ```
   - If a file with the same name already exists, append a version suffix:
     - `mvj_note_type-2026-03-08.ankiaddon` already exists → use `mvj_note_type-2026-03-08.2.ankiaddon`
     - `mvj_note_type-2026-03-08.2.ankiaddon` already exists → use `mvj_note_type-2026-03-08.3.ankiaddon`
     - And so on, incrementing until the name is unique
   - Rename the local file before uploading if a suffix is needed
3. Upload the `.ankiaddon` file to Google Drive:
   ```
   rclone copy <file> "work-drive:MvJ Drive/Add-ons/"
   ```
4. Report the final filename and confirm the upload succeeded
