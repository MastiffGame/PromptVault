# PromptVault

A desktop app for managing and organizing image-generation prompts, built with Python and customtkinter.

## Features

- Organize prompts in categories (Clothing, Hairstyle, Environment, Appearance, Position)
- Add, edit, and delete prompts
- Search within any category
- Random prompt picker with configurable count
- One-click copy to clipboard
- Dark UI

## Requirements

- Python 3.10+
- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) >= 5.2.0

```
pip install -r requirements.txt
```

## Run

```
python main.py
```

or use the included `start.bat` on Windows.

## Build (Windows .exe)

Requires [PyInstaller](https://pyinstaller.org):

```
pip install pyinstaller
build.bat
```

The executable will be in `dist/PromptVault.exe`.

## Data

Prompts are stored locally in `prompts.json` next to the executable (or next to `main.py` when running from source). This file is excluded from version control.
