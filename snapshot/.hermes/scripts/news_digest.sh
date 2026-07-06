#!/usr/bin/env bash
set -euo pipefail
exec "$HOME/.hermes/scripts/news_monitor.py" --digest
