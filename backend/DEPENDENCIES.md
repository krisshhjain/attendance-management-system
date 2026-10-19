# Python dependency locks

`requirements.txt` and `requirements-dev.txt` contain exact-version inputs.
Installations use the generated lockfiles, which pin every transitive package
and include SHA-256 hashes for accepted distributions:

- Runtime image: `requirements.lock`
- CI and local development: `requirements-dev.lock`

The backend development lock also includes `coverage.py` for Django coverage
reports. CI runs the full Django test suite and writes `coverage.xml` in the
backend directory; this tooling is not installed in the runtime image.

Both locks target Python 3.10 on 64-bit Linux. Pip is configured to accept
binary distributions only, and installs use `--require-hashes` so an
unlisted package or artifact with a different hash is rejected.

After changing either input file, regenerate both locks from `backend/` with
uv:

```powershell
uv pip compile requirements.txt --generate-hashes --python-version 3.10 --python-platform x86_64-manylinux_2_17 --output-file requirements.lock
uv pip compile requirements-dev.txt --generate-hashes --python-version 3.10 --python-platform x86_64-manylinux_2_17 --output-file requirements-dev.lock
```

Then verify both installation paths with the backend Docker build and the CI
dependency installation step.
