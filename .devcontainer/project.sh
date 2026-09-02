#!/usr/bin/env bash
# Project tools. The template-owned Dockerfile copies this file and runs it as root, once, at
# the end of the image build, so a project never edits the Dockerfile: install apt packages,
# runtimes or CLIs here, then Rebuild Container. Keep it idempotent; a failing command fails
# the build. This file is yours: a template update never touches it (see .ai/OWNERSHIP).
set -euo pipefail

# Example:
# apt-get update && apt-get install -y --no-install-recommends postgresql-client \
#  && rm -rf /var/lib/apt/lists/*

echo "project.sh: no project tools defined"
