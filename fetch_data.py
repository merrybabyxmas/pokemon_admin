"""
PokéAPI에서 포켓몬 데이터를 받아와 로컬 SQLite DB에 저장하는 스크립트.
리전 폼(알로라/가라르/히스이/팔데아) 및 주요 폼 체인지까지 수집합니다.
최초 1회만 실행하면 됩니다.
"""

import os
import sqlite3
import time

import requests

API_BASE = "https://pokeapi.co/api/v2"
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "pokemon.db")

# 폼 접미사 → 한국어 이름 매핑
FORM_SUFFIX_KO = {
    "alola": "알로라",
    "alolan": "알로라",
    "galar": "가라르",
    "galarian": "가라르",
    "hisui": "히스이",
    "hisuian": "히스이",
    "paldea": "팔데아",
    "paldean": "팔데아",
    "paldea-combat-breed": "팔데아 컴뱃종",
    "paldea-blaze-breed": "팔데아 블레이즈종",
    "paldea-aqua-breed": "팔데아 아쿠아종",
    "mega": "메가",
    "mega-x": "메가X",
    "mega-y": "메가Y",
    "gmax": "거다이맥스",
    "origin": "오리진",
    "altered": "어나더",
    "sky": "스카이",
    "land": "랜드",
    "therian": "영물",
    "incarnate": "화신",
    "black": "블랙",
    "white": "화이트",
    "heat": "히트",
    "wash": "워시",
    "frost": "프로스트",
    "fan": "스핀",
    "mow": "커트",
    "attack": "어택",
    "defense": "디펜스",
    "speed": "스피드",
    "sandy": "모래땅",
    "trash": "슈레땅",
    "plant": "초목",
    "sunshine": "선샤인",
    "rainy": "레이니",
    "snowy": "스노우",
    "primal": "원시회귀",
    "ash": "지우",
    "dusk-mane": "황혼의갈기",
    "dawn-wings": "새벽의날개",
    "ultra": "울트라",
    "crowned-sword": "검의왕",
    "crowned-shield": "방패의왕",
    "ice-rider": "백마탄",
    "shadow-rider": "흑마탄",
    "bloodmoon": "붉은달",
    "cornerstone": "주춧돌",
    "hearthflame": "화덕",
    "wellspring": "우물",
    "teal": "벽록",
}


def create_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 기존 DB가 이전 스키마(species_id 컬럼 없음)이면 테이블 삭제 후 재생성
    try:
        c.execute("SELECT species_id FROM pokemon LIMIT 1")
    except sqlite3.OperationalError:
        print("  기존 DB 스키마가 오래되어 pokemon 테이블을 재생성합니다...")
        c.execute("DROP TABLE IF EXISTS pokemon")
        conn.commit()

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
            species_id INTEGER NOT NULL,
            name_en TEXT NOT NULL,
            name_ko TEXT NOT NULL,
            display_name TEXT NOT NULL,
            form_name TEXT,
            type1_id INTEGER NOT NULL,
            type2_id INTEGER,
            hp INTEGER DEFAULT 0,
            attack INTEGER DEFAULT 0,
            defense INTEGER DEFAULT 0,
            sp_attack INTEGER DEFAULT 0,
            sp_defense INTEGER DEFAULT 0,
            speed INTEGER DEFAULT 0,
            sprite_url TEXT,
            is_default INTEGER DEFAULT 1,
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

    data = fetch_json(f"{API_BASE}/type?limit=30")
    if not data:
        return

    type_map = {}

    for entry in data["results"]:
        type_data = fetch_json(entry["url"])
        if not type_data:
            continue

        type_id = type_data["id"]
        if type_id >= 10000:
            continue

        name_en = type_data["name"]
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

        relations = type_data["damage_relations"]
        for factor_key, factor_val in [
            ("double_damage_to", 200),
            ("half_damage_to", 50),
            ("no_damage_to", 0),
        ]:
            for t in relations[factor_key]:
                target_id = int(t["url"].rstrip("/").split("/")[-1])
                c.execute(
                    "INSERT OR REPLACE INTO type_efficacy VALUES (?, ?, ?)",
                    (type_id, target_id, factor_val),
                )

    conn.commit()
    print(f"  총 {len(type_map)}개 타입 저장 완료\n")
    return type_map


def parse_form_suffix(pokemon_name, species_name):
    """포켓몬 API 이름에서 폼 접미사를 추출. 예: 'vulpix-alola' -> 'alola'"""
    if pokemon_name == species_name:
        return None
    if pokemon_name.startswith(species_name + "-"):
        return pokemon_name[len(species_name) + 1:]
    return None


def form_suffix_to_ko(suffix):
    """영문 폼 접미사를 한국어로 변환"""
    if not suffix:
        return None
    # 정확 매치 먼저
    if suffix in FORM_SUFFIX_KO:
        return FORM_SUFFIX_KO[suffix]
    # 부분 매치 (복합 접미사용)
    for key, val in FORM_SUFFIX_KO.items():
        if key in suffix:
            return val
    # 매칭 안 되면 영문 그대로
    return suffix


def save_pokemon_row(c, poke_id, species_id, name_en, name_ko, display_name,
                     form_name, poke_data, is_default):
    """포켓몬 데이터 한 행을 DB에 저장"""
    types = poke_data["types"]
    type1_id = None
    type2_id = None
    for t in types:
        tid = int(t["type"]["url"].rstrip("/").split("/")[-1])
        if t["slot"] == 1:
            type1_id = tid
        else:
            type2_id = tid

    stats = {s["stat"]["name"]: s["base_stat"] for s in poke_data["stats"]}
    sprite_url = poke_data["sprites"].get("front_default", "")

    c.execute(
        """INSERT OR REPLACE INTO pokemon
           (id, species_id, name_en, name_ko, display_name, form_name,
            type1_id, type2_id, hp, attack, defense, sp_attack, sp_defense,
            speed, sprite_url, is_default)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            poke_id, species_id, name_en, name_ko, display_name, form_name,
            type1_id, type2_id,
            stats.get("hp", 0), stats.get("attack", 0), stats.get("defense", 0),
            stats.get("special-attack", 0), stats.get("special-defense", 0),
            stats.get("speed", 0), sprite_url, 1 if is_default else 0,
        ),
    )


def fetch_pokemon(conn, max_species=1025):
    """종(species) 기준으로 순회하며 기본 폼 + 리전 폼 전부 수집"""
    print("=== 포켓몬 데이터 수집 중 (리전 폼 포함) ===")
    c = conn.cursor()

    for species_id in range(1, max_species + 1):
        # 이미 이 종의 기본 폼이 있으면 건너뜀
        existing = c.execute(
            "SELECT id FROM pokemon WHERE species_id = ?", (species_id,)
        ).fetchone()
        if existing:
            continue

        # 종 데이터
        species_data = fetch_json(f"{API_BASE}/pokemon-species/{species_id}")
        if not species_data:
            continue

        # 한국어 이름
        base_name_ko = species_data["name"]
        for name_entry in species_data.get("names", []):
            if name_entry["language"]["name"] == "ko":
                base_name_ko = name_entry["name"]
                break

        species_name_en = species_data["name"]

        # 모든 폼(variety) 순회
        varieties = species_data.get("varieties", [])
        for variety in varieties:
            is_default = variety["is_default"]
            poke_url = variety["pokemon"]["url"]
            poke_name_en = variety["pokemon"]["name"]
            poke_id = int(poke_url.rstrip("/").split("/")[-1])

            # 거다이맥스 폼은 타입이 동일하므로 건너뜀 (선택적)
            suffix = parse_form_suffix(poke_name_en, species_name_en)
            if suffix and "gmax" in suffix:
                continue
            # totem 폼도 건너뜀 (타입 동일)
            if suffix and "totem" in suffix:
                continue

            poke_data = fetch_json(f"{API_BASE}/pokemon/{poke_id}")
            if not poke_data:
                continue

            # 기본 폼: 종족 한국어 이름 그대로
            # 리전 폼: "이름(리전명)" 형식
            if is_default or suffix is None:
                display_name = base_name_ko
                form_name_ko = None
            else:
                form_name_ko = form_suffix_to_ko(suffix)
                display_name = f"{base_name_ko}({form_name_ko})"

            save_pokemon_row(
                c, poke_id, species_id, poke_name_en, base_name_ko,
                display_name, form_name_ko, poke_data, is_default,
            )

            if not is_default:
                print(f"    폼: {display_name} (id={poke_id})")

        if species_id % 50 == 0:
            conn.commit()
            print(f"  진행: {species_id}/{max_species} ({base_name_ko})")

    conn.commit()
    print(f"  포켓몬 데이터 저장 완료!\n")


def main():
    print("PokéAPI 데이터 수집을 시작합니다 (리전 폼 포함)...\n")
    conn = create_db()

    fetch_types(conn)
    fetch_pokemon(conn)

    c = conn.cursor()
    type_count = c.execute("SELECT COUNT(*) FROM types").fetchone()[0]
    poke_count = c.execute("SELECT COUNT(*) FROM pokemon").fetchone()[0]
    form_count = c.execute("SELECT COUNT(*) FROM pokemon WHERE is_default = 0").fetchone()[0]
    eff_count = c.execute("SELECT COUNT(*) FROM type_efficacy").fetchone()[0]

    print("=== 수집 완료 ===")
    print(f"  타입: {type_count}개")
    print(f"  포켓몬: {poke_count}마리 (리전/폼 체인지: {form_count}개 포함)")
    print(f"  상성 데이터: {eff_count}건")
    print(f"  DB 위치: {DB_PATH}")

    conn.close()


if __name__ == "__main__":
    main()
