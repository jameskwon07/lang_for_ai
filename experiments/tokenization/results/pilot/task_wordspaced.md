# 장난감 언어 사양

## 어근
- bov = wrong (형용사)
- fek = result (명사)
- geg = task (명사)
- kef = file (명사)
- kig = tool (명사)
- kog = run (동사)
- kuz = small (형용사)
- lup = read (동사)
- pof = delete (동사)
- reb = send (동사)
- rur = server (명사)
- tep = fix (동사)
- tuf = check (동사)
- vab = agent (명사)
- vef = find (동사)
- vik = user (명사)
- vok = old (형용사)
- vug = large (형용사)
- vum = plan (명사)
- zaz = write (동사)
- zim = error (명사)
- zoz = ready (형용사)
- zud = message (명사)
- zun = new (형용사)

## 접사 (뜻풀이에서는 대문자 이름을 쓴다)
- ag = INS: 도구 (무엇으로)
- ap = REC: 받는 쪽 (누구에게)
- eg = PST: 과거
- ib = SRC: 출처 (어디에서)
- id = NEG: 부정
- ip = AGT: 행위자 (누가)
- iv = PL: 복수
- od = PAT: 대상 (무엇을)
- ot = Q: 의문
- ub = CERT: 확실함 (직접 확인)
- uf = INFR: 추론함
- ut = FUT: 미래

## 문법
- 문장은 술어 단어 하나로 시작하고, 그 뒤에 논항 단어가 1~4개 온다.
- 술어 단어 = 동사 어근 + [PST 또는 FUT] + [NEG] + (CERT 또는 INFR 중 하나, 필수) + [Q]
- 논항 단어 = 명사 어근 + [형용사 어근] + [PL] + 역할 접사(AGT, PAT, REC, INS, SRC 중 하나, 필수)
- 논항은 AGT, PAT, REC, INS, SRC 순서로 온다.
- 형용사 어근은 명사 어근 바로 뒤에 붙어 같은 단어가 된다.

## 표기
- 단어(어근과 그 뒤에 붙는 접사들)마다 공백 하나로 띄어 쓰고, 단어 안의 형태소는 붙여 쓴다.

## 뜻풀이 형식
- 단어 안의 형태소 뜻은 하이픈(-)으로 잇고, 단어 사이는 공백 하나로 띄운다.
- 어근은 영어 뜻(user, send, new …), 접사는 대문자 이름(PST, AGT …)으로 쓴다.

## 예시
- 문장: tepeguf fekzozod fekivap
  뜻풀이: fix-PST-INFR result-ready-PAT result-PL-REC
- 문장: pofeguf vikivip vabbovod kefvugag kefib
  뜻풀이: delete-PST-INFR user-PL-AGT agent-wrong-PAT file-large-INS file-SRC

# 과제 A: 문장 분석
각 문장을 형태소로 나누고(morphemes: 형태소 문자열 목록, 소문자로) 뜻풀이(gloss)를 쓴다.

- p0: tepub fekivag
- p1: rebeguf fekip zudag kefib
- p2: pofuf vumivod vabivap vikag fekib
- p3: tufiduf rurip gegivod zudzunivap fekzunib
- p4: zazub kefivag
- p5: koguf zimvugivip gegvokod kigap vumzunag
- p6: kogutidufot zudkuzip vumbovod rurzozag vumkuzib
- p7: tufegubot fekivip rurivap rurivag kigivib
- p8: pofegub zimkuzip zimvugivod vikivap vabivib
- p9: vefub kefod kigivag
- p10: vefutuf vumbovivip vikivap zudag kefib
- p11: rebegub gegivod
- p12: vefutidub vikip zudzunod gegivag zudib
- p13: zazutub gegivod gegap zudzunib
- p14: lupegub kefkuzod gegivib
- p15: vefutuf zudvokivip kigod zimivap fekvugib
- p16: zazeguf zudzozod rurivap rurag kefib
- p17: lupidub fekip fekod zimkuzag zudib
- p18: luputuf kigip zudivap gegag vabkuzivib
- p19: pofuf zudip zudivib

# 과제 B: 문장 생성
각 뜻풀이를 이 언어의 표기 규칙대로 정확히 적는다(text).

- g0: run-FUT-CERT plan-AGT server-PAT tool-wrong-INS file-small-SRC
- g1: send-PST-NEG-INFR tool-AGT user-wrong-REC server-small-INS message-PL-SRC
- g2: fix-PST-CERT agent-AGT file-PAT task-ready-REC file-INS
- g3: find-PST-NEG-INFR server-AGT agent-ready-REC server-ready-PL-INS
- g4: run-NEG-CERT result-AGT user-wrong-REC tool-small-INS agent-new-SRC
- g5: read-FUT-INFR message-SRC
- g6: write-FUT-INFR task-AGT plan-REC task-PL-SRC
- g7: fix-INFR agent-AGT
- g8: send-FUT-INFR-Q task-AGT tool-PL-PAT user-PL-REC task-PL-SRC
- g9: fix-FUT-INFR plan-old-AGT message-wrong-INS server-large-SRC
- g10: run-NEG-CERT tool-large-PAT file-REC server-INS server-ready-PL-SRC
- g11: check-PST-INFR-Q file-ready-AGT plan-PL-REC
- g12: delete-FUT-CERT task-AGT result-PL-PAT
- g13: delete-PST-CERT-Q result-wrong-PAT server-PL-REC
- g14: fix-FUT-CERT file-ready-AGT error-REC task-wrong-SRC
- g15: write-PST-NEG-CERT file-AGT file-PL-PAT task-REC result-wrong-INS
- g16: check-FUT-NEG-CERT error-AGT file-PL-PAT result-PL-INS plan-SRC
- g17: fix-FUT-CERT-Q message-AGT file-PL-REC tool-SRC
- g18: send-PST-NEG-CERT file-REC
- g19: find-PST-INFR file-PAT
