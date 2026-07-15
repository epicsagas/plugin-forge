#!/usr/bin/env python3
"""i18n_translate.py — regenerate docs/i18n/<lang>/README.md from README.md.

Called by .github/workflows/i18n-translate.yml. Uses any OpenAI-compatible
chat completions endpoint (Anthropic, OpenAI, or a gateway).

Env vars:
  LLM_API_KEY   API key (required)
  LLM_BASE_URL  OpenAI-compatible endpoint base, e.g. https://api.anthropic.com/v1
  LLM_MODEL     model id, e.g. claude-sonnet-5, gpt-4o-mini

Usage:
  python3 scripts/i18n_translate.py            # translate all non-EN languages
  python3 scripts/i18n_translate.py ja ko      # translate a subset
"""
from __future__ import annotations
import json
import os
import sys
import urllib.request
from pathlib import Path

ALL_LANGS = ["ja", "zh-Hans", "zh-Hant", "es", "fr", "de", "pt", "ru", "it", "ko"]
LANG_NAMES = {
    "ja": "Japanese", "zh-Hans": "Simplified Chinese", "zh-Hant": "Traditional Chinese",
    "es": "Spanish", "fr": "French", "de": "German",
    "pt": "Portuguese", "ru": "Russian", "it": "Italian", "ko": "Korean",
}
ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "README.md"

SYSTEM = """You are a professional technical translator for open-source documentation.
Translate the user-provided Markdown document to the target language.
Rules:
- Preserve ALL Markdown formatting exactly (headings, tables, lists, blockquotes).
- Do NOT translate fenced code blocks — keep them byte-for-byte.
- Do NOT translate URLs, image paths, or badge markdown links.
- Keep the language switcher line at the top; provide a relative link back to
  ../../../README.md for English.
- Keep technical terms (Claude Code, Codex, agy, manifest, SKILL, marketplace,
  doctor, publish, plugin-forge) in English where the local convention prefers it.
- Add a one-line HTML comment near the top noting the English README.md is
  the authoritative source.
- Do not add commentary outside the translated document."""


def translate(text: str, lang: str) -> str:
    api_key = os.environ["LLM_API_KEY"]
    base = os.environ["LLM_BASE_URL"].rstrip("/")
    model = os.environ["LLM_MODEL"]
    name = LANG_NAMES[lang]
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Translate this Markdown to {name}.\n\n{text}"},
        ],
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


def main(argv: list[str]) -> int:
    if not SOURCE.exists():
        print(f"ERROR: source {SOURCE} not found", file=sys.stderr)
        return 1
    missing = [v for v in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL") if not os.environ.get(v)]
    if missing:
        print(f"ERROR: missing env: {', '.join(missing)}", file=sys.stderr)
        return 2

    langs = argv or ALL_LANGS
    src = SOURCE.read_text(encoding="utf-8")
    for lang in langs:
        if lang not in LANG_NAMES:
            print(f"WARN: unknown language {lang}, skipping", file=sys.stderr)
            continue
        out = ROOT / "docs" / "i18n" / lang / "README.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        print(f"Translating {lang} -> {out.relative_to(ROOT)}")
        result = translate(src, lang)
        out.write_text(result, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
