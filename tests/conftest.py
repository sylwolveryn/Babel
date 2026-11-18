"""Shared test fixtures."""

import os

# Never let a test run load (and download) the local OPUS-MT models, even on a
# machine where the optional packages are installed. Tests that exercise the
# backend hand it a fake loader instead.
os.environ.setdefault("BABELCHAT_DISABLE_OPUSMT", "1")
