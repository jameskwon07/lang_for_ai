"""A module that exposes several LLM tokenizers through one interface.

Run `python3 fetch_tokenizers.py` first to download the tokenizer files.

    from toklib import load_all
    toks = load_all()
    for t in toks.values():
        print(t.name, t.count("katenmirob"), t.pieces("katenmirob"))

Every tokenizer provides:
- count(text)       number of tokens
- pieces(text)      list of token piece strings. Joined, they equal the input (for ASCII input)
- boundaries(text)  set of character positions where a token starts (includes 0 and len(text))

The current Claude tokenizer is not public. claude_legacy is the Claude 2-era tokenizer and is used only as a proxy.
"""

from __future__ import annotations

import base64
import json
from functools import lru_cache
from pathlib import Path

import tiktoken
from tiktoken.load import load_tiktoken_bpe

CACHE = Path(__file__).resolve().parent / ".cache" / "tokenizers"

# Pre-tokenization regexes for tiktoken-based tokenizers
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
    """Common tokenizer interface."""

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
        """Token start positions (in characters). Assumes ASCII input."""
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
    """Hugging Face tokenizers format (ByteLevel BPE)."""

    def __init__(self, name: str, description: str, path: Path):
        from tokenizers import Tokenizer

        self.name, self.description = name, description
        self._tok = Tokenizer.from_file(str(path))
        self.vocab_size = self._tok.get_vocab_size()
        # Reverse mapping from GPT-2 ByteLevel characters to bytes
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
    """SentencePiece format. The dummy prefix space (▁) added before the text is stripped from the first piece."""

    def __init__(self, name: str, description: str, path: Path):
        import sentencepiece as spm

        self.name, self.description = name, description
        self._sp = spm.SentencePieceProcessor(model_file=str(path))
        self.vocab_size = self._sp.get_piece_size()

    def _piece_bytes(self, text: str) -> list[bytes]:
        out = []
        for p in self._sp.encode(text, out_type=str):
            if len(p) == 6 and p.startswith("<0x") and p.endswith(">"):
                out.append(bytes([int(p[3:5], 16)]))  # byte fallback piece
            else:
                out.append(p.replace("▁", " ").encode("utf-8"))
        if out and not text.startswith(" ") and out[0].startswith(b" "):
            # A token made only of the dummy space is still a token the model actually sees, so it stays in the count as an empty piece
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
        raise FileNotFoundError(f"Tokenizer files are missing: {missing}. Run python3 fetch_tokenizers.py first.")
    toks: list[Tok] = [
        _tiktoken_file("o200k", "o200k_base.tiktoken", _O200K_PAT, "OpenAI GPT-4o / o-series / GPT-5 family (200K)"),
        _tiktoken_file("cl100k", "cl100k_base.tiktoken", _CL100K_PAT, "OpenAI GPT-4 / GPT-3.5 (100K)"),
        HFTok("claude_legacy", "Anthropic Claude 2-era tokenizer (65K, proxy for the current Claude)", CACHE / "claude_legacy.json"),
        _tiktoken_file("llama3", "llama3.tiktoken", _LLAMA3_PAT, "Meta Llama 3 (128K)"),
        _tiktoken_file("llama4", "llama4.tiktoken", _O200K_PAT, "Meta Llama 4 (200K)"),
        _tekken("mistral_tekken", "mistral_tekken_240911.json", "Mistral Tekken (Nemo and later, 131K)"),
        SentencePieceTok("mistral_sp", "Mistral SentencePiece v3 (7B family, 32K)", CACHE / "mistral_sp_v3.model"),
    ]
    return {t.name: t for t in toks}


if __name__ == "__main__":
    # The last sample is a Korean sentence used as tokenizer input data; it stays in Korean.
    samples = ["The user sent the file to me.", "katenmirob", " kat en mir ob", "사용자가 파일을 나에게 보냈다."]
    for t in load_all().values():
        print(f"{t.name:15} vocab={t.vocab_size:>7}")
        for s in samples:
            print(f"    {t.count(s):>3}  {t.pieces(s)}")
