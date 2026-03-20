"""
Pokemon Another Red 게임 데이터 동기화 모듈.

게임의 .dat 파일(Ruby Marshal)에서 포켓몬/타입/기술 데이터를 읽고,
세이브 파일(Game.rxdata)에서 현재 파티를 가져옵니다.
"""

import os
import platform
import sqlite3

try:
    import rubymarshal.classes
    import rubymarshal.reader
    HAS_RUBYMARSHAL = True
except ImportError:
    HAS_RUBYMARSHAL = False

import marshal_reader

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "pokemon.db")

# 기술 분류: 0=물리, 1=특수, 2=변화
MOVE_CATEGORY = {0: "물리", 1: "특수", 2: "변화"}


def _sym(name):
    """Symbol 생성 (rubymarshal 또는 커스텀)"""
    if HAS_RUBYMARSHAL:
        return rubymarshal.classes.Symbol(name)
    return marshal_reader.RubySymbol(name)


def _sym_str(sym):
    """Symbol 객체를 문자열로 변환"""
    if HAS_RUBYMARSHAL and isinstance(sym, rubymarshal.classes.Symbol):
        return str(sym).lstrip(":")
    if isinstance(sym, marshal_reader.RubySymbol):
        return sym.name
    s = str(sym)
    return s.lstrip(":")


def _to_str(val):
    """RubyString 등 Ruby 타입을 Python str로 안전하게 변환"""
    if val is None:
        return None
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return str(val)


def _obj_get(obj, key):
    """RubyObject에서 속성 읽기 (양쪽 파서 호환)"""
    if isinstance(obj, marshal_reader.RubyObject):
        # 커스텀 파서: 키가 "@name" 형식
        return obj.attributes.get(f"@{key}") or obj.attributes.get(key)
    if HAS_RUBYMARSHAL and hasattr(obj, "attributes"):
        return obj.attributes.get(f"@{key}") or obj.attributes.get(key)
    if isinstance(obj, dict):
        return obj.get(key) or obj.get(f"@{key}")
    return None


def find_game_data_dir():
    """게임 Data 폴더 자동 탐색. 여러 경로를 시도합니다."""
    candidates = []

    # 1. 환경변수로 지정된 경로
    env_path = os.environ.get("POKEMON_GAME_DIR")
    if env_path:
        candidates.append(os.path.join(env_path, "Data"))

    # 2. 현재 프로젝트 내 extracted 폴더
    project_root = os.path.dirname(__file__)
    raw_dir = os.path.join(os.path.dirname(project_root), "pokemon_raw", "extracted")
    if os.path.exists(raw_dir):
        for name in os.listdir(raw_dir):
            candidates.append(os.path.join(raw_dir, name, "Data"))

    # 3. 직접 지정 경로 (필요시 수정)
    candidates.append(os.path.join(project_root, "game_data", "Data"))

    for path in candidates:
        if os.path.isdir(path) and os.path.exists(os.path.join(path, "species.dat")):
            return path

    return None


def find_save_file():
    """세이브 파일(Game.rxdata) 자동 탐색."""
    candidates = []

    env_path = os.environ.get("POKEMON_SAVE_DIR")
    if env_path:
        candidates.append(os.path.join(env_path, "Game.rxdata"))

    system = platform.system()
    if system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            candidates.append(os.path.join(appdata, "Pokemon Another Red", "Game.rxdata"))
            # 일반적인 다른 경로들
            for name in os.listdir(appdata) if os.path.isdir(appdata) else []:
                if "pokemon" in name.lower() and "another" in name.lower():
                    candidates.append(os.path.join(appdata, name, "Game.rxdata"))
    elif system == "Linux":
        home = os.path.expanduser("~")
        candidates.append(os.path.join(home, ".local", "share", "mkxp", "Game.rxdata"))

    # 게임 폴더 내 세이브
    game_dir = find_game_data_dir()
    if game_dir:
        parent = os.path.dirname(game_dir)
        candidates.append(os.path.join(parent, "Game.rxdata"))
        # Auto Multi Save 플러그인 패턴
        for i in range(1, 4):
            candidates.append(os.path.join(parent, f"Game_{i}.rxdata"))

    for path in candidates:
        if os.path.isfile(path):
            return path

    return None


def load_ruby_marshal(filepath, use_custom=False):
    """Ruby Marshal 파일 로드. use_custom=True면 커스텀 파서 사용 (세이브 파일용)."""
    if use_custom or not HAS_RUBYMARSHAL:
        return marshal_reader.load(filepath)
    try:
        with open(filepath, "rb") as f:
            return rubymarshal.reader.load(f)
    except Exception:
        # rubymarshal 실패 시 커스텀 파서로 폴백
        return marshal_reader.load(filepath)


# ─── 게임 데이터 임포트 (species.dat, types.dat, moves.dat → SQLite) ───


def import_game_data(data_dir, db_path=None):
    """
    게임의 .dat 파일에서 타입, 포켓몬, 기술 데이터를 읽어
    로컬 SQLite DB에 저장합니다.
    PokéAPI 대신 게임 자체 데이터를 사용하므로 더 정확합니다.
    """
    if db_path is None:
        db_path = DB_PATH

    print("=== 게임 데이터 임포트 시작 ===\n")

    # DB 초기화
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.executescript("""
        DROP TABLE IF EXISTS pokemon;
        DROP TABLE IF EXISTS types;
        DROP TABLE IF EXISTS type_efficacy;
        DROP TABLE IF EXISTS moves;

        CREATE TABLE types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE NOT NULL,
            name_en TEXT NOT NULL,
            name_ko TEXT NOT NULL
        );

        CREATE TABLE type_efficacy (
            attack_type_id INTEGER NOT NULL,
            defend_type_id INTEGER NOT NULL,
            damage_factor INTEGER NOT NULL,
            PRIMARY KEY (attack_type_id, defend_type_id)
        );

        CREATE TABLE pokemon (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_key TEXT UNIQUE NOT NULL,
            species_key TEXT NOT NULL,
            name_en TEXT NOT NULL,
            name_ko TEXT NOT NULL,
            display_name TEXT NOT NULL,
            form_name TEXT,
            form_number INTEGER DEFAULT 0,
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

        CREATE TABLE moves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE NOT NULL,
            name_en TEXT NOT NULL,
            name_ko TEXT NOT NULL,
            type_id INTEGER,
            category INTEGER,
            power INTEGER DEFAULT 0,
            accuracy INTEGER DEFAULT 0,
            pp INTEGER DEFAULT 0,
            FOREIGN KEY (type_id) REFERENCES types(id)
        );
    """)

    # ─── 1. 타입 임포트 ───
    print("[1/3] 타입 데이터 임포트 중...")
    types_raw = load_ruby_marshal(os.path.join(data_dir, "types.dat"))

    # 한국어 번역 로드
    msg_path = os.path.join(data_dir, "messages_kor_core.dat")
    type_ko_names = {}
    if os.path.exists(msg_path):
        msg_data = load_ruby_marshal(msg_path)
        # 섹션 0이 타입 이름일 수 있음, 또는 types.dat 자체에 한국어가 들어있음
        # types.dat의 @real_name이 이미 한국어이므로 그것을 사용

    type_sym_to_id = {}  # Symbol -> DB id 매핑
    for sym, val in types_raw.items():
        attrs = val.attributes
        sym_str = _sym_str(attrs["@id"])
        name_ko = _to_str(attrs["@real_name"])
        name_en = sym_str.capitalize()

        # 스텔라, QMARKS 등 특수 타입은 제외
        if sym_str in ("QMARKS",):
            continue

        c.execute(
            "INSERT INTO types (symbol, name_en, name_ko) VALUES (?, ?, ?)",
            (sym_str, name_en, name_ko),
        )
        db_id = c.lastrowid
        type_sym_to_id[sym_str] = db_id
        print(f"  {name_ko} ({name_en})")

    # 상성 데이터 (weaknesses/resistances/immunities → efficacy)
    for sym, val in types_raw.items():
        attrs = val.attributes
        atk_sym = _sym_str(attrs["@id"])
        if atk_sym not in type_sym_to_id:
            continue
        atk_id = type_sym_to_id[atk_sym]

        # weaknesses = 이 타입이 약점을 찌르는 타입 (2배 데미지)
        # → 반대로 해석: weaknesses는 "이 타입의 약점 타입"
        # Pokemon Essentials에서:
        #   weaknesses = 이 타입에 2배 데미지를 주는 공격 타입
        #   resistances = 이 타입에 0.5배 데미지를 주는 공격 타입
        #   immunities = 이 타입에 0배 데미지를 주는 공격 타입
        # → type_efficacy 기준: attack → defense
        for weak_sym in attrs.get("@weaknesses", []):
            weak_str = _sym_str(weak_sym)
            if weak_str in type_sym_to_id:
                # weak_str 타입으로 공격하면 atk_sym 타입에 2배
                c.execute(
                    "INSERT OR REPLACE INTO type_efficacy VALUES (?, ?, ?)",
                    (type_sym_to_id[weak_str], atk_id, 200),
                )

        for resist_sym in attrs.get("@resistances", []):
            resist_str = _sym_str(resist_sym)
            if resist_str in type_sym_to_id:
                c.execute(
                    "INSERT OR REPLACE INTO type_efficacy VALUES (?, ?, ?)",
                    (type_sym_to_id[resist_str], atk_id, 50),
                )

        for immune_sym in attrs.get("@immunities", []):
            immune_str = _sym_str(immune_sym)
            if immune_str in type_sym_to_id:
                c.execute(
                    "INSERT OR REPLACE INTO type_efficacy VALUES (?, ?, ?)",
                    (type_sym_to_id[immune_str], atk_id, 0),
                )

    conn.commit()
    print(f"  → {len(type_sym_to_id)}개 타입 완료\n")

    # ─── 2. 기술 임포트 ───
    print("[2/3] 기술 데이터 임포트 중...")
    moves_raw = load_ruby_marshal(os.path.join(data_dir, "moves.dat"))

    # 한국어 기술명
    move_ko_names = {}
    if os.path.exists(msg_path):
        msg_data = load_ruby_marshal(msg_path)
        if len(msg_data) > 5 and isinstance(msg_data[5], dict):
            move_ko_names = {_to_str(k): _to_str(v) for k, v in msg_data[5].items()}

    move_sym_to_id = {}
    for sym, val in moves_raw.items():
        attrs = val.attributes
        sym_str = _sym_str(attrs["@id"])
        name_en = _to_str(attrs["@real_name"])
        name_ko = _to_str(move_ko_names.get(name_en, name_en))

        type_sym = _sym_str(attrs["@type"])
        type_id = type_sym_to_id.get(type_sym)

        category = attrs.get("@category", 2)
        power = attrs.get("@power", 0)
        accuracy = attrs.get("@accuracy", 0)
        pp = attrs.get("@total_pp", 0)

        c.execute(
            "INSERT INTO moves (symbol, name_en, name_ko, type_id, category, power, accuracy, pp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (sym_str, name_en, name_ko, type_id, category, power, accuracy, pp),
        )
        move_sym_to_id[sym_str] = c.lastrowid

    conn.commit()
    print(f"  → {len(move_sym_to_id)}개 기술 완료\n")

    # ─── 3. 포켓몬 임포트 ───
    print("[3/3] 포켓몬 데이터 임포트 중...")
    species_raw = load_ruby_marshal(os.path.join(data_dir, "species.dat"))

    # 한국어 포켓몬 이름
    poke_ko_names = {}
    if os.path.exists(msg_path):
        msg_data = load_ruby_marshal(msg_path)
        if len(msg_data) > 1 and isinstance(msg_data[1], dict):
            poke_ko_names = {_to_str(k): _to_str(v) for k, v in msg_data[1].items()}

    # 폼 이름 한국어 매핑
    FORM_NAME_KO = {
        "Mega": "메가",
        "Mega X": "메가X",
        "Mega Y": "메가Y",
        "Alolan": "알로라", "Alola": "알로라",
        "Galarian": "가라르", "Galar": "가라르",
        "Hisuian": "히스이", "Hisui": "히스이",
        "Paldean": "팔데아", "Paldea": "팔데아",
        "Origin": "오리진", "Origin Forme": "오리진",
        "Primal": "원시회귀", "Primal Reversion": "원시회귀",
        "Therian": "영물", "Therian Forme": "영물",
        "Incarnate": "화신",
        "Black": "블랙", "White": "화이트",
        "Mega Charizard X": "메가X",
        "Mega Charizard Y": "메가Y",
        "Mega Mewtwo X": "메가X",
        "Mega Mewtwo Y": "메가Y",
        "Midnight": "한밤", "Dusk": "황혼",
        "School": "군집",
        "Teal Mask": "벽록",
        "Wellspring Mask": "우물",
        "Hearthflame Mask": "화덕",
        "Cornerstone Mask": "주춧돌",
        "Terastal Teal Mask": "테라스탈 벽록",
        "Terastal Wellspring Mask": "테라스탈 우물",
        "Terastal Hearthflame Mask": "테라스탈 화덕",
        "Terastal Cornerstone Mask": "테라스탈 주춧돌",
        "Blood Moon": "붉은달",
        "Ice Rider": "백마탄",
        "Shadow Rider": "흑마탄",
        "Crowned Sword": "검의왕",
        "Crowned Shield": "방패의왕",
        "Rapid Strike": "연격",
        "Heat": "히트", "Wash": "워시", "Frost": "프로스트",
        "Fan": "스핀", "Mow": "커트",
        "Sandy Cloak": "모래땅", "Trash Cloak": "슈레땅", "Plant Cloak": "초목",
        "Sunshine": "선샤인", "Rainy": "레이니", "Snowy": "스노우",
        "Attack": "어택", "Defense": "디펜스", "Speed": "스피드",
        "Sky": "스카이", "Sky Forme": "스카이",
        "Ultra": "울트라",
        "Eternamax": "무한",
        "Dusk Mane": "황혼의갈기",
        "Dawn Wings": "새벽의날개",
        "Complete": "퍼펙트",
    }

    poke_count = 0
    form_count = 0
    for sym, val in species_raw.items():
        attrs = val.attributes
        game_key = _sym_str(attrs["@id"])
        species_key = _sym_str(attrs.get("@species", attrs["@id"]))
        name_en = _to_str(attrs["@real_name"])
        form_number = attrs.get("@form", 0)
        form_name_en = _to_str(attrs.get("@real_form_name"))

        # 한국어 이름 결정
        name_ko = _to_str(poke_ko_names.get(name_en, name_en))

        # 폼 이름 한국어 변환 및 display_name 생성
        form_name_ko = None
        if form_name_en and form_number > 0:
            # FORM_NAME_KO에서 찾기
            form_name_ko = FORM_NAME_KO.get(form_name_en)
            if not form_name_ko:
                # "Mega Venusaur" → "메가" 추출
                for en_key, ko_val in FORM_NAME_KO.items():
                    if en_key in form_name_en:
                        form_name_ko = ko_val
                        break
            if not form_name_ko:
                form_name_ko = form_name_en  # 매핑 없으면 영문 그대로

        if form_name_ko:
            display_name = f"{name_ko}({form_name_ko})"
            is_default = 0
            form_count += 1
        else:
            display_name = name_ko
            is_default = 1

        # 타입
        type_list = attrs["@types"]
        type1_sym = _sym_str(type_list[0])
        type1_id = type_sym_to_id.get(type1_sym)
        type2_id = None
        if len(type_list) > 1:
            type2_sym = _sym_str(type_list[1])
            type2_id = type_sym_to_id.get(type2_sym)

        if type1_id is None:
            continue

        # 종족값
        base_stats = attrs["@base_stats"]
        hp = base_stats.get(_sym("HP"), 0)
        atk = base_stats.get(_sym("ATTACK"), 0)
        defense = base_stats.get(_sym("DEFENSE"), 0)
        sp_atk = base_stats.get(_sym("SPECIAL_ATTACK"), 0)
        sp_def = base_stats.get(_sym("SPECIAL_DEFENSE"), 0)
        speed = base_stats.get(_sym("SPEED"), 0)

        c.execute(
            """INSERT OR REPLACE INTO pokemon
               (game_key, species_key, name_en, name_ko, display_name, form_name,
                form_number, type1_id, type2_id, hp, attack, defense,
                sp_attack, sp_defense, speed, is_default)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (game_key, species_key, name_en, name_ko, display_name, form_name_ko,
             form_number, type1_id, type2_id, hp, atk, defense, sp_atk, sp_def,
             speed, is_default),
        )
        poke_count += 1

    conn.commit()

    print(f"  → {poke_count}마리 완료 (리전/폼: {form_count}개 포함)\n")

    # 최종 요약
    type_count = c.execute("SELECT COUNT(*) FROM types").fetchone()[0]
    eff_count = c.execute("SELECT COUNT(*) FROM type_efficacy").fetchone()[0]
    move_count = c.execute("SELECT COUNT(*) FROM moves").fetchone()[0]

    print("=== 임포트 완료 ===")
    print(f"  타입: {type_count}개")
    print(f"  상성 데이터: {eff_count}건")
    print(f"  기술: {move_count}개")
    print(f"  포켓몬: {poke_count}마리")
    print(f"  DB: {db_path}")

    conn.close()
    return True


# ─── 세이브 파일 파싱 (파티 동기화) ───


def read_save_party(save_path):
    """
    세이브 파일에서 현재 파티 포켓몬 정보를 읽어옵니다.

    Returns:
        list of dict: 파티 포켓몬 정보
        [{"species": "GARCHOMP", "form": 0, "level": 75, "moves": [...], ...}, ...]
    """
    # 세이브 파일은 커스텀 파서 사용 (순환 참조 문제 회피)
    save_data = load_ruby_marshal(save_path, use_custom=True)

    # 세이브 데이터는 Hash: {:player => Player, :bag => ..., ...}
    # 커스텀 파서에서는 키가 문자열 "player"
    player = None
    if isinstance(save_data, dict):
        player = save_data.get("player")
    if player is None and hasattr(save_data, 'get'):
        player = save_data.get(_sym("player"))
    if player is None:
        raise ValueError("세이브 파일에서 플레이어 데이터를 찾을 수 없습니다.")

    # 속성 접근 (양쪽 파서 호환)
    def _get_attr(obj, key):
        if obj is None:
            return None
        if isinstance(obj, dict):
            return obj.get(key) or obj.get(f"@{key}")
        if hasattr(obj, "attributes"):
            return obj.attributes.get(f"@{key}") or obj.attributes.get(key)
        return None

    party = _get_attr(player, "party") or []
    player_name = _to_str(_get_attr(player, "name")) or "???"

    result = []
    for poke in party:
        if poke is None:
            continue

        species_raw = _get_attr(poke, "species")
        species_sym = _sym_str(species_raw) if species_raw else "???"
        form = _get_attr(poke, "forced_form") or _get_attr(poke, "form") or 0

        # 게임 키 결정
        if form and form > 0:
            game_key = f"{species_sym}_{form}"
        else:
            game_key = species_sym

        # 기술 목록
        moves_raw = _get_attr(poke, "moves") or []
        moves = []
        for m in moves_raw:
            if m is None:
                continue
            move_id = _get_attr(m, "id")
            if move_id:
                moves.append(_sym_str(move_id))

        # 레벨
        level = _get_attr(poke, "level") or 50

        # 능력
        ability = _get_attr(poke, "ability")
        ability_str = _sym_str(ability) if ability else None

        # 지닌 물건
        item = _get_attr(poke, "item")
        item_str = _sym_str(item) if item else None

        # 성격
        nature = _get_attr(poke, "nature")
        nature_str = _sym_str(nature) if nature else None

        # HP
        hp = _get_attr(poke, "hp") or 0
        totalhp = _get_attr(poke, "totalhp") or 0

        # 개체값/노력치
        iv = {}
        ev = {}
        raw_iv = _get_attr(poke, "iv") or {}
        raw_ev = _get_attr(poke, "ev") or {}
        stat_names = ["HP", "ATTACK", "DEFENSE", "SPECIAL_ATTACK", "SPECIAL_DEFENSE", "SPEED"]
        for stat_name in stat_names:
            # dict 키가 Symbol일 수도, 문자열일 수도 있음
            iv_val = raw_iv.get(stat_name, 0) if isinstance(raw_iv, dict) else 0
            ev_val = raw_ev.get(stat_name, 0) if isinstance(raw_ev, dict) else 0
            iv[stat_name] = iv_val
            ev[stat_name] = ev_val

        result.append({
            "species": species_sym,
            "form": form,
            "game_key": game_key,
            "level": level,
            "moves": moves,
            "ability": ability_str,
            "item": item_str,
            "nature": nature_str,
            "hp": hp,
            "totalhp": totalhp,
            "iv": iv,
            "ev": ev,
        })

    return player_name, result


def sync_party_to_team(save_path, db_path=None):
    """
    세이브 파일의 파티를 읽어서 my_team.json에 동기화합니다.

    Returns:
        (player_name, list of matched pokemon dicts)
    """
    if db_path is None:
        db_path = DB_PATH

    player_name, party = read_save_party(save_path)
    conn = sqlite3.connect(db_path)

    team_ids = []
    matched = []

    for poke in party:
        # game_key로 DB에서 포켓몬 찾기
        row = conn.execute(
            "SELECT id, display_name, game_key FROM pokemon WHERE game_key = ?",
            (poke["game_key"],),
        ).fetchone()

        if not row:
            # 폼 없이 기본 종으로 재시도
            row = conn.execute(
                "SELECT id, display_name, game_key FROM pokemon WHERE game_key = ?",
                (poke["species"],),
            ).fetchone()

        if row:
            team_ids.append(row[0])
            poke["db_id"] = row[0]
            poke["display_name"] = row[1]
            matched.append(poke)
        else:
            print(f"  경고: {poke['game_key']}을(를) DB에서 찾을 수 없습니다.")
            poke["display_name"] = poke["species"]
            matched.append(poke)

    conn.close()

    # my_team.json 저장
    from db import save_team
    save_team(team_ids)

    return player_name, matched


# ─── CLI 실행 ───

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "import":
        # 게임 데이터 임포트
        data_dir = sys.argv[2] if len(sys.argv) > 2 else find_game_data_dir()
        if not data_dir:
            print("게임 Data 폴더를 찾을 수 없습니다.")
            print("사용법: python game_sync.py import [게임Data폴더경로]")
            sys.exit(1)
        print(f"게임 데이터 경로: {data_dir}\n")
        import_game_data(data_dir)

    elif len(sys.argv) > 1 and sys.argv[1] == "party":
        # 파티 동기화
        save_path = sys.argv[2] if len(sys.argv) > 2 else find_save_file()
        if not save_path:
            print("세이브 파일을 찾을 수 없습니다.")
            print("사용법: python game_sync.py party [세이브파일경로]")
            sys.exit(1)
        print(f"세이브 파일: {save_path}\n")
        player_name, party = sync_party_to_team(save_path)
        print(f"\n플레이어: {player_name}")
        print(f"파티 ({len(party)}마리):")
        for p in party:
            print(f"  Lv.{p['level']} {p['display_name']} | 기술: {', '.join(p['moves'])}")

    else:
        print("포켓몬 게임 데이터 동기화 도구")
        print()
        print("사용법:")
        print("  python game_sync.py import [Data폴더]   게임 데이터를 DB로 임포트")
        print("  python game_sync.py party [세이브파일]   세이브 파티를 팀에 동기화")
