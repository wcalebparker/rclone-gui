# Changelog

## v1.0.5 — Fix app not launching on double-click
- Fixed app flashing and disappearing on launch (macOS was killing it for having no native window)
- Added LSUIElement so macOS treats the app as a background agent — no dock bounce, no window needed
- Browser now waits for the server to actually be ready before opening (no more timing guesses)
- If the app is already running, double-clicking opens the browser instead of crashing

## v1.0.4 — App icon + installation fix
- Added app icon (orange square with ⇄ arrows)
- Fixed "damaged or incomplete" error on macOS by including an installer script
- Open the DMG and double-click "Install rclone GUI" to install — it copies the app and removes the macOS security flag automatically

## v1.0.3 — Fix app bundle
- Fixed app crashing on launch when downloaded from GitHub
- Fixed rclone download location when running as installed .app
- App now opens your browser automatically on launch

## v1.0.0 — Initial release
- Copy files between local folders and cloud storage (Google Drive, Dropbox, OneDrive, Box, S3, Backblaze B2, SFTP, and more)
- Verify files match between source and destination
- Auto-install rclone on first launch
- Cloud storage browser with list view and search
- Dark mode UI
- rclone version checking and in-app updates
