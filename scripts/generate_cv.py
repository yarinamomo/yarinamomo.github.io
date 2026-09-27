#!/usr/bin/env python3
"""Generate cv.html and publications.html from the Overleaf LaTeX CV (``curve`` class).

The .bib file of the CV is the only list of publications: the Publications page
shows the same list as the CV's publication section.

Usage, from the repository root:

    python scripts/generate_cv.py
    python scripts/generate_cv.py --source path/to/CV.zip --output cv.html

``--source`` accepts the Overleaf .zip export or an extracted folder.

Everything is read from the LaTeX project, so the web CV follows the PDF:

* The header (name and contact fields) comes from ``\\leftheader{...}``.
* Every ``\\makerubric{name}`` / ``\\input{name}`` in the main .tex file becomes
  a section, in the same order as in the PDF.
* A file with ``\\begin{rubric}{Title}`` becomes a timeline of ``\\entry``
  items; ``\\subrubric{...}`` becomes a sub-heading.
* A file with ``\\printbibliography`` becomes a numbered publication list built
  from the .bib file, in ``\\nocite`` order.

Only the Python standard library is used. Anything the converter does not
understand is reported as a warning instead of being silently dropped.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "_data" / "CV.zip"
DEFAULT_OUTPUT = ROOT / "cv.html"
DEFAULT_PUBLICATIONS_OUTPUT = ROOT / "publications.html"
AVATAR_URL = "/images/profile.jpg"


# --------------------------------------------------------------------------
# Warnings
# --------------------------------------------------------------------------

_warned: set = set()


def warn(message: str) -> None:
    if message not in _warned:
        _warned.add(message)
        print(f"warning: {message}", file=sys.stderr)


# --------------------------------------------------------------------------
# Reading the LaTeX project
# --------------------------------------------------------------------------


def load_source_files(source_path: Path) -> Dict[str, str]:
    """Return the project's text files as a basename-to-text map."""

    raw: List[Tuple[str, bytes]] = []
    if source_path.is_dir():
        raw = [(p.name, p.read_bytes()) for p in sorted(source_path.rglob("*")) if p.is_file()]
    elif source_path.is_file() and source_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(source_path) as archive:
            raw = [
                (PurePosixPath(info.filename).name, archive.read(info))
                for info in archive.infolist()
                if not info.is_dir()
            ]
    else:
        raise FileNotFoundError(f"cannot read CV source from {source_path}")

    files: Dict[str, str] = {}
    for name, data in raw:
        if not name.endswith((".tex", ".bib")):
            continue
        if name in files:
            warn(f"several files are named {name}; using the first one")
            continue
        files[name] = data.decode("utf-8-sig", errors="replace")
    return files


def strip_comments(text: str) -> str:
    """Remove LaTeX comments (an unescaped % up to the end of the line)."""

    return "\n".join(re.sub(r"(?<!\\)%.*", "", line) for line in text.splitlines())


def read_group(text: str, start: int) -> Tuple[str, int]:
    """Read the brace group opening at text[start]; return (inside, index after it)."""

    depth = 0
    i = start
    while i < len(text):
        char = text[i]
        if char == "\\":
            i += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i], i + 1
        i += 1
    warn(f"unbalanced braces near: {text[start:start + 60]!r}")
    return text[start + 1 :], len(text)


def read_arg(text: str, i: int) -> Tuple[str, int]:
    """Read one macro argument at text[i]: a {group} or, as in LaTeX, a single token."""

    while i < len(text) and text[i] in " \t\n":
        i += 1
    if i >= len(text):
        return "", i
    if text[i] == "{":
        return read_group(text, i)
    if text[i] == "\\":
        match = COMMAND_RE.match(text, i)
        return match.group(0), match.end()
    return text[i], i + 1


def read_optional_arg(text: str, i: int) -> Tuple[Optional[str], int]:
    """Read an optional [argument] at text[i], if there is one."""

    j = i
    while j < len(text) and text[j] in " \t\n":
        j += 1
    if j < len(text) and text[j] == "[":
        depth = 0
        for k in range(j, len(text)):
            if text[k] == "{":
                depth += 1
            elif text[k] == "}":
                depth -= 1
            elif text[k] == "]" and depth == 0:
                return text[j + 1 : k], k + 1
    return None, i


def find_command_args(text: str, command: str) -> List[str]:
    """Return the first {argument} of every \\command in text, in order."""

    args = []
    for match in re.finditer(rf"\\{command}(?![A-Za-z])", text):
        arg, _ = read_arg(text, match.end())
        args.append(arg)
    return args


# --------------------------------------------------------------------------
# Inline LaTeX -> HTML
# --------------------------------------------------------------------------

COMMAND_RE = re.compile(r"\\([A-Za-z]+\*?|.)")

# Stands for a forced line break (\\) until render_inline turns it into <br>.
LINE_BREAK = "\u2028"

# Commands without arguments.
SYMBOLS = {
    "&": "&", "%": "%", "$": "$", "#": "#", "_": "_", "{": "{", "}": "}",
    " ": " ", ",": "\u2009", "-": "", "/": "", "@": "", "\\": LINE_BREAK,
    "LaTeX": "LaTeX", "TeX": "TeX", "ldots": "\u2026", "dots": "\u2026",
    "textendash": "\u2013", "textemdash": "\u2014", "textbar": "|",
    "quad": "\u2003", "qquad": "\u2003\u2003", "newline": LINE_BREAK, "linebreak": LINE_BREAK,
    "ss": "ß", "aa": "å", "AA": "Å", "o": "ø", "O": "Ø", "ae": "æ", "AE": "Æ",
    "oe": "œ", "OE": "Œ", "l": "ł", "L": "Ł", "i": "ı", "j": "ȷ",
    "copyright": "©", "textregistered": "®", "texttrademark": "™",
}

# Accent commands, applied to their argument as a Unicode combining mark.
ACCENTS = {
    "'": "\u0301", "`": "\u0300", "^": "\u0302", '"': "\u0308", "~": "\u0303",
    "=": "\u0304", ".": "\u0307", "u": "\u0306", "v": "\u030c", "H": "\u030b",
    "c": "\u0327", "r": "\u030a", "k": "\u0328",
}

# Commands whose single argument is wrapped in an HTML element.
WRAPPERS = {
    "textbf": ("<strong>", "</strong>"),
    "emph": ("<em>", "</em>"),
    "textit": ("<em>", "</em>"),
    "textsl": ("<em>", "</em>"),
    "texttt": ("<code>", "</code>"),
    "textsc": ('<span class="smallcaps">', "</span>"),
    "smallcaps": ('<span class="smallcaps">', "</span>"),
    "underline": ("<u>", "</u>"),
    "textsuperscript": ("<sup>", "</sup>"),
    "textsubscript": ("<sub>", "</sub>"),
    "mbox": ("", ""), "hbox": ("", ""), "text": ("", ""), "textrm": ("", ""),
    "textsf": ("", ""), "textnormal": ("", ""), "textmd": ("", ""),
    "textup": ("", ""), "enquote": ("\u201c", "\u201d"),
}

# Commands that are ignored, together with this many {arguments}.
IGNORED = {
    "bfseries": 0, "itshape": 0, "sffamily": 0, "rmfamily": 0, "ttfamily": 0,
    "scshape": 0, "normalfont": 0, "upshape": 0, "mdseries": 0,
    "tiny": 0, "scriptsize": 0, "footnotesize": 0, "small": 0, "normalsize": 0,
    "large": 0, "Large": 0, "LARGE": 0, "huge": 0, "Huge": 0,
    "raggedright": 0, "raggedleft": 0, "centering": 0, "noindent": 0,
    "hfill": 0, "vfill": 0, "smallskip": 0, "medskip": 0, "bigskip": 0,
    "hspace": 1, "hspace*": 1, "vspace": 1, "vspace*": 1, "color": 1,
    "textcolor": 1, "label": 1, "index": 1, "relscale": 1,
}


def _accent(mark: str, base: str) -> str:
    base = {"ı": "i", "ȷ": "j"}.get(base, base)
    return unicodedata.normalize("NFC", base[:1] + mark + base[1:]) if base else ""


def _link(url: str, label: str) -> str:
    url = url.strip()
    new_tab = "" if url.startswith("mailto:") else ' target="_blank" rel="noreferrer"'
    return f'<a href="{html.escape(url, quote=True)}"{new_tab}>{label}</a>'


def _render(text: str) -> str:
    out: List[str] = []
    i = 0
    n = len(text)
    while i < n:
        char = text[i]
        if char == "\\":
            match = COMMAND_RE.match(text, i)
            if not match:  # a lone backslash at the very end
                break
            name = match.group(1)
            i = match.end()
            if name in ACCENTS:
                arg, i = read_arg(text, i)
                out.append(html.escape(_accent(ACCENTS[name], html.unescape(_render(arg))), quote=False))
            elif name in SYMBOLS:
                out.append(html.escape(SYMBOLS[name], quote=False))
            elif name in WRAPPERS:
                arg, i = read_arg(text, i)
                start, end = WRAPPERS[name]
                out.append(f"{start}{_render(arg)}{end}")
            elif name == "href":
                url, i = read_arg(text, i)
                label, i = read_arg(text, i)
                out.append(_link(url, _render(label)))
            elif name == "url":
                url, i = read_arg(text, i)
                out.append(_link(url, html.escape(url.strip(), quote=False)))
            elif name in IGNORED:
                for _ in range(IGNORED[name]):
                    _, i = read_arg(text, i)
            else:
                warn(f"unsupported LaTeX command \\{name} (its text is kept, the command dropped)")
        elif char == "{":
            inner, i = read_group(text, i)
            out.append(_render(inner))
        elif char in "}$":
            i += 1
        elif char == "~":
            out.append("\u00a0")
            i += 1
        elif text.startswith("---", i):
            out.append("\u2014")
            i += 3
        elif text.startswith("--", i):
            out.append("\u2013")
            i += 2
        elif text.startswith("``", i):
            out.append("\u201c")
            i += 2
        elif text.startswith("''", i):
            out.append("\u201d")
            i += 2
        else:
            out.append(html.escape(char, quote=False))
            i += 1
    return "".join(out)


def render_inline(text: str) -> str:
    """Convert inline LaTeX to HTML, collapsing whitespace like LaTeX does."""

    rendered = _render(text)
    lines = [re.sub(r"[ \t\r\n]+", " ", line).strip() for line in rendered.split(LINE_BREAK)]
    return "<br>".join(line for line in lines if line)


def render_paragraphs(body: str) -> str:
    """Render a body that may contain \\par or blank lines as paragraphs."""

    parts = [part for part in re.split(r"\\par(?![A-Za-z])|\n\s*\n", body)]
    rendered = [render_inline(part) for part in parts]
    rendered = [part for part in rendered if part]
    if len(rendered) <= 1:
        return "".join(rendered)
    return rendered[0] + "".join(f"<p>{part}</p>" for part in rendered[1:])


def plain_text(text: str) -> str:
    """Render inline LaTeX to plain text (for attributes and dates)."""

    return html.unescape(re.sub(r"<[^>]+>", "", render_inline(text)))


# --------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------


def parse_header(main_tex: str) -> Tuple[str, List[str]]:
    """Return (name line, rendered contact fields) from \\leftheader{...}."""

    match = re.search(r"\\leftheader(?![A-Za-z])", main_tex)
    if not match:
        warn("no \\leftheader found in the main .tex file; using a generic title")
        return "Curriculum Vitae", []
    body, _ = read_arg(main_tex, match.end())

    contacts: List[str] = []
    remainder: List[str] = []
    i = 0
    for field in re.finditer(r"\\makefield(?![A-Za-z])", body):
        if field.start() < i:
            continue
        remainder.append(body[i : field.start()])
        _icon, j = read_arg(body, field.end())
        content, i = read_arg(body, j)
        contact = render_inline(content)
        if contact:
            contacts.append(contact)
    remainder.append(body[i:])

    name = plain_text("".join(remainder)) or "Curriculum Vitae"
    return name, contacts


# --------------------------------------------------------------------------
# Rubric sections (timelines)
# --------------------------------------------------------------------------


def render_rubric(text: str) -> Optional[str]:
    match = re.search(r"\\begin\{rubric\}", text)
    if not match:
        return None
    title, start = read_arg(text, match.end())
    end_match = re.compile(r"\\end\{rubric\}").search(text, start)
    body = text[start : end_match.start() if end_match else len(text)]

    # Split the body into \entry items and \subrubric headings.
    blocks: List[Tuple[str, str, str]] = []  # (kind, label, body)
    markers = list(re.finditer(r"\\(entry\*?|subrubric)(?![A-Za-z])", body))
    for index, marker in enumerate(markers):
        stop = markers[index + 1].start() if index + 1 < len(markers) else len(body)
        if marker.group(1) == "subrubric":
            label, j = read_arg(body, marker.end())
            blocks.append(("subrubric", label, ""))
            if body[j:stop].strip():
                warn(f"text after \\subrubric{{{label}}} but before the next \\entry was ignored")
        else:
            label, j = read_optional_arg(body, marker.end())
            blocks.append(("entry", label or "", body[j:stop]))
    if markers and body[: markers[0].start()].strip():
        leftover = plain_text(body[: markers[0].start()])
        if leftover:
            warn(f"text before the first \\entry in rubric '{plain_text(title)}' was ignored: {leftover[:60]!r}")
    if not blocks:
        warn(f"rubric '{plain_text(title)}' has no \\entry items; skipped")
        return None

    lines = ['<section class="cv-section">', f"  <h2>{render_inline(title)}</h2>"]
    in_list = False
    for kind, label, content in blocks:
        if kind == "subrubric":
            if in_list:
                lines.append("  </ul>")
                in_list = False
            lines.append(f"  <h3>{render_inline(label)}</h3>")
            continue
        if not in_list:
            lines.append('  <ul class="cv-timeline">')
            in_list = True
        lines += [
            "    <li>",
            f'      <span class="cv-date">{render_inline(label)}</span>',
            f"      <div>{render_paragraphs(content)}</div>",
            "    </li>",
        ]
    if in_list:
        lines.append("  </ul>")
    lines.append("</section>")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Bibliography
# --------------------------------------------------------------------------


def parse_bib(text: str) -> Dict[str, Dict[str, str]]:
    """Parse a .bib file into {key: {field: raw value}}, keeping file order."""

    entries: Dict[str, Dict[str, str]] = {}
    for match in re.finditer(r"@\s*(\w+)\s*\{", text):
        entry_type = match.group(1).lower()
        body, _ = read_group(text, match.end() - 1)
        if entry_type in ("comment", "string", "preamble"):
            continue
        key, _, rest = body.partition(",")
        fields: Dict[str, str] = {"ENTRYTYPE": entry_type}
        i = 0
        field_re = re.compile(r"\s*([\w:.+-]+)\s*=\s*")
        while True:
            field = field_re.match(rest, i)
            if not field:
                break
            name = field.group(1).lower()
            i = field.end()
            if i < len(rest) and rest[i] == "{":
                value, i = read_group(rest, i)
            elif i < len(rest) and rest[i] == '"':
                close = re.compile(r'(?<!\\)"').search(rest, i + 1)
                j = close.start() if close else len(rest)
                value, i = rest[i + 1 : j], j + 1
            else:
                bare = re.compile(r"[^,]*").match(rest, i)
                value, i = bare.group(0).strip(), bare.end()
            fields[name] = value.strip()
            comma = rest.find(",", i)
            if comma == -1:
                break
            i = comma + 1
        entries[key.strip()] = fields
    return entries


def format_authors(raw: str) -> str:
    names = []
    for name in re.split(r"\s+and\s+", raw.strip()):
        if name.strip() == "others":
            names.append("et al.")
            continue
        parts = [part.strip() for part in name.split(",")]
        if len(parts) == 2:  # "Last, First"
            name = f"{parts[1]} {parts[0]}"
        elif len(parts) == 3:  # "Last, Jr, First"
            name = f"{parts[2]} {parts[0]} {parts[1]}"
        names.append(render_inline(name))
    if names and names[-1] == "et al.":
        return ", ".join(names[:-1]) + " et al."
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + ", and " + names[-1]


def with_period(text: str) -> str:
    text = text.rstrip()
    return text if not text or re.search(r"[.?!](</\w+>)*$", text) else text + "."


def format_publication(entry: Dict[str, str]) -> str:
    def field(name: str) -> str:
        return render_inline(entry.get(name, ""))

    pages = field("pages").replace("-", "\u2013").replace("\u2013\u2013", "\u2013")
    details: List[str] = []
    if entry["ENTRYTYPE"] == "article":
        details.append(field("journal"))
        if field("volume"):
            details.append(f"vol. {field('volume')}")
        if field("number"):
            details.append(f"no. {field('number')}")
    else:
        venue = field("booktitle") or field("journal") or field("howpublished")
        if venue:
            if field("series"):
                venue += f" ({field('series')})"
            details += [f"In {venue}", field("location")]
    if pages:
        details.append(f"pp. {pages}")

    parts = [with_period(format_authors(entry.get("author", ""))), with_period(field("year"))]
    parts.append(with_period(f"<strong>{field('title')}</strong>"))
    parts.append(with_period(", ".join(part for part in details if part)))
    parts.append(with_period(field("note")))

    doi = entry.get("doi", "").strip()
    eprint = entry.get("eprint", "").strip()
    # Show the full identifier (not just "DOI") so readers can copy it for citations.
    if doi:
        doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
        link = _link(f"https://doi.org/{doi}", f"doi: {html.escape(doi, quote=False)}")
    elif eprint and entry.get("archiveprefix", "arXiv").lower() == "arxiv":
        link = _link(f"https://arxiv.org/abs/{eprint}", f"arXiv: {html.escape(eprint, quote=False)}")
    elif entry.get("url") or entry.get("opturl"):
        link = _link(entry.get("url") or entry["opturl"], "Link")
    else:
        link = ""
    parts.append(link)
    return " ".join(part for part in parts if part)


def _bib_options(options: str) -> Dict[str, str]:
    """Parse "key=value, key={value, with commas}" into a dict."""

    parts, depth, current = [], 0, ""
    for char in options:
        depth += {"{": 1, "}": -1}.get(char, 0)
        if char == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += char
    parts.append(current)

    result = {}
    for part in parts:
        key, _, value = part.partition("=")
        value = value.strip()
        if value.startswith("{") and value.endswith("}"):
            value = value[1:-1]
        if key.strip():
            result[key.strip()] = value
    return result


def render_bibliography(text: str, bib: Dict[str, Dict[str, str]]) -> Optional[Tuple[str, List[str]]]:
    """Return (heading, HTML lines of the numbered lists) for a file with \\printbibliography."""

    prints = list(re.finditer(r"\\printbibliography(?![A-Za-z])", text))
    if not prints:
        return None
    heading = find_command_args(text, "makerubrichead")
    title = render_inline(heading[0]) if heading else "Publications"

    cited: List[str] = []
    for arg in find_command_args(text, "nocite"):
        for key in (part.strip() for part in arg.split(",")):
            if key == "*":
                cited += [k for k in bib if k not in cited]
            elif key and key not in cited:
                cited.append(key)
    if not cited:
        cited = list(bib)
    missing = [key for key in cited if key not in bib]
    for key in missing:
        warn(f"\\nocite{{{key}}} is not in the .bib file")
    cited = [key for key in cited if key in bib]

    lines: List[str] = []
    number = 1
    for match in prints:
        options, _ = read_optional_arg(text, match.end())
        opts = _bib_options(options or "")
        for unsupported in set(opts) - {"heading", "title", "type", "nottype", "keyword", "notkeyword", "resetnumbers"}:
            warn(f"\\printbibliography option '{unsupported}' is not supported; it was ignored")

        def keep(key: str) -> bool:
            entry = bib[key]
            keywords = [k.strip() for k in entry.get("keywords", "").split(",")]
            return (
                ("type" not in opts or entry["ENTRYTYPE"] == opts["type"].lower())
                and ("nottype" not in opts or entry["ENTRYTYPE"] != opts["nottype"].lower())
                and ("keyword" not in opts or opts["keyword"] in keywords)
                and ("notkeyword" not in opts or opts["notkeyword"] not in keywords)
            )

        keys = [key for key in cited if keep(key)]
        if not keys:
            continue
        if opts.get("title"):
            lines.append(f"<h3>{render_inline(opts['title'])}</h3>")
        start = f' start="{number}"' if number > 1 else ""
        lines.append(f'<ol class="cv-publications"{start}>')
        lines += [f"  <li>{format_publication(bib[key])}</li>" for key in keys]
        lines.append("</ol>")
        number += len(keys)
    return title, lines


def indent(lines: List[str], prefix: str = "  ") -> List[str]:
    return [prefix + line for line in lines]


def page_text(front_matter: Dict[str, str], body: List[str]) -> str:
    header = ["---", "# Generated by scripts/generate_cv.py from the LaTeX CV. Do not edit by hand."]
    header += [f"{key}: {value}" for key, value in front_matter.items()] + ["---", ""]
    return "\n".join(header + body) + "\n"


# --------------------------------------------------------------------------
# Page
# --------------------------------------------------------------------------


def find_file(files: Dict[str, str], name: str, extension: str) -> Optional[str]:
    base = PurePosixPath(name.strip()).name
    for candidate in (base, base + extension):
        if candidate in files:
            return files[candidate]
    return None


def build_pages(files: Dict[str, str]) -> Tuple[str, Optional[str]]:
    """Return the text of cv.html and of publications.html (None if the CV has no publications)."""

    main_name = next((name for name, text in files.items() if r"\begin{document}" in text), None)
    if main_name is None:
        raise SystemExit("error: no .tex file with \\begin{document} found in the CV source")
    main_tex = strip_comments(files[main_name])

    bib: Dict[str, Dict[str, str]] = {}
    bib_names = find_command_args(main_tex, "addbibresource") or find_command_args(main_tex, "bibliography")
    if not bib_names:
        bib_names = [name for name in files if name.endswith(".bib")]
    for bib_name in bib_names:
        for part in bib_name.split(","):
            bib_text = find_file(files, part, ".bib")
            if bib_text is None:
                warn(f"bibliography file {part} not found")
            else:
                # Only whole-line comments: a % inside a field (e.g. a URL's %20) is literal.
                bib.update(parse_bib(re.sub(r"(?m)^\s*%.*$", "", bib_text)))

    name, contacts = parse_header(main_tex)
    person = name.split(",")[0].strip()

    document = main_tex.split(r"\begin{document}", 1)[1].split(r"\end{document}", 1)[0]
    sections: List[str] = []
    publications: List[str] = []
    for match in re.finditer(r"\\(makerubric|input|include)(?![A-Za-z])", document):
        file_name, _ = read_arg(document, match.end())
        text = find_file(files, file_name, ".tex")
        if text is None:
            warn(f"\\{match.group(1)}{{{file_name}}}: file not found; section skipped")
            continue
        text = strip_comments(text)
        rubric = render_rubric(text)
        bibliography = None if rubric else render_bibliography(text, bib)
        if rubric:
            sections.append(rubric)
        elif bibliography:
            title, lists = bibliography
            sections.append("\n".join(['<section class="cv-section">', f"  <h2>{title}</h2>"] + indent(lists) + ["</section>"]))
            publications += lists
        else:
            warn(f"{file_name}: no rubric or bibliography found; section skipped")

    header = [
        '<header class="cv-header">',
        f"  <img src=\"{{{{ '{AVATAR_URL}' | relative_url }}}}\" class=\"cv-avatar\" alt=\"{html.escape(person)}\" />",
        "  <div>",
        f"    <h1>{html.escape(name, quote=False)}</h1>",
    ]
    if contacts:
        header.append(f'    <p class="cv-contact">{" | ".join(contacts)}</p>')
    header += ["  </div>", "</header>"]

    # {% raw %} keeps Jekyll from treating any {{ or {% in the CV text as Liquid.
    cv_page = page_text(
        {"layout": "default", "title": "CV", "body_class": "cv"},
        ['<section class="content-wrapper cv-page">'] + header
        + ["{% raw %}"] + sections + ["{% endraw %}", "</section>"],
    )
    if not publications:
        return cv_page, None
    publications_page = page_text(
        {"layout": "default", "title": "Publications", "body_class": "publications"},
        ['<section class="content-wrapper publications-page">', "  <h1>Publications</h1>", "{% raw %}"]
        + indent(publications) + ["{% endraw %}", "</section>"],
    )
    return cv_page, publications_page


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate cv.html and publications.html from the LaTeX CV source.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Overleaf .zip export or extracted folder.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Where to write the CV page.")
    parser.add_argument(
        "--publications-output", type=Path, default=DEFAULT_PUBLICATIONS_OUTPUT,
        help="Where to write the publications page.",
    )
    args = parser.parse_args()

    cv_page, publications_page = build_pages(load_source_files(args.source))
    args.output.write_text(cv_page, encoding="utf-8", newline="\n")
    written = [args.output]
    if publications_page is None:
        warn(f"the CV has no publication list; {args.publications_output} was left unchanged")
    else:
        args.publications_output.write_text(publications_page, encoding="utf-8", newline="\n")
        written.append(args.publications_output)
    summary = f" with {len(_warned)} warning(s)" if _warned else ""
    print("Wrote " + " and ".join(str(path) for path in written) + summary)


if __name__ == "__main__":
    main()
