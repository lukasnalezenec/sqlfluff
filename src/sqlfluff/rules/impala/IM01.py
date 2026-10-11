"""Implementation of Rule IM01."""

from typing import Optional

from sqlfluff.core.parser import IdentifierSegment
from sqlfluff.core.rules import BaseRule, LintFix, LintResult, RuleContext
from sqlfluff.core.rules.crawlers import SegmentSeekerCrawler


def _backtick_identifier(raw: str) -> IdentifierSegment:
    """Quote an Impala identifier with backticks."""
    escaped = raw.replace("`", "``")
    return IdentifierSegment(
        raw=f"`{escaped}`",
        instance_types=("quoted_identifier", "identifier", "back_quote"),
    )


class Rule_IM01(BaseRule):
    """Impala CTE names must not be unquoted reserved words.

    Impala reserved words cannot be used as unquoted identifiers. ``HOLD`` and
    ``TREAT`` have been reserved since Impala 3, and both are reserved keywords
    in SQLFluff's Impala dialect, so an unquoted CTE of either name fails a
    strict parse. The reserved-word list is the one published in the Impala
    documentation:

    https://impala.apache.org/docs/build/html/topics/impala_reserved_words.html

    This rule only applies to the ``impala`` dialect. Quote the CTE name with
    backticks.

    **Anti-pattern**

    An unquoted reserved word used as a CTE name.

    .. code-block:: sql
       :force:

        WITH hold AS (
            SELECT 1 AS id
        ),
        treat AS (
            SELECT 2 AS id
        )
        SELECT id

    **Best practice**

    Backtick-quote any CTE name that is an Impala reserved word.

    .. code-block:: sql
       :force:

        WITH `hold` AS (
            SELECT 1 AS id
        ),
        `treat` AS (
            SELECT 2 AS id
        )
        SELECT id

    """

    name = "impala.reserved_cte_name"
    aliases = ()
    groups = ("all", "impala")
    crawl_behaviour = SegmentSeekerCrawler({"common_table_expression"})
    is_fix_compatible = True

    def _eval(self, context: RuleContext) -> Optional[LintResult]:
        """Flag unquoted reserved words used as CTE names."""
        if context.dialect.name != "impala":
            return None

        identifier = context.segment.get_child("identifier")
        # The CTE grammar always starts with an identifier.
        assert identifier is not None
        # Quoted identifiers are already valid Impala names.
        if identifier.is_type("quoted_identifier"):
            return None

        if identifier.raw_upper not in context.dialect.sets("reserved_keywords"):
            return None

        return LintResult(
            anchor=identifier,
            description=(
                f"CTE name {identifier.raw!r} is an Impala reserved word "
                "and must be backtick-quoted."
            ),
            fixes=[LintFix.replace(identifier, [_backtick_identifier(identifier.raw)])],
        )
