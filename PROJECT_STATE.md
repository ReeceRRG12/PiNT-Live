# PiNT Live — project brief and checkpoint

## Brief

- **Purpose:** turn live, mixed-vendor switch data into accurate, shareable network documentation.
- **Deliverable:** a refreshed Python desktop app, navigable Excel workbooks, and a new beta release with Windows EXE and macOS DMG downloads.
- **Success:** clearer setup and readable results; usable Windows/macOS sizing; supported polling/export behavior preserved; automated checks pass; native release builds and published asset checksums verified.
- **Constraints:** preserve the current desktop workflow and vendor support. Credentials stay in memory; raw configuration export remains opt-in. Live hardware validation must be distinguished from simulated checks.
- **Non-goals:** scheduled/headless polling, desired-state configuration changes, and promoting this beta to stable without live hardware validation.
- **Stages:** latest-code baseline (complete) → GUI and desktop packaging → local verification → native CI builds and GitHub prerelease.
- **Finish condition:** scoped GUI changes verified, new beta published with Windows EXE and Mac DMGs/checksums, and remaining platform/hardware validation recorded here.

## Active checkpoint — desktop release, 3 October 2026

- User requested pulling latest code, making the GUI nicer/easier, Windows EXE and macOS DMG distribution, and a new release. This explicitly expands the prior scope to UI redesign and Mac packaging.
- `git pull --ff-only` confirmed clean `main` at `20d67dc` is current. Baseline: all 33 automated tests pass.
- Work branch: `codex/desktop-v0.7.0`. Planned release: `v0.7.0-beta.1` / package version `0.7.0b1`; retain beta classification because hardware validation is outstanding.
- Implemented: slate/teal workspace, summary cards, numbered setup, persistent poll/stop/status controls, credential readiness, keyboard search/export, searchable link-filtered results, Retina asset loading, native DPI sizing and matching table scaling. Search filters do not change export data.
- Packaging: Windows x64 portable EXE and native Apple Silicon/Intel Mac apps in DMGs with Applications shortcuts. Three native CI jobs run tests and actual frozen-GUI startup checks; publication depends on all three and verifies checksums. Builds are not publisher-signed or Apple-notarized.
- Local verification: all **44 tests** pass; compileall, pip check, and git diff --check pass. Mac desktop checks covered empty and populated views, 980×620 resizing, keyboard search (1 of 16 ports while metrics retain full totals), and bulk credentials dialog. No Tk callback errors. Fixed export-footer clipping discovered visually; independent review also caught and resolved a debounce cancellation issue.
- Current stage: local GUI/source verification complete; native package build verification in progress. Next: publish and verify v0.7.0-beta.1 assets, then update main and this checkpoint.
- Documentation references: [CustomTkinter native scaling](https://customtkinter.tomschimansky.com/documentation/scaling/), [GitHub native runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners), [PyInstaller native builds](https://www.pyinstaller.org/en/stable/usage.html), and [Apple first-launch guidance](https://support.apple.com/en-gb/102445).
- Remaining validation: live switch hardware and interactive Windows/high-DPI testing. No switches contacted during this work.
- Native usage check: 53% used / 47% remaining in the visible weekly window; secondary window unavailable. No model change or active routing exception.

## Checkpoint — 3 October 2026

- User authorized reviewing the current app, pulling the repository, and implementing improvements.
- `git pull --ff-only` confirmed `main` at `0c8c301` was current. Checkout was clean; work continues on `codex/reliability-review`.
- Baseline: all 12 tests passed with `.venv/bin/python -m unittest discover -s tests -v`.
- Implemented: correct SSH/Telnet default ports; safe and unique Excel sheet names with working Summary links; literal device/ARP strings and removal of unsupported control characters; interface sheet filters; unique ARP records with hostname retention and isolated import failures; per-snapshot MAC display for duplicate hosts; Cisco model and ordered allowed-VLAN parsing; platform-appropriate icon loading.
- Verification: all **33 tests** pass (`.venv/bin/python -m unittest discover -s tests -v`), including workbook save/reload checks and offline Netmiko driver checks across all supported vendors/protocols. `compileall`, `pip check`, and `git diff --check` pass. ARP changes received independent review; final combined source and tests were inspected.
- Desktop check: macOS startup initially exposed an existing ICO callback error; after the icon fix it completed with no Tk callback errors. The sandbox could not start Tk, so this check ran with approved desktop access.
- Cisco VLAN command semantics were checked against [Cisco's command reference](https://www.cisco.com/c/en/us/td/docs/switches/connectedgrid/cgs2520/software/release/12_2_53_ex/command/reference/cr2520/cli3.pdf), pages 93–94. Fixtures are synthetic; no live switches were contacted.
- User subsequently authorized pushing a beta branch and publishing a beta release with a Windows EXE (explicitly clarified from “EXT”).
- Current stage: beta delivery and requested branch organization complete. The beta was pushed as `codex/beta-v0.6.2`, then renamed to `main` at the user's request. Tag `v0.6.2-beta.1` still points to release code `6ad8303d2653d57f4f3b1f9b01725d8736f6eab5`, package/app version `0.6.2b1`.
- Branch organization: the former `main` is now `stable`, preserving v0.6.1 commit `0c8c30154bc4c08004aa985684857d8eb374dbff`. The former beta branch is now `main` and is GitHub's default branch. Local names and upstream tracking match. This is a branch rename, not stable-release promotion; existing tags and release status are unchanged.
- Published [PiNT Live v0.6.2 Beta 1](https://github.com/ReeceRRG12/PiNT-Live/releases/tag/v0.6.2-beta.1). GitHub confirms it is a published prerelease, with an EXE and checksum attached; `v0.6.1` remains Latest/stable.
- [Windows build 37151346773](https://github.com/ReeceRRG12/PiNT-Live/actions/runs/37151346773) succeeded on the tagged commit: all 33 tests passed and PyInstaller built the executable successfully.
- Download verification: `PiNT-Live-v0.6.2-beta.1-Windows.exe` is a Windows x64 PE file, 32,413,580 bytes. Its SHA-256 matches both the published checksum file and GitHub asset digest: `e287e75364359e69903263e3f66226569fa80d7858705d366ff194d908c4523e`.
- Next action: test the beta EXE interactively on Windows and supported switch hardware, especially Cisco VLAN modifiers and Telnet. Stable promotion remains outside the authorized beta scope.
- Model setting unchanged; no active routing exception.

## Backlog

- Minor polling status issue: Stop requested during the last switch's read timeout can still finish as a failure rather than “Stopped.” Existing completed results are preserved. Reproduce with a collector that sets the stop event and raises `ReadTimeout`, then adjust the worker's completion status in a future polling pass.
