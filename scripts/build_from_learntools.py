#!/usr/bin/env python3
"""
Build the local course notebooks from Kaggle's open-source `learntools` repo.

Kaggle authors every Kaggle Learn notebook as a "raw" template in
https://github.com/Kaggle/learntools/tree/master/notebooks (Apache-2.0) and renders
it with a small macro system before publishing it on kaggle.com. This script
re-implements that rendering for local use:

  * expands the same macros (#$HIDE$, #%%RM%%, #_UNCOMMENT_IF(PROD)_, #$KEEP_GOING$ ...)
  * rewrites links between lessons so they point at the local .ipynb files
  * rewrites /kaggle/input and /kaggle/working paths to local relative paths
  * writes courses/manifest.json listing the Kaggle datasets/competitions each
    course needs (used by scripts/download_data.py)

The upstream `track_meta.py` files are plain Python data. They are checked with
`ast` (only literals, comprehensions, loops and a few whitelisted calls allowed)
before being evaluated with a minimal set of builtins, so no upstream code runs.

Usage:
    git clone --depth 1 https://github.com/Kaggle/learntools.git /path/to/learntools
    python scripts/build_from_learntools.py /path/to/learntools
"""
import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COURSES_DIR = REPO_ROOT / "courses"

# Order mirrors https://www.kaggle.com/learn. (upstream track dir, local dir name)
CURRENT_COURSES = [
    ("intro_to_programming", "01-intro-to-programming"),
    ("python", "02-python"),
    ("machine_learning", "03-intro-to-machine-learning"),
    ("pandas", "04-pandas"),
    ("ml_intermediate", "05-intermediate-machine-learning"),
    ("data_viz_to_coder", "06-data-visualization"),
    ("feature_engineering_new", "07-feature-engineering"),
    ("sql", "08-intro-to-sql"),
    ("sql_advanced", "09-advanced-sql"),
    ("deep_learning_intro", "10-intro-to-deep-learning"),
    ("computer_vision", "11-computer-vision"),
    ("time_series", "12-time-series"),
    ("geospatial", "13-geospatial-analysis"),
    ("ml_explainability", "14-machine-learning-explainability"),
    ("ethics", "15-intro-to-ai-ethics"),
    ("data_cleaning", "16-data-cleaning"),
    ("game_ai", "17-intro-to-game-ai-and-reinforcement-learning"),
]
# Courses that were retired from the Kaggle Learn homepage but still live in learntools.
LEGACY_COURSES = [
    ("nlp", "legacy-natural-language-processing"),
    ("deep_learning", "legacy-deep-learning"),
    ("feature_engineering", "legacy-feature-engineering"),
    ("embeddings", "legacy-embeddings"),
    ("microchallenges", "legacy-microchallenges"),
    ("bqml", "legacy-bigquery-ml"),
]

BIGQUERY_TRACKS = {"sql", "sql_advanced", "bqml"}

# --------------------------------------------------------------------------- #
# Safe loading of track_meta.py
# --------------------------------------------------------------------------- #
_ALLOWED_NODES = (
    ast.Module, ast.Assign, ast.AugAssign, ast.For, ast.If, ast.Expr, ast.Name,
    ast.Constant, ast.List, ast.Tuple, ast.Dict, ast.Set, ast.ListComp,
    ast.comprehension, ast.Call, ast.keyword, ast.Attribute, ast.Subscript,
    ast.Slice, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.IfExp,
    ast.JoinedStr, ast.FormattedValue, ast.Load, ast.Store, ast.operator,
    ast.unaryop, ast.boolop, ast.cmpop, ast.Pass,
)
_ALLOWED_FUNCS = {"dict", "list", "range", "enumerate", "len", "zip", "sorted", "str", "int"}
_ALLOWED_METHODS = {"append", "extend", "format", "copy", "update", "get", "lower", "upper"}


def load_track_meta(path: Path) -> dict:
    src = path.read_text()
    tree = ast.parse(src, filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(f"{path}: disallowed syntax {type(node).__name__} at line {getattr(node, 'lineno', '?')}")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise ValueError(f"{path}: dunder name {node.id!r}")
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("_") or node.attr not in _ALLOWED_METHODS:
                raise ValueError(f"{path}: disallowed attribute .{node.attr}")
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id not in _ALLOWED_FUNCS:
                raise ValueError(f"{path}: disallowed call {f.id}()")
            if not isinstance(f, (ast.Name, ast.Attribute)):
                raise ValueError(f"{path}: disallowed call expression")
    safe_builtins = {name: __builtins__[name] if isinstance(__builtins__, dict) else getattr(__builtins__, name)
                     for name in _ALLOWED_FUNCS | {"True", "False", "None"}}
    ns = {"__builtins__": safe_builtins}
    exec(compile(tree, str(path), "exec"), ns)  # noqa: S102 - validated above
    return {k: ns[k] for k in ("track", "lessons", "notebooks")}


# --------------------------------------------------------------------------- #
# Track model (mirrors notebooks/nb_utils/track_metadata.py upstream)
# --------------------------------------------------------------------------- #
def slug_munge(s):
    s = s.translate({ord(c): None for c in "(),:&"}).lower()
    return "-".join(s.split())


def file_slug(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "notebook"


def titlecase_simple(s):
    small = {"a", "an", "and", "as", "at", "but", "by", "for", "in", "of", "on", "or", "the", "to", "with", "vs"}
    words = s.split()
    out = []
    for i, w in enumerate(words):
        if w.isupper() or any(c.isupper() for c in w[1:]):
            out.append(w)
        elif i and w.lower() in small:
            out.append(w.lower())
        else:
            out.append(w[:1].upper() + w[1:])
    return " ".join(out)


class Track:
    def __init__(self, track_dir: Path, local_dir: str, legacy: bool):
        meta = load_track_meta(track_dir / "track_meta.py")
        self.key = track_dir.name
        self.track_dir = track_dir
        self.local_dir = local_dir
        self.legacy = legacy
        t = meta["track"]
        self.course_name = t["course_name"]
        self.course_url = t["course_url"]
        author = t["author_username"]
        enable_gpu = t.get("enable_gpu", False)
        self.lessons = [dict(idx=i, topic=l["topic"]) for i, l in enumerate(meta["lessons"])]
        self.notebooks = []
        for raw in meta["notebooks"]:
            nb = dict(raw)
            lesson_idx = nb.pop("lesson_idx", None)
            nb["lesson"] = self.lessons[lesson_idx] if lesson_idx is not None else None
            nb.setdefault("author", author)
            nb.setdefault("enable_gpu", enable_gpu)
            if nb.get("title") is None:
                topic = nb["lesson"]["topic"]
                nb["title"] = ("Exercise: " if nb["type"] == "exercise" else "") + titlecase_simple(topic)
            title = nb["title"][:49] if len(nb["title"]) > 50 else nb["title"]
            nb.setdefault("slug", f"{nb['author']}/{slug_munge(title)}")
            if nb.get("slug") is None:
                nb["slug"] = f"{nb['author']}/{slug_munge(title)}"
            nb.setdefault("scriptid", None)
            for k in ("kernel_sources", "dataset_sources", "competition_sources"):
                v = nb.get(k) or []
                nb[k] = [v] if isinstance(v, str) else list(v)
            # SQL courses query BigQuery directly; their "datasets" are BigQuery-backed placeholders
            nb["bigquery_sources"] = []
            if self.key in BIGQUERY_TRACKS:
                nb["bigquery_sources"], nb["dataset_sources"] = nb["dataset_sources"], []
            # local file name
            if nb["lesson"] is not None:
                n = nb["lesson"]["idx"] + 1
                nb["local_name"] = f"{n:02d}-{nb['type']}-{file_slug(nb['lesson']['topic'])}.ipynb"
                nb["lesson"][nb["type"]] = nb
            else:
                nb["local_name"] = f"extra-{file_slug(Path(nb['filename']).stem)}.ipynb"
            self.notebooks.append(nb)
        # exercise scriptids from prod.yaml (optional)
        prod = track_dir / "prod.yaml"
        if prod.exists():
            ids = parse_exercise_scriptids(prod.read_text())
            for lesson, sid in zip(self.lessons, ids or []):
                if sid is not None and "exercise" in lesson:
                    lesson["exercise"]["scriptid"] = sid
        # resolve kernel deps given as filenames
        by_file = {nb["filename"]: nb for nb in self.notebooks}
        for nb in self.notebooks:
            nb["kernel_sources"] = [by_file[d]["slug"] if d.endswith(".ipynb") and d in by_file else d
                                    for d in nb["kernel_sources"]]
        for i, lesson in enumerate(self.lessons):
            lesson["next"] = self.lessons[i + 1] if i + 1 < len(self.lessons) else None

    @property
    def ordered_notebooks(self):
        order = {"tutorial": 0, "exercise": 1, "extra": 2}
        return sorted(self.notebooks, key=lambda nb: (nb["lesson"]["idx"] if nb["lesson"] else 10**6,
                                                     order[nb["type"]], nb["local_name"]))


def parse_exercise_scriptids(yaml_text):
    """Tiny parser for the `exercise_scriptids: [..]` key (avoids a PyYAML dependency)."""
    m = re.search(r"^exercise_scriptids:\s*\[([^\]]*)\]", yaml_text, re.M)
    if not m:
        m2 = re.search(r"^exercise_scriptids:\s*\n((?:\s*-\s*.*\n?)+)", yaml_text, re.M)
        if not m2:
            return None
        items = [l.strip()[1:].strip() for l in m2.group(1).splitlines() if l.strip().startswith("-")]
    else:
        items = [x.strip() for x in m.group(1).split(",") if x.strip()]
    out = []
    for x in items:
        x = x.split("#")[0].strip()
        out.append(None if x in ("null", "None", "~", "") else int(x))
    return out


# --------------------------------------------------------------------------- #
# Notebook rendering
# --------------------------------------------------------------------------- #
PROD = True  # we render the published ("prod", non-testing) variant


def rel_link(src_track, dst_track, dst_nb):
    if src_track is dst_track:
        return dst_nb["local_name"]
    return f"../{dst_track.local_dir}/{dst_nb['local_name']}"


class Renderer:
    def __init__(self, tracks):
        self.tracks = tracks
        # url -> (track, nb) for rewriting kaggle links to local files
        self.url_map = {}
        for tr in tracks:
            for nb in tr.notebooks:
                self.url_map[f"https://www.kaggle.com/{nb['slug']}"] = (tr, nb)
                if nb.get("scriptid"):
                    self.url_map[f"https://www.kaggle.com/kernels/fork/{nb['scriptid']}"] = (tr, nb)
                    self.url_map[f"https://www.kaggle.com/kernels/fork-version/{nb['scriptid']}"] = (tr, nb)

    # --- macro helpers -----------------------------------------------------
    def _lesson(self, tr, nb, lesson_num):
        if lesson_num is None:
            return nb["lesson"]
        return tr.lessons[int(lesson_num) - 1]

    def _link_to(self, tr, lesson, kind):
        target = lesson.get(kind) or lesson.get("exercise") or lesson.get("tutorial")
        return self.cur_link(tr, target)

    def cur_link(self, tr, target):
        return rel_link(self.cur_track, tr, target)

    def expand(self, name, arg, tr, nb, cell):
        lesson = nb["lesson"]
        if name in ("HIDE_INPUT", "HIDE_OUTPUT", "HIDE"):
            md = cell.setdefault("metadata", {}).setdefault("jupyter", {})
            if name in ("HIDE_INPUT", "HIDE"):
                md["source_hidden"] = True
            if name in ("HIDE_OUTPUT", "HIDE"):
                md["outputs_hidden"] = True
            return ""
        if name in ("EXERCISE_FORKING_URL", "EXERCISE_URL"):
            return self._link_to(tr, self._lesson(tr, nb, arg), "exercise")
        if name == "TUTORIAL_URL":
            return self._link_to(tr, self._lesson(tr, nb, arg), "tutorial")
        if name == "NEXT_NOTEBOOK_URL":
            if nb["type"] == "tutorial" and "exercise" in lesson:
                return self.cur_link(tr, lesson["exercise"])
            nxt = lesson["next"]
            return self._link_to(tr, nxt, "tutorial")
        if name == "YOURTURN":
            ex = lesson.get("exercise")
            link = self.cur_link(tr, ex) if ex else "#"
            return f"# Your Turn\n\nTry the [hands-on exercise]({link}) with {lesson['topic']}"
        if name == "KEEP_GOING":
            nxt = lesson["next"]
            if nxt is None:
                return ""
            return f"# Keep Going\n\nYou are ready for **[{nxt['topic']}]({self._link_to(tr, nxt, 'tutorial')}).**\n"
        if name == "SUBMIT_TO_COMP":
            return ("To submit to the competition, upload the generated `submission.csv` on the competition's "
                    "**Submit Predictions** page on kaggle.com, or use the Kaggle CLI:\n\n"
                    "```bash\nkaggle competitions submit -c <competition-slug> -f submission.csv -m \"my submission\"\n```\n")
        raise ValueError(f"Unknown macro {name!r} in {tr.key}/{nb['filename']}")

    # --- cell processing ---------------------------------------------------
    @staticmethod
    def _cond(arg):
        return {"PROD": PROD, "DAILY": False, "NOTDAILY": True}.get(arg, arg)

    def process_cell(self, cell, tr, nb):
        src = cell["source"]
        if isinstance(src, list):
            src = "".join(src)
        # expanding macros  #$NAME$ / #$NAME(arg)$
        def repl(m):
            body = m.group(1)
            name, arg = body, None
            if body.endswith(")"):
                name, arg = body[:-1].split("(", 1)
                arg = arg.strip() or None
            return self.expand(name, arg, tr, nb, cell) or ""
        src = re.sub(r"#\$([^$]+)\$", repl, src)
        # cell macros  #%%RM%% / #%%RM_IF(PROD)%%
        top = src.split("\n")[0]
        m = re.match(r"#%%(.+)%%\s*$", top)
        if m:
            name = m.group(1)
            if name == "RM":
                return None
            if name.startswith("RM_IF("):
                if self._cond(name[6:-1].strip()):
                    return None
            else:
                raise ValueError(f"Unknown cell macro {name}")
        # line macros  #_UNCOMMENT_IF(PROD)_ applies to the following line
        lines = src.split("\n")
        out, i = [], 0
        while i < len(lines):
            lm = re.match(r"\s*#_(.+)_\s*$", lines[i])
            if lm and i + 1 < len(lines):
                body = lm.group(1)
                name, arg = body, None
                if body.endswith(")"):
                    name, arg = body[:-1].split("(", 1)
                    arg = self._cond(arg.strip())
                nxt = lines[i + 1]
                if name == "RM" or (name == "RM_IF" and arg):
                    pass
                elif name == "COMMENT" or (name == "COMMENT_IF" and arg):
                    out.append("#" + nxt)
                elif name == "UNCOMMENT" or (name == "UNCOMMENT_IF" and arg):
                    out.append(nxt.replace("#", "", 1))
                else:
                    out.append(nxt)
                i += 2
            else:
                out.append(lines[i])
                i += 1
        src = "\n".join(out)
        src = self.localize(src, cell["cell_type"])
        cell["source"] = src
        return cell

    def localize(self, src, cell_type):
        # Kaggle filesystem -> local layout (notebooks live in courses/<course>/, data in courses/input/)
        if cell_type == "code":
            # Kaggle-only workaround: pip installing learntools into /kaggle/working.
            # Locally learntools is installed once from requirements.txt instead.
            src = re.sub(r"^[ \t]*# Get most recent checking code[ \t]*\n(?=[ \t]*!pip install -U -t)", "", src, flags=re.M)
            src = re.sub(r"^[ \t]*!pip install -U -t \S+ git\+https://github\.com/Kaggle/learntools\.git[^\n]*\n?", "", src, flags=re.M)
            src = re.sub(r"^[ \t]*sys\.path\.append\(['\"]/kaggle/working['\"]\)[ \t]*\n?", "", src, flags=re.M)
        src = src.replace("/kaggle/input", "../input")
        src = src.replace("/kaggle/working/", "./").replace("/kaggle/working", ".")
        # Links to other Kaggle Learn notebooks -> local files
        def link_repl(m):
            url = m.group(0)
            key = url.rstrip("/").split("?")[0].split("#")[0]
            hit = self.url_map.get(key)
            if hit:
                return self.cur_link(*hit)
            return url
        src = re.sub(r"https?://www\.kaggle\.com/(?:kernels/fork(?:-version)?/\d+|[\w-]+/[\w-]+)(?:\?[^\s)\"']*)?",
                     link_repl, src)
        return src

    def render(self, tr, nb):
        self.cur_track = tr
        raw = json.loads((tr.track_dir / "raw" / nb["filename"]).read_text())
        cells = []
        for cell in raw["cells"]:
            src = cell["source"]
            src = "".join(src) if isinstance(src, list) else src
            if src.strip() == "#%%RM_BELOW%%":
                break
            cell = dict(cell)
            cell["source"] = src
            c = self.process_cell(cell, tr, nb)
            if c is None:
                continue
            md = {k: v for k, v in c.get("metadata", {}).items() if not k.startswith("_")}
            c["metadata"] = md
            if c["cell_type"] == "code":
                c["outputs"] = []
                c["execution_count"] = None
            c.pop("id", None)
            c.pop("attachments", None) if not c.get("attachments") else None
            cells.append(c)
        # header / footer like the published versions, but with local links
        if nb["type"] == "exercise" and nb["lesson"] and "tutorial" in nb["lesson"]:
            tut = self.cur_link(tr, nb["lesson"]["tutorial"])
            cells.insert(0, md_cell(f"**This notebook is an exercise in the [{tr.course_name}]({tr.course_url}) course.  "
                                    f"You can reference the tutorial at [this link]({tut}).**\n\n---\n"))
        cells.append(md_cell(f"---\n\n\n\n*Have questions or comments? Visit the [course discussion forum]"
                             f"({tr.course_url}/discussion) to chat with other learners.*"))
        for c in cells:
            c["source"] = split_lines(c["source"])
        out = {
            "cells": cells,
            "metadata": {
                "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                "language_info": {"name": "python"},
                "kaggle_learn": {
                    "course": tr.course_name,
                    "course_url": tr.course_url,
                    "original_notebook": f"https://www.kaggle.com/{nb['slug']}",
                    "dataset_sources": sorted(nb["dataset_sources"]),
                    "competition_sources": sorted(nb["competition_sources"]),
                    "kernel_sources": sorted(nb["kernel_sources"]),
                    "enable_gpu": bool(nb["enable_gpu"]),
                },
            },
            "nbformat": 4,
            "nbformat_minor": 4,
        }
        return out


def md_cell(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text}


def split_lines(s):
    if isinstance(s, list):
        return s
    lines = s.split("\n")
    return [l + "\n" for l in lines[:-1]] + ([lines[-1]] if lines[-1] else [])


# --------------------------------------------------------------------------- #
# Course README
# --------------------------------------------------------------------------- #
def course_readme(tr, nbs, datasets, comps, kernels):
    lines = [f"# {tr.course_name}", ""]
    if tr.legacy:
        lines += ["> **Legacy course** – this course has been retired from the Kaggle Learn homepage, "
                  "but its notebooks are still in Kaggle's `learntools` repo.", ""]
    lines += [f"Original course: <{tr.course_url}>", "", "## Lessons", "",
              "| # | Lesson | Tutorial | Exercise |", "|---|---|---|---|"]
    for lesson in tr.lessons:
        tut = lesson.get("tutorial")
        ex = lesson.get("exercise")
        tut_cell = "[tutorial](%s)" % tut["local_name"] if tut else "–"
        ex_cell = "[exercise](%s)" % ex["local_name"] if ex else "–"
        lines.append(f"| {lesson['idx'] + 1} | {lesson['topic']} | {tut_cell} | {ex_cell} |")
    extras = [nb for nb in nbs if nb["type"] == "extra"]
    if extras:
        lines += ["", "Extra notebooks:", ""] + [f"- [{nb['title']}]({nb['local_name']})" for nb in extras]
    lines += ["", "## Data", ""]
    if tr.key in BIGQUERY_TRACKS:
        lines += ["This course queries Google BigQuery public datasets live, so there is nothing to download. "
                  "You need a (free) Google Cloud project – see **SQL courses (BigQuery)** in the main README.", ""]
    elif not (datasets or comps or kernels):
        lines += ["This course does not need any Kaggle data.", ""]
    else:
        lines += ["Download everything this course needs with (run from the repo root):", "", "```bash",
                  f"python scripts/download_data.py {tr.local_dir}", "```", ""]
    if datasets:
        lines += ["Datasets:", ""] + [f"- [{d}](https://www.kaggle.com/datasets/{d})" for d in datasets] + [""]
    if comps:
        lines += ["Competitions (you must click **Join Competition / I Understand and Accept** on each "
                  "competition's page once before the API lets you download it):", ""]
        lines += [f"- [{c}](https://www.kaggle.com/competitions/{c}/rules)" for c in comps] + [""]
    if kernels:
        lines += ["Outputs of other Kaggle notebooks:", ""] + [f"- [{k}](https://www.kaggle.com/code/{k})" for k in kernels] + [""]
    return "\n".join(lines).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("learntools", type=Path, help="path to a clone of github.com/Kaggle/learntools")
    ap.add_argument("--no-legacy", action="store_true", help="skip retired courses")
    args = ap.parse_args()
    nb_root = args.learntools / "notebooks"
    specs = [(k, d, False) for k, d in CURRENT_COURSES]
    if not args.no_legacy:
        specs += [(k, d, True) for k, d in LEGACY_COURSES]
    tracks = [Track(nb_root / k, d, legacy) for k, d, legacy in specs if (nb_root / k / "track_meta.py").exists()]
    renderer = Renderer(tracks)

    try:
        commit = subprocess.check_output(["git", "-C", str(args.learntools), "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        commit = "unknown"

    manifest = {"source": "https://github.com/Kaggle/learntools", "learntools_commit": commit, "courses": []}
    COURSES_DIR.mkdir(exist_ok=True)
    for tr in tracks:
        out_dir = COURSES_DIR / tr.local_dir
        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True)
        nbs = tr.ordered_notebooks
        datasets, comps, kernels = set(), set(), set()
        entries = []
        for nb in nbs:
            rendered = renderer.render(tr, nb)
            (out_dir / nb["local_name"]).write_text(json.dumps(rendered, indent=1, ensure_ascii=False) + "\n")
            datasets.update(nb["dataset_sources"])
            comps.update(nb["competition_sources"])
            kernels.update(nb["kernel_sources"])
            entries.append(dict(file=nb["local_name"], type=nb["type"], title=nb["title"],
                                lesson=(nb["lesson"]["topic"] if nb["lesson"] else None),
                                original=f"https://www.kaggle.com/{nb['slug']}",
                                datasets=sorted(nb["dataset_sources"]),
                                competitions=sorted(nb["competition_sources"]),
                                kernels=sorted(nb["kernel_sources"]),
                                gpu=bool(nb["enable_gpu"])))
        (out_dir / "README.md").write_text(course_readme(tr, nbs, sorted(datasets), sorted(comps), sorted(kernels)))
        manifest["courses"].append(dict(dir=tr.local_dir, upstream_track=tr.key, name=tr.course_name,
                                        url=tr.course_url, legacy=tr.legacy, datasets=sorted(datasets),
                                        competitions=sorted(comps), kernels=sorted(kernels), notebooks=entries))
        print(f"{tr.local_dir:55s} {len(nbs):3d} notebooks  {len(datasets)} datasets  "
              f"{len(comps)} competitions  {len(kernels)} kernel outputs")
    (COURSES_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    sys.exit(main())
