# PiNT Live — project brief and checkpoint

## Brief

- **Purpose:** turn live, mixed-vendor switch data into accurate, shareable network documentation.
- **Deliverable:** the existing Python desktop app and navigable Excel workbooks described in `README.md`.
- **Success:** supported polling paths report failures accurately; exports preserve collected data as text and keep navigation valid; automated regression checks pass.
- **Constraints:** preserve the current desktop workflow and vendor support. Credentials stay in memory; raw configuration export remains opt-in. Live hardware validation must be distinguished from simulated checks.
- **Non-goals:** scheduled/headless polling, desired-state configuration changes, UI redesign, and promoting this beta to stable.
- **Stages:** review and bounded fixes (complete) → local verification (complete) → beta branch, Windows build, and GitHub prerelease (authorized 3 October 2026).
- **Finish condition:** scoped fixes verified, beta branch pushed, Windows executable and checksum attached to a verified GitHub prerelease, and remaining validation recorded here.

## Checkpoint — 3 October 2026

- User authorized reviewing the current app, pulling the repository, and implementing improvements.
- `git pull --ff-only` confirmed `main` at `0c8c301` was current. Checkout was clean; work continues on `codex/reliability-review`.
- Baseline: all 12 tests passed with `.venv/bin/python -m unittest discover -s tests -v`.
- Implemented: correct SSH/Telnet default ports; safe and unique Excel sheet names with working Summary links; literal device/ARP strings and removal of unsupported control characters; interface sheet filters; unique ARP records with hostname retention and isolated import failures; per-snapshot MAC display for duplicate hosts; Cisco model and ordered allowed-VLAN parsing; platform-appropriate icon loading.
- Verification: all **33 tests** pass (`.venv/bin/python -m unittest discover -s tests -v`), including workbook save/reload checks and offline Netmiko driver checks across all supported vendors/protocols. `compileall`, `pip check`, and `git diff --check` pass. ARP changes received independent review; final combined source and tests were inspected.
- Desktop check: macOS startup initially exposed an existing ICO callback error; after the icon fix it completed with no Tk callback errors. The sandbox could not start Tk, so this check ran with approved desktop access.
- Cisco VLAN command semantics were checked against [Cisco's command reference](https://www.cisco.com/c/en/us/td/docs/switches/connectedgrid/cgs2520/software/release/12_2_53_ex/command/reference/cr2520/cli3.pdf), pages 93–94. Fixtures are synthetic; no live switches were contacted.
- User subsequently authorized pushing a beta branch and publishing a beta release with a Windows EXE (explicitly clarified from “EXT”).
- Current stage: preparing `codex/beta-v0.6.2` and tag `v0.6.2-beta.1`, package/app version `0.6.2b1`. The release workflow marks hyphenated prerelease tags as prereleases and excludes them from Latest.
- Next action: verify release metadata and tests, commit and push the beta branch/tag, wait for the Windows build, then verify the published executable, checksum, and prerelease flag. Stable v0.6.1 remains unchanged.
- Model setting unchanged; no active routing exception.

## Backlog

- Minor polling status issue: Stop requested during the last switch's read timeout can still finish as a failure rather than “Stopped.” Existing completed results are preserved. Reproduce with a collector that sets the stop event and raises `ReadTimeout`, then adjust the worker's completion status in a future polling pass.
