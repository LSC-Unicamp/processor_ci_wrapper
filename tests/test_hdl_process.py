from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.hdl_process import _ghdl_work_library


class GhdlWorkLibraryTests(unittest.TestCase):
    def test_normalizes_processor_name(self) -> None:
        self.assertEqual(_ghdl_work_library("Rudi-RV32I"), "Rudi_RV32I")

    def test_prefixes_identifier_starting_with_digit(self) -> None:
        self.assertEqual(_ghdl_work_library("32-bit-core"), "processor_32_bit_core")

    def test_explicit_work_library_is_normalized(self) -> None:
        self.assertEqual(_ghdl_work_library("ignored", "my-work"), "my_work")


if __name__ == "__main__":
    unittest.main()
