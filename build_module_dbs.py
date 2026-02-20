#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

try:
    from build_db import create_schema  # type: ignore
except Exception:
    from hsrdb.build_db import create_schema  # type: ignore

try:
    from serve import hash_text_key, load_avatar_story_index, load_light_cone_index, load_monster_index  # type: ignore
except Exception:
    from hsrdb.serve import hash_text_key, load_avatar_story_index, load_light_cone_index, load_monster_index  # type: ignore


MODULES = ("avatar", "dialogue", "mission", "item", "monster")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")


def parse_langs(raw: str) -> List[str]:
    langs = [x.strip().upper() for x in raw.split(",") if x.strip()]
    return langs if langs else ["CHS", "EN", "JP", "KR"]


def file_mb(path: Path) -> float:
    return path.stat().st_size / (1024 * 1024)


def add_hash_if_any(out: Set[str], raw: Optional[str]) -> None:
    if not raw:
        return
    h = hash_text_key(str(raw))
    if h:
        out.add(str(h))


def ensure_needed_hash_table(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TEMP TABLE IF NOT EXISTS needed_hash(hash TEXT PRIMARY KEY)")


def add_hashes_from_sql(conn: sqlite3.Connection, sql: str) -> None:
    conn.execute(f"INSERT OR IGNORE INTO needed_hash(hash) {sql}")


def add_hashes_from_iter(conn: sqlite3.Connection, hashes: Iterable[str]) -> None:
    rows = [(h,) for h in sorted(set(hashes)) if h]
    if not rows:
        return
    conn.executemany("INSERT OR IGNORE INTO needed_hash(hash) VALUES(?)", rows)


def copy_table(conn: sqlite3.Connection, table: str) -> None:
    conn.execute(f"INSERT INTO {table} SELECT * FROM src.{table}")


def copy_module_tables(conn: sqlite3.Connection, module: str) -> None:
    copy_table(conn, "meta")

    if module == "avatar":
        for t in ("avatar", "avatar_promotion", "avatar_skill", "avatar_rank"):
            copy_table(conn, t)
    elif module == "dialogue":
        # Keep dialogue shard focused on sentence text only.
        for t in ("talk_sentence", "talk_sentence_multi_voice"):
            copy_table(conn, t)
    elif module == "mission":
        for t in ("main_mission", "sub_mission", "mission_pack_link"):
            copy_table(conn, t)
        conn.execute(
            """
            INSERT INTO story_reference(
                source_path, source_group, json_path, task_type, talk_sentence_id,
                timeline_name, performance_type, performance_id, trigger_custom_string, custom_string
            )
            SELECT source_path, source_group, json_path, task_type, talk_sentence_id,
                   timeline_name, performance_type, performance_id, trigger_custom_string, custom_string
            FROM src.story_reference
            WHERE source_path LIKE 'Story/Mission/%' OR source_path LIKE 'Config/Level/Mission/%'
            """
        )
    elif module == "item":
        copy_table(conn, "item")
    elif module == "monster":
        # Monster API reads excel/json directly; this shard only needs text_map/meta.
        pass


def gather_module_hashes(conn: sqlite3.Connection, resources_root: Path, module: str) -> Set[str]:
    out: Set[str] = set()

    if module == "avatar":
        add_hashes_from_sql(conn, "SELECT name_hash FROM avatar WHERE name_hash IS NOT NULL AND name_hash != ''")
        add_hashes_from_sql(conn, "SELECT full_name_hash FROM avatar WHERE full_name_hash IS NOT NULL AND full_name_hash != ''")
        add_hashes_from_sql(conn, "SELECT name_hash FROM avatar_skill WHERE name_hash IS NOT NULL AND name_hash != ''")
        add_hashes_from_sql(conn, "SELECT desc_hash FROM avatar_skill WHERE desc_hash IS NOT NULL AND desc_hash != ''")
        add_hashes_from_sql(conn, "SELECT tag_hash FROM avatar_skill WHERE tag_hash IS NOT NULL AND tag_hash != ''")

        for row in conn.execute("SELECT name_raw, desc_raw, rank_ability_json FROM avatar_rank"):
            name_raw = row[0] if isinstance(row[0], str) else None
            desc_raw = row[1] if isinstance(row[1], str) else None
            add_hash_if_any(out, name_raw)
            add_hash_if_any(out, desc_raw)
            raw_json = row[2] if isinstance(row[2], str) else "[]"
            try:
                arr = json.loads(raw_json)
            except Exception:
                arr = []
            if isinstance(arr, list):
                for item in arr:
                    if isinstance(item, str):
                        add_hash_if_any(out, item)

        try:
            stories_by_avatar, story_name_hash_by_id = load_avatar_story_index(str(resources_root.resolve()))
            for stories in stories_by_avatar.values():
                for entry in stories:
                    val = entry.get("story_hash")
                    if isinstance(val, str):
                        add_hash_if_any(out, val)
            for val in story_name_hash_by_id.values():
                if isinstance(val, str):
                    add_hash_if_any(out, val)
        except Exception:
            pass

    elif module == "dialogue":
        add_hashes_from_sql(conn, "SELECT speaker_hash FROM talk_sentence WHERE speaker_hash IS NOT NULL AND speaker_hash != ''")
        add_hashes_from_sql(conn, "SELECT text_hash FROM talk_sentence WHERE text_hash IS NOT NULL AND text_hash != ''")

    elif module == "mission":
        add_hashes_from_sql(conn, "SELECT name_hash FROM main_mission WHERE name_hash IS NOT NULL AND name_hash != ''")
        add_hashes_from_sql(conn, "SELECT target_hash FROM sub_mission WHERE target_hash IS NOT NULL AND target_hash != ''")
        add_hashes_from_sql(conn, "SELECT description_hash FROM sub_mission WHERE description_hash IS NOT NULL AND description_hash != ''")

    elif module == "item":
        add_hashes_from_sql(conn, "SELECT item_name_hash FROM item WHERE item_name_hash IS NOT NULL AND item_name_hash != ''")
        add_hashes_from_sql(conn, "SELECT item_desc_hash FROM item WHERE item_desc_hash IS NOT NULL AND item_desc_hash != ''")
        add_hashes_from_sql(conn, "SELECT item_bg_desc_hash FROM item WHERE item_bg_desc_hash IS NOT NULL AND item_bg_desc_hash != ''")
        try:
            lc_index = load_light_cone_index(str(resources_root.resolve()))
            for entry in lc_index.values():
                levels = entry.get("levels") or []
                for lv in levels:
                    if not isinstance(lv, dict):
                        continue
                    for key in ("skill_name_hash", "skill_desc_hash"):
                        val = lv.get(key)
                        if isinstance(val, str):
                            add_hash_if_any(out, val)
        except Exception:
            pass

    elif module == "monster":
        try:
            idx = load_monster_index(str(resources_root.resolve()))
            for item in idx.get("items") or []:
                if not isinstance(item, dict):
                    continue
                for key in ("name_hash", "introduction_hash"):
                    val = item.get(key)
                    if isinstance(val, str):
                        add_hash_if_any(out, val)
                for raw in item.get("ability_name_keys") or []:
                    if isinstance(raw, str):
                        add_hash_if_any(out, raw)
            for skill in (idx.get("skills") or {}).values():
                if not isinstance(skill, dict):
                    continue
                for key in ("name_hash", "desc_hash", "type_desc_hash", "tag_hash"):
                    val = skill.get(key)
                    if isinstance(val, str):
                        add_hash_if_any(out, val)
        except Exception:
            pass

    return out


def copy_text_map_for_hashes(conn: sqlite3.Connection, langs: List[str]) -> int:
    placeholders = ",".join("?" for _ in langs)
    conn.execute(
        f"""
        INSERT INTO text_map(lang, hash, text)
        SELECT tm.lang, tm.hash, tm.text
        FROM src.text_map tm
        JOIN needed_hash nh ON nh.hash = tm.hash
        WHERE tm.lang IN ({placeholders})
        """,
        langs,
    )
    return int(conn.execute("SELECT COUNT(*) FROM text_map").fetchone()[0])


def rebuild_fts_for_module(conn: sqlite3.Connection, module: str) -> None:
    try:
        if module == "avatar":
            conn.execute("DELETE FROM avatar_fts")
            conn.execute(
                """
                INSERT INTO avatar_fts(rowid, name, full_name, damage_type, base_type)
                SELECT avatar_id, COALESCE(name_chs, ''), COALESCE(full_name_chs, ''),
                       COALESCE(damage_type, ''), COALESCE(avatar_base_type, '')
                FROM avatar
                """
            )
        elif module == "dialogue":
            conn.execute("DELETE FROM talk_sentence_fts")
            conn.execute(
                """
                INSERT INTO talk_sentence_fts(rowid, speaker, text)
                SELECT talk_sentence_id, COALESCE(speaker_chs, ''), COALESCE(text_chs, '')
                FROM talk_sentence
                """
            )
        elif module == "mission":
            conn.execute("DELETE FROM mission_fts")
            conn.execute(
                """
                INSERT INTO mission_fts(rowid, name, mission_type)
                SELECT main_mission_id, COALESCE(name_chs, ''), COALESCE(mission_type, '')
                FROM main_mission
                """
            )
        elif module == "item":
            conn.execute("DELETE FROM item_fts")
            conn.execute(
                """
                INSERT INTO item_fts(rowid, name, description)
                SELECT item_id, COALESCE(item_name_chs, ''), COALESCE(item_desc_chs, '')
                FROM item
                """
            )
    except sqlite3.OperationalError:
        pass


def update_meta(conn: sqlite3.Connection, module: str, langs: List[str], source_db: Path) -> None:
    table_counts: Dict[str, int] = {}
    tables = (
        "text_map",
        "talk_sentence",
        "story_reference",
        "main_mission",
        "sub_mission",
        "avatar",
        "avatar_skill",
        "avatar_rank",
        "item",
    )
    for t in tables:
        try:
            table_counts[t] = int(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
        except Exception:
            table_counts[t] = 0

    profile = {
        "module": module,
        "langs": langs,
        "source_db": str(source_db.resolve()),
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    upserts = [
        ("table_counts", json.dumps(table_counts, ensure_ascii=False)),
        ("module_profile", json.dumps(profile, ensure_ascii=False)),
    ]
    conn.executemany(
        """
        INSERT INTO meta(key, value) VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """,
        upserts,
    )


def build_one_module(
    source_db: Path,
    output_db: Path,
    resources_root: Path,
    module: str,
    langs: List[str],
    with_text_map: bool,
    vacuum: bool,
) -> Tuple[int, float]:
    t0 = time.time()
    if output_db.exists():
        output_db.unlink()

    conn = sqlite3.connect(output_db)
    conn.row_factory = sqlite3.Row
    try:
        create_schema(conn)
        conn.execute("ATTACH DATABASE ? AS src", (str(source_db.resolve()),))
        conn.execute("PRAGMA foreign_keys = OFF")

        copy_module_tables(conn, module)
        text_rows = 0
        if with_text_map:
            ensure_needed_hash_table(conn)
            extra = gather_module_hashes(conn, resources_root, module)
            add_hashes_from_iter(conn, extra)
            text_rows = copy_text_map_for_hashes(conn, langs)
        rebuild_fts_for_module(conn, module)
        update_meta(conn, module, langs, source_db)

        conn.commit()
        if vacuum:
            conn.execute("VACUUM")
            conn.commit()
    finally:
        conn.close()
    return text_rows, time.time() - t0


def main() -> int:
    parser = argparse.ArgumentParser(description="Split one database into per-module databases.")
    default_db_dir = Path(__file__).resolve().parent / "database"
    parser.add_argument(
        "--source-db",
        type=Path,
        default=None,
        help="Source DB path. If omitted, auto-pick hsr_resources.db, then hsr_resources_lite.db.",
    )
    parser.add_argument("--output-dir", type=Path, default=default_db_dir)
    parser.add_argument("--output-prefix", type=str, default="hsr_resources")
    parser.add_argument("--resources-root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--langs", type=str, default="CHS,EN,JP,KR")
    parser.add_argument("--modules", type=str, default="avatar,dialogue,mission,item,monster")
    parser.add_argument(
        "--text-map-modules",
        type=str,
        default="avatar,item,monster",
        help="Comma list of modules that should embed text_map rows. Others keep text_map empty for smaller DB size.",
    )
    parser.add_argument("--no-vacuum", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.source_db is not None:
        source_db = args.source_db.resolve()
    else:
        full_db = (default_db_dir / "hsr_resources.db").resolve()
        lite_db = (default_db_dir / "hsr_resources_lite.db").resolve()
        source_db = full_db if full_db.exists() else lite_db
    output_dir = args.output_dir.resolve()
    resources_root = args.resources_root.resolve()
    langs = parse_langs(args.langs)
    modules = [m.strip().lower() for m in args.modules.split(",") if m.strip()]
    modules = [m for m in modules if m in MODULES]
    text_map_modules = {m.strip().lower() for m in args.text_map_modules.split(",") if m.strip()}
    text_map_modules = {m for m in text_map_modules if m in MODULES}

    if not source_db.exists():
        raise FileNotFoundError(f"Source DB not found: {source_db}")
    output_dir.mkdir(parents=True, exist_ok=True)

    outputs = [output_dir / f"{args.output_prefix}_{m}.db" for m in modules]
    if not args.force:
        existed = [p for p in outputs if p.exists()]
        if existed:
            raise FileExistsError(f"Output DB already exists: {existed[0]}. Use --force.")
    else:
        for p in outputs:
            if p.exists():
                os.remove(p)

    log(f"Source DB: {source_db} ({file_mb(source_db):.2f} MB)")
    log(f"Modules: {', '.join(modules)}")
    log(f"Langs: {','.join(langs)}")
    log(f"Embed text_map modules: {', '.join(sorted(text_map_modules)) if text_map_modules else '(none)'}")

    for module in modules:
        out_db = output_dir / f"{args.output_prefix}_{module}.db"
        text_rows, elapsed = build_one_module(
            source_db=source_db,
            output_db=out_db,
            resources_root=resources_root,
            module=module,
            langs=langs,
            with_text_map=module in text_map_modules,
            vacuum=not args.no_vacuum,
        )
        log(f"[{module}] done in {elapsed:.1f}s | text_map={text_rows:,} | size={file_mb(out_db):.2f} MB | {out_db.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
