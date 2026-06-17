# My Personal GitHub Page

This repository contains the source for my GitHub Page site published at https://yarinamomo.github.io/.

## How to update the site
This site is organized using a Jekyll-style layout. Key places to edit site-wide layout and styles are shown as follows.

### General settings (layout, style, etc):
- `/_layouts/default.html`: the base HTML layout used by most pages. Modify header/footer wrappers and where the site nav is inserted.
- `/_includes/`: reusable fragments (for example `nav.html`) that are included into layouts and pages.
- `/css/style.css`: global styles. Note there is a generator-managed block between `/* CV GENERATOR START */` and `/* CV GENERATOR END */` — the CV generator will overwrite that block when it runs.
- `/_data/nav.yml`: controls the navigation entries. Edit this to add/remove top-level nav items (e.g., the `CV` entry).
- Front matter: pages use YAML front matter at the top (e.g., `layout`, `title`, `body_class`). Changing `body_class` is used by the layout to apply page-specific behaviors (for example the home page centers the nav).

### Home page
`index.html` (root) contains the hero section and is marked with `body_class: home` in its front matter. The home page differs from inner pages:
- Hero content (the big header area) lives in `index.html`; edit the title, subheading, and description there.
- The home page deliberately places the site navigation below the hero. If you need to change nav placement, update `/_layouts/default.html` or `index.html` where the nav is included.
- Profile image: the avatar used on the site is `images/profile.jpg`. Replace that file with your updated photo (keep the same name) and re-run the CV generator if you want the CV header to pick it up.
- Small visual changes (spacing, fonts) are usually in `css/style.css` — prefer local tweaks there rather than changing many templates.

### Publication page:
Data is in `/_data/publications.yml` and the page template is `publications.html`. 

How to add a publication:

1. Add an entry to `/_data/publications.yml` with the desired fields.
2. Optionally add a `url` or `doi` — the template will show a link only if present.
3. Save and preview the site locally.

### Hobbies page:
Data is in `/_data/hobbies.yml` and the page template is `hobbies.html`.

How to add a hobby entry:

1. Add a YAML entry to `_data/hobbies.yml` with `title`, `description`, and optional `image`.
2. Place the image under `images/hobbies/` and reference its filename from the YAML.

### CV page
The CV page is generated from an Overleaf / LaTeX project (a `.zip` export) into a native HTML page. The generator script does two things:

1. Converts the LaTeX source (sections like `education.tex`, `employment.tex`, `publications.tex`) into `cv.html`.
2. Rewrites the CV-specific CSS block in `css/style.css` (the code between `/* CV GENERATOR START */` and `/* CV GENERATOR END */`).

Usage:

```bash
# from the repository root
python scripts/generate_cv.py
```

## Testing locally with Docker (Windows)

```powershell
# build the image
docker build -t my-jekyll-site .

# run the container and mount the local folder so changes appear immediately
docker run --rm -it -p 4000:4000 -v C:\Users\yirwa29\Downloads\GitHubPage_Yiran\yarinamomo.github.io:/srv/jekyll my-jekyll-site

# then visit in the browser:
http://localhost:4000/
```
