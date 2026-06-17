#!/usr/bin/env python3
"""Generate the CV webpage from the LaTeX source archive.

Usage:
  python scripts/generate_cv.py
  python scripts/generate_cv.py --source path\to\CV.zip --output cv.html

The script accepts either a zip archive or an extracted source directory.
"""

from __future__ import annotations

import argparse
import html
import re
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "_data" / "CV.zip"
DEFAULT_OUTPUT = ROOT / "cv.html"
STYLESHEET_PATH = ROOT / "css" / "style.css"
CV_CSS_START = "/* CV GENERATOR START */"
CV_CSS_END = "/* CV GENERATOR END */"


def load_source_files(source_path: Path) -> Dict[str, str]:
    """Return the archive or directory contents as a filename-to-text map."""

    if source_path.is_dir():
        files: Dict[str, str] = {}
        for path in source_path.rglob("*"):
            if path.is_file():
                try:
                    files[path.name] = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
        return files

    if source_path.is_file() and source_path.suffix.lower() == ".zip":
        files = {}
        with zipfile.ZipFile(source_path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                name = Path(info.filename).name
                try:
                    files[name] = archive.read(info).decode("utf-8")
                except UnicodeDecodeError:
                    continue
        return files

    raise FileNotFoundError(f"Cannot read CV source from {source_path}")


def clean_text(text: str) -> str:
    return text.strip().replace("~", " ")


def render_inline(text: str) -> str:
    """Convert a small subset of LaTeX inline commands into HTML."""

    text = clean_text(text)
    text = text.replace(r"\LaTeX", "LaTeX")
    text = text.replace(r"\ldots", "...")
    text = text.replace(r"\&", "&")
    text = text.replace(r"\%", "%")

    def replace_braced(pattern: str, wrapper) -> None:
        nonlocal text
        regex = re.compile(pattern)
        while True:
            new_text = regex.sub(lambda match: wrapper(match.group(1)), text)
            if new_text == text:
                return
            text = new_text

    replace_braced(r"\\textbf\{([^{}]*)\}", lambda inner: f"<strong>{render_inline(inner)}</strong>")
    replace_braced(r"\\emph\{([^{}]*)\}", lambda inner: f"<em>{render_inline(inner)}</em>")
    replace_braced(r"\\texttt\{([^{}]*)\}", lambda inner: f"<code>{html.escape(clean_text(inner))}</code>")
    replace_braced(
        r"\\textsc\{([^{}]*)\}", lambda inner: f"<span class=\"smallcaps\">{render_inline(inner)}</span>"
    )
    replace_braced(
        r"\\smallcaps\{([^{}]*)\}", lambda inner: f"<span class=\"smallcaps\">{render_inline(inner)}</span>"
    )

    href_pattern = re.compile(r"\\href\{([^{}]*)\}\{([^{}]*)\}")
    while True:
        new_text = href_pattern.sub(
            lambda match: (
                f'<a href="{html.escape(clean_text(match.group(1)), quote=True)}" '
                'target="_blank" rel="noreferrer">'
                f"{render_inline(match.group(2))}</a>"
            ),
            text,
        )
        if new_text == text:
            break
        text = new_text

    return text.replace("``", "\u201c").replace("''", "\u201d")


def parse_entry_lines(text: str) -> List[Tuple[str, str]]:
    entries: List[Tuple[str, str]] = []
    current_date = ""
    current_parts: List[str] = []

    def flush() -> None:
        nonlocal current_date, current_parts
        if current_date:
            body = " ".join(part for part in current_parts if part).strip()
            entries.append((current_date, body))
        current_date = ""
        current_parts = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("%") or line.startswith("%!TEX") or line == r"\raggedright":
            continue
        if line.startswith(r"\begin{rubric}") or line.startswith(r"\end{rubric}"):
            continue
        if line.startswith(r"\makerubrichead") or line.startswith(r"\noentry"):
            continue

        match = re.match(r"^\\entry\*?\[(?P<date>[^\]]*)\](?P<rest>.*)$", line)
        if match:
            flush()
            current_date = clean_text(match.group("date"))
            rest = match.group("rest").lstrip()
            if rest.startswith("%"):
                rest = rest[1:].lstrip()
            if rest:
                current_parts.append(rest)
            continue

        if current_date:
            current_parts.append(line)

    flush()
    return entries


def render_paragraphs(body: str) -> str:
    parts = [part.strip() for part in body.split(r"\par") if part.strip()]
    if not parts:
        return ""
    if len(parts) == 1:
        return render_inline(parts[0])
    rendered = [render_inline(parts[0])]
    rendered.extend(f"<p>{render_inline(part)}</p>" for part in parts[1:])
    return "".join(rendered)


def render_timeline_section(title: str, entries: Iterable[Tuple[str, str]]) -> str:
    items = []
    for date, body in entries:
        items.append(
            "<li>"
            f'<span class="cv-date">{html.escape(date)}</span>'
            f"<div>{render_paragraphs(body)}</div>"
            "</li>"
        )
    return (
        '<section class="cv-section">'
        f"<h2>{html.escape(title)}</h2>"
        '<ul class="cv-list cv-timeline">'
        + "".join(items)
        + "</ul></section>"
    )


def parse_bib_entries(text: str) -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []
    current: Dict[str, str] | None = None

    def flush() -> None:
        nonlocal current
        if current:
            entries.append(current)
        current = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("%"):
            continue
        if line.startswith("@"):
            flush()
            current = {}
            continue
        if line == "}":
            flush()
            continue
        if current is None or "=" not in line:
            continue
        field, value = line.split("=", 1)
        field = field.strip().lower()
        value = value.strip().rstrip(",")
        if value.startswith("{") and value.endswith("}"):
            value = value[1:-1]
        elif value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        current[field] = value

    flush()
    return entries


def clean_bib_value(text: str) -> str:
    text = text.strip()
    text = text.replace("{", "").replace("}", "")
    text = text.replace("~", " ")
    text = text.replace(r"\LaTeX", "LaTeX")
    text = text.replace(r"\&", "&")
    return text


def render_publications_section(fields: List[Dict[str, str]]) -> str:
    items = []
    for entry in fields:
        title = clean_bib_value(entry.get("title", ""))
        authors = clean_bib_value(entry.get("author", ""))
        year = clean_bib_value(entry.get("year", ""))
        note = clean_bib_value(entry.get("note", ""))
        journal = clean_bib_value(entry.get("journal", ""))
        booktitle = clean_bib_value(entry.get("booktitle", ""))
        location = clean_bib_value(entry.get("location", ""))
        series = clean_bib_value(entry.get("series", ""))
        pages = clean_bib_value(entry.get("pages", ""))
        link_url = entry.get("doi") or entry.get("opturl") or entry.get("url") or entry.get("eprint")
        link_label = ""
        if entry.get("doi"):
            link_label = "DOI"
            link_url = f"https://doi.org/{entry['doi']}"
        elif entry.get("opturl"):
            link_label = "arXiv"
            link_url = entry["opturl"]
        elif entry.get("url"):
            link_label = "Link"
        elif entry.get("eprint"):
            link_label = "arXiv"
            link_url = f"https://arxiv.org/abs/{entry['eprint']}"

        details = []
        if journal:
            details.append(journal)
        if booktitle:
            details.append(booktitle)
        if pages:
            details.append(f"pp. {pages}")
        if location:
            details.append(location)
        if series:
            details.append(series)
        if note:
            details.append(note)

        meta = ". ".join(part for part in details if part)
        body = f"{authors}. {year}. <strong>{title}</strong>"
        if meta:
            body += f". {meta}"
        if link_url and link_label:
            body += f' <a href="{html.escape(link_url, quote=True)}" target="_blank" rel="noreferrer">{html.escape(link_label)}</a>'

        items.append(f"<li>{body}</li>")

    return (
        '<section class="cv-section">'
        '<h2>Research Publications</h2>'
        '<ol class="cv-publications">'
        + "".join(items)
        + "</ol></section>"
    )


def render_skills_section(text: str) -> str:
    entries = parse_entry_lines(text)
    if not entries:
        return ""
    items = []
    for label, body in entries:
        label = clean_bib_value(label)
        body = render_inline(body)
        items.append(f"<dt>{html.escape(label)}</dt><dd>{body}</dd>")
    return (
        '<section class="cv-section">'
        '<h2>Skills</h2>'
        '<dl class="cv-skills">'
        + "".join(items)
        + "</dl></section>"
    )


def parse_cv_header(text: str) -> Tuple[str, str]:
    title_match = re.search(r"\\LARGE\\bfseries\\sffamily\s*(.*?)\s*\}\s*$", text, re.M)
    name = clean_text(title_match.group(1)) if title_match else ""

    email_match = re.search(r"\\href\{mailto:([^}]+)\}\{[^}]*\}", text)
    email = clean_text(email_match.group(1)) if email_match else ""

    return name, email


def build_cv_css() -> str:
        return """/* CV GENERATOR START */
.cv-page {
    max-width: 800px;
    line-height: 1.6;
}

.cv-header {
    padding: 1.5rem;
    background: #fff;
    border: 1px solid #ececec;
    border-radius: 14px;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.06);
    display: grid;
    grid-template-columns: 120px 1fr;
    gap: 1.25rem;
    align-items: center;
    text-align: left;
}

.cv-avatar {
    width: 120px;
    height: 120px;
    border-radius: 50%;
    object-fit: cover;
    display: block;
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.12);
}

.cv-header h1,
.cv-header p {
    margin: 0;
    text-align: left;
}

.cv-header p {
    color: #555;
}

.cv-header h1 {
    font-size: 1.25rem;
    line-height: 1.2;
}

.cv-header p {
    font-size: 0.95rem;
}

.cv-contact {
    margin-top: 0.4rem;
    color: #555;
}

.cv-section {
    margin-top: 2rem;
    padding: 1.25rem 1.35rem;
    background: #fff;
    border: 1px solid #ececec;
    border-radius: 14px;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.04);
}

.cv-section h2 {
    margin-top: 0;
    margin-bottom: 0.75rem;
}

.cv-list,
.cv-bullets,
.cv-publications {
    margin: 0;
    padding-left: 1.2rem;
}

.cv-timeline {
    list-style: none;
    padding-left: 0;
}

.cv-timeline li {
    display: grid;
    grid-template-columns: 10rem 1fr;
    gap: 1rem;
    padding: 0.75rem 0;
    border-top: 1px solid #f0f0f0;
}

.cv-timeline li:first-child {
    border-top: 0;
    padding-top: 0;
}

.cv-date {
    font-weight: 700;
    color: #6b4e16;
}

.cv-timeline strong,
.cv-publications strong {
    color: #222;
}

.cv-timeline p,
.cv-publications div,
.cv-bullets li {
    margin: 0;
}

.cv-publications li {
    line-height: 1.55;
}

.cv-publications li + li {
    margin-top: 1rem;
}

.cv-bullets li + li {
    margin-top: 0.85rem;
}

.cv-publications li strong,
.cv-bullets strong {
    display: inline;
}

.cv-publications a {
    white-space: nowrap;
}

.cv-section a {
    color: #8a4d08;
    text-decoration-thickness: 1px;
    text-underline-offset: 0.15em;
}

.cv-section a:hover {
    text-decoration: underline;
}

@media (max-width: 760px) {
    .cv-header {
        text-align: center;
    }

    .cv-timeline li {
        grid-template-columns: 1fr;
    }

    .cv-date {
        margin-bottom: 0.25rem;
        display: block;
    }
}
/* CV GENERATOR END */"""


def update_stylesheet() -> Path:
    stylesheet = STYLESHEET_PATH.read_text(encoding="utf-8")
    pattern = re.compile(rf"{re.escape(CV_CSS_START)}.*?{re.escape(CV_CSS_END)}", re.S)
    if pattern.search(stylesheet):
        stylesheet = pattern.sub(build_cv_css(), stylesheet)
    else:
        stylesheet = stylesheet.rstrip() + "\n\n" + build_cv_css() + "\n"
    STYLESHEET_PATH.write_text(stylesheet, encoding="utf-8")
    return STYLESHEET_PATH


def build_page(files: Dict[str, str]) -> str:
    cv_header_text, cv_email = parse_cv_header(files.get("cv-llt.tex", ""))
    header_title = html.escape(cv_header_text) if cv_header_text else "CV"
    header_email = html.escape(cv_email) if cv_email else ""
    avatar_src = "{{ '/images/profile.jpg' | relative_url }}"

    sections = [
        "---\nlayout: default\ntitle: CV\nbody_class: cv\n---\n",
        '<section class="content-wrapper cv-page">',
        '<header class="cv-header">',
        f'<img src="{avatar_src}" class="cv-avatar" alt="Yiran Wang" />',
        '<div class="cv-header__content">',
        f"<h1>{header_title}</h1>",
        f'<p class="cv-contact"><a href="mailto:{header_email}">{header_email}</a></p>' if header_email else "",
        '</div>',
        "</header>",
        render_timeline_section("Education", parse_entry_lines(files.get("education.tex", ""))),
        render_timeline_section("Employment", parse_entry_lines(files.get("employment.tex", ""))),
        render_publications_section(parse_bib_entries(files.get("own-bib.bib", ""))),
        render_timeline_section("Projects", parse_entry_lines(files.get("projects.tex", ""))),
        render_timeline_section("Talks", parse_entry_lines(files.get("talks.tex", ""))),
        render_timeline_section("International Activities", parse_entry_lines(files.get("activities.tex", ""))),
        render_timeline_section("Academic Service", parse_entry_lines(files.get("service.tex", ""))),
        "</section>",
    ]
    return "\n".join(sections) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the CV webpage from LaTeX source files.")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="Path to CV.zip or an extracted source directory.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Path to the generated cv.html file.")
    args = parser.parse_args()

    source_path = Path(args.source)
    output_path = Path(args.output)

    files = load_source_files(source_path)
    output_path.write_text(build_page(files), encoding="utf-8")
    stylesheet_path = update_stylesheet()
    print(f"Wrote {output_path}")
    print(f"Updated {stylesheet_path}")


if __name__ == "__main__":
    main()