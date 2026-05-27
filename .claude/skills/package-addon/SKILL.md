---
name: package-addon
description: Package the Anki addon, upload it to Google Drive, and point the mvj.link/notetype short link at the new file
disable-model-invocation: true
argument-hint: ""
allowed-tools: Bash(bash addon/package_addon.sh*), Bash(rclone copy*), Bash(rclone lsf*), Bash(rclone link*), Bash(curl*)
---

Package the MvJ Anki addon, upload to Google Drive, and repoint the download short link.

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
4. Get a shareable Google Drive link for the file you just uploaded:
   ```
   rclone link "work-drive:MvJ Drive/Add-ons/<final-filename>"
   ```
   (If you already have the new share link, use that instead.)
5. Point the download short link at the new file. The add-on's download link is
   **`mvj.link/notetype`** (Shlink short code `notetype`) — Dojo members use it to fetch
   the add-on, so it must redirect to the file you just uploaded. Update its destination to
   the step-4 link via the Shlink REST API. The API base and key live in the laptop vault
   `.env` — read them at runtime, never hardcode the key:
   ```
   ENV="/Users/matt/Documents/Obsidian/life/.env"
   BASE=$(grep -E '^SHLINK_API_URL=' "$ENV" | cut -d= -f2- | tr -d '\r')
   KEY=$(grep -E '^SHLINK_API_KEY=' "$ENV" | cut -d= -f2- | tr -d '\r')

   # current destination (capture it for the before/after report)
   curl -fsS "$BASE/rest/v3/short-urls/notetype" -H "X-Api-Key: $KEY"

   # repoint it at the new file
   curl -fsS -X PATCH "$BASE/rest/v3/short-urls/notetype" \
     -H "X-Api-Key: $KEY" -H "Content-Type: application/json" \
     -d '{"longUrl": "<step-4 link>"}'
   ```
   (If it 404s, the code may sit on a non-default domain — retry with `?domain=mvj.link`.)
6. Report the final filename, confirm the upload succeeded, and show the short link's
   old → new destination
