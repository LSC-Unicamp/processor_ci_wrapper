from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.hdl_process import _ghdl_work_library, validate_wrapper_simulation


class GhdlWorkLibraryTests(unittest.TestCase):
    def test_normalizes_processor_name(self) -> None:
        self.assertEqual(_ghdl_work_library("Rudi-RV32I"), "Rudi_RV32I")

    def test_prefixes_identifier_starting_with_digit(self) -> None:
        self.assertEqual(_ghdl_work_library("32-bit-core"), "processor_32_bit_core")

    def test_explicit_work_library_is_normalized(self) -> None:
        self.assertEqual(_ghdl_work_library("ignored", "my-work"), "my_work")


class SignatureMemoryTests(unittest.TestCase):
    def test_missing_explicit_memory_file_is_a_setup_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wrapper = root / "wrapper.sv"
            wrapper.write_text("module processorci_top; endmodule\n")
            result = validate_wrapper_simulation(
                "fixture", [], [], wrapper_path=wrapper, build_dir=root / "build",
                memory_file=root / "missing.hex",
            )
            self.assertEqual(result["status"], "missing_memory_file")
            self.assertIn("missing.hex", result["reason"])


if __name__ == "__main__":
    unittest.main()
