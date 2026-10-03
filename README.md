# idle — Terminal Typing + LeetCode Toolkit

Keyboard-only companion for typing practice and LeetCode in a terminal pane.

## Requirements

- Python 3.11+
- uv
- Terminal with minimum dimensions of 40x10

## Setup & Running

Setup (installs dependencies):

```powershell
uv sync
```

### GUI Mode (Default)

Launch full GUI main menu:

```powershell
uv run idle
# or
uv run idle gui
```

Open a specific GUI screen directly using `--gui`:

```powershell
uv run idle type --gui        # or: uv run idle typing --gui
uv run idle drill --gui
uv run idle lc --gui          # or: uv run idle leetcode --gui
uv run idle stats --gui
uv run idle config --gui
```

### Terminal / CLI Mode

Launch interactive terminal menu:

```powershell
uv run idle --cli
```

Run CLI commands directly:

```powershell
uv run idle type              # or: uv run idle typing
uv run idle drill
uv run idle lc list           # or: uv run idle leetcode list
uv run idle stats
uv run idle config
```

## GUI Controls

Keyboard-first. Mouse optional.

| Key | Action |
| --- | ------ |
| Esc | Back / quit |
| Ctrl+C | Return to menu (from subscreen) / Exit program (from menu) |
| Tab | Restart session (typing/drill) / Confirm |
| Enter | Select / Confirm |
| Arrows | Navigate lists and menus |
| Ctrl+W | Delete word |
| Ctrl+T | Test LeetCode solution |
| Ctrl+S | Submit LeetCode solution |
| Ctrl+O | Open in browser |

## Developer Commands

```powershell
uv run pytest -q
uv run ruff check
uv run mypy
```

## Usage & CLI Reference

```text
idle [--cli | --gui]
idle {type,typing} [--time 30|60|120 | --words 25|50|100 | --quote | --code python] [--list 200|1000] [--punct] [--numbers] [--stop-on-error] [--gui]
idle drill [--gui]
idle {lc,leetcode} {login,list,show,pick,daily,start,test,submit,stats,open} [--gui]
idle stats [--limit 20] [--gui]
idle config [--edit] [--gui]
```

### Typing Examples

```powershell
# Terminal mode
uv run idle type
uv run idle type --time 30
uv run idle type --words 50 --list 1000 --punct --numbers --stop-on-error
uv run idle type --quote
uv run idle type --code python
uv run idle drill
uv run idle stats --limit 20

# Directly in GUI
uv run idle type --gui
uv run idle drill --gui
uv run idle stats --gui
```

### LeetCode Examples

```powershell
uv run idle lc login
uv run idle lc list -n 20
uv run idle lc list --difficulty e --tag array --status todo --refresh
uv run idle lc show 1
uv run idle lc pick --difficulty e
uv run idle lc daily
uv run idle lc start two-sum
uv run idle lc test
uv run idle lc test two-sum
uv run idle lc submit
uv run idle lc submit two-sum
uv run idle lc stats
uv run idle lc open two-sum

# Directly in GUI
uv run idle lc --gui
```

## Login

1. Log in to leetcode.com in a browser.
2. Copy `LEETCODE_SESSION` and `csrftoken` cookies.
3. Run `uv run idle lc login` and paste each value.
4. Credentials save to `auth.json` with `0600` permissions on POSIX.

Cookies are never logged. On expiry run `uv run idle lc login` again.

## Graceful Failures

No traceback for expected cases:

- terminal too small: needs 40x10, resize and retry
- Ctrl+C: prints `exited cleanly`, restores terminal
- offline: `could not ... (offline?). Check network and retry.`
- expired login: `Session expired. Run: idle lc login`
- empty history: `no sessions yet. Run: idle type`
- missing editor: `could not open editor: ...`
- missing pygame: run `uv sync`, no separate GUI install needed
