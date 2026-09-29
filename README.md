# PromptVault

A desktop app for managing, organizing and combining image-generation prompts
(Stable Diffusion, Flux, NovelAI, …). Built with Python and customtkinter.

## Features

### Library
- Categories with drag-to-sort, rename, move up/down, sort by name or size
- Prompts with **title, tags, note, weight, variants and example image**
- Tag bar with click-to-filter, search syntax `tag:name`, full-text search over text/title/note/tags
- Favorites, sort by manual / A→Z / most used / recently used / newest / longest
- Drag & drop reordering, multi-select with bulk copy / move / star / tag / delete (Ctrl+A, Delete)
- Detail view (click a prompt), right-click context menu, double-click to edit
- Usage counter (copies and builder results), duplicate finder with auto-clean
- Random picker with tag filter and favorites-only
- Editor with syntax highlighting for `(word:1.2)`, `((emphasis))`, `[de-emphasis]`, `__wildcards__`, `<lora:…>`
  plus character / word / approximate CLIP token counter (75-token chunks)

### Builder
- Slots from categories or free text; lock, pick, reroll, drag to reorder
- Per-slot fill probability (0–100 % slider), **draw 2–4 prompts per slot**, tag filter per slot
- Per-prompt weight (1–10) changes how often a prompt is drawn
- **Rules**: "if Outfit contains *bikini* → Environment only *beach, pool*" (or exclude)
- **Negative-prompt slots** with a separate result line and copy button
- Wildcard-syntax output (`__Category__`) for Dynamic Prompts workflows
- **Batch generate** N results, copy all, save all to a category, export .txt
- Templates: save, overwrite, load, rename, delete (slots + rules)
- Persistent history with pin / filter / save, template name recorded
- Builder state (slots, separator, rules) survives restarts
- Send the result straight to **Automatic1111** (`/sdapi/v1/txt2img`) or **ComfyUI** (`/prompt` with an API workflow)

### Data & safety
- Prompt objects with stable IDs (favorites no longer collide on identical text)
- Rotating backups (`backups/`, configurable count and interval) with a restore dialog
- Trash with restore, plus Ctrl+Z undo
- Configurable data folder (e.g. a OneDrive / Dropbox folder) with optional file copy
- Import: JSON (old and new format), TXT (one prompt per line), CSV (`category,text,tags,…`)
- Export: full backup (prompts, templates, rules, history), plain JSON, CSV, wildcard `.txt` per category
- Corrupted `prompts.json` is detected, kept aside and the latest backup is offered

### UI
- Dark / light theme, six accent colors, font scaling
- Settings dialog (Ctrl+,), statistics, shortcut help (F1)
- Window size and position remembered
- Optional: minimize to system tray and a global hotkey that rolls the Builder and copies the result

PromptVault works fully offline and contains no AI / LLM integration. The only network feature is the
optional connection to an Automatic1111 or ComfyUI instance running on your own machine, and it is
disabled until you enter a URL in the settings.

## Keyboard shortcuts

| Key | Action |
|---|---|
| Ctrl+N / Ctrl+Shift+N | New prompt / new category |
| Ctrl+F, Esc | Search, clear search / close dialog |
| Ctrl+A, Delete | Select all visible, delete selected |
| Ctrl+C | Copy selected prompts or builder result |
| Ctrl+Z | Undo delete |
| Ctrl+1 … 9 | Jump to category |
| Ctrl+L / Ctrl+B | Library / Builder |
| Space | Builder: randomize |
| Ctrl+Enter | Editor: save |
| Ctrl+, / Ctrl+D / Ctrl+T / F1 | Settings / duplicates / trash / help |

## Requirements

- Python 3.10+
- `customtkinter`, `pillow` (required)
- `pystray` (optional, system tray)

```
pip install -r requirements.txt
```

## Run

```
python main.py
```

or use `start.bat` on Windows.

## Build (Windows .exe)

```
pip install pyinstaller
build.bat
```

The executable will be in `dist/PromptVault.exe`.

## Data

All data lives next to the executable (or next to `main.py` when running from source),
or in the folder chosen under *Settings → Data folder*:

| File / folder | Content |
|---|---|
| `prompts.json` | prompts (format version 2, see `storage.py`) |
| `builder_templates.json` | builder templates (slots + rules) |
| `builder_state.json` | current builder slots, separator, rules |
| `history.json`, `trash.json` | builder history, deleted prompts |
| `backups/` | rotating backups of `prompts.json` |
| `images/`, `outputs/` | example images, images returned by A1111 |
| `settings.json` | app settings (always next to the executable) |

An existing version-1 `prompts.json` (`{category: [text, …]}`) plus `favorites.json` is migrated
automatically on first start; the original is kept as `prompts_v1_backup.json`.

## Project layout

| Module | Responsibility |
|---|---|
| `main.py` | app class, sidebar, categories, shortcuts, undo, toast |
| `library.py` | prompt list, cards, CRUD, multi-select, detail view, random picker |
| `builder.py` | slots, rules, result, batch generation, history, templates |
| `dialogs.py` | editors, settings, duplicates, trash, backups, import/export |
| `integrations.py` | local A1111 / ComfyUI, tray, global hotkey |
| `storage.py` | files, migration, backups, settings |
| `theme.py`, `widgets.py` | colors, fonts, DPI scaling, reusable widgets |

## License

PromptVault is released under the MIT License, see `LICENSE`. Third-party components:
customtkinter (CC0 1.0), Pillow (MIT-CMU), PyInstaller (GPL 2.0 with bootloader exception, build
tool only), and the optional `pystray` (LGPL 3.0). The Windows build bundles `pystray`; you can rebuild
the executable with a modified copy of that library from this repository using `build.bat`.
See `CHANGELOG.md` for release notes.

## Web version

`docs/index.html` is a single-file browser version with the same feature set, minus what a browser
cannot do: example images, the local image backend, system tray and global hotkey. It stores everything
in the browser's `localStorage` and uses the same data format, so a *Full backup* exported from the
desktop app can be imported into the web version and vice versa. Browser storage is limited to a few
megabytes, so export regularly. It is hosted with GitHub Pages; see `docs/privacy.html`.
