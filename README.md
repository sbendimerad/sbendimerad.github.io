# sbendimerad.github.io

Personal website, built with [Quarto](https://quarto.org) and published to GitHub Pages by a GitHub Action on every push to `main`.

## Preview locally

```bash
quarto preview
```

Opens the site at http://localhost:4321 (or the port shown) and reloads when you save a file.

## Everyday tasks

**New external article** (published on TDS, Medium, a client blog…)
Create `writing/<short-slug>.qmd`, copy an existing one and change the fields:

```yaml
---
title: "Article title"
date: 2026-12-01
categories: ["Production ML"]    # Production ML · Responsible AI · AI in health · Careers & learning
description: "One sentence."
source: "Towards Data Science"
external: https://towardsdatascience.com/...
---

{{< include _article.qmd >}}
```

It appears automatically on the Writing page, in the RSS feed, and on the home page
(the "Latest" card and the theme tabs). To change the "Featured article" card on the home page,
move `featured: true` to another article.

**New post written on this site**
Same file, without `external:` and without the include line. Write the post below the `---`.

**New project**
In `projects/index.qmd`, copy one card block and edit it.

**Course pages (generated, do not edit by hand)**
Course pages are built from the course repos by `tools/build_courses.py`. The originals are never modified.

```bash
gh repo clone sbendimerad/python-course-instructor /tmp/pci -- --depth 1
python3 tools/build_courses.py /tmp/pci
quarto preview
```

The script merges each lesson with its exercises, puts every solution in a collapsed
"Show solution" box, makes a zip (notebooks + data) per section, and runs a privacy scan
(emails, keys, Jedha links). It stops if anything is found.

New section: add it to `COURSES` at the top of `tools/build_courses.py` and to the course
sidebar in `_quarto.yml`, then run the script again.

**Publish**
Commit and push to `main`. The site is live a minute or two later.

## Where things are

| What | File |
|---|---|
| Navbar, footer, site settings | `_quarto.yml` |
| Colours (light / dark) | `custom.scss` / `custom-dark.scss` |
| Layout and components | `_sb-rules.scss` |
| Home page | `index.qmd` (+ `_home-writing.ejs` for the article blocks) |
| Writing list | `writing/index.qmd` (+ `_writing.ejs`) |
| Photo, fonts, favicon | `assets/` |

Notebooks are never executed when the site is built: outputs saved in the notebooks are shown as they are.

## Custom domain (later)

1. Buy the domain.
2. Add a file `CNAME` at the root containing `sabrinebendimerad.com`, and add `CNAME` to `resources:` in `_quarto.yml`.
3. DNS: four `A` records for the apex to GitHub Pages (185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153) and a `CNAME` record `www` → `<user>.github.io`.
4. GitHub → Settings → Pages: set the custom domain, tick "Enforce HTTPS".
5. Update `site-url` in `_quarto.yml` and the sitemap line in `robots.txt`.
