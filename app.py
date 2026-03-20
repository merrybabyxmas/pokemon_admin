"""
포켓몬 실전 상성 분석기 - PyQt6 데스크톱 앱
리전 폼 + 테라스탈 타입 + 게임 세이브 동기화 지원
"""

import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QCompleter,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from db import (
    get_all_pokemon_names,
    get_all_types,
    get_move_by_symbol,
    get_moves_for_pokemon,
    get_pokemon_by_id,
    get_type_name,
    load_team,
    save_team,
    search_pokemon_by_name,
)
from matchup import recommend_counters

# 다크 테마 스타일시트
DARK_STYLE = """
QMainWindow {
    background-color: #1a1a2e;
}
QWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
    font-size: 13px;
}
QLabel {
    color: #e0e0e0;
    border: none;
}
QLabel#title {
    font-size: 18px;
    font-weight: bold;
    color: #ff6b6b;
    padding: 5px;
}
QLabel#sectionTitle {
    font-size: 14px;
    font-weight: bold;
    color: #4ecdc4;
    padding: 3px;
}
QLineEdit {
    background-color: #16213e;
    border: 2px solid #0f3460;
    border-radius: 8px;
    padding: 8px 12px;
    color: #e0e0e0;
    font-size: 14px;
}
QLineEdit:focus {
    border-color: #4ecdc4;
}
QListWidget {
    background-color: #16213e;
    border: 1px solid #0f3460;
    border-radius: 8px;
    padding: 4px;
    outline: none;
}
QListWidget::item {
    padding: 6px 8px;
    border-radius: 4px;
}
QListWidget::item:selected {
    background-color: #0f3460;
    color: #4ecdc4;
}
QListWidget::item:hover {
    background-color: #1a1a4e;
}
QPushButton {
    background-color: #0f3460;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    color: #e0e0e0;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #4ecdc4;
    color: #1a1a2e;
}
QPushButton#removeBtn {
    background-color: #c0392b;
}
QPushButton#removeBtn:hover {
    background-color: #e74c3c;
    color: white;
}
QPushButton#syncBtn {
    background-color: #2d3436;
    border: 1px solid #ffa502;
    color: #ffa502;
}
QPushButton#syncBtn:hover {
    background-color: #ffa502;
    color: #1a1a2e;
}
QFrame#separator {
    background-color: #0f3460;
}
QComboBox {
    background-color: #16213e;
    border: 2px solid #0f3460;
    border-radius: 6px;
    padding: 6px 10px;
    color: #e0e0e0;
    font-size: 13px;
}
QComboBox:focus {
    border-color: #4ecdc4;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #4ecdc4;
    margin-right: 8px;
}
QComboBox QAbstractItemView {
    background-color: #16213e;
    border: 2px solid #4ecdc4;
    color: #e0e0e0;
    selection-background-color: #0f3460;
    selection-color: #4ecdc4;
}
/* 자동완성 드롭다운 */
QListView {
    background-color: #16213e;
    border: 2px solid #4ecdc4;
    border-radius: 4px;
    color: #e0e0e0;
    font-size: 13px;
}
QListView::item:selected {
    background-color: #0f3460;
    color: #4ecdc4;
}
"""

TYPE_COLORS = {
    "노말": "#A8A878", "불꽃": "#F08030", "물": "#6890F0", "풀": "#78C850",
    "전기": "#F8D030", "얼음": "#98D8D8", "격투": "#C03028", "독": "#A040A0",
    "땅": "#E0C068", "비행": "#A890F0", "에스퍼": "#F85888", "벌레": "#A8B820",
    "바위": "#B8A038", "고스트": "#705898", "드래곤": "#7038F8", "악": "#705848",
    "강철": "#B8B8D0", "페어리": "#EE99AC",
}

MOVE_CATEGORY_KO = {0: "물리", 1: "특수", 2: "변화"}


class PokemonCounterApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("포켓몬 실전 상성 분석기")
        self.resize(980, 650)
        self.setMinimumSize(780, 480)

        # 포켓몬 이름 DB 로드
        self.all_pokemon = get_all_pokemon_names()
        self.name_to_id = {p[1]: p[0] for p in self.all_pokemon}
        self.pokemon_names = [p[1] for p in self.all_pokemon]

        # 타입 목록
        self.all_types = get_all_types()
        self.type_ko_to_id = {v["name_ko"]: k for k, v in self.all_types.items()}

        # 내 팀
        self.my_team_ids = load_team()

        # 파티 동기화 시 읽어온 상세 정보 (기술 등)
        self.party_details = {}  # {db_id: {moves: [...], level: ..., ...}}

        self._build_ui()

    def _build_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        root_layout = QVBoxLayout(main_widget)
        root_layout.setContentsMargins(12, 8, 12, 8)

        # 타이틀
        title = QLabel("포켓몬 실전 상성 분석기")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(title)

        body_layout = QHBoxLayout()
        root_layout.addLayout(body_layout, stretch=1)

        # ─── 좌측: 내 팀 ───
        left = QVBoxLayout()
        left.setSpacing(6)

        lbl = QLabel("내 포켓몬 파티")
        lbl.setObjectName("sectionTitle")
        left.addWidget(lbl)

        # 세이브 동기화 버튼
        sync_btn = QPushButton("세이브 파일에서 파티 불러오기")
        sync_btn.setObjectName("syncBtn")
        sync_btn.clicked.connect(self._sync_from_save)
        left.addWidget(sync_btn)

        # 수동 추가용 검색창
        self.team_input = QLineEdit()
        self.team_input.setPlaceholderText("수동 추가: 포켓몬 이름...")
        team_completer = QCompleter(self.pokemon_names)
        team_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        team_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.team_input.setCompleter(team_completer)
        self.team_input.returnPressed.connect(self._add_to_team)
        left.addWidget(self.team_input)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("추가")
        add_btn.clicked.connect(self._add_to_team)
        remove_btn = QPushButton("제거")
        remove_btn.setObjectName("removeBtn")
        remove_btn.clicked.connect(self._remove_from_team)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(remove_btn)
        left.addLayout(btn_row)

        self.team_list = QListWidget()
        left.addWidget(self.team_list, stretch=1)

        # 구분선
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(2)

        # ─── 우측: 검색 & 결과 ───
        right = QVBoxLayout()
        right.setSpacing(6)

        lbl2 = QLabel("상대 포켓몬 검색")
        lbl2.setObjectName("sectionTitle")
        right.addWidget(lbl2)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("상대 포켓몬 이름을 입력하세요...")
        search_completer = QCompleter(self.pokemon_names)
        search_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        search_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.search_input.setCompleter(search_completer)
        self.search_input.returnPressed.connect(self._analyze)
        search_btn = QPushButton("분석")
        search_btn.clicked.connect(self._analyze)
        search_row.addWidget(self.search_input, stretch=1)
        search_row.addWidget(search_btn)
        right.addLayout(search_row)

        # 테라스탈
        tera_row = QHBoxLayout()
        tera_label = QLabel("테라스탈:")
        tera_label.setFixedWidth(65)
        self.tera_combo = QComboBox()
        self.tera_combo.addItem("없음 (원래 타입)")
        for type_id in sorted(self.all_types.keys()):
            info = self.all_types[type_id]
            self.tera_combo.addItem(info["name_ko"])
        self.tera_combo.currentIndexChanged.connect(self._on_tera_changed)
        tera_row.addWidget(tera_label)
        tera_row.addWidget(self.tera_combo, stretch=1)
        right.addLayout(tera_row)

        # 상대 정보
        self.enemy_info = QLabel("")
        self.enemy_info.setWordWrap(True)
        self.enemy_info.setStyleSheet(
            "background-color: #16213e; border-radius: 8px; padding: 10px;"
        )
        self.enemy_info.setMinimumHeight(50)
        right.addWidget(self.enemy_info)

        result_lbl = QLabel("추천 카운터")
        result_lbl.setObjectName("sectionTitle")
        right.addWidget(result_lbl)

        self.result_list = QListWidget()
        right.addWidget(self.result_list, stretch=1)

        body_layout.addLayout(left, 1)
        body_layout.addWidget(sep)
        body_layout.addLayout(right, 2)

        self._refresh_team_list()

    # ─── 세이브 동기화 ───

    def _sync_from_save(self):
        """세이브 파일 선택 → 파티 자동 동기화"""
        try:
            from game_sync import find_save_file, sync_party_to_team
        except ImportError:
            QMessageBox.warning(self, "오류", "game_sync 모듈을 찾을 수 없습니다.\nrubymarshal 패키지를 설치해 주세요: pip install rubymarshal")
            return

        # 자동 탐색 시도
        save_path = find_save_file()

        if not save_path:
            save_path, _ = QFileDialog.getOpenFileName(
                self,
                "세이브 파일 선택",
                "",
                "세이브 파일 (*.rxdata *.dat);;All Files (*.*)",
            )

        if not save_path:
            return

        try:
            player_name, party = sync_party_to_team(save_path)
        except Exception as e:
            QMessageBox.critical(self, "동기화 실패", f"세이브 파일을 읽을 수 없습니다:\n{e}")
            return

        # 팀 ID 및 상세 정보 업데이트
        self.my_team_ids = load_team()
        self.party_details.clear()
        for p in party:
            if "db_id" in p:
                self.party_details[p["db_id"]] = p

        self._refresh_team_list()

        # 동기화 결과 알림
        party_names = [p["display_name"] for p in party]
        msg = f"플레이어: {player_name}\n파티 ({len(party)}마리):\n"
        for p in party:
            moves_str = ""
            if p.get("moves"):
                move_data = get_moves_for_pokemon(p["moves"])
                move_names = [m["name_ko"] for m in move_data]
                moves_str = " | " + ", ".join(move_names)
            msg += f"  Lv.{p['level']} {p['display_name']}{moves_str}\n"

        QMessageBox.information(self, "파티 동기화 완료", msg)

    # ─── 팀 관리 ───

    def _add_to_team(self):
        name = self.team_input.text().strip()
        if not name:
            return
        if name not in self.name_to_id:
            QMessageBox.warning(self, "알 수 없는 포켓몬", f"'{name}'을(를) 도감에서 찾을 수 없습니다.")
            return
        pid = self.name_to_id[name]
        if pid in self.my_team_ids:
            QMessageBox.information(self, "중복", f"'{name}'은(는) 이미 팀에 있습니다.")
            return
        self.my_team_ids.append(pid)
        save_team(self.my_team_ids)
        self.team_input.clear()
        self._refresh_team_list()

    def _remove_from_team(self):
        row = self.team_list.currentRow()
        if row < 0:
            return
        removed_id = self.my_team_ids.pop(row)
        self.party_details.pop(removed_id, None)
        save_team(self.my_team_ids)
        self._refresh_team_list()

    def _refresh_team_list(self):
        self.team_list.clear()
        for pid in self.my_team_ids:
            poke = get_pokemon_by_id(pid)
            if not poke:
                continue
            type1 = get_type_name(poke["type1_id"])
            type2 = get_type_name(poke["type2_id"]) if poke["type2_id"] else None
            type_str = f"{type1}/{type2}" if type2 else type1

            # 동기화된 파티 정보가 있으면 레벨/기술 표시
            detail = self.party_details.get(pid)
            if detail:
                level_str = f"Lv.{detail['level']}"
                move_data = get_moves_for_pokemon(detail.get("moves", []))
                move_names = [m["name_ko"] for m in move_data]
                moves_str = ", ".join(move_names) if move_names else ""
                text = f"{level_str} {poke['display_name']} [{type_str}]"
                if moves_str:
                    text += f"\n    {moves_str}"
            else:
                text = f"{poke['display_name']}  [{type_str}]"

            self.team_list.addItem(text)

    # ─── 테라스탈 ───

    def _get_tera_type_id(self):
        idx = self.tera_combo.currentIndex()
        if idx == 0:
            return None
        type_name_ko = self.tera_combo.currentText()
        return self.type_ko_to_id.get(type_name_ko)

    def _on_tera_changed(self):
        if self.search_input.text().strip():
            self._analyze()

    # ─── 상성 분석 ───

    def _analyze(self):
        enemy_name = self.search_input.text().strip()
        if not enemy_name:
            return

        self.result_list.clear()
        self.enemy_info.setText("분석 중...")

        tera_type_id = self._get_tera_type_id()
        enemy, results = recommend_counters(enemy_name, self.my_team_ids, tera_type_id)

        if enemy is None:
            self.enemy_info.setText(f"'{enemy_name}'을(를) 도감에서 찾을 수 없습니다.")
            return

        # 상대 정보 표시
        type1 = get_type_name(enemy["type1_id"])
        type2 = get_type_name(enemy["type2_id"]) if enemy["type2_id"] else None

        color1 = TYPE_COLORS.get(type1, "#888")
        type_html = f'<span style="color:{color1}; font-weight:bold">{type1}</span>'
        if type2:
            color2 = TYPE_COLORS.get(type2, "#888")
            type_html += f' / <span style="color:{color2}; font-weight:bold">{type2}</span>'

        tera_html = ""
        if tera_type_id is not None:
            tera_name = get_type_name(tera_type_id)
            tera_color = TYPE_COLORS.get(tera_name, "#888")
            tera_html = (
                f'<br>테라스탈: <span style="color:{tera_color}; font-weight:bold">'
                f'{tera_name}</span> (방어 타입 변경됨)'
            )

        form_html = ""
        if enemy.get("form_name"):
            form_html = f' <span style="color:#ffa502">[{enemy["form_name"]} 폼]</span>'

        bst = (
            enemy["hp"] + enemy["attack"] + enemy["defense"]
            + enemy["sp_attack"] + enemy["sp_defense"] + enemy["speed"]
        )
        info_html = (
            f'<b style="font-size:15px; color:#ff6b6b">'
            f'{enemy["display_name"]}</b>'
            f'{form_html}'
            f'<span style="color:#888"> ({enemy["name_en"]})</span><br>'
            f'타입: {type_html}{tera_html}<br>'
            f'종족값 합계: <b>{bst}</b> '
            f'(HP {enemy["hp"]} / 공{enemy["attack"]} / 방{enemy["defense"]} / '
            f'특공{enemy["sp_attack"]} / 특방{enemy["sp_defense"]} / 스피드{enemy["speed"]})'
        )
        self.enemy_info.setText(info_html)

        if not results:
            self.result_list.addItem("팀에 포켓몬을 먼저 추가해 주세요!")
            return

        for r in results:
            poke = r["pokemon"]
            p_type1 = get_type_name(poke["type1_id"])
            p_type2 = get_type_name(poke["type2_id"]) if poke["type2_id"] else None
            p_type_str = f"{p_type1}/{p_type2}" if p_type2 else p_type1

            score = r["total_score"]
            if score >= 6.0:
                grade, grade_color = "S", "#ff6b6b"
            elif score >= 4.5:
                grade, grade_color = "A", "#ffa502"
            elif score >= 3.5:
                grade, grade_color = "B", "#4ecdc4"
            elif score >= 2.5:
                grade, grade_color = "C", "#a0a0a0"
            else:
                grade, grade_color = "D", "#555"

            atk_text = f"공격배율 x{r['atk_multiplier']:.1f}"
            def_text = f"피격배율 x{r['def_multiplier']:.1f}"

            # 동기화된 파티면 레벨 표시
            detail = self.party_details.get(poke["id"])
            level_prefix = f"Lv.{detail['level']} " if detail else ""

            line1 = f"[{grade}] {level_prefix}{poke['display_name']} [{p_type_str}]  —  {atk_text} | {def_text}"
            line2 = "    " + " / ".join(r["reasons"])

            item = QListWidgetItem(f"{line1}\n{line2}")
            item.setForeground(QColor(grade_color))
            self.result_list.addItem(item)


def main():
    db_path = os.path.join(os.path.dirname(__file__), "data", "pokemon.db")
    if not os.path.exists(db_path):
        print("데이터베이스가 없습니다!")
        print("  게임 데이터: python game_sync.py import [Data폴더]")
        print("  PokéAPI:     python fetch_data.py")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLE)

    window = PokemonCounterApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
