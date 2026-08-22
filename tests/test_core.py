import unittest

from connstr_format import normalize


class NormalizeBasicsTests(unittest.TestCase):
    def test_known_aliases_map_to_canonical_names(self):
        raw = "Server=myServer;UID=sa;PWD=hunter2;Database=myDb"
        self.assertEqual(
            normalize(raw), "host=myServer;database=myDb;user=sa;password=hunter2"
        )

    def test_different_spellings_normalize_identically(self):
        a = "Server=db1;UID=sa;PWD=hunter2;Database=orders"
        b = "data source=db1; user id=sa; pwd=hunter2; database=orders"
        self.assertEqual(normalize(a), normalize(b))

    def test_unknown_keys_are_kept_lowercased_and_sorted(self):
        raw = "Server=db1;Encrypt=true;AppName=myApp"
        self.assertEqual(normalize(raw), "host=db1;appname=myApp;encrypt=true")

    def test_empty_string_returns_empty_string(self):
        self.assertEqual(normalize(""), "")


class NormalizeQuotedValueTests(unittest.TestCase):
    def test_semicolon_inside_single_quotes_is_preserved(self):
        raw = "Server=db1;Password='a;b'"
        self.assertEqual(normalize(raw), "host=db1;password=a;b")

    def test_equals_inside_double_quotes_is_preserved(self):
        raw = 'Server=db1;Password="a=b"'
        self.assertEqual(normalize(raw), "host=db1;password=a=b")

    def test_unquoted_value_with_matching_leading_trailing_char_only(self):
        # A single character alone isn't treated as a quote pair.
        raw = "Server=db1;AppName='"
        self.assertEqual(normalize(raw), "host=db1;appname='")

    def test_unterminated_quote_consumes_rest_of_string(self):
        # No closing quote: everything after it, including further ';'
        # and '=' characters, becomes part of the value.
        raw = "Server=db1;Password='a;Database=b"
        self.assertEqual(normalize(raw), "host=db1;password='a;Database=b")


class NormalizeMalformedPairTests(unittest.TestCase):
    def test_pair_without_equals_is_skipped(self):
        raw = "Server=db1;notapair;Database=orders"
        self.assertEqual(normalize(raw), "host=db1;database=orders")

    def test_pair_with_blank_key_is_skipped(self):
        raw = "Server=db1;=value;Database=orders"
        self.assertEqual(normalize(raw), "host=db1;database=orders")

    def test_pair_with_whitespace_only_key_is_skipped(self):
        raw = "Server=db1;   =value;Database=orders"
        self.assertEqual(normalize(raw), "host=db1;database=orders")

    def test_pair_with_empty_value_is_kept(self):
        raw = "Server=db1;Database="
        self.assertEqual(normalize(raw), "host=db1;database=")

    def test_blank_segments_from_stray_semicolons_are_ignored(self):
        raw = ";;Server=db1;;Database=orders;;"
        self.assertEqual(normalize(raw), "host=db1;database=orders")

    def test_surrounding_whitespace_on_pairs_is_stripped(self):
        raw = "  Server = db1 ; Database = orders  "
        self.assertEqual(normalize(raw), "host=db1;database=orders")


class NormalizeDuplicateKeyTests(unittest.TestCase):
    def test_last_occurrence_of_a_duplicate_key_wins(self):
        raw = "Server=db1;Server=db2"
        self.assertEqual(normalize(raw), "host=db2")

    def test_last_occurrence_wins_across_aliases_of_the_same_field(self):
        raw = "Server=db1;Data Source=db2"
        self.assertEqual(normalize(raw), "host=db2")


if __name__ == "__main__":
    unittest.main()
