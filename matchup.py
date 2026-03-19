"""
상성 계산 엔진.
상대 포켓몬에 대해 내 팀에서 최적의 카운터를 찾아 점수화합니다.
테라스탈 타입 오버라이드를 지원합니다.
"""

from db import (
    get_damage_factor,
    get_pokemon_by_id,
    get_type_efficacy,
    get_type_name,
    search_pokemon_by_name,
)


def calc_attack_multiplier(efficacy, atk_type_id, def_type1_id, def_type2_id):
    """공격 타입 하나가 상대 포켓몬(1~2타입)에 주는 총 배율"""
    factor1 = get_damage_factor(efficacy, atk_type_id, def_type1_id)
    if def_type2_id is not None:
        factor2 = get_damage_factor(efficacy, atk_type_id, def_type2_id)
    else:
        factor2 = 100
    return (factor1 * factor2) / 100


def evaluate_matchup(my_pokemon, enemy_pokemon, efficacy, tera_type_id=None):
    """
    내 포켓몬 vs 상대 포켓몬의 상성 점수를 계산합니다.

    테라스탈 시: 상대의 방어 타입이 tera_type_id 단일 타입으로 변경됩니다.
    (원래 타입 2개가 사라지고 테라 타입 1개만 남음)

    Returns:
        dict with score, atk_multiplier, def_multiplier, reason text
    """
    my_types = [my_pokemon["type1_id"]]
    if my_pokemon["type2_id"] is not None:
        my_types.append(my_pokemon["type2_id"])

    # 테라스탈 적용: 상대의 방어 타입 결정
    if tera_type_id is not None:
        enemy_def_type1 = tera_type_id
        enemy_def_type2 = None
    else:
        enemy_def_type1 = enemy_pokemon["type1_id"]
        enemy_def_type2 = enemy_pokemon["type2_id"]

    # 상대의 공격 타입 (자속)은 테라스탈과 무관하게 원래 타입 유지
    # (실전에서는 테라 타입 자속도 받지만, 원래 자속도 유지됨)
    enemy_atk_types = [enemy_pokemon["type1_id"]]
    if enemy_pokemon["type2_id"] is not None:
        enemy_atk_types.append(enemy_pokemon["type2_id"])
    if tera_type_id is not None and tera_type_id not in enemy_atk_types:
        enemy_atk_types.append(tera_type_id)

    # 공격 점수: 내 자속 타입들 중 상대 (테라 적용된) 방어 타입에 가장 효과적인 배율
    best_atk = 100
    best_atk_type = my_types[0]
    for my_type in my_types:
        mult = calc_attack_multiplier(efficacy, my_type, enemy_def_type1, enemy_def_type2)
        if mult > best_atk:
            best_atk = mult
            best_atk_type = my_type

    # 방어 점수: 상대 자속 타입들 중 나에게 가장 위협적인 배율
    worst_def = 100
    worst_def_type = enemy_atk_types[0]
    for enemy_type in enemy_atk_types:
        mult = calc_attack_multiplier(
            efficacy, enemy_type, my_pokemon["type1_id"], my_pokemon["type2_id"]
        )
        if mult > worst_def:
            worst_def = mult
            worst_def_type = enemy_type

    # 점수 계산
    atk_score = best_atk / 100
    def_score = 100 / worst_def if worst_def > 0 else 10

    speed_bonus = my_pokemon["speed"] / 1000
    total_score = (atk_score * 2) + (def_score * 1.5) + speed_bonus

    # 이유 텍스트 생성
    reasons = []

    atk_type_name = get_type_name(best_atk_type)
    if best_atk >= 400:
        reasons.append(f"자속 {atk_type_name} 타입으로 4배 약점!")
    elif best_atk >= 200:
        reasons.append(f"자속 {atk_type_name} 타입으로 2배 약점")
    elif best_atk >= 100:
        reasons.append(f"자속 {atk_type_name} 타입 등배")
    else:
        reasons.append(f"자속 공격 반감됨")

    if tera_type_id is not None:
        tera_name = get_type_name(tera_type_id)
        reasons.append(f"테라스탈({tera_name}) 적용")

    def_type_name = get_type_name(worst_def_type)
    if worst_def >= 400:
        reasons.append(f"상대 {def_type_name} 타입에 4배 약점 주의!")
    elif worst_def >= 200:
        reasons.append(f"상대 {def_type_name} 타입에 2배 약점")
    elif worst_def <= 0:
        reasons.append(f"상대 {def_type_name} 타입 공격 무효!")
    elif worst_def <= 50:
        reasons.append(f"상대 {def_type_name} 타입 공격 반감")
    else:
        reasons.append(f"상대 공격 등배")

    if my_pokemon["speed"] > enemy_pokemon["speed"]:
        reasons.append(f"스피드 우위 ({my_pokemon['speed']} vs {enemy_pokemon['speed']})")

    return {
        "pokemon": my_pokemon,
        "total_score": total_score,
        "atk_multiplier": best_atk / 100,
        "def_multiplier": worst_def / 100,
        "best_atk_type": atk_type_name,
        "reasons": reasons,
    }


def recommend_counters(enemy_display_name, my_team_ids, tera_type_id=None):
    """
    상대 포켓몬 display_name과 내 팀 ID 리스트를 받아
    상성 점수가 높은 순으로 추천 결과를 반환합니다.

    tera_type_id가 주어지면 상대가 해당 타입으로 테라스탈한 것으로 계산합니다.

    Returns:
        (enemy_pokemon_dict, list of matchup_results) or (None, error_msg)
    """
    enemy = search_pokemon_by_name(enemy_display_name)
    if not enemy:
        return None, f"'{enemy_display_name}'을(를) 찾을 수 없습니다."

    if not my_team_ids:
        return enemy, []

    efficacy = get_type_efficacy()
    results = []

    for pid in my_team_ids:
        my_poke = get_pokemon_by_id(pid)
        if not my_poke:
            continue
        result = evaluate_matchup(my_poke, enemy, efficacy, tera_type_id)
        results.append(result)

    results.sort(key=lambda x: x["total_score"], reverse=True)
    return enemy, results
