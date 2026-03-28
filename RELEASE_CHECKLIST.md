# Labellix Studio Release Checklist

Use this checklist before shipping a new release.

## 1. Brand Name
- [ ] Main window title shows "Labellix Studio".
- [ ] Dialogs/messages use "Labellix Studio".
- [ ] Startup command/docs use `labellix_studio.py`.

## 2. Logo and Icons
- [ ] Final logo is present and approved.
- [ ] App icon is updated in runtime resources.
- [ ] Packaging icons exist: 512, 256, 128, 64, 32.

## 3. UI and Text
- [ ] User-facing text has no old brand names.
- [ ] README branding is fully updated.
- [ ] About/help text branding is fully updated.

## 4. Settings and Runtime
- [ ] App closes without crash.
- [ ] Settings save/load works after restart.
- [ ] Window size/position/state persist.
- [ ] Line/fill colors persist.
- [ ] Label file format persists.

## 5. Data and Naming Policy
- [ ] Canonical technical identifiers use Labellix naming.
- [ ] Legacy compatibility behavior is intentionally set (enabled or removed).

## 6. Quality Gate
- [ ] Unit tests pass.
- [ ] Manual smoke test pass:
  - [ ] Open image folder
  - [ ] Draw/edit annotation
  - [ ] Save annotation
  - [ ] Export dataset
  - [ ] Reopen app and verify state restore

## 7. Release Artifacts
- [ ] README updated for this release.
- [ ] Release package includes updated logo/icon assets.
- [ ] Release notes mention Labellix Studio branding update.
- [ ] Version/tag is finalized.
