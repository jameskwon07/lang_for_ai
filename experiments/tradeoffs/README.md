# 별도 언어의 득실 분석

결론은 [docs/03-tradeoffs.md](../../docs/03-tradeoffs.md)에 있다.

| 파일 | 내용 |
|---|---|
| `analysts.json` | 관점별 분석가 5명(비용, 정확성, 운영, 안전·감독, 표현력)의 원본 분류 |
| `critique.json` | 비평가가 중복을 합치고 과장을 바로잡은 통합본, 빠진 관점, 합친 항목 목록 |
| `roundtrip/write_task.md` | 작성자에게 준 과제 (설계에 쓰지 않은 홀수 메시지 20개) |
| `roundtrip/results.json` | 작성 결과, 독자의 되번역, 블라인드 채점 (Z1 Haiku 저노력, Z2 신중한 인코더, Z3 기본 모델) |
| `roundtrip/validity.json` | 작성 결과의 사전 밖 단어 비율과 토크나이저별 토큰 비율 |
| `roundtrip/first_run_invalid.json` | 무효 처리한 첫 실행. Haiku 작성자가 과제 대신 함께 전달된 질문에 답했다 |

작성자에게 준 사양은 `../tokenization/verify/a2_spec_A_conservative.txt`다.
