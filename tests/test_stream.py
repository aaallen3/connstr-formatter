import io
import unittest

from connstr_format import normalize_stream, validate_stream


class NormalizeStreamTests(unittest.TestCase):
    def test_yields_one_normalized_line_per_input_line(self):
        lines = ["Server=db1;UID=sa;Database=orders", "Server=db2;UID=app;Database=orders"]
        result = list(normalize_stream(lines))
        self.assertEqual(
            result,
            ["host=db1;database=orders;user=sa", "host=db2;database=orders;user=app"],
        )

    def test_blank_lines_are_skipped_by_default(self):
        lines = ["Server=db1;UID=sa", "", "   ", "Server=db2;UID=app"]
        result = list(normalize_stream(lines))
        self.assertEqual(result, ["host=db1;user=sa", "host=db2;user=app"])

    def test_blank_lines_are_kept_when_skip_blank_is_false(self):
        lines = ["Server=db1;UID=sa", ""]
        result = list(normalize_stream(lines, skip_blank=False))
        self.assertEqual(result, ["host=db1;user=sa", ""])

    def test_trailing_newline_and_carriage_return_are_stripped(self):
        lines = ["Server=db1;UID=sa\r\n"]
        result = list(normalize_stream(lines))
        self.assertEqual(result, ["host=db1;user=sa"])

    def test_mask_password_is_forwarded_to_every_line(self):
        lines = ["Server=db1;PWD=hunter2", "Server=db2;PWD=hunter3"]
        result = list(normalize_stream(lines, mask_password=True))
        self.assertEqual(result, ["host=db1;password=***", "host=db2;password=***"])

    def test_aliases_are_forwarded_to_every_line(self):
        lines = ["datasource=db1;secret=hunter2"]
        aliases = {"datasource": "host", "secret": "password"}
        result = list(normalize_stream(lines, aliases=aliases))
        self.assertEqual(result, ["host=db1;password=hunter2"])

    def test_consumes_a_file_object_lazily(self):
        text = "Server=db1;UID=sa\nServer=db2;UID=app\n"
        result = list(normalize_stream(io.StringIO(text)))
        self.assertEqual(result, ["host=db1;user=sa", "host=db2;user=app"])

    def test_empty_input_yields_nothing(self):
        self.assertEqual(list(normalize_stream([])), [])


class ValidateStreamTests(unittest.TestCase):
    def test_well_formed_lines_yield_nothing(self):
        lines = ["Server=db1;UID=sa", "Server=db2;UID=app"]
        self.assertEqual(list(validate_stream(lines)), [])

    def test_malformed_line_is_yielded_with_its_number_and_issues(self):
        lines = ["Server=db1;UID=sa", "Server=db2;notapair"]
        result = list(validate_stream(lines))
        self.assertEqual(
            result, [(2, "Server=db2;notapair", ["missing '=': 'notapair'"])]
        )

    def test_line_numbers_are_one_based_and_count_skipped_blanks(self):
        lines = ["Server=db1;UID=sa", "", "Server=db2;notapair"]
        result = list(validate_stream(lines))
        self.assertEqual(result[0][0], 3)

    def test_only_malformed_lines_are_yielded_among_several(self):
        lines = ["Server=db1;UID=sa", "Server=db2;notapair", "Server=db3;UID=app"]
        result = list(validate_stream(lines))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], 2)

    def test_multiple_issues_on_one_line_are_all_included(self):
        lines = ["Server=db1;notapair;=value"]
        result = list(validate_stream(lines))
        self.assertEqual(
            result[0][2], ["missing '=': 'notapair'", "blank key: '=value'"]
        )

    def test_aliases_are_forwarded(self):
        lines = ["datasource=db1;notapair"]
        aliases = {"datasource": "host"}
        result = list(validate_stream(lines, aliases=aliases))
        self.assertEqual(result, [(1, "datasource=db1;notapair", ["missing '=': 'notapair'"])])

    def test_blank_lines_are_never_yielded_even_though_they_are_well_formed(self):
        lines = ["", "Server=db1;notapair"]
        result = list(validate_stream(lines))
        self.assertEqual([r[0] for r in result], [2])


if __name__ == "__main__":
    unittest.main()
