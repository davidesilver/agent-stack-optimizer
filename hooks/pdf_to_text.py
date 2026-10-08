#!/usr/bin/env python3
"""PreToolUse hook (matcher: Read): un PDF letto con il Read nativo manda ogni pagina come testo E
come immagine. Qui il Read viene riscritto (updatedInput) per puntare a un .txt estratto: nessun
blocco, nessun secondo giro. Tecnica da Riccardo Belli Contarini ("Come Risparmiare Tokens").

Vie d'uscita (un hook che trasforma i dati non deve mai chiudere la porta al dato vero):
1. PDF-immagine (meno di 200 caratteri a pagina): passa il PDF originale.
2. Serve il visivo (grafici, firme, layout): `touch ~/.claude/pdf-visual-once`, poi rileggi il PDF;
   il file viene cancellato e il PDF passa intero una sola volta. Lo dice anche l'intestazione del .txt.
3. Estrazione fallita o libreria mancante: esce in silenzio e il Read normale fa il suo lavoro.

Richiede pypdf (pip install pypdf) oppure pdftotext (poppler) nel PATH.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

MIN_CHARS_PER_PAGE = 200
CACHE = Path.home() / ".claude" / "pdf-text-cache"
SENTINEL = Path.home() / ".claude" / "pdf-visual-once"
MAX_AGE_DAYS = 30


def extract(pdf: Path):
    try:
        from pypdf import PdfReader
        r = PdfReader(str(pdf))
        pages = len(r.pages)
        body = "\n\n".join(f"--- pagina {i + 1} ---\n{(p.extract_text() or '').strip()}" for i, p in enumerate(r.pages))
        return pages, body, "pypdf"
    except Exception:
        pass
    exe = shutil.which("pdftotext")
    if exe:
        out = subprocess.run([exe, "-layout", str(pdf), "-"], capture_output=True, text=True, encoding="utf-8", errors="ignore")
        if out.returncode == 0:
            return out.stdout.count("\f") + 1, out.stdout, "pdftotext -layout"
    return 0, "", ""


def clean_cache():
    cutoff = time.time() - MAX_AGE_DAYS * 86400
    for f in CACHE.glob("*.txt"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            pass


def main():
    try:
        data = json.load(sys.stdin)
        if data.get("tool_name") != "Read":
            return 0
        tool_input = dict(data.get("tool_input") or {})
        pdf = Path(tool_input.get("file_path", ""))
        if pdf.suffix.lower() != ".pdf" or not pdf.is_file():
            return 0
        if SENTINEL.exists():
            SENTINEL.unlink()
            return 0  # via d'uscita 2: PDF intero una volta sola

        st = pdf.stat()
        key = hashlib.sha1(f"{pdf.resolve()}|{st.st_mtime_ns}|{st.st_size}".encode()).hexdigest()[:16]
        CACHE.mkdir(parents=True, exist_ok=True)
        clean_cache()
        txt = CACHE / f"{key}.txt"
        if not txt.exists():
            pages, body, how = extract(pdf)
            if pages == 0 or len(body) < MIN_CHARS_PER_PAGE * pages:
                return 0  # via d'uscita 1 e 3
            header = (
                f"[Testo estratto da {pdf.name}: {pages} pagine, metodo {how}. Le immagini del PDF NON sono incluse. "
                f"Per vedere grafici, firme o layout: esegui `touch ~/.claude/pdf-visual-once` e rileggi il PDF originale.]\n\n"
            )
            txt.write_text(header + body, encoding="utf-8")
        pages_note = txt.read_text(encoding="utf-8", errors="ignore")[:120]
        tool_input["file_path"] = str(txt)
        tool_input.pop("pages", None)
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "updatedInput": tool_input,
            },
            "systemMessage": f"PDF {pdf.name} letto come testo (cache {txt.name}). Per il PDF visivo: touch ~/.claude/pdf-visual-once e rileggi.",
        }))
    except Exception:
        return 0  # via d'uscita 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
