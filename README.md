# Kaggle Learn – Local Edition

Every [Kaggle Learn](https://www.kaggle.com/learn) course as Jupyter notebooks you can run **on your own
machine**: no Kaggle notebook editor or browser session needed. Exercises keep their automatic feedback
(`q1.check()`, `q1.hint()`, `q1.solution()`), and the links between lessons point at the local files.

- **17 current courses + 6 retired ("legacy") courses**, 242 notebooks (tutorials and exercises)
- A one-command **data downloader** that fetches each course's Kaggle datasets into the folder the
  notebooks expect
- Per-course `README.md` with the lesson list and the data that course uses

> This is an unofficial community project, not affiliated with or endorsed by Kaggle.
> The notebooks come from Kaggle's open-source [`learntools`](https://github.com/Kaggle/learntools)
> repository (Apache-2.0). See [Credits & license](#credits--license).

---

## Courses

| Folder | Course | Extra requirements | Data |
|---|---|---|---|
| [01-intro-to-programming](courses/01-intro-to-programming) | Intro to Programming | – | Titanic competition (1 lesson) |
| [02-python](courses/02-python) | Python | – (lesson 7 imports TensorFlow: `requirements/deep-learning.txt`) | none |
| [03-intro-to-machine-learning](courses/03-intro-to-machine-learning) | Intro to Machine Learning | – | datasets + competitions |
| [04-pandas](courses/04-pandas) | Pandas | – | datasets |
| [05-intermediate-machine-learning](courses/05-intermediate-machine-learning) | Intermediate Machine Learning | – | competition |
| [06-data-visualization](courses/06-data-visualization) | Data Visualization | – | dataset |
| [07-feature-engineering](courses/07-feature-engineering) | Feature Engineering | – | dataset + competition |
| [08-intro-to-sql](courses/08-intro-to-sql) | Intro to SQL | `requirements/sql.txt` | BigQuery (no download) |
| [09-advanced-sql](courses/09-advanced-sql) | Advanced SQL | `requirements/sql.txt` | BigQuery (no download) |
| [10-intro-to-deep-learning](courses/10-intro-to-deep-learning) | Intro to Deep Learning | `requirements/deep-learning.txt` | datasets |
| [11-computer-vision](courses/11-computer-vision) | Computer Vision | `requirements/deep-learning.txt` | datasets |
| [12-time-series](courses/12-time-series) | Time Series | – | dataset + competition |
| [13-geospatial-analysis](courses/13-geospatial-analysis) | Geospatial Analysis | `requirements/geospatial.txt` | datasets |
| [14-machine-learning-explainability](courses/14-machine-learning-explainability) | Machine Learning Explainability | `requirements/explainability.txt` | datasets |
| [15-intro-to-ai-ethics](courses/15-intro-to-ai-ethics) | Intro to AI Ethics | – | datasets |
| [16-data-cleaning](courses/16-data-cleaning) | Data Cleaning | `requirements/data-cleaning.txt` | datasets |
| [17-intro-to-game-ai-and-reinforcement-learning](courses/17-intro-to-game-ai-and-reinforcement-learning) | Intro to Game AI & RL | `requirements/game-ai.txt` | none to download |
| `legacy-*` (6 folders) | Retired: NLP, Deep Learning (old), Feature Engineering (old), Embeddings, Microchallenges, BigQuery ML | `requirements/legacy.txt` | varies |

Each lesson has a **tutorial** (`NN-tutorial-*.ipynb`) and usually an **exercise** (`NN-exercise-*.ipynb`).
Read the tutorial, then do the exercise.

---

## Prerequisites

| What | Why | How |
|---|---|---|
| **Python 3.10 – 3.12** (3.11 recommended) | Runs the notebooks. TensorFlow doesn't support newer versions yet. | [python.org](https://www.python.org/downloads/), `brew install python@3.11`, `pyenv`, or conda |
| **Git** | To clone this repo and install `learntools` | [git-scm.com](https://git-scm.com/downloads) (macOS: `xcode-select --install`) |
| **A free Kaggle account + API token** | To download the course datasets | See [Kaggle API token](#kaggle-api-token) |
| **~2 GB disk** for the core courses (much more for deep learning / `--all`) | Datasets | – |
| macOS only: **OpenMP** | XGBoost won't load without it (`libomp.dylib could not be loaded`) | `brew install libomp` |
| SQL courses only: **Google Cloud project** (free BigQuery sandbox) | The SQL courses query BigQuery live | See [SQL courses (BigQuery)](#sql-courses-bigquery) |
| Optional: **GPU** | Speeds up deep learning / computer vision. CPU works too, just slower. | NVIDIA CUDA, or `pip install tensorflow-metal` on Apple Silicon |
| Optional: **Graphviz** system package | Decision-tree drawing in ML Explainability | `brew install graphviz` / `sudo apt install graphviz` / `choco install graphviz` |

---

## Quick start

### 1. Get the code

```bash
git clone https://github.com/actuallyhrishikesh/kaggle-learn-local.git
```

```bash
cd kaggle-learn-local
```

### 2. Create an environment and install

**Easiest: run the setup script.** It creates `.venv/`, installs the core requirements and `learntools`.
Add course extras as arguments (`sql`, `deep-learning`, `geospatial`, `explainability`, `data-cleaning`,
`game-ai`, `legacy`, `all`).

macOS / Linux:

```bash
./scripts/setup.sh
```

```bash
./scripts/setup.sh deep-learning geospatial
```

Windows (PowerShell):

```powershell
.\scripts\setup.ps1 deep-learning
```

**Or by hand:**

```bash
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
pip install --no-build-isolation git+https://github.com/Kaggle/learntools.git
# then any extras you need, e.g.
pip install -r requirements/deep-learning.txt
```

> `learntools` must be installed **after** `requirements.txt` with `--no-build-isolation`, because its
> `setup.py` imports pandas.

Using conda instead? `conda create -n kaggle-learn python=3.11 && conda activate kaggle-learn`, then run
the same `pip install` lines.

### 3. Add your Kaggle API token

See [Kaggle API token](#kaggle-api-token) below. It takes about a minute.

### 4. Download a course's data

```bash
python scripts/download_data.py 04-pandas
```

- `python scripts/download_data.py --list` shows every course and what it downloads
- partial names work: `python scripts/download_data.py pandas time-series`
- `--all` downloads everything (many GB), `--dry-run` only shows what would be fetched,
  `--skip <name>` skips a source

Files go to `courses/input/<dataset-name>/`. That is the local stand-in for Kaggle's `/kaggle/input/`, so
the notebooks' `../input/...` paths work unchanged.

### 5. Start Jupyter and open a lesson

```bash
jupyter lab
```

Open e.g. `courses/04-pandas/01-tutorial-creating-reading-and-writing.ipynb`. Run the cells top to bottom.
In exercises, run the setup cell first, then use `q1.check()`, `q1.hint()` and `q1.solution()`.

VS Code works too: open the folder, open a notebook, and pick the `.venv` interpreter as the kernel.

> **Run notebooks from their own folder.** Jupyter and VS Code do this by default. Paths like
> `../input/...` are relative to the notebook's location (`courses/<course>/`).

---

## Kaggle API token

1. Sign in at [kaggle.com](https://www.kaggle.com) and go to **Settings → API**.
2. Choose one way to authenticate:
   - **Easiest:** run `kaggle auth login` inside the activated environment and follow the browser prompt.
   - **Token:** click **Generate New Token**, then either
     - `export KAGGLE_API_TOKEN=<token>` (PowerShell: `$env:KAGGLE_API_TOKEN="<token>"`), or
     - save the token in `~/.kaggle/access_token` (Windows: `C:\Users\<you>\.kaggle\access_token`).
   - **Older `kaggle.json` file** (from "Create Legacy API Key"): put it at `~/.kaggle/kaggle.json` and run
     `chmod 600 ~/.kaggle/kaggle.json` on macOS/Linux.
3. **Competitions:** some courses use competition data (Titanic, House Prices, Store Sales, ...). Kaggle
   only lets you download it after you **accept that competition's rules once on the website**. If a download
   fails with `403`, the script prints the link. Open it, click **I Understand and Accept** (or
   **Join Competition**), and run the script again.

Never commit your token. `.gitignore` already excludes `kaggle.json`, `access_token` and `.env`.

---

## SQL courses (BigQuery)

*Intro to SQL* and *Advanced SQL* query Google's public BigQuery datasets live. On Kaggle that works with no
setup. Locally you need your own Google Cloud project. The **BigQuery sandbox is free** (no credit card;
1 TB of queries per month).

1. Create a project at <https://console.cloud.google.com/> and enable the BigQuery API
   (the [sandbox guide](https://cloud.google.com/bigquery/docs/sandbox) covers this).
2. Install the [gcloud CLI](https://cloud.google.com/sdk/docs/install), then log in for local code:
   ```bash
   gcloud auth application-default login
   ```
3. Tell the client library which project to bill (free in the sandbox):
   ```bash
   export GOOGLE_CLOUD_PROJECT=<your-project-id>
   ```
4. `pip install -r requirements/sql.txt`

`bigquery.Client()` in the notebooks will then just work. Some queries scan large tables. The courses
already show you how to use `dry_run` and `maximum_bytes_billed` to stay within limits.

---

## What's different from running on Kaggle

| On Kaggle | Locally |
|---|---|
| Data mounted at `/kaggle/input` | `courses/input/`, filled by `scripts/download_data.py` |
| "Copy & Edit" / fork links | Links open the local exercise/tutorial notebook |
| Free GPU / TPU | Your hardware. Two notebooks need a **TPU** and only run on Kaggle/Colab: `10-intro-to-deep-learning/07-tutorial-detecting-the-higgs-boson-with-tpus.ipynb` and `legacy-deep-learning/09-tutorial-create-your-first-submission.ipynb` |
| Progress tracked on your Kaggle profile | Not tracked. The checks still tell you whether your answer is right. |
| "Submit to competition" button | Upload `submission.csv` on the competition page, or `kaggle competitions submit -c <comp> -f submission.csv -m "msg"` |
| Kaggle's Docker image pins every library | You install current versions. Rare API changes in newer libraries can break a cell (see Troubleshooting). |

**Want an identical environment?** Kaggle publishes its notebook image
([docker-python](https://github.com/Kaggle/docker-python)). Running it with this repo mounted gives the
exact library versions Kaggle uses, but the image is very large (20 GB+).

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `XGBoostError: libomp.dylib could not be loaded` (macOS) | `brew install libomp` |
| `ModuleNotFoundError: learntools` | Activate the venv, then `pip install --no-build-isolation git+https://github.com/Kaggle/learntools.git` |
| `ModuleNotFoundError` for anything else | Install that course's extras from `requirements/` (see the Courses table) |
| `FileNotFoundError: ../input/...` | Run `python scripts/download_data.py <course>` and make sure the notebook runs from its own folder |
| Competition download `403 Forbidden` | Accept the competition rules on kaggle.com (link printed by the script) |
| `Authentication required to call the Kaggle API` | Set up your token (see [Kaggle API token](#kaggle-api-token)) |
| `DefaultCredentialsError` in SQL notebooks | Follow [SQL courses (BigQuery)](#sql-courses-bigquery) |
| An exercise's setup cell fails after a library upgrade | Pin an older version, e.g. `pip install "scikit-learn<1.6"`, or use Kaggle's Docker image |
| `os.symlink` error on Windows | Enable Windows *Developer Mode* (allows symlinks) or run Jupyter as administrator |
| Tutorials show red error cells | Some are intentional. Tutorials sometimes show what an error looks like. |

---

## Repository layout

```
kaggle-learn-local/
├── courses/
│   ├── 01-intro-to-programming/     # notebooks + README per course
│   ├── ...
│   ├── legacy-*/                    # retired courses
│   ├── input/                       # downloaded data (git-ignored)
│   └── manifest.json                # courses, notebooks and data sources (used by the downloader)
├── requirements.txt                 # core packages
├── requirements/                    # per-course extras
└── scripts/
    ├── setup.sh / setup.ps1         # one-step environment setup
    ├── download_data.py             # fetch Kaggle data for a course
    └── build_from_learntools.py     # regenerate courses/ from Kaggle's learntools repo
```

### Updating the notebooks

Kaggle updates its courses in the `learntools` repo. To regenerate `courses/` from the latest version:

```bash
git clone --depth 1 https://github.com/Kaggle/learntools.git /tmp/learntools
python scripts/build_from_learntools.py /tmp/learntools
```

The script expands Kaggle's notebook macros the way Kaggle's own publishing pipeline does, rewrites
lesson links and `/kaggle/...` paths for local use, and rebuilds `courses/manifest.json`. It reads the
upstream metadata files as data and never runs upstream code. The commit it was built from is recorded in
`manifest.json` (`learntools_commit`).

---

## Credits & license

- Course content © Kaggle and the original authors (Alexis Cook, Dan Becker, Rachael Tatman, Ryan Holbrook,
  Aleksey Bilogur, Colin Morris and others). It comes from
  [github.com/Kaggle/learntools](https://github.com/Kaggle/learntools), released under the
  **Apache License 2.0**. The notebooks were modified for local use (macro expansion, local links and
  paths, Kaggle-only install cells removed).
- The original courses with videos, certificates and discussion forums are at <https://www.kaggle.com/learn>.
  Please support them.
- **Datasets are not included in this repo.** They are downloaded from Kaggle under each dataset's own
  license and Kaggle's terms. Check a dataset's page before reusing it elsewhere.
- This repository is distributed under the Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
