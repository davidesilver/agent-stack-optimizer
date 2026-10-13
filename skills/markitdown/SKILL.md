---
name: markitdown
description: Convert PDF, Word, PowerPoint, Excel, EPUB, HTML, CSV/JSON/XML, ZIP, images (OCR/EXIF), audio and YouTube URLs to Markdown with Microsoft markitdown before reading them. Use when a file is not plain text, or to turn a document into text for analysis or the wiki.
---
<!-- agent-stack-managed-v1 -->

# markitdown

CLI by Microsoft (`markitdown`, MIT). Converts a file or URL to Markdown that keeps headings, lists, tables and links. Cheaper than reading the binary or its images.

```sh
markitdown FILE.docx                 # Markdown to stdout
markitdown FILE.xlsx -o out.md       # write to a file
```

- Prefer `-o` on Windows: console encoding can garble accents on stdout (or set `PYTHONUTF8=1`).
- Long output: save with `-o` to a scratch path, then read only the needed part.
- Scanned PDFs have no text layer: markitdown returns nothing useful. Read the original PDF instead.
- Image data URIs are truncated by default. Use `--keep-data-uris` only if you need them.
- Do not use for graphs, signatures or page layout: those need the original file.
- Plugins and Azure Document Intelligence (`-d -e ENDPOINT`) are optional and not enabled here.

Install if missing: `uv tool install "markitdown[pdf,docx,pptx,xlsx,xls,outlook]"` (or `pipx install`). Check: `markitdown --version`.

The `pdf` module's Read hook already converts `.docx .pptx .xlsx .xls .epub` for you; use this skill for everything else and for explicit conversions.
