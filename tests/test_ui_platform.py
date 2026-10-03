import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from pint_live.ui import assets
from pint_live.ui.scale_manager import initial_window_size


class _Screen:
    def __init__(self, width, height, scale=1):
        self.width, self.height, self.scale = width, height, scale

    def winfo_screenwidth(self):
        return self.width

    def winfo_screenheight(self):
        return self.height

    def _reverse_window_scaling(self, value):
        return int(value / self.scale)


class WindowSizingTests(unittest.TestCase):
    def test_large_screen_keeps_preferred_logical_size(self):
        self.assertEqual(initial_window_size(_Screen(1920, 1080)), (1240, 820))

    def test_small_laptop_leaves_space_for_title_bar_and_taskbar(self):
        self.assertEqual(initial_window_size(_Screen(1280, 800)), (1216, 704))

    def test_windows_dpi_is_accounted_for_once(self):
        # 4K at 200% and full-HD at 100% have the same usable logical area.
        self.assertEqual(
            initial_window_size(_Screen(3840, 2160, 2)),
            initial_window_size(_Screen(1920, 1080)),
        )
        self.assertEqual(initial_window_size(_Screen(1920, 1080, 1.5)), (1216, 624))


class AssetTests(unittest.TestCase):
    def test_shipped_logo_is_available_without_freezing(self):
        self.assertTrue(assets.asset_path("PiNT_InAppLogo.png").is_file())
        self.assertIsNotNone(assets.load_image_fit_width("PiNT_InAppLogo.png", 240))

    def test_retina_image_keeps_source_pixels_and_logical_aspect_ratio(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "assets"
            folder.mkdir()
            Image.new("RGBA", (600, 240)).save(folder / "logo.png")
            with patch.object(assets, "base_path", return_value=directory):
                fit = assets.load_image_fit_width("logo.png", 150)
                exact = assets.load_image("logo.png", (100, 40))
        self.assertEqual(fit.cget("size"), (150, 60))
        self.assertEqual(exact.cget("size"), (100, 40))
        for image in (fit, exact):
            self.assertEqual(image.cget("light_image").size, (600, 240))
            self.assertEqual(image.cget("dark_image").size, (600, 240))

    def test_current_bundle_preferred_and_legacy_layout_still_loads(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            package = bundle / "pint_live" / "ui"
            for folder in (package / "assets", bundle / "assets"):
                folder.mkdir(parents=True)
                Image.new("RGBA", (12, 8)).save(folder / "logo.png")
            with (
                patch.object(assets, "__file__", str(package / "assets.py")),
                patch.object(sys, "_MEIPASS", directory, create=True),
            ):
                self.assertEqual(assets.asset_path("logo.png"), (package / "assets" / "logo.png").resolve())
                (package / "assets" / "logo.png").unlink()
                self.assertEqual(assets.asset_path("logo.png"), bundle / "assets" / "logo.png")
                self.assertIsNotNone(assets.load_image_fit_width("logo.png", 6))

    def test_missing_and_invalid_images_allow_text_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "assets"
            folder.mkdir()
            (folder / "invalid.png").write_text("not an image")
            with patch.object(assets, "base_path", return_value=directory):
                self.assertIsNone(assets.load_image("missing.png", (20, 20)))
                self.assertIsNone(assets.load_image_fit_width("invalid.png", 20))


if __name__ == "__main__":
    unittest.main()
