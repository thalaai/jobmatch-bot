# Contributing

Thanks for contributing to `jobmatch-bot`.

## Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

## Default Engine

Open-source contributions should target `job_intel/`.

Primary run command:

```bash
cp job_intel_sources.example.yaml job_intel_sources.yaml
python -m job_intel.cli --sources job_intel_sources.yaml --out-dir ./out --min-score 0.50
```

## Add a Source
1. Add a company entry and a source entry in `job_intel_sources.example.yaml`.
2. Use a stable structured source if possible.
3. Prefer ATS-backed endpoints over general HTML scraping.

## Add an Adapter
1. Add a new adapter in `job_intel/adapters/`.
2. Implement the `BaseAdapter` contract.
3. Return `RawJob` objects from `fetch_raw`.
4. Normalize through `normalize_job`.
5. Wire the adapter in `job_intel/pipeline.py`.

## Coding Expectations
- Keep functions small and readable.
- Prefer structured APIs and embedded data over DOM scraping.
- Never swallow source failures silently.
- Keep diagnostics accurate.
- Don’t add a web app or auth layer.

## Testing
Run focused tests when available:

```bash
python -m pytest
```

If `pytest` is not installed in the target environment, document that in your PR notes.

## Submitting a PR
- Keep changes focused.
- Update docs when you add a source or adapter.
- Include a sample diagnostics row when possible.
- Avoid committing local output files, resumes, caches, or virtualenv content.
