"""여러 LLM 토크나이저를 같은 인터페이스로 다루는 모듈.

먼저 `python3 fetch_tokenizers.py` 로 토크나이저 파일을 받아야 한다.

    from toklib import load_all
    toks = load_all()
    for t in toks.values():
        print(t.name, t.count("katenmirob"), t.pieces("katenmirob"))

모든 토크나이저는 다음을 제공한다.
- count(text)       토큰 수
- pieces(text)      토큰 조각 문자열 목록. 이어 붙이면 원문과 같다 (ASCII 입력 기준)
- boundaries(text)  토큰이 시작하는 문자 위치 집합 (0과 len(text) 포함)

현행 Claude 토크나이저는 공개되지 않았다. claude_legacy 는 Claude 2 시절 토크나이저로, 대용 지표로만 쓴다.
"""

from __future__ import annotations

import base64
import json
from functools import lru_cache
from pathlib import Path

import tiktoken
from tiktoken.load import load_tiktoken_bpe

CACHE = Path(__file__).resolve().parent / ".cache" / "tokenizers"

# tiktoken 계열 토크나이저의 사전 분할(pre-tokenization) 정규식
_O200K_PAT = "|".join([
    r"""[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}]*[\p{Ll}\p{Lm}\p{Lo}\p{M}]+(?i:'s|'t|'re|'ve|'m|'ll|'d)?""",
    r"""[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}]+[\p{Ll}\p{Lm}\p{Lo}\p{M}]*(?i:'s|'t|'re|'ve|'m|'ll|'d)?""",
    r"""\p{N}{1,3}""",
    r""" ?[^\s\p{L}\p{N}]+[\r\n/]*""",
    r"""\s*[\r\n]+""",
    r"""\s+(?!\S)""",
    r"""\s+""",
])
_CL100K_PAT = r"""'(?i:[sdmt]|ll|ve|re)|[^\r\n\p{L}\p{N}]?+\p{L}++|\p{N}{1,3}+| ?[^\s\p{L}\p{N}]++[\r\n]*+|\s++$|\s*[\r\n]|\s+(?!\S)|\s"""
_LLAMA3_PAT = r"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\n\p{L}\p{N}]?\p{L}+|\p{N}{1,3}| ?[^\s\p{L}\p{N}]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+"


class Tok:
    """토크나이저 공통 인터페이스."""

    name: str
    description: str
    vocab_size: int

    def _piece_bytes(self, text: str) -> list[bytes]:
        raise NotImplementedError

    def pieces(self, text: str) -> list[str]:
        return [b.decode("utf-8", errors="replace") for b in self._piece_bytes(text)]

    def count(self, text: str) -> int:
        return len(self._piece_bytes(text))

    def boundaries(self, text: str) -> set[int]:
        """토큰 시작 위치(문자 단위). ASCII 입력을 가정한다."""
        out, pos = {0}, 0
        for p in self.pieces(text):
            pos += len(p)
            out.add(pos)
        return out

    def is_single_token(self, text: str) -> bool:
        return self.count(text) == 1

    def __repr__(self) -> str:
        return f"<Tok {self.name} vocab={self.vocab_size}>"


class TiktokenTok(Tok):
    def __init__(self, name: str, description: str, enc: tiktoken.Encoding):
        self.name, self.description, self._enc = name, description, enc
        self.vocab_size = enc.n_vocab

    def _piece_bytes(self, text: str) -> list[bytes]:
        return [self._enc.decode_single_token_bytes(t) for t in self._enc.encode_ordinary(text)]


class HFTok(Tok):
    """Hugging Face tokenizers 형식 (ByteLevel BPE)."""

    def __init__(self, name: str, description: str, path: Path):
        from tokenizers import Tokenizer

        self.name, self.description = name, description
        self._tok = Tokenizer.from_file(str(path))
        self.vocab_size = self._tok.get_vocab_size()
        # GPT-2 ByteLevel 문자 → 바이트 역매핑
        bs = list(range(ord("!"), ord("~") + 1)) + list(range(ord("¡"), ord("¬") + 1)) + list(range(ord("®"), ord("ÿ") + 1))
        cs = bs[:]
        n = 0
        for b in range(256):
            if b not in bs:
                bs.append(b)
                cs.append(256 + n)
                n += 1
        self._byte_of = {chr(c): b for b, c in zip(bs, cs)}

    def _piece_bytes(self, text: str) -> list[bytes]:
        enc = self._tok.encode(text, add_special_tokens=False)
        return [bytes(self._byte_of[ch] for ch in tok) for tok in enc.tokens]


class SentencePieceTok(Tok):
    """SentencePiece 형식. 문장 앞에 붙는 가짜 공백(▁)은 첫 조각에서 떼어 낸다."""

    def __init__(self, name: str, description: str, path: Path):
        import sentencepiece as spm

        self.name, self.description = name, description
        self._sp = spm.SentencePieceProcessor(model_file=str(path))
        self.vocab_size = self._sp.get_piece_size()

    def _piece_bytes(self, text: str) -> list[bytes]:
        out = []
        for p in self._sp.encode(text, out_type=str):
            if len(p) == 6 and p.startswith("<0x") and p.endswith(">"):
                out.append(bytes([int(p[3:5], 16)]))  # byte fallback 조각
            else:
                out.append(p.replace("▁", " ").encode("utf-8"))
        if out and not text.startswith(" ") and out[0].startswith(b" "):
            # 가짜 공백만으로 된 토큰도 모델이 실제로 보는 토큰이므로 빈 조각으로 개수에 남긴다
            out[0] = out[0][1:]
        return out


def _tiktoken_file(name: str, filename: str, pat: str, description: str) -> TiktokenTok:
    ranks = load_tiktoken_bpe(str(CACHE / filename))
    return TiktokenTok(name, description, tiktoken.Encoding(name=name, pat_str=pat, mergeable_ranks=ranks, special_tokens={}))


def _tekken(name: str, filename: str, description: str) -> TiktokenTok:
    data = json.loads((CACHE / filename).read_text())
    cfg = data["config"]
    inner = cfg["default_vocab_size"] - cfg["default_num_special_tokens"]
    ranks = {base64.b64decode(v["token_bytes"]): v["rank"] for v in data["vocab"][:inner]}
    enc = tiktoken.Encoding(name=name, pat_str=cfg["pattern"], mergeable_ranks=ranks, special_tokens={})
    return TiktokenTok(name, description, enc)


@lru_cache(maxsize=1)
def load_all() -> dict[str, Tok]:
    missing = [p for p in ["o200k_base.tiktoken", "cl100k_base.tiktoken", "claude_legacy.json", "llama3.tiktoken",
                           "llama4.tiktoken", "mistral_tekken_240911.json", "mistral_sp_v3.model"]
               if not (CACHE / p).exists()]
    if missing:
        raise FileNotFoundError(f"토크나이저 파일이 없습니다: {missing}. 먼저 python3 fetch_tokenizers.py 를 실행하세요.")
    toks: list[Tok] = [
        _tiktoken_file("o200k", "o200k_base.tiktoken", _O200K_PAT, "OpenAI GPT-4o / o-series / GPT-5 계열 (200K)"),
        _tiktoken_file("cl100k", "cl100k_base.tiktoken", _CL100K_PAT, "OpenAI GPT-4 / GPT-3.5 (100K)"),
        HFTok("claude_legacy", "Anthropic Claude 2 시절 토크나이저 (65K, 현행 Claude의 대용)", CACHE / "claude_legacy.json"),
        _tiktoken_file("llama3", "llama3.tiktoken", _LLAMA3_PAT, "Meta Llama 3 (128K)"),
        _tiktoken_file("llama4", "llama4.tiktoken", _O200K_PAT, "Meta Llama 4 (200K)"),
        _tekken("mistral_tekken", "mistral_tekken_240911.json", "Mistral Tekken (Nemo 이후, 131K)"),
        SentencePieceTok("mistral_sp", "Mistral SentencePiece v3 (7B 계열, 32K)", CACHE / "mistral_sp_v3.model"),
    ]
    return {t.name: t for t in toks}


if __name__ == "__main__":
    samples = ["The user sent the file to me.", "katenmirob", " kat en mir ob", "사용자가 파일을 나에게 보냈다."]
    for t in load_all().values():
        print(f"{t.name:15} vocab={t.vocab_size:>7}")
        for s in samples:
            print(f"    {t.count(s):>3}  {t.pieces(s)}")
