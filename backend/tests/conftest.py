"""Tests use a throw-away data folder, never the real data/."""
import os
import tempfile

os.environ["HOOPSCOUT_DATA_DIR"] = tempfile.mkdtemp(prefix="hoopscout_test_")

# no network in tests: rule-based coach report
os.environ["GROQ_API_KEY"] = ""
