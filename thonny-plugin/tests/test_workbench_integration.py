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
            wb_mock.add_command.assert_called_once()
            args, kwargs = wb_mock.add_command.call_args
            cmd_id = kwargs.get("command_id") or args[0]
            menu = kwargs.get("menu_name") or args[1]
            label = kwargs.get("command_label") or args[2]
            self.assertEqual(cmd_id, "codestruct_analyze")
            self.assertEqual(menu, "tools")
            self.assertEqual(label, "Analyze with CodeStruct")
            print(
                "PASS: load_plugin successfully registered codestruct_analyze command on Workbench autospec!"
            )
        finally:
            thonny._workbench = None


if __name__ == "__main__":
    unittest.main()
