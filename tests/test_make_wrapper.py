from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.make_wrapper import generate_instance


class SystemVerilogExpressionMappingTests(unittest.TestCase):
    def test_processorci_output_can_be_driven_by_expression(self) -> None:
        header = """module cpu(
          output logic [1:0] bus_width,
          input logic bus_busy
        );"""
        mapping = {
            "core_cyc": "(1'b1)",
            "core_sel": "(bus_width == 2'b00) ? 4'b0001 : 4'b1111",
            "bus_busy": "(~core_ack)",
        }

        instance, assignments, declarations = generate_instance(header, mapping)

        self.assertIn(".bus_busy  ((~core_ack))", instance)
        self.assertIn(".bus_width (bus_width)", instance)
        self.assertIn("assign core_cyc = (1'b1);", assignments)
        self.assertIn("assign core_sel = (bus_width == 2'b00)", assignments)
        self.assertIn("logic [1:0] bus_width;", declarations)
        self.assertNotIn("logic core_ack;", declarations)


if __name__ == "__main__":
    unittest.main()
