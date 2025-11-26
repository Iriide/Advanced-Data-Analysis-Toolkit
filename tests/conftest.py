import sys
import os
import types


def pytest_configure(config):
    # Ensure 'src' directory is on sys.path so packages like 'core' and 'visualizer' import
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    src_path = os.path.join(repo_root, "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    # Provide a minimal stub for google.genai to avoid import errors during tests
    if "google" not in sys.modules:
        google_mod = types.ModuleType("google")
        genai_mod = types.ModuleType("google.genai")

        # Provide a minimal Client class that can be instantiated by LLMClient
        class DummyClient:
            def __init__(self, *args, **kwargs):
                pass

        genai_mod.Client = DummyClient
        google_mod.genai = genai_mod
        sys.modules["google"] = google_mod
        sys.modules["google.genai"] = genai_mod
