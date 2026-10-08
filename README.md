# lang_for_ai

**사람은 못 읽고 AI끼리만 읽고 쓰는 알파벳 언어를 만들 수 있을까?** 그 언어로 AI 간 통신의 토큰을 아낄 수 있을까?

이 질문을 단계별로 실험한 기록이다. 실험은 여기서 마쳤다.

## 결론

> **만들 수는 있다. 하지만 AI끼리 쓰기에 영어보다 낫지 않았다.**
>
> - Claude는 사양(약 1만 토큰)만 읽고 이 언어를 95~100% 정확히 읽었다.
> - 하지만 **직접 쓰면** 정보가 7.5~40% 샜고, 토큰은 일반 영어와 비슷했다(0.92~1.11배).
> - 관사 등을 뺀 **전보체 영어**는 사양 없이도 읽히는데, 어떤 설계도 처음 보는 메시지에서 이를 이기지 못했다.

## 이렇게 생겼다

| | 메시지 | 토큰 (o200k / Claude 대용) |
|---|---|---|
| 영어 | Find recent peer-reviewed studies on how sleep deprivation affects working memory. Return the five most relevant, each with a one-sentence summary. | 27 / 28 |
| 전보체 영어 | Find recent peer-reviewed studies: sleep deprivation -> working memory. Return top 5, 1-sentence summary each. | 24 / 23 |
| **이 언어 (LEAN)** | `aqu antib persec despe adap tob obliv sovere consec afges agreg fle oll fres swo flav avut anunc conv` | 20 / 24 |
| Claude가 사양만 보고 되읽은 것 | Find recent peer-reviewed studies about how sleep loss affects working memory, and return the 5 most relevant ones, with a one-sentence summary for each. | |

이 예시는 설계에 쓴 메시지라 이 언어에 유리하다. 설계에 쓰지 않은 메시지에서는 이 언어가 전보체 영어보다 7~34% 길었다.

## 실험과 결과

| 단계 | 질문 | 한 일 | 결과 | 자세히 |
|---|---|---|---|---|
| 1. 설계 원칙 | 어떤 구조로 만들까? | 사람과 LLM의 차이를 정리하고, 언어를 7개 계층(문자 → 형태소 → … → 화용)으로 나눠 선택지 검토 | 핵심 위험은 토큰화. LLM은 글자가 아니라 토큰을 본다 | [00](docs/00-foundations.md), [01](docs/01-structure.md) |
| 2. 표기 | 글자를 어떻게 적어야 AI가 싸게 읽나? | 토크나이저 7종으로 형태 후보 10만 개와 표기 방식 5가지 측정, Claude 읽기·쓰기 파일럿 | **소문자 + 형태소마다 띄어쓰기**가 최선. 7개 중 5개 토크나이저에서 형태소 하나가 1.01토큰 | [02 §2](docs/02-tokens-and-forms.md#2-표기-l0-l1) |
| 3. 토큰 절약 | 영어보다 짧게 쓸 수 있나? | AI 에이전트 메시지 40개 말뭉치, 초안 문법 투영, 이 언어 편에 선 에이전트 2명의 반박 시도, 처음 보는 메시지로 일반화 시험 | 초안 문법은 전보체 영어의 1.26~2.20배. 최선 설계(LEAN)도 처음 보는 메시지에서 **전보체의 1.07~1.34배**, 일반 영어의 0.81~0.99배 | [02 §3](docs/02-tokens-and-forms.md#3-토큰-절약-l2l5까지) |
| 4. 읽기 | Claude가 사양만 보고 읽나? | 새 Claude에게 사양과 메시지만 주고 영어로 되돌리게 한 뒤 블라인드 채점 | 기본 모델 **98%**, Haiku 86%. 장치가 많은 설계(KODEX)는 Haiku **5%** | [02 §3.4](docs/02-tokens-and-forms.md#34-claude가-실제로-읽는가--verifyreadability) |
| 5. 쓰기와 득실 | 직접 쓰면? 영어 대신 쓸 이유가 있나? | Claude가 쓰고 다른 Claude가 읽는 왕복 시험, 관점 5개 분석 + 비평 | 기본 모델이 쓰면 **88~93%** 보존, 토큰은 일반 영어의 0.92~1.11배. Haiku가 쓰면 60~63% 보존 | [03](docs/03-tradeoffs.md) |

## 별도 언어를 만들면 (영어, 전보체 영어, JSON과 비교)

| 좋아지는 점 | 나빠지는 점 | 그대로인 점 |
|---|---|---|
| 공들여 인코딩하면 메시지가 일반 영어보다 1~19% 짧다 (모델이 직접 쓰면 사라짐) | 대화마다 사양 약 1만 토큰이 고정으로 든다 | 강한 모델이 읽을 때의 정확도 |
| 사양 없는 사람에게 내용이 가려진다 (보안은 아님) | 직접 쓸 때 정보 손실 7.5~40% | 확신도·근거 표현 |
| 실험으로서의 가치 | 약한 모델에서 읽기·쓰기가 크게 떨어진다 | 경로·URL·숫자 전달 |
| | 사람과 키워드 필터의 감독이 어려워진다 | 보안 (둘 다 없음) |
| | 사양 판본·사전 관리, 디버깅, JSON 도구 연동 비용 | |

전체 비교표와 근거는 [03. 별도 언어의 득실](docs/03-tradeoffs.md)에 있다.

## 배운 것

1. **영어 토크나이저 안에서는 영어를 이기기 어렵다.** 영어 단어는 이미 1토큰이다. 새 언어가 쓸 수 있는 싼 형태는 남은 조각뿐이고, LEAN 사전의 68%가 흔한 영어 단어의 앞부분이었다.
2. **설계에 쓴 예시에서의 우위는 과적합이었다.** 두 설계 모두 설계용 메시지에서는 대부분의 토크나이저에서 전보체 영어를 이겼지만, 처음 보는 메시지에서는 모든 토크나이저에서 졌다.
3. **읽기는 쉽고 쓰기는 어렵다.** 같은 언어를 Claude는 거의 완벽히 읽었지만, 직접 쓸 때는 정보를 흘렸다. 약한 모델은 영어 단어를 섞어 썼다.
4. **단순해야 약한 모델도 쓸 수 있다.** 같은 Haiku가 단순한 설계는 86%, 장치가 많은 설계는 5%를 읽었다.
5. **사양 비용이 메시지당 절약을 압도한다.** 메시지당 몇 토큰을 아껴도, 매 대화 1만 토큰의 사양을 회수하려면 한 호출에 메시지를 수십~수백 개 써야 한다. Claude 대용 토크나이저에서는 사실상 회수할 수 없었다.

## 한계

- 피험자(읽기·쓰기)와 판정자는 모두 Claude다. 다른 회사 모델은 재지 않았다.
- 현행 Claude 토크나이저는 공개되지 않아 Claude 2 시절 토크나이저(`claude_legacy`)를 대용으로 썼다.
- 메시지는 20~40개이고, 조건마다 한 번씩 실행했다.
- 전보체 영어나 JSON으로 쓰고 되읽는 대조 시험은 하지 않았다.

## 저장소 구성

| 경로 | 내용 |
|---|---|
| [docs/](docs/) | 설계 원칙(00), 언어 구조(01), 표기·토큰 실험(02), 득실 분석(03), [결정 기록](docs/decisions.md) |
| [experiments/tokenization/](experiments/tokenization/) | 토크나이저 7종 측정 스크립트, AI 메시지 말뭉치, 반박 검증과 읽기 실험 기록. 재현 방법은 그 안의 README |
| [experiments/tradeoffs/](experiments/tradeoffs/) | 득실 분석 원자료와 쓰고 읽는 왕복 시험 |

재현:

```bash
cd experiments/tokenization
pip install -r requirements.txt
python3 fetch_tokenizers.py   # 토크나이저 7종을 PyPI 패키지에서 받는다
python3 inventory.py && python3 alignment.py && python3 baseline.py && python3 projection.py
```

## 라이선스

[MIT License](LICENSE)
