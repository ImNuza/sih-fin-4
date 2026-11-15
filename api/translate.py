"""Translate the assistant's English replies into Malay or Tamil, on this machine.

A general 8B model writes poor Tamil, so for those languages the local model answers in English
and NLLB-200 (Meta's translation model, distilled 600M, int8 through CTranslate2) translates it.
Line by line, so lists and bold stay in place; S$ amounts and numbers are kept as they are.
Chinese is not routed here: the local model writes it well and NLLB does not.
The model (TRANSLATION_MODEL, about 600 MB) downloads on first use. Its licence is CC-BY-NC-4.0:
fine for this prototype, but a launch would need a commercial translator.
"""

from __future__ import annotations

import os
import re
import threading
from functools import lru_cache

MODEL_REPO = os.environ.get("TRANSLATION_MODEL", "JustFrederik/nllb-200-distilled-600M-ct2-int8")
CODES = {"en": "eng_Latn", "ms": "zsm_Latn", "ta": "tam_Taml", "zh": "zho_Hans"}
_lock = threading.Lock()
# Emoji and other pictographs: NLLB has no tokens for them and writes "⁇".
SYMBOLS = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]")


def installed() -> bool:
    try:
        import ctranslate2  # noqa: F401
        import sentencepiece  # noqa: F401
    except ImportError:
        return False
    return True


@lru_cache(maxsize=1)
def model():
    import ctranslate2
    import sentencepiece
    from huggingface_hub import snapshot_download

    path = snapshot_download(MODEL_REPO)
    tokenizer = sentencepiece.SentencePieceProcessor(model_file=f"{path}/sentencepiece.bpe.model")
    return ctranslate2.Translator(path, device="cpu", compute_type="int8"), tokenizer


def tidy(text: str) -> str:
    """Undo NLLB's spacing inside amounts: 'S $ 16.11' -> 'S$16.11', '3 , 000' -> '3,000'."""
    text = re.sub(r"S\s*\$\s*", "S$", text)
    return re.sub(r"(\d)\s*([.,])\s*(\d)", r"\1\2\3", text)


def translate(text: str, language: str) -> str:
    """text in English, translated to language. Unchanged for English or an unknown language."""
    if language == "en" or language not in CODES or not text.strip():
        return text
    translator, tokenizer = model()
    lines = text.split("\n")
    # Keep each line's list marker and bold markers outside the translation.
    parts = []
    for line in lines:
        match = re.match(r"^(\s*(?:[-*•]|\d+\.)\s+)?([^\w\s(*]*\s*)(.*)$", line)
        prefix = (match.group(1) or "") + match.group(2)
        body = SYMBOLS.sub("", match.group(3).replace("**", ""))
        parts.append((prefix, body))
    to_translate = [body for _, body in parts if body.strip()]
    if not to_translate:
        return text
    source = [["eng_Latn"] + tokenizer.encode(body, out_type=str) + ["</s>"] for body in to_translate]
    with _lock:
        results = translator.translate_batch(
            source, target_prefix=[[CODES[language]]] * len(source), beam_size=4,
            max_decoding_length=256,
        )
    translated = iter(tidy(tokenizer.decode(r.hypotheses[0][1:])).replace("⁇", "").strip()
                      for r in results)
    return "\n".join(prefix + next(translated) if body.strip() else prefix + body
                     for prefix, body in parts)
