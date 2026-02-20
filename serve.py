#!/usr/bin/env python3
from __future__ import annotations

import argparse
import functools
import json
import mimetypes
import re
import shutil
import sqlite3
import subprocess
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse, unquote


def json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def as_int(value: str, default: int, min_value: int = 1, max_value: int = 1000) -> int:
    try:
        iv = int(value)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(max_value, iv))


def norm_fts_query(q: str) -> str:
    terms = [t for t in re.split(r"\s+", q.strip()) if t]
    return " ".join(terms)


def qv(query: Dict[str, List[str]], key: str, default: str = "") -> str:
    return (query.get(key, [default])[0] or default).strip()


def paging(query: Dict[str, List[str]], default_size: int = 20, max_size: int = 100) -> Tuple[int, int, int]:
    page = as_int(qv(query, "page", "1"), 1, 1, 100000)
    page_size = as_int(qv(query, "page_size", str(default_size)), default_size, 1, max_size)
    offset = (page - 1) * page_size
    return page, page_size, offset


def with_paging_meta(payload: Dict[str, Any], page: int, page_size: int, total: int) -> Dict[str, Any]:
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    payload["page"] = page
    payload["page_size"] = page_size
    payload["total"] = total
    payload["total_pages"] = total_pages
    return payload


def escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


SKILL_PARAM_RE = re.compile(r"#(\d+)(?:\[([^\]]+)\])?(%)?")
XXH64_TOKEN_RE = re.compile(r"^[0-9a-fA-F]{16}$")
RAW_HASH_RE = re.compile(r"^\d+$")
XXHSUM_BIN = shutil.which("xxhsum")
LANG_ALIAS = {
    "ZH": "CHS",
    "ZH_CN": "CHS",
    "CN": "CHS",
    "CHS": "CHS",
    "EN": "EN",
    "EN_US": "EN",
    "JP": "JP",
    "JA": "JP",
    "JA_JP": "JP",
    "KR": "KR",
    "KO": "KR",
    "KO_KR": "KR",
}
SUPPORTED_LANGS = {"CHS", "EN", "JP", "KR"}
SUPPORTED_MODULES = {"default", "avatar", "dialogue", "mission", "item", "monster"}

try:
    import xxhash  # type: ignore[import-not-found]
except Exception:
    xxhash = None


def parse_param_values(raw: Any) -> List[float]:
    if raw is None:
        return []
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except Exception:
            return []
    if not isinstance(data, list):
        return []

    vals: List[float] = []
    for item in data:
        src = item.get("Value") if isinstance(item, dict) else item
        if isinstance(src, (int, float)):
            vals.append(float(src))
            continue
        if isinstance(src, str):
            try:
                vals.append(float(src))
            except ValueError:
                continue
    return vals


def normalize_lang(raw: str, default: str = "CHS") -> str:
    token = (raw or "").strip().upper().replace("-", "_")
    if not token:
        return default
    mapped = LANG_ALIAS.get(token, token)
    return mapped if mapped in SUPPORTED_LANGS else default


def format_num(value: float, decimals: Optional[int] = None, trim: bool = True) -> str:
    if decimals is not None:
        out = f"{value:.{decimals}f}"
        if trim and decimals > 0:
            out = out.rstrip("0").rstrip(".")
        return out
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def apply_param_template(template: Optional[str], raw_params: Any) -> Optional[str]:
    if template is None:
        return None
    params = parse_param_values(raw_params)
    if not params:
        return template

    def repl(match: re.Match[str]) -> str:
        index = int(match.group(1)) - 1
        fmt = (match.group(2) or "").strip().lower()
        is_percent = bool(match.group(3))
        if index < 0 or index >= len(params):
            return match.group(0)

        value = params[index] * 100.0 if is_percent else params[index]
        if fmt.startswith("i"):
            rendered = str(int(round(value)))
        elif fmt.startswith("f"):
            m = re.match(r"f(\d+)", fmt)
            decimals = int(m.group(1)) if m else 0
            rendered = format_num(value, decimals=decimals, trim=False)
        else:
            rendered = format_num(value)
        return rendered + ("%" if is_percent else "")

    return SKILL_PARAM_RE.sub(repl, template)


@functools.lru_cache(maxsize=8192)
def hash_text_key(raw_key: str) -> Optional[str]:
    token = raw_key.strip()
    if not token:
        return None
    if RAW_HASH_RE.fullmatch(token):
        return token

    if xxhash is not None:
        try:
            return str(xxhash.xxh64(token.encode("utf-8")).intdigest())
        except Exception:
            pass

    if XXHSUM_BIN:
        try:
            proc = subprocess.run(
                [XXHSUM_BIN, "-H1"],
                input=token.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if proc.returncode == 0:
                first = proc.stdout.decode("utf-8", errors="ignore").strip().split()
                if first and XXH64_TOKEN_RE.fullmatch(first[0]):
                    return str(int(first[0], 16))
        except Exception:
            pass
    return None


def resolve_text_from_key(conn: sqlite3.Connection, lang: str, raw_key: Optional[str]) -> Optional[str]:
    if not raw_key:
        return None
    hashed = hash_text_key(str(raw_key))
    if not hashed:
        return None
    row = conn.execute(
        "SELECT text FROM text_map WHERE lang = ? AND hash = ?",
        (lang, hashed),
    ).fetchone()
    return row["text"] if row else None


def stat_at_level(base: Optional[float], growth: Optional[float], level: int) -> Optional[float]:
    if base is None:
        return None
    if growth is None:
        return round(base, 4)
    return round(base + growth * (level - 1), 4)


def build_avatar_level_stats(promotions: List[Dict[str, Any]], max_level: int = 80) -> List[Dict[str, Any]]:
    valid = [row for row in promotions if row.get("max_level") is not None]
    valid.sort(key=lambda x: int(x.get("max_level") or 0))
    if not valid:
        return []

    results: List[Dict[str, Any]] = []
    for level in range(1, max_level + 1):
        stage = next((p for p in valid if level <= int(p.get("max_level") or 0)), valid[-1])
        results.append(
            {
                "level": level,
                "promotion": stage.get("promotion"),
                "hp": stat_at_level(stage.get("hp_base"), stage.get("hp_add"), level),
                "attack": stat_at_level(stage.get("attack_base"), stage.get("attack_add"), level),
                "defence": stat_at_level(stage.get("defence_base"), stage.get("defence_add"), level),
                "speed": stat_at_level(stage.get("speed_base"), None, level),
            }
        )
    return results


def extract_hash_value(raw: Any) -> Optional[str]:
    if isinstance(raw, dict):
        raw = raw.get("Hash")
    if raw is None:
        return None
    if isinstance(raw, int):
        return str(raw)
    if isinstance(raw, str):
        token = raw.strip()
        return token if token else None
    return None


def read_json_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


@functools.lru_cache(maxsize=4)
def load_avatar_story_index(resources_root_str: str) -> Tuple[Dict[int, List[Dict[str, Any]]], Dict[int, Optional[str]]]:
    resources_root = Path(resources_root_str)
    atlas_path = resources_root / "ExcelOutput" / "StoryAtlas.json"
    atlas_name_path = resources_root / "ExcelOutput" / "StoryAtlasTextmap.json"

    stories_by_avatar: Dict[int, List[Dict[str, Any]]] = {}
    story_name_hash_by_id: Dict[int, Optional[str]] = {}

    if atlas_path.exists():
        atlas_data = read_json_file(atlas_path)
        if isinstance(atlas_data, list):
            for row in atlas_data:
                if not isinstance(row, dict):
                    continue
                avatar_id = row.get("AvatarID")
                story_id = row.get("StoryID")
                if not isinstance(avatar_id, int) or not isinstance(story_id, int):
                    continue
                stories_by_avatar.setdefault(avatar_id, []).append(
                    {
                        "story_id": story_id,
                        "story_hash": extract_hash_value(row.get("Story")),
                        "unlock": row.get("Unlock"),
                    }
                )

    if atlas_name_path.exists():
        atlas_name_data = read_json_file(atlas_name_path)
        if isinstance(atlas_name_data, list):
            for row in atlas_name_data:
                if not isinstance(row, dict):
                    continue
                story_id = row.get("StoryID")
                if not isinstance(story_id, int):
                    continue
                story_name_hash_by_id[story_id] = extract_hash_value(row.get("StoryName"))

    for avatar_id in list(stories_by_avatar.keys()):
        stories_by_avatar[avatar_id].sort(key=lambda x: int(x.get("story_id") or 0))
    return stories_by_avatar, story_name_hash_by_id


def resolve_hash_texts(conn: sqlite3.Connection, lang: str, hashes: List[Optional[str]]) -> Dict[str, str]:
    clean = sorted({h for h in hashes if h})
    if not clean:
        return {}
    placeholders = ",".join("?" for _ in clean)
    rows = conn.execute(
        f"SELECT hash, text FROM text_map WHERE lang = ? AND hash IN ({placeholders})",
        (lang, *clean),
    ).fetchall()
    return {str(row["hash"]): row["text"] for row in rows}


@functools.lru_cache(maxsize=8)
def resolve_textmap_root(resources_root_str: str) -> Path:
    base = Path(resources_root_str)
    # Relative-path first layout:
    # - if resources_root points to repo root => use hsrdb/Textmap
    # - if resources_root points to hsrdb/    => use Textmap
    if (base / "database").exists() and (base / "web").exists():
        candidates = [base / "Textmap", base / "TextMap"]
    else:
        candidates = [base / "hsrdb" / "Textmap", base / "hsrdb" / "TextMap"]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def ensure_lang_loaded(conn: sqlite3.Connection, resources_root: Path, lang: str) -> bool:
    lang = normalize_lang(lang)
    exists = conn.execute("SELECT 1 FROM text_map WHERE lang = ? LIMIT 1", (lang,)).fetchone()
    if exists is not None:
        return True

    text_root = resolve_textmap_root(str(resources_root.resolve()))
    merged: Dict[str, str] = {}
    for name in (f"TextMapMain{lang}.json", f"TextMap{lang}.json"):
        path = text_root / name
        if not path.exists():
            continue
        try:
            data = read_json_file(path)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        for k, v in data.items():
            merged[str(k)] = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)

    if not merged:
        return False

    conn.executemany(
        "INSERT INTO text_map(lang, hash, text) VALUES(?, ?, ?) ON CONFLICT(lang, hash) DO UPDATE SET text=excluded.text",
        [(lang, k, v) for k, v in merged.items()],
    )
    return True


@functools.lru_cache(maxsize=4)
def load_light_cone_index(resources_root_str: str) -> Dict[int, Dict[str, Any]]:
    resources_root = Path(resources_root_str)
    eq_cfg_path = resources_root / "ExcelOutput" / "EquipmentConfig.json"
    eq_skill_path = resources_root / "ExcelOutput" / "EquipmentSkillConfig.json"
    if not eq_cfg_path.exists() or not eq_skill_path.exists():
        return {}

    eq_data = read_json_file(eq_cfg_path)
    eq_skill_data = read_json_file(eq_skill_path)
    if not isinstance(eq_data, list) or not isinstance(eq_skill_data, list):
        return {}

    skill_by_id: Dict[int, List[Dict[str, Any]]] = {}
    for row in eq_skill_data:
        if not isinstance(row, dict):
            continue
        skill_id = row.get("SkillID")
        level = row.get("Level")
        if not isinstance(skill_id, int) or not isinstance(level, int):
            continue
        skill_by_id.setdefault(skill_id, []).append(
            {
                "level": level,
                "skill_name_hash": extract_hash_value(row.get("SkillName")),
                "skill_desc_hash": extract_hash_value(row.get("SkillDesc")),
                "ability_name": row.get("AbilityName") if isinstance(row.get("AbilityName"), str) else None,
                "param_list": row.get("ParamList"),
                "ability_property": row.get("AbilityProperty"),
            }
        )

    out: Dict[int, Dict[str, Any]] = {}
    for row in eq_data:
        if not isinstance(row, dict):
            continue
        equipment_id = row.get("EquipmentID")
        skill_id = row.get("SkillID")
        if not isinstance(equipment_id, int):
            continue
        levels = skill_by_id.get(skill_id, []) if isinstance(skill_id, int) else []
        levels.sort(key=lambda x: int(x.get("level") or 0))
        out[equipment_id] = {
            "equipment_id": equipment_id,
            "skill_id": skill_id,
            "avatar_base_type": row.get("AvatarBaseType") if isinstance(row.get("AvatarBaseType"), str) else None,
            "max_rank": row.get("MaxRank"),
            "max_promotion": row.get("MaxPromotion"),
            "thumbnail_path": row.get("ThumbnailPath") if isinstance(row.get("ThumbnailPath"), str) else None,
            "image_path": row.get("ImagePath") if isinstance(row.get("ImagePath"), str) else None,
            "levels": levels,
        }
    return out


def build_light_cone_summary_map(conn: sqlite3.Connection, lang: str, resources_root: Path, equipment_ids: List[int]) -> Dict[int, Dict[str, Any]]:
    index = load_light_cone_index(str(resources_root.resolve()))
    needed_hashes: List[Optional[str]] = []
    base: Dict[int, Dict[str, Any]] = {}

    for equipment_id in equipment_ids:
        entry = index.get(equipment_id)
        if not entry:
            continue
        levels = entry.get("levels") or []
        lv1 = levels[0] if levels else None
        if not lv1:
            continue
        needed_hashes.extend([lv1.get("skill_name_hash"), lv1.get("skill_desc_hash")])
        base[equipment_id] = {
            "equipment_id": equipment_id,
            "skill_id": entry.get("skill_id"),
            "avatar_base_type": entry.get("avatar_base_type"),
            "max_rank": entry.get("max_rank"),
            "max_promotion": entry.get("max_promotion"),
            "skill_name_hash": lv1.get("skill_name_hash"),
            "skill_desc_hash": lv1.get("skill_desc_hash"),
            "param_values": parse_param_values(lv1.get("param_list")),
            "skill_name": None,
            "skill_desc": None,
        }

    text_map = resolve_hash_texts(conn, lang, needed_hashes)
    for equipment_id, row in base.items():
        name_hash = row.get("skill_name_hash")
        desc_hash = row.get("skill_desc_hash")
        if name_hash:
            row["skill_name"] = text_map.get(str(name_hash))
        if desc_hash:
            template = text_map.get(str(desc_hash))
            row["skill_desc"] = apply_param_template(template, row.get("param_values")) if template else None
    return base


def build_light_cone_detail(conn: sqlite3.Connection, lang: str, resources_root: Path, equipment_id: int) -> Optional[Dict[str, Any]]:
    index = load_light_cone_index(str(resources_root.resolve()))
    entry = index.get(equipment_id)
    if not entry:
        return None

    levels = entry.get("levels") or []
    needed_hashes: List[Optional[str]] = []
    for lv in levels:
        needed_hashes.extend([lv.get("skill_name_hash"), lv.get("skill_desc_hash")])
    text_map = resolve_hash_texts(conn, lang, needed_hashes)

    out_levels: List[Dict[str, Any]] = []
    for lv in levels:
        name_hash = lv.get("skill_name_hash")
        desc_hash = lv.get("skill_desc_hash")
        desc_template = text_map.get(str(desc_hash)) if desc_hash else None
        params = parse_param_values(lv.get("param_list"))
        out_levels.append(
            {
                "level": lv.get("level"),
                "skill_name": text_map.get(str(name_hash)) if name_hash else None,
                "skill_desc": apply_param_template(desc_template, params) if desc_template else None,
                "param_values": params,
            }
        )

    return {
        "equipment_id": equipment_id,
        "skill_id": entry.get("skill_id"),
        "avatar_base_type": entry.get("avatar_base_type"),
        "max_rank": entry.get("max_rank"),
        "max_promotion": entry.get("max_promotion"),
        "thumbnail_path": entry.get("thumbnail_path"),
        "image_path": entry.get("image_path"),
        "levels": out_levels,
    }


def numeric_value(raw: Any) -> Optional[float]:
    if isinstance(raw, dict):
        raw = raw.get("Value")
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        token = raw.strip()
        if not token:
            return None
        try:
            return float(token)
        except ValueError:
            return None
    return None


def parse_override_skill_params(raw: Any) -> Dict[int, Any]:
    out: Dict[int, Any] = {}
    if not isinstance(raw, list):
        return out
    for row in raw:
        if not isinstance(row, dict):
            continue
        skill_id: Optional[int] = None
        params: Any = None
        for val in row.values():
            if skill_id is None and isinstance(val, int):
                skill_id = val
            elif params is None and isinstance(val, list):
                params = val
        if skill_id is not None and params is not None:
            out[int(skill_id)] = params
    return out


def resolve_text_with_fallback(conn: sqlite3.Connection, lang: str, raw_key: Optional[str], fallback: Optional[str] = None) -> Optional[str]:
    text = resolve_text_from_key(conn, lang, raw_key)
    if text:
        return text
    if lang != "CHS":
        text = resolve_text_from_key(conn, "CHS", raw_key)
        if text:
            return text
    if lang != "EN":
        text = resolve_text_from_key(conn, "EN", raw_key)
        if text:
            return text
    return fallback


@functools.lru_cache(maxsize=4)
def load_monster_index(resources_root_str: str) -> Dict[str, Any]:
    resources_root = Path(resources_root_str)
    cfg_path = resources_root / "ExcelOutput" / "MonsterConfig.json"
    tpl_path = resources_root / "ExcelOutput" / "MonsterTemplateConfig.json"
    skill_path = resources_root / "ExcelOutput" / "MonsterSkillConfig.json"
    if not cfg_path.exists() or not tpl_path.exists() or not skill_path.exists():
        return {"items": [], "by_id": {}, "skills": {}, "rank": [], "weakness": []}

    cfg_data = read_json_file(cfg_path)
    tpl_data = read_json_file(tpl_path)
    skill_data = read_json_file(skill_path)
    if not isinstance(cfg_data, list) or not isinstance(tpl_data, list) or not isinstance(skill_data, list):
        return {"items": [], "by_id": {}, "skills": {}, "rank": [], "weakness": []}

    template_by_id: Dict[int, Dict[str, Any]] = {}
    for row in tpl_data:
        if not isinstance(row, dict):
            continue
        template_id = row.get("MonsterTemplateID")
        if not isinstance(template_id, int):
            continue
        template_by_id[template_id] = {
            "monster_template_id": template_id,
            "name_hash": extract_hash_value(row.get("MonsterName")),
            "rank": row.get("Rank") if isinstance(row.get("Rank"), str) else None,
            "icon_path": row.get("IconPath") if isinstance(row.get("IconPath"), str) else None,
            "round_icon_path": row.get("RoundIconPath") if isinstance(row.get("RoundIconPath"), str) else None,
            "image_path": row.get("ImagePath") if isinstance(row.get("ImagePath"), str) else None,
            "manikin_image_path": row.get("ManikinImagePath") if isinstance(row.get("ManikinImagePath"), str) else None,
            "json_config": row.get("JsonConfig") if isinstance(row.get("JsonConfig"), str) else None,
            "prefab_path": row.get("PrefabPath") if isinstance(row.get("PrefabPath"), str) else None,
            "ai_path": row.get("AIPath") if isinstance(row.get("AIPath"), str) else None,
            "stance_type": row.get("StanceType") if isinstance(row.get("StanceType"), str) else None,
            "attack_base": numeric_value(row.get("AttackBase")),
            "defence_base": numeric_value(row.get("DefenceBase")),
            "hp_base": numeric_value(row.get("HPBase")),
            "speed_base": numeric_value(row.get("SpeedBase")),
            "stance_base": numeric_value(row.get("StanceBase")),
            "critical_damage_base": numeric_value(row.get("CriticalDamageBase")),
            "status_resistance_base": numeric_value(row.get("StatusResistanceBase")),
            "minimum_fatigue_ratio": numeric_value(row.get("MinimumFatigueRatio")),
        }

    skill_by_id: Dict[int, Dict[str, Any]] = {}
    for row in skill_data:
        if not isinstance(row, dict):
            continue
        skill_id = row.get("SkillID")
        if not isinstance(skill_id, int):
            continue
        skill_by_id[skill_id] = {
            "skill_id": skill_id,
            "name_hash": extract_hash_value(row.get("SkillName")),
            "desc_hash": extract_hash_value(row.get("SkillDesc")),
            "type_desc_hash": extract_hash_value(row.get("SkillTypeDesc")),
            "tag_hash": extract_hash_value(row.get("SkillTag")),
            "damage_type": row.get("DamageType") if isinstance(row.get("DamageType"), str) else None,
            "attack_type": row.get("AttackType") if isinstance(row.get("AttackType"), str) else None,
            "skill_trigger_key": row.get("SkillTriggerKey") if isinstance(row.get("SkillTriggerKey"), str) else None,
            "icon_path": row.get("IconPath") if isinstance(row.get("IconPath"), str) else None,
            "param_list": row.get("ParamList"),
            "phase_list": row.get("PhaseList"),
        }

    out: List[Dict[str, Any]] = []
    out_by_id: Dict[int, Dict[str, Any]] = {}
    ranks: set[str] = set()
    weakness_set: set[str] = set()

    for row in cfg_data:
        if not isinstance(row, dict):
            continue
        monster_id = row.get("MonsterID")
        if not isinstance(monster_id, int):
            continue
        template_id = row.get("MonsterTemplateID")
        template = template_by_id.get(template_id) if isinstance(template_id, int) else None

        skill_ids = [int(v) for v in (row.get("SkillList") or []) if isinstance(v, int)]
        weaknesses = [v for v in (row.get("StanceWeakList") or []) if isinstance(v, str) and v]
        for token in weaknesses:
            weakness_set.add(token)

        resistances: List[Dict[str, Any]] = []
        for r in (row.get("DamageTypeResistance") or []):
            if not isinstance(r, dict):
                continue
            damage_type = r.get("DamageType")
            if not isinstance(damage_type, str) or not damage_type:
                continue
            resistances.append(
                {
                    "damage_type": damage_type,
                    "value": numeric_value(r.get("Value")),
                }
            )

        rank = template.get("rank") if template else None
        if isinstance(rank, str) and rank:
            ranks.add(rank)

        item = {
            "monster_id": monster_id,
            "monster_template_id": template_id if isinstance(template_id, int) else None,
            "name_hash": extract_hash_value(row.get("MonsterName")) or (template.get("name_hash") if template else None),
            "introduction_hash": extract_hash_value(row.get("MonsterIntroduction")),
            "rank": rank,
            "elite_group": row.get("EliteGroup"),
            "hard_level_group": row.get("HardLevelGroup"),
            "attack_modify_ratio": numeric_value(row.get("AttackModifyRatio")),
            "defence_modify_ratio": numeric_value(row.get("DefenceModifyRatio")),
            "hp_modify_ratio": numeric_value(row.get("HPModifyRatio")),
            "speed_modify_ratio": numeric_value(row.get("SpeedModifyRatio")),
            "stance_modify_ratio": numeric_value(row.get("StanceModifyRatio")),
            "stance_weak_list": weaknesses,
            "damage_type_resistance": resistances,
            "ability_name_keys": [str(v) for v in (row.get("AbilityNameList") or []) if isinstance(v, str) and v],
            "skill_ids": skill_ids,
            "override_skill_params": parse_override_skill_params(row.get("OverrideSkillParams")),
            "icon_path": template.get("icon_path") if template else None,
            "round_icon_path": template.get("round_icon_path") if template else None,
            "image_path": template.get("image_path") if template else None,
            "manikin_image_path": template.get("manikin_image_path") if template else None,
            "json_config": template.get("json_config") if template else None,
            "prefab_path": template.get("prefab_path") if template else None,
            "ai_path": template.get("ai_path") if template else None,
            "stance_type": template.get("stance_type") if template else None,
            "attack_base": template.get("attack_base") if template else None,
            "defence_base": template.get("defence_base") if template else None,
            "hp_base": template.get("hp_base") if template else None,
            "speed_base": template.get("speed_base") if template else None,
            "stance_base": template.get("stance_base") if template else None,
            "critical_damage_base": template.get("critical_damage_base") if template else None,
            "status_resistance_base": template.get("status_resistance_base") if template else None,
            "minimum_fatigue_ratio": template.get("minimum_fatigue_ratio") if template else None,
        }
        out.append(item)
        out_by_id[monster_id] = item

    out.sort(key=lambda x: int(x.get("monster_id") or 0))
    return {
        "items": out,
        "by_id": out_by_id,
        "skills": skill_by_id,
        "rank": sorted(ranks),
        "weakness": sorted(weakness_set),
    }


class AppHandler(SimpleHTTPRequestHandler):
    server_version = "HSRDB/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    @property
    def db_path(self) -> Path:
        return self.db_paths["default"]

    @property
    def db_paths(self) -> Dict[str, Path]:
        return self.server.db_paths  # type: ignore[attr-defined]

    @property
    def web_root(self) -> Path:
        return self.server.web_root  # type: ignore[attr-defined]

    @property
    def resources_root(self) -> Path:
        return self.server.resources_root  # type: ignore[attr-defined]

    def _db(self, module: str = "default") -> sqlite3.Connection:
        mod = (module or "default").strip().lower()
        path = self.db_paths.get(mod) or self.db_paths.get("default")
        if path is None:
            raise FileNotFoundError(f"No database path configured for module={module}")
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn

    def _module_name(self, raw: Optional[str], default: str = "default") -> str:
        token = (raw or "").strip().lower()
        if not token:
            return default
        return token if token in SUPPORTED_MODULES else default

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        body = path.read_bytes()
        ctype, _ = mimetypes.guess_type(str(path))
        self.send_response(200)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            self._handle_api(path, parse_qs(parsed.query))
            return

        if path == "/":
            self._send_file(self.web_root / "index.html")
            return

        if path.startswith("/web/"):
            rel = unquote(path[len("/web/"):])
            rel_path = Path(rel)
            if any(part in ("..", "") for part in rel_path.parts):
                self.send_error(HTTPStatus.BAD_REQUEST, "Invalid path")
                return
            self._send_file(self.web_root / rel_path)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def _handle_api(self, path: str, query: Dict[str, List[str]]) -> None:
        try:
            if path == "/api/stats":
                self._send_json(self._api_stats())
                return
            if path == "/api/search/dialogue":
                self._send_json(self._api_search_dialogue(query))
                return
            if path.startswith("/api/dialogue/") and path.endswith("/refs"):
                parts = path.strip("/").split("/")
                if len(parts) == 4:
                    self._send_json(self._api_dialogue_refs(int(parts[2]), query))
                    return
            if path == "/api/search/mission":
                self._send_json(self._api_search_mission(query))
                return
            if path.startswith("/api/mission/"):
                parts = path.strip("/").split("/")
                if len(parts) == 3:
                    self._send_json(self._api_mission_detail(int(parts[2]), query))
                    return
            if path == "/api/search/avatar":
                self._send_json(self._api_search_avatar(query))
                return
            if path.startswith("/api/avatar/"):
                parts = path.strip("/").split("/")
                if len(parts) == 3:
                    self._send_json(self._api_avatar_detail(int(parts[2]), query))
                    return
            if path == "/api/search/item":
                self._send_json(self._api_search_item(query))
                return
            if path == "/api/item/facets":
                self._send_json(self._api_item_facets())
                return
            if path.startswith("/api/item/"):
                parts = path.strip("/").split("/")
                if len(parts) == 3:
                    self._send_json(self._api_item_detail(int(parts[2]), query))
                    return
            if path == "/api/search/monster":
                self._send_json(self._api_search_monster(query))
                return
            if path == "/api/monster/facets":
                self._send_json(self._api_monster_facets())
                return
            if path.startswith("/api/monster/"):
                parts = path.strip("/").split("/")
                if len(parts) == 3:
                    self._send_json(self._api_monster_detail(int(parts[2]), query))
                    return
            if path == "/api/term/explain":
                self._send_json(self._api_term_explain(query))
                return
            if path == "/api/search/text":
                self._send_json(self._api_search_text(query))
                return

            self._send_json({"error": "not_found"}, status=404)
        except ValueError:
            self._send_json({"error": "bad_request"}, status=400)
        except Exception as exc:
            self._send_json({"error": "server_error", "detail": str(exc)}, status=500)

    def _api_stats(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        with self._db("default") as conn:
            rows = conn.execute("SELECT key, value FROM meta WHERE key IN ('build_at', 'elapsed_seconds', 'table_counts')").fetchall()
            out = {row["key"]: row["value"] for row in rows}
            for key in ("elapsed_seconds", "table_counts"):
                if key in out:
                    try:
                        out[key] = json.loads(out[key])
                    except Exception:
                        pass

        def count_in(module: str, table: str) -> Optional[int]:
            try:
                with self._db(module) as conn:
                    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            except Exception:
                return None

        table_counts = out.get("table_counts")
        if not isinstance(table_counts, dict):
            table_counts = {}
        mapping = {
            "talk_sentence": ("dialogue", "talk_sentence"),
            "story_reference": ("mission", "story_reference"),
            "main_mission": ("mission", "main_mission"),
            "avatar": ("avatar", "avatar"),
            "item": ("item", "item"),
        }
        for key, (module, table) in mapping.items():
            value = count_in(module, table)
            if value is not None:
                table_counts[key] = value
        out["table_counts"] = table_counts
        try:
            out["monster_count"] = len((load_monster_index(str(self.resources_root.resolve())).get("items") or []))
        except Exception:
            out["monster_count"] = 0
        return out

    def _api_search_dialogue(self, query: Dict[str, List[str]]) -> Dict[str, Any]:
        q = qv(query, "q")
        lang = normalize_lang(qv(query, "lang", "CHS"))
        order = qv(query, "order", "asc").lower()
        order = "desc" if order == "desc" else "asc"
        order_sql = "DESC" if order == "desc" else "ASC"
        page, page_size, offset = paging(query, default_size=20, max_size=100)
        speaker_col = "speaker_en" if lang == "EN" else "speaker_chs"
        text_col = "text_en" if lang == "EN" else "text_chs"

        with self._db("dialogue") as conn:
            if lang in ("CHS", "EN"):
                if not q:
                    total = conn.execute("SELECT COUNT(*) FROM talk_sentence").fetchone()[0]
                    sql = f"""
                        SELECT talk_sentence_id, {speaker_col} AS speaker, {text_col} AS text
                        FROM talk_sentence
                        ORDER BY talk_sentence_id {order_sql}
                        LIMIT ? OFFSET ?
                    """
                    rows = conn.execute(sql, (page_size, offset)).fetchall()
                else:
                    total = 0
                    rows = []
                    like = f"%{q}%"
                    if lang == "EN":
                        count_sql = f"""
                            SELECT COUNT(*)
                            FROM talk_sentence
                            WHERE ({speaker_col} LIKE ? OR {text_col} LIKE ?)
                        """
                        total = conn.execute(count_sql, (like, like)).fetchone()[0]
                        sql = f"""
                            SELECT talk_sentence_id, {speaker_col} AS speaker, {text_col} AS text
                            FROM talk_sentence
                            WHERE ({speaker_col} LIKE ? OR {text_col} LIKE ?)
                            ORDER BY talk_sentence_id {order_sql}
                            LIMIT ? OFFSET ?
                        """
                        rows = conn.execute(sql, (like, like, page_size, offset)).fetchall()
                    else:
                        fts_q = norm_fts_query(q)
                        try:
                            count_sql = """
                                SELECT COUNT(*)
                                FROM talk_sentence_fts f
                                JOIN talk_sentence t ON t.talk_sentence_id = f.rowid
                                WHERE talk_sentence_fts MATCH ?
                            """
                            total = conn.execute(count_sql, (fts_q,)).fetchone()[0]
                            sql = f"""
                                SELECT t.talk_sentence_id, t.{speaker_col} AS speaker, t.{text_col} AS text
                                FROM talk_sentence_fts f
                                JOIN talk_sentence t ON t.talk_sentence_id = f.rowid
                                WHERE talk_sentence_fts MATCH ?
                                ORDER BY t.talk_sentence_id {order_sql}
                                LIMIT ? OFFSET ?
                            """
                            rows = conn.execute(sql, (fts_q, page_size, offset)).fetchall()
                        except sqlite3.OperationalError:
                            total = 0
                            rows = []

                        if total == 0:
                            count_sql = f"""
                                SELECT COUNT(*)
                                FROM talk_sentence
                                WHERE ({speaker_col} LIKE ? OR {text_col} LIKE ?)
                            """
                            total = conn.execute(count_sql, (like, like)).fetchone()[0]
                            sql = f"""
                                SELECT talk_sentence_id, {speaker_col} AS speaker, {text_col} AS text
                                FROM talk_sentence
                                WHERE ({speaker_col} LIKE ? OR {text_col} LIKE ?)
                                ORDER BY talk_sentence_id {order_sql}
                                LIMIT ? OFFSET ?
                            """
                            rows = conn.execute(sql, (like, like, page_size, offset)).fetchall()
            else:
                ensure_lang_loaded(conn, self.resources_root, lang)
                if not q:
                    total = conn.execute("SELECT COUNT(*) FROM talk_sentence").fetchone()[0]
                    sql = f"""
                        SELECT t.talk_sentence_id,
                               COALESCE(sp.text, '') AS speaker,
                               COALESCE(tx.text, '') AS text
                        FROM talk_sentence t
                        LEFT JOIN text_map sp ON sp.lang = ? AND sp.hash = t.speaker_hash
                        LEFT JOIN text_map tx ON tx.lang = ? AND tx.hash = t.text_hash
                        ORDER BY t.talk_sentence_id {order_sql}
                        LIMIT ? OFFSET ?
                    """
                    rows = conn.execute(sql, (lang, lang, page_size, offset)).fetchall()
                else:
                    like = f"%{q}%"
                    count_sql = """
                        SELECT COUNT(*)
                        FROM talk_sentence t
                        LEFT JOIN text_map sp ON sp.lang = ? AND sp.hash = t.speaker_hash
                        LEFT JOIN text_map tx ON tx.lang = ? AND tx.hash = t.text_hash
                        WHERE (sp.text LIKE ? OR tx.text LIKE ?)
                    """
                    total = conn.execute(count_sql, (lang, lang, like, like)).fetchone()[0]
                    sql = f"""
                        SELECT t.talk_sentence_id,
                               COALESCE(sp.text, '') AS speaker,
                               COALESCE(tx.text, '') AS text
                        FROM talk_sentence t
                        LEFT JOIN text_map sp ON sp.lang = ? AND sp.hash = t.speaker_hash
                        LEFT JOIN text_map tx ON tx.lang = ? AND tx.hash = t.text_hash
                        WHERE (sp.text LIKE ? OR tx.text LIKE ?)
                        ORDER BY t.talk_sentence_id {order_sql}
                        LIMIT ? OFFSET ?
                    """
                    rows = conn.execute(sql, (lang, lang, like, like, page_size, offset)).fetchall()

        payload = {
            "q": q,
            "lang": lang,
            "order": order,
            "items": [dict(row) for row in rows],
        }
        return with_paging_meta(payload, page, page_size, total)

    def _api_dialogue_refs(self, talk_sentence_id: int, query: Dict[str, List[str]]) -> Dict[str, Any]:
        page, page_size, offset = paging(query, default_size=30, max_size=200)
        with self._db("mission") as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM story_reference WHERE talk_sentence_id = ?",
                (talk_sentence_id,),
            ).fetchone()[0]
            rows = conn.execute(
                """
                SELECT source_path, source_group, json_path, task_type, timeline_name,
                       performance_type, performance_id, trigger_custom_string, custom_string
                FROM story_reference
                WHERE talk_sentence_id = ?
                ORDER BY source_path, json_path
                LIMIT ? OFFSET ?
                """,
                (talk_sentence_id, page_size, offset),
            ).fetchall()
        payload = {"talk_sentence_id": talk_sentence_id, "items": [dict(row) for row in rows]}
        return with_paging_meta(payload, page, page_size, total)

    def _api_search_mission(self, query: Dict[str, List[str]]) -> Dict[str, Any]:
        q = qv(query, "q")
        lang = normalize_lang(qv(query, "lang", "CHS"))
        page, page_size, offset = paging(query, default_size=20, max_size=100)
        name_col = "name_en" if lang == "EN" else "name_chs"
        target_col = "target_en" if lang == "EN" else "target_chs"
        desc_col = "description_en" if lang == "EN" else "description_chs"
        sub_preview_limit = as_int(qv(query, "sub_preview_limit", "8"), 8, 1, 50)
        content_exists_pred = """
            (
                EXISTS (
                    SELECT 1
                    FROM sub_mission sx
                    WHERE sx.main_mission_guess = m.main_mission_id
                )
                OR EXISTS (
                    SELECT 1
                    FROM story_reference sr
                    WHERE sr.source_path LIKE ('Story/Mission/' || m.main_mission_id || '/%')
                       OR sr.source_path LIKE ('Config/Level/Mission/' || m.main_mission_id || '/%')
                )
            )
        """

        with self._db("mission") as conn:
            if lang in ("CHS", "EN"):
                if not q:
                    total = conn.execute(
                        f"""
                        SELECT COUNT(*)
                        FROM main_mission m
                        WHERE {content_exists_pred}
                        """
                    ).fetchone()[0]
                    sql = f"""
                        SELECT m.main_mission_id, m.mission_type, m.{name_col} AS name, m.chapter_id, m.world_id, m.display_priority
                        FROM main_mission m
                        WHERE {content_exists_pred}
                        ORDER BY m.main_mission_id ASC
                        LIMIT ? OFFSET ?
                    """
                    rows = conn.execute(sql, (page_size, offset)).fetchall()
                else:
                    like = f"%{q}%"
                    total = conn.execute(
                        f"""
                        SELECT COUNT(*)
                        FROM main_mission m
                        WHERE {content_exists_pred}
                          AND (
                            m.{name_col} LIKE ?
                            OR CAST(m.main_mission_id AS TEXT) LIKE ?
                            OR EXISTS (
                                SELECT 1
                                FROM sub_mission s
                                WHERE s.main_mission_guess = m.main_mission_id
                                  AND (
                                    s.{target_col} LIKE ?
                                    OR s.{desc_col} LIKE ?
                                    OR CAST(s.sub_mission_id AS TEXT) LIKE ?
                                  )
                            )
                          )
                        """,
                        (like, like, like, like, like),
                    ).fetchone()[0]
                    rows = conn.execute(
                        f"""
                        SELECT m.main_mission_id, m.mission_type, m.{name_col} AS name, m.chapter_id, m.world_id, m.display_priority
                        FROM main_mission m
                        WHERE {content_exists_pred}
                          AND (
                            m.{name_col} LIKE ?
                            OR CAST(m.main_mission_id AS TEXT) LIKE ?
                            OR EXISTS (
                                SELECT 1
                                FROM sub_mission s
                                WHERE s.main_mission_guess = m.main_mission_id
                                  AND (
                                    s.{target_col} LIKE ?
                                    OR s.{desc_col} LIKE ?
                                    OR CAST(s.sub_mission_id AS TEXT) LIKE ?
                                  )
                            )
                          )
                        ORDER BY m.main_mission_id ASC
                        LIMIT ? OFFSET ?
                        """,
                        (like, like, like, like, like, page_size, offset),
                    ).fetchall()
            else:
                ensure_lang_loaded(conn, self.resources_root, lang)
                if not q:
                    total = conn.execute(
                        f"""
                        SELECT COUNT(*)
                        FROM main_mission m
                        WHERE {content_exists_pred}
                        """
                    ).fetchone()[0]
                    rows = conn.execute(
                        f"""
                        SELECT m.main_mission_id, m.mission_type, COALESCE(tm.text, '') AS name,
                               m.chapter_id, m.world_id, m.display_priority
                        FROM main_mission m
                        LEFT JOIN text_map tm ON tm.lang = ? AND tm.hash = m.name_hash
                        WHERE {content_exists_pred}
                        ORDER BY m.main_mission_id ASC
                        LIMIT ? OFFSET ?
                        """,
                        (lang, page_size, offset),
                    ).fetchall()
                else:
                    like = f"%{q}%"
                    total = conn.execute(
                        f"""
                        SELECT COUNT(*)
                        FROM main_mission m
                        WHERE {content_exists_pred}
                          AND (
                            CAST(m.main_mission_id AS TEXT) LIKE ?
                            OR EXISTS (
                                SELECT 1
                                FROM text_map tmn
                                WHERE tmn.lang = ?
                                  AND tmn.hash = m.name_hash
                                  AND tmn.text LIKE ?
                            )
                            OR EXISTS (
                                SELECT 1
                                FROM sub_mission s
                                LEFT JOIN text_map st ON st.lang = ? AND st.hash = s.target_hash
                                LEFT JOIN text_map sd ON sd.lang = ? AND sd.hash = s.description_hash
                                WHERE s.main_mission_guess = m.main_mission_id
                                  AND (
                                    st.text LIKE ?
                                    OR sd.text LIKE ?
                                    OR CAST(s.sub_mission_id AS TEXT) LIKE ?
                                  )
                            )
                          )
                        """,
                        (like, lang, like, lang, lang, like, like, like),
                    ).fetchone()[0]
                    rows = conn.execute(
                        f"""
                        SELECT m.main_mission_id, m.mission_type, COALESCE(tm.text, '') AS name,
                               m.chapter_id, m.world_id, m.display_priority
                        FROM main_mission m
                        LEFT JOIN text_map tm ON tm.lang = ? AND tm.hash = m.name_hash
                        WHERE {content_exists_pred}
                          AND (
                            CAST(m.main_mission_id AS TEXT) LIKE ?
                            OR tm.text LIKE ?
                            OR EXISTS (
                                SELECT 1
                                FROM sub_mission s
                                LEFT JOIN text_map st ON st.lang = ? AND st.hash = s.target_hash
                                LEFT JOIN text_map sd ON sd.lang = ? AND sd.hash = s.description_hash
                                WHERE s.main_mission_guess = m.main_mission_id
                                  AND (
                                    st.text LIKE ?
                                    OR sd.text LIKE ?
                                    OR CAST(s.sub_mission_id AS TEXT) LIKE ?
                                  )
                            )
                          )
                        ORDER BY m.main_mission_id ASC
                        LIMIT ? OFFSET ?
                        """,
                        (lang, like, like, lang, lang, like, like, like, page_size, offset),
                    ).fetchall()

            item_rows = [dict(row) for row in rows]
            mission_ids = [int(r["main_mission_id"]) for r in item_rows]
            sub_map: Dict[int, List[Dict[str, Any]]] = {}
            if mission_ids:
                placeholders = ",".join("?" for _ in mission_ids)
                if lang in ("CHS", "EN"):
                    sub_rows = conn.execute(
                        f"""
                        SELECT main_mission_guess, sub_mission_id, {target_col} AS target, {desc_col} AS description
                        FROM sub_mission
                        WHERE main_mission_guess IN ({placeholders})
                        ORDER BY main_mission_guess ASC, sub_mission_id ASC
                        """,
                        mission_ids,
                    ).fetchall()
                else:
                    sub_rows = conn.execute(
                        f"""
                        SELECT s.main_mission_guess, s.sub_mission_id,
                               COALESCE(st.text, '') AS target,
                               COALESCE(sd.text, '') AS description
                        FROM sub_mission s
                        LEFT JOIN text_map st ON st.lang = ? AND st.hash = s.target_hash
                        LEFT JOIN text_map sd ON sd.lang = ? AND sd.hash = s.description_hash
                        WHERE s.main_mission_guess IN ({placeholders})
                        ORDER BY s.main_mission_guess ASC, s.sub_mission_id ASC
                        """,
                        (lang, lang, *mission_ids),
                    ).fetchall()
                for row in sub_rows:
                    main_id = int(row["main_mission_guess"])
                    sub_map.setdefault(main_id, []).append(
                        {
                            "sub_mission_id": row["sub_mission_id"],
                            "target": row["target"],
                            "description": row["description"],
                        }
                    )

            for item in item_rows:
                subs = sub_map.get(int(item["main_mission_id"]), [])
                item["sub_mission_count"] = len(subs)
                item["sub_missions_preview"] = subs[:sub_preview_limit]
                item["sub_missions_more"] = max(0, len(subs) - sub_preview_limit)

        payload = {"q": q, "lang": lang, "items": item_rows}
        return with_paging_meta(payload, page, page_size, total)

    def _api_mission_detail(self, main_mission_id: int, query: Dict[str, List[str]]) -> Dict[str, Any]:
        lang = normalize_lang((query.get("lang", ["CHS"])[0] or "CHS"))
        name_col = "name_en" if lang == "EN" else "name_chs"
        target_col = "target_en" if lang == "EN" else "target_chs"
        desc_col = "description_en" if lang == "EN" else "description_chs"
        speaker_col = "speaker_en" if lang == "EN" else "speaker_chs"
        text_col = "text_en" if lang == "EN" else "text_chs"
        ref_limit = as_int(query.get("ref_limit", ["200"])[0], 200, 1, 1000)
        dialogue_limit = as_int(query.get("dialogue_limit", ["300"])[0], 300, 1, 3000)

        with self._db("mission") as conn:
            if lang in ("CHS", "EN"):
                mission = conn.execute(
                    f"SELECT main_mission_id, mission_type, world_id, chapter_id, mission_pack, display_priority, {name_col} AS name FROM main_mission WHERE main_mission_id = ?",
                    (main_mission_id,),
                ).fetchone()
            else:
                ensure_lang_loaded(conn, self.resources_root, lang)
                mission = conn.execute(
                    """
                    SELECT m.main_mission_id, m.mission_type, m.world_id, m.chapter_id, m.mission_pack, m.display_priority,
                           COALESCE(tm.text, '') AS name
                    FROM main_mission m
                    LEFT JOIN text_map tm ON tm.lang = ? AND tm.hash = m.name_hash
                    WHERE m.main_mission_id = ?
                    """,
                    (lang, main_mission_id),
                ).fetchone()
            if mission is None:
                return {"error": "not_found", "main_mission_id": main_mission_id}

            if lang in ("CHS", "EN"):
                subs = conn.execute(
                    f"""
                    SELECT sub_mission_id, {target_col} AS target, {desc_col} AS description
                    FROM sub_mission
                    WHERE main_mission_guess = ?
                    ORDER BY sub_mission_id
                    """,
                    (main_mission_id,),
                ).fetchall()
            else:
                subs = conn.execute(
                    """
                    SELECT s.sub_mission_id, COALESCE(st.text, '') AS target, COALESCE(sd.text, '') AS description
                    FROM sub_mission s
                    LEFT JOIN text_map st ON st.lang = ? AND st.hash = s.target_hash
                    LEFT JOIN text_map sd ON sd.lang = ? AND sd.hash = s.description_hash
                    WHERE s.main_mission_guess = ?
                    ORDER BY s.sub_mission_id
                    """,
                    (lang, lang, main_mission_id),
                ).fetchall()

            pack_links = conn.execute(
                "SELECT mission_pack FROM mission_pack_link WHERE main_mission_id = ? ORDER BY mission_pack",
                (main_mission_id,),
            ).fetchall()

            like_story = f"Story/Mission/{main_mission_id}/%"
            like_cfg = f"Config/Level/Mission/{main_mission_id}/%"
            refs_base = conn.execute(
                """
                SELECT sr.source_path, sr.source_group, sr.json_path, sr.task_type, sr.timeline_name,
                       sr.performance_type, sr.performance_id, sr.talk_sentence_id
                FROM story_reference sr
                WHERE sr.source_path LIKE ? OR sr.source_path LIKE ?
                ORDER BY (sr.talk_sentence_id IS NULL), sr.talk_sentence_id, sr.source_path, sr.json_path
                LIMIT ?
                """,
                (like_story, like_cfg, ref_limit),
            ).fetchall()

        talk_ids = sorted(
            {
                int(row["talk_sentence_id"])
                for row in refs_base
                if isinstance(row["talk_sentence_id"], int)
            }
        )
        talk_map: Dict[int, Dict[str, Any]] = {}
        if talk_ids:
            placeholders = ",".join("?" for _ in talk_ids)
            with self._db("dialogue") as conn:
                if lang in ("CHS", "EN"):
                    talk_rows = conn.execute(
                        f"""
                        SELECT talk_sentence_id, voice_id, {speaker_col} AS speaker, {text_col} AS text
                        FROM talk_sentence
                        WHERE talk_sentence_id IN ({placeholders})
                        """,
                        talk_ids,
                    ).fetchall()
                else:
                    ensure_lang_loaded(conn, self.resources_root, lang)
                    talk_rows = conn.execute(
                        f"""
                        SELECT t.talk_sentence_id, t.voice_id,
                               COALESCE(sp.text, '') AS speaker,
                               COALESCE(tx.text, '') AS text
                        FROM talk_sentence t
                        LEFT JOIN text_map sp ON sp.lang = ? AND sp.hash = t.speaker_hash
                        LEFT JOIN text_map tx ON tx.lang = ? AND tx.hash = t.text_hash
                        WHERE t.talk_sentence_id IN ({placeholders})
                        """,
                        (lang, lang, *talk_ids),
                    ).fetchall()
            for row in talk_rows:
                tid = int(row["talk_sentence_id"])
                talk_map[tid] = {
                    "voice_id": row["voice_id"],
                    "speaker": row["speaker"] or "",
                    "text": row["text"] or "",
                }

        refs: List[Dict[str, Any]] = []
        first_source_by_talk: Dict[int, Tuple[str, str]] = {}
        for row in refs_base:
            item = dict(row)
            tid = item.get("talk_sentence_id")
            if isinstance(tid, int) and tid in talk_map:
                talk = talk_map[tid]
                item["voice_id"] = talk.get("voice_id")
                item["speaker"] = talk.get("speaker") or ""
                item["text"] = talk.get("text") or ""
                if tid not in first_source_by_talk:
                    first_source_by_talk[tid] = (item.get("source_path") or "", item.get("json_path") or "")
            else:
                item["voice_id"] = None
                item["speaker"] = ""
                item["text"] = ""
            refs.append(item)

        dialogues: List[Dict[str, Any]] = []
        for tid in sorted(first_source_by_talk.keys()):
            talk = talk_map.get(tid)
            if not talk:
                continue
            text = str(talk.get("text") or "").strip()
            if not text:
                continue
            source_path, json_path = first_source_by_talk[tid]
            dialogues.append(
                {
                    "talk_sentence_id": tid,
                    "voice_id": talk.get("voice_id"),
                    "speaker": talk.get("speaker") or "",
                    "text": text,
                    "source_path": source_path,
                    "json_path": json_path,
                }
            )
            if len(dialogues) >= dialogue_limit:
                break

        return {
            "main_mission": dict(mission),
            "sub_missions": [dict(row) for row in subs],
            "mission_packs": [row["mission_pack"] for row in pack_links],
            "story_refs": refs,
            "dialogues": dialogues,
        }

    def _api_search_avatar(self, query: Dict[str, List[str]]) -> Dict[str, Any]:
        q = qv(query, "q")
        lang = normalize_lang(qv(query, "lang", "CHS"))
        page, page_size, offset = paging(query, default_size=20, max_size=100)
        name_col = "name_en" if lang == "EN" else "name_chs"
        full_col = "full_name_en" if lang == "EN" else "full_name_chs"

        with self._db("avatar") as conn:
            if lang in ("CHS", "EN"):
                if not q:
                    total = conn.execute("SELECT COUNT(*) FROM avatar").fetchone()[0]
                    sql = f"""
                        SELECT avatar_id, {name_col} AS name, {full_col} AS full_name, rarity, damage_type, avatar_base_type
                        FROM avatar
                        ORDER BY avatar_id
                        LIMIT ? OFFSET ?
                    """
                    rows = conn.execute(sql, (page_size, offset)).fetchall()
                else:
                    like = f"%{q}%"
                    if lang == "EN":
                        total = conn.execute(
                            f"SELECT COUNT(*) FROM avatar WHERE ({name_col} LIKE ? OR {full_col} LIKE ?)",
                            (like, like),
                        ).fetchone()[0]
                        sql = f"""
                            SELECT avatar_id, {name_col} AS name, {full_col} AS full_name, rarity, damage_type, avatar_base_type
                            FROM avatar
                            WHERE ({name_col} LIKE ? OR {full_col} LIKE ?)
                            LIMIT ? OFFSET ?
                        """
                        rows = conn.execute(sql, (like, like, page_size, offset)).fetchall()
                    else:
                        total = 0
                        rows = []
                        try:
                            count_sql = """
                                SELECT COUNT(*)
                                FROM avatar_fts f
                                JOIN avatar a ON a.avatar_id = f.rowid
                                WHERE avatar_fts MATCH ?
                            """
                            total = conn.execute(count_sql, (norm_fts_query(q),)).fetchone()[0]
                            sql = f"""
                                SELECT a.avatar_id, a.{name_col} AS name, a.{full_col} AS full_name, a.rarity, a.damage_type, a.avatar_base_type
                                FROM avatar_fts f
                                JOIN avatar a ON a.avatar_id = f.rowid
                                WHERE avatar_fts MATCH ?
                                LIMIT ? OFFSET ?
                            """
                            rows = conn.execute(sql, (norm_fts_query(q), page_size, offset)).fetchall()
                        except sqlite3.OperationalError:
                            total = 0
                            rows = []

                        if total == 0:
                            total = conn.execute(
                                f"SELECT COUNT(*) FROM avatar WHERE ({name_col} LIKE ? OR {full_col} LIKE ?)",
                                (like, like),
                            ).fetchone()[0]
                            sql = f"""
                                SELECT avatar_id, {name_col} AS name, {full_col} AS full_name, rarity, damage_type, avatar_base_type
                                FROM avatar
                                WHERE ({name_col} LIKE ? OR {full_col} LIKE ?)
                                LIMIT ? OFFSET ?
                            """
                            rows = conn.execute(sql, (like, like, page_size, offset)).fetchall()
            else:
                ensure_lang_loaded(conn, self.resources_root, lang)
                if not q:
                    total = conn.execute("SELECT COUNT(*) FROM avatar").fetchone()[0]
                    rows = conn.execute(
                        """
                        SELECT a.avatar_id, COALESCE(nm.text, '') AS name, COALESCE(fn.text, '') AS full_name,
                               a.rarity, a.damage_type, a.avatar_base_type
                        FROM avatar a
                        LEFT JOIN text_map nm ON nm.lang = ? AND nm.hash = a.name_hash
                        LEFT JOIN text_map fn ON fn.lang = ? AND fn.hash = a.full_name_hash
                        ORDER BY a.avatar_id
                        LIMIT ? OFFSET ?
                        """,
                        (lang, lang, page_size, offset),
                    ).fetchall()
                else:
                    like = f"%{q}%"
                    total = conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM avatar a
                        LEFT JOIN text_map nm ON nm.lang = ? AND nm.hash = a.name_hash
                        LEFT JOIN text_map fn ON fn.lang = ? AND fn.hash = a.full_name_hash
                        WHERE (nm.text LIKE ? OR fn.text LIKE ? OR CAST(a.avatar_id AS TEXT) LIKE ?)
                        """,
                        (lang, lang, like, like, like),
                    ).fetchone()[0]
                    rows = conn.execute(
                        """
                        SELECT a.avatar_id, COALESCE(nm.text, '') AS name, COALESCE(fn.text, '') AS full_name,
                               a.rarity, a.damage_type, a.avatar_base_type
                        FROM avatar a
                        LEFT JOIN text_map nm ON nm.lang = ? AND nm.hash = a.name_hash
                        LEFT JOIN text_map fn ON fn.lang = ? AND fn.hash = a.full_name_hash
                        WHERE (nm.text LIKE ? OR fn.text LIKE ? OR CAST(a.avatar_id AS TEXT) LIKE ?)
                        ORDER BY a.avatar_id
                        LIMIT ? OFFSET ?
                        """,
                        (lang, lang, like, like, like, page_size, offset),
                    ).fetchall()

        payload = {"q": q, "lang": lang, "items": [dict(row) for row in rows]}
        return with_paging_meta(payload, page, page_size, total)

    def _api_avatar_detail(self, avatar_id: int, query: Dict[str, List[str]]) -> Dict[str, Any]:
        lang = normalize_lang((query.get("lang", ["CHS"])[0] or "CHS"))
        name_col = "name_en" if lang == "EN" else "name_chs"
        full_col = "full_name_en" if lang == "EN" else "full_name_chs"
        skill_name_col = "name_en" if lang == "EN" else "name_chs"
        skill_desc_col = "desc_en" if lang == "EN" else "desc_chs"
        skill_tag_col = "tag_en" if lang == "EN" else "tag_chs"
        skill_level_limit = as_int(qv(query, "skill_level_limit", "10"), 10, 1, 20)
        level_max = as_int(qv(query, "level_max", "80"), 80, 1, 80)

        with self._db("item") as conn:
            if lang not in ("CHS", "EN"):
                ensure_lang_loaded(conn, self.resources_root, lang)
            avatar = conn.execute(
                """
                SELECT avatar_id, name_hash, name_chs, name_en, full_name_hash, full_name_chs, full_name_en,
                       rarity, damage_type, avatar_base_type, sp_need, max_promotion, max_rank,
                       rank_id_list_json, skill_id_list_json
                FROM avatar
                WHERE avatar_id = ?
                """,
                (avatar_id,),
            ).fetchone()
            if avatar is None:
                return {"error": "not_found", "avatar_id": avatar_id}

            promotions = conn.execute(
                """
                SELECT promotion, max_level, player_level_require, world_level_require,
                       hp_base, hp_add, attack_base, attack_add, defence_base, defence_add,
                       speed_base, critical_chance, critical_damage, base_aggro, promotion_cost_json
                FROM avatar_promotion
                WHERE avatar_id = ?
                ORDER BY promotion
                """,
                (avatar_id,),
            ).fetchall()

            skill_ids = []
            rank_ids = []
            try:
                skill_ids = [int(x) for x in json.loads(avatar["skill_id_list_json"] or "[]")]
            except Exception:
                pass
            try:
                rank_ids = [int(x) for x in json.loads(avatar["rank_id_list_json"] or "[]")]
            except Exception:
                pass

            skills = []
            if skill_ids:
                placeholders = ",".join("?" for _ in skill_ids)
                if lang in ("CHS", "EN"):
                    skills = conn.execute(
                        f"""
                        SELECT skill_id, level, max_level, {skill_name_col} AS name, {skill_desc_col} AS description,
                               {skill_tag_col} AS tag, skill_effect, attack_type, stance_damage_type,
                               sp_base, bp_need, bp_add, param_json
                        FROM avatar_skill
                        WHERE skill_id IN ({placeholders})
                        ORDER BY skill_id, level
                        """,
                        skill_ids,
                    ).fetchall()
                else:
                    skills = conn.execute(
                        f"""
                        SELECT s.skill_id, s.level, s.max_level,
                               COALESCE(nm.text, '') AS name,
                               COALESCE(dc.text, '') AS description,
                               COALESCE(tg.text, '') AS tag,
                               s.skill_effect, s.attack_type, s.stance_damage_type,
                               s.sp_base, s.bp_need, s.bp_add, s.param_json
                        FROM avatar_skill s
                        LEFT JOIN text_map nm ON nm.lang = ? AND nm.hash = s.name_hash
                        LEFT JOIN text_map dc ON dc.lang = ? AND dc.hash = s.desc_hash
                        LEFT JOIN text_map tg ON tg.lang = ? AND tg.hash = s.tag_hash
                        WHERE s.skill_id IN ({placeholders})
                        ORDER BY s.skill_id, s.level
                        """,
                        (lang, lang, lang, *skill_ids),
                    ).fetchall()

            ranks = []
            if rank_ids:
                placeholders = ",".join("?" for _ in rank_ids)
                ranks = conn.execute(
                    f"SELECT rank_id, rank, name_raw, desc_raw, icon_path, skill_add_level_json, rank_ability_json, param_json FROM avatar_rank WHERE rank_id IN ({placeholders}) ORDER BY rank",
                    rank_ids,
                ).fetchall()
            promotion_rows = [dict(row) for row in promotions]
            level_stats = build_avatar_level_stats(promotion_rows, max_level=level_max)
            checkpoints = [row for row in level_stats if row["level"] == 1 or row["level"] % 10 == 0]

            skill_groups: Dict[int, Dict[str, Any]] = {}
            for row in skills:
                item = dict(row)
                sid = int(item["skill_id"])
                if sid not in skill_groups:
                    skill_groups[sid] = {
                        "skill_id": sid,
                        "name": item.get("name"),
                        "tag": item.get("tag"),
                        "skill_effect": item.get("skill_effect"),
                        "attack_type": item.get("attack_type"),
                        "stance_damage_type": item.get("stance_damage_type"),
                        "sp_base": item.get("sp_base"),
                        "bp_need": item.get("bp_need"),
                        "bp_add": item.get("bp_add"),
                        "available_levels": 0,
                        "shown_levels": 0,
                        "levels": [],
                    }
                group = skill_groups[sid]
                level = int(item.get("level") or 0)
                group["available_levels"] = max(group["available_levels"], level)
                if level > skill_level_limit:
                    continue

                params = parse_param_values(item.get("param_json"))
                group["levels"].append(
                    {
                        "level": level,
                        "max_level": item.get("max_level"),
                        "description_raw": item.get("description"),
                        "description": apply_param_template(item.get("description"), item.get("param_json")),
                        "param_values": params,
                    }
                )
                group["shown_levels"] += 1

            rank_items: List[Dict[str, Any]] = []
            for row in ranks:
                item = dict(row)
                params = parse_param_values(item.get("param_json"))
                name = resolve_text_from_key(conn, lang, item.get("name_raw"))
                desc_template = resolve_text_from_key(conn, lang, item.get("desc_raw"))
                desc = apply_param_template(desc_template, item.get("param_json")) if desc_template else None
                try:
                    skill_add_level = json.loads(item.get("skill_add_level_json") or "{}")
                except Exception:
                    skill_add_level = {}
                try:
                    rank_ability_keys = json.loads(item.get("rank_ability_json") or "[]")
                except Exception:
                    rank_ability_keys = []

                rank_abilities = []
                for key in rank_ability_keys if isinstance(rank_ability_keys, list) else []:
                    text = resolve_text_from_key(conn, lang, key if isinstance(key, str) else None)
                    rank_abilities.append(
                        {
                            "key": key,
                            "text": text,
                        }
                    )

                rank_items.append(
                    {
                        "rank_id": item.get("rank_id"),
                        "rank": item.get("rank"),
                        "name": name,
                        "description": desc,
                        "name_key": item.get("name_raw"),
                        "desc_key": item.get("desc_raw"),
                        "icon_path": item.get("icon_path"),
                        "param_values": params,
                        "skill_add_level": skill_add_level,
                        "rank_abilities": rank_abilities,
                    }
                )

            personal_story_items: List[Dict[str, Any]] = []
            try:
                stories_by_avatar, story_name_hash_by_id = load_avatar_story_index(str(self.resources_root.resolve()))
                raw_stories = stories_by_avatar.get(avatar_id, [])
                if raw_stories:
                    need_hashes: List[Optional[str]] = []
                    for entry in raw_stories:
                        need_hashes.append(entry.get("story_hash"))
                        need_hashes.append(story_name_hash_by_id.get(int(entry.get("story_id") or 0)))
                    text_map = resolve_hash_texts(conn, lang, need_hashes)

                    for entry in raw_stories:
                        story_id = int(entry.get("story_id") or 0)
                        story_hash = entry.get("story_hash")
                        title_hash = story_name_hash_by_id.get(story_id)
                        personal_story_items.append(
                            {
                                "story_id": story_id,
                                "unlock": entry.get("unlock"),
                                "title_hash": title_hash,
                                "title": text_map.get(str(title_hash)) if title_hash else None,
                                "content_hash": story_hash,
                                "content": text_map.get(str(story_hash)) if story_hash else None,
                            }
                        )
            except Exception:
                personal_story_items = []

            avatar_dict = dict(avatar)
            if lang == "CHS":
                avatar_dict["name"] = avatar_dict.get("name_chs")
                avatar_dict["full_name"] = avatar_dict.get("full_name_chs")
            elif lang == "EN":
                avatar_dict["name"] = avatar_dict.get("name_en")
                avatar_dict["full_name"] = avatar_dict.get("full_name_en")
            else:
                hash_text = resolve_hash_texts(conn, lang, [avatar_dict.get("name_hash"), avatar_dict.get("full_name_hash")])
                avatar_dict["name"] = hash_text.get(str(avatar_dict.get("name_hash") or "")) or avatar_dict.get("name_chs") or avatar_dict.get("name_en")
                avatar_dict["full_name"] = hash_text.get(str(avatar_dict.get("full_name_hash") or "")) or avatar_dict.get("full_name_chs") or avatar_dict.get("full_name_en")

        return {
            "avatar": avatar_dict,
            "promotions": promotion_rows,
            "level_stats": level_stats,
            "level_checkpoints": checkpoints,
            "skills": list(skill_groups.values()),
            "ranks": rank_items,
            "personal_stories": personal_story_items,
            "skill_level_limit": skill_level_limit,
            "level_max": level_max,
        }

    def _api_search_item(self, query: Dict[str, List[str]]) -> Dict[str, Any]:
        q = qv(query, "q")
        lang = normalize_lang(qv(query, "lang", "CHS"))
        page, page_size, offset = paging(query, default_size=20, max_size=100)
        rarity = qv(query, "rarity")
        item_main_type = qv(query, "item_main_type")
        item_sub_type = qv(query, "item_sub_type")

        name_col = "item_name_en" if lang == "EN" else "item_name_chs"
        desc_col = "item_desc_en" if lang == "EN" else "item_desc_chs"
        bg_desc_col = "item_bg_desc_en" if lang == "EN" else "item_bg_desc_chs"
        purpose_col = "purpose_text_en" if lang == "EN" else "purpose_text_chs"

        where_parts: List[str] = []
        params: List[Any] = []

        if rarity:
            where_parts.append("rarity = ?")
            params.append(rarity)
        if item_main_type:
            where_parts.append("item_main_type = ?")
            params.append(item_main_type)
        if item_sub_type:
            where_parts.append("item_sub_type = ?")
            params.append(item_sub_type)

        where_sql = ""
        if where_parts:
            where_sql = "WHERE " + " AND ".join(where_parts)

        with self._db("item") as conn:
            if lang in ("CHS", "EN"):
                if q:
                    rows = []
                    total = 0
                    like = f"%{q}%"
                    text_cond = f"(i.{name_col} LIKE ? OR i.{desc_col} LIKE ? OR i.{bg_desc_col} LIKE ?)"
                    if lang == "EN":
                        count_sql = f"SELECT COUNT(*) FROM item i {where_sql} {'AND' if where_sql else 'WHERE'} {text_cond}"
                        total = conn.execute(count_sql, (*params, like, like, like)).fetchone()[0]
                        sql = f"""
                            SELECT i.item_id, i.item_main_type, i.item_sub_type, i.rarity,
                                   i.{name_col} AS name, i.{desc_col} AS description, i.{bg_desc_col} AS bg_description,
                                   i.{purpose_col} AS purpose, i.icon_path
                            FROM item i
                            {where_sql}
                            {"AND" if where_sql else "WHERE"} {text_cond}
                            ORDER BY i.item_id
                            LIMIT ? OFFSET ?
                        """
                        rows = conn.execute(sql, (*params, like, like, like, page_size, offset)).fetchall()
                    else:
                        try:
                            fts_q = norm_fts_query(q)
                            count_sql = f"""
                                SELECT COUNT(*)
                                FROM item_fts f
                                JOIN item i ON i.item_id = f.rowid
                                {where_sql}
                                {"AND" if where_sql else "WHERE"} item_fts MATCH ?
                            """
                            total = conn.execute(count_sql, (*params, fts_q)).fetchone()[0]
                            sql = f"""
                                SELECT i.item_id, i.item_main_type, i.item_sub_type, i.rarity,
                                       i.{name_col} AS name, i.{desc_col} AS description, i.{bg_desc_col} AS bg_description,
                                       i.{purpose_col} AS purpose, i.icon_path
                                FROM item_fts f
                                JOIN item i ON i.item_id = f.rowid
                                {where_sql}
                                {"AND" if where_sql else "WHERE"} item_fts MATCH ?
                                ORDER BY i.item_id
                                LIMIT ? OFFSET ?
                            """
                            rows = conn.execute(sql, (*params, fts_q, page_size, offset)).fetchall()
                        except sqlite3.OperationalError:
                            total = 0
                            rows = []

                        if total == 0:
                            count_sql = f"SELECT COUNT(*) FROM item i {where_sql} {'AND' if where_sql else 'WHERE'} {text_cond}"
                            total = conn.execute(count_sql, (*params, like, like, like)).fetchone()[0]
                            sql = f"""
                                SELECT i.item_id, i.item_main_type, i.item_sub_type, i.rarity,
                                       i.{name_col} AS name, i.{desc_col} AS description, i.{bg_desc_col} AS bg_description,
                                       i.{purpose_col} AS purpose, i.icon_path
                                FROM item i
                                {where_sql}
                                {"AND" if where_sql else "WHERE"} {text_cond}
                                ORDER BY i.item_id
                                LIMIT ? OFFSET ?
                            """
                            rows = conn.execute(sql, (*params, like, like, like, page_size, offset)).fetchall()
                else:
                    total_sql = f"SELECT COUNT(*) FROM item {where_sql}"
                    total = conn.execute(total_sql, params).fetchone()[0]
                    sql = f"""
                        SELECT item_id, item_main_type, item_sub_type, rarity,
                               {name_col} AS name, {desc_col} AS description, {bg_desc_col} AS bg_description,
                               {purpose_col} AS purpose, icon_path
                        FROM item
                        {where_sql}
                        ORDER BY item_id
                        LIMIT ? OFFSET ?
                    """
                    rows = conn.execute(sql, (*params, page_size, offset)).fetchall()
            else:
                ensure_lang_loaded(conn, self.resources_root, lang)
                if q:
                    like = f"%{q}%"
                    count_sql = f"""
                        SELECT COUNT(*)
                        FROM item i
                        LEFT JOIN text_map nm ON nm.lang = ? AND nm.hash = i.item_name_hash
                        LEFT JOIN text_map dc ON dc.lang = ? AND dc.hash = i.item_desc_hash
                        LEFT JOIN text_map bg ON bg.lang = ? AND bg.hash = i.item_bg_desc_hash
                        {where_sql}
                        {"AND" if where_sql else "WHERE"} (nm.text LIKE ? OR dc.text LIKE ? OR bg.text LIKE ? OR CAST(i.item_id AS TEXT) LIKE ?)
                    """
                    total = conn.execute(count_sql, (lang, lang, lang, *params, like, like, like, like)).fetchone()[0]
                    sql = f"""
                        SELECT i.item_id, i.item_main_type, i.item_sub_type, i.rarity,
                               COALESCE(nm.text, '') AS name,
                               COALESCE(dc.text, '') AS description,
                               COALESCE(bg.text, '') AS bg_description,
                               i.{purpose_col} AS purpose, i.icon_path
                        FROM item i
                        LEFT JOIN text_map nm ON nm.lang = ? AND nm.hash = i.item_name_hash
                        LEFT JOIN text_map dc ON dc.lang = ? AND dc.hash = i.item_desc_hash
                        LEFT JOIN text_map bg ON bg.lang = ? AND bg.hash = i.item_bg_desc_hash
                        {where_sql}
                        {"AND" if where_sql else "WHERE"} (nm.text LIKE ? OR dc.text LIKE ? OR bg.text LIKE ? OR CAST(i.item_id AS TEXT) LIKE ?)
                        ORDER BY i.item_id
                        LIMIT ? OFFSET ?
                    """
                    rows = conn.execute(sql, (lang, lang, lang, *params, like, like, like, like, page_size, offset)).fetchall()
                else:
                    total_sql = f"SELECT COUNT(*) FROM item {where_sql}"
                    total = conn.execute(total_sql, params).fetchone()[0]
                    sql = f"""
                        SELECT i.item_id, i.item_main_type, i.item_sub_type, i.rarity,
                               COALESCE(nm.text, '') AS name,
                               COALESCE(dc.text, '') AS description,
                               COALESCE(bg.text, '') AS bg_description,
                               i.{purpose_col} AS purpose, i.icon_path
                        FROM item i
                        LEFT JOIN text_map nm ON nm.lang = ? AND nm.hash = i.item_name_hash
                        LEFT JOIN text_map dc ON dc.lang = ? AND dc.hash = i.item_desc_hash
                        LEFT JOIN text_map bg ON bg.lang = ? AND bg.hash = i.item_bg_desc_hash
                        {where_sql}
                        ORDER BY i.item_id
                        LIMIT ? OFFSET ?
                    """
                    rows = conn.execute(sql, (lang, lang, lang, *params, page_size, offset)).fetchall()

            item_rows = [dict(row) for row in rows]
            equipment_ids = [
                int(r["item_id"])
                for r in item_rows
                if (r.get("item_main_type") == "Equipment" or r.get("item_sub_type") == "Equipment")
            ]
            lc_map = build_light_cone_summary_map(conn, lang, self.resources_root, equipment_ids) if equipment_ids else {}
            for row in item_rows:
                row["light_cone"] = lc_map.get(int(row["item_id"])) if row.get("item_id") is not None else None

        payload = {
            "q": q,
            "lang": lang,
            "rarity": rarity,
            "item_main_type": item_main_type,
            "item_sub_type": item_sub_type,
            "items": item_rows,
        }
        return with_paging_meta(payload, page, page_size, total)

    def _api_item_detail(self, item_id: int, query: Dict[str, List[str]]) -> Dict[str, Any]:
        lang = normalize_lang(qv(query, "lang", "CHS"))
        name_col = "item_name_en" if lang == "EN" else "item_name_chs"
        desc_col = "item_desc_en" if lang == "EN" else "item_desc_chs"
        bg_desc_col = "item_bg_desc_en" if lang == "EN" else "item_bg_desc_chs"
        purpose_col = "purpose_text_en" if lang == "EN" else "purpose_text_chs"

        with self._db("item") as conn:
            if lang in ("CHS", "EN"):
                row = conn.execute(
                    f"""
                    SELECT item_id, source_file, item_main_type, item_sub_type, rarity, purpose_type,
                           {purpose_col} AS purpose, {name_col} AS name, {desc_col} AS description,
                           {bg_desc_col} AS bg_description, icon_path, figure_icon_path, currency_icon_path,
                           avatar_icon_path, pile_limit
                    FROM item
                    WHERE item_id = ?
                    """,
                    (item_id,),
                ).fetchone()
            else:
                ensure_lang_loaded(conn, self.resources_root, lang)
                row = conn.execute(
                    f"""
                    SELECT i.item_id, i.source_file, i.item_main_type, i.item_sub_type, i.rarity, i.purpose_type,
                           i.{purpose_col} AS purpose,
                           COALESCE(nm.text, '') AS name,
                           COALESCE(dc.text, '') AS description,
                           COALESCE(bg.text, '') AS bg_description,
                           i.icon_path, i.figure_icon_path, i.currency_icon_path, i.avatar_icon_path, i.pile_limit
                    FROM item i
                    LEFT JOIN text_map nm ON nm.lang = ? AND nm.hash = i.item_name_hash
                    LEFT JOIN text_map dc ON dc.lang = ? AND dc.hash = i.item_desc_hash
                    LEFT JOIN text_map bg ON bg.lang = ? AND bg.hash = i.item_bg_desc_hash
                    WHERE i.item_id = ?
                    """,
                    (lang, lang, lang, item_id),
                ).fetchone()
            if row is None:
                return {"error": "not_found", "item_id": item_id}
            item = dict(row)
            light_cone = None
            if item.get("item_main_type") == "Equipment" or item.get("item_sub_type") == "Equipment":
                light_cone = build_light_cone_detail(conn, lang, self.resources_root, item_id)
            return {"item": item, "light_cone": light_cone}

    def _api_item_facets(self) -> Dict[str, Any]:
        with self._db("monster") as conn:
            rarity = [
                row["rarity"]
                for row in conn.execute(
                    "SELECT DISTINCT rarity FROM item WHERE rarity IS NOT NULL AND rarity != '' ORDER BY rarity"
                ).fetchall()
            ]
            main_types = [
                row["item_main_type"]
                for row in conn.execute(
                    "SELECT DISTINCT item_main_type FROM item WHERE item_main_type IS NOT NULL AND item_main_type != '' ORDER BY item_main_type"
                ).fetchall()
            ]
            sub_types = [
                row["item_sub_type"]
                for row in conn.execute(
                    "SELECT DISTINCT item_sub_type FROM item WHERE item_sub_type IS NOT NULL AND item_sub_type != '' ORDER BY item_sub_type"
                ).fetchall()
            ]
        return {
            "rarity": rarity,
            "item_main_type": main_types,
            "item_sub_type": sub_types,
        }

    def _api_monster_facets(self) -> Dict[str, Any]:
        idx = load_monster_index(str(self.resources_root.resolve()))
        return {
            "rank": idx.get("rank", []),
            "weakness": idx.get("weakness", []),
        }

    def _api_search_monster(self, query: Dict[str, List[str]]) -> Dict[str, Any]:
        q = qv(query, "q")
        lang = normalize_lang(qv(query, "lang", "CHS"))
        rank = qv(query, "rank")
        weakness = qv(query, "weakness")
        page, page_size, offset = paging(query, default_size=20, max_size=100)

        idx = load_monster_index(str(self.resources_root.resolve()))
        all_items = idx.get("items", [])

        with self._db("monster") as conn:
            ensure_lang_loaded(conn, self.resources_root, lang)
            ensure_lang_loaded(conn, self.resources_root, "CHS")
            ensure_lang_loaded(conn, self.resources_root, "EN")

            hashes: List[Optional[str]] = []
            for row in all_items:
                hashes.extend([row.get("name_hash"), row.get("introduction_hash")])
            lang_map = resolve_hash_texts(conn, lang, hashes)
            chs_map = resolve_hash_texts(conn, "CHS", hashes) if lang != "CHS" else {}
            en_map = resolve_hash_texts(conn, "EN", hashes) if lang != "EN" else {}

            def resolve_hash(h: Optional[str]) -> str:
                if not h:
                    return ""
                key = str(h)
                return lang_map.get(key) or chs_map.get(key) or en_map.get(key) or ""

            q_norm = q.casefold()
            filtered: List[Dict[str, Any]] = []
            for row in all_items:
                if rank and row.get("rank") != rank:
                    continue
                weak_list = row.get("stance_weak_list") or []
                if weakness and weakness not in weak_list:
                    continue

                item = {
                    "monster_id": row.get("monster_id"),
                    "monster_template_id": row.get("monster_template_id"),
                    "name": resolve_hash(row.get("name_hash")),
                    "introduction": resolve_hash(row.get("introduction_hash")),
                    "rank": row.get("rank"),
                    "elite_group": row.get("elite_group"),
                    "hard_level_group": row.get("hard_level_group"),
                    "stance_weak_list": weak_list,
                    "stance_type": row.get("stance_type"),
                    "icon_path": row.get("icon_path"),
                    "image_path": row.get("image_path"),
                    "skill_count": len(row.get("skill_ids") or []),
                }
                if q_norm:
                    search_blob = " ".join(
                        [
                            str(item.get("monster_id") or ""),
                            str(item.get("monster_template_id") or ""),
                            str(item.get("name") or ""),
                            str(item.get("introduction") or ""),
                            str(item.get("rank") or ""),
                            " ".join(item.get("stance_weak_list") or []),
                        ]
                    ).casefold()
                    if q_norm not in search_blob:
                        continue
                filtered.append(item)

        total = len(filtered)
        items = filtered[offset: offset + page_size]
        payload = {
            "q": q,
            "lang": lang,
            "rank": rank,
            "weakness": weakness,
            "items": items,
        }
        return with_paging_meta(payload, page, page_size, total)

    def _api_monster_detail(self, monster_id: int, query: Dict[str, List[str]]) -> Dict[str, Any]:
        lang = normalize_lang(qv(query, "lang", "CHS"))
        idx = load_monster_index(str(self.resources_root.resolve()))
        monster = (idx.get("by_id") or {}).get(monster_id)
        if monster is None:
            return {"error": "not_found", "monster_id": monster_id}

        skills_by_id: Dict[int, Dict[str, Any]] = idx.get("skills") or {}

        with self._db("monster") as conn:
            ensure_lang_loaded(conn, self.resources_root, lang)
            ensure_lang_loaded(conn, self.resources_root, "CHS")
            ensure_lang_loaded(conn, self.resources_root, "EN")

            hashes: List[Optional[str]] = [monster.get("name_hash"), monster.get("introduction_hash")]
            for skill_id in monster.get("skill_ids") or []:
                skill = skills_by_id.get(int(skill_id))
                if not skill:
                    continue
                hashes.extend(
                    [
                        skill.get("name_hash"),
                        skill.get("desc_hash"),
                        skill.get("type_desc_hash"),
                        skill.get("tag_hash"),
                    ]
                )
            lang_map = resolve_hash_texts(conn, lang, hashes)
            chs_map = resolve_hash_texts(conn, "CHS", hashes) if lang != "CHS" else {}
            en_map = resolve_hash_texts(conn, "EN", hashes) if lang != "EN" else {}

            def resolve_hash(h: Optional[str]) -> Optional[str]:
                if not h:
                    return None
                key = str(h)
                return lang_map.get(key) or chs_map.get(key) or en_map.get(key)

            def scaled(base: Optional[float], ratio: Optional[float]) -> Optional[float]:
                if base is None or ratio is None:
                    return None
                return round(base * ratio, 4)

            skill_items: List[Dict[str, Any]] = []
            override_map = monster.get("override_skill_params") or {}
            for skill_id in monster.get("skill_ids") or []:
                sid = int(skill_id)
                skill = skills_by_id.get(sid)
                if not skill:
                    continue
                override_params = override_map.get(sid)
                raw_params = override_params if override_params is not None else skill.get("param_list")
                desc_template = resolve_hash(skill.get("desc_hash"))
                skill_items.append(
                    {
                        "skill_id": sid,
                        "name": resolve_hash(skill.get("name_hash")),
                        "skill_type": resolve_hash(skill.get("type_desc_hash")),
                        "skill_tag": resolve_hash(skill.get("tag_hash")),
                        "damage_type": skill.get("damage_type"),
                        "attack_type": skill.get("attack_type"),
                        "skill_trigger_key": skill.get("skill_trigger_key"),
                        "icon_path": skill.get("icon_path"),
                        "description": apply_param_template(desc_template, raw_params) if desc_template else None,
                        "description_raw": desc_template,
                        "param_values": parse_param_values(raw_params),
                        "has_override_params": override_params is not None,
                    }
                )

            ability_items: List[Dict[str, Any]] = []
            for key in monster.get("ability_name_keys") or []:
                text = resolve_text_with_fallback(conn, lang, key, fallback=key)
                ability_items.append({"key": key, "text": text or key})

            monster_payload = {
                "monster_id": monster.get("monster_id"),
                "monster_template_id": monster.get("monster_template_id"),
                "name": resolve_hash(monster.get("name_hash")) or f"Monster {monster_id}",
                "introduction": resolve_hash(monster.get("introduction_hash")),
                "rank": monster.get("rank"),
                "elite_group": monster.get("elite_group"),
                "hard_level_group": monster.get("hard_level_group"),
                "stance_type": monster.get("stance_type"),
                "stance_weak_list": monster.get("stance_weak_list") or [],
                "damage_type_resistance": monster.get("damage_type_resistance") or [],
                "attack_modify_ratio": monster.get("attack_modify_ratio"),
                "defence_modify_ratio": monster.get("defence_modify_ratio"),
                "hp_modify_ratio": monster.get("hp_modify_ratio"),
                "speed_modify_ratio": monster.get("speed_modify_ratio"),
                "stance_modify_ratio": monster.get("stance_modify_ratio"),
                "icon_path": monster.get("icon_path"),
                "round_icon_path": monster.get("round_icon_path"),
                "image_path": monster.get("image_path"),
                "manikin_image_path": monster.get("manikin_image_path"),
                "json_config": monster.get("json_config"),
                "prefab_path": monster.get("prefab_path"),
                "ai_path": monster.get("ai_path"),
                "base_stats": {
                    "hp_base": monster.get("hp_base"),
                    "attack_base": monster.get("attack_base"),
                    "defence_base": monster.get("defence_base"),
                    "speed_base": monster.get("speed_base"),
                    "stance_base": monster.get("stance_base"),
                    "critical_damage_base": monster.get("critical_damage_base"),
                    "status_resistance_base": monster.get("status_resistance_base"),
                    "minimum_fatigue_ratio": monster.get("minimum_fatigue_ratio"),
                },
                "scaled_stats": {
                    "hp": scaled(monster.get("hp_base"), monster.get("hp_modify_ratio")),
                    "attack": scaled(monster.get("attack_base"), monster.get("attack_modify_ratio")),
                    "defence": scaled(monster.get("defence_base"), monster.get("defence_modify_ratio")),
                    "speed": scaled(monster.get("speed_base"), monster.get("speed_modify_ratio")),
                    "stance": scaled(monster.get("stance_base"), monster.get("stance_modify_ratio")),
                },
            }

        return {
            "monster": monster_payload,
            "abilities": ability_items,
            "skills": skill_items,
        }

    def _api_term_explain(self, query: Dict[str, List[str]]) -> Dict[str, Any]:
        term = qv(query, "term")
        lang = normalize_lang(qv(query, "lang", "CHS"))
        limit = as_int(qv(query, "limit", "5"), 5, 1, 20)
        if not term:
            return {"term": term, "lang": lang, "used_lang": lang, "items": []}

        raw_term = term[:64]
        escaped = escape_like(raw_term)
        starts = [f"{escaped}：%", f"{escaped}:%", f"{escaped}（%", f"{escaped} (%"]
        contains = f"%{escaped}%"

        def score_term(text: str) -> float:
            clean = text.strip().replace("\r", " ").replace("\n", " ")
            if not clean:
                return -9999.0
            score = 0.0
            if clean.startswith(raw_term + "：") or clean.startswith(raw_term + ":"):
                score += 140
            elif clean.startswith(raw_term):
                score += 100

            if f"「{raw_term}」" in clean or f"【{raw_term}】" in clean:
                score += 35
            if ":" in clean[:20] or "：" in clean[:20] or "指" in clean[:20] or "是" in clean[:20]:
                score += 20
            if "http://" in clean or "https://" in clean:
                score -= 20
            if clean.count(raw_term) > 1:
                score += 8
            score -= len(clean) * 0.03
            return score

        def search_in_lang(conn: sqlite3.Connection, q_lang: str) -> List[Dict[str, Any]]:
            ensure_lang_loaded(conn, self.resources_root, q_lang)
            rows_a = conn.execute(
                """
                SELECT hash, text
                FROM text_map
                WHERE lang = ?
                  AND LENGTH(text) <= 420
                  AND (
                    text LIKE ? ESCAPE '\\'
                    OR text LIKE ? ESCAPE '\\'
                    OR text LIKE ? ESCAPE '\\'
                    OR text LIKE ? ESCAPE '\\'
                  )
                LIMIT 300
                """,
                (q_lang, starts[0], starts[1], starts[2], starts[3]),
            ).fetchall()

            rows_b = conn.execute(
                """
                SELECT hash, text
                FROM text_map
                WHERE lang = ?
                  AND LENGTH(text) BETWEEN 6 AND 420
                  AND text LIKE ? ESCAPE '\\'
                LIMIT 800
                """,
                (q_lang, contains),
            ).fetchall()

            seen: set[str] = set()
            scored: List[Dict[str, Any]] = []
            for row in [*rows_a, *rows_b]:
                text = (row["text"] or "").strip()
                if not text or text in seen:
                    continue
                seen.add(text)
                s = score_term(text)
                if s < 5:
                    continue
                scored.append(
                    {
                        "hash": row["hash"],
                        "text": text,
                        "score": round(s, 3),
                    }
                )

            scored.sort(key=lambda x: (-float(x["score"]), len(str(x["text"]))))
            return scored[:limit]

        module_name = self._module_name(qv(query, "module", ""), "default")
        with self._db(module_name) as conn:
            primary = search_in_lang(conn, lang)
            used_lang = lang
            if not primary and lang != "CHS":
                fallback = search_in_lang(conn, "CHS")
                if fallback:
                    primary = fallback
                    used_lang = "CHS"

        return {
            "term": raw_term,
            "lang": lang,
            "used_lang": used_lang,
            "items": primary,
        }

    def _api_search_text(self, query: Dict[str, List[str]]) -> Dict[str, Any]:
        q = qv(query, "q")
        lang = normalize_lang(qv(query, "lang", "CHS"))
        page, page_size, offset = paging(query, default_size=20, max_size=100)
        if not q:
            return with_paging_meta({"q": q, "lang": lang, "items": []}, page, page_size, 0)

        like = f"%{q}%"
        module_name = self._module_name(qv(query, "module", ""), "default")
        with self._db(module_name) as conn:
            ensure_lang_loaded(conn, self.resources_root, lang)
            total = conn.execute(
                "SELECT COUNT(*) FROM text_map WHERE lang = ? AND text LIKE ?",
                (lang, like),
            ).fetchone()[0]
            rows = conn.execute(
                "SELECT hash, text FROM text_map WHERE lang = ? AND text LIKE ? LIMIT ? OFFSET ?",
                (lang, like, page_size, offset),
            ).fetchall()
        payload = {"q": q, "lang": lang, "items": [dict(row) for row in rows]}
        return with_paging_meta(payload, page, page_size, total)


def run(host: str, port: int, db_path: Path, web_root: Path, resources_root: Path, db_module_paths: Optional[Dict[str, Path]] = None) -> None:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    if not web_root.exists():
        raise FileNotFoundError(f"Web root not found: {web_root}")
    if not resources_root.exists():
        raise FileNotFoundError(f"Resources root not found: {resources_root}")

    db_paths: Dict[str, Path] = {"default": db_path}
    for key, path in (db_module_paths or {}).items():
        if key not in SUPPORTED_MODULES or key == "default":
            continue
        if not path.exists():
            raise FileNotFoundError(f"Database not found for module {key}: {path}")
        db_paths[key] = path

    httpd = ThreadingHTTPServer((host, port), AppHandler)
    httpd.db_paths = db_paths  # type: ignore[attr-defined]
    httpd.web_root = web_root  # type: ignore[attr-defined]
    httpd.resources_root = resources_root  # type: ignore[attr-defined]
    print(f"Serving on http://{host}:{port}")
    print(f"DB(default): {db_path}")
    for mod in ("avatar", "dialogue", "mission", "item", "monster"):
        if mod in db_paths:
            print(f"DB({mod}): {db_paths[mod]}")
    httpd.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve database query API and frontend.")
    default_db_dir = Path(__file__).resolve().parent / "database"
    parser.add_argument("--db-path", type=Path, default=default_db_dir / "hsr_resources.db")
    parser.add_argument("--db-avatar", type=Path, default=None, help="Optional avatar module database path.")
    parser.add_argument("--db-dialogue", type=Path, default=None, help="Optional dialogue module database path.")
    parser.add_argument("--db-mission", type=Path, default=None, help="Optional mission module database path.")
    parser.add_argument("--db-item", type=Path, default=None, help="Optional item module database path.")
    parser.add_argument("--db-monster", type=Path, default=None, help="Optional monster/text module database path.")
    parser.add_argument("--web-root", type=Path, default=Path(__file__).resolve().parent / "web")
    parser.add_argument("--resources-root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()

    module_paths: Dict[str, Path] = {}
    if args.db_avatar:
        module_paths["avatar"] = args.db_avatar.resolve()
    if args.db_dialogue:
        module_paths["dialogue"] = args.db_dialogue.resolve()
    if args.db_mission:
        module_paths["mission"] = args.db_mission.resolve()
    if args.db_item:
        module_paths["item"] = args.db_item.resolve()
    if args.db_monster:
        module_paths["monster"] = args.db_monster.resolve()

    run(
        args.host,
        args.port,
        args.db_path.resolve(),
        args.web_root.resolve(),
        args.resources_root.resolve(),
        db_module_paths=module_paths,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
