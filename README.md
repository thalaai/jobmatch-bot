# jobmatch-bot



JobMatch Bot is an AI-assisted job intelligence pipeline that aggregates,
normalizes, deduplicates, and ranks jobs from multiple ATS and company
career systems such as Workday, Greenhouse, Lever, and Eightfold.

The system focuses on **recall-first ingestion followed by ranking**
to help candidates discover relevant roles that traditional job
portals often hide.


## Setup

```bash
git clone https://github.com/thalaai/jobmatch-bot.git
cd jobmatch-bot
deactivate 2>/dev/null
hash -r
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install -e .
```

Verify the install before your first run:

```bash
which python
python --version
python -m pip show job-intel
python -c "import job_intel; print('job_intel import OK')"
job-intel --help
```

Expected result:
- `which python` points to `.venv/bin/python`
- `python -m pip show job-intel` prints package metadata
- the import check prints `job_intel import OK`
- `job-intel --help` shows the CLI usage

## Quick Start

The maintained engine is `job_intel`.

```bash
cp job_intel_sources.example.yaml job_intel_sources.yaml
job-intel --sources job_intel_sources.yaml --resume resume.txt --out-dir ./out --min-score 0.50
```

Outputs:
- `out/normalized_jobs.csv`
- `out/ranked_jobs.csv`
- `out/job_matches.csv`
- `out/job_matches.md`
- `out/diagnostics.csv`

Which file to use:
- Open `out/job_matches.md` first. This is the main human-readable shortlist to review and apply from.
- Use `out/job_matches.csv` if you want the same shortlist in spreadsheet form for sorting or filtering.
- Use `out/ranked_jobs.csv` if you want a larger ranked pool beyond the shortlist.
- Use `out/normalized_jobs.csv` and `out/diagnostics.csv` for analysis and debugging, not for direct job applications.

## First Run

After copying the repo, do this in order:

1. Create your working source registry from the example:

```bash
cp job_intel_sources.example.yaml job_intel_sources.yaml
```

2. Add your resume as `resume.txt` in the repo root.

Example:

```text
jobmatch-bot/
  resume.txt
  job_intel_sources.yaml
  pyproject.toml
```

3. Edit `job_intel_sources.yaml` and add or remove companies/sources you want to search.

Example:
- keep the provided `Amazon`, `Waymo`, and `Zoox` sources if you want a known-good starting point
- disable any source by setting `enabled: false`
- add more companies by adding entries under `companies:` and `sources:`

4. Run the engine:

```bash
job-intel --sources job_intel_sources.yaml --resume resume.txt --out-dir ./out --min-score 0.50
```

Optional first run with source discovery enabled:

```bash
job-intel --sources job_intel_sources.yaml --resume resume.txt --out-dir ./out --min-score 0.50 --discover
```

5. Inspect the results:

```bash
sed -n '1,25p' out/diagnostics.csv
sed -n '1,40p' out/job_matches.md
```

Apply from `out/job_matches.md` first. If you need more options, expand to `out/ranked_jobs.csv`.

## Test Before Upload

Before uploading the repo to GitHub, run one clean local test from the repo root:

```bash
cd /xxxxxx/jobmatch-bot
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install -e .
cp job_intel_sources.example.yaml job_intel_sources.yaml
cp examples/resume.txt resume.txt
which python
which job-intel
python -c "import job_intel; print('job_intel import OK')"
job-intel --help
job-intel --sources ./job_intel_sources.yaml --resume ./resume.txt --out-dir ./out --min-score 0.50
ls -la out
sed -n '1,20p' out/diagnostics.csv
sed -n '1,40p' out/job_matches.md
```

This validates:
- the package installs cleanly
- the CLI resolves correctly
- the app runs end-to-end with example inputs
- the expected output files are generated

Optional test:

```bash
python -m pytest job_intel/tests
```

After testing, remove local-only files before uploading to GitHub:

```bash
rm -rf .venv cache out resume.txt job_intel_sources.yaml
find . -name "__pycache__" -type d -exec rm -rf {} +
find . -name "*.pyc" -delete
```

Do not remove:
- `job_intel_sources.example.yaml`
- `examples/resume.txt`

## Editing Companies

All company configuration lives in `job_intel_sources.yaml`.

You do not need to edit Python code just to:
- add a new company
- remove a company
- disable a failing source
- change a source endpoint
- change search queries in `metadata`

Example source entry:

```yaml
- company: Amazon
  source_name: amazon_search_json
  source_type: amazon_json
  entrypoint: https://www.amazon.jobs/en/search.json
  metadata:
    page_size: 100
    queries:
      - technical program manager
      - program manager
```

## Resume and Candidate Fit

Place your resume in the repo root as `resume.txt`.

The intended default workflow is:
- clone the repo
- add `resume.txt`
- edit `job_intel_sources.yaml`
- run the CLI
- review `out/job_matches.md` first, then use `out/diagnostics.csv` only for troubleshooting

Current scoring uses:
- title family
- seniority signals
- leadership / delivery signals
- domain signals
- location fit

Resume-aware scoring is the next intended extension point in `job_intel/engine/`.

The file `examples/resume.txt` is a format example only.

## Project Layout

- `job_intel/`
  The publishable multi-source engine.
- `job_intel_sources.example.yaml`
  Safe example source registry.
- `examples/`
  Example input files only.

## Source Registry

The engine reads a registry YAML with:
- `companies`
- `sources`

Each source entry defines:
- `company`
- `source_name`
- `source_type`
- `entrypoint`
- optional `metadata`

Supported source families currently include:
- `amazon_json`
- `greenhouse`
- `lever`
- `workday`
- `apple_jsonld`
- `microsoft_search`
- `eightfold`
- `meta_graphql`

## Diagnostics

Every run emits a diagnostics CSV with source health and per-stage counts:
- `raw_found`
- `normalized_found`
- `deduped_out`
- `scored_count`
- `output_count`
- `error`

This is the primary debugging surface when a company returns no jobs.

## Roadmap (short)
- More ATS adapters
- Better Workday and Eightfold coverage
- Stronger normalization and location handling
- Resume-aware scoring
- Historical crawl tracking
- Hosted version later

## Contributing
See `CONTRIBUTING.md` for how to add adapters, sources, and tests.

## Release Checklist

Before publishing a release:
- verify `python -m pip install -e .` succeeds in a clean virtualenv
- copy `job_intel_sources.example.yaml` to `job_intel_sources.yaml` and run one sample crawl
- confirm `out/diagnostics.csv` contains at least one `working` source
- make sure no local outputs, resumes, caches, or temporary directories are present
- replace the placeholder clone URL in `README.md`

## License
MIT (see `LICENSE`).
