"""Run selected isolated pytest suites after initializing Django."""

import os
import sys
from pathlib import Path

import django
import pytest

backend_root = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(backend_root))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django.setup()

raise SystemExit(pytest.main(sys.argv[1:]))
