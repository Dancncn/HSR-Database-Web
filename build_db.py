#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple


TALK_SENTENCE_RE = re.compile(r"TalkSentence_(\d+)")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def to_int(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def as_hash(value: Any) -> Optional[str]:
    if isinstance(value, dict) and "Hash" in value:
        raw = value.get("Hash")
    else:
        raw = value
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return str(raw)
    if isinstance(raw, str):
        s = raw.strip()
        return s if s else None
    return None


def as_value(value: Any) -> Optional[float]:
    raw = value.get("Value") if isinstance(value, dict) else value
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(raw)
        except ValueError:
            return None
    return None


def as_custom(value: Any) -> Optional[str]:
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and isinstance(value.get("Value"), str):
        return value["Value"]
    return None


def resolve(lang_maps: Dict[str, Dict[str, str]], lang: str, hash_key: Optional[str]) -> Optional[str]:
    if not hash_key:
        return None
    return lang_maps.get(lang, {}).get(hash_key)


def source_group(path: str) -> str:
    parts = path.replace("\\", "/").split("/")
    if len(parts) >= 2 and parts[0] == "Story":
        return f"Story/{parts[1]}"
    if len(parts) >= 3 and parts[0] == "Config" and parts[1] == "Level":
        return f"Config/Level/{parts[2]}"
    return parts[0] if parts else "Unknown"


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA journal_mode = WAL;
        PRAGMA synchronous = OFF;
        PRAGMA temp_store = MEMORY;

        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS text_map (
            lang TEXT NOT NULL,
            hash TEXT NOT NULL,
            text TEXT NOT NULL,
            PRIMARY KEY(lang, hash)
        );
        CREATE INDEX IF NOT EXISTS idx_text_map_hash ON text_map(hash);

        CREATE TABLE IF NOT EXISTS talk_sentence (
            talk_sentence_id INTEGER PRIMARY KEY,
            voice_id INTEGER,
            speaker_hash TEXT,
            speaker_chs TEXT,
            speaker_en TEXT,
            text_hash TEXT,
            text_chs TEXT,
            text_en TEXT
        );

        CREATE TABLE IF NOT EXISTS talk_sentence_multi_voice (
            talk_sentence_id INTEGER NOT NULL,
            seq INTEGER NOT NULL,
            voice_id INTEGER NOT NULL,
            PRIMARY KEY(talk_sentence_id, seq, voice_id)
        );

        CREATE TABLE IF NOT EXISTS story_reference (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_path TEXT NOT NULL,
            source_group TEXT NOT NULL,
            json_path TEXT NOT NULL,
            task_type TEXT,
            talk_sentence_id INTEGER,
            timeline_name TEXT,
            performance_type TEXT,
            performance_id INTEGER,
            trigger_custom_string TEXT,
            custom_string TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_story_reference_talk ON story_reference(talk_sentence_id);
        CREATE INDEX IF NOT EXISTS idx_story_reference_path ON story_reference(source_path);

        CREATE TABLE IF NOT EXISTS main_mission (
            main_mission_id INTEGER PRIMARY KEY,
            mission_type TEXT,
            world_id INTEGER,
            chapter_id INTEGER,
            mission_pack INTEGER,
            display_priority INTEGER,
            name_hash TEXT,
            name_chs TEXT,
            name_en TEXT,
            next_track_main_mission INTEGER,
            reward_id INTEGER,
            display_reward_id INTEGER
        );

        CREATE TABLE IF NOT EXISTS sub_mission (
            sub_mission_id INTEGER PRIMARY KEY,
            main_mission_guess INTEGER,
            target_hash TEXT,
            target_chs TEXT,
            target_en TEXT,
            description_hash TEXT,
            description_chs TEXT,
            description_en TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_sub_mission_main_guess ON sub_mission(main_mission_guess);

        CREATE TABLE IF NOT EXISTS mission_pack_link (
            mission_pack INTEGER NOT NULL,
            main_mission_id INTEGER NOT NULL,
            PRIMARY KEY(mission_pack, main_mission_id)
        );

        CREATE TABLE IF NOT EXISTS avatar (
            avatar_id INTEGER PRIMARY KEY,
            name_hash TEXT,
            name_chs TEXT,
            name_en TEXT,
            full_name_hash TEXT,
            full_name_chs TEXT,
            full_name_en TEXT,
            rarity TEXT,
            damage_type TEXT,
            avatar_base_type TEXT,
            sp_need REAL,
            max_promotion INTEGER,
            max_rank INTEGER,
            rank_id_list_json TEXT,
            skill_id_list_json TEXT,
            release_state INTEGER
        );

        CREATE TABLE IF NOT EXISTS avatar_promotion (
            avatar_id INTEGER NOT NULL,
            promotion INTEGER NOT NULL,
            max_level INTEGER,
            player_level_require INTEGER,
            world_level_require INTEGER,
            hp_base REAL,
            hp_add REAL,
            attack_base REAL,
            attack_add REAL,
            defence_base REAL,
            defence_add REAL,
            speed_base REAL,
            critical_chance REAL,
            critical_damage REAL,
            base_aggro REAL,
            promotion_cost_json TEXT,
            PRIMARY KEY(avatar_id, promotion)
        );

        CREATE TABLE IF NOT EXISTS avatar_skill (
            skill_id INTEGER NOT NULL,
            level INTEGER NOT NULL,
            max_level INTEGER,
            name_hash TEXT,
            name_chs TEXT,
            name_en TEXT,
            desc_hash TEXT,
            desc_chs TEXT,
            desc_en TEXT,
            tag_hash TEXT,
            tag_chs TEXT,
            tag_en TEXT,
            skill_trigger_key TEXT,
            skill_effect TEXT,
            attack_type TEXT,
            stance_damage_type TEXT,
            sp_base REAL,
            bp_need REAL,
            bp_add REAL,
            param_json TEXT,
            PRIMARY KEY(skill_id, level)
        );

        CREATE TABLE IF NOT EXISTS avatar_rank (
            rank_id INTEGER PRIMARY KEY,
            rank INTEGER,
            trigger_hash TEXT,
            name_raw TEXT,
            desc_raw TEXT,
            icon_path TEXT,
            skill_add_level_json TEXT,
            rank_ability_json TEXT,
            param_json TEXT
        );

        CREATE TABLE IF NOT EXISTS item (
            item_id INTEGER PRIMARY KEY,
            source_file TEXT,
            item_main_type TEXT,
            item_sub_type TEXT,
            rarity TEXT,
            purpose_type INTEGER,
            purpose_text_chs TEXT,
            purpose_text_en TEXT,
            item_name_hash TEXT,
            item_name_chs TEXT,
            item_name_en TEXT,
            item_desc_hash TEXT,
            item_desc_chs TEXT,
            item_desc_en TEXT,
            item_bg_desc_hash TEXT,
            item_bg_desc_chs TEXT,
            item_bg_desc_en TEXT,
            icon_path TEXT,
            figure_icon_path TEXT,
            currency_icon_path TEXT,
            avatar_icon_path TEXT,
            pile_limit INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_item_main_type ON item(item_main_type);
        CREATE INDEX IF NOT EXISTS idx_item_sub_type ON item(item_sub_type);
        CREATE INDEX IF NOT EXISTS idx_item_rarity ON item(rarity);
        """
    )

    try:
        conn.executescript(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS talk_sentence_fts USING fts5(speaker, text);
            CREATE VIRTUAL TABLE IF NOT EXISTS mission_fts USING fts5(name, mission_type UNINDEXED);
            CREATE VIRTUAL TABLE IF NOT EXISTS avatar_fts USING fts5(name, full_name, damage_type UNINDEXED, base_type UNINDEXED);
            CREATE VIRTUAL TABLE IF NOT EXISTS item_fts USING fts5(name, description);
            """
        )
    except sqlite3.OperationalError:
        log("FTS5 not available; continuing without FTS tables.")


def parse_langs(raw: str) -> List[str]:
    langs = [x.strip().upper() for x in raw.split(",") if x.strip()]
    return langs if langs else ["CHS", "EN"]


def load_text_maps(resources_root: Path, langs: List[str]) -> Dict[str, Dict[str, str]]:
    result: Dict[str, Dict[str, str]] = {}
    text_root = resources_root / "TextMap"
    for lang in langs:
        merged: Dict[str, str] = {}
        for name in (f"TextMapMain{lang}.json", f"TextMap{lang}.json"):
            path = text_root / name
            if not path.exists():
                continue
            data = load_json(path)
            if not isinstance(data, dict):
                continue
            for k, v in data.items():
                merged[str(k)] = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        result[lang] = merged
        log(f"TextMap {lang}: {len(merged):,}")
    return result


def insert_text_map(conn: sqlite3.Connection, lang_maps: Dict[str, Dict[str, str]]) -> int:
    rows: List[Tuple[str, str, str]] = []
    for lang, mapping in lang_maps.items():
        rows.extend((lang, k, v) for k, v in mapping.items())
    conn.executemany(
        "INSERT INTO text_map(lang, hash, text) VALUES(?, ?, ?) ON CONFLICT(lang, hash) DO UPDATE SET text=excluded.text",
        rows,
    )
    return len(rows)


def insert_talk(conn: sqlite3.Connection, resources_root: Path, lang_maps: Dict[str, Dict[str, str]]) -> Dict[str, int]:
    excel = resources_root / "ExcelOutput"
    talk_data = load_json(excel / "TalkSentenceConfig.json")
    talk_rows: List[Tuple[Any, ...]] = []
    fts_rows: List[Tuple[int, str, str]] = []

    if isinstance(talk_data, list):
        for item in talk_data:
            if not isinstance(item, dict):
                continue
            tid = to_int(item.get("TalkSentenceID"))
            if tid is None:
                continue
            vh = to_int(item.get("VoiceID"))
            speaker_hash = as_hash(item.get("TextmapTalkSentenceName"))
            text_hash = as_hash(item.get("TalkSentenceText"))
            speaker_chs = resolve(lang_maps, "CHS", speaker_hash)
            speaker_en = resolve(lang_maps, "EN", speaker_hash)
            text_chs = resolve(lang_maps, "CHS", text_hash)
            text_en = resolve(lang_maps, "EN", text_hash)
            talk_rows.append((tid, vh, speaker_hash, speaker_chs, speaker_en, text_hash, text_chs, text_en))
            fts_rows.append((tid, speaker_chs or "", text_chs or ""))

    conn.executemany(
        """
        INSERT INTO talk_sentence(
            talk_sentence_id, voice_id, speaker_hash, speaker_chs, speaker_en, text_hash, text_chs, text_en
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(talk_sentence_id) DO UPDATE SET
            voice_id=excluded.voice_id,
            speaker_hash=excluded.speaker_hash,
            speaker_chs=excluded.speaker_chs,
            speaker_en=excluded.speaker_en,
            text_hash=excluded.text_hash,
            text_chs=excluded.text_chs,
            text_en=excluded.text_en
        """,
        talk_rows,
    )

    mv_rows: List[Tuple[int, int, int]] = []
    mv_data = load_json(excel / "TalkSentenceMultiVoice.json")
    if isinstance(mv_data, list):
        for item in mv_data:
            if not isinstance(item, dict):
                continue
            tid = to_int(item.get("TalkSentenceID"))
            voices = item.get("VoiceIDList")
            if tid is None or not isinstance(voices, list):
                continue
            for i, v in enumerate(voices):
                vi = to_int(v)
                if vi is None:
                    continue
                mv_rows.append((tid, i, vi))

    if mv_rows:
        conn.executemany(
            "INSERT INTO talk_sentence_multi_voice(talk_sentence_id, seq, voice_id) VALUES(?, ?, ?) ON CONFLICT(talk_sentence_id, seq, voice_id) DO NOTHING",
            mv_rows,
        )

    try:
        conn.execute("DELETE FROM talk_sentence_fts")
        conn.executemany("INSERT INTO talk_sentence_fts(rowid, speaker, text) VALUES(?, ?, ?)", fts_rows)
    except sqlite3.OperationalError:
        pass

    return {"talk_sentence": len(talk_rows), "talk_sentence_multi_voice": len(mv_rows)}

def insert_missions(conn: sqlite3.Connection, resources_root: Path, lang_maps: Dict[str, Dict[str, str]]) -> Dict[str, int]:
    excel = resources_root / "ExcelOutput"

    main_rows: List[Tuple[Any, ...]] = []
    mission_fts: List[Tuple[int, str, str]] = []
    main_data = load_json(excel / "MainMission.json")
    if isinstance(main_data, list):
        for item in main_data:
            if not isinstance(item, dict):
                continue
            mid = to_int(item.get("MainMissionID"))
            if mid is None:
                continue
            name_hash = as_hash(item.get("Name"))
            name_chs = resolve(lang_maps, "CHS", name_hash)
            name_en = resolve(lang_maps, "EN", name_hash)
            mtype = item.get("Type") if isinstance(item.get("Type"), str) else None
            main_rows.append(
                (
                    mid,
                    mtype,
                    to_int(item.get("WorldID")),
                    to_int(item.get("ChapterID")),
                    to_int(item.get("MissionPack")),
                    to_int(item.get("DisplayPriority")),
                    name_hash,
                    name_chs,
                    name_en,
                    to_int(item.get("NextTrackMainMission")),
                    to_int(item.get("RewardID")),
                    to_int(item.get("DisplayRewardID")),
                )
            )
            mission_fts.append((mid, name_chs or "", mtype or ""))

    conn.executemany(
        """
        INSERT INTO main_mission(
            main_mission_id, mission_type, world_id, chapter_id, mission_pack, display_priority,
            name_hash, name_chs, name_en, next_track_main_mission, reward_id, display_reward_id
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(main_mission_id) DO UPDATE SET
            mission_type=excluded.mission_type,
            world_id=excluded.world_id,
            chapter_id=excluded.chapter_id,
            mission_pack=excluded.mission_pack,
            display_priority=excluded.display_priority,
            name_hash=excluded.name_hash,
            name_chs=excluded.name_chs,
            name_en=excluded.name_en,
            next_track_main_mission=excluded.next_track_main_mission,
            reward_id=excluded.reward_id,
            display_reward_id=excluded.display_reward_id
        """,
        main_rows,
    )

    sub_rows: List[Tuple[Any, ...]] = []
    sub_data = load_json(excel / "SubMission.json")
    if isinstance(sub_data, list):
        for item in sub_data:
            if not isinstance(item, dict):
                continue
            sid = to_int(item.get("SubMissionID"))
            if sid is None:
                continue
            target_hash = as_hash(item.get("TargetText"))
            desc_hash = as_hash(item.get("DescrptionText"))
            sub_rows.append(
                (
                    sid,
                    sid // 100,
                    target_hash,
                    resolve(lang_maps, "CHS", target_hash),
                    resolve(lang_maps, "EN", target_hash),
                    desc_hash,
                    resolve(lang_maps, "CHS", desc_hash),
                    resolve(lang_maps, "EN", desc_hash),
                )
            )

    conn.executemany(
        """
        INSERT INTO sub_mission(
            sub_mission_id, main_mission_guess, target_hash, target_chs, target_en,
            description_hash, description_chs, description_en
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(sub_mission_id) DO UPDATE SET
            main_mission_guess=excluded.main_mission_guess,
            target_hash=excluded.target_hash,
            target_chs=excluded.target_chs,
            target_en=excluded.target_en,
            description_hash=excluded.description_hash,
            description_chs=excluded.description_chs,
            description_en=excluded.description_en
        """,
        sub_rows,
    )

    pack_rows: List[Tuple[int, int]] = []
    pack_data = load_json(excel / "MainMissionPack.json")
    if isinstance(pack_data, list):
        for item in pack_data:
            if not isinstance(item, dict):
                continue
            pack = to_int(item.get("MissionPack"))
            lst = item.get("MainMissionIdList")
            if pack is None or not isinstance(lst, list):
                continue
            for raw in lst:
                mid = to_int(raw)
                if mid is not None:
                    pack_rows.append((pack, mid))
    if pack_rows:
        conn.executemany(
            "INSERT INTO mission_pack_link(mission_pack, main_mission_id) VALUES(?, ?) ON CONFLICT(mission_pack, main_mission_id) DO NOTHING",
            pack_rows,
        )

    try:
        conn.execute("DELETE FROM mission_fts")
        conn.executemany("INSERT INTO mission_fts(rowid, name, mission_type) VALUES(?, ?, ?)", mission_fts)
    except sqlite3.OperationalError:
        pass

    return {"main_mission": len(main_rows), "sub_mission": len(sub_rows), "mission_pack_link": len(pack_rows)}


def insert_avatars(conn: sqlite3.Connection, resources_root: Path, lang_maps: Dict[str, Dict[str, str]]) -> Dict[str, int]:
    excel = resources_root / "ExcelOutput"

    avatar_rows: List[Tuple[Any, ...]] = []
    avatar_fts: List[Tuple[int, str, str, str, str]] = []
    avatar_data = load_json(excel / "AvatarConfig.json")
    if isinstance(avatar_data, list):
        for item in avatar_data:
            if not isinstance(item, dict):
                continue
            aid = to_int(item.get("AvatarID"))
            if aid is None:
                continue
            name_hash = as_hash(item.get("AvatarName"))
            full_hash = as_hash(item.get("AvatarFullName"))
            damage_type = item.get("DamageType") if isinstance(item.get("DamageType"), str) else None
            base_type = item.get("AvatarBaseType") if isinstance(item.get("AvatarBaseType"), str) else None
            name_chs = resolve(lang_maps, "CHS", name_hash)
            name_en = resolve(lang_maps, "EN", name_hash)
            full_chs = resolve(lang_maps, "CHS", full_hash)
            full_en = resolve(lang_maps, "EN", full_hash)

            avatar_rows.append(
                (
                    aid,
                    name_hash,
                    name_chs,
                    name_en,
                    full_hash,
                    full_chs,
                    full_en,
                    item.get("Rarity") if isinstance(item.get("Rarity"), str) else None,
                    damage_type,
                    base_type,
                    as_value(item.get("SPNeed")),
                    to_int(item.get("MaxPromotion")),
                    to_int(item.get("MaxRank")),
                    json.dumps(item.get("RankIDList", []), ensure_ascii=False),
                    json.dumps(item.get("SkillList", []), ensure_ascii=False),
                    1 if item.get("Release") is True else 0,
                )
            )
            avatar_fts.append((aid, name_chs or "", full_chs or "", damage_type or "", base_type or ""))

    conn.executemany(
        """
        INSERT INTO avatar(
            avatar_id, name_hash, name_chs, name_en, full_name_hash, full_name_chs, full_name_en,
            rarity, damage_type, avatar_base_type, sp_need, max_promotion, max_rank,
            rank_id_list_json, skill_id_list_json, release_state
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(avatar_id) DO UPDATE SET
            name_hash=excluded.name_hash,
            name_chs=excluded.name_chs,
            name_en=excluded.name_en,
            full_name_hash=excluded.full_name_hash,
            full_name_chs=excluded.full_name_chs,
            full_name_en=excluded.full_name_en,
            rarity=excluded.rarity,
            damage_type=excluded.damage_type,
            avatar_base_type=excluded.avatar_base_type,
            sp_need=excluded.sp_need,
            max_promotion=excluded.max_promotion,
            max_rank=excluded.max_rank,
            rank_id_list_json=excluded.rank_id_list_json,
            skill_id_list_json=excluded.skill_id_list_json,
            release_state=excluded.release_state
        """,
        avatar_rows,
    )

    prom_rows: List[Tuple[Any, ...]] = []
    prom_data = load_json(excel / "AvatarPromotionConfig.json")
    if isinstance(prom_data, list):
        for item in prom_data:
            if not isinstance(item, dict):
                continue
            aid = to_int(item.get("AvatarID"))
            if aid is None:
                continue
            prom_rows.append(
                (
                    aid,
                    to_int(item.get("Promotion")) or 0,
                    to_int(item.get("MaxLevel")),
                    to_int(item.get("PlayerLevelRequire")),
                    to_int(item.get("WorldLevelRequire")),
                    as_value(item.get("HPBase")),
                    as_value(item.get("HPAdd")),
                    as_value(item.get("AttackBase")),
                    as_value(item.get("AttackAdd")),
                    as_value(item.get("DefenceBase")),
                    as_value(item.get("DefenceAdd")),
                    as_value(item.get("SpeedBase")),
                    as_value(item.get("CriticalChance")),
                    as_value(item.get("CriticalDamage")),
                    as_value(item.get("BaseAggro")),
                    json.dumps(item.get("PromotionCostList", []), ensure_ascii=False),
                )
            )

    if prom_rows:
        conn.executemany(
            """
            INSERT INTO avatar_promotion(
                avatar_id, promotion, max_level, player_level_require, world_level_require,
                hp_base, hp_add, attack_base, attack_add, defence_base, defence_add,
                speed_base, critical_chance, critical_damage, base_aggro, promotion_cost_json
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(avatar_id, promotion) DO UPDATE SET
                max_level=excluded.max_level,
                player_level_require=excluded.player_level_require,
                world_level_require=excluded.world_level_require,
                hp_base=excluded.hp_base,
                hp_add=excluded.hp_add,
                attack_base=excluded.attack_base,
                attack_add=excluded.attack_add,
                defence_base=excluded.defence_base,
                defence_add=excluded.defence_add,
                speed_base=excluded.speed_base,
                critical_chance=excluded.critical_chance,
                critical_damage=excluded.critical_damage,
                base_aggro=excluded.base_aggro,
                promotion_cost_json=excluded.promotion_cost_json
            """,
            prom_rows,
        )

    skill_rows: List[Tuple[Any, ...]] = []
    skill_data = load_json(excel / "AvatarSkillConfig.json")
    if isinstance(skill_data, list):
        for item in skill_data:
            if not isinstance(item, dict):
                continue
            sid = to_int(item.get("SkillID"))
            lvl = to_int(item.get("Level"))
            if sid is None or lvl is None:
                continue
            name_hash = as_hash(item.get("SkillName"))
            desc_hash = as_hash(item.get("SkillDesc"))
            tag_hash = as_hash(item.get("SkillTag"))
            skill_rows.append(
                (
                    sid,
                    lvl,
                    to_int(item.get("MaxLevel")),
                    name_hash,
                    resolve(lang_maps, "CHS", name_hash),
                    resolve(lang_maps, "EN", name_hash),
                    desc_hash,
                    resolve(lang_maps, "CHS", desc_hash),
                    resolve(lang_maps, "EN", desc_hash),
                    tag_hash,
                    resolve(lang_maps, "CHS", tag_hash),
                    resolve(lang_maps, "EN", tag_hash),
                    item.get("SkillTriggerKey") if isinstance(item.get("SkillTriggerKey"), str) else None,
                    item.get("SkillEffect") if isinstance(item.get("SkillEffect"), str) else None,
                    item.get("AttackType") if isinstance(item.get("AttackType"), str) else None,
                    item.get("StanceDamageType") if isinstance(item.get("StanceDamageType"), str) else None,
                    as_value(item.get("SPBase")),
                    as_value(item.get("BPNeed")),
                    as_value(item.get("BPAdd")),
                    json.dumps(item.get("ParamList", []), ensure_ascii=False),
                )
            )

    if skill_rows:
        conn.executemany(
            """
            INSERT INTO avatar_skill(
                skill_id, level, max_level, name_hash, name_chs, name_en,
                desc_hash, desc_chs, desc_en, tag_hash, tag_chs, tag_en,
                skill_trigger_key, skill_effect, attack_type, stance_damage_type,
                sp_base, bp_need, bp_add, param_json
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(skill_id, level) DO UPDATE SET
                max_level=excluded.max_level,
                name_hash=excluded.name_hash,
                name_chs=excluded.name_chs,
                name_en=excluded.name_en,
                desc_hash=excluded.desc_hash,
                desc_chs=excluded.desc_chs,
                desc_en=excluded.desc_en,
                tag_hash=excluded.tag_hash,
                tag_chs=excluded.tag_chs,
                tag_en=excluded.tag_en,
                skill_trigger_key=excluded.skill_trigger_key,
                skill_effect=excluded.skill_effect,
                attack_type=excluded.attack_type,
                stance_damage_type=excluded.stance_damage_type,
                sp_base=excluded.sp_base,
                bp_need=excluded.bp_need,
                bp_add=excluded.bp_add,
                param_json=excluded.param_json
            """,
            skill_rows,
        )

    rank_rows: List[Tuple[Any, ...]] = []
    rank_data = load_json(excel / "AvatarRankConfig.json")
    if isinstance(rank_data, list):
        for item in rank_data:
            if not isinstance(item, dict):
                continue
            rid = to_int(item.get("RankID"))
            if rid is None:
                continue
            rank_rows.append(
                (
                    rid,
                    to_int(item.get("Rank")),
                    as_hash(item.get("Trigger")),
                    item.get("Name") if isinstance(item.get("Name"), str) else None,
                    item.get("Desc") if isinstance(item.get("Desc"), str) else None,
                    item.get("IconPath") if isinstance(item.get("IconPath"), str) else None,
                    json.dumps(item.get("SkillAddLevelList", {}), ensure_ascii=False),
                    json.dumps(item.get("RankAbility", []), ensure_ascii=False),
                    json.dumps(item.get("Param", []), ensure_ascii=False),
                )
            )

    if rank_rows:
        conn.executemany(
            """
            INSERT INTO avatar_rank(
                rank_id, rank, trigger_hash, name_raw, desc_raw, icon_path,
                skill_add_level_json, rank_ability_json, param_json
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(rank_id) DO UPDATE SET
                rank=excluded.rank,
                trigger_hash=excluded.trigger_hash,
                name_raw=excluded.name_raw,
                desc_raw=excluded.desc_raw,
                icon_path=excluded.icon_path,
                skill_add_level_json=excluded.skill_add_level_json,
                rank_ability_json=excluded.rank_ability_json,
                param_json=excluded.param_json
            """,
            rank_rows,
        )

    try:
        conn.execute("DELETE FROM avatar_fts")
        conn.executemany("INSERT INTO avatar_fts(rowid, name, full_name, damage_type, base_type) VALUES(?, ?, ?, ?, ?)", avatar_fts)
    except sqlite3.OperationalError:
        pass

    return {
        "avatar": len(avatar_rows),
        "avatar_promotion": len(prom_rows),
        "avatar_skill": len(skill_rows),
        "avatar_rank": len(rank_rows),
    }


def insert_items(conn: sqlite3.Connection, resources_root: Path, lang_maps: Dict[str, Dict[str, str]]) -> Dict[str, int]:
    excel = resources_root / "ExcelOutput"
    purpose_map: Dict[int, Tuple[Optional[str], Optional[str]]] = {}

    purpose_path = excel / "ItemPurpose.json"
    if purpose_path.exists():
        purpose_data = load_json(purpose_path)
        if isinstance(purpose_data, list):
            for row in purpose_data:
                if not isinstance(row, dict):
                    continue
                pid = to_int(row.get("ID"))
                if pid is None:
                    continue
                h = as_hash(row.get("PurposeText"))
                purpose_map[pid] = (
                    resolve(lang_maps, "CHS", h),
                    resolve(lang_maps, "EN", h),
                )

    item_files = sorted(excel.glob("ItemConfig*.json"))
    rows: List[Tuple[Any, ...]] = []
    fts_by_id: Dict[int, Tuple[str, str]] = {}
    parsed_rows = 0

    for path in item_files:
        data = load_json(path)
        if not isinstance(data, list):
            continue
        for item in data:
            if not isinstance(item, dict):
                continue
            item_id = to_int(item.get("ID"))
            if item_id is None:
                continue
            parsed_rows += 1
            purpose_type = to_int(item.get("PurposeType"))
            purpose_chs = None
            purpose_en = None
            if purpose_type is not None and purpose_type in purpose_map:
                purpose_chs, purpose_en = purpose_map[purpose_type]

            name_hash = as_hash(item.get("ItemName"))
            desc_hash = as_hash(item.get("ItemDesc"))
            bg_hash = as_hash(item.get("ItemBGDesc"))
            name_chs = resolve(lang_maps, "CHS", name_hash)
            name_en = resolve(lang_maps, "EN", name_hash)
            desc_chs = resolve(lang_maps, "CHS", desc_hash)
            desc_en = resolve(lang_maps, "EN", desc_hash)
            bg_chs = resolve(lang_maps, "CHS", bg_hash)
            bg_en = resolve(lang_maps, "EN", bg_hash)

            rows.append(
                (
                    item_id,
                    path.name,
                    item.get("ItemMainType") if isinstance(item.get("ItemMainType"), str) else None,
                    item.get("ItemSubType") if isinstance(item.get("ItemSubType"), str) else None,
                    item.get("Rarity") if isinstance(item.get("Rarity"), str) else None,
                    purpose_type,
                    purpose_chs,
                    purpose_en,
                    name_hash,
                    name_chs,
                    name_en,
                    desc_hash,
                    desc_chs,
                    desc_en,
                    bg_hash,
                    bg_chs,
                    bg_en,
                    item.get("ItemIconPath") if isinstance(item.get("ItemIconPath"), str) else None,
                    item.get("ItemFigureIconPath") if isinstance(item.get("ItemFigureIconPath"), str) else None,
                    item.get("ItemCurrencyIconPath") if isinstance(item.get("ItemCurrencyIconPath"), str) else None,
                    item.get("ItemAvatarIconPath") if isinstance(item.get("ItemAvatarIconPath"), str) else None,
                    to_int(item.get("PileLimit")),
                )
            )

            fts_by_id[item_id] = (
                name_chs or "",
                desc_chs or bg_chs or "",
            )

    if rows:
        conn.executemany(
            """
            INSERT INTO item(
                item_id, source_file, item_main_type, item_sub_type, rarity, purpose_type,
                purpose_text_chs, purpose_text_en, item_name_hash, item_name_chs, item_name_en,
                item_desc_hash, item_desc_chs, item_desc_en, item_bg_desc_hash, item_bg_desc_chs,
                item_bg_desc_en, icon_path, figure_icon_path, currency_icon_path, avatar_icon_path, pile_limit
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(item_id) DO UPDATE SET
                source_file=excluded.source_file,
                item_main_type=excluded.item_main_type,
                item_sub_type=excluded.item_sub_type,
                rarity=excluded.rarity,
                purpose_type=excluded.purpose_type,
                purpose_text_chs=excluded.purpose_text_chs,
                purpose_text_en=excluded.purpose_text_en,
                item_name_hash=excluded.item_name_hash,
                item_name_chs=excluded.item_name_chs,
                item_name_en=excluded.item_name_en,
                item_desc_hash=excluded.item_desc_hash,
                item_desc_chs=excluded.item_desc_chs,
                item_desc_en=excluded.item_desc_en,
                item_bg_desc_hash=excluded.item_bg_desc_hash,
                item_bg_desc_chs=excluded.item_bg_desc_chs,
                item_bg_desc_en=excluded.item_bg_desc_en,
                icon_path=excluded.icon_path,
                figure_icon_path=excluded.figure_icon_path,
                currency_icon_path=excluded.currency_icon_path,
                avatar_icon_path=excluded.avatar_icon_path,
                pile_limit=excluded.pile_limit
            """,
            rows,
        )

    try:
        conn.execute("DELETE FROM item_fts")
        fts_rows = [(item_id, name, desc) for item_id, (name, desc) in fts_by_id.items()]
        conn.executemany("INSERT INTO item_fts(rowid, name, description) VALUES(?, ?, ?)", fts_rows)
    except sqlite3.OperationalError:
        pass

    unique_count = conn.execute("SELECT COUNT(*) FROM item").fetchone()[0]
    return {
        "item_files": len(item_files),
        "item_rows_parsed": parsed_rows,
        "item_rows_upserted": len(rows),
        "item_unique": unique_count,
    }

def iter_reference_files(resources_root: Path, include_level_config: bool) -> Iterator[Path]:
    story_root = resources_root / "Story"
    if story_root.exists():
        for path in story_root.rglob("*.json"):
            if not path.name.endswith(".layout.json"):
                yield path
    if include_level_config:
        level_root = resources_root / "Config" / "Level"
        if level_root.exists():
            for path in level_root.rglob("*.json"):
                if not path.name.endswith(".layout.json"):
                    yield path


def extract_reference_rows(rel_path: str, data: Any) -> List[Tuple[Any, ...]]:
    rows: List[Tuple[Any, ...]] = []
    seen: set[Tuple[Any, ...]] = set()
    group = source_group(rel_path)

    def walk(node: Any, json_path: str, inherited_task_type: Optional[str]) -> None:
        if isinstance(node, dict):
            task_type = node.get("$type") if isinstance(node.get("$type"), str) else inherited_task_type
            talk_id = to_int(node.get("TalkSentenceID"))
            trigger = as_custom(node.get("TriggerCustomString"))
            custom = as_custom(node.get("CustomString"))
            if talk_id is None:
                for candidate in (trigger, custom):
                    if candidate:
                        m = TALK_SENTENCE_RE.search(candidate)
                        if m:
                            talk_id = int(m.group(1))
                            break

            timeline = node.get("TimelineName") if isinstance(node.get("TimelineName"), str) else None
            perf_type = node.get("PerformanceType") if isinstance(node.get("PerformanceType"), str) else None
            perf_id = to_int(node.get("PerformanceID"))

            if any((talk_id is not None, timeline, perf_type, perf_id is not None, trigger, custom)):
                key = (json_path, task_type, talk_id, timeline, perf_type, perf_id, trigger, custom)
                if key not in seen:
                    seen.add(key)
                    rows.append((rel_path, group, json_path, task_type, talk_id, timeline, perf_type, perf_id, trigger, custom))

            for key, value in node.items():
                child = f"{json_path}.{key}" if json_path != "$" else f"$.{key}"
                walk(value, child, task_type)
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{json_path}[{i}]", inherited_task_type)

    walk(data, "$", None)
    return rows


def insert_story_references(conn: sqlite3.Connection, resources_root: Path, include_level_config: bool) -> Dict[str, int]:
    files = list(iter_reference_files(resources_root, include_level_config))
    log(f"Reference files: {len(files):,}")

    total_rows = 0
    parse_errors = 0
    batch: List[Tuple[Any, ...]] = []

    for i, path in enumerate(files, start=1):
        rel = path.relative_to(resources_root).as_posix()
        try:
            data = load_json(path)
        except Exception:
            parse_errors += 1
            continue

        rows = extract_reference_rows(rel, data)
        if rows:
            batch.extend(rows)
            total_rows += len(rows)

        if len(batch) >= 10000:
            conn.executemany(
                """
                INSERT INTO story_reference(
                    source_path, source_group, json_path, task_type, talk_sentence_id,
                    timeline_name, performance_type, performance_id, trigger_custom_string, custom_string
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                batch,
            )
            batch.clear()

        if i % 1000 == 0:
            log(f"Processed {i:,}/{len(files):,} files, refs: {total_rows:,}")

    if batch:
        conn.executemany(
            """
            INSERT INTO story_reference(
                source_path, source_group, json_path, task_type, talk_sentence_id,
                timeline_name, performance_type, performance_id, trigger_custom_string, custom_string
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            batch,
        )

    return {"reference_files": len(files), "story_reference": total_rows, "parse_errors": parse_errors}


def table_counts(conn: sqlite3.Connection) -> Dict[str, int]:
    names = [
        "text_map",
        "talk_sentence",
        "talk_sentence_multi_voice",
        "story_reference",
        "main_mission",
        "sub_mission",
        "mission_pack_link",
        "avatar",
        "avatar_promotion",
        "avatar_skill",
        "avatar_rank",
        "item",
    ]
    out: Dict[str, int] = {}
    for name in names:
        out[name] = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
    return out


def write_meta(conn: sqlite3.Connection, payload: Dict[str, Any]) -> None:
    rows = []
    for k, v in payload.items():
        rows.append((k, v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)))
    conn.executemany(
        "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        rows,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a local sqlite DB for querying resources.")
    parser.add_argument("--resources-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--db-path", type=Path, default=Path(__file__).resolve().parent / "hsr_resources.db")
    parser.add_argument("--langs", type=str, default="CHS,EN")
    parser.add_argument("--skip-level-config", action="store_true", help="Only scan Story/ for references.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing db if present.")
    args = parser.parse_args()

    resources_root = args.resources_root.resolve()
    db_path = args.db_path.resolve()
    include_level_config = not args.skip_level_config
    langs = parse_langs(args.langs)

    if not resources_root.exists():
        raise FileNotFoundError(resources_root)

    if db_path.exists():
        if not args.force:
            raise FileExistsError(f"{db_path} already exists. Use --force to overwrite.")
        db_path.unlink()

    log(f"Resources: {resources_root}")
    log(f"Database: {db_path}")
    log(f"Languages: {', '.join(langs)}")
    log(f"Include Config/Level: {include_level_config}")

    t0 = time.time()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        create_schema(conn)
        lang_maps = load_text_maps(resources_root, langs)

        text_count = insert_text_map(conn, lang_maps)
        log(f"Inserted text_map rows: {text_count:,}")

        talk_stats = insert_talk(conn, resources_root, lang_maps)
        log(f"Talk stats: {talk_stats}")

        mission_stats = insert_missions(conn, resources_root, lang_maps)
        log(f"Mission stats: {mission_stats}")

        avatar_stats = insert_avatars(conn, resources_root, lang_maps)
        log(f"Avatar stats: {avatar_stats}")

        item_stats = insert_items(conn, resources_root, lang_maps)
        log(f"Item stats: {item_stats}")

        ref_stats = insert_story_references(conn, resources_root, include_level_config)
        log(f"Reference stats: {ref_stats}")

        counts = table_counts(conn)
        elapsed = round(time.time() - t0, 2)
        write_meta(
            conn,
            {
                "build_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "resources_root": str(resources_root),
                "langs": langs,
                "include_level_config": include_level_config,
                "elapsed_seconds": elapsed,
                "table_counts": counts,
            },
        )
        conn.commit()

        log("Build completed.")
        for k, v in counts.items():
            log(f"  {k}: {v:,}")
        log(f"Elapsed: {elapsed}s")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
