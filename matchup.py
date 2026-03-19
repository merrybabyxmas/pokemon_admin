"""
상성 계산 엔진.
상대 포켓몬에 대해 내 팀에서 최적의 카운터를 찾아 점수화합니다.
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
    # 배율은 곱셈: (200 * 200) / 100 = 400 (4배)
    return (factor1 * factor2) / 100


def calc_defense_multiplier(efficacy, atk_type_id, def_type1_id, def_type2_id):
    """상대의 공격 타입 하나가 내 포켓몬(1~2타입)에 주는 총 배율"""
    return calc_attack_multiplier(efficacy, atk_type_id, def_type1_id, def_type2_id)


def evaluate_matchup(my_pokemon, enemy_pokemon, efficacy):
    """
    내 포켓몬 vs 상대 포켓몬의 상성 점수를 계산합니다.

    공격 점수: 내 자속 타입이 상대에게 주는 최대 배율
    방어 점수: 상대 자속 타입이 나에게 주는 배율의 역수
    총합 점수가 높을수록 유리한 매치업.

    Returns:
        dict with score, atk_multiplier, def_multiplier, reason text
    """
    my_types = [my_pokemon["type1_id"]]
    if my_pokemon["type2_id"] is not None:
        my_types.append(my_pokemon["type2_id"])

    enemy_types = [enemy_pokemon["type1_id"]]
    if enemy_pokemon["type2_id"] is not None:
        enemy_types.append(enemy_pokemon["type2_id"])

    # 공격 점수: 내 자속 타입들 중 상대에 가장 효과적인 배율
    best_atk = 100
    best_atk_type = my_types[0]
    for my_type in my_types:
        mult = calc_attack_multiplier(
            efficacy, my_type, enemy_pokemon["type1_id"], enemy_pokemon["type2_id"]
        )
        if mult > best_atk:
            best_atk = mult
            best_atk_type = my_type

    # 방어 점수: 상대 자속 타입들 중 나에게 가장 위협적인 배율
    worst_def = 100
    worst_def_type = enemy_types[0]
    for enemy_type in enemy_types:
        mult = calc_defense_multiplier(
            efficacy, enemy_type, my_pokemon["type1_id"], my_pokemon["type2_id"]
        )
        if mult > worst_def:
            worst_def = mult
            worst_def_type = enemy_type

    # 점수 계산
    # 공격 배율이 높을수록 좋고, 방어에서 받는 배율이 낮을수록 좋음
    # 공격 점수: best_atk / 100 (2.0이면 2배)
    # 방어 점수: 100 / worst_def (0.5이면 반감 = 좋음)
    atk_score = best_atk / 100
    def_score = 100 / worst_def if worst_def > 0 else 10  # 무효 = 매우 유리

    # 스피드 보너스 (미세 조정용)
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


def recommend_counters(enemy_name_ko, my_team_ids):
    """
    상대 포켓몬 이름(한국어)과 내 팀 ID 리스트를 받아
    상성 점수가 높은 순으로 추천 결과를 반환합니다.

    Returns:
        (enemy_pokemon_dict, list of matchup_results) or (None, error_msg)
    """
    enemy = search_pokemon_by_name(enemy_name_ko)
    if not enemy:
        return None, f"'{enemy_name_ko}'을(를) 찾을 수 없습니다."

    if not my_team_ids:
        return enemy, []

    efficacy = get_type_efficacy()
    results = []

    for pid in my_team_ids:
        my_poke = get_pokemon_by_id(pid)
        if not my_poke:
            continue
        result = evaluate_matchup(my_poke, enemy, efficacy)
        results.append(result)

    results.sort(key=lambda x: x["total_score"], reverse=True)
    return enemy, results
