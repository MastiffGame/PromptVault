# Changelog

All notable changes to PromptVault are documented here.

## 2.0.1 — 2026-09-30

### Added
- Builder → Batch ×N: new **→ Send all** button queues every generated result on the local image backend. ComfyUI receives one job per result (all land in its queue); Automatic1111 jobs run one after another with progress toasts and each image is saved to `outputs/`. A confirmation appears above 20 jobs.
- `%SEED%` placeholder for ComfyUI workflows. PromptVault fills it with a fresh random seed for every job, so identical prompts still produce different images. Works as `"seed": "%SEED%"` and as `"seed": %SEED%`.

### Changed
- Single sends and batch sends share one implementation; the send button is disabled until a backend URL is configured.
- A warning toast appears if the ComfyUI workflow contains no `%PROMPT%` placeholder.

## 2.0.0 — 2026-09-29

Platforms: Windows desktop (Python 3.10+ / PyInstaller build), Web (single file, GitHub Pages).
Data format: version 2, automatic migration from version 1.

### Highlights
- Prompts are full objects: title, tags, note, weight, variants, example image, usage counter and timestamps. Favorites are tracked per prompt ID instead of by text.
- Builder rules, multi-draw slots, negative-prompt slots, batch generation and wildcard output.
- Rotating backups, trash, duplicate finder and a configurable data folder.
- Settings dialog with dark/light theme, six accent colors and font scaling.
- Optional local image backend (Automatic1111 / ComfyUI on your own machine), disabled by default.
- The web version was rewritten to the same feature set and data format; exports are interchangeable between desktop and web.
- No AI/LLM integration and no network requests except to a local image backend URL you enter yourself.

### Upgrade notes
- On first start an existing version-1 `prompts.json` (`{category: [text, …]}`) and `favorites.json` are migrated automatically. The original is kept as `prompts_v1_backup.json`.
- Old builder templates (list format) are converted on load.
- Settings live in `settings.json` next to the executable and can point to a different data folder (Settings → Data folder).
- The web version migrates data from the previous `localStorage` keys and leaves the old keys untouched as a safety copy.
- Older builds cannot read the new format. To go back, restore `prompts_v1_backup.json` to `prompts.json`.

### Library
**Added**
- Tags per prompt with a clickable tag bar, multi-tag filtering and `tag:name` search syntax.
- Optional title and note; search covers text, title, note, tags and variants.
- Sort modes: manual, A→Z, most used, recently used, newest, longest.
- Drag & drop reordering (manual sort, no active filters).
- Multi-select with bulk copy / move / star / unstar / tag / delete; Ctrl+A and Delete.
- Detail view, right-click context menu, double-click to edit.
- Duplicate finder across all categories with auto-clean (keeps starred / most used).
- Usage counter and last-used timestamp, incremented on copy and on Builder results.
- Random picker with tag filter and favorites-only option.
- Duplicate prompt; categories can be dragged, moved up/down, sorted by name or size, added to the Builder or exported as wildcard from the context menu.

**Editor**
- Full editor with title, weight slider (1–10), tags with quick-add chips, note, variants and example image (desktop only).
- Syntax highlighting for `(word:1.2)`, `((emphasis))`, `[de-emphasis]`, `__wildcards__`, `<lora:…>` and `BREAK`.
- Character / word / approximate CLIP token counter with 75-token chunk warning; Ctrl+Enter saves.

**Changed**
- Copy on a card shows a confirmation toast.

### Builder
**Added**
- Slot settings: fill probability slider (0–100 %), draw count min–max, tag filter per slot, negative toggle.
- Per-prompt weight (1–10) influences draw frequency; variants are drawn at random.
- Rules: "if a slot of category A rolled X → category B only / exclude terms", evaluated in two passes after each roll, saved with templates and state.
- Negative-prompt slots with a separate result line and copy button.
- Wildcard-syntax output mode (`__Category__`).
- Batch generate: roll N times, unique-only, copy all, save all, export .txt.
- Manual pick with multi-selection (Ctrl-click) and search by text or tag.
- Drag & drop reordering of slots.
- Persistent history with pin, filter, delete, save-to-category and template name.
- Builder state (slots, rules, separator, wildcard toggle) survives restarts.
- Templates: overwrite current, rename, delete; templates store slot settings and rules.
- Result bar shows character count, token estimate and chunk count.
- "Use in Builder" adds a locked slot with a given prompt.

### Data & safety
**Added**
- Rotating backups in `backups/` (count and interval configurable) with a restore dialog.
- Trash with restore and empty; Ctrl+Z undo keeps working.
- Configurable data folder with optional copy of existing files.
- Import: JSON (v1 and v2, plain lists), TXT (one prompt per line), CSV (category, text, tags, title, note). Imports merge and skip duplicates.
- Export: full backup (prompts, templates, rules, history), plain JSON, CSV, wildcard .txt per category.
- Corrupted `prompts.json` is detected, kept aside as `prompts.json.corrupt.<time>` and the newest backup is offered.
- Statistics dialog.

**Changed**
- Atomic writes for all data files.

### User interface
**Added**
- Settings dialog (Ctrl+,): theme, accent color, font size, default separator, random count, confirm-before-delete, remember window, data folder, backups, image backend, tray and hotkey.
- Dark and light theme, six accent colors, font scaling; UI rebuilds live after saving.
- Window size, position and maximized state are remembered.
- Shortcut help (F1) and new shortcuts: Ctrl+N, Ctrl+Shift+N, Ctrl+A, Delete, Ctrl+1…9, Ctrl+L, Ctrl+B, Ctrl+D, Ctrl+T, Ctrl+, and Esc.
- Tooltips on icon buttons; correct scaling on high-DPI displays.

### Integrations (desktop, optional)
- Local image backend: send the Builder result or a single prompt to Automatic1111 (`/sdapi/v1/txt2img`, image saved to `outputs/`) or ComfyUI (`/prompt` with an API-format workflow using `%PROMPT%` and `%NEGATIVE%`). Disabled until a URL is entered.
- Minimize to system tray (requires `pystray`) with roll-and-copy and quit.
- Global hotkey (Windows) that rolls the Builder and copies the result. Off by default.

### Web version (`docs/index.html`)
- Rewritten as a single offline file with the desktop feature set, except example images, image backend, tray and hotkey.
- Same data format; full backups can be exchanged with the desktop app.
- Browser-local backups (up to 5), trash, history, settings and builder state.
- "Delete all local data" in settings; privacy policy updated.

### Removed
- Nothing user-facing. A briefly added AI prompt-assistant was removed before release; no LLM or cloud dependency ships with PromptVault.

### Fixed
- Favorites were matched by text, so identical prompts in one category shared the star.
- Fixed pixel sizes were not scaled with Windows DPI, clipping top-bar buttons.
- Export button label was truncated; logo overlapped at larger font sizes.
- Builder history was lost on restart.
- Deleting a category left its prompts unrecoverable except via undo; they now go to trash.

### Known limitations
- Data files are stored unencrypted (JSON).
- Browser storage in the web version is limited to roughly 5 MB per site.
- The executable is not code-signed; SmartScreen may warn on first launch.
- The local image backend sends prompt text in plain text to the configured URL.

### Technical
- Code split into `main.py`, `library.py`, `builder.py`, `dialogs.py`, `integrations.py`, `storage.py`, `theme.py`, `widgets.py`.
- Dependencies: customtkinter, pillow; optional pystray. Build via `build.bat` (PyInstaller).

## 1.x

- Categories, prompts, search, random picker, batch import, favorites, undo, Builder with templates, web version with localStorage and privacy policy.
