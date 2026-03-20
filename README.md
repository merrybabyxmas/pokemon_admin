# 포켓몬 실전 상성 분석기

내 포켓몬 파티를 등록하고, 상대 포켓몬을 검색하면 최적의 카운터를 추천해주는 로컬 데스크톱 앱.

리전 폼 + 메가진화 + 테라스탈 타입 + **게임 세이브 자동 동기화**까지 지원합니다.

---

## 요구사항

- Python 3.10 이상

---

## 설치 및 실행

### 1. 파일 다운로드

이 폴더 전체를 원하는 위치에 복사합니다.

```
pokemon_admin/
├── app.py           # 메인 앱 (PyQt6 GUI)
├── db.py            # DB 접근 모듈
├── matchup.py       # 상성 계산 엔진
├── game_sync.py     # 게임 데이터 동기화 모듈
├── fetch_data.py    # PokéAPI 데이터 수집 (게임 없을 때)
└── data/            ← 빈 폴더 (없으면 자동 생성됨)
```

### 2. 파이썬 패키지 설치

```bash
cd pokemon_admin
pip install PyQt6 requests rubymarshal
```

> 가상환경을 쓰고 싶다면:
> ```bash
> python -m venv venv
> source venv/bin/activate   # Windows: venv\Scripts\activate
> pip install PyQt6 requests rubymarshal
> ```

### 3. 데이터 준비 (둘 중 하나 선택)

#### 방법 A: 게임 데이터에서 임포트 (추천)

Pokemon Another Red 게임의 Data 폴더에서 직접 읽어옵니다.
게임 고유의 포켓몬, 기술, 타입 데이터를 그대로 사용하므로 가장 정확합니다.

```bash
python game_sync.py import "게임폴더/Data"
```

예시:
```bash
python game_sync.py import "C:\Games\Pokemon Another Red\Data"
```

게임 파일이 `pokemon_raw/extracted/` 아래에 있으면 자동으로 찾습니다:
```bash
python game_sync.py import
```

#### 방법 B: PokéAPI에서 수집 (게임 없을 때)

```bash
python fetch_data.py
```

- 인터넷 연결 필요, 소요 시간 약 15~30분

### 4. 앱 실행

```bash
python app.py
```

---

## 사용법

### 게임 세이브 파티 동기화
1. 좌측 패널의 **"세이브 파일에서 파티 불러오기"** 버튼 클릭
2. 세이브 파일 (Game.rxdata) 선택
3. 게임 내 현재 파티가 자동으로 팀에 등록됨
4. 각 포켓몬의 레벨, 배운 기술까지 함께 표시

> Windows에서는 보통 `%APPDATA%\Pokemon Another Red\Game.rxdata` 경로에 세이브가 저장됩니다.

> CLI로도 동기화 가능:
> ```bash
> python game_sync.py party "세이브파일경로"
> ```

### 수동 팀 등록
1. 왼쪽 패널의 검색창에 포켓몬 이름 입력 (자동완성 지원)
2. Enter 또는 "추가" 버튼 클릭
3. 제거하려면 목록에서 선택 후 "제거" 클릭
4. 팀 정보는 `data/my_team.json`에 자동 저장됨

### 리전 폼 검색
리전 폼은 `이름(리전명)` 형식으로 검색합니다.
- `나인테일` → 일반 나인테일 (불꽃)
- `나인테일(알로라)` → 알로라 나인테일 (얼음/페어리)
- `오거폰(화덕)` → 화덕의 가면 오거폰 (풀/불꽃)
- 자동완성에서 `나인` 까지만 쳐도 모든 폼이 드롭다운으로 표시됩니다

### 상성 분석
1. 오른쪽 패널의 검색창에 상대 포켓몬 이름 입력
2. Enter 또는 "분석" 버튼 클릭
3. 내 팀에서 상성이 좋은 순서대로 S~D 등급으로 추천

### 테라스탈 타입
검색창 아래 드롭다운에서 테라스탈 타입을 선택하면:
- 상대의 **방어 타입**이 선택한 테라 타입 단일로 변경됩니다
- 상대의 **공격 자속**은 원래 타입 + 테라 타입 모두 유지됩니다
- 테라 타입을 바꾸면 자동으로 재분석됩니다

### 등급 기준
| 등급 | 의미 |
|------|------|
| S | 4배 약점을 찌르거나 상대 공격을 무효화 |
| A | 2배 약점을 찌르면서 방어도 유리 |
| B | 약점을 찌르거나 방어가 유리한 쪽 |
| C | 등배 매치업 |
| D | 불리한 매치업 |

---

## 문제 해결

**`ModuleNotFoundError: No module named 'PyQt6'`**
→ `pip install PyQt6` 재실행

**`ModuleNotFoundError: No module named 'rubymarshal'`**
→ `pip install rubymarshal` (게임 동기화 기능에 필요)

**`데이터베이스가 없습니다!`**
→ `python game_sync.py import` 또는 `python fetch_data.py` 실행

**`sqlite3.OperationalError: no such column`**
→ DB 스키마가 변경되었습니다. `data/pokemon.db`를 삭제하고 데이터를 다시 수집하세요.

**세이브 파일을 찾을 수 없음**
→ 파일 선택 다이얼로그에서 직접 Game.rxdata 파일을 지정해 주세요.
