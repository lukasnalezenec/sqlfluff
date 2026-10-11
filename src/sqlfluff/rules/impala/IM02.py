"""Implementation of Rule IM02."""

from typing import Optional

from sqlfluff.core.parser import BaseSegment, WhitespaceSegment
from sqlfluff.core.rules import BaseRule, LintFix, LintResult, RuleContext
from sqlfluff.core.rules.crawlers import SegmentSeekerCrawler

# Impala CREATE TABLE / CTAS clause order, from the CREATE TABLE statement
# reference:
# https://impala.apache.org/docs/build/html/topics/impala_create_table.html
# STORED AS, then LOCATION, then CACHED IN / UNCACHED, then TBLPROPERTIES.
_CLAUSE_ORDER: tuple[str, ...] = (
    "partitioned_by",
    "partition_by",
    "sort_by",
    "comment",
    "row_format",
    "serdeproperties",
    "stored_as",
    "location",
    "cache",
    "tblproperties",
)

_CLAUSE_LABELS: dict[str, str] = {
    "partitioned_by": "PARTITIONED BY",
    "partition_by": "PARTITION BY",
    "sort_by": "SORT BY",
    "comment": "COMMENT",
    "row_format": "ROW FORMAT",
    "serdeproperties": "WITH SERDEPROPERTIES",
    "stored_as": "STORED AS",
    "location": "LOCATION",
    "cache": "CACHED IN or UNCACHED",
    "tblproperties": "TBLPROPERTIES",
}

# Two leading keywords identify these clauses. The rest start with one.
_TWO_KEYWORD_CLAUSES: frozenset[str] = frozenset(
    {
        "partitioned_by",
        "partition_by",
        "sort_by",
        "serdeproperties",
        "stored_as",
    }
)

_INTERIOR_TYPES: tuple[str, ...] = (
    "keyword",
    "bracketed",
    "quoted_literal",
    "numeric_literal",
    "symbol",
    "comma",
    "comparison_operator",
    "raw_comparison_operator",
)


def _keyword_at(code: list[BaseSegment], index: int) -> str:
    """Return the upper-case keyword at ``index``, or an empty string."""
    if 0 <= index < len(code) and code[index].is_type("keyword"):
        return code[index].raw_upper
    return ""


def _clause_kind(code: list[BaseSegment], index: int) -> Optional[str]:
    """Return the clause that starts at ``index``, if any."""
    segment = code[index]
    if segment.is_type("row_format_clause"):
        return "row_format"

    raw = _keyword_at(code, index)
    if not raw:
        return None
    nxt = _keyword_at(code, index + 1)
    if raw == "PARTITIONED" and nxt == "BY":
        return "partitioned_by"
    if raw == "PARTITION" and nxt == "BY":
        return "partition_by"
    if raw == "SORT" and nxt == "BY":
        return "sort_by"
    if raw == "COMMENT":
        return "comment"
    if raw == "WITH" and nxt == "SERDEPROPERTIES":
        return "serdeproperties"
    if raw == "STORED" and nxt == "AS":
        return "stored_as"
    if raw == "LOCATION":
        return "location"
    if raw in {"CACHED", "UNCACHED"}:
        return "cache"
    if raw == "TBLPROPERTIES":
        return "tblproperties"
    return None


def _is_clause_interior(code: list[BaseSegment], index: int) -> bool:
    """Return whether ``code[index]`` continues the current clause."""
    if _clause_kind(code, index) is not None:
        return False
    segment = code[index]
    # CREATE TABLE AS SELECT: the statement-level AS is not part of STORED AS.
    if segment.is_type("keyword") and segment.raw_upper == "AS":
        return False
    return segment.is_type(*_INTERIOR_TYPES)


def _consume_clause(code: list[BaseSegment], index: int) -> Optional[tuple[str, int]]:
    """If a clause starts at ``index``, return its name and exclusive end."""
    kind = _clause_kind(code, index)
    if kind is None:
        return None
    cursor = index + (2 if kind in _TWO_KEYWORD_CLAUSES else 1)
    while cursor < len(code) and _is_clause_interior(code, cursor):
        cursor += 1
    return kind, cursor


def _join_clauses(
    cores: list[list[BaseSegment]],
    gaps: list[list[BaseSegment]],
    tail: list[BaseSegment],
) -> list[BaseSegment]:
    """Reassemble clause cores in caller order, keeping a separator."""
    separator = next((gap for gap in gaps if gap), None)
    if separator is None:
        separator = [WhitespaceSegment(raw=" ")]

    rejoined: list[BaseSegment] = []
    for position, core in enumerate(cores):
        if position:
            rejoined.extend(separator)
        rejoined.extend(core)
    rejoined.extend(tail)
    return rejoined


class Rule_IM02(BaseRule):
    """Impala CREATE TABLE clauses must follow the documented order.

    Impala's ``CREATE TABLE`` grammar is a fixed sequence. Among the trailing
    options the order is ``STORED AS``, then ``LOCATION``, then ``CACHED IN``
    or ``UNCACHED``, then ``TBLPROPERTIES``. ``TBLPROPERTIES`` before
    ``LOCATION`` does not parse. The same sequence applies to ``CREATE TABLE
    AS SELECT``. The full documented order is:

    ``PARTITIONED BY``, ``PARTITION BY``, ``SORT BY``, ``COMMENT``,
    ``ROW FORMAT``, ``WITH SERDEPROPERTIES``, ``STORED AS``, ``LOCATION``,
    ``CACHED IN`` or ``UNCACHED``, ``TBLPROPERTIES``.

    https://impala.apache.org/docs/build/html/topics/impala_create_table.html

    This rule only applies to the ``impala`` dialect.

    **Anti-pattern**

    ``TBLPROPERTIES`` placed before ``LOCATION``.

    .. code-block:: sql
       :force:

        CREATE EXTERNAL TABLE db.staging (
            id INT
        )
        STORED AS PARQUET
        TBLPROPERTIES ('transactional'='true')
        LOCATION '/data/staging';

    **Best practice**

    Keep the documented clause order.

    .. code-block:: sql
       :force:

        CREATE EXTERNAL TABLE db.staging (
            id INT
        )
        STORED AS PARQUET
        LOCATION '/data/staging'
        TBLPROPERTIES ('transactional'='true');

    """

    name = "impala.create_table_clause_order"
    aliases = ()
    groups = ("all", "impala")
    crawl_behaviour = SegmentSeekerCrawler(
        {"create_table_statement", "create_table_as_select_statement"}
    )
    is_fix_compatible = True

    def _eval(self, context: RuleContext) -> Optional[LintResult]:
        """Flag CREATE TABLE clauses that are not in Impala's fixed order."""
        if context.dialect.name != "impala":
            return None

        children = list(context.segment.segments)
        code_at = [idx for idx, seg in enumerate(children) if seg.is_code]
        code = [children[idx] for idx in code_at]

        found: list[tuple[str, int, int]] = []
        cursor = 0
        while cursor < len(code):
            consumed = _consume_clause(code, cursor)
            if consumed is None:
                cursor += 1
                continue
            kind, end = consumed
            found.append((kind, cursor, end))
            cursor = end

        if len(found) < 2:
            return None

        expected = sorted(found, key=lambda clause: _CLAUSE_ORDER.index(clause[0]))
        if [clause[0] for clause in found] == [clause[0] for clause in expected]:
            return None

        anchor_at = found[0][1]
        for actual, wanted in zip(found, expected):
            if actual[0] != wanted[0]:
                anchor_at = actual[1]
                break

        return LintResult(
            anchor=code[anchor_at],
            description=_describe(found, expected),
            fixes=_reorder_fixes(children, code_at, found),
        )


def _describe(
    found: list[tuple[str, int, int]],
    expected: list[tuple[str, int, int]],
) -> str:
    """Explain the actual clause order and the order Impala requires."""
    actual_labels = ", ".join(_CLAUSE_LABELS[name] for name, _, _ in found)
    expected_labels = ", ".join(_CLAUSE_LABELS[name] for name, _, _ in expected)
    return (
        "Impala CREATE TABLE clauses are out of order "
        f"({actual_labels}). Expected {expected_labels}."
    )


def _reorder_fixes(
    children: list[BaseSegment],
    code_at: list[int],
    found: list[tuple[str, int, int]],
) -> list[LintFix]:
    """Build fixes that rewrite the clause span into documented order."""
    cores: list[list[BaseSegment]] = []
    gaps: list[list[BaseSegment]] = []
    for position, (_, start, end) in enumerate(found):
        child_start = code_at[start]
        child_end = code_at[end - 1] + 1
        cores.append(children[child_start:child_end])
        if position + 1 < len(found):
            next_start = code_at[found[position + 1][1]]
            gaps.append(children[child_end:next_start])

    last_code_end = found[-1][2]
    if last_code_end < len(code_at):
        tail_end = code_at[last_code_end]
    else:
        tail_end = len(children)
    last_child_end = code_at[found[-1][2] - 1] + 1
    tail = children[last_child_end:tail_end]

    rank = {name: index for index, name in enumerate(_CLAUSE_ORDER)}
    reordered = [
        core for _, core in sorted(zip(found, cores), key=lambda item: rank[item[0][0]])
    ]

    rejoined = _join_clauses(reordered, gaps, tail)
    region_start = code_at[found[0][1]]
    region = children[region_start:tail_end]
    return [
        LintFix.replace(region[0], rejoined),
        *[LintFix.delete(segment) for segment in region[1:]],
    ]
