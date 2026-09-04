import unittest

from connstr_format import normalize, normalize_with_issues


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


class NormalizeMaskPasswordTests(unittest.TestCase):
    def test_password_is_replaced_with_placeholder(self):
        raw = "Server=db1;UID=sa;PWD=hunter2;Database=orders"
        self.assertEqual(
            normalize(raw, mask_password=True),
            "host=db1;database=orders;user=sa;password=***",
        )

    def test_placeholder_does_not_reveal_password_length(self):
        short = normalize("Server=db1;PWD=ab", mask_password=True)
        long = normalize("Server=db1;PWD=a-much-longer-password", mask_password=True)
        self.assertEqual(short.split(";")[-1], long.split(";")[-1])

    def test_no_password_field_means_no_change(self):
        raw = "Server=db1;UID=sa;Database=orders"
        self.assertEqual(normalize(raw, mask_password=True), normalize(raw))

    def test_mask_password_false_is_the_default(self):
        raw = "Server=db1;PWD=hunter2"
        self.assertEqual(normalize(raw), "host=db1;password=hunter2")

    def test_url_style_password_is_also_masked(self):
        raw = "postgres://sa:hunter2@db1/orders"
        self.assertEqual(
            normalize(raw, mask_password=True),
            "host=db1;database=orders;user=sa;password=***",
        )


class NormalizeUrlStyleTests(unittest.TestCase):
    def test_basic_postgres_url(self):
        raw = "postgres://sa:hunter2@db1:5432/orders"
        self.assertEqual(
            normalize(raw), "host=db1;port=5432;database=orders;user=sa;password=hunter2"
        )

    def test_user_without_password_and_no_port(self):
        raw = "mysql://app@db1/orders"
        self.assertEqual(normalize(raw), "host=db1;database=orders;user=app")

    def test_percent_encoded_password_is_decoded(self):
        raw = "postgres://sa:hun%40ter2@db1/orders"
        self.assertEqual(normalize(raw), "host=db1;database=orders;user=sa;password=hun@ter2")

    def test_query_string_params_become_sorted_extras(self):
        raw = "postgres://sa:pw@db1/orders?sslmode=require"
        self.assertEqual(
            normalize(raw),
            "host=db1;database=orders;user=sa;password=pw;sslmode=require",
        )

    def test_query_string_can_carry_user_and_password(self):
        raw = "jdbc:postgresql://db1:5432/orders?user=sa&password=hunter2"
        self.assertEqual(
            normalize(raw), "host=db1;port=5432;database=orders;user=sa;password=hunter2"
        )

    def test_jdbc_sqlserver_semicolon_params(self):
        raw = "jdbc:sqlserver://db1:1433;databaseName=orders;user=sa;password=hunter2"
        self.assertEqual(
            normalize(raw), "host=db1;port=1433;database=orders;user=sa;password=hunter2"
        )

    def test_bracketed_ipv6_host_with_port(self):
        raw = "postgres://[::1]:5432/orders"
        self.assertEqual(normalize(raw), "host=::1;port=5432;database=orders")

    def test_no_path_means_no_database_field(self):
        raw = "postgres://db1:5432"
        self.assertEqual(normalize(raw), "host=db1;port=5432")

    def test_no_host_means_no_host_field(self):
        raw = "postgres:///orders"
        self.assertEqual(normalize(raw), "database=orders")

    def test_url_style_and_odbc_style_can_normalize_identically(self):
        url = "postgres://sa:hunter2@db1:5432/orders"
        odbc = "Server=db1;Port=5432;UID=sa;PWD=hunter2;Database=orders"
        self.assertEqual(normalize(url), normalize(odbc))


class NormalizeWithIssuesTests(unittest.TestCase):
    def test_well_formed_input_has_no_issues(self):
        value, issues = normalize_with_issues("Server=db1;UID=sa;Database=orders")
        self.assertEqual(value, "host=db1;database=orders;user=sa")
        self.assertEqual(issues, [])

    def test_result_matches_normalize_for_well_formed_input(self):
        raw = "Server=db1;UID=sa;PWD=hunter2;Database=orders"
        value, _ = normalize_with_issues(raw)
        self.assertEqual(value, normalize(raw))

    def test_pair_without_equals_is_reported(self):
        value, issues = normalize_with_issues("Server=db1;notapair;Database=orders")
        self.assertEqual(value, "host=db1;database=orders")
        self.assertEqual(issues, ["missing '=': 'notapair'"])

    def test_pair_with_blank_key_is_reported(self):
        value, issues = normalize_with_issues("Server=db1;=value;Database=orders")
        self.assertEqual(value, "host=db1;database=orders")
        self.assertEqual(issues, ["blank key: '=value'"])

    def test_multiple_malformed_segments_are_all_reported(self):
        raw = "Server=db1;notapair;=value;Database=orders"
        _, issues = normalize_with_issues(raw)
        self.assertEqual(issues, ["missing '=': 'notapair'", "blank key: '=value'"])

    def test_mask_password_still_applies(self):
        value, issues = normalize_with_issues("Server=db1;PWD=hunter2;bad", mask_password=True)
        self.assertEqual(value, "host=db1;password=***")
        self.assertEqual(issues, ["missing '=': 'bad'"])

    def test_malformed_query_param_in_url_style_is_reported(self):
        raw = "postgres://sa:pw@db1/orders?=oops&sslmode=require"
        value, issues = normalize_with_issues(raw)
        self.assertEqual(value, "host=db1;database=orders;user=sa;password=pw;sslmode=require")
        self.assertEqual(issues, ["blank key: '=oops'"])

    def test_malformed_jdbc_tail_param_is_reported(self):
        raw = "jdbc:sqlserver://db1:1433;databaseName=orders;notapair;user=sa"
        value, issues = normalize_with_issues(raw)
        self.assertEqual(value, "host=db1;port=1433;database=orders;user=sa")
        self.assertEqual(issues, ["missing '=': 'notapair'"])


if __name__ == "__main__":
    unittest.main()
