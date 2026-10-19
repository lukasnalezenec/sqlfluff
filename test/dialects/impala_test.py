"""Tests specific to the Impala dialect."""

import pytest

from sqlfluff.core import Linter


@pytest.mark.xfail(
    strict=True,
    reason="Impala 2.8+ allows comparison operators in DROP/SET partition clauses",
)
def test_drop_partition_with_comparison_operator() -> None:
    """ALTER TABLE DROP PARTITION accepts a comparison operator."""
    parsed = Linter(dialect="impala").parse_string(
        "alter table db.t drop partition (k < 1);"
    )
    assert parsed.tree is not None
    assert not parsed.violations


@pytest.mark.xfail(
    strict=True,
    reason="Null-safe equality operator <=> is not parsed",
)
def test_null_safe_equality_operator() -> None:
    """The <=> operator is an alias for IS NOT DISTINCT FROM."""
    parsed = Linter(dialect="impala").parse_string(
        "select a from t x join u y on x.a <=> y.a;"
    )
    assert parsed.tree is not None
    assert not parsed.violations


def test_comment_after_stored_as_kudu_is_rejected() -> None:
    """The Kudu table COMMENT must precede STORED AS KUDU."""
    parsed = Linter(dialect="impala").parse_string(
        "create table db.t (a int, primary key (a)) partition by range (a) "
        "(partition value = 1) stored as kudu comment 'x';"
    )
    assert parsed.tree is not None
    assert list(parsed.tree.recursive_crawl("unparsable"))
