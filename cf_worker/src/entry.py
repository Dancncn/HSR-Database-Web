from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from js import JSON
from workers import Response, WorkerEntrypoint

DEFAULT_WORKER_NAME = "hsrdb-api"
META_TABLE = "hsr_resources_avatar__meta"
AVATAR_TABLE = "hsr_resources_avatar__avatar"
TALK_SENTENCE_TABLE = "hsr_resources_dialogue__talk_sentence"
API_ROUTE_HINTS = [
    "/api/stats",
    "/api/search/dialogue",
    "/api/dialogue/<TalkSentenceID>/refs",
    "/api/search/mission",
    "/api/mission/<MainMissionID>",
    "/api/search/avatar",
    "/api/avatar/<AvatarID>",
    "/api/search/item",
    "/api/item/<ItemID>",
    "/api/item/facets",
    "/api/search/monster",
    "/api/monster/<MonsterID>",
    "/api/monster/facets",
    "/api/term/explain",
    "/api/search/text",
    "/__health",
    "/__debug",
]


class HttpError(Exception):
    def __init__(self, status: int, error: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.error = error
        self.message = message


def to_py(value: Any, default: Any = None) -> Any:
    if value is None:
        return default
    try:
        raw = JSON.stringify(value)
    except Exception:
        return value
    if raw is None or raw == "undefined":
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def cors_headers() -> Dict[str, str]:
    return {
        "access-control-allow-origin": "*",
        "access-control-allow-methods": "GET, OPTIONS",
        "access-control-allow-headers": "Content-Type",
    }


def json_response(payload: Any, status: int = 200, cors: bool = False) -> Any:
    body = json.dumps(payload, ensure_ascii=False)
    headers: Dict[str, str] = {"content-type": "application/json; charset=utf-8"}
    if cors:
        headers.update(cors_headers())
    return Response(
        body,
        status=status,
        headers=headers,
    )


def empty_response(status: int = 204, cors: bool = False) -> Any:
    headers: Dict[str, str] = {}
    if cors:
        headers.update(cors_headers())
    return Response("", status=status, headers=headers)


def with_cors(response: Any) -> Any:
    try:
        headers = getattr(response, "headers", None)
        if headers is not None:
            for k, v in cors_headers().items():
                headers.set(k, v)
    except Exception:
        pass
    return response


def qv(query: Dict[str, List[str]], key: str, default: str = "") -> str:
    return (query.get(key, [default])[0] or default).strip()


def as_int(value: str, default: int, min_value: int = 1, max_value: int = 1000) -> int:
    try:
        iv = int(value)
    except Exception:
        return default
    return max(min_value, min(max_value, iv))


def paging(query: Dict[str, List[str]], default_size: int = 20, max_size: int = 100) -> Tuple[int, int, int]:
    page = as_int(qv(query, "page", "1"), 1, 1, 100000)
    page_size = as_int(qv(query, "page_size", str(default_size)), default_size, 1, max_size)
    return page, page_size, (page - 1) * page_size


def with_paging_meta(payload: Dict[str, Any], page: int, page_size: int, total: int) -> Dict[str, Any]:
    payload["page"] = page
    payload["page_size"] = page_size
    payload["total"] = total
    payload["total_pages"] = (total + page_size - 1) // page_size if page_size > 0 else 0
    return payload


def normalize_lang(raw: str) -> str:
    token = (raw or "").strip().upper().replace("-", "_")
    if token in {"EN", "EN_US"}:
        return "EN"
    if token in {"CHS", "ZH", "ZH_CN", "CN"}:
        return "CHS"
    return "CHS"


def get_worker_name(env: Any) -> str:
    for key in ("WORKER_NAME", "SERVICE_NAME", "APP_NAME"):
        try:
            value = getattr(env, key, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
        except Exception:
            pass
    return DEFAULT_WORKER_NAME


def binding_exists(env: Any, name: str) -> bool:
    try:
        return getattr(env, name, None) is not None
    except Exception:
        return False


def is_api_path(path: str) -> bool:
    return path.startswith("/api/")


async def d1_all(db: Any, sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
    stmt = db.prepare(sql)
    if params:
        stmt = stmt.bind(*params)
    result = await stmt.all()
    out = to_py(result, {}) or {}
    rows = out.get("results")
    return rows if isinstance(rows, list) else []


async def d1_first(db: Any, sql: str, params: Optional[List[Any]] = None) -> Optional[Dict[str, Any]]:
    stmt = db.prepare(sql)
    if params:
        stmt = stmt.bind(*params)
    row = await stmt.first()
    out = to_py(row)
    return out if isinstance(out, dict) else None


async def safe_count(db: Any, table: str) -> Optional[int]:
    try:
        rows = await d1_all(db, f"SELECT COUNT(*) AS c FROM {table}")
        if not rows:
            return 0
        return int(rows[0].get("c") or 0)
    except Exception:
        return None


def as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def build_level_stats(promotions: List[Dict[str, Any]], level_max: int) -> List[Dict[str, Any]]:
    valid = [p for p in promotions if p.get("max_level") is not None]
    valid.sort(key=lambda x: int(x.get("max_level") or 0))
    if not valid:
        return []

    out: List[Dict[str, Any]] = []
    for level in range(1, level_max + 1):
        stage = next((p for p in valid if level <= int(p.get("max_level") or 0)), valid[-1])
        hp_base = as_float(stage.get("hp_base")) or 0.0
        hp_add = as_float(stage.get("hp_add")) or 0.0
        atk_base = as_float(stage.get("attack_base")) or 0.0
        atk_add = as_float(stage.get("attack_add")) or 0.0
        def_base = as_float(stage.get("defence_base")) or 0.0
        def_add = as_float(stage.get("defence_add")) or 0.0
        spd = as_float(stage.get("speed_base")) or 0.0
        out.append(
            {
                "level": level,
                "promotion": int(stage.get("promotion") or 0),
                "hp": round(hp_base + hp_add * (level - 1), 4),
                "attack": round(atk_base + atk_add * (level - 1), 4),
                "defence": round(def_base + def_add * (level - 1), 4),
                "speed": round(spd, 4),
            }
        )
    return out


async def handle_stats(env: Any) -> Any:
    db = env.DB
    rows = await d1_all(
        db,
        f"SELECT key, value FROM {META_TABLE} WHERE key IN ('build_at', 'elapsed_seconds', 'table_counts')",
    )
    out: Dict[str, Any] = {}
    for row in rows:
        key = row.get("key")
        if not key:
            continue
        val = row.get("value")
        if key in {"elapsed_seconds", "table_counts"} and isinstance(val, str):
            try:
                out[key] = json.loads(val)
                continue
            except Exception:
                pass
        out[key] = val

    table_counts = out.get("table_counts")
    if not isinstance(table_counts, dict):
        table_counts = {}

    mapping = {
        "talk_sentence": "talk_sentence",
        "story_reference": "story_reference",
        "main_mission": "main_mission",
        "avatar": "avatar",
        "item": "item",
    }
    for key, table in mapping.items():
        value = await safe_count(db, table)
        if value is not None:
            table_counts[key] = value
    out["table_counts"] = table_counts

    monster_count = await safe_count(db, "monster")
    out["monster_count"] = monster_count if monster_count is not None else int(table_counts.get("monster", 0) or 0)
    return json_response(out)


async def handle_search_dialogue(query: Dict[str, List[str]], env: Any) -> Any:
    db = env.DB
    q = qv(query, "q")
    raw_lang = (qv(query, "lang", "") or "").strip().lower()
    if raw_lang in {"zh", "chs", "zh-cn", "zh_cn", "cn"}:
        lang_mode = "chs"
        lang = "CHS"
    elif raw_lang == "en":
        lang_mode = "en"
        lang = "EN"
    else:
        lang_mode = "both"
        lang = (raw_lang or "").upper()
    order = "desc" if qv(query, "order", "asc").lower() == "desc" else "asc"
    order_sql = "DESC" if order == "desc" else "ASC"
    page, page_size, offset = paging(query, default_size=20, max_size=100)

    if lang_mode == "chs":
        non_empty = "(text_chs IS NOT NULL AND text_chs <> '')"
        if not q:
            total_rows = await d1_all(
                db,
                f"SELECT COUNT(*) AS c FROM {TALK_SENTENCE_TABLE} WHERE {non_empty}",
            )
            total = int((total_rows[0] if total_rows else {}).get("c") or 0)
            rows = await d1_all(
                db,
                f"""
                SELECT talk_sentence_id, speaker_chs AS speaker, text_chs AS text
                FROM {TALK_SENTENCE_TABLE}
                WHERE {non_empty}
                ORDER BY talk_sentence_id {order_sql}
                LIMIT ? OFFSET ?
                """,
                [page_size, offset],
            )
        else:
            like = f"%{q}%"
            total_rows = await d1_all(
                db,
                f"""
                SELECT COUNT(*) AS c
                FROM {TALK_SENTENCE_TABLE}
                WHERE {non_empty}
                  AND (speaker_chs LIKE ? OR text_chs LIKE ?)
                """,
                [like, like],
            )
            total = int((total_rows[0] if total_rows else {}).get("c") or 0)
            rows = await d1_all(
                db,
                f"""
                SELECT talk_sentence_id, speaker_chs AS speaker, text_chs AS text
                FROM {TALK_SENTENCE_TABLE}
                WHERE {non_empty}
                  AND (speaker_chs LIKE ? OR text_chs LIKE ?)
                ORDER BY talk_sentence_id {order_sql}
                LIMIT ? OFFSET ?
                """,
                [like, like, page_size, offset],
            )
    elif lang_mode == "en":
        non_empty = "(text_en IS NOT NULL AND text_en <> '')"
        if not q:
            total_rows = await d1_all(
                db,
                f"SELECT COUNT(*) AS c FROM {TALK_SENTENCE_TABLE} WHERE {non_empty}",
            )
            total = int((total_rows[0] if total_rows else {}).get("c") or 0)
            rows = await d1_all(
                db,
                f"""
                SELECT talk_sentence_id, speaker_en AS speaker, text_en AS text
                FROM {TALK_SENTENCE_TABLE}
                WHERE {non_empty}
                ORDER BY talk_sentence_id {order_sql}
                LIMIT ? OFFSET ?
                """,
                [page_size, offset],
            )
        else:
            like = f"%{q}%"
            total_rows = await d1_all(
                db,
                f"""
                SELECT COUNT(*) AS c
                FROM {TALK_SENTENCE_TABLE}
                WHERE {non_empty}
                  AND (speaker_en LIKE ? OR text_en LIKE ?)
                """,
                [like, like],
            )
            total = int((total_rows[0] if total_rows else {}).get("c") or 0)
            rows = await d1_all(
                db,
                f"""
                SELECT talk_sentence_id, speaker_en AS speaker, text_en AS text
                FROM {TALK_SENTENCE_TABLE}
                WHERE {non_empty}
                  AND (speaker_en LIKE ? OR text_en LIKE ?)
                ORDER BY talk_sentence_id {order_sql}
                LIMIT ? OFFSET ?
                """,
                [like, like, page_size, offset],
            )
    else:
        non_empty = "((text_chs IS NOT NULL AND text_chs <> '') OR (text_en IS NOT NULL AND text_en <> ''))"
        if not q:
            total_rows = await d1_all(
                db,
                f"SELECT COUNT(*) AS c FROM {TALK_SENTENCE_TABLE} WHERE {non_empty}",
            )
            total = int((total_rows[0] if total_rows else {}).get("c") or 0)
            rows = await d1_all(
                db,
                f"""
                SELECT
                    talk_sentence_id,
                    speaker_chs,
                    speaker_en,
                    text_chs,
                    text_en,
                    COALESCE(NULLIF(speaker_chs, ''), NULLIF(speaker_en, ''), '') AS speaker,
                    COALESCE(NULLIF(text_chs, ''), NULLIF(text_en, ''), '') AS text
                FROM {TALK_SENTENCE_TABLE}
                WHERE {non_empty}
                ORDER BY talk_sentence_id {order_sql}
                LIMIT ? OFFSET ?
                """,
                [page_size, offset],
            )
        else:
            like = f"%{q}%"
            total_rows = await d1_all(
                db,
                f"""
                SELECT COUNT(*) AS c
                FROM {TALK_SENTENCE_TABLE}
                WHERE {non_empty}
                  AND (
                    speaker_chs LIKE ? OR text_chs LIKE ?
                    OR speaker_en LIKE ? OR text_en LIKE ?
                  )
                """,
                [like, like, like, like],
            )
            total = int((total_rows[0] if total_rows else {}).get("c") or 0)
            rows = await d1_all(
                db,
                f"""
                SELECT
                    talk_sentence_id,
                    speaker_chs,
                    speaker_en,
                    text_chs,
                    text_en,
                    COALESCE(NULLIF(speaker_chs, ''), NULLIF(speaker_en, ''), '') AS speaker,
                    COALESCE(NULLIF(text_chs, ''), NULLIF(text_en, ''), '') AS text
                FROM {TALK_SENTENCE_TABLE}
                WHERE {non_empty}
                  AND (
                    speaker_chs LIKE ? OR text_chs LIKE ?
                    OR speaker_en LIKE ? OR text_en LIKE ?
                  )
                ORDER BY talk_sentence_id {order_sql}
                LIMIT ? OFFSET ?
                """,
                [like, like, like, like, page_size, offset],
            )

    payload = {
        "q": q,
        "lang": lang,
        "order": order,
        "items": rows,
    }
    return json_response(with_paging_meta(payload, page, page_size, total))


async def handle_avatar_detail(path: str, query: Dict[str, List[str]], env: Any) -> Any:
    parts = path.strip("/").split("/")
    if len(parts) != 3 or not parts[2]:
        raise HttpError(400, "bad_request", "missing avatar id")
    try:
        avatar_id = int(parts[2])
    except Exception:
        raise HttpError(400, "bad_request", "invalid avatar id")

    lang = normalize_lang(qv(query, "lang", "CHS"))
    skill_level_limit = as_int(qv(query, "skill_level_limit", "10"), 10, 1, 20)
    level_max = as_int(qv(query, "level_max", "80"), 80, 1, 80)
    name_col = "name_en" if lang == "EN" else "name_chs"
    full_col = "full_name_en" if lang == "EN" else "full_name_chs"

    db = env.DB
    avatar = await d1_first(
        db,
        f"""
        SELECT avatar_id, name_hash, name_chs, name_en, full_name_hash, full_name_chs, full_name_en,
               rarity, damage_type, avatar_base_type, sp_need, max_promotion, max_rank,
               rank_id_list_json, skill_id_list_json,
               {name_col} AS name, {full_col} AS full_name
        FROM {AVATAR_TABLE}
        WHERE avatar_id = ?
        """,
        [avatar_id],
    )
    if avatar is None:
        raise HttpError(404, "not_found", "avatar not found")

    promotions = await d1_all(
        db,
        """
        SELECT promotion, max_level, player_level_require, world_level_require,
               hp_base, hp_add, attack_base, attack_add, defence_base, defence_add,
               speed_base, critical_chance, critical_damage, base_aggro, promotion_cost_json
        FROM avatar_promotion
        WHERE avatar_id = ?
        ORDER BY promotion
        """,
        [avatar_id],
    )

    level_stats = build_level_stats(promotions, level_max=level_max)
    checkpoints = [row for row in level_stats if row.get("level") == 1 or int(row.get("level") or 0) % 10 == 0]

    payload = {
        "avatar": avatar,
        "promotions": promotions,
        "level_stats": level_stats,
        "level_checkpoints": checkpoints,
        "skills": [],
        "ranks": [],
        "personal_stories": [],
        "skill_level_limit": skill_level_limit,
        "level_max": level_max,
    }
    return json_response(payload)


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        method = str(getattr(request, "method", "GET")).upper()
        parsed = urlparse(str(request.url))
        path = parsed.path
        query = parse_qs(parsed.query, keep_blank_values=True)

        try:
            if method == "OPTIONS" and (is_api_path(path) or path in {"/__health", "/__debug"}):
                return empty_response(status=204, cors=True)

            if path == "/__health":
                return json_response(
                    {
                        "ok": True,
                        "service": get_worker_name(self.env),
                        "time": datetime.now(timezone.utc).isoformat(),
                    },
                    cors=True,
                )
            if path == "/__debug":
                bindings = {
                    "DB": binding_exists(self.env, "DB"),
                    "KV": binding_exists(self.env, "KV"),
                    "R2": binding_exists(self.env, "R2"),
                    "AI": binding_exists(self.env, "AI"),
                    "ASSETS": binding_exists(self.env, "ASSETS"),
                    "QUEUE": binding_exists(self.env, "QUEUE"),
                }
                return json_response(
                    {
                        "method": str(getattr(request, "method", "")),
                        "url": str(request.url),
                        "pathname": parsed.path,
                        "search": parsed.query,
                        "cf": to_py(getattr(request, "cf", None), None),
                        "bindings": bindings,
                    },
                    cors=True,
                )
            if path == "/":
                return json_response(
                    {
                        "ok": True,
                        "service": get_worker_name(self.env),
                        "routes": API_ROUTE_HINTS,
                    },
                    cors=True,
                )

            if method != "GET":
                return json_response({"error": "method_not_allowed", "method": method, "path": path}, status=405, cors=is_api_path(path))

            if path == "/api/stats":
                resp = await handle_stats(self.env)
                return with_cors(resp)
            if path == "/api/search/dialogue":
                resp = await handle_search_dialogue(query, self.env)
                return with_cors(resp)
            if path.startswith("/api/dialogue/") and path.endswith("/refs"):
                return json_response({"error": "not_implemented", "path": path}, status=501, cors=True)
            if path == "/api/search/mission":
                return json_response({"error": "not_implemented", "path": path}, status=501, cors=True)
            if path.startswith("/api/mission/"):
                return json_response({"error": "not_implemented", "path": path}, status=501, cors=True)
            if path == "/api/search/avatar":
                return json_response({"error": "not_implemented", "path": path}, status=501, cors=True)
            if path.startswith("/api/avatar/"):
                resp = await handle_avatar_detail(path, query, self.env)
                return with_cors(resp)
            if path == "/api/search/item":
                return json_response({"error": "not_implemented", "path": path}, status=501, cors=True)
            if path == "/api/item/facets":
                return json_response({"error": "not_implemented", "path": path}, status=501, cors=True)
            if path.startswith("/api/item/"):
                return json_response({"error": "not_implemented", "path": path}, status=501, cors=True)
            if path == "/api/search/monster":
                return json_response({"error": "not_implemented", "path": path}, status=501, cors=True)
            if path == "/api/monster/facets":
                return json_response({"error": "not_implemented", "path": path}, status=501, cors=True)
            if path.startswith("/api/monster/"):
                return json_response({"error": "not_implemented", "path": path}, status=501, cors=True)
            if path == "/api/term/explain":
                return json_response({"error": "not_implemented", "path": path}, status=501, cors=True)
            if path == "/api/search/text":
                return json_response({"error": "not_implemented", "path": path}, status=501, cors=True)
            return json_response({"error": "app_not_found", "path": parsed.path}, status=404, cors=is_api_path(path))
        except HttpError as exc:
            return json_response({"error": exc.error, "message": exc.message}, status=exc.status, cors=is_api_path(path))
        except Exception as exc:
            return json_response({"error": "server_error", "message": str(exc)}, status=500, cors=is_api_path(path))
