# 파일럿: 표기 방식별 Claude의 읽기·쓰기 정확도

`pilot_segmentation.py`로 만든 장난감 언어(어근 CVC 24개, 접사 VC 12개)를 네 가지 표기로 적었다.
Claude 피험자에게 사양만 주고 문장 20개 분석(형태소 분절 + 뜻풀이)과 20개 생성을 시켰다.
피험자는 과제 파일 하나만 읽었고 다른 도구는 쓰지 않았다(실행 기록으로 확인). 과제 파일은 `pilot/task_*.md`, 답안은 `pilot/answers.json`, 정답은 `pilot/gold.json`이다.

- 조건: default = 세션 기본 모델, haiku-low = Claude Haiku + 낮은 추론 노력
- 문장당 형태소: 4~17개 (평균 11.2), 분석 문장 20개의 형태소 합계 231개

## 정확도 (맞힌 문장 수 / 20)

| 표기 | 조건 | 분절 | 뜻풀이 | 생성 |
|---|---|---|---|---|
| camel | default | 20/20 | 20/20 | 20/20 |
| camel | haiku-low | 20/20 | 18/20 | 20/20 |
| nospace | default | 20/20 | 20/20 | 20/20 |
| nospace | haiku-low | 20/20 | 20/20 | 20/20 |
| spaced | default | 20/20 | 20/20 | 20/20 |
| spaced | haiku-low | 20/20 | 15/20 | 20/20 |
| wordspaced | default | 20/20 | 20/20 | 20/20 |
| wordspaced | haiku-low | 20/20 | 20/20 | 20/20 |

## 틀린 항목

분절 오류는 하나도 없었다. 틀린 7건은 모두 haiku-low 조건에서 나온 어휘 혼동이다.

- camel/haiku-low p0: 정답 `fix-CERT result-PL-INS` / 답 `fix-CERT result-PL-AGT`
- camel/haiku-low p4: 정답 `write-CERT file-PL-INS` / 답 `write-CERT file-PL-AGT`
- spaced/haiku-low p2: 정답 `delete-INFR plan-PL-PAT agent-PL-REC user-INS result-SRC` / 답 `delete-INFR plan-PL-PAT agent-PL-REC user-INS file-SRC`
- spaced/haiku-low p3: 정답 `check-NEG-INFR server-AGT task-PL-PAT message-new-PL-REC result-new-SRC` / 답 `check-NEG-INFR server-AGT task-PL-PAT message-new-PL-REC file-new-SRC`
- spaced/haiku-low p7: 정답 `check-PST-CERT-Q result-PL-AGT server-PL-REC server-PL-INS tool-PL-SRC` / 답 `check-PST-CERT-Q file-PL-AGT server-PL-REC server-PL-INS tool-PL-SRC`
- spaced/haiku-low p15: 정답 `find-FUT-INFR message-old-PL-AGT tool-PAT error-PL-REC result-large-SRC` / 답 `find-FUT-INFR message-old-PL-AGT tool-PAT error-PL-REC file-large-SRC`
- spaced/haiku-low p17: 정답 `read-NEG-CERT result-AGT result-PAT error-small-INS message-SRC` / 답 `read-NEG-CERT file-AGT file-PAT error-small-INS message-SRC`

- spaced 5건: 어근 `fek`(result)와 `kef`(file)를 혼동했다. 두 형태는 같은 글자를 순서만 바꾼 것이다.
- camel 2건: 접사 `Ag`(INS)를 AGT로 읽었다. 형태 `ag`가 다른 접사의 이름표 `AGT` 앞 글자와 같다.

## 분석 문장의 토큰 수 (형태소당 토큰)

| 표기 | o200k | cl100k | claude_legacy | llama3 | llama4 | mistral_tekken | mistral_sp |
|---|---|---|---|---|---|---|---|
| nospace | 1.25 | 1.33 | 1.25 | 1.31 | 1.19 | 1.25 | 1.38 |
| spaced | 1.14 | 1.38 | 1.44 | 1.35 | 1.22 | 1.36 | 1.48 |
| wordspaced | 1.16 | 1.33 | 1.31 | 1.31 | 1.19 | 1.26 | 1.42 |
| camel | 1.45 | 1.70 | 1.72 | 1.70 | 1.49 | 1.66 | 1.80 |

이 장난감 어휘는 토큰에 맞춰 고르지 않았다. 그래서 형태소마다 띄어 써도(spaced) 붙여 쓰기보다 싸지 않다.

## 한계

- 조건마다 한 번씩만 돌렸고 문항이 40개뿐이다. 기본 모델은 네 표기 모두 만점이라 표기 간 차이를 가르지 못했다(천장 효과).
- 피험자는 Claude뿐이다. 다른 회사 모델은 재지 않았다.
- 장난감 언어는 실제 설계보다 훨씬 작고 단순하다.
