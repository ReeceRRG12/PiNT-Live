# PiNT Live — project brief and checkpoint

## Brief

- **Purpose:** turn live, mixed-vendor switch data into accurate, shareable network documentation.
- **Current deliverable:** publish the verified bug fixes on `main` as `v0.7.0-beta.4` (`0.7.0b4`), with Windows x64 EXE and Apple Silicon/Intel macOS DMGs.
- **Success:** fixes and version committed to `main`; local tests pass; all native release jobs and frozen startup checks pass; published download checksums verified.
- **Constraints:** preserve the current desktop workflow and vendor support. Credentials stay in memory; raw configuration export remains opt-in. Live hardware validation must be distinguished from simulated checks.
- **Non-goals:** scheduled/headless polling, desired-state configuration changes, and promoting this beta to stable without live hardware validation.
- **Stages:** correctness fixes complete → version and local checks → main/tag push → native builds and release verification.
- **Finish condition:** beta 4 published with verified native downloads and saved checkpoint. Stable promotion remains outside scope.
- **Current next action:** resume release verification at GitHub Actions run `38066502696`; confirm publication and all three native downloads/checksums, then update release notes from pending to verified.

## Active checkpoint — bug-fix release, 10 October 2026

- User explicitly authorized fixing the review findings, pushing to `main` as a new version, and publishing the release. The fixes are already implemented; release target is `v0.7.0-beta.4`, package/app version `0.7.0b4`.
- Remote recheck confirmed `origin/main` at `0f82fb6` and no beta 4 tag/release. Preserve beta classification and existing stable branches; live-switch validation remains outstanding.
- Local verification complete: all 53 tests pass, tag/package/app versions agree at `0.7.0b4`, and ARM64 source-GUI startup reports `ok: true` with no callback errors.
- Committed fixes/version/docs at `44f8883ee0e50e1f6341d42d02b88b154ebe8328`, fast-forwarded main, and successfully pushed main and annotated tag `v0.7.0-beta.4` atomically.
- Created a draft prerelease titled PiNT Live v0.7.0 Beta 4 — Polling and Data Accuracy, with bug-fix notes. [Native release run 38066502696](https://github.com/ReeceRRG12/PiNT-Live/actions/runs/38066502696) is queued at the tagged commit. Workflow automatically publishes only after Windows x64, Apple Silicon and Intel macOS tests/builds/frozen startup checks and checksum verification succeed.
- **Current stage: native release build dispatched; final verification pending.** Work paused under the user-authorized usage reserve at 88% used / 12% remaining, with further release verification likely to cross the 10% reserve. No model change. The remote workflow continues independently.
- Exact resume: `gh run view 38066502696 --json status,conclusion,jobs,url`; inspect failures if any (never rewrite the tag). On success, `gh release view v0.7.0-beta.4 --json isDraft,isPrerelease,assets,url`; download all six assets to an ignored version-specific directory, compare SHA-256 values with checksum files and GitHub asset digests, and verify both DMGs. Then update beta 4 RELEASE_NOTES.md and GitHub release notes from pending to verified, record completion here, and push the final documentation checkpoint.
- Expected public release: https://github.com/ReeceRRG12/PiNT-Live/releases/tag/v0.7.0-beta.4 . Publication has not yet been verified; v0.6.1 remains stable.
- Usage at release start: 80% used / 20% remaining in the visible weekly window; secondary window unavailable. Preserve the authorized 10% reserve and save an exact continuation if reached.

## Checkpoint — bug review, 10 October 2026

- User requested pulling the latest code and ensuring it is free from bugs. Scope interpreted as review, reproducible fixes, and proportionate verification; no claim that all possible bugs have been eliminated.
- Clean `main`; `git pull --ff-only` successfully reached GitHub and returned **Already up to date** at `0f82fb6`. Local fixes are on `codex/bug-review-2026-10-10`; no push or release performed.
- Fixed Cisco VLAN reporting: observed trunk mode selects native VLAN rather than stale access settings; access VLANs come from the interface status even if omitted from configuration; inactive trunk allowed lists are ignored on access/routed ports. Semantics verified against [Cisco's command reference](https://www.cisco.com/c/en/us/td/docs/switches/connectedgrid/cgs2520/software/release/12_2_53_ex/command/reference/cr2520/cli3.pdf), PDF page 94. Default trunk VLAN omission behavior is unchanged.
- Fixed ARP display/export alignment: missing hostname slots now remain aligned with the corresponding MAC/IP slots in both the results table and saved Excel workbook.
- Fixed polling Stop handling: a final read timeout after Stop no longer creates a false failure; Stop during retry cleanup prevents reconnection; late Stop preserves completed results and reports Stopped. This resolves the prior backlog item.
- Verification: **53 tests passed**, including nine new regression tests; `compileall`, `pip check`, and `git diff --check` passed. Workbook alignment includes a save/reload check. Polling regressions reproduced four failing assertions before the fix and passed afterward. Independent reviews covered polling/session/collectors, data paths, sidebar credentials, and packaging helpers.
- macOS ARM64 source-GUI startup check passed with `ok: true`, version `0.7.0b3`, and no callback errors. No binaries rebuilt, no Windows interactive test, and no live switches contacted.
- Environment: the existing `.venv` had cloud-offloaded (`dataless`) dependency files that stalled imports. Verification used a temporary environment with the exact installed dependency versions (no project dependency upgrades). Interpreter: `/var/folders/_4/3qdmz6ps78v9hs0l7qf6jy180000gn/T/pint-review-20261010-3e3zoic8/venv/bin/python`; source smoke report alongside it at `desktop-smoke.json`. The temporary environment can expire; recreate from project dependencies if necessary.
- **Current stage: local review and fixes complete.** Next action remains supported-switch and interactive Windows/high-DPI validation; publication or stable promotion requires a separate delivery decision.
- Native usage checkpoint: 70% used / 30% remaining in the visible weekly window; secondary window unavailable. No model change or active routing exception.

## Checkpoint — desktop release, 3 October 2026

- User requested pulling latest code, making the GUI nicer/easier, Windows EXE and macOS DMG distribution, and a new release. This explicitly expands the prior scope to UI redesign and Mac packaging.
- `git pull --ff-only` confirmed clean `main` at `20d67dc` is current. Baseline: all 33 automated tests pass.
- Implemented on `codex/desktop-v0.7.0`, then fast-forwarded into `main`. Released `v0.7.0-beta.3` / package version `0.7.0b3` at commit `17bbbedf3fb417986fc9b1bee610958e9ae5aa61`; beta classification retained because hardware validation is outstanding.
- Implemented: slate/teal workspace, summary cards, numbered setup, persistent poll/stop/status controls, credential readiness, keyboard search/export, searchable link-filtered results, Retina asset loading, native DPI sizing and matching table scaling. Search filters do not change export data.
- Packaging: Windows x64 portable EXE and native Apple Silicon/Intel Mac apps in DMGs with Applications shortcuts. Three native CI jobs run tests and actual frozen-GUI startup checks; publication depends on all three and verifies checksums. Builds are not publisher-signed or Apple-notarized.
- Local verification: all **44 tests** pass; compileall, pip check, and git diff --check pass. Mac desktop checks covered empty and populated views, 980×620 resizing, keyboard search (1 of 16 ports while metrics retain full totals), and bulk credentials dialog. No Tk callback errors. Fixed export-footer clipping discovered visually; independent review also caught and resolved a debounce cancellation issue.
- Native attempt `v0.7.0-beta.1` / `21de4e3` built Windows and Apple Silicon binaries but frozen startup detected missing ntc-templates distribution metadata. Publication was blocked; no beta.1 release exists. Its tag is retained for traceability. Corrected packaging keeps a new versioned tag for each candidate, without rewriting an existing tag.
- Beta 2 / `2c80121`: Windows x64 and Apple Silicon native builds, 44 tests, frozen GUI startup, and package checks passed. Downloaded Apple Silicon DMG additionally passed local SHA-256 and hdiutil verification. Intel frozen startup failed because source-built cryptography linked newer Homebrew OpenSSL while PyInstaller selected Python's older same-name library. Publication remained blocked.
- Intel fix: fresh cryptography source build with OPENSSL_STATIC=1 and Homebrew OPENSSL_DIR; no crypto downgrade and no reused dynamic wheel cache. A native linkage check now rejects colliding OpenSSL dylibs before bundling, following [official cryptography guidance](https://cryptography.io/en/latest/installation/#building-cryptography-on-macos).
- **Current stage: requested desktop release complete.** [Native build 37156531859](https://github.com/ReeceRRG12/PiNT-Live/actions/runs/37156531859) succeeded on the tagged commit: all 44 tests, frozen GUI startup, architecture verification, and packaging passed on Windows x64, macOS Apple Silicon, and macOS Intel. Mac builds were checked on macOS 15.
- Published [PiNT Live v0.7.0 Beta 3](https://github.com/ReeceRRG12/PiNT-Live/releases/tag/v0.7.0-beta.3) with three native downloads and three checksums. GitHub confirms published prerelease; `v0.6.1` remains Latest/stable.
- Download verification: all three local SHA-256 hashes match published checksum contents and GitHub binary asset digests. Windows file is an x86-64 GUI PE executable. Both final DMGs passed local `hdiutil verify`. Verified downloads are saved under `dist/release/` (ignored by Git).
- Windows checksum text was normalized to LF after publication so macOS `shasum -c` also accepts it; the executable and its hash did not change. The release helper now emits LF on every OS. This metadata-only packaging fix and final checkpoint follow the tagged application commit on main.
- Final binary hashes: Windows `b8c080ad104dca5e2d47bf8938f108759c85f9a24cf8ccc8871dd7f8e3657dad`; Apple Silicon `f7ce4cd6aff692c8b4ebc44c1598773b21973bb3098e2b71e4fe1daa363ada57`; Intel `69a46461de8d303c7340210d077682539a1c670be37818eadad21395acca0aeb`.
- User confirmed new release/main and requested a stable release branch for the old code. `main` contains the new desktop release; `stable-v0.6.2` preserves the exact pre-update main commit `20d67dc71a12b3a0f923036590bd8f136a2e46ca`. Existing `stable` remains at v0.6.1 (`0c8c301`). The branch name does not change the older beta release classification.
- Next action: interactive Windows/high-DPI and live switch validation before considering stable promotion. Signing/notarization remains absent and documented; no live hardware was contacted.
- Documentation references: [CustomTkinter native scaling](https://customtkinter.tomschimansky.com/documentation/scaling/), [GitHub native runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners), [PyInstaller native builds](https://www.pyinstaller.org/en/stable/usage.html), and [Apple first-launch guidance](https://support.apple.com/en-gb/102445).
- Remaining validation: live switch hardware and interactive Windows/high-DPI testing. No switches contacted during this work.
- Native usage check: 60% used / 40% remaining in the visible weekly window; secondary window unavailable. No model change or active routing exception.

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
