from dataclasses import fields
from unittest import TestCase

from dhpython.options import build_parser, DHPythonOptions


class TestPybuildOptions(TestCase):
    def test_args_match_options(self) -> None:
        parser = build_parser()
        parser_options = {action.dest for action in parser._get_optional_actions()} | {
            action.dest for action in parser._get_positional_actions()
        }
        # Built-ins
        parser_options -= {"help", "version"}

        options = {field.name for field in fields(DHPythonOptions)}
        # Added in parse_args()
        options -= {"write_log"}

        self.assertEqual(parser_options, options)
