import sys
import unittest
from unittest.mock import create_autospec

# Add thonny and plugin to sys.path
sys.path.insert(0, r"d:\REP\thonny")
sys.path.insert(0, r"d:\REP\Codestruct\Codestruct\thonny-plugin")

import thonny
import thonnycontrib.codestruct
from thonny.workbench import Workbench


class TestThonnyWorkbenchIntegration(unittest.TestCase):
    def test_load_plugin_registers_command(self):
        wb_mock = create_autospec(Workbench, instance=True)
        thonny._workbench = wb_mock
        try:
            thonnycontrib.codestruct.load_plugin()
            self.assertEqual(wb_mock.add_command.call_count, 1)
            calls = wb_mock.add_command.call_args_list
            registered_ids = {c.kwargs.get("command_id") for c in calls}
            self.assertIn("codestruct", registered_ids)
            self.assertNotIn("codestruct_analyze", registered_ids)

            # Check primary workbench command
            workbench_call = next(
                c for c in calls if c.kwargs.get("command_id") == "codestruct"
            )
            self.assertEqual(workbench_call.kwargs.get("menu_name"), "tools")
            self.assertEqual(workbench_call.kwargs.get("command_label"), "CodeStruct")
            print(
                "PASS: load_plugin successfully registered codestruct workbench command on Workbench autospec!"
            )
        finally:
            thonny._workbench = None


if __name__ == "__main__":
    unittest.main()
