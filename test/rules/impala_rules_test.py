"""Coverage for Impala clause-order helpers that SQL fixtures do not reach."""

from sqlfluff.core import Linter
from sqlfluff.core.parser import KeywordSegment
from sqlfluff.rules.impala.IM02 import _is_clause_interior, _join_clauses


def test_select_statement_is_not_clause_interior() -> None:
    """A following statement is not part of a CREATE TABLE clause."""
    parsed = Linter(dialect="impala").parse_string(
        "CREATE TABLE t STORED AS PARQUET AS SELECT 1"
    )
    assert parsed.tree is not None
    create = next(parsed.tree.recursive_crawl("create_table_as_select_statement"))
    code = [segment for segment in create.segments if segment.is_code]
    select_at = next(
        index
        for index, segment in enumerate(code)
        if segment.is_type("select_statement")
    )
    assert _is_clause_interior(code, select_at) is False


def test_join_clauses_inserts_space_when_gap_is_empty() -> None:
    """Adjacent clauses still need a separator when the source has none."""
    left = [KeywordSegment(raw="LOCATION")]
    right = [KeywordSegment(raw="TBLPROPERTIES")]
    joined = _join_clauses([left, right], [[]], [])
    assert "".join(segment.raw for segment in joined) == "LOCATION TBLPROPERTIES"
