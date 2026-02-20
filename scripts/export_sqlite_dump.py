from __future__ import annotations

import argparse
import re
import sqlite3
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


EXCLUDE_DIRS = {"node_modules", ".git", "dist", "build"}
IDENT = r'(?:`[^`]+`|"[^"]+"|\[[^\]]+\]|[A-Za-z_][A-Za-z0-9_$]*)'
CREATE_TABLE_RE = re.compile(rf'^(CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?)(?P<name>{IDENT})(?P<rest>\s*\(.*)$', re.IGNORECASE)
CREATE_INDEX_RE = re.compile(
    rf'^(CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?)(?P<idx>{IDENT})(\s+ON\s+)(?P<table>{IDENT})(?P<rest>\s*\(.*)$',
    re.IGNORECASE,
)
CREATE_VIEW_RE = re.compile(rf'^(CREATE\s+VIEW\s+(?:IF\s+NOT\s+EXISTS\s+)?)(?P<name>{IDENT})(?P<rest>\s+AS\s+.*)$', re.IGNORECASE)
CREATE_TRIGGER_RE = re.compile(rf'^(CREATE\s+TRIGGER\s+(?:IF\s+NOT\s+EXISTS\s+)?)(?P<name>{IDENT})(?P<rest>\s+.*)$', re.IGNORECASE)
INSERT_INTO_RE = re.compile(rf'^(INSERT\s+INTO\s+)(?P<name>{IDENT})(?P<rest>\s+VALUES\s*\(.*)$', re.IGNORECASE)
DELETE_FROM_RE = re.compile(rf'^(DELETE\s+FROM\s+)(?P<name>{IDENT})(?P<rest>\s*;?)$', re.IGNORECASE)
D1_SKIP_PATTERNS = [
    re.compile(r"^\s*PRAGMA\b", re.IGNORECASE),
    re.compile(r"\bBEGIN\s+TRANSACTION\b", re.IGNORECASE),
    re.compile(r"\bCOMMIT\b", re.IGNORECASE),
    re.compile(r"\bROLLBACK\b", re.IGNORECASE),
    re.compile(r"\bSAVEPOINT\b", re.IGNORECASE),
    re.compile(r"\bRELEASE\s+SAVEPOINT\b", re.IGNORECASE),
    re.compile(r"\bVACUUM\b", re.IGNORECASE),
]
FTS_SKIP_PATTERNS_D1 = [
    re.compile(r"__[A-Za-z0-9_]*_fts(?:\b|_)", re.IGNORECASE),
    re.compile(r"\bfts5\b", re.IGNORECASE),
    re.compile(r"\btokenize\s*=", re.IGNORECASE),
    re.compile(r"_fts_data\b", re.IGNORECASE),
    re.compile(r"_fts_idx\b", re.IGNORECASE),
    re.compile(r"_fts_docsize\b", re.IGNORECASE),
    re.compile(r"_fts_config\b", re.IGNORECASE),
]
SQLITE_SEQUENCE_CREATE_RE = re.compile(r'^\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:"?|\[?|`?)sqlite_sequence(?:"?|\]?|`?)\b', re.IGNORECASE)
SQLITE_SEQUENCE_INSERT_RE = re.compile(r'^\s*INSERT\s+INTO\s+(?:"?|\[?|`?)sqlite_sequence(?:"?|\]?|`?)\b', re.IGNORECASE)
CREATE_TRIGGER_RE_D1 = re.compile(r"^\s*CREATE\s+TRIGGER\b", re.IGNORECASE)
CREATE_VIEW_RE_D1 = re.compile(r"^\s*CREATE\s+VIEW\b", re.IGNORECASE)
CREATE_VIRTUAL_TABLE_RE_D1 = re.compile(r"^\s*CREATE\s+VIRTUAL\s+TABLE\b", re.IGNORECASE)
SQLITE_MASTER_MUTATION_RE_D1 = re.compile(r"^\s*(INSERT\s+INTO|DELETE\s+FROM|UPDATE)\s+sqlite_master\b", re.IGNORECASE)
CREATE_OBJ_ANYWHERE_RE_D1 = re.compile(r"\bCREATE\s+(?:TRIGGER|VIEW|VIRTUAL\s+TABLE)\b", re.IGNORECASE)
END_SEMI_RE = re.compile(r"\bEND\s*;\s*$", re.IGNORECASE)


def normalize_path(p: Path) -> Path:
    return p if p.is_absolute() else (Path.cwd() / p)


def strip_ident(token: str) -> str:
    token = token.strip()
    if len(token) >= 2 and ((token[0] == '"' and token[-1] == '"') or (token[0] == "`" and token[-1] == "`")):
        return token[1:-1]
    if len(token) >= 2 and token[0] == "[" and token[-1] == "]":
        return token[1:-1]
    return token


def quote_ident(name: str, template: str) -> str:
    template = template.strip()
    if len(template) >= 2 and template[0] == '"' and template[-1] == '"':
        return f'"{name}"'
    if len(template) >= 2 and template[0] == "`" and template[-1] == "`":
        return f"`{name}`"
    if len(template) >= 2 and template[0] == "[" and template[-1] == "]":
        return f"[{name}]"
    return f'"{name}"'


def prefixed_name(raw_ident: str, prefix: str) -> str:
    name = strip_ident(raw_ident)
    if name.startswith(f"{prefix}__"):
        return quote_ident(name, raw_ident)
    return quote_ident(f"{prefix}__{name}", raw_ident)


def find_default_sources(repo_root: Path) -> Tuple[List[Path], List[Path]]:
    default_db_dir = repo_root / "database"
    primary = sorted(p for p in default_db_dir.glob("hsr_resources_*.db") if p.is_file())
    if primary:
        return primary, []

    candidates: List[Path] = []
    for p in repo_root.rglob("*.db"):
        if not p.is_file():
            continue
        rel_parts = {part.lower() for part in p.relative_to(repo_root).parts}
        if rel_parts & EXCLUDE_DIRS:
            continue
        candidates.append(p)
    candidates.sort()
    return [], candidates


def resolve_sources(args_sources: Optional[Sequence[Path]], repo_root: Path) -> Tuple[List[Path], List[Path], bool]:
    if args_sources:
        resolved: List[Path] = []
        missing: List[Path] = []
        for src in args_sources:
            p = normalize_path(src).resolve()
            if p.exists() and p.is_file():
                resolved.append(p)
            else:
                missing.append(src)
        return resolved, missing, False

    primary, candidates = find_default_sources(repo_root)
    if primary:
        return primary, [], True
    return [], candidates, True


def clone_and_prefix_db(source_db: Path, prefix: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(prefix=f"{prefix}_", suffix=".db", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    with sqlite3.connect(source_db) as src, sqlite3.connect(tmp_path) as dst:
        src.backup(dst)
        dst.execute("PRAGMA foreign_keys=OFF")
        virtual_rows = dst.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
              AND sql LIKE 'CREATE VIRTUAL TABLE%'
            """
        ).fetchall()
        virtual_names = {str(name) for (name,) in virtual_rows}

        table_rows = dst.execute(
            """
            SELECT name, sql
            FROM sqlite_master
            WHERE type='table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
        for name, sql in table_rows:
            if name in virtual_names:
                pass
            else:
                # Skip virtual-table shadow tables (e.g. fts5 *_data/_idx/_config).
                if any(name.startswith(f"{vname}_") for vname in virtual_names):
                    continue
                if not sql:
                    continue
            dst.execute(f'ALTER TABLE "{name}" RENAME TO "{prefix}__{name}"')
        dst.commit()
    return tmp_path


def rewrite_dump_line(
    line: str,
    prefix: str,
    prefix_enabled: bool,
    seen_sqlite_sequence_create: bool,
) -> Tuple[Optional[str], bool]:
    text = line.strip()
    if not text:
        return None, seen_sqlite_sequence_create
    if text.upper() in {"BEGIN TRANSACTION;", "COMMIT;"}:
        return None, seen_sqlite_sequence_create

    m = CREATE_TABLE_RE.match(text)
    if m:
        table_name = strip_ident(m.group("name"))
        if table_name.lower() == "sqlite_sequence":
            if seen_sqlite_sequence_create:
                return None, seen_sqlite_sequence_create
            seen_sqlite_sequence_create = True
            return text, seen_sqlite_sequence_create
        if prefix_enabled:
            return f'{m.group(1)}{prefixed_name(m.group("name"), prefix)}{m.group("rest")}', seen_sqlite_sequence_create
        return text, seen_sqlite_sequence_create

    m = CREATE_INDEX_RE.match(text)
    if m:
        if prefix_enabled:
            return (
                f'{m.group(1)}{prefixed_name(m.group("idx"), prefix)}{m.group(3)}{prefixed_name(m.group("table"), prefix)}{m.group("rest")}',
                seen_sqlite_sequence_create,
            )
        return text, seen_sqlite_sequence_create

    m = CREATE_VIEW_RE.match(text)
    if m:
        if prefix_enabled:
            return f'{m.group(1)}{prefixed_name(m.group("name"), prefix)}{m.group("rest")}', seen_sqlite_sequence_create
        return text, seen_sqlite_sequence_create

    m = CREATE_TRIGGER_RE.match(text)
    if m:
        if prefix_enabled:
            return f'{m.group(1)}{prefixed_name(m.group("name"), prefix)}{m.group("rest")}', seen_sqlite_sequence_create
        return text, seen_sqlite_sequence_create

    m = INSERT_INTO_RE.match(text)
    if m:
        target_name = strip_ident(m.group("name"))
        if target_name.lower() == "sqlite_sequence":
            if prefix_enabled:
                rest = m.group("rest")
                rest = re.sub(
                    r"^(\s+VALUES\s*\(\s*)'([^']+)'",
                    lambda mm: (
                        f"{mm.group(1)}'{mm.group(2)}'"
                        if mm.group(2).startswith(f"{prefix}__")
                        else f"{mm.group(1)}'{prefix}__{mm.group(2)}'"
                    ),
                    rest,
                    count=1,
                    flags=re.IGNORECASE,
                )
                return f'{m.group(1)}{m.group("name")}{rest}', seen_sqlite_sequence_create
            return text, seen_sqlite_sequence_create
        if prefix_enabled:
            return f'{m.group(1)}{prefixed_name(m.group("name"), prefix)}{m.group("rest")}', seen_sqlite_sequence_create
        return text, seen_sqlite_sequence_create

    m = DELETE_FROM_RE.match(text)
    if m and strip_ident(m.group("name")).lower() == "sqlite_sequence":
        return None, seen_sqlite_sequence_create

    return text, seen_sqlite_sequence_create


def iterdump_prefixed(source_db: Path, prefix: str, prefix_enabled: bool) -> Iterable[str]:
    if prefix_enabled:
        working_db = clone_and_prefix_db(source_db, prefix)
    else:
        working_db = source_db

    seen_sqlite_sequence_create = False
    try:
        with sqlite3.connect(working_db) as conn:
            for line in conn.iterdump():
                rewritten, seen_sqlite_sequence_create = rewrite_dump_line(
                    line=line,
                    prefix=prefix,
                    prefix_enabled=prefix_enabled,
                    seen_sqlite_sequence_create=seen_sqlite_sequence_create,
                )
                if rewritten is not None:
                    yield rewritten
    finally:
        if prefix_enabled:
            try:
                working_db.unlink(missing_ok=True)
            except Exception:
                pass


def export_merge(sources: Sequence[Path], output_sql: Path, prefix_enabled: bool) -> None:
    output_sql.parent.mkdir(parents=True, exist_ok=True)
    with output_sql.open("w", encoding="utf-8", newline="\n") as f:
        f.write("PRAGMA foreign_keys=OFF;\n")
        f.write("BEGIN TRANSACTION;\n")
        for source_db in sources:
            prefix = source_db.stem
            f.write(f"-- source: {source_db.as_posix()}\n")
            for stmt in iterdump_prefixed(source_db, prefix=prefix, prefix_enabled=prefix_enabled):
                f.write(stmt)
                if not stmt.endswith("\n"):
                    f.write("\n")
        f.write("COMMIT;\n")


def d1_filter_line(line: str, in_trigger_block: bool) -> Tuple[Optional[str], bool]:
    text = line.strip()
    if not text:
        return None, in_trigger_block

    if in_trigger_block:
        if END_SEMI_RE.search(text):
            return None, False
        return None, True

    if re.match(r"^\s*\.", line):
        return None, in_trigger_block

    for pat in FTS_SKIP_PATTERNS_D1:
        if pat.search(text):
            return None, in_trigger_block

    if CREATE_TRIGGER_RE_D1.match(text):
        if END_SEMI_RE.search(text):
            return None, False
        return None, True

    if CREATE_VIEW_RE_D1.match(text):
        return None, in_trigger_block

    if CREATE_VIRTUAL_TABLE_RE_D1.match(text):
        return None, in_trigger_block

    if SQLITE_MASTER_MUTATION_RE_D1.match(text):
        return None, in_trigger_block

    if CREATE_OBJ_ANYWHERE_RE_D1.search(text):
        return None, in_trigger_block

    if SQLITE_SEQUENCE_CREATE_RE.match(text):
        return None, in_trigger_block

    if SQLITE_SEQUENCE_INSERT_RE.match(text):
        return None, in_trigger_block

    for pat in D1_SKIP_PATTERNS:
        if pat.search(text):
            return None, in_trigger_block
    return text, in_trigger_block


def export_merge_d1_compatible(sources: Sequence[Path], output_sql: Path, prefix_enabled: bool) -> None:
    output_sql.parent.mkdir(parents=True, exist_ok=True)
    with output_sql.open("w", encoding="utf-8", newline="\n") as f:
        in_trigger_block = False
        for source_db in sources:
            prefix = source_db.stem
            f.write(f"-- source: {source_db.as_posix()}\n")
            for stmt in iterdump_prefixed(source_db, prefix=prefix, prefix_enabled=prefix_enabled):
                lines = stmt.splitlines() or [stmt]
                for one_line in lines:
                    filtered, in_trigger_block = d1_filter_line(one_line, in_trigger_block)
                    if filtered is None:
                        continue
                    f.write(filtered)
                    if not filtered.endswith("\n"):
                        f.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export SQLite dump for Cloudflare D1 import.")
    parser.add_argument(
        "--source",
        type=Path,
        action="append",
        default=None,
        help="SQLite DB path. Can be used multiple times.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("dump_all.sql"),
        help="Output SQL file path (default: dump_all.sql)",
    )
    parser.add_argument(
        "--no-prefix",
        action="store_true",
        help="Disable object prefix rewrite. Only valid for a single source DB.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    sources, aux_list, auto_mode = resolve_sources(args.source, repo_root=repo_root)

    if args.source and aux_list:
        print("Error: some --source files do not exist:")
        for p in aux_list[:15]:
            print(f"  - {p}")
        return 2

    if not sources:
        print("Error: no SQLite DB found.")
        if auto_mode:
            print("Searched pattern: database/hsr_resources_*.db")
            print("Fallback candidates (*.db, recursive, excluded node_modules/.git/dist/build):")
            if aux_list:
                for p in aux_list[:15]:
                    print(f"  - {p.relative_to(repo_root)}")
            else:
                print("  (none)")
        return 2

    if args.no_prefix and len(sources) != 1:
        print("Error: --no-prefix is only allowed when exporting exactly one DB.")
        return 2

    use_prefix = not args.no_prefix and len(sources) >= 1
    output_path = normalize_path(args.out).resolve()
    d1_output_path = (repo_root / "dump_all_d1.sql").resolve()
    try:
        export_merge(sources=sources, output_sql=output_path, prefix_enabled=use_prefix)
        export_merge_d1_compatible(sources=sources, output_sql=d1_output_path, prefix_enabled=use_prefix)
    except Exception as exc:
        print(f"Error: export failed: {exc}")
        return 1

    print(f"Dump exported: {output_path}")
    print(f"D1-compatible dump exported: {d1_output_path}")
    print("Exported DB files:")
    for p in sources:
        print(f"  - {p}")
    print("Import into D1:")
    print(f"  wrangler d1 execute hsrdb --file={output_path}")
    print("Remote import (recommended, D1-compatible):")
    print("  wrangler --config cf_worker/wrangler.jsonc d1 execute hsrdb --remote --file=.\\dump_all_d1.sql")
    print("已在 dump_all_d1.sql 中跳过 FTS 相关对象；如需全文检索请在 Worker 里改用 LIKE 降级或后续再实现 FTS。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
