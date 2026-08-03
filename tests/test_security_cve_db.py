from port_scanner.security import cve_db
from port_scanner.security.models import Vulnerability


def _vuln(cve_id="CVE-2024-0001"):
    return Vulnerability(
        cve_id=cve_id,
        description="Test description.",
        cvss_score=9.8,
        cvss_version="3.1",
        fixed_version="9.8",
        references=("https://example.com/advisory",),
        source="test",
    )


class TestConnect:
    def test_creates_parent_directory_and_schema(self, tmp_path):
        db_path = tmp_path / "nested" / "cve.db"

        with cve_db.connect(db_path) as conn:
            # The schema must exist and be queryable — no exception.
            conn.execute("SELECT COUNT(*) FROM cached_vulnerabilities")

        assert db_path.exists()


class TestUpsertAndQuery:
    def test_round_trips_a_record(self, tmp_path):
        db_path = tmp_path / "cve.db"
        vuln = _vuln()

        with cve_db.connect(db_path) as conn:
            cve_db.upsert(conn, vuln, "openssh", "9.0", True, "9.7", False)

        with cve_db.connect(db_path) as conn:
            records = cve_db.query_by_product(conn, "openssh")

        assert len(records) == 1
        record = records[0]
        assert record.vulnerability.cve_id == "CVE-2024-0001"
        assert record.vulnerability.references == ("https://example.com/advisory",)
        assert record.version_start == (9, 0)
        assert record.version_start_inclusive is True
        assert record.version_end == (9, 7)
        assert record.version_end_inclusive is False

    def test_query_is_case_insensitive_on_product(self, tmp_path):
        db_path = tmp_path / "cve.db"
        with cve_db.connect(db_path) as conn:
            cve_db.upsert(conn, _vuln(), "OpenSSH", None, True, None, True)

        with cve_db.connect(db_path) as conn:
            records = cve_db.query_by_product(conn, "openssh")

        assert len(records) == 1

    def test_query_for_unknown_product_is_empty(self, tmp_path):
        db_path = tmp_path / "cve.db"
        with cve_db.connect(db_path) as conn:
            records = cve_db.query_by_product(conn, "nginx")

        assert records == []

    def test_repeat_upsert_replaces_rather_than_duplicates(self, tmp_path):
        db_path = tmp_path / "cve.db"
        vuln = _vuln()

        with cve_db.connect(db_path) as conn:
            cve_db.upsert(conn, vuln, "openssh", "9.0", True, "9.7", False)
            cve_db.upsert(conn, vuln, "openssh", "9.0", True, "9.7", False)
            records = cve_db.query_by_product(conn, "openssh")

        assert len(records) == 1

    def test_unbounded_range_round_trips_as_none(self, tmp_path):
        db_path = tmp_path / "cve.db"
        with cve_db.connect(db_path) as conn:
            cve_db.upsert(conn, _vuln(), "openssh", None, True, None, True)
            records = cve_db.query_by_product(conn, "openssh")

        assert records[0].version_start is None
        assert records[0].version_end is None
