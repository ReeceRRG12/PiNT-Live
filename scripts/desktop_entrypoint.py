"""Frozen desktop entry point, including an offline release smoke check."""

from __future__ import annotations

import json
import platform
import sys
import traceback
from pathlib import Path


def smoke_test(report_path: Path) -> int:
    """Exercise the actual bundled GUI and data without contacting switches."""
    report = {"ok": False, "architecture": platform.machine(), "errors": []}
    app = None
    try:
        import customtkinter as ctk
        import ntc_templates

        from pint_live import __version__
        from pint_live.ui.app import PintLiveApp
        from pint_live.ui.assets import load_image_fit_width

        report["version"] = __version__
        templates = Path(ntc_templates.__file__).parent / "templates"
        if not (templates / "index").is_file():
            raise RuntimeError("Bundled TextFSM template index is missing")

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Install this before construction to capture any initialization callbacks.
        class CheckedApp(PintLiveApp):
            def report_callback_exception(self, exc, value, tb):
                report["errors"].append("".join(traceback.format_exception(exc, value, tb)))

        app = CheckedApp()
        if load_image_fit_width("PiNT_InAppLogo.png", 160) is None:
            raise RuntimeError("Bundled application logo failed to load")
        app.after(750, app.quit)
        app.mainloop()
        report["ok"] = not report["errors"]
    except Exception:
        report["errors"].append(traceback.format_exc())
    finally:
        if app is not None:
            app.destroy()
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--smoke-test":
        raise SystemExit(smoke_test(Path(sys.argv[2]).resolve()))
    from pint_live.ui.app import main

    main()
