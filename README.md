# idle — Terminal Typing + LeetCode Toolkit

Keyboard-only companion for typing practice and LeetCode in a terminal pane.

## Requirements

- Python 3.11+
- uv
- Terminal with minimum dimensions of 40x10

## Setup & Running

Setup (installs CLI and GUI deps):

```powershell
uv sync
```

Run (GUI is default):

```powershell
uv run idle
uv run python -m idle
uv run idle gui
uv run idle type
```

CLI subcommands still work. No separate `pip install idle[gui]` needed.

Dev:

```powershell
uv run pytest -q
uv run ruff check
uv run mypy
```

## Usage

```text
idle
idle type [--time 30|60|120 | --words 25|50|100 | --quote | --code python] [--list 200|1000] [--punct] [--numbers] [--stop-on-error]
idle drill
idle lc {login,list,show,pick,daily,start,test,submit,stats,open}
idle stats [--limit 20]
idle config [--edit]
```

Bare `idle` shows a numbered menu: `1) type  2) drill  3) leetcode  4) stats  5) quit` with `Best` and `Solved` one-liners. Menu option `1` runs `idle type` with config defaults (`time 60`, `list 200`).

Typing:

```bash
idle type
idle type --time 30
idle type --words 50 --list 1000 --punct --numbers --stop-on-error
idle type --quote
idle type --code python
idle drill
idle stats --limit 20
```

LeetCode:

```bash
idle lc login
idle lc list -n 20
idle lc list --difficulty e --tag array --status todo --refresh
idle lc show 1
idle lc pick --difficulty e
idle lc daily
idle lc start two-sum
idle lc test
idle lc test two-sum
idle lc submit
idle lc submit two-sum
idle lc stats
idle lc open two-sum
```

## Login

1. Log in to leetcode.com in a browser.
2. Copy `LEETCODE_SESSION` and `csrftoken` cookies.
3. Run `idle lc login` and paste each value.
4. Credentials save to `auth.json` with `0600` on POSIX.

Cookies are never logged. On expiry run `idle lc login` again.


## Graceful failures

No traceback for expected cases:

- terminal too small: needs 40x10, resize and retry
- Ctrl+C: prints `exited cleanly`, restores terminal
- offline: `could not ... (offline?). Check network and retry.`
- expired login: `Session expired. Run: idle lc login`
- empty history: `no sessions yet. Run: idle type`
- missing editor: `could not open editor: ...`
- missing pygame: run `uv sync`, no separate GUI install needed
