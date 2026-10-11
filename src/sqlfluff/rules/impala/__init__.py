"""The Impala rules plugin bundle.

Rules here apply to the Apache Impala dialect. They flag SQL that parses in
this dialect only so the linter can explain it, but that Impala itself rejects.
"""

from sqlfluff.core.plugin import hookimpl
from sqlfluff.core.rules import BaseRule


@hookimpl
def get_rules() -> list[type[BaseRule]]:
    """Get plugin rules.

    NOTE: Rules are imported only on fetch to manage import times
    when rules aren't used.
    """
    from sqlfluff.rules.impala.IM01 import Rule_IM01
    from sqlfluff.rules.impala.IM02 import Rule_IM02

    return [Rule_IM01, Rule_IM02]
