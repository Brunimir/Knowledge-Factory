#!/usr/bin/env python3
"""kzn_paths.py - the one home for the vault root.

In this repository the scripts and the knowledge base share one directory.
Set VAULT_ROOT to point the scripts at a vault that lives somewhere else.
"""
import os
import re
from pathlib import Path

REPO = os.environ.get("VAULT_ROOT") or os.path.dirname(os.path.abspath(__file__))
VAULT = REPO

REPO_PATH = Path(REPO)
VAULT_PATH = Path(VAULT)


def repo_rel(vault_relative_path):
    """Vault-relative to repo-relative, for handing a path to git."""
    return str(vault_relative_path).replace(os.sep, "/").lstrip("/")


# A cloud-sync twin: the copy a sync client leaves after a collision, named
# `<name> (# Edit conflict <date> <id> #)<ext>`. It is not a file of the vault.
_TWIN_SUFFIX = re.compile(r" \(# [^#()]+ \d{4}-\d{2}-\d{2} [0-9A-Za-z]+ #\)")
_TWIN_NAME = re.compile(_TWIN_SUFFIX.pattern + r"(\.[^.\s]+)?$")


def is_sync_twin(name):
    """Is this file name, stem or path a cloud-sync twin?"""
    return bool(_TWIN_NAME.search(os.path.basename(str(name).replace("\\", "/"))))


def without_twins(names):
    """The names or paths that are not twins, in their order and of their type."""
    return (n for n in names if not is_sync_twin(n))
