# My Personal GitHub Page

Source for my site at https://yarinamomo.github.io/. GitHub Pages builds it with Jekyll on every push to `main`.

## Where things are

| To change…                     | Edit                                                        |
| ------------------------------ | ----------------------------------------------------------- |
| Home page text, links          | `index.html`                                                |
| Profile photo                  | replace `images/profile.jpg` (keep the name)                |
| CV page, Publications page     | the Overleaf project, then regenerate (see below)           |
| Hobbies gallery                | `_data/hobbies.yml` + images in `images/hobbies/`           |
| Navigation bar                 | `_data/nav.yml`                                             |
| Blog posts                     | `_posts/YYYY-MM-DD-title.md` (listed on `/blogs.html`)      |
| Styles (all pages)             | `css/style.css`                                             |
| Page wrapper (`<head>`, nav)   | `_layouts/default.html`, `_includes/nav.html`               |
| Site title / description       | `_config.yml`                                               |

Pages start with YAML front matter (`layout`, `title`, `body_class`). `body_class: home` is special: the layout then
leaves out the nav, because `index.html` places it below the hero itself.

### Add a publication

Publications have one source: `own-bib.bib` in the Overleaf CV. Add the entry there plus a `\nocite{key}` in
`publications.tex` (the `\nocite` order is the display order), then regenerate as described under
[Updating the CV](#updating-the-cv). This updates the PDF, `cv.html` and `publications.html` together.

### Add a drawing

Put the image in `images/hobbies/` and add to `_data/hobbies.yml`:

```yaml
- image: /images/hobbies/my-drawing.jpg   # file names are case-sensitive on GitHub Pages
  alt: Short description for screen readers
  caption: Caption shown under the image
```

### Add a blog post

Create `_posts/YYYY-MM-DD-some-title.md` with front matter `title:` (and optionally `tags:`). The post layout is applied
automatically. Put its images in `images/<post-name>/` and reference them as
`{{ '/images/<post-name>/file.png' | relative_url }}`. The blog page is `/blogs.html`; add it to `_data/nav.yml` to
show it in the menu.

## Updating the CV

`cv.html` and `publications.html` are generated from the Overleaf LaTeX project, so the website always matches the
PDF. Don't edit either file by hand; the next run overwrites them.

1. In Overleaf: *Menu → Download → Source* and save the zip as `_data/CV.zip`.
2. From the repository root, run (Python 3.8+, no packages needed):

   ```bash
   python scripts/generate_cv.py
   ```

3. Read any `warning:` lines, preview the site, and commit `_data/CV.zip`, `cv.html` and `publications.html`
   together.

What the generator reads:

- **Header**: the name line and each `\makefield{icon}{content}` inside `\leftheader{...}`.
- **Sections**: every `\makerubric{file}` / `\input{file}` between `\begin{document}` and `\end{document}`, in that
  order. Adding a new `\makerubric{awards}` with an `awards.tex` rubric adds an Awards section automatically.
- **Rubric files**: `\begin{rubric}{Title}` with `\entry*[date] text` items (`\par` starts a new paragraph) and optional
  `\subrubric{Heading}`.
- **Publications** (CV section and the Publications page): the file with `\printbibliography`; entries come from the
  `\addbibresource` file in `\nocite` order (`\nocite{*}` = file order).
  `\printbibliography[type=article, title={Journal Articles}]` style splits are supported.

LaTeX it doesn't know is reported as a warning (the text is kept, the command dropped). To use a different source:
`python scripts/generate_cv.py --source path/to/folder-or.zip --output cv.html --publications-output publications.html`.

## Preview locally with Docker

The Docker image uses the same Jekyll version as GitHub Pages. From the repository root in PowerShell:

```powershell
# once (and after editing the Dockerfile)
docker build -t my-jekyll-site .

# every time; pages rebuild when you save
docker run --rm -it -p 4000:4000 -p 35729:35729 -v "${PWD}:/srv/jekyll" my-jekyll-site
```

Then open http://localhost:4000/. Changes to `_config.yml` need a restart (Ctrl+C, run again).
