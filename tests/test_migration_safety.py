"""Static safety checks for Alembic migrations.

Every check here exists because the failure it catches cost a production
deploy. None of them need a database, so they run in CI in under a second and
fail the build instead of Render.

Deploy failures these encode:
  1. ADD CONSTRAINT guards that caught duplicate_object but not duplicate_table.
     A UNIQUE constraint builds an index, so a name clash raises 42P07 (the
     index), not 42710 (the constraint).
  2. A raw INSERT that omitted a NOT NULL column. create_all renders
     Column(default=False) as NOT NULL with NO database default — that default
     is applied Python-side by the ORM — so a migration INSERT cannot rely on
     it existing.
"""
from __future__ import annotations

import ast
import pathlib
import re

import pglast
import pytest

PROJ = pathlib.Path(__file__).resolve().parent.parent
VERSIONS = PROJ / "alembic" / "versions"


def _sql_statements():
    """(filename, sql) for every op.execute() literal in the migration set."""
    for p in sorted(VERSIONS.glob("0*.py")):
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call)
                    and getattr(node.func, "attr", "") == "execute"
                    and node.args and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                    and node.args[0].value.strip()):
                yield p.name, node.args[0].value


def test_every_statement_is_valid_postgres():
    """Parsed with the real PostgreSQL grammar, not a permissive dialect."""
    bad = []
    for fname, sql in _sql_statements():
        try:
            pglast.parse_sql(sql)
        except Exception as e:  # pragma: no cover - only on a real failure
            bad.append(f"{fname}: {str(e)[:120]}")
    assert not bad, "invalid SQL:\n" + "\n".join(bad)


def test_one_statement_per_execute():
    """asyncpg refuses more than one statement in a prepared execute()."""
    multi = [
        f"{fname}: {len(pglast.parse_sql(sql))} statements"
        for fname, sql in _sql_statements()
        if len(pglast.parse_sql(sql)) > 1
    ]
    assert not multi, "multi-statement execute():\n" + "\n".join(multi)


def test_add_constraint_guards_catch_both_sqlstates():
    weak = []
    for p in sorted(VERSIONS.glob("0*.py")):
        for block in re.findall(r"ADD CONSTRAINT.*?END \$\$", p.read_text(encoding="utf-8"), re.S):
            if not ("duplicate_table" in block and "duplicate_object" in block):
                weak.append(p.name)
    assert not weak, (
        "ADD CONSTRAINT guard missing a sqlstate in: " + ", ".join(sorted(set(weak)))
        + "\nA UNIQUE constraint builds an index; a clash raises duplicate_table."
    )


def test_no_handler_repeats_a_condition():
    dupes = []
    for p in sorted(VERSIONS.glob("0*.py")):
        for block in re.findall(r"EXCEPTION(.*?)END \$\$", p.read_text(encoding="utf-8"), re.S):
            conds = re.findall(r"\b(duplicate_\w+|undefined_\w+)\b", block)
            if len(conds) != len(set(conds)):
                dupes.append(f"{p.name}: {conds}")
    assert not dupes, "duplicate exception conditions:\n" + "\n".join(dupes)


def _notnull_columns_without_default() -> dict:
    tables: dict = {}
    for _, sql in _sql_statements():
        for m in re.finditer(r'CREATE TABLE IF NOT EXISTS\s+"(\w+)"\s*\((.*?)\n\s*\)', sql, re.S):
            table, body = m.group(1), m.group(2)
            cols = set()
            for line in body.splitlines():
                line = line.strip().rstrip(",")
                cm = re.match(r'"?(\w+)"?\s+.*NOT NULL', line, re.I)
                if cm and "DEFAULT" not in line.upper() and "PRIMARY KEY" not in line.upper():
                    cols.add(cm.group(1))
            tables[table] = cols
    return tables


def test_inserts_supply_every_not_null_column():
    required_by_table = _notnull_columns_without_default()
    missing = []
    for fname, sql in _sql_statements():
        m = re.search(r'INSERT INTO\s+"(\w+)"\s*\(([^)]*)\)', sql, re.S)
        if not m:
            continue
        supplied = {c.strip().strip('"') for c in m.group(2).split(",")}
        gap = required_by_table.get(m.group(1), set()) - supplied
        if gap:
            missing.append(f"{fname}: INSERT INTO {m.group(1)} omits {sorted(gap)}")
    assert not missing, (
        "\n".join(missing)
        + "\nA deployed table may have NOT NULL with no database default, "
          "because SQLAlchemy applies Column(default=...) Python-side."
    )


def test_migration_chain_is_linear():
    revs = {}
    for p in sorted(VERSIONS.glob("*.py")):
        rev = down = None
        for node in ast.parse(p.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.AnnAssign):
                name = getattr(node.target, "id", None)
                if name == "revision":
                    rev = ast.literal_eval(node.value)
                elif name == "down_revision":
                    down = ast.literal_eval(node.value)
        if rev:
            revs[rev] = down

    heads = [r for r in revs if r not in set(revs.values())]
    assert len(heads) == 1, f"expected one head, found {heads}"

    dangling = [d for d in revs.values() if d and d not in revs]
    assert not dangling, f"revisions point at missing parents: {dangling}"


@pytest.mark.parametrize("column", ["cancelAtPeriodEnd"])
def test_grandfather_insert_supplies_known_notnull_columns(column):
    """Regression: this exact column aborted a deploy."""
    billing = (VERSIONS / "015_billing.py").read_text(encoding="utf-8")
    insert = re.search(r'INSERT INTO\s+"Subscription".*?"""', billing, re.S)
    assert insert, "grandfather INSERT not found"
    assert column in insert.group(0), f"{column} missing from the INSERT column list"
