# Book My Date

A private, local-first desktop calendar and event booker for Linux, Windows and
macOS. Events, reminders and preferences stay on your computer in a local SQLite
database.

## Highlights

- Month calendar with distinct weekend colours and multiple events per day
- Agenda panel with create, edit, delete and all-day events
- Search across titles, descriptions and locations
- Reminder scheduling with 20-second polling, snooze and native notifications
- Optional system tray integration and close-to-tray behaviour
- Six event categories, Monday/Sunday week start, five accent themes
- Automatic database backups during updates
- Browser-based setup wizard that creates an isolated environment and installs
  `PySide6` without a terminal workflow
- One-click launchers for Linux, Windows and macOS

## Requirements

- Python 3.9 or newer available as `python3` (Linux/macOS) or `py`/`python`
  (Windows)
- A desktop session with a system tray is recommended but not required
- Internet access during the first setup so the wizard can download PySide6
- On Ubuntu/Debian, the wizard can install missing Qt libraries with
  administrator permission:

  ```text
  libxcb-cursor0 libxkbcommon-x11-0
  ```

The setup wizard uses only the Python standard library. It starts before PySide6
exists and creates a private virtual environment beside your calendar data.

## Start the app

### Linux

Double-click **Start Book My Date.sh**. If your file manager opens scripts in a
text editor instead, choose “Run” or run:

```bash
./"Start Book My Date.sh"
```

### Windows

Double-click **Start Book My Date.lnk**. The shortcut carries the app icon and
works when the project is opened through a WSL UNC path.

If the shortcuts are missing (for example after moving or downloading the
project), run **Create Windows Shortcuts.bat** once to regenerate them. The
`.bat` launchers also work directly.

### macOS

Double-click **Start Book My Date.command**. The first time, macOS may ask you
to confirm that the script can run.

On first launch the setup wizard opens in your browser. After setup, the same
launcher opens the app directly.

To update, repair or change shortcut options, use:

- Linux: **Setup Book My Date.sh**
- Windows: **Setup Book My Date.lnk** (run **Create Windows Shortcuts.bat** if missing)
- macOS: **Setup Book My Date.command**

You can also run setup from any platform with:

```bash
python3 launcher.py --setup
```

## What setup does

The wizard:

1. Checks the Python version and available system libraries.
2. Backs up any existing database.
3. Copies the application into its private data folder.
4. Creates a virtual environment and installs PySide6.
5. Adds a desktop shortcut, Start menu entry or macOS app bundle.
6. Verifies the toolkit and optionally opens the calendar.

Nothing is installed system-wide. Removing the application data folder removes
the app and your events, so keep a backup first.

## Data locations

| Platform | Default location |
| --- | --- |
| Linux | `~/.local/share/book-my-date` |
| Windows | `%USERPROFILE%\BookMyDate` |
| macOS | `~/Library/Application Support/BookMyDate` |

On Windows the profile folder is used deliberately so Microsoft Store Python's
AppData redirection cannot split the app and its virtual environment into
different locations.

Set `BOOK_MY_DATE_HOME` to use a different folder:

```bash
BOOK_MY_DATE_HOME=/path/to/data python3 launcher.py --setup
```

Useful files inside the data folder:

- `book_my_date.db` — events and settings
- `book_my_date.log` — application log
- `install.json` — installed version and environment metadata
- `backups/` — database snapshots created before updates
- `app/` — installed application copy
- `venv/` — private Python environment

## Development

Create a local environment and install dependencies:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

Run from source:

```bash
python -m book_my_date
```

Run with an isolated data directory:

```bash
BOOK_MY_DATE_HOME=/tmp/book-my-date-dev python -m book_my_date
```

Run tests:

```bash
python -m unittest discover -s tests -v
```

CI and Jenkins use pytest for JUnit and coverage output:

```bash
python -m pytest tests -q
```

Run lint and compilation checks:

```bash
ruff check .
python -m compileall -q book_my_date installer launcher.py
```

A headless smoke test can start the UI without a display server:

```bash
BOOK_MY_DATE_HOME=/tmp/book-my-date-smoke \
QT_QPA_PLATFORM=offscreen \
python -c "from PySide6.QtWidgets import QApplication; from book_my_date.core.database import Database; from book_my_date.core.reminders import ReminderEngine; from book_my_date.ui.main_window import MainWindow; app=QApplication([]); db=Database(':memory:'); window=MainWindow(db, ReminderEngine(db)); print(window.size()); window.close()"
```

`QT_QPA_PLATFORM=offscreen` warnings about tray icons or missing platform themes
are expected in headless environments.

## Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl+N` | New event |
| `Ctrl+F` | Focus search |
| `Ctrl+,` | Settings |
| `Ctrl+Left` / `Ctrl+Right` | Previous / next month |
| `Ctrl+T` | Jump to today |
| `Escape` | Close search or clear the query |

## Packaging

Build a native single-folder artifact with PyInstaller:

```bash
python -m pip install -r requirements-dev.txt
python packaging/build.py
```

Artifacts are written to `release/`. Build on each target operating system;
PyInstaller does not cross-compile. The GitHub Actions workflow in
`.github/workflows/build.yml` builds Linux, Windows and macOS archives and
attaches them to the workflow run.

## Jenkins pipelines

Production Jenkins pipelines are kept separately in `jenkins-pipeline/`.
Both a Declarative and a Scripted pipeline cover checkout, dependencies,
quality checks, tests, security scans, SonarQube quality gate, packaging,
S3 publishing, release approval, deployment, smoke testing and CloudWatch
monitoring. See `jenkins-pipeline/README.md` for Jenkins setup, credentials,
agent requirements and release-tag behavior.

## Project layout

```text
book_my_date/
  app.py                 application bootstrap and single-instance guard
  config.py              paths, metadata and bundled assets
  core/
    calendar_utils.py    pure date and calendar helpers
    database.py          SQLite schema, CRUD, reminders and backups
    models.py            validated Event and Category models
    notifications.py     optional native notification bridge
    reminders.py         reminder polling and snooze logic
  ui/
    main_window.py       main window, sidebar, search and tray
    calendar_widget.py   month grid and day cells
    day_panel.py         selected-day agenda
    event_dialog.py      create/edit/delete dialog
    settings_dialog.py   preferences and backup
    theme.py             palette and Qt stylesheet
    widgets.py           reusable cards, toasts and search popup
installer/
  wizard.py              standard-library local setup server
  wizard.html            branded browser setup interface
launcher.py              click launcher and installed-app starter
tools/generate_assets.py brand asset generator
tools/windows/           Windows shortcut-with-icon helper
jenkins-pipeline/        Declarative and Scripted production pipelines
packaging/               PyInstaller spec and release builder
tests/                   unit and installer tests
```

## Privacy

Book My Date has no account system, analytics, telemetry or cloud sync. Event
data is written only to the local SQLite database. Native notifications are sent
through the operating system when available. The setup wizard downloads packages
from PyPI through `pip`.

## Troubleshooting

### The window does not open on Linux

Qt needs XCB cursor and keyboard libraries. Run the setup wizard and use **Fix
libraries with administrator permission**, or install the packages manually:

```bash
sudo apt-get install libxcb-cursor0 libxkbcommon-x11-0
```

### Setup cannot download PySide6

Check the internet connection, proxy settings and available disk space, then
run setup again. The wizard reuses a healthy existing virtual environment.

### The launcher opens setup after installation

This usually means the private environment is missing or the Qt interface cannot
load. Run **Setup Book My Date** to repair it. Your database is backed up before
the app files are replaced.

### Windows reports that UNC paths are not supported

This warning is harmless when the project lives on a WSL share. Use the
generated `.lnk` shortcuts, or run **Create Windows Shortcuts.bat** once. The
batch launchers switch to a temporary drive with `pushd` so they can run from a
`\\wsl.localhost\...` path.

### Find the log

Open the data folder from the setup page, or use the path for your platform from
the table above. The log is `book_my_date.log`.
