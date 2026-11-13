#!/usr/bin/env python3
"""Build the course pages from a course repo.

Usage:
    python3 tools/build_courses.py python <path-to-course-repo>

The course repo is the source of truth: content fixes (translation, images, bugs) are made
there, on its `website` branch, and every notebook is executed before it is pushed.
This script only reads it (never writes to it) and generates, for each section:

  courses/<course>/<NN-slug>.ipynb             lesson page
  courses/<course>/<NN-slug>-exercises.ipynb   exercises page: hints and solutions folded
  courses/<course>/files/<NN-slug>.zip         lesson + exercise notebooks + data, to download
  courses/<course>/img/...                     local images used by the notebooks
  courses/<course>/index.qmd                   course overview
  courses/_sidebars.yml                        sidebar for every course (loaded by _quarto.yml)

Safety nets on the published copy: Jedha links / Jedha-hosted images dropped, outputs with
email addresses dropped, unclosed code blocks closed, very long outputs shortened, saved
Plotly figures redrawn from their data. A privacy scan runs at the end and fails the build.
"""
import copy, difflib, json, re, shutil, sys, zipfile
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent

COURSES = {
    "python": {
        "title": "Python",
        "number": "01",
        "subtitle": "Course 01 · no prerequisites",
        "intro": "From your first variable to calling an API, in five sections. Each section has a "
                 "**lesson** to read and an **exercises** page: try on your own first, open a hint "
                 "if you are stuck, then compare with the solution.",
        "sections": [
            {
                "slug": "python-basics",
                "title": "Python basics",
                "description": "Types, operators, strings, data structures, conditions, loops and functions.",
                "lesson": "P01_python_basics/course/S1_python_basics_course.ipynb",
                "exercises": [("P01_python_basics/exercises/S1_python_basics_exercises.ipynb",
                               "P01_python_basics/solutions/S1_python_basics_solutions.ipynb")],
            },
            {
                "slug": "numpy-pandas",
                "title": "NumPy and pandas",
                "description": "Arrays with NumPy, then loading, cleaning, combining and reshaping tables with pandas.",
                "lesson": "P02_eda_viz/course/S2_numpy_pandas_course.ipynb",
                "exercises": [("P02_eda_viz/exercises/S2_numpy_exercises.ipynb",
                               "P02_eda_viz/solutions/S2_numpy_solutions.ipynb"),
                              ("P02_eda_viz/exercises/S2_pandas_exercises.ipynb",
                               "P02_eda_viz/solutions/S2_pandas_solutions.ipynb"),
                              ("P02_eda_viz/exercises/S2_datetime.ipynb",
                               "P02_eda_viz/solutions/S2_datetime_solutions.ipynb")],
            },
            {
                "slug": "data-visualization",
                "title": "Data visualisation",
                "description": "Exploring a dataset with Plotly Express: distributions, comparisons, relationships.",
                "lesson": "P02_eda_viz/course/S3_visualization_course.ipynb",
                "exercises": [("P02_eda_viz/exercises/S3_visualization_exercises.ipynb",
                               "P02_eda_viz/solutions/S3_visualization_solutions.ipynb")],
            },
            {
                "slug": "interactive-charts",
                "title": "Interactive charts",
                "description": "Subplots, sliders, dropdowns and animations with plotly.graph_objects.",
                "lesson": "P02_eda_viz/course/S3_visualization_advanced_course.ipynb",
                "exercises": [("P02_eda_viz/exercises/S3_visualization_advanced_exercises.ipynb",
                               "P02_eda_viz/solutions/S3_visualization_advanced_solutions.ipynb")],
            },
            {
                "slug": "apis",
                "title": "Working with APIs",
                "description": "What an API is, and how to call one from Python with requests.",
                "lesson": "P03_api/course/S4_api_course.ipynb",
                "exercises": [("P03_api/exercises/S4_api_exercises.ipynb",
                               "P03_api/solutions/S4_api_solutions.ipynb")],
            },
        ],
    },
}

BLOCKED_HOSTS = ("jedha", "fullstack-assets", "full-stack-assets", "essentials-assets")
MAX_TEXT_LINES = 40
MAX_HTML_BYTES = 1_000_000
# Self-hosted (assets/js); course pages live two levels down: courses/<course>/<page>.html
PLOTLY_JS = "../../assets/js/plotly-2.35.2.min.js"
CALLOUT = {"hint": "tip", "tip": "tip", "note": "note", "important": "important",
           "warning": "warning", "caution": "caution", "info": "note"}
HINT_START = re.compile(r"^\s*(💡|\*\*(hints?|tip)\b|(hints?|tip)\s*:)", re.I)
# anchored at the start of a word so long base64 runs (Plotly data) stay linear-time
EMAIL_RE = re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@(?!example\.com)[A-Za-z0-9.-]+\.[a-z]{2,}")
PRIVACY = re.compile(r"(jedha|" + EMAIL_RE.pattern + r"|api[_-]?key\s*=\s*['\"][A-Za-z0-9]{12,}"
                     r"|bucket-|hntran|huynam)", re.I)
DATA_RE = re.compile(r"""['"](\.\./data/[^'"]+)['"]""")

log = []
_fig = [0]


# ---------- helpers ----------

def src(cell):
    s = cell.get("source", "")
    return "".join(s) if isinstance(s, list) else s


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text}


def load(path):
    return json.load(open(path, encoding="utf-8"))


# ---------- markdown ----------

def convert_notes(text):
    def repl(m):
        kind = CALLOUT.get(m.group(1).strip().lower(), "note")
        return f"\n::: {{.callout-{kind}}}\n{m.group(2).strip()}\n:::\n"
    return re.sub(r'<Note\s+type\s*=\s*"([^"]+)"\s*>(.*?)</Note>', repl, text, flags=re.S | re.I)


def drop_blocked(text, where):
    out = []
    for line in text.split("\n"):
        low = line.lower()
        if any(h in low for h in BLOCKED_HOSTS):
            log.append(f"{where}: dropped line pointing to a blocked host: {line.strip()[:90]}")
            continue
        out.append(line)
    return "\n".join(out)


LIST_ITEM = re.compile(r"^\s{0,3}([-*+]|\d+[.)])\s+\S")


def blank_before_lists(text):
    """Jupyter renders a list right under a paragraph line; pandoc needs a blank line first."""
    out, fence = [], False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fence = not fence
        if (not fence and LIST_ITEM.match(line) and out and out[-1].strip()
                and not LIST_ITEM.match(out[-1]) and not out[-1].startswith((" ", "\t", "|", ">"))):
            out.append("")
        out.append(line)
    return "\n".join(out)


def fold_hints(text):
    """Wrap hint paragraphs (💡…, **Hint:**, Tip:, …) in a collapsed 'Show hint' callout."""
    blocks, out = re.split(r"\n\s*\n", text), []
    for b in blocks:
        if HINT_START.match(b) and "Show hint" not in b:
            body = re.sub(r"^\s*💡\s*", "", b)
            out.append(f'::: {{.callout-tip collapse="true" title="Show hint"}}\n{body}\n:::')
        else:
            out.append(b)
    return "\n\n".join(out)


def heading_levels(cells):
    levels = []
    for c in cells:
        if c["cell_type"] != "markdown":
            continue
        fence = False
        for line in src(c).split("\n"):
            if line.lstrip().startswith("```"):
                fence = not fence
            m = None if fence else re.match(r"^(#{1,6})\s", line)
            if m:
                levels.append(len(m.group(1)))
    return levels


def shift_all(cells, top_level):
    levels = heading_levels(cells)
    shift = (top_level - min(levels)) if levels else 0
    for c in cells:
        if c["cell_type"] != "markdown" or not shift:
            continue
        out, fence = [], False
        for line in src(c).split("\n"):
            if line.lstrip().startswith("```"):
                fence = not fence
            m = None if fence else re.match(r"^(#{1,6})(\s+.*)$", line)
            if m:
                line = "#" * min(6, max(1, len(m.group(1)) + shift)) + m.group(2)
            out.append(line)
        c["source"] = "\n".join(out)
    return cells


def copy_local_images(text, nb_path, img_dir, img_rel):
    def fix(path):
        if re.match(r"^(https?:|data:|attachment:)", path):
            return path
        source = (nb_path.parent / path).resolve()
        if not source.exists():
            log.append(f"{nb_path.name}: missing image {path}")
            return path
        img_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, img_dir / source.name)
        return f"{img_rel}/{source.name}"
    text = re.sub(r"(!\[[^\]]*\]\()([^)\s]+)", lambda m: m.group(1) + fix(m.group(2)), text)
    return re.sub(r'(<img[^>]*\bsrc=")([^"]+)', lambda m: m.group(1) + fix(m.group(2)), text)


# ---------- outputs ----------

def plotly_to_html(o):
    """Replace a saved Plotly figure (JSON) with HTML that draws it from the saved data."""
    fig = o["data"]["application/vnd.plotly.v1+json"]
    _fig[0] += 1
    div = f"sbfig{_fig[0]}"
    fig_out = {"data": fig.get("data", []), "layout": fig.get("layout", {})}
    if fig.get("frames"):
        fig_out["frames"] = fig["frames"]  # animations
    payload = json.dumps(fig_out, ensure_ascii=False).replace("</", "<\\/")
    html = (f'<div id="{div}" class="sb-plotly" style="width:100%;min-height:420px"></div>\n'
            f'<script>(function(){{var f={payload};f.layout.autosize=true;delete f.layout.width;'
            f'f.config={{responsive:true,displaylogo:false}};Plotly.newPlot("{div}",f);}})();</script>')
    return {"output_type": "display_data", "metadata": {"sb_plotly": True}, "data": {"text/html": html}}


def shorten(text, where):
    lines = text.split("\n")
    if len(lines) <= MAX_TEXT_LINES:
        return text
    log.append(f"{where}: shortened an output of {len(lines)} lines")
    return "\n".join(lines[:MAX_TEXT_LINES] + [f"… ({len(lines) - MAX_TEXT_LINES} more lines)"])


def clean_outputs(cell, where):
    outs = []
    for o in cell.get("outputs", []):
        if "application/vnd.plotly.v1+json" in o.get("data", {}):
            o = plotly_to_html(o)
        if EMAIL_RE.search(json.dumps(o)):
            log.append(f"{where}: dropped an output containing email addresses")
            continue
        data = o.get("data", {})
        if "text/html" in data and not o.get("metadata", {}).get("sb_plotly"):
            h = src({"source": data["text/html"]})
            if len(h) > MAX_HTML_BYTES:
                log.append(f"{where}: dropped an oversized HTML output ({len(h)//1024} KB)")
                continue
        if "text/plain" in data:
            data["text/plain"] = shorten(src({"source": data["text/plain"]}), where)
        if o.get("output_type") == "stream":
            o["text"] = shorten(src({"source": o["text"]}), where)
        o.pop("execution_count", None) if o.get("output_type") != "execute_result" else o.update(execution_count=None)
        outs.append(o)
    cell["outputs"], cell["execution_count"] = outs, None


# ---------- notebooks ----------

def prepare(cells, nb_path, where, img_dir, img_rel, top_level=None, hints=False):
    cells = [copy.deepcopy(c) for c in cells]
    for c in cells:
        c["metadata"] = {}
        c.pop("id", None)
        if c["cell_type"] == "markdown":
            t = drop_blocked(convert_notes(src(c)), where)
            t = copy_local_images(t, nb_path, img_dir, img_rel)
            t = blank_before_lists(t)
            if sum(1 for l in t.split("\n") if l.lstrip().startswith("```")) % 2:
                t = t.rstrip("\n") + "\n```"
                log.append(f"{where}: closed an unclosed code block in {nb_path.name}")
            c["source"] = fold_hints(t) if hints else t
        elif c["cell_type"] == "code":
            clean_outputs(c, where)
    cells = [c for c in cells if not (c["cell_type"] == "markdown" and not src(c).strip())]
    return shift_all(cells, top_level) if top_level else cells


def drop_title(cells):
    for i, c in enumerate(cells):
        if c["cell_type"] == "markdown" and src(c).strip():
            lines = src(c).split("\n")
            if re.match(r"^#\s", lines[0]):
                rest = "\n".join(lines[1:]).strip()
                return cells[:i] + ([md(rest)] if rest else []) + cells[i + 1:]
            return cells
    return cells


def merge_solutions(ex_cells, sol_cells):
    """Exercise cells in order; cells only in the solution notebook go in a collapsed callout."""
    def key(c, side, i):
        body = src(c).strip()
        if c["cell_type"] == "code" and (not body or body.startswith("# put your code here") and len(body) < 30):
            return f"{side}{i}:empty"  # empty answer cells never act as anchors
        return c["cell_type"] + "\x00" + body
    a = [key(c, "e", i) for i, c in enumerate(ex_cells)]
    b = [key(c, "s", j) for j, c in enumerate(sol_cells)]
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        out += ex_cells[i1:i2]
        extra = [c for c in sol_cells[j1:j2] if src(c).strip()]
        if op != "equal" and extra:
            out.append(md('::: {.callout-note collapse="true" title="Show solution"}'))
            out += extra
            out.append(md(":::"))
    return out


def front_matter(title, description, subtitle):
    return {"cell_type": "raw", "metadata": {}, "source": (
        "---\n"
        f"title: {json.dumps(title, ensure_ascii=False)}\n"
        f"description: {json.dumps(description, ensure_ascii=False)}\n"
        f"subtitle: {json.dumps(subtitle, ensure_ascii=False)}\n"
        "include-in-header:\n"
        "  text: |\n"
        "    <script>window.__sbDefine = window.define; window.define = undefined;</script>\n"
        f"    <script src=\"{PLOTLY_JS}\" charset=\"utf-8\"></script>\n"
        "    <script>window.define = window.__sbDefine;</script>\n"
        "---")}


def write_nb(path, cells):
    nb = {"cells": cells, "nbformat": 4, "nbformat_minor": 5,
          "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                       "language_info": {"name": "python"}}}
    for c in nb["cells"]:
        c["source"] = src(c).splitlines(keepends=True)
        c.setdefault("metadata", {})
        if c["cell_type"] == "code":
            c.setdefault("outputs", [])
            c.setdefault("execution_count", None)
            for o in c["outputs"]:
                if o.get("output_type") == "stream":
                    o["text"] = src({"source": o["text"]}).splitlines(keepends=True)
                for k, v in o.get("data", {}).items():
                    if isinstance(v, str) and k.startswith("text/"):
                        o["data"][k] = v.splitlines(keepends=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(nb, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def student_copy(nb_path, name, img_dir):
    """Lesson / exercise notebook as learners download it: the repo notebook unchanged,
    except image paths (-> ./img) and metadata. Outputs are kept as saved in the repo."""
    cells = copy.deepcopy(load(nb_path)["cells"])
    for c in cells:
        c["metadata"] = {}
        if c["cell_type"] == "markdown":
            c["source"] = copy_local_images(src(c), nb_path, img_dir, "img")
        c["source"] = src(c).splitlines(keepends=True)
    return json.dumps({"cells": cells, "nbformat": 4, "nbformat_minor": 5,
                       "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python",
                                                   "name": "python3"}}}, ensure_ascii=False, indent=1)


# ---------- build ----------

def build_course(key, course, repo):
    out_dir = SITE / "courses" / key
    for sub in ("img", "files"):
        shutil.rmtree(out_dir / sub, ignore_errors=True)
    for old in out_dir.glob("[0-9][0-9]-*.ipynb"):
        old.unlink()
    pages = []
    for n, sec in enumerate(course["sections"], 1):
        name = f"{n:02d}-{sec['slug']}"
        img_dir, img_rel = out_dir / "img" / name, f"img/{name}"
        where = name
        links = (f"::: {{.sb-lesson-links}}\n[Exercises →]({name}-exercises.ipynb)\n"
                 f"[Download notebooks and data (zip)](files/{name}.zip)\n:::")
        ex_links = (f"::: {{.sb-lesson-links}}\n[← Lesson]({name}.ipynb)\n"
                    f"[Download notebooks and data (zip)](files/{name}.zip)\n:::")

        lesson_path = repo / sec["lesson"]
        lesson = prepare(load(lesson_path)["cells"], lesson_path, where, img_dir, img_rel, top_level=1)
        lesson = shift_all(drop_title(lesson), top_level=2)
        write_nb(out_dir / f"{name}.ipynb",
                 [front_matter(sec["title"], sec["description"], f"{course['title']} · Section {n} · Lesson"),
                  md(links)] + lesson +
                 [md(f"::: {{.sb-next}}\n**Your turn:** [{sec['title']}: exercises →]({name}-exercises.ipynb)\n:::")])

        ex_cells = []
        for ex_rel, sol_rel in sec["exercises"]:
            ex_path, sol_path = repo / ex_rel, repo / sol_rel
            ex = prepare(load(ex_path)["cells"], ex_path, where, img_dir, img_rel, top_level=2, hints=True)
            sol = prepare(load(sol_path)["cells"], sol_path, where, img_dir, img_rel, top_level=2, hints=True)
            ex_cells += merge_solutions(ex, sol)
        write_nb(out_dir / f"{name}-exercises.ipynb",
                 [front_matter(f"{sec['title']}: exercises", f"Exercises with hints and solutions: {sec['description']}",
                               f"{course['title']} · Section {n} · Exercises"),
                  md(ex_links + "\n\nTry each exercise on your own first. Open a **hint** if you are stuck, "
                     "then compare with the **solution**.")] + ex_cells)

        # download bundle: lesson + exercise notebooks (no solutions) + data + images
        zpath = out_dir / "files" / f"{name}.zip"
        zpath.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            nbdir = f"{name}/notebooks"
            z.writestr(f"{nbdir}/lesson.ipynb", student_copy(lesson_path, where, img_dir))
            for ex_rel, _ in sec["exercises"]:
                z.writestr(f"{nbdir}/{Path(ex_rel).name}", student_copy(repo / ex_rel, where, img_dir))
            used = set()
            for p in [lesson_path] + [repo / e for e, s in sec["exercises"]] + [repo / s for e, s in sec["exercises"]]:
                used |= set(DATA_RE.findall("\n".join(src(c) for c in load(p)["cells"] if c["cell_type"] == "code")))
            data_root = (lesson_path.parent / "../data").resolve()
            for d in sorted(used):
                f = (lesson_path.parent / d).resolve()
                if f.exists():
                    z.write(f, f"{name}/data/{f.relative_to(data_root)}")
                else:
                    log.append(f"{name}: data file not found {d}")
            if img_dir.exists():
                for f in sorted(img_dir.iterdir()):
                    z.write(f, f"{nbdir}/img/{f.name}")
        pages.append((n, sec, name))
        log.append(f"{name}: built lesson + exercises (zip {zpath.stat().st_size // 1024} KB)")
    write_overview(key, course, pages)
    return out_dir


def write_overview(key, course, pages):
    lines = ["---", f"title: {json.dumps(course['title'])}", f"subtitle: {json.dumps(course['subtitle'])}",
             f"description: {json.dumps('Free ' + course['title'] + ' course: ' + '; '.join(s['title'] for _, s, _ in pages) + '. Lessons, exercises, hints and solutions.')}",
             "---", "", "<!-- Generated by tools/build_courses.py: edit the COURSES config there. -->", "",
             course["intro"], "",
             "Each section comes with a zip of the notebooks and the data, so you can run everything "
             "on your computer (Python 3 with Jupyter, or [Anaconda](https://www.anaconda.com/download)).", ""]
    for n, sec, name in pages:
        lines.append(f"{n}. **[{sec['title']}]({name}.ipynb)**: {sec['description']} "
                     f"[Exercises →]({name}-exercises.ipynb)")
    (SITE / "courses" / key / "index.qmd").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_sidebars(built):
    out = ["# Generated by tools/build_courses.py — do not edit by hand.", "website:", "  sidebar:"]
    for key, course, pages in built:
        out += [f"    - id: {key}", f"      title: \"{course['number']} · {course['title']}\"",
                "      style: floating", "      contents:",
                "        - text: \"← All courses\"", "          href: courses/index.qmd",
                "        - text: \"Overview\"", f"          href: courses/{key}/index.qmd"]
        for n, sec, name in pages:
            out += [f"        - section: \"{n}. {sec['title']}\"", "          contents:",
                    "            - text: \"Lesson\"", f"              href: courses/{key}/{name}.ipynb",
                    "            - text: \"Exercises\"", f"              href: courses/{key}/{name}-exercises.ipynb"]
    (SITE / "courses" / "_sidebars.yml").write_text("\n".join(out) + "\n", encoding="utf-8")


def privacy_scan(paths):
    problems = []
    for p in paths:
        if p.suffix == ".zip":
            with zipfile.ZipFile(p) as z:
                for n in z.namelist():
                    if n.endswith((".ipynb", ".csv", ".json", ".txt", ".md")):
                        t = z.read(n).decode("utf-8", "ignore")
                        problems += [f"{p.name}:{n}: {m.group(0)}" for m in PRIVACY.finditer(t)]
        else:
            t = p.read_text(encoding="utf-8", errors="ignore")
            problems += [f"{p.name}: {m.group(0)}" for m in PRIVACY.finditer(t)]
    return problems


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in COURSES:
        sys.exit(__doc__)
    key, repo = sys.argv[1], Path(sys.argv[2]).resolve()
    course = COURSES[key]
    out = build_course(key, course, repo)
    pages = [(n, s, f"{n:02d}-{s['slug']}") for n, s in enumerate(course["sections"], 1)]
    write_sidebars([(key, course, pages)])
    print("\n".join(dict.fromkeys(log)))
    problems = privacy_scan(list(out.glob("*.ipynb")) + list((out / "files").glob("*.zip")))
    if problems:
        print("\nPRIVACY SCAN FAILED:\n  " + "\n  ".join(sorted(set(problems))))
        sys.exit(1)
    print(f"\n{key}: privacy scan clean.")


if __name__ == "__main__":
    main()
