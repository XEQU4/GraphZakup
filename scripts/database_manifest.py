"""Read-only PostgreSQL data and schema fingerprints for deployment recovery.

This helper runs in the application image. --native explicitly permits reading
the repository .env for a native-to-container transfer. Reports contain hashes
and schema metadata, never row values or connection credentials.
"""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backup_database import (  # noqa: E402
    BackupError, HASH_SCHEME, ROOT, configure_snapshot, database_config,
    safe_output_directory, table_metadata,
)

MANIFEST_VERSION = 1


def canonical_index_definition(definition):
    """Normalise PostgreSQL's equivalent varchar-literal array cast rewrite.

    pg_dump/restore can distribute an unbounded varchar[] -> text[] cast into
    text casts of each literal. Values, order and all other SQL remain intact.
    Bounded varchar casts, expressions and custom types are never normalised.
    """
    # Work only outside quoted values/identifiers. A literal can itself contain
    # cast-looking SQL, which must never become executable normalisation input.
    if re.search(r"\b(?:E|U&)['\"]", definition, flags=re.IGNORECASE):
        return definition
    prefix = "__iz2_sql_literal_"
    while prefix in definition:
        prefix += "x"
    quoted = {}

    def protect(match):
        kind = "s" if match.group(0).startswith("'") else "i"
        token = prefix + kind + str(len(quoted)) + "__"
        quoted[token] = match.group(0)
        return token

    definition = re.sub(r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"", protect, definition)
    literal = re.escape(prefix) + r"s[0-9]+__"
    varchar_item = literal + r"::character varying"
    definition = re.sub(
        r"\(ARRAY\[((?:" + varchar_item + r")(?:, " + varchar_item + r")*)\]\)::text\[\]",
        lambda match: "ARRAY[" + re.sub("(" + literal + r")::character varying",
                                        r"\1::text", match.group(1)) + "]",
        definition,
    )
    definition = re.sub(r"\((" + literal + r")::character varying\)::text", r"\1::text", definition)
    for token, value in quoted.items():
        definition = definition.replace(token, value)
    return definition


def structure_metadata(connection, sql):
    """Keep definitions and sequence state; omit environment-specific role names."""
    queries = {
        "schemas": "SELECT nspname FROM pg_namespace WHERE nspname !~ '^pg_' "
                   "AND nspname <> 'information_schema' ORDER BY 1",
        "relations": "SELECT n.nspname,c.relname,c.relkind FROM pg_class c "
                     "JOIN pg_namespace n ON n.oid=c.relnamespace "
                     "WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema' "
                     "ORDER BY 1,2",
        "defaults": "SELECT n.nspname,c.relname,a.attname,pg_get_expr(d.adbin,d.adrelid) "
                    "FROM pg_attrdef d JOIN pg_class c ON c.oid=d.adrelid "
                    "JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=d.adnum "
                    "WHERE n.nspname='public' ORDER BY 1,2,3",
        "constraints": "SELECT n.nspname,c.relname,k.conname,k.contype,"
                       "pg_get_constraintdef(k.oid),k.convalidated,k.condeferrable,k.condeferred "
                       "FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid "
                       "JOIN pg_namespace n ON n.oid=c.relnamespace "
                       "WHERE n.nspname='public' ORDER BY 1,2,3",
        "indexes": "SELECT n.nspname,c.relname,i.relname,pg_get_indexdef(x.indexrelid),"
                   "x.indisvalid,x.indisready FROM pg_index x "
                   "JOIN pg_class c ON c.oid=x.indrelid JOIN pg_class i ON i.oid=x.indexrelid "
                   "JOIN pg_namespace n ON n.oid=c.relnamespace "
                   "WHERE n.nspname='public' ORDER BY 1,2,3",
        "routines": "SELECT n.nspname,p.proname,pg_get_function_identity_arguments(p.oid) "
                    "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                    "WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema' "
                    "ORDER BY 1,2,3",
        "extensions": "SELECT extname,extversion FROM pg_extension ORDER BY 1",
    }
    result = {}
    with connection.cursor() as cursor:
        for key, query in queries.items():
            cursor.execute(query)
            # Host database collations can differ (Windows -> Linux). Metadata
            # names are compared in Python code-point order on both platforms.
            result[key] = sorted(list(row) for row in cursor.fetchall())
        for index in result["indexes"]:
            index[3] = canonical_index_definition(index[3])
        cursor.execute(
            "SELECT n.nspname,c.relname,format_type(s.seqtypid,NULL),s.seqstart,"
            "s.seqincrement,s.seqmax,s.seqmin,s.seqcache,s.seqcycle "
            "FROM pg_sequence s JOIN pg_class c ON c.oid=s.seqrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' ORDER BY 1,2"
        )
        sequences = cursor.fetchall()
        result["sequences"] = {}
        for schema, name, *definition in sequences:
            cursor.execute(sql.SQL("SELECT last_value,is_called FROM {}")
                           .format(sql.Identifier(schema, name)))
            result["sequences"][schema + "." + name] = {
                "definition": definition, "state": list(cursor.fetchone()),
            }
    return result


def capture(config):
    import psycopg2
    from psycopg2 import sql

    connection = psycopg2.connect(**config, connect_timeout=10)
    try:
        configure_snapshot(connection)
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('server_version_num')::int")
            major = cursor.fetchone()[0] // 10000
        structure = structure_metadata(connection, sql)
        if structure["schemas"] != [["public"]] or structure["routines"]:
            raise BackupError("unsupported_custom_schema_or_routine")
        if any(row[2] not in {"r", "p", "i", "I", "S"} for row in structure["relations"]):
            raise BackupError("unsupported_relation_type")
        with tempfile.TemporaryDirectory(prefix="iz2-db-manifest-") as temporary:
            tables = table_metadata(connection, Path(temporary), sql)
        return {"manifest_version": MANIFEST_VERSION, "hash_scheme": HASH_SCHEME,
                "postgres_major": major, "tables": tables, "structure": structure}
    finally:
        connection.rollback()
        connection.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--output", type=Path)
    options = parser.parse_args(argv)
    try:
        values = dict(os.environ)
        if options.native:
            from dotenv import dotenv_values
            values = {**dotenv_values(ROOT / ".env"), **values}
        result = capture(database_config(values))
        payload = json.dumps(result, ensure_ascii=False, sort_keys=True)
        if options.output:
            directory = safe_output_directory(options.output.parent)
            directory.mkdir(parents=True, exist_ok=True)
            with options.output.open("x", encoding="utf-8") as stream:
                stream.write(payload + "\n")
            print(json.dumps({"status": "passed", "tables": len(result["tables"]),
                              "sequences": len(result["structure"]["sequences"])}))
        else:
            print(payload)
        return 0
    except Exception as error:
        print(json.dumps({"status": "failed", "code": str(error)
                          if isinstance(error, BackupError) else type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
