from port_scanner.security.matching import (
    compare_versions,
    cpe_product_candidates,
    in_range,
    normalize,
    parse_version,
)


class TestNormalize:
    def test_ssh_banner(self):
        result = normalize("SSH", "OpenSSH_9.6")
        assert result.product == "openssh"
        assert result.version == "9.6"

    def test_ssh_banner_with_patch_suffix(self):
        result = normalize("SSH", "OpenSSH_6.6.1p1 Ubuntu-2ubuntu2.13")
        assert result.product == "openssh"
        assert result.version.startswith("6.6.1")

    def test_http_banner_with_version(self):
        result = normalize("HTTP", "nginx/1.18.0")
        assert result == normalize("HTTP", "nginx/1.18.0")
        assert result.product == "nginx"
        assert result.version == "1.18.0"

    def test_http_banner_apache_with_trailing_comment(self):
        result = normalize("HTTP", "Apache/2.4.7 (Ubuntu)")
        assert result.product == "apache"
        assert result.version == "2.4.7"

    def test_http_banner_without_version(self):
        result = normalize("HTTP", "Caddy")
        assert result.product == "caddy"
        assert result.version is None

    def test_mysql_banner(self):
        result = normalize("MySQL", "MySQL 8.0.34")
        assert result.product == "mysql"
        assert result.version == "8.0.34"

    def test_redis_banner_with_version(self):
        result = normalize("Redis", "Redis 7.2.3")
        assert result.product == "redis"
        assert result.version == "7.2.3"

    def test_redis_banner_auth_required_has_no_version(self):
        result = normalize("Redis", "Redis (authentication required)")
        assert result.product == "redis"
        assert result.version is None

    def test_unknown_banner_returns_none(self):
        assert normalize("Unknown", "Unknown") is None

    def test_unrecognized_service_returns_none(self):
        assert normalize("DNS", "some raw bytes") is None

    def test_empty_banner_returns_none(self):
        assert normalize("SSH", "") is None


class TestCpeProductCandidates:
    def test_apache_gets_both_names(self):
        assert cpe_product_candidates("apache") == ("apache", "http_server")

    def test_unmapped_product_returns_itself_only(self):
        assert cpe_product_candidates("openssh") == ("openssh",)


class TestParseVersion:
    def test_simple_dotted_version(self):
        assert parse_version("2.4.7") == (2, 4, 7)

    def test_strips_patch_suffix(self):
        assert parse_version("9.6p1") == (9, 6)

    def test_strips_trailing_word_suffix(self):
        assert parse_version("5.7.30-log") == (5, 7, 30)

    def test_single_number(self):
        assert parse_version("9") == (9,)

    def test_none_input_returns_none(self):
        assert parse_version(None) is None

    def test_empty_string_returns_none(self):
        assert parse_version("") is None

    def test_non_numeric_returns_none(self):
        assert parse_version("unknown") is None


class TestCompareVersions:
    def test_equal(self):
        assert compare_versions((9, 6), (9, 6)) == 0

    def test_less_than(self):
        assert compare_versions((9, 5), (9, 6)) < 0

    def test_greater_than(self):
        assert compare_versions((9, 7), (9, 6)) > 0

    def test_pads_shorter_tuple_with_zeros(self):
        assert compare_versions((9,), (9, 0)) == 0
        assert compare_versions((9,), (9, 1)) < 0


class TestInRange:
    def test_within_inclusive_bounds(self):
        assert in_range((2, 4, 5), (2, 4, 0), True, (2, 4, 10), True) is True

    def test_at_exclusive_upper_bound_is_excluded(self):
        assert in_range((3, 1), None, True, (3, 1), False) is False

    def test_at_inclusive_upper_bound_is_included(self):
        assert in_range((3, 1), None, True, (3, 1), True) is True

    def test_below_lower_bound_is_excluded(self):
        assert in_range((1, 0), (2, 0), True, None, True) is False

    def test_unbounded_range_matches_anything(self):
        assert in_range((99, 0, 0), None, True, None, True) is True
