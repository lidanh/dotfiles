#!/bin/bash
# mise 2026.10.8 fetches formula JSON per process, but caches the bulk cask index.
# Invalidate metadata only. Keep all downloaded installers and installed tools.
set -euo pipefail
brew update
cache=$(mise cache path)
[ -n "$cache" ] && [ "${cache#/}" != "$cache" ] || { echo 'Invalid mise cache path' >&2; exit 1; }
echo 'Refreshing Homebrew metadata used by mise (downloaded installers are kept)...'
if [ -d "$cache/system-brew/api" ]; then
  find "$cache/system-brew/api" -type f -name 'cask.*' -delete
fi
