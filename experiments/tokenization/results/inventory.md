# E1. Morpheme candidate inventory: how many forms fit in one token?

Output of `python3 inventory.py`. All numbers and form lists are in [inventory.json](inventory.json). Spellings are written `kat` (glued, lowercase), `␣kat` (leading space), `Kat` (glued, capitalized), `␣Kat` (leading space + capitalized). 'zipf < 3.0' means that the highest zipf frequency across the 11 languages (en, es, de, fr, it, pt, nl, tr, id, pl, sv) is below 3.0.

## 1. Answer to the key question

Question: is there a shape and spelling that can supply about 1,000 roots and about 100 grammatical forms with forms that are a single token on all 7 tokenizers (or on all but mistral_sp) and are not common words?

- **No shape and spelling combination meets the target (1,000 roots + 100 grammatical forms, single token, word filter zipf < 3.0).** None does at any level: all 7, the 6 other than mistral_sp, or 6 or more of 7. The roots are what falls short.
- 100 grammatical forms can be filled with forms that are single tokens on all 7: VCC kat 125 (zipf < 3.0), VCVC kat 225 (zipf < 3.0), VCVC kat 148 (zipf < 2.0). All of these are glued spellings, so they fit the glued design or the 'space before roots only' design. But almost all of these forms are fragments inside common words (e.g. `ated`, `atic`, `ity`) (section 2.5).
- Measuring the docs/01 sketch (glued CVC roots + VC affixes) as is: CVC kat single on all 7: 547 → zipf < 3.0: 41 → < 2.0: 5; VC kat single on all 7: 102 → zipf < 3.0: 0 → < 2.0: 0. Regardless of tokenization, only 1 of the 105 VC forms has zipf < 3.0 (almost every two-letter string is a word or abbreviation in some language).
- Maximum roots (all 7, one shape): no filter: 610 (CVC ␣kat) → zipf < 3.0: 78 (CVCC ␣kat) → zipf < 2.0: 26 (CVCVC ␣kat).
- Maximum roots (all 6 except mistral_sp, one shape): no filter: 728 (CVC ␣kat) → zipf < 3.0: 121 (CVCC ␣kat) → zipf < 2.0: 44 (CVCC ␣kat).
- Root pool that combines all consonant-initial shapes in a spaced design (␣kat, single token on all 7): no filter: 2,063 → zipf < 3.0: 205 → < 2.0: 62. Without the word filter it exceeds 1,000; with the filter it falls far short.
- The bottleneck is the word filter. Share of forms with zipf ≥ 3.0 in some language — CVC ␣kat: 95% of the 610 forms that are single tokens on all 7, 13% of the 598 forms that are a single token on no tokenizer; CVC kat: 92% of the 547 forms that are single tokens on all 7, 26% of the 837 forms that are a single token on no tokenizer. A letter string that a tokenizer made into one token is a string that occurs often in the first place, so forms that are single tokens on more tokenizers are more often real words (section 2.4).
- Regardless of tokenization, only 907 of the 2,205 CVC forms have zipf < 3.0, and only 493 have zipf < 2.0. CVC alone cannot supply 1,000 roots even before token counts are considered.
- Even the single tokens that pass the filter are mostly fragments of common words (e.g. ` calc`, ` gover`, `ated`). Share of forms that are a proper prefix (␣ spelling) or a proper substring (glued spelling) of a common word: CVCC ␣kat 100% (of 78); CVCVC ␣kat 93% (of 46); VCVC kat 100% (of 225), baseline (not a single token) 45%; CVC ␣kat 100% (of 32), baseline (not a single token) 37% (section 2.5). The only forms single on all 7 that are not fragments: `akov`, `cref`, `debug`, `href`, `idx`, `javax`, `json`, `mutex`, `popup`, `regex`, `yaml` (many are code identifiers). The zipf filter removes only 'the word itself'; it does not remove the meaning that such fragments bring in.
- Compromise 1 (allow 2 tokens): picking the 1,000 roots with the lowest token cost while keeping zipf < 3.0 — root pool (spaced designs only) ␣kat: 205 single on all 7, 987 at 2 tokens or fewer on all 7, mean tokens o200k 1.03 / claude_legacy 1.59 / mistral_sp 1.72; CVCV ␣kat: 10 single on all 7, 940 at 2 tokens or fewer on all 7, mean tokens o200k 1.54 / claude_legacy 2.00 / mistral_sp 2.03; CVCC kat: 66 single on all 7, 981 at 2 tokens or fewer on all 7, mean tokens o200k 1.71 / claude_legacy 1.74 / mistral_sp 1.90 (section 2.3).
- Compromise 2 (relax the filter): CVC ␣kat forms that are single tokens on all 7: 32 at zipf < 3.0 and 165 at < 4.0 by the 11-language measure; by English alone, 169 at < 3.0 and 400 at < 4.0 (section 2.1). Relaxing the filter means using real words as roots.
- Of the CVC ␣kat forms that are single tokens on all 7, those removed for zipf ≥ 3.0, split by the language with the highest frequency: en 189, sv 72, de 49, id 46, tr 46, nl 43 …; of these, 137 have an English zipf below 3.0.
- claude_legacy alone: roots (one shape) max 900 with no filter (CVC kat), max 271 at zipf < 3.0 (CVCC kat); ␣kat root pool at zipf < 3.0: 560; grammatical forms max 448 at zipf < 3.0 (VCVC kat). Tokenizers with fewer CVC single tokens for ␣kat than for kat: claude_legacy (claude_legacy ␣kat 762 / kat 900). On the other tokenizers, CVC has at least as many single tokens for ␣kat as for kat.

### 1.1 Maximum per design (one shape each)

For roots, pick the one consonant-initial shape (CV, CVV, CCV, CVC, CVCV, CCVC, CVCC, CVCVC) that yields the most forms; for grammatical forms, the one vowel-initial shape (V, VV, VC, VCV, VCC, VCVC) that yields the most. This is the condition under which even glued text can be split by the rule 'if the next letter is a consonant, a root starts; if it is a vowel, a grammatical form starts'. Each cell is `shape count`, and the three values are `no filter / zipf < 3.0 / zipf < 2.0` (the shape with the most forms can differ by filter).

| Design (root spelling + grammatical spelling) | Agreement level | Roots | Grammatical forms |
| --- | --- | --- | --- |
| Glued (no spaces) (kat + kat) | all 7 | CVC 547 / CVCC 66 / CCVC 25 | VCVC 383 / VCVC 225 / VCVC 148 |
|  | all 6 except mistral_sp | CVC 655 / CVCC 81 / CCVC 36 | VCVC 534 / VCVC 324 / VCVC 220 |
|  | 6 or more of 7 | CVC 692 / CVCC 95 / CCVC 41 | VCVC 584 / VCVC 355 / VCVC 242 |
|  | claude_legacy alone | CVC 900 / CVCC 271 / CCVC 161 | VCVC 700 / VCVC 448 / VCVC 315 |
| Glued + capitalized first letter of each morpheme (Kat + Kat) | all 7 | CVC 212 / CVCC 11 / CVCC 1 | VCC 55 / VCC 4 / VCV 1 |
|  | all 6 except mistral_sp | CVC 348 / CVCC 18 / CVCVC 2 | VCC 82 / VCC 8 / VCV 1 |
|  | 6 or more of 7 | CVC 350 / CVCC 18 / CVCVC 3 | VCC 84 / VCC 9 / VCV 1 |
|  | claude_legacy alone | CVC 463 / CVCC 42 / CVCVC 14 | VCC 99 / VCC 12 / VCVC 2 |
| One space between morphemes (␣kat + ␣kat) | all 7 | CVC 610 / CVCC 78 / CVCVC 26 | VCC 126 / VCC 20 / VCVC 8 |
|  | all 6 except mistral_sp | CVC 728 / CVCC 121 / CVCC 44 | VCC 161 / VCVC 32 / VCVC 20 |
|  | 6 or more of 7 | CVC 785 / CVCC 138 / CVCVC 50 | VCC 172 / VCVC 37 / VCVC 23 |
|  | claude_legacy alone | CVCC 810 / CVCC 173 / CVCVC 93 | VCC 205 / VCC 51 / VCVC 32 |
| Space before roots only (grammatical forms glued) (␣kat + kat) | all 7 | CVC 610 / CVCC 78 / CVCVC 26 | VCVC 383 / VCVC 225 / VCVC 148 |
|  | all 6 except mistral_sp | CVC 728 / CVCC 121 / CVCC 44 | VCVC 534 / VCVC 324 / VCVC 220 |
|  | 6 or more of 7 | CVC 785 / CVCC 138 / CVCVC 50 | VCVC 584 / VCVC 355 / VCVC 242 |
|  | claude_legacy alone | CVCC 810 / CVCC 173 / CVCVC 93 | VCVC 700 / VCVC 448 / VCVC 315 |
| Space before roots + capital letter (grammatical forms glued) (␣Kat + kat) | all 7 | CVC 562 / CVCC 34 / CVC 1 | VCVC 383 / VCVC 225 / VCVC 148 |
|  | all 6 except mistral_sp | CVC 699 / CVCC 55 / CVCC 8 | VCVC 534 / VCVC 324 / VCVC 220 |
|  | 6 or more of 7 | CVC 742 / CVCC 70 / CVCC 11 | VCVC 584 / VCVC 355 / VCVC 242 |
|  | claude_legacy alone | CVC 739 / CVCC 84 / CVCC 20 | VCVC 700 / VCVC 448 / VCVC 315 |

### 1.2 Spaced designs: pools that combine shapes of different lengths

The space marks the boundary, so shapes of different lengths can be mixed. Each cell is `no filter / zipf < 3.0 / zipf < 2.0`.

| Spelling | Agreement level | Root pool | Grammatical pool |
| --- | --- | ---: | ---: |
| ␣kat | all 7 | 2,063 / 205 / 62 | 315 / 37 / 13 |
|  | all 6 except mistral_sp | 2,720 / 319 / 104 | 437 / 63 / 26 |
|  | 6 or more of 7 | 2,924 / 366 / 118 | 460 / 73 / 29 |
|  | claude_legacy alone | 3,148 / 560 / 255 | 528 / 106 / 40 |
|  | 2 tokens or fewer on all 7 | 119,536 / 107,295 / 99,214 | 9,896 / 8,099 / 6,827 |
| ␣Kat | all 7 | 1,407 / 81 / 3 | 213 / 11 / 1 |
|  | all 6 except mistral_sp | 1,975 / 143 / 19 | 270 / 14 / 2 |
|  | 6 or more of 7 | 2,097 / 170 / 26 | 288 / 17 / 2 |
|  | claude_legacy alone | 2,222 / 240 / 55 | 303 / 25 / 7 |
|  | 2 tokens or fewer on all 7 | 102,003 / 90,130 / 82,443 | 8,554 / 6,801 / 5,578 |

### 1.3 Per tokenizer (zipf < 3.0, single token)

Number of single-token forms that pass the word filter (zipf < 3.0), looking at one tokenizer at a time. The claude_legacy row is the Claude proxy.

| Tokenizer | Root pool ␣kat | CVC kat | CVC ␣kat | CVCC ␣kat | VCC kat | VCVC kat | Grammatical pool ␣kat |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| o200k | 3,009 | 203 | 375 | 852 | 352 | 1,219 | 607 |
| cl100k | 781 | 107 | 109 | 296 | 237 | 594 | 165 |
| claude_legacy | 560 | 128 | 59 | 173 | 218 | 448 | 106 |
| llama3 | 1,042 | 124 | 137 | 359 | 250 | 671 | 196 |
| llama4 | 2,234 | 217 | 259 | 705 | 359 | 1,192 | 407 |
| mistral_tekken | 1,593 | 154 | 181 | 540 | 231 | 810 | 300 |
| mistral_sp | 303 | 62 | 47 | 113 | 154 | 283 | 51 |

## 2. Size of the compromises

### 2.1 Changing the word-filter threshold

Number of forms that are single tokens on all 7. The upper row uses the maximum over the 11 languages; the lower row (en) uses the English zipf only.

| Shape, spelling | Filter languages | < 2.0 | < 2.5 | < 3.0 | < 3.5 | < 4.0 | < 4.5 | < 5.0 | no filter |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| VC kat | 11 languages | 0 | 0 | 0 | 9 | 25 | 41 | 47 | 102 |
|  | en | 0 | 4 | 12 | 30 | 58 | 74 | 85 | 102 |
| VCV kat | 11 languages | 11 | 24 | 44 | 86 | 132 | 171 | 192 | 246 |
|  | en | 29 | 81 | 171 | 213 | 228 | 238 | 240 | 246 |
| VCC kat | 11 languages | 21 | 69 | 125 | 200 | 254 | 285 | 302 | 340 |
|  | en | 66 | 149 | 220 | 277 | 309 | 322 | 326 | 340 |
| VC ␣kat | 11 languages | 0 | 0 | 0 | 4 | 11 | 23 | 28 | 79 |
|  | en | 0 | 0 | 5 | 16 | 38 | 52 | 63 | 79 |
| VCC ␣kat | 11 languages | 4 | 11 | 20 | 47 | 64 | 81 | 92 | 126 |
|  | en | 7 | 22 | 48 | 76 | 97 | 108 | 112 | 126 |
| CVC kat | 11 languages | 5 | 13 | 41 | 77 | 153 | 244 | 335 | 547 |
|  | en | 16 | 61 | 171 | 269 | 364 | 439 | 484 | 547 |
| CVC ␣kat | 11 languages | 0 | 3 | 32 | 82 | 165 | 266 | 359 | 610 |
|  | en | 6 | 42 | 169 | 288 | 400 | 486 | 539 | 610 |
| CCV ␣kat | 11 languages | 1 | 7 | 14 | 28 | 34 | 44 | 48 | 65 |
|  | en | 8 | 14 | 39 | 51 | 57 | 59 | 61 | 65 |
| CVCV ␣kat | 11 languages | 5 | 8 | 10 | 17 | 26 | 68 | 114 | 212 |
|  | en | 16 | 32 | 41 | 49 | 71 | 120 | 157 | 212 |
| CCVC kat | 11 languages | 25 | 35 | 47 | 56 | 73 | 89 | 110 | 135 |
|  | en | 32 | 50 | 62 | 74 | 89 | 105 | 118 | 135 |
| CVCC ␣kat | 11 languages | 25 | 50 | 78 | 106 | 166 | 274 | 386 | 550 |
|  | en | 53 | 104 | 137 | 173 | 249 | 350 | 447 | 550 |
| CVCVC ␣kat | 11 languages | 26 | 39 | 46 | 59 | 91 | 176 | 234 | 304 |
|  | en | 54 | 70 | 77 | 91 | 120 | 210 | 261 | 304 |

### 2.2 Allowing '2 tokens or fewer' instead of a single token

Number of forms that take 2 tokens or fewer on all 7 (`no filter / zipf < 3.0 / zipf < 2.0`).

| Shape | kat | ␣kat | Kat | ␣Kat |
| --- | ---: | ---: | ---: | ---: |
| VC | 105 / 1 / 0 | 105 / 1 / 0 | 105 / 1 / 0 | 105 / 1 / 0 |
| VCV | 516 / 198 / 84 | 499 / 184 / 70 | 487 / 175 / 64 | 495 / 181 / 67 |
| VCC | 2,157 / 1,639 / 986 | 1,960 / 1,445 / 807 | 1,691 / 1,195 / 608 | 1,841 / 1,334 / 717 |
| CVC | 2,199 / 901 / 487 | 2,196 / 898 / 484 | 2,169 / 874 / 462 | 2,197 / 899 / 485 |
| CCV | 2,110 / 1,692 / 1,007 | 2,071 / 1,656 / 973 | 2,035 / 1,625 / 945 | 2,048 / 1,632 / 952 |
| CVCV | 7,970 / 5,164 / 3,866 | 7,990 / 5,146 / 3,841 | 6,331 / 3,790 / 2,701 | 7,444 / 4,685 / 3,431 |
| CCVC | 26,383 / 25,548 / 24,691 | 19,568 / 18,749 / 17,927 | 13,962 / 13,242 / 12,539 | 14,872 / 14,095 / 13,351 |
| CVCC | 19,510 / 17,512 / 15,845 | 21,105 / 19,066 / 17,323 | 11,384 / 9,527 / 8,146 | 18,063 / 16,051 / 14,375 |

### 2.3 Picking the cheapest 1,000 roots / 100 grammatical forms that pass the filter

Candidates that pass the word filter (zipf < 3.0) were sorted by token cost (number of tokenizers on which the form is not a single token → total tokens over the 7). Then 1,000 roots and 100 grammatical forms were picked, and the mean number of tokens per form was measured. `pool` combines all shapes of a role and can be used only in spaced designs. `Candidates` is the number of forms that pass the filter (for CCVC, CVCC and CVCVC, only forms whose frequency was measured are counted, that is, forms that are a single token somewhere or take 2 tokens or fewer on all 7). The seven columns on the right are the mean number of tokens of the picked forms.

| Spelling | Candidate pool | Candidates | Picked | Single on all 7 | ≤2 on all 7 | o200k | cl100k | claude_legacy | llama3 | llama4 | mistral_tekken | mistral_sp |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| kat | root CVC | 907 | 907 | 41 | 901 | 1.78 | 1.88 | 1.86 | 1.86 | 1.76 | 1.83 | 1.94 |
| kat | root CVCV | 8,000 | 1,000 | 10 | 989 | 1.78 | 1.96 | 1.95 | 1.94 | 1.83 | 1.87 | 1.99 |
| kat | root CVCC | 22,963 | 1,000 | 66 | 981 | 1.71 | 1.81 | 1.74 | 1.80 | 1.68 | 1.80 | 1.90 |
| kat | root CVCVC | 80,024 | 1,000 | 25 | 943 | 1.74 | 1.86 | 1.83 | 1.82 | 1.68 | 1.82 | 1.99 |
| kat | grammatical VC | 1 | 1 | 0 | 1 | 1.00 | 2.00 | 2.00 | 2.00 | 1.00 | 1.00 | 2.00 |
| kat | grammatical VCV | 207 | 100 | 44 | 100 | 1.01 | 1.12 | 1.41 | 1.06 | 1.01 | 1.10 | 1.47 |
| kat | grammatical VCC | 1,687 | 100 | 100 | 100 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| kat | grammatical VCVC | 10,113 | 100 | 100 | 100 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| ␣kat | root CVC | 907 | 907 | 32 | 898 | 1.59 | 1.88 | 1.94 | 1.85 | 1.71 | 1.80 | 1.96 |
| ␣kat | root CVCV | 8,000 | 1,000 | 10 | 940 | 1.54 | 1.98 | 2.00 | 1.96 | 1.82 | 1.88 | 2.03 |
| ␣kat | root CVCC | 22,963 | 1,000 | 78 | 974 | 1.22 | 1.71 | 1.85 | 1.65 | 1.32 | 1.48 | 1.91 |
| ␣kat | root CVCVC | 80,024 | 1,000 | 46 | 839 | 1.34 | 1.86 | 1.97 | 1.78 | 1.38 | 1.57 | 2.04 |
| ␣kat | root pool | 139,963 | 1,000 | 205 | 987 | 1.03 | 1.29 | 1.59 | 1.19 | 1.04 | 1.16 | 1.72 |
| ␣kat | grammatical VC | 1 | 1 | 0 | 1 | 1.00 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 |
| ␣kat | grammatical VCV | 207 | 100 | 2 | 97 | 1.29 | 1.91 | 1.97 | 1.91 | 1.71 | 1.87 | 2.01 |
| ␣kat | grammatical VCC | 1,687 | 100 | 20 | 100 | 1.05 | 1.22 | 1.58 | 1.12 | 1.07 | 1.30 | 1.73 |
| ␣kat | grammatical VCVC | 10,113 | 100 | 15 | 99 | 1.02 | 1.36 | 1.57 | 1.30 | 1.03 | 1.10 | 1.79 |
| ␣kat | grammatical pool | 12,008 | 100 | 37 | 100 | 1.00 | 1.01 | 1.31 | 1.01 | 1.01 | 1.05 | 1.51 |
| ␣Kat | root CVC | 907 | 907 | 20 | 899 | 1.81 | 1.91 | 1.94 | 1.90 | 1.82 | 1.86 | 1.98 |
| ␣Kat | root CVCV | 8,000 | 1,000 | 0 | 996 | 1.97 | 1.99 | 1.99 | 1.99 | 1.98 | 1.98 | 2.00 |
| ␣Kat | root CVCC | 22,963 | 1,000 | 34 | 989 | 1.72 | 1.85 | 1.92 | 1.84 | 1.69 | 1.74 | 1.95 |
| ␣Kat | root CVCVC | 80,024 | 1,000 | 5 | 975 | 1.90 | 1.96 | 1.97 | 1.95 | 1.86 | 1.90 | 2.00 |
| ␣Kat | root pool | 139,963 | 1,000 | 81 | 988 | 1.32 | 1.63 | 1.78 | 1.60 | 1.25 | 1.40 | 1.88 |
| ␣Kat | grammatical VC | 1 | 1 | 0 | 1 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 |
| ␣Kat | grammatical VCV | 207 | 100 | 2 | 99 | 1.93 | 1.98 | 1.98 | 1.98 | 1.92 | 1.97 | 1.99 |
| ␣Kat | grammatical VCC | 1,687 | 100 | 6 | 100 | 1.57 | 1.71 | 1.88 | 1.71 | 1.48 | 1.67 | 1.90 |
| ␣Kat | grammatical VCVC | 10,113 | 100 | 3 | 100 | 1.63 | 1.86 | 1.89 | 1.85 | 1.59 | 1.71 | 1.93 |
| ␣Kat | grammatical pool | 12,008 | 100 | 11 | 100 | 1.26 | 1.55 | 1.76 | 1.55 | 1.18 | 1.42 | 1.81 |

### 2.4 Single-token forms are more often real words

Number of forms and the share (%) with zipf ≥ 3.0, by the number of tokenizers (k) on which the form is a single token (`forms (share)`).

| Shape, spelling | k=0 | k=1 | k=2 | k=3 | k=4 | k=5 | k=6 | k=7 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| VC kat | - | - | - | 1 (0) | 1 (100) | - | 1 (100) | 102 (100) |
| VC ␣kat | - | 1 (0) | 3 (100) | 1 (100) | 1 (100) | 5 (100) | 15 (100) | 79 (100) |
| VCV kat | 64 (14) | 28 (32) | 35 (40) | 34 (44) | 25 (48) | 39 (62) | 54 (61) | 246 (82) |
| VCV ␣kat | 199 (34) | 112 (60) | 59 (75) | 48 (88) | 20 (85) | 29 (90) | 27 (96) | 31 (94) |
| CVC kat | 837 (26) | 160 (54) | 115 (71) | 162 (66) | 113 (74) | 126 (80) | 145 (81) | 547 (92) |
| CVC ␣kat | 598 (13) | 195 (39) | 147 (50) | 184 (61) | 104 (71) | 192 (81) | 175 (85) | 610 (95) |
| CCV kat | 1,759 (13) | 129 (32) | 66 (36) | 66 (29) | 37 (24) | 41 (51) | 51 (63) | 56 (75) |
| CCV ␣kat | 1,820 (13) | 127 (25) | 62 (42) | 37 (38) | 28 (39) | 41 (59) | 25 (64) | 65 (78) |
| CVCV kat | 9,889 (22) | 380 (57) | 187 (65) | 187 (74) | 76 (79) | 88 (88) | 84 (85) | 134 (93) |
| CVCV ␣kat | 8,982 (17) | 773 (56) | 363 (78) | 376 (84) | 71 (83) | 138 (93) | 110 (96) | 212 (95) |

### 2.5 Single tokens that pass the filter are mostly word fragments

We collected the 319,468 words with zipf ≥ 3.0 in the 11 languages (duplicates across languages removed) and measured the share (%) of zipf < 3.0 forms that are a proper prefix of those words (␣ spelling: a fragment from the start of a word, e.g. ` calc` ← calculate) or a proper substring (glued spelling: a fragment inside a word, e.g. `ated` ← created). The baseline is the set of forms of the same shape that are a single token on no tokenizer (only shapes where every form's frequency was measured).

| Shape, spelling | Single on all 7 & < 3.0 | Fragment % | Not single & < 3.0 | Fragment % | Non-fragment forms single on all 7 (up to 10) |
| --- | ---: | ---: | ---: | ---: | --- |
| VCV kat | 44 | 100 | 55 | 67 | - |
| VCV ␣kat | 2 | 100 | 132 | 49 | - |
| VCC kat | 125 | 99 | 1,245 | 60 | idx |
| VCC ␣kat | 20 | 95 | 1,435 | 25 | idx |
| VCVC kat | 225 | 100 | 8,564 | 45 | akov |
| VCVC ␣kat | 15 | 100 | 9,705 | 10 | - |
| CVC kat | 41 | 100 | 623 | 62 | - |
| CVC ␣kat | 32 | 100 | 518 | 37 | - |
| CCV kat | 14 | 100 | 1,529 | 71 | - |
| CCV ␣kat | 14 | 100 | 1,576 | 13 | - |
| CVCV kat | 10 | 100 | 7,673 | 50 | - |
| CVCV ␣kat | 10 | 100 | 7,484 | 28 | - |
| CVCC kat | 66 | 98 | - | - | yaml |
| CVCC ␣kat | 78 | 100 | - | - | - |
| CCVC kat | 47 | 96 | - | - | href json |
| CCVC ␣kat | 25 | 88 | - | - | cref href json |
| CVCVC kat | 25 | 84 | - | - | debug mutex popup regex |
| CVCVC ␣kat | 46 | 93 | - | - | debug javax regex |

## 3. Method and checks

- Vowels V = aeiou, consonants C = the other 21 letters (including y). Every possible form of each shape was generated.
- Leading-space spellings were appended after `the` and glued spellings after `1`, then tokenized, and the tokens after the context were counted. If the context and the form merged into one token, the form counted as not a single token.
  - Reason: mistral_sp (SentencePiece) adds a dummy space at the start of the input. So measuring `kat` alone in effect measures `␣kat`, and measuring `␣kat` alone measures a form with two spaces. With a context, the measurement reflects the form as it actually appears mid-sentence.
  - Glued-spelling values are for 'the form at the start of a run of letters'. When letters run on, as in `katenmirob`, a form can be cut together with neighboring letters; this experiment did not measure that (E2 does).
  - The pre-tokenization regexes of o200k, llama4 and mistral_tekken split before a capital letter, so each morpheme in `KatEnMirOb` is tokenized under the same condition as the `Kat` spelling value. cl100k, llama3 and claude_legacy do not split at case boundaries.
- Word filter: wordfreq `zipf_frequency` was measured in the 11 languages and the maximum was used. Capitalized spellings are also filtered by the frequency of the lowercase form.
- Agreement levels: `all 7`, `all 6 except mistral_sp`, `6 or more of 7`, `5 or more of 7`, `claude_legacy alone`, `2 tokens or fewer on all 7`. `6 or more of 7` allows any one tokenizer to miss.
- claude_legacy is the tokenizer from the Claude 2 era. The current Claude tokenizer is not public, so claude_legacy serves only as a proxy.

**Check 1: number of forms, over all of CVC + VC, where the single-token verdict differs between the in-context and standalone measurements**

| Spelling | o200k | cl100k | claude_legacy | llama3 | llama4 | mistral_tekken | mistral_sp |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| kat | 0 | 0 | 0 | 0 | 0 | 0 | 405 |
| ␣kat | 0 | 0 | 0 | 0 | 0 | 0 | 760 |
| Kat | 0 | 0 | 0 | 0 | 0 | 0 | 435 |
| ␣Kat | 0 | 0 | 0 | 0 | 0 | 0 | 680 |

**Check 2: number of forms, over all shapes, that merged with the context token** (0 means the context did not affect the form)

| Spelling | o200k | cl100k | claude_legacy | llama3 | llama4 | mistral_tekken | mistral_sp |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| kat | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| ␣kat | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Kat | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| ␣Kat | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## 4. Single-token counts by shape and spelling (per tokenizer, no filter)

| Shape | Spelling | Total | o200k | cl100k | claude_legacy | llama3 | llama4 | mistral_tekken | mistral_sp |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V | kat | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
|  | ␣kat | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
|  | Kat | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
|  | ␣Kat | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| CV | kat | 105 | 105 | 103 | 104 | 103 | 105 | 102 | 96 |
|  | ␣kat | 105 | 105 | 101 | 97 | 102 | 103 | 101 | 89 |
|  | Kat | 105 | 103 | 88 | 98 | 89 | 101 | 95 | 50 |
|  | ␣Kat | 105 | 103 | 99 | 95 | 99 | 104 | 101 | 90 |
| VC | kat | 105 | 105 | 103 | 103 | 104 | 105 | 105 | 102 |
|  | ␣kat | 105 | 105 | 100 | 94 | 100 | 104 | 97 | 82 |
|  | Kat | 105 | 99 | 68 | 74 | 68 | 96 | 72 | 46 |
|  | ␣Kat | 105 | 96 | 84 | 73 | 88 | 99 | 92 | 66 |
| VV | kat | 25 | 25 | 25 | 25 | 25 | 25 | 25 | 24 |
|  | ␣kat | 25 | 24 | 23 | 19 | 23 | 24 | 17 | 9 |
|  | Kat | 25 | 18 | 7 | 10 | 7 | 19 | 7 | 2 |
|  | ␣Kat | 25 | 17 | 9 | 6 | 9 | 18 | 10 | 3 |
| CCV | kat | 2,205 | 319 | 198 | 195 | 209 | 294 | 200 | 95 |
|  | ␣kat | 2,205 | 333 | 147 | 117 | 177 | 266 | 173 | 71 |
|  | Kat | 2,205 | 84 | 42 | 58 | 43 | 77 | 45 | 19 |
|  | ␣Kat | 2,205 | 127 | 90 | 79 | 98 | 138 | 116 | 52 |
| CVC | kat | 2,205 | 1,192 | 843 | 900 | 915 | 1,229 | 965 | 613 |
|  | ␣kat | 2,205 | 1,573 | 1,009 | 762 | 1,107 | 1,396 | 1,212 | 678 |
|  | Kat | 2,205 | 736 | 431 | 463 | 438 | 676 | 448 | 219 |
|  | ␣Kat | 2,205 | 1,196 | 932 | 739 | 965 | 1,207 | 1,064 | 614 |
| CVV | kat | 525 | 243 | 136 | 138 | 148 | 233 | 163 | 61 |
|  | ␣kat | 525 | 320 | 137 | 75 | 151 | 229 | 177 | 60 |
|  | Kat | 525 | 93 | 41 | 35 | 42 | 76 | 43 | 8 |
|  | ␣Kat | 525 | 194 | 111 | 50 | 114 | 184 | 156 | 33 |
| VCC | kat | 2,205 | 682 | 517 | 486 | 536 | 680 | 500 | 382 |
|  | ␣kat | 2,205 | 464 | 277 | 205 | 298 | 412 | 328 | 140 |
|  | Kat | 2,205 | 158 | 112 | 99 | 112 | 149 | 100 | 58 |
|  | ␣Kat | 2,205 | 227 | 168 | 113 | 172 | 235 | 193 | 99 |
| VCV | kat | 525 | 448 | 351 | 292 | 375 | 426 | 381 | 268 |
|  | ␣kat | 525 | 316 | 98 | 68 | 106 | 211 | 147 | 32 |
|  | Kat | 525 | 67 | 25 | 26 | 25 | 51 | 28 | 8 |
|  | ␣Kat | 525 | 135 | 55 | 34 | 56 | 110 | 81 | 28 |
| CCVC | kat | 46,305 | 597 | 358 | 419 | 380 | 630 | 421 | 206 |
|  | ␣kat | 46,305 | 876 | 436 | 359 | 508 | 739 | 580 | 223 |
|  | Kat | 46,305 | 193 | 121 | 141 | 121 | 181 | 114 | 52 |
|  | ␣Kat | 46,305 | 368 | 275 | 201 | 287 | 417 | 348 | 121 |
| CVCC | kat | 46,305 | 986 | 714 | 839 | 734 | 1,032 | 723 | 427 |
|  | ␣kat | 46,305 | 2,086 | 1,140 | 810 | 1,233 | 1,788 | 1,480 | 629 |
|  | Kat | 46,305 | 545 | 328 | 333 | 328 | 483 | 307 | 144 |
|  | ␣Kat | 46,305 | 1,225 | 877 | 570 | 890 | 1,224 | 1,060 | 399 |
| CVCV | kat | 11,025 | 832 | 362 | 380 | 424 | 773 | 561 | 169 |
|  | ␣kat | 11,025 | 1,872 | 512 | 342 | 591 | 1,266 | 916 | 246 |
|  | Kat | 11,025 | 264 | 138 | 132 | 138 | 215 | 141 | 62 |
|  | ␣Kat | 11,025 | 656 | 368 | 203 | 380 | 605 | 489 | 126 |
| VCVC | kat | 11,025 | 1,744 | 925 | 700 | 1,032 | 1,723 | 1,226 | 466 |
|  | ␣kat | 11,025 | 654 | 197 | 137 | 261 | 517 | 384 | 81 |
|  | Kat | 11,025 | 73 | 45 | 48 | 45 | 62 | 46 | 27 |
|  | ␣Kat | 11,025 | 174 | 111 | 72 | 119 | 191 | 147 | 41 |
| CVCVC | kat | 231,525 | 655 | 393 | 470 | 452 | 731 | 424 | 155 |
|  | ␣kat | 231,525 | 2,104 | 820 | 586 | 1,027 | 1,952 | 1,368 | 363 |
|  | Kat | 231,525 | 284 | 174 | 169 | 175 | 254 | 149 | 50 |
|  | ␣Kat | 231,525 | 715 | 451 | 285 | 478 | 778 | 602 | 147 |

## 5. Agreement level × word filter

Cells are in the order `no filter / zipf < 3.0 / zipf < 2.0`. `Pass filter` is the number of forms that pass the word filter regardless of tokenization (`-` for large shapes where frequency was measured for only some forms).

| Shape | Spelling | Total | Pass filter (< 3.0 / < 2.0) | all 7 | all 6 except mistral_sp | 6 or more of 7 | 5 or more of 7 | claude_legacy alone | 2 tokens or fewer on all 7 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V | kat | 5 | 0 / 0 | 5 / 0 / 0 | 5 / 0 / 0 | 5 / 0 / 0 | 5 / 0 / 0 | 5 / 0 / 0 | 5 / 0 / 0 |
|  | ␣kat | 5 |  | 5 / 0 / 0 | 5 / 0 / 0 | 5 / 0 / 0 | 5 / 0 / 0 | 5 / 0 / 0 | 5 / 0 / 0 |
|  | Kat | 5 |  | 5 / 0 / 0 | 5 / 0 / 0 | 5 / 0 / 0 | 5 / 0 / 0 | 5 / 0 / 0 | 5 / 0 / 0 |
|  | ␣Kat | 5 |  | 5 / 0 / 0 | 5 / 0 / 0 | 5 / 0 / 0 | 5 / 0 / 0 | 5 / 0 / 0 | 5 / 0 / 0 |
| CV | kat | 105 | 2 / 0 | 96 / 1 / 0 | 102 / 1 / 0 | 102 / 1 / 0 | 103 / 1 / 0 | 104 / 1 / 0 | 105 / 2 / 0 |
|  | ␣kat | 105 |  | 88 / 0 / 0 | 95 / 0 / 0 | 96 / 0 / 0 | 100 / 1 / 0 | 97 / 0 / 0 | 105 / 2 / 0 |
|  | Kat | 105 |  | 50 / 0 / 0 | 86 / 0 / 0 | 86 / 0 / 0 | 89 / 0 / 0 | 98 / 1 / 0 | 105 / 2 / 0 |
|  | ␣Kat | 105 |  | 89 / 0 / 0 | 95 / 0 / 0 | 96 / 0 / 0 | 99 / 0 / 0 | 95 / 0 / 0 | 105 / 2 / 0 |
| VC | kat | 105 | 1 / 0 | 102 / 0 / 0 | 103 / 0 / 0 | 103 / 0 / 0 | 103 / 0 / 0 | 103 / 0 / 0 | 105 / 1 / 0 |
|  | ␣kat | 105 |  | 79 / 0 / 0 | 91 / 0 / 0 | 94 / 0 / 0 | 99 / 0 / 0 | 94 / 0 / 0 | 105 / 1 / 0 |
|  | Kat | 105 |  | 46 / 0 / 0 | 61 / 0 / 0 | 61 / 0 / 0 | 65 / 0 / 0 | 74 / 0 / 0 | 105 / 1 / 0 |
|  | ␣Kat | 105 |  | 64 / 0 / 0 | 73 / 0 / 0 | 75 / 0 / 0 | 84 / 0 / 0 | 73 / 0 / 0 | 105 / 1 / 0 |
| VV | kat | 25 | 0 / 0 | 24 / 0 / 0 | 25 / 0 / 0 | 25 / 0 / 0 | 25 / 0 / 0 | 25 / 0 / 0 | 25 / 0 / 0 |
|  | ␣kat | 25 |  | 9 / 0 / 0 | 16 / 0 / 0 | 16 / 0 / 0 | 20 / 0 / 0 | 19 / 0 / 0 | 25 / 0 / 0 |
|  | Kat | 25 |  | 2 / 0 / 0 | 6 / 0 / 0 | 6 / 0 / 0 | 7 / 0 / 0 | 10 / 0 / 0 | 25 / 0 / 0 |
|  | ␣Kat | 25 |  | 3 / 0 / 0 | 6 / 0 / 0 | 6 / 0 / 0 | 8 / 0 / 0 | 6 / 0 / 0 | 25 / 0 / 0 |
| CCV | kat | 2,205 | 1,787 / 1,099 | 56 / 14 / 2 | 88 / 26 / 3 | 107 / 33 / 4 | 148 / 53 / 11 | 195 / 83 / 20 | 2,110 / 1,692 / 1,007 |
|  | ␣kat | 2,205 |  | 65 / 14 / 1 | 88 / 23 / 1 | 90 / 23 / 1 | 131 / 40 / 1 | 117 / 37 / 5 | 2,071 / 1,656 / 973 |
|  | Kat | 2,205 |  | 16 / 1 / 0 | 30 / 2 / 0 | 31 / 3 / 0 | 37 / 4 / 0 | 58 / 12 / 1 | 2,035 / 1,625 / 945 |
|  | ␣Kat | 2,205 |  | 47 / 9 / 0 | 68 / 14 / 1 | 70 / 16 / 1 | 82 / 19 / 1 | 79 / 18 / 1 | 2,048 / 1,632 / 952 |
| CVC | kat | 2,205 | 907 / 493 | 547 / 41 / 5 | 655 / 59 / 7 | 692 / 68 / 8 | 818 / 93 / 15 | 900 / 128 / 26 | 2,199 / 901 / 487 |
|  | ␣kat | 2,205 |  | 610 / 32 / 0 | 728 / 50 / 1 | 785 / 59 / 1 | 977 / 95 / 3 | 762 / 59 / 2 | 2,196 / 898 / 484 |
|  | Kat | 2,205 |  | 212 / 6 / 0 | 348 / 8 / 0 | 350 / 8 / 0 | 402 / 11 / 0 | 463 / 21 / 2 | 2,169 / 874 / 462 |
|  | ␣Kat | 2,205 |  | 562 / 20 / 1 | 699 / 40 / 3 | 742 / 46 / 3 | 895 / 73 / 4 | 739 / 55 / 6 | 2,197 / 899 / 485 |
| CVV | kat | 525 | 154 / 69 | 51 / 2 / 0 | 84 / 3 / 0 | 89 / 3 / 0 | 117 / 5 / 0 | 138 / 11 / 4 | 524 / 153 / 68 |
|  | ␣kat | 525 |  | 46 / 0 / 0 | 64 / 0 / 0 | 77 / 1 / 0 | 117 / 2 / 1 | 75 / 2 / 0 | 523 / 152 / 67 |
|  | Kat | 525 |  | 8 / 0 / 0 | 25 / 0 / 0 | 25 / 0 / 0 | 33 / 0 / 0 | 35 / 0 / 0 | 519 / 151 / 67 |
|  | ␣Kat | 525 |  | 27 / 1 / 0 | 45 / 1 / 0 | 49 / 1 / 0 | 97 / 3 / 1 | 50 / 1 / 0 | 523 / 152 / 67 |
| VCC | kat | 2,205 | 1,687 / 1,034 | 340 / 125 / 21 | 383 / 149 / 26 | 410 / 168 / 31 | 472 / 206 / 41 | 486 / 218 / 48 | 2,157 / 1,639 / 986 |
|  | ␣kat | 2,205 |  | 126 / 20 / 4 | 161 / 28 / 5 | 172 / 33 / 5 | 232 / 57 / 6 | 205 / 51 / 7 | 1,960 / 1,445 / 807 |
|  | Kat | 2,205 |  | 55 / 4 / 0 | 82 / 8 / 0 | 84 / 9 / 0 | 96 / 9 / 0 | 99 / 12 / 1 | 1,691 / 1,195 / 608 |
|  | ␣Kat | 2,205 |  | 80 / 6 / 0 | 99 / 8 / 0 | 111 / 9 / 0 | 143 / 18 / 1 | 113 / 12 / 1 | 1,841 / 1,334 / 717 |
| VCV | kat | 525 | 207 / 90 | 246 / 44 / 11 | 280 / 58 / 16 | 300 / 65 / 19 | 339 / 80 / 23 | 292 / 61 / 17 | 516 / 198 / 84 |
|  | ␣kat | 525 |  | 31 / 2 / 1 | 57 / 3 / 1 | 58 / 3 / 1 | 87 / 6 / 1 | 68 / 4 / 1 | 499 / 184 / 70 |
|  | Kat | 525 |  | 7 / 1 / 1 | 14 / 1 / 1 | 15 / 1 / 1 | 24 / 2 / 1 | 26 / 3 / 1 | 487 / 175 / 64 |
|  | ␣Kat | 525 |  | 25 / 2 / 1 | 30 / 2 / 1 | 31 / 2 / 1 | 48 / 2 / 1 | 34 / 2 / 1 | 495 / 181 / 67 |
| CCVC | kat | 46,305 | - | 135 / 47 / 25 | 181 / 68 / 36 | 210 / 81 / 41 | 288 / 130 / 75 | 419 / 235 / 161 | 26,383 / 25,548 / 24,691 |
|  | ␣kat | 46,305 |  | 188 / 25 / 5 | 258 / 42 / 9 | 283 / 47 / 10 | 371 / 88 / 30 | 359 / 121 / 71 | 19,568 / 18,749 / 17,927 |
|  | Kat | 46,305 |  | 47 / 4 / 0 | 91 / 6 / 0 | 92 / 6 / 0 | 106 / 10 / 0 | 141 / 24 / 9 | 13,962 / 13,242 / 12,539 |
|  | ␣Kat | 46,305 |  | 106 / 12 / 0 | 163 / 20 / 2 | 169 / 21 / 3 | 231 / 40 / 7 | 201 / 34 / 7 | 14,872 / 14,095 / 13,351 |
| CVCC | kat | 46,305 | - | 341 / 66 / 21 | 431 / 81 / 29 | 465 / 95 / 34 | 608 / 137 / 53 | 839 / 271 / 135 | 19,510 / 17,512 / 15,845 |
|  | ␣kat | 46,305 |  | 550 / 78 / 25 | 721 / 121 / 44 | 771 / 138 / 49 | 978 / 230 / 101 | 810 / 173 / 74 | 21,105 / 19,066 / 17,323 |
|  | Kat | 46,305 |  | 138 / 11 / 1 | 240 / 18 / 1 | 242 / 18 / 1 | 278 / 25 / 4 | 333 / 42 / 12 | 11,384 / 9,527 / 8,146 |
|  | ␣Kat | 46,305 |  | 340 / 34 / 1 | 491 / 55 / 8 | 535 / 70 / 11 | 752 / 119 / 23 | 570 / 84 / 20 | 18,063 / 16,051 / 14,375 |
| CVCV | kat | 11,025 | 8,000 / 6,471 | 134 / 10 / 3 | 205 / 21 / 5 | 218 / 23 / 5 | 306 / 34 / 11 | 380 / 58 / 21 | 7,970 / 5,164 / 3,866 |
|  | ␣kat | 11,025 |  | 212 / 10 / 5 | 296 / 12 / 6 | 322 / 14 / 7 | 460 / 24 / 9 | 342 / 21 / 10 | 7,990 / 5,146 / 3,841 |
|  | Kat | 11,025 |  | 58 / 0 / 0 | 105 / 0 / 0 | 105 / 0 / 0 | 119 / 1 / 0 | 132 / 3 / 0 | 6,331 / 3,790 / 2,701 |
|  | ␣Kat | 11,025 |  | 110 / 0 / 0 | 175 / 0 / 0 | 187 / 1 / 1 | 301 / 2 / 1 | 203 / 8 / 3 | 7,444 / 4,685 / 3,431 |
| VCVC | kat | 11,025 | 10,113 / 9,547 | 383 / 225 / 148 | 534 / 324 / 220 | 584 / 355 / 242 | 809 / 491 / 341 | 700 / 448 / 315 | 10,034 / 9,130 / 8,571 |
|  | ␣kat | 11,025 |  | 65 / 15 / 8 | 107 / 32 / 20 | 115 / 37 / 23 | 173 / 60 / 38 | 137 / 51 / 32 | 7,302 / 6,469 / 5,950 |
|  | Kat | 11,025 |  | 23 / 4 / 0 | 34 / 4 / 0 | 34 / 4 / 0 | 39 / 4 / 0 | 48 / 7 / 2 | 4,893 / 4,164 / 3,721 |
|  | ␣Kat | 11,025 |  | 36 / 3 / 0 | 57 / 4 / 1 | 60 / 6 / 1 | 93 / 12 / 5 | 72 / 11 / 5 | 6,083 / 5,285 / 4,794 |
| CVCVC | kat | 231,525 | - | 104 / 25 / 17 | 162 / 41 / 29 | 176 / 47 / 33 | 266 / 76 / 54 | 470 / 201 / 145 | 58,606 / 54,623 / 51,843 |
|  | ␣kat | 231,525 |  | 304 / 46 / 26 | 470 / 71 / 43 | 500 / 84 / 50 | 678 / 125 / 83 | 586 / 147 / 93 | 65,978 / 61,626 / 58,599 |
|  | Kat | 231,525 |  | 48 / 4 / 0 | 114 / 8 / 2 | 115 / 9 / 3 | 143 / 13 / 4 | 169 / 28 / 14 | 27,143 / 24,501 / 22,639 |
|  | ␣Kat | 231,525 |  | 126 / 5 / 1 | 239 / 13 / 5 | 249 / 15 / 7 | 351 / 29 / 13 | 285 / 40 / 18 | 56,751 / 52,614 / 49,782 |

**For forms that are single tokens on exactly 6 of 7, the one tokenizer that failed** (no filter)

| Shape | Spelling | o200k | cl100k | claude_legacy | llama3 | llama4 | mistral_tekken | mistral_sp |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CV | kat | 0 | 0 | 0 | 0 | 0 | 0 | 6 |
|  | ␣kat | 0 | 0 | 1 | 0 | 0 | 0 | 7 |
|  | Kat | 0 | 0 | 0 | 0 | 0 | 0 | 36 |
|  | ␣Kat | 0 | 0 | 1 | 0 | 0 | 0 | 6 |
| VC | kat | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
|  | ␣kat | 0 | 0 | 3 | 0 | 0 | 0 | 12 |
|  | Kat | 0 | 0 | 0 | 0 | 0 | 0 | 15 |
|  | ␣Kat | 0 | 0 | 2 | 0 | 0 | 0 | 9 |
| VCV | kat | 0 | 1 | 19 | 0 | 0 | 0 | 34 |
|  | ␣kat | 0 | 0 | 1 | 0 | 0 | 0 | 26 |
|  | Kat | 0 | 0 | 1 | 0 | 0 | 0 | 7 |
|  | ␣Kat | 0 | 0 | 1 | 0 | 0 | 0 | 5 |
| VCC | kat | 0 | 1 | 19 | 0 | 0 | 7 | 43 |
|  | ␣kat | 0 | 1 | 9 | 0 | 1 | 0 | 35 |
|  | Kat | 0 | 0 | 1 | 0 | 0 | 1 | 27 |
|  | ␣Kat | 0 | 0 | 11 | 0 | 1 | 0 | 19 |
| CCV | kat | 0 | 1 | 9 | 0 | 0 | 9 | 32 |
|  | ␣kat | 0 | 0 | 1 | 0 | 0 | 1 | 23 |
|  | Kat | 0 | 0 | 1 | 0 | 0 | 0 | 14 |
|  | ␣Kat | 0 | 0 | 2 | 0 | 0 | 0 | 21 |
| CVC | kat | 1 | 4 | 17 | 0 | 0 | 15 | 108 |
|  | ␣kat | 0 | 2 | 54 | 0 | 0 | 1 | 118 |
|  | Kat | 0 | 0 | 1 | 0 | 0 | 1 | 136 |
|  | ␣Kat | 0 | 1 | 40 | 0 | 0 | 2 | 137 |
| CVCV | kat | 0 | 0 | 11 | 0 | 0 | 2 | 71 |
|  | ␣kat | 0 | 0 | 24 | 0 | 0 | 2 | 84 |
|  | Kat | 0 | 0 | 0 | 0 | 0 | 0 | 47 |
|  | ␣Kat | 0 | 0 | 12 | 0 | 0 | 0 | 65 |
| CVCC | kat | 0 | 1 | 18 | 0 | 1 | 14 | 90 |
|  | ␣kat | 0 | 0 | 47 | 0 | 2 | 1 | 171 |
|  | Kat | 0 | 0 | 0 | 0 | 0 | 2 | 102 |
|  | ␣Kat | 1 | 0 | 42 | 0 | 1 | 0 | 151 |

## 6. Productivity by letter

Single-token share (%) in CVC when the consonant is in the first position (C1) or the last position (C2). `mean` is the mean single-token share over the 7, `6+` is the share that is a single token on 6 or more of 7, and `claude` is the claude_legacy share. Rows are sorted by the sum of C1 6+ and C2 6+, largest first. No word filter is applied.

**CVC ␣kat**

| Consonant | C1 mean | C1 6+ | C1 claude | C2 mean | C2 6+ | C2 claude |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| r | 65 | 51 | 48 | 80 | 71 | 68 |
| t | 64 | 47 | 48 | 77 | 70 | 70 |
| n | 61 | 44 | 38 | 82 | 72 | 71 |
| l | 65 | 50 | 50 | 74 | 62 | 57 |
| d | 70 | 53 | 50 | 69 | 58 | 55 |
| m | 67 | 51 | 52 | 69 | 56 | 55 |
| s | 72 | 56 | 58 | 69 | 51 | 52 |
| b | 69 | 57 | 54 | 56 | 39 | 37 |
| g | 49 | 40 | 39 | 66 | 50 | 50 |
| p | 62 | 49 | 45 | 52 | 41 | 43 |
| c | 56 | 42 | 42 | 49 | 37 | 38 |
| v | 50 | 39 | 42 | 41 | 24 | 21 |
| f | 50 | 40 | 39 | 26 | 14 | 16 |
| h | 60 | 46 | 46 | 28 | 4 | 5 |
| w | 34 | 22 | 24 | 29 | 22 | 21 |
| k | 51 | 21 | 16 | 47 | 11 | 7 |
| j | 40 | 22 | 20 | 31 | 7 | 2 |
| z | 32 | 10 | 8 | 39 | 16 | 13 |
| y | 21 | 5 | 7 | 38 | 22 | 23 |
| x | 6 | 2 | 2 | 25 | 16 | 19 |
| q | 8 | 0 | 0 | 4 | 2 | 2 |

**CVC kat**

| Consonant | C1 mean | C1 6+ | C1 claude | C2 mean | C2 6+ | C2 claude |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| r | 83 | 75 | 73 | 76 | 65 | 70 |
| n | 58 | 43 | 53 | 83 | 77 | 84 |
| l | 67 | 50 | 59 | 70 | 57 | 70 |
| s | 49 | 37 | 57 | 75 | 66 | 71 |
| t | 47 | 33 | 53 | 71 | 61 | 70 |
| d | 54 | 43 | 55 | 62 | 49 | 58 |
| m | 51 | 44 | 53 | 60 | 41 | 61 |
| c | 46 | 36 | 47 | 44 | 31 | 50 |
| p | 47 | 35 | 50 | 41 | 32 | 47 |
| b | 55 | 44 | 54 | 38 | 22 | 39 |
| g | 38 | 26 | 39 | 42 | 30 | 46 |
| v | 41 | 30 | 41 | 30 | 18 | 34 |
| h | 53 | 38 | 50 | 20 | 6 | 9 |
| k | 42 | 24 | 27 | 41 | 18 | 19 |
| f | 39 | 27 | 39 | 22 | 9 | 22 |
| w | 30 | 20 | 25 | 21 | 13 | 20 |
| z | 33 | 17 | 20 | 26 | 14 | 20 |
| j | 39 | 25 | 34 | 20 | 7 | 6 |
| y | 16 | 7 | 10 | 28 | 19 | 24 |
| x | 13 | 5 | 16 | 27 | 21 | 32 |
| q | 5 | 0 | 2 | 9 | 3 | 6 |

**Vowels** (CVC by its middle vowel, VC and CV by the vowel they contain; share (%) of those forms that are single tokens on 6 or more of 7)

| Vowel | CVC␣ mean | CVC␣ 6+ | CVC mean | CVC 6+ | VC 6+ | VC␣ 6+ | CV 6+ | CV␣ 6+ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| a | 62 | 45 | 52 | 38 | 100 | 95 | 100 | 90 |
| e | 53 | 38 | 56 | 43 | 100 | 95 | 95 | 95 |
| i | 48 | 35 | 42 | 33 | 100 | 90 | 100 | 95 |
| o | 51 | 37 | 42 | 30 | 95 | 90 | 95 | 90 |
| u | 37 | 23 | 23 | 13 | 95 | 76 | 95 | 86 |

**Consonants in VC / CV** (share (%) that are single tokens on 6 or more of 7; only consonants not at 100)

| Consonant | VC | VC␣ | CV | CV␣ |
| --- | ---: | ---: | ---: | ---: |
| f | 100 | 80 | 100 | 100 |
| j | 100 | 60 | 100 | 100 |
| q | 60 | 20 | 60 | 40 |
| w | 100 | 80 | 100 | 80 |
| x | 100 | 80 | 80 | 40 |
| y | 100 | 80 | 100 | 60 |
| z | 100 | 80 | 100 | 100 |

In CVC ␣kat, the consonants with the highest 6+ share (mean of C1 and C2) are r 61%, t 59%, n 58%, l 56%, d 56%, m 54%, and the lowest are k 16%, j 14%, z 13%, y 13%, x 9%, q 1%. Vowels rank a 45%, e 38%, o 37%, i 35%, u 23%. Consonants whose 6+ share in the last position (C2) is at least 20 percentage points lower than in the first position (C1): f, h.

Per-tokenizer letter shares are in `letters` in inventory.json.

## 7. Shrinking the consonant set

Consonants were removed one at a time, starting with the one whose removal loses the fewest CVC forms that are single tokens at the given agreement level (no word filter). `Yield` is the share of single-token forms among all CVC forms that the remaining consonants can make; `Of which < 3.0` is the number that pass the word filter.

**CVC ␣kat, all 6 except mistral_sp**

| Consonants | Removed | Single token | All CVC | Yield % | Of which < 3.0 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 21 | - | 728 | 2,205 | 33 | 50 |
| 20 | q | 726 | 2,000 | 36 | 49 |
| 19 | x | 707 | 1,805 | 39 | 45 |
| 18 | j | 687 | 1,620 | 42 | 43 |
| 17 | z | 666 | 1,445 | 46 | 43 |
| 16 | k | 643 | 1,280 | 50 | 42 |
| 15 | y | 618 | 1,125 | 55 | 42 |
| 14 | w | 581 | 980 | 59 | 39 |
| 13 | h | 539 | 845 | 64 | 36 |
| 12 | f | 490 | 720 | 68 | 28 |
| 11 | v | 440 | 605 | 73 | 16 |
| 10 | c | 375 | 500 | 75 | 10 |

**CVC ␣kat, 6 or more of 7**

| Consonants | Removed | Single token | All CVC | Yield % | Of which < 3.0 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 21 | - | 785 | 2,205 | 36 | 59 |
| 20 | q | 783 | 2,000 | 39 | 58 |
| 19 | x | 764 | 1,805 | 42 | 54 |
| 18 | y | 736 | 1,620 | 45 | 54 |
| 17 | j | 708 | 1,445 | 49 | 51 |
| 16 | z | 681 | 1,280 | 53 | 50 |
| 15 | k | 651 | 1,125 | 58 | 49 |
| 14 | w | 612 | 980 | 62 | 45 |
| 13 | h | 567 | 845 | 67 | 41 |
| 12 | f | 515 | 720 | 72 | 32 |
| 11 | v | 458 | 605 | 76 | 19 |
| 10 | c | 392 | 500 | 78 | 13 |

**CVC kat, all 6 except mistral_sp**

| Consonants | Removed | Single token | All CVC | Yield % | Of which < 3.0 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 21 | - | 655 | 2,205 | 30 | 59 |
| 20 | q | 652 | 2,000 | 33 | 57 |
| 19 | x | 631 | 1,805 | 35 | 52 |
| 18 | y | 605 | 1,620 | 37 | 51 |
| 17 | j | 579 | 1,445 | 40 | 46 |
| 16 | z | 551 | 1,280 | 43 | 43 |
| 15 | w | 521 | 1,125 | 46 | 38 |
| 14 | f | 488 | 980 | 50 | 35 |
| 13 | k | 452 | 845 | 53 | 32 |
| 12 | h | 414 | 720 | 57 | 25 |
| 11 | v | 373 | 605 | 62 | 19 |
| 10 | g | 326 | 500 | 65 | 16 |

**CVC kat, 6 or more of 7**

| Consonants | Removed | Single token | All CVC | Yield % | Of which < 3.0 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 21 | - | 692 | 2,205 | 31 | 68 |
| 20 | q | 689 | 2,000 | 34 | 66 |
| 19 | x | 662 | 1,805 | 37 | 58 |
| 18 | y | 635 | 1,620 | 39 | 57 |
| 17 | j | 604 | 1,445 | 42 | 50 |
| 16 | z | 572 | 1,280 | 45 | 46 |
| 15 | w | 539 | 1,125 | 48 | 39 |
| 14 | f | 505 | 980 | 52 | 36 |
| 13 | h | 465 | 845 | 55 | 29 |
| 12 | k | 425 | 720 | 59 | 26 |
| 11 | v | 383 | 605 | 63 | 19 |
| 10 | g | 335 | 500 | 67 | 16 |

**Proposal (criterion: the smallest set that keeps at least 95% of the single-token forms)**

- CVC ␣kat, all 6 except mistral_sp: 19 consonants `bcdfghjklmnprstvwyz` (removed `qx`) → single tokens 707/728, yield 33% → 39%, pass word filter 50 → 45
- CVC ␣kat, 6 or more of 7: 19 consonants `bcdfghjklmnprstvwyz` (removed `qx`) → single tokens 764/785, yield 36% → 42%, pass word filter 59 → 54
- CVC kat, all 6 except mistral_sp: 19 consonants `bcdfghjklmnprstvwyz` (removed `qx`) → single tokens 631/655, yield 30% → 35%, pass word filter 59 → 52
- CVC kat, 6 or more of 7: 19 consonants `bcdfghjklmnprstvwyz` (removed `qx`) → single tokens 662/692, yield 31% → 37%, pass word filter 68 → 58

Shrinking the consonant set does not increase the absolute number of single-token forms. If forms are picked from a list, shrinking gains nothing in count; the only gains are a shorter spec and possibly less boundary instability in glued strings (to be checked in E2).

## 8. Form list preview

The full lists are in `lists` in inventory.json (shape → spelling → `all7_lt3`, `no_sp_lt3`, `ge6_lt3`; each entry is [form, max zipf]). Below are the first 40 in alphabetical order.

- VC kat, all 7, zipf < 3.0 (0 forms): none
- VCV kat, all 7, zipf < 3.0 (44 forms): aco aho ake aqu avo awi aze azi azu enu equ ibe ifi igi igu ija ije iji ime iqu iro ixa ize obe oci oga oge ogo olo ope ote ube uce uga uge ugu ule ulo ume ura
- VCC kat, all 7, zipf < 3.0 (125 forms): acy adr adt agn ahr aky ald aml amm anz aph apy arb arl atz avy awk awn axy ays azy ekt ell elt emb emy enc enn eny erv esh ety etz exc ibr icl icz idx idy iff
- VCVC kat, all 7, zipf < 3.0 (225 forms): aban abet abil abol aced acon aded ades ador adow ager agon ahan aked akes akov aled alen aler amic anes anim aped aper apon ared aret ased aser asis ason atal ated ateg ater atic atin atis ativ aton
- CVC kat, all 7, zipf < 3.0 (41 forms): buf ced cer cil cov cur ded gom gos gow hed hib hir hom jav jud ked ker kov mov mul neg rac ral reb req rew ril ror rov rup vec veh vey wid wor xic xit zej zek
- CVC ␣kat, all 7, zipf < 3.0 (32 forms): buf cer cig cov cur fid fif fos hom jud ker lod lum mov mul neg nob rac rav reb req suc tob vac vec veh vig viv vot wid wor wur
- CVC ␣kat, all 6 except mistral_sp, zipf < 3.0 (50 forms): bif buf cer cif cig cov cur dob fid fif foc fos fug gid hil hom jav jud ker lod lum mav mov muc mul neg nob nud piv pix rac rav reb req suc tob tox vac vap vec
- CVCC ␣kat, all 7, zipf < 3.0 (78 forms): bapt barg batt bicy calc camb cand circ coff cogn conc cond conj conv cort cosm curr cush cust decl desc desp dest dict dign disg dist fant forg foss fost func furn hadn hasn horm kidn larg lect magn
- CCVC kat, all 7, zipf < 3.0 (47 forms): blem bler bles brid ched ches cker cles cret crit ctic ctor ffen ffic flix frac ften fter ghan gres href json ktop ndef nder nten phan pler plex plit pped prec pred prev ptic pton sson sted ston thal
- CVCVC ␣kat, all 7, zipf < 3.0 (46 forms): benef capac catal citiz conoc coron debug decid dedic deleg delet demol denom depos deriv difer dimin divid divis divor domin famil femin gover javax manip memor milit navig neces nomin polic popul posit recip regex regul relig renov reput

## 9. Limitations

- The current Claude tokenizer is not public. There is no guarantee that claude_legacy results apply as is to current Claude.
- Only single-token status was measured. Whether morpheme boundaries match token boundaries inside glued strings was not measured (E2).
- The word filter looks only at frequencies in 11 languages. Overlaps with romanized Korean, Japanese or Chinese, abbreviations, trademarks and programming identifiers are not filtered out.
- For short letter strings, wordfreq also counts the frequency of abbreviations, names and fragments of other languages. So the shorter the shape, the more forms the filter removes, and zipf ≥ 3.0 does not guarantee that every such form carries a strong meaning for an LLM. The actual size of semantic interference cannot be measured without a model API.
- Even a single token can be tied to a specific meaning in the training data (a name, an abbreviation, a code fragment). This experiment cannot measure that either.
