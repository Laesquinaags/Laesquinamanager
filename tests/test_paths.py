import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import paths


class ApplicationPathTests(unittest.TestCase):
    def test_source_mode_points_to_project_folder(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(paths.sys, "frozen", False, create=True):
            expected = Path(paths.__file__).resolve().parent.parent
            self.assertEqual(paths.application_folder(), expected)

    def test_override_supports_isolated_tests_and_recovery(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.dict(os.environ, {"LA_ESQUINA_HOME": folder}):
            self.assertEqual(paths.application_folder(), Path(folder).resolve())

    def test_packaged_mode_uses_executable_location(self):
        executable = Path("C:/LaEsquina/LaEsquinaManager.exe")
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(paths.sys, "frozen", True, create=True), \
             patch.object(paths.sys, "executable", str(executable)):
            self.assertEqual(
                paths.application_folder(), executable.resolve().parent
            )


if __name__ == "__main__":
    unittest.main()
