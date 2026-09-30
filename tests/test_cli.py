import contextlib
import io
import os
import tempfile
import unittest
from unittest.mock import patch

from connstr_format.cli import main


class CliStdinStdoutTests(unittest.TestCase):
    def test_normalizes_each_line_from_stdin_to_stdout(self):
        stdin = io.StringIO("Server=db1;UID=sa;Database=orders\nServer=db2;UID=app;Database=orders\n")
        captured = io.StringIO()
        with patch("sys.stdin", stdin), contextlib.redirect_stdout(captured):
            status = main([])
        self.assertEqual(status, 0)
        self.assertEqual(
            captured.getvalue(),
            "host=db1;database=orders;user=sa\nhost=db2;database=orders;user=app\n",
        )

    def test_mask_password_flag_is_forwarded(self):
        stdin = io.StringIO("Server=db1;PWD=hunter2\n")
        captured = io.StringIO()
        with patch("sys.stdin", stdin), contextlib.redirect_stdout(captured):
            status = main(["--mask-password"])
        self.assertEqual(status, 0)
        self.assertEqual(captured.getvalue(), "host=db1;password=***\n")


class CliFileArgumentTests(unittest.TestCase):
    def test_reads_input_from_a_file_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            in_path = os.path.join(tmp, "connections.txt")
            with open(in_path, "w", encoding="utf-8") as f:
                f.write("Server=db1;UID=sa;Database=orders\n")

            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                status = main([in_path])
            self.assertEqual(status, 0)
            self.assertEqual(captured.getvalue(), "host=db1;database=orders;user=sa\n")

    def test_writes_output_to_a_file_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            in_path = os.path.join(tmp, "connections.txt")
            out_path = os.path.join(tmp, "normalized.txt")
            with open(in_path, "w", encoding="utf-8") as f:
                f.write("Server=db1;UID=sa;Database=orders\n")

            status = main([in_path, "-o", out_path])
            self.assertEqual(status, 0)
            with open(out_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "host=db1;database=orders;user=sa\n")


class CliFileErrorTests(unittest.TestCase):
    def test_missing_input_file_returns_two_and_reports_error(self):
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured):
            status = main(["/no/such/connections.txt"])
        self.assertEqual(status, 2)
        self.assertIn("connstr-format:", captured.getvalue())
        self.assertIn("connections.txt", captured.getvalue())

    def test_unwritable_output_path_returns_two_and_reports_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            in_path = os.path.join(tmp, "connections.txt")
            with open(in_path, "w", encoding="utf-8") as f:
                f.write("Server=db1\n")
            out_path = os.path.join(tmp, "no-such-dir", "out.txt")

            captured = io.StringIO()
            with contextlib.redirect_stderr(captured):
                status = main([in_path, "-o", out_path])
            self.assertEqual(status, 2)
            self.assertIn("out.txt", captured.getvalue())


class CliValidateTests(unittest.TestCase):
    def test_returns_zero_and_prints_nothing_when_all_lines_are_well_formed(self):
        stdin = io.StringIO("Server=db1;UID=sa\n")
        captured = io.StringIO()
        with patch("sys.stdin", stdin), contextlib.redirect_stdout(captured):
            status = main(["--validate"])
        self.assertEqual(status, 0)
        self.assertEqual(captured.getvalue(), "")

    def test_returns_one_and_reports_malformed_lines(self):
        stdin = io.StringIO("Server=db1;notapair;Database=orders\n")
        captured = io.StringIO()
        with patch("sys.stdin", stdin), contextlib.redirect_stdout(captured):
            status = main(["--validate"])
        self.assertEqual(status, 1)
        self.assertEqual(
            captured.getvalue(),
            "line 1: Server=db1;notapair;Database=orders\n  missing '=': 'notapair'\n",
        )


class CliAliasConfigTests(unittest.TestCase):
    def test_alias_config_file_is_layered_on_top_of_built_ins(self):
        with tempfile.TemporaryDirectory() as tmp:
            alias_path = os.path.join(tmp, "aliases.conf")
            with open(alias_path, "w", encoding="utf-8") as f:
                f.write("datasource = host\nsecret = password\n")

            stdin = io.StringIO("datasource=db1;secret=hunter2\n")
            captured = io.StringIO()
            with patch("sys.stdin", stdin), contextlib.redirect_stdout(captured):
                status = main(["--alias-config", alias_path])
            self.assertEqual(status, 0)
            self.assertEqual(captured.getvalue(), "host=db1;password=hunter2\n")

    def test_missing_alias_config_file_returns_two_and_reports_error(self):
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured):
            status = main(["--alias-config", "/no/such/file.conf"])
        self.assertEqual(status, 2)
        self.assertIn("--alias-config", captured.getvalue())

    def test_malformed_alias_config_file_returns_two_and_reports_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            alias_path = os.path.join(tmp, "aliases.conf")
            with open(alias_path, "w", encoding="utf-8") as f:
                f.write("notapair\n")

            captured = io.StringIO()
            with contextlib.redirect_stderr(captured):
                status = main(["--alias-config", alias_path])
            self.assertEqual(status, 2)
            self.assertIn("line 1", captured.getvalue())


if __name__ == "__main__":
    unittest.main()
