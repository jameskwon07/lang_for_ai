# 투영: 초안 문법의 실제 토큰 비용

`projection.py`가 만든다. 두 추정자의 형태소 분석(corpus/gloss_1.json, gloss_2.json)을 W2 표기(형태소마다 띄어쓰기)의 실제 문자열로 바꿔 잰 값이다.

- 후보 형태: 100,240개 (CV, CVC, CCV, CVCC, CCVC, CVCV, 11개 언어 max zipf < 3.0)
- 닫힌 부류(접사·표지·숫자·변수)에 가장 싼 형태 150개, 어근은 그다음 1,000개 안에 고르게 배정
- 형태당 평균 토큰 (앞 공백 포함, 닫힌 부류 / 어근): o200k 1.00 / 1.07, cl100k 1.00 / 1.57, claude_legacy 1.00 / 1.82, llama3 1.00 / 1.45, llama4 1.00 / 1.09, mistral_tekken 1.00 / 1.22, mistral_sp 1.00 / 1.93

## 메시지 40개 합계 토큰과 영어 대비 비율

| 추정자 | 시나리오 | 형태소/메시지 | o200k (en·terse 대비) | claude_legacy (en·terse 대비) | llama3 (en·terse 대비) | mistral_tekken (en·terse 대비) |
|---|---|---|---|---|---|---|
| 1 | S0_strict | 37.0 | 1,608 (1.39·1.90) | 1,880 (1.59·2.20) | 1,687 (1.45·1.98) | 1,659 (1.38·1.85) |
| 1 | S1_elided | 30.7 | 1,357 (1.17·1.60) | 1,629 (1.38·1.91) | 1,436 (1.23·1.69) | 1,408 (1.17·1.57) |
| 1 | S2_fused | 30.7 | 1,357 (1.17·1.60) | 1,629 (1.38·1.91) | 1,436 (1.23·1.69) | 1,408 (1.17·1.57) |
| 1 | S3_positional | 26.9 | 1,202 (1.04·1.42) | 1,474 (1.25·1.72) | 1,281 (1.10·1.51) | 1,253 (1.04·1.39) |
| 1 | S4_no_linker | 24.1 | 1,094 (0.94·1.29) | 1,365 (1.16·1.60) | 1,172 (1.01·1.38) | 1,145 (0.95·1.27) |
| 1 | S5_raw_digits | 21.7 | 1,075 (0.93·1.27) | 1,310 (1.11·1.53) | 1,154 (0.99·1.36) | 1,145 (0.95·1.27) |
| 2 | S0_strict | 36.0 | 1,565 (1.35·1.85) | 1,856 (1.57·2.17) | 1,657 (1.42·1.95) | 1,619 (1.35·1.80) |
| 2 | S1_elided | 29.2 | 1,292 (1.11·1.52) | 1,583 (1.34·1.85) | 1,384 (1.19·1.63) | 1,346 (1.12·1.50) |
| 2 | S2_fused | 29.2 | 1,290 (1.11·1.52) | 1,581 (1.34·1.85) | 1,382 (1.19·1.62) | 1,344 (1.12·1.49) |
| 2 | S3_positional | 25.4 | 1,141 (0.98·1.35) | 1,432 (1.21·1.67) | 1,233 (1.06·1.45) | 1,195 (0.99·1.33) |
| 2 | S4_no_linker | 25.0 | 1,124 (0.97·1.33) | 1,415 (1.20·1.65) | 1,216 (1.04·1.43) | 1,178 (0.98·1.31) |
| 2 | S5_raw_digits | 22.6 | 1,105 (0.95·1.30) | 1,359 (1.15·1.59) | 1,197 (1.03·1.41) | 1,178 (0.98·1.31) |

기준선 합계: o200k en 1,160 / terse 848, claude_legacy en 1,179 / terse 855, llama3 en 1,164 / terse 851, mistral_tekken en 1,202 / terse 899

## 예시 (m01)

- en: Please refactor the retry logic in src/net/client.py to use exponential backoff with at most 5 attempts. Keep the public interface unchanged.
- en_terse: Refactor retry logic in src/net/client.py -> exponential backoff, max 5 attempts. Keep public interface unchanged.
- gloss_1 S0_strict: `phim vibr cer desc bicy murm trig phen vibr pix kidn dign src/net/client.py migr sequ spol vibr pav cust pinc togg trig magn rhet fost pert cer slic sigu bicy murm lesz vibr sufr kidn kuri togg`
- gloss_1 S5_raw_digits: `phim cer buf trig forg pix kidn src/net/client.py liqu togg spol pav hasn pinc trig redu 5 dict cer vibr dign lesz sufr kuri`
- gloss_2 S0_strict: `duyg turb fos prec bicy kidn taxp fost dets liqu migr src/net/client.py dign cosm kuj turb kho csal decl vibr mant desc cung cust fos vacc cogn bicy kidn wod leth liqu`
- gloss_2 S5_raw_digits: `duyg fos dest taxp sigu dets togg src/net/client.py murm rhet kuj kho csal sequ 5 buf cung pict fos puzz dign wod leth`

## 한계

- 형태소 수는 두 추정자가 손으로 단 분석에 기댄다. 실제 문법이 정해지면 달라진다.
- S3(어순으로 역할 표시)은 생략된 논항과 겹칠 때의 모호성을 따지지 않은 낙관적 추정이다.
- 어근 배정은 '말뭉치에 나온 어근이 1,000개 어휘 안에 고르게 흩어져 있다'는 가정이다.
- 현행 Claude 토크나이저는 공개되지 않았다. claude_legacy는 대용 지표다.
- LLM이 이 문자열을 실제로 정확히 읽고 쓰는지는 재지 않았다.
