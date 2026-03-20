"""
SQLite DB 접근 모듈.
게임 데이터(game_sync) 또는 PokéAPI(fetch_data)로 생성된 DB 모두 지원합니다.
"""

import json
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "pokemon.db")
TEAM_PATH = os.path.join(os.path.dirname(__file__), "data", "my_team.json")


def get_conn():
    return sqlite3.connect(DB_PATH)


def _detect_schema():
    """현재 DB가 게임 스키마(game_key)인지 PokéAPI 스키마(species_id)인지 감지"""
    conn = get_conn()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(pokemon)").fetchall()]
    conn.close()
    return "game" if "game_key" in cols else "api"


# === 포켓몬 조회 ===

def _row_to_dict(row, schema):
    if not row:
        return None
    if schema == "game":
        return {
            "id": row[0],
            "game_key": row[1],
            "species_key": row[2],
            "name_en": row[3],
            "name_ko": row[4],
            "display_name": row[5],
            "form_name": row[6],
            "type1_id": row[7],
            "type2_id": row[8],
            "hp": row[9],
            "attack": row[10],
            "defense": row[11],
            "sp_attack": row[12],
            "sp_defense": row[13],
            "speed": row[14],
            "is_default": row[15],
        }
    else:
        return {
            "id": row[0],
            "species_id": row[1],
            "name_en": row[2],
            "name_ko": row[3],
            "display_name": row[4],
            "form_name": row[5],
            "type1_id": row[6],
            "type2_id": row[7],
            "hp": row[8],
            "attack": row[9],
            "defense": row[10],
            "sp_attack": row[11],
            "sp_defense": row[12],
            "speed": row[13],
            "sprite_url": row[14],
            "is_default": row[15],
        }


def _pokemon_cols(schema):
    if schema == "game":
        return """id, game_key, species_key, name_en, name_ko, display_name, form_name,
                  type1_id, type2_id, hp, attack, defense, sp_attack, sp_defense,
                  speed, is_default"""
    else:
        return """id, species_id, name_en, name_ko, display_name, form_name,
                  type1_id, type2_id, hp, attack, defense, sp_attack, sp_defense,
                  speed, sprite_url, is_default"""


def get_all_pokemon_names():
    """전체 포켓몬 display_name 목록 반환"""
    conn = get_conn()
    schema = _detect_schema()
    if schema == "game":
        order = "species_key, is_default DESC, id"
    else:
        order = "species_id, is_default DESC, id"
    rows = conn.execute(
        f"SELECT id, display_name, name_en FROM pokemon ORDER BY {order}"
    ).fetchall()
    conn.close()
    return [(r[0], r[1], r[2]) for r in rows]


def search_pokemon_by_name(display_name):
    """display_name으로 포켓몬 검색"""
    conn = get_conn()
    schema = _detect_schema()
    row = conn.execute(
        f"SELECT {_pokemon_cols(schema)} FROM pokemon WHERE display_name = ?",
        (display_name,),
    ).fetchone()
    conn.close()
    return _row_to_dict(row, schema)


def get_pokemon_by_id(poke_id):
    conn = get_conn()
    schema = _detect_schema()
    row = conn.execute(
        f"SELECT {_pokemon_cols(schema)} FROM pokemon WHERE id = ?",
        (poke_id,),
    ).fetchone()
    conn.close()
    return _row_to_dict(row, schema)


def get_pokemon_by_game_key(game_key):
    """게임 키(GARCHOMP, GARCHOMP_1 등)로 검색"""
    conn = get_conn()
    schema = _detect_schema()
    if schema != "game":
        conn.close()
        return None
    row = conn.execute(
        f"SELECT {_pokemon_cols(schema)} FROM pokemon WHERE game_key = ?",
        (game_key,),
    ).fetchone()
    conn.close()
    return _row_to_dict(row, schema)


# === 타입 조회 ===

def get_type_name(type_id):
    if type_id is None:
        return None
    conn = get_conn()
    row = conn.execute(
        "SELECT name_ko FROM types WHERE id = ?", (type_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else "???"


def get_all_types():
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, name_en, name_ko FROM types ORDER BY id"
    ).fetchall()
    conn.close()
    return {r[0]: {"name_en": r[1], "name_ko": r[2]} for r in rows}


def get_type_id_by_ko(name_ko):
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM types WHERE name_ko = ?", (name_ko,)
    ).fetchone()
    conn.close()
    return row[0] if row else None


# === 상성 조회 ===

def get_type_efficacy():
    conn = get_conn()
    rows = conn.execute(
        "SELECT attack_type_id, defend_type_id, damage_factor FROM type_efficacy"
    ).fetchall()
    conn.close()
    return {(r[0], r[1]): r[2] for r in rows}


def get_damage_factor(efficacy_map, atk_type_id, def_type_id):
    return efficacy_map.get((atk_type_id, def_type_id), 100)


# === 기술 조회 (게임 데이터 전용) ===

def get_move_by_symbol(symbol):
    """기술 심볼로 조회 (게임 데이터 전용)"""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id, symbol, name_en, name_ko, type_id, category, power, accuracy, pp "
            "FROM moves WHERE symbol = ?",
            (symbol,),
        ).fetchone()
    except sqlite3.OperationalError:
        conn.close()
        return None
    conn.close()
    if not row:
        return None
    return {
        "id": row[0], "symbol": row[1], "name_en": row[2], "name_ko": row[3],
        "type_id": row[4], "category": row[5], "power": row[6],
        "accuracy": row[7], "pp": row[8],
    }


def get_moves_for_pokemon(move_symbols):
    """여러 기술 심볼 리스트를 한 번에 조회"""
    if not move_symbols:
        return []
    conn = get_conn()
    try:
        placeholders = ",".join("?" * len(move_symbols))
        rows = conn.execute(
            f"SELECT symbol, name_ko, type_id, category, power FROM moves WHERE symbol IN ({placeholders})",
            move_symbols,
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []
    conn.close()
    return [
        {"symbol": r[0], "name_ko": r[1], "type_id": r[2], "category": r[3], "power": r[4]}
        for r in rows
    ]


# === 내 팀 관리 ===

def load_team():
    if not os.path.exists(TEAM_PATH):
        return []
    with open(TEAM_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_team(team_ids):
    os.makedirs(os.path.dirname(TEAM_PATH), exist_ok=True)
    with open(TEAM_PATH, "w", encoding="utf-8") as f:
        json.dump(team_ids, f, ensure_ascii=False, indent=2)
