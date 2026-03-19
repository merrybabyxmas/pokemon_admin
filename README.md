# 포켓몬 실전 상성 분석기

내 포켓몬 파티를 등록하고, 상대 포켓몬을 검색하면 최적의 카운터를 추천해주는 로컬 데스크톱 앱.

---

## 요구사항

- Python 3.10 이상

---

## 설치 및 실행

### 1. 파일 다운로드

이 폴더 전체를 원하는 위치에 복사합니다.

```
pokemon_admin/
├── app.py
├── db.py
├── matchup.py
├── fetch_data.py
└── data/          ← 빈 폴더 (없으면 자동 생성됨)
```

### 2. 파이썬 패키지 설치

터미널(명령 프롬프트)을 열고 `pokemon_admin` 폴더로 이동한 뒤 실행:

```bash
cd pokemon_admin
pip install PyQt6 requests
```

> 가상환경을 쓰고 싶다면:
> ```bash
> python -m venv venv
> source venv/bin/activate   # Windows: venv\Scripts\activate
> pip install PyQt6 requests
> ```

### 3. 포켓몬 데이터 수집 (최초 1회)

PokéAPI에서 1025마리 데이터를 받아와 로컬 DB에 저장합니다.

```bash
python fetch_data.py
```

- 인터넷 연결 필요 (이후에는 오프라인 사용 가능)
- 소요 시간: 약 10~20분 (API 응답 속도에 따라 다름)
- 완료되면 `data/pokemon.db` 파일이 생성됩니다

### 4. 앱 실행

```bash
python app.py
```

---

## 사용법

### 내 팀 등록
1. 왼쪽 패널의 검색창에 포켓몬 이름 입력 (자동완성 지원)
2. Enter 또는 "추가" 버튼 클릭
3. 제거하려면 목록에서 선택 후 "제거" 클릭
4. 팀 정보는 `data/my_team.json`에 자동 저장됨

### 상성 분석
1. 오른쪽 패널의 검색창에 상대 포켓몬 이름 입력
2. Enter 또는 "분석" 버튼 클릭
3. 내 팀에서 상성이 좋은 순서대로 S~D 등급으로 추천

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

**`데이터베이스가 없습니다!`**
→ `python fetch_data.py`를 먼저 실행

**fetch_data.py 도중 네트워크 오류**
→ 다시 실행하면 이미 받은 데이터는 건너뛰고 이어서 수집됩니다
