import sqlglot
from sqlglot import exp


class UnsafeSQLError(Exception):
    """Raised whenever AI-generated SQL fails the safety checks below."""


FORBIDDEN_NODES = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create)


def validate_and_limit(sql: str, max_rows: int) -> str:
    """
    Enforces that generated SQL is exactly one read-only SELECT statement,
    and caps the returned rows at max_rows. Raises UnsafeSQLError on
    anything else — multiple statements (blocks `; DROP TABLE ...`
    injection), any write/DDL keyword, or a non-SELECT query.
    """
    statements = [s for s in sqlglot.parse(sql, read="mysql") if s is not None]

    if len(statements) != 1:
        raise UnsafeSQLError("Only a single SELECT statement is allowed per query.")

    tree = statements[0]
    if not isinstance(tree, exp.Select):
        raise UnsafeSQLError("Only SELECT statements are allowed.")

    if tree.find(*FORBIDDEN_NODES):
        raise UnsafeSQLError("Write or schema-changing operations are not permitted.")

    existing_limit = tree.args.get("limit")
    needs_cap = existing_limit is None
    if existing_limit is not None:
        try:
            needs_cap = int(existing_limit.expression.this) > max_rows
        except Exception:
            needs_cap = True

    if needs_cap:
        tree.set("limit", exp.Limit(expression=exp.Literal.number(max_rows)))

    return tree.sql(dialect="mysql")


def add_execution_time_hint(sql: str, timeout_seconds: int) -> str:
    """Adds a MySQL optimizer hint capping server-side execution time."""
    if sql.strip().upper().startswith("SELECT"):
        hint = f"/*+ MAX_EXECUTION_TIME({timeout_seconds * 1000}) */"
        return "SELECT " + hint + sql.strip()[6:]
    return sql
