"""
SQLite DB 접근 모듈.
포켓몬/타입 데이터 조회 및 팀 관리 기능 제공.
"""

import json
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "pokemon.db")
TEAM_PATH = os.path.join(os.path.dirname(__file__), "data", "my_team.json")


def get_conn():
    return sqlite3.connect(DB_PATH)


# === 포켓몬 조회 ===

def get_all_pokemon_names():
    """전체 포켓몬 이름 목록 (한국어) 반환"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, name_ko, name_en FROM pokemon ORDER BY id"
    ).fetchall()
    conn.close()
    return [(r[0], r[1], r[2]) for r in rows]


def search_pokemon_by_name(name_ko):
    """한국어 이름으로 포켓몬 검색 (정확 매치)"""
    conn = get_conn()
    row = conn.execute(
        """SELECT id, name_en, name_ko, type1_id, type2_id,
                  hp, attack, defense, sp_attack, sp_defense, speed, sprite_url
           FROM pokemon WHERE name_ko = ?""",
        (name_ko,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "name_en": row[1],
        "name_ko": row[2],
        "type1_id": row[3],
        "type2_id": row[4],
        "hp": row[5],
        "attack": row[6],
        "defense": row[7],
        "sp_attack": row[8],
        "sp_defense": row[9],
        "speed": row[10],
        "sprite_url": row[11],
    }


def get_pokemon_by_id(poke_id):
    conn = get_conn()
    row = conn.execute(
        """SELECT id, name_en, name_ko, type1_id, type2_id,
                  hp, attack, defense, sp_attack, sp_defense, speed, sprite_url
           FROM pokemon WHERE id = ?""",
        (poke_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "name_en": row[1],
        "name_ko": row[2],
        "type1_id": row[3],
        "type2_id": row[4],
        "hp": row[5],
        "attack": row[6],
        "defense": row[7],
        "sp_attack": row[8],
        "sp_defense": row[9],
        "speed": row[10],
        "sprite_url": row[11],
    }


# === 타입 조회 ===

def get_type_name(type_id):
    """타입 ID로 한국어 이름 조회"""
    conn = get_conn()
    row = conn.execute(
        "SELECT name_ko FROM types WHERE id = ?", (type_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else "???"


def get_all_types():
    conn = get_conn()
    rows = conn.execute("SELECT id, name_en, name_ko FROM types ORDER BY id").fetchall()
    conn.close()
    return {r[0]: {"name_en": r[1], "name_ko": r[2]} for r in rows}


# === 상성 조회 ===

def get_type_efficacy():
    """전체 상성표를 딕셔너리로 반환. key: (공격타입id, 방어타입id), value: 배율(200/50/0)"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT attack_type_id, defend_type_id, damage_factor FROM type_efficacy"
    ).fetchall()
    conn.close()
    return {(r[0], r[1]): r[2] for r in rows}


def get_damage_factor(efficacy_map, atk_type_id, def_type_id):
    """공격 타입이 방어 타입에 주는 배율 (100 = 1배, 200 = 2배, 50 = 0.5배, 0 = 무효)"""
    return efficacy_map.get((atk_type_id, def_type_id), 100)


# === 내 팀 관리 ===

def load_team():
    """저장된 팀 불러오기. 리스트 of 포켓몬 ID."""
    if not os.path.exists(TEAM_PATH):
        return []
    with open(TEAM_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_team(team_ids):
    """팀 저장 (포켓몬 ID 리스트)."""
    os.makedirs(os.path.dirname(TEAM_PATH), exist_ok=True)
    with open(TEAM_PATH, "w", encoding="utf-8") as f:
        json.dump(team_ids, f, ensure_ascii=False, indent=2)
