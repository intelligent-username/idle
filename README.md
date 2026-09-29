# idle — Terminal Typing + LeetCode Toolkit

Keyboard-only companion for typing practice and LeetCode in a terminal pane.

## Install

```bash
pip install -e .
pip install -e .[dev]
python -m idle
idle
```

`idle --help` starts in under 100ms via lazy `curses`/`urllib` imports.

## Config paths

Linux/macOS:

- `~/.config/idle/config.toml`
- `~/.config/idle/auth.json` (0600)
- `~/.local/share/idle/idle.db`

Honors `XDG_CONFIG_HOME` and `XDG_DATA_HOME` when set.

Windows:

- `%APPDATA%\idle\config.toml`
- `%APPDATA%\idle\auth.json`
- `%APPDATA%\idle\idle.db`

Config auto-creates on first run. View with `idle config`, edit with `idle config --edit`.

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

## Windows

Unix uses stdlib `curses`. On Windows install the extra:

```bash
pip install -e .[windows]
```

This installs `windows-curses` with the same API.

## Graceful failures

No traceback for expected cases:

- terminal too small: needs 40x10, resize and retry
- Ctrl+C: prints `exited cleanly`, restores terminal
- offline: `could not ... (offline?). Check network and retry.`
- expired login: `Session expired. Run: idle lc login`
- empty history: `no sessions yet. Run: idle type`
- missing editor: `could not open editor: ...`
