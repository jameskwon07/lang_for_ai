# 토큰화 실험 (2단계)

결론과 해석은 [docs/02-tokens-and-forms.md](../../docs/02-tokens-and-forms.md)에 있다. 이 디렉터리는 재현용이다.

## 재현

```bash
cd experiments/tokenization
pip install -r requirements.txt
python3 fetch_tokenizers.py   # PyPI 패키지에서 토크나이저 7종을 꺼내 .cache/에 저장 (SHA-256 확인)
python3 inventory.py          # 약 70초, results/inventory.*
python3 alignment.py          # 약 30초, results/alignment.*
python3 baseline.py           # 몇 초, results/baseline.*
python3 projection.py         # 약 30초, results/projection.*
```

출력은 `runtime_sec` 필드를 빼면 실행마다 같다.

## 파일

| 파일 | 내용 |
|---|---|
| `toklib.py` | 토크나이저 7종 공통 인터페이스 (`count`, `pieces`, `boundaries`, `is_single_token`) |
| `fetch_tokenizers.py` | 토크나이저 파일을 버전 고정 PyPI 휠에서 받는다 |
| `inventory.py` | 모양·표기별로 1토큰이면서 단어가 아닌 형태가 몇 개인지 |
| `alignment.py` | 표기 방식별 토큰 경계와 형태소 경계의 일치 |
| `baseline.py` | 말뭉치의 일반 영어·전보체 영어·한국어·JSON 토큰 수 |
| `projection.py` | 1단계 초안 문법의 형태소 분석을 실제 문자열로 바꿔 잰 토큰 수 |
| `pilot_segmentation.py` | 표기 방식별 Claude 읽기·쓰기 파일럿 자료 생성과 채점 |
| `corpus/ai_messages.json` | AI 에이전트 간 메시지 40개 (en, en_terse, ko, json) |
| `corpus/gloss_{1,2}.json` | 두 추정자가 독립적으로 단 형태소 분석 |
| `results/` | 각 실험의 json·md 결과, `pilot/` 파일럿 과제·답안·정답·채점 |
| `verify/` | 반박 검증: 독립 재구현(`v_*`), 전보체 영어를 이기려는 두 설계(KODEX `attempt_1*`, LEAN `a2_*`), 새 메시지 일반화(`heldout_*`), Claude 읽기 실험(`readability/`) |

`verify/`의 큰 캐시 파일(어휘 스캔 결과)은 저장소에 넣지 않았다. 각 스크립트가 다시 만든다.
현행 Claude 토크나이저는 공개되지 않아 `claude_legacy`(Claude 2 시절)를 대용으로 썼다.
