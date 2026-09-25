"""Root conftest.py — excludes scripts/ from pytest collection.

scripts/ contains standalone helper scripts (e2e_api_test.py, train_real_model.py,
dataset_stats.py etc.) that have module-level statements / sys.exit() calls and
are NOT test modules. Excluding them prevents INTERNALERROR during collection.
"""
collect_ignore_glob = ["scripts/*.py"]
