"""
PokéAPI에서 포켓몬 데이터를 받아와 로컬 SQLite DB에 저장하는 스크립트.
최초 1회만 실행하면 됩니다.
"""

import json
import os
import sqlite3
import time

import requests

API_BASE = "https://pokeapi.co/api/v2"
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "pokemon.db")


def create_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS types (
            id INTEGER PRIMARY KEY,
            name_en TEXT NOT NULL,
            name_ko TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS type_efficacy (
            attack_type_id INTEGER NOT NULL,
            defend_type_id INTEGER NOT NULL,
            damage_factor INTEGER NOT NULL,
            PRIMARY KEY (attack_type_id, defend_type_id)
        );

        CREATE TABLE IF NOT EXISTS pokemon (
            id INTEGER PRIMARY KEY,
            name_en TEXT NOT NULL,
            name_ko TEXT NOT NULL,
            type1_id INTEGER NOT NULL,
            type2_id INTEGER,
            hp INTEGER DEFAULT 0,
            attack INTEGER DEFAULT 0,
            defense INTEGER DEFAULT 0,
            sp_attack INTEGER DEFAULT 0,
            sp_defense INTEGER DEFAULT 0,
            speed INTEGER DEFAULT 0,
            sprite_url TEXT,
            FOREIGN KEY (type1_id) REFERENCES types(id),
            FOREIGN KEY (type2_id) REFERENCES types(id)
        );
    """)
    conn.commit()
    return conn


def fetch_json(url, retries=3):
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            if attempt < retries - 1:
                print(f"  재시도 중... ({attempt + 1}/{retries})")
                time.sleep(2)
            else:
                print(f"  실패: {e}")
                return None


def fetch_types(conn):
    """18개 타입 데이터 + 상성표 수집"""
    print("=== 타입 데이터 수집 중 ===")
    c = conn.cursor()

    # 타입 목록
    data = fetch_json(f"{API_BASE}/type?limit=30")
    if not data:
        return

    type_map = {}  # id -> name_en

    for entry in data["results"]:
        type_data = fetch_json(entry["url"])
        if not type_data:
            continue

        type_id = type_data["id"]
        # 10000번대 이상은 특수 타입(스텔라 등), 건너뜀
        if type_id >= 10000:
            continue

        name_en = type_data["name"]

        # 한국어 이름 찾기
        name_ko = name_en
        for name_entry in type_data.get("names", []):
            if name_entry["language"]["name"] == "ko":
                name_ko = name_entry["name"]
                break

        type_map[type_id] = name_en
        c.execute(
            "INSERT OR REPLACE INTO types (id, name_en, name_ko) VALUES (?, ?, ?)",
            (type_id, name_en, name_ko),
        )
        print(f"  타입: {name_ko} ({name_en})")

        # 상성 데이터 저장
        relations = type_data["damage_relations"]

        # 2배 데미지를 주는 상대 타입
        for t in relations["double_damage_to"]:
            target_url = t["url"]
            target_id = int(target_url.rstrip("/").split("/")[-1])
            c.execute(
                "INSERT OR REPLACE INTO type_efficacy VALUES (?, ?, ?)",
                (type_id, target_id, 200),
            )

        # 0.5배 데미지를 주는 상대 타입
        for t in relations["half_damage_to"]:
            target_url = t["url"]
            target_id = int(target_url.rstrip("/").split("/")[-1])
            c.execute(
                "INSERT OR REPLACE INTO type_efficacy VALUES (?, ?, ?)",
                (type_id, target_id, 50),
            )

        # 0배 데미지를 주는 상대 타입
        for t in relations["no_damage_to"]:
            target_url = t["url"]
            target_id = int(target_url.rstrip("/").split("/")[-1])
            c.execute(
                "INSERT OR REPLACE INTO type_efficacy VALUES (?, ?, ?)",
                (type_id, target_id, 0),
            )

    conn.commit()
    print(f"  총 {len(type_map)}개 타입 저장 완료\n")
    return type_map


def fetch_pokemon(conn, max_id=1025):
    """포켓몬 데이터 수집 (기본: 1~1025번까지)"""
    print("=== 포켓몬 데이터 수집 중 ===")
    c = conn.cursor()

    # 한 번에 목록 가져오기
    list_data = fetch_json(f"{API_BASE}/pokemon?limit={max_id}&offset=0")
    if not list_data:
        return

    total = len(list_data["results"])

    for i, entry in enumerate(list_data["results"]):
        pokemon_url = entry["url"]
        poke_id = int(pokemon_url.rstrip("/").split("/")[-1])

        # 이미 DB에 있으면 건너뜀
        existing = c.execute(
            "SELECT id FROM pokemon WHERE id = ?", (poke_id,)
        ).fetchone()
        if existing:
            continue

        # 포켓몬 기본 데이터
        poke_data = fetch_json(pokemon_url)
        if not poke_data:
            continue

        name_en = poke_data["name"]

        # 타입
        types = poke_data["types"]
        type1_id = None
        type2_id = None
        for t in types:
            tid = int(t["type"]["url"].rstrip("/").split("/")[-1])
            if t["slot"] == 1:
                type1_id = tid
            else:
                type2_id = tid

        # 종족값
        stats = {s["stat"]["name"]: s["base_stat"] for s in poke_data["stats"]}

        # 스프라이트
        sprite_url = poke_data["sprites"].get("front_default", "")

        # 한국어 이름 (pokemon-species 엔드포인트)
        name_ko = name_en
        species_data = fetch_json(f"{API_BASE}/pokemon-species/{poke_id}")
        if species_data:
            for name_entry in species_data.get("names", []):
                if name_entry["language"]["name"] == "ko":
                    name_ko = name_entry["name"]
                    break

        c.execute(
            """INSERT OR REPLACE INTO pokemon
               (id, name_en, name_ko, type1_id, type2_id,
                hp, attack, defense, sp_attack, sp_defense, speed, sprite_url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                poke_id,
                name_en,
                name_ko,
                type1_id,
                type2_id,
                stats.get("hp", 0),
                stats.get("attack", 0),
                stats.get("defense", 0),
                stats.get("special-attack", 0),
                stats.get("special-defense", 0),
                stats.get("speed", 0),
                sprite_url,
            ),
        )

        if (i + 1) % 50 == 0:
            conn.commit()
            print(f"  진행: {i + 1}/{total} ({name_ko})")

    conn.commit()
    print(f"  포켓몬 데이터 저장 완료!\n")


def main():
    print("PokéAPI 데이터 수집을 시작합니다...\n")
    conn = create_db()

    fetch_types(conn)
    fetch_pokemon(conn)

    # 최종 확인
    c = conn.cursor()
    type_count = c.execute("SELECT COUNT(*) FROM types").fetchone()[0]
    poke_count = c.execute("SELECT COUNT(*) FROM pokemon").fetchone()[0]
    eff_count = c.execute("SELECT COUNT(*) FROM type_efficacy").fetchone()[0]

    print("=== 수집 완료 ===")
    print(f"  타입: {type_count}개")
    print(f"  포켓몬: {poke_count}마리")
    print(f"  상성 데이터: {eff_count}건")
    print(f"  DB 위치: {DB_PATH}")

    conn.close()


if __name__ == "__main__":
    main()
