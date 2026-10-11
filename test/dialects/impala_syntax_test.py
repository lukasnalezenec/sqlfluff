"""Live Impala checks for clause order.

These tests execute SQL against a local Impala coordinator (HiveServer2) and
record which clause permutations the server accepts. Install ``impyla`` and
point the tests at the coordinator with ``IMPALA_HOST`` and ``IMPALA_PORT``
(defaults: ``127.0.0.1`` and ``21050``).

Kudu ``UPDATE`` and ``DELETE`` need a Kudu master already configured on that
Impala (``--kudu_master_hosts``). Tablet replication is set to 1 so a
single-node master can create the tables.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest

pytestmark = pytest.mark.integration

_DATABASE = "syntax_order_lab"
_SYNTAX_MARKERS = ("syntax", "parse")


@dataclass
class ImpalaSession:
    """Open Impala cursor plus the warehouse path for DDL tests."""

    connection: Any
    cursor: Any
    warehouse: str

    def execute(self, sql: str) -> list[tuple[Any, ...]]:
        """Run one statement and drain any result set."""
        self.cursor.execute(sql)
        if self.cursor.description is None:
            return []
        rows = self.cursor.fetchall()
        return list(rows)

    def reseed_kudu(self) -> None:
        """Restore the Kudu rows that DML cases mutate."""
        self.execute(
            "UPSERT INTO kudu_target (id, name) VALUES (1, 'old'), (2, 'keep')"
        )
        self.execute("UPSERT INTO kudu_lookup (id, name) VALUES (1, 'new')")


def _assert_outcome(session: ImpalaSession, sql: str, outcome: str) -> None:
    """Succeed, or require a parse/syntax error from Impala."""
    if outcome == "ok":
        session.execute(sql)
        return

    from impala.error import HiveServer2Error

    with pytest.raises(HiveServer2Error) as caught:
        session.execute(sql)
    message = str(caught.value).lower()
    assert any(marker in message for marker in _SYNTAX_MARKERS), message


@pytest.fixture(scope="module")
def impala_session() -> Iterator[ImpalaSession]:
    """Connect, pin a one-node plan, and create the non-Kudu lab tables."""
    pytest.importorskip("impala.dbapi")
    from impala.dbapi import connect
    from thrift.transport.TTransport import TTransportException

    host = os.environ.get("IMPALA_HOST", "127.0.0.1")
    port = int(os.environ.get("IMPALA_PORT", "21050"))
    try:
        connection = connect(
            host=host,
            port=port,
            auth_mechanism="NOSASL",
            timeout=30,
        )
    except (OSError, TTransportException) as exc:
        pytest.skip(f"Impala is not reachable at {host}:{port}: {exc}")

    cursor = connection.cursor()
    session = ImpalaSession(connection, cursor, warehouse="")
    try:
        session.execute("SET NUM_NODES=1")
        session.execute("SET DISABLE_CODEGEN=1")
        session.execute(f"CREATE DATABASE IF NOT EXISTS {_DATABASE}")
        session.execute(f"USE {_DATABASE}")
        described = session.execute(f"DESCRIBE DATABASE {_DATABASE}")
        session.warehouse = described[0][1].rstrip("/")
        for statement in _LAB_TABLES:
            session.execute(statement)
        yield session
    finally:
        try:
            cursor.execute("USE default")
            cursor.execute(f"DROP DATABASE IF EXISTS {_DATABASE} CASCADE")
        finally:
            cursor.close()
            connection.close()


@pytest.fixture(scope="module")
def kudu_session(impala_session: ImpalaSession) -> ImpalaSession:
    """Create the Kudu tables used by UPDATE and DELETE."""
    for statement in _KUDU_TABLES:
        impala_session.execute(statement)
    impala_session.reseed_kudu()
    return impala_session


_LAB_TABLES: tuple[str, ...] = (
    "DROP TABLE IF EXISTS src_rows",
    """
    CREATE TABLE src_rows (
        id INT,
        name STRING
    )
    STORED AS TEXTFILE
    """,
    "INSERT INTO src_rows (id, name) VALUES (1, 'a')",
    "DROP TABLE IF EXISTS insert_rows",
    """
    CREATE TABLE insert_rows (
        id INT,
        name STRING
    )
    STORED AS TEXTFILE
    """,
    "DROP TABLE IF EXISTS insert_part",
    """
    CREATE TABLE insert_part (
        id INT,
        name STRING
    )
    PARTITIONED BY (dt STRING)
    STORED AS PARQUET
    """,
)

_KUDU_TABLES: tuple[str, ...] = (
    "DROP TABLE IF EXISTS kudu_target",
    """
    CREATE TABLE kudu_target (
        id BIGINT,
        name STRING,
        PRIMARY KEY (id)
    )
    PARTITION BY HASH PARTITIONS 2
    STORED AS KUDU
    TBLPROPERTIES ('kudu.num_tablet_replicas'='1')
    """,
    "DROP TABLE IF EXISTS kudu_lookup",
    """
    CREATE TABLE kudu_lookup (
        id BIGINT,
        name STRING,
        PRIMARY KEY (id)
    )
    PARTITION BY HASH PARTITIONS 2
    STORED AS KUDU
    TBLPROPERTIES ('kudu.num_tablet_replicas'='1')
    """,
)


@pytest.mark.parametrize(
    ("sql", "outcome"),
    [
        pytest.param(
            """
            SELECT src.id
            FROM src_rows src
            JOIN src_rows other ON src.id = other.id
            WHERE src.id > 0
            GROUP BY src.id
            HAVING COUNT(*) >= 0
            ORDER BY src.id
            LIMIT 10
            OFFSET 0
            """,
            "ok",
            id="canonical",
        ),
        pytest.param(
            """
            SELECT id
            FROM src_rows
            ORDER BY id
            OFFSET 0
            LIMIT 10
            """,
            "syntax",
            id="offset_before_limit",
        ),
        pytest.param(
            """
            SELECT id
            FROM src_rows
            HAVING COUNT(*) > 0
            GROUP BY id
            """,
            "syntax",
            id="having_before_group_by",
        ),
        pytest.param(
            """
            SELECT id
            FROM src_rows
            GROUP BY id
            ORDER BY id
            HAVING COUNT(*) > 0
            """,
            "syntax",
            id="order_by_before_having",
        ),
        pytest.param(
            "SELECT id FROM src_rows SORT BY id",
            "syntax",
            id="hive_sort_by",
        ),
        pytest.param(
            "SELECT id FROM src_rows DISTRIBUTE BY id",
            "syntax",
            id="hive_distribute_by",
        ),
    ],
)
def test_select_ordering(impala_session: ImpalaSession, sql: str, outcome: str) -> None:
    """SELECT clauses follow FROM, JOIN, WHERE, GROUP BY, HAVING, ORDER BY, LIMIT, OFFSET."""
    if outcome == "ok":
        rows = impala_session.execute(sql)
        assert rows == [(1,)]
        return
    _assert_outcome(impala_session, sql, outcome)


@pytest.mark.parametrize(
    ("table_name", "sql", "outcome"),
    [
        pytest.param(
            "ddl_canonical",
            """
            CREATE TABLE ddl_canonical (
                id INT,
                name STRING
            )
            PARTITIONED BY (dt STRING)
            SORT BY (id)
            COMMENT 'order test'
            ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
            STORED AS PARQUET
            LOCATION '{location}/ddl_canonical'
            TBLPROPERTIES ('purpose'='clause-order')
            """,
            "ok",
            id="canonical",
        ),
        pytest.param(
            "ddl_location_before_stored",
            """
            CREATE TABLE ddl_location_before_stored (id INT)
            LOCATION '{location}/ddl_location_before_stored'
            STORED AS PARQUET
            """,
            "syntax",
            id="location_before_stored_as",
        ),
        pytest.param(
            "ddl_props_before_location",
            """
            CREATE TABLE ddl_props_before_location (id INT)
            STORED AS PARQUET
            TBLPROPERTIES ('purpose'='clause-order')
            LOCATION '{location}/ddl_props_before_location'
            """,
            "syntax",
            id="tblproperties_before_location",
        ),
        pytest.param(
            "ddl_sort_after_stored",
            """
            CREATE TABLE ddl_sort_after_stored (id INT)
            STORED AS PARQUET
            SORT BY (id)
            """,
            "syntax",
            id="sort_by_after_stored_as",
        ),
        pytest.param(
            "ddl_comment_after_stored",
            """
            CREATE TABLE ddl_comment_after_stored (id INT)
            STORED AS PARQUET
            COMMENT 'late'
            """,
            "syntax",
            id="comment_after_stored_as",
        ),
    ],
)
def test_create_table_ordering(
    impala_session: ImpalaSession,
    table_name: str,
    sql: str,
    outcome: str,
) -> None:
    """CREATE TABLE options follow the fixed Impala sequence through TBLPROPERTIES."""
    if outcome == "ok":
        impala_session.execute(f"DROP TABLE IF EXISTS {table_name}")
    formatted = sql.format(location=impala_session.warehouse)
    try:
        _assert_outcome(impala_session, formatted, outcome)
    finally:
        if outcome == "ok":
            impala_session.execute(f"DROP TABLE IF EXISTS {table_name}")


@pytest.mark.parametrize(
    ("sql", "outcome"),
    [
        pytest.param(
            """
            WITH cte AS (SELECT 1 AS id, 'a' AS name)
            INSERT /* +SHUFFLE */ INTO insert_part (id, name)
            PARTITION (dt='2020-01-01')
            SELECT id, name FROM cte
            """,
            "ok",
            id="with_shuffle_partition_select",
        ),
        pytest.param(
            """
            WITH cte AS (SELECT 2 AS id, 'b' AS name)
            INSERT [SHUFFLE] INTO insert_part (id, name)
            PARTITION (dt='2020-01-02')
            SELECT id, name FROM cte
            """,
            "ok",
            id="bracket_shuffle_select",
        ),
        pytest.param(
            "INSERT INTO insert_rows (id, name) VALUES (1, 'a')",
            "ok",
            id="values",
        ),
        pytest.param(
            """
            INSERT INTO insert_part
            PARTITION (dt='2020-01-03') (id, name)
            SELECT 3, 'c'
            """,
            "syntax",
            id="partition_before_column_list",
        ),
        # Impala parses WITH on the nested SELECT after INSERT. The statement
        # runs; it is not a syntax error.
        pytest.param(
            """
            INSERT INTO insert_rows (id, name)
            WITH cte AS (SELECT 4 AS id, 'd' AS name)
            SELECT id, name FROM cte
            """,
            "ok",
            id="with_after_insert",
        ),
        # SHUFFLE hints are accepted on VALUES as well as SELECT. The planner
        # keeps the constant row and does not raise a parse error.
        pytest.param(
            "INSERT /* +SHUFFLE */ INTO insert_rows (id, name) VALUES (5, 'e')",
            "ok",
            id="shuffle_hint_on_values",
        ),
        pytest.param(
            "INSERT [SHUFFLE] INTO insert_rows (id, name) VALUES (6, 'f')",
            "ok",
            id="bracket_shuffle_hint_on_values",
        ),
    ],
)
def test_insert_ordering(impala_session: ImpalaSession, sql: str, outcome: str) -> None:
    """INSERT allows WITH and a hint before the target, then columns, then PARTITION."""
    _assert_outcome(impala_session, sql, outcome)


@pytest.mark.parametrize(
    ("sql", "outcome"),
    [
        pytest.param(
            """
            UPDATE kudu_target
            SET kudu_target.name = d.name
            FROM kudu_target, kudu_lookup d
            WHERE kudu_target.id = d.id
            """,
            "ok",
            id="update_from_where",
        ),
        pytest.param(
            """
            UPDATE kudu_target
            SET kudu_target.name = d.name
            FROM kudu_target
            JOIN kudu_lookup d ON kudu_target.id = d.id
            WHERE kudu_target.id = 1
            """,
            "ok",
            id="update_from_join",
        ),
        pytest.param(
            """
            DELETE kudu_target
            FROM kudu_target
            JOIN kudu_lookup d ON kudu_target.id = d.id
            WHERE kudu_target.id = 1
            """,
            "ok",
            id="delete_from_where",
        ),
        pytest.param(
            """
            UPDATE kudu_target
            SET kudu_target.name = 'x'
            WHERE kudu_target.id = 1
            FROM kudu_lookup d
            """,
            "syntax",
            id="update_where_before_from",
        ),
        pytest.param(
            """
            DELETE kudu_target
            WHERE kudu_target.id = 1
            FROM kudu_target
            JOIN kudu_lookup d ON kudu_target.id = d.id
            """,
            "syntax",
            id="delete_where_before_from",
        ),
    ],
)
def test_kudu_dml_ordering(kudu_session: ImpalaSession, sql: str, outcome: str) -> None:
    """Kudu UPDATE and DELETE take FROM before WHERE. The reverse does not parse."""
    kudu_session.reseed_kudu()
    _assert_outcome(kudu_session, sql, outcome)


def test_kudu_update_from_changes_row(kudu_session: ImpalaSession) -> None:
    """A parsed UPDATE ... FROM ... WHERE writes the joined Kudu row."""
    kudu_session.reseed_kudu()
    kudu_session.execute(
        """
        UPDATE kudu_target
        SET kudu_target.name = d.name
        FROM kudu_target, kudu_lookup d
        WHERE kudu_target.id = d.id
        """
    )
    rows = kudu_session.execute("SELECT name FROM kudu_target WHERE id = 1")
    assert rows == [("new",)]
