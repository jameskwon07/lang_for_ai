"""Extracts tokenizer files from PyPI packages and saves them to .cache/tokenizers/.

It downloads pinned versions of PyPI packages that bundle the same files,
so the results can be reproduced even where the original tokenizer sources
(openaipublic, Hugging Face) are unreachable.
File integrity is checked with SHA-256. The o200k/cl100k hashes match tiktoken's official expected_hash.

Usage: python3 fetch_tokenizers.py
"""

import hashlib
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

CACHE = Path(__file__).resolve().parent / ".cache" / "tokenizers"

# (pip requirement, extra pip arguments, path inside the wheel, saved name, sha256)
FILES = [
    ("litellm==1.104.1",
     ["--platform", "manylinux_2_28_x86_64", "--python-version", "3.10", "--only-binary=:all:"],
     "litellm/litellm_core_utils/tokenizers/fb374d419588a4632f3f557e76b4b70aebbca790",
     "o200k_base.tiktoken",
     "446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d"),
    ("litellm==1.104.1",
     ["--platform", "manylinux_2_28_x86_64", "--python-version", "3.10", "--only-binary=:all:"],
     "litellm/litellm_core_utils/tokenizers/9b5ad71b2ce5302211f9c61530b329a4922fc6a4",
     "cl100k_base.tiktoken",
     "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7"),
    ("litellm==1.104.1",
     ["--platform", "manylinux_2_28_x86_64", "--python-version", "3.10", "--only-binary=:all:"],
     "litellm/litellm_core_utils/tokenizers/anthropic_tokenizer.json",
     "claude_legacy.json",
     "c241737df24b4e7f7c9af4fdcee29a0ca903dcb288a8b753bc346a3092911767"),
    ("llama-models==0.3.0", [],
     "llama_models/llama3/tokenizer.model",
     "llama3.tiktoken",
     "82e9d31979e92ab929cd544440f129d9ecd797b69e327f80f17e1c50d5551b55"),
    ("llama-models==0.3.0", [],
     "llama_models/llama4/tokenizer.model",
     "llama4.tiktoken",
     "d0bdbaf59b0762c8c807617e2d8ea51420eb1b1de266df2495be755c8e0ed6ed"),
    ("mistral-common==1.12.0", [],
     "mistral_common/data/tekken_240911.json",
     "mistral_tekken_240911.json",
     "1948e2d48b0e7377f1bb5f1210f1ae5f984934e75713fc07e2452729b8365316"),
    ("mistral-common==1.12.0", [],
     "mistral_common/data/mistral_instruct_tokenizer_240323.model.v3",
     "mistral_sp_v3.model",
     "9addc8bdce5988448ae81b729336f43a81262160ae8da760674badab9d4c7d33"),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    CACHE.mkdir(parents=True, exist_ok=True)
    todo = [f for f in FILES if not ((CACHE / f[3]).exists() and sha256(CACHE / f[3]) == f[4])]
    if not todo:
        print(f"all tokenizer files present in {CACHE}")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        for req, extra in {(f[0], tuple(f[1])) for f in todo}:
            print(f"downloading {req} ...")
            subprocess.run([sys.executable, "-m", "pip", "download", "--no-deps", "-q", "-d", tmp, req, *extra],
                           check=True)
        wheels = list(Path(tmp).glob("*.whl"))
        for req, _, inner, name, digest in todo:
            pkg = req.split("==")[0].replace("-", "_")
            wheel = next(w for w in wheels if w.name.startswith(pkg))
            with zipfile.ZipFile(wheel) as z:
                data = z.read(inner)
            if hashlib.sha256(data).hexdigest() != digest:
                print(f"hash mismatch for {name}", file=sys.stderr)
                return 1
            (CACHE / name).write_bytes(data)
            print(f"saved {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
