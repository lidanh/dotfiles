#!/bin/bash
# Install only the small bootstrap prerequisites, then hand off to mise tasks.
set -euo pipefail
root=$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)
profile=${1:-}
if [ -z "$profile" ] && [ -f "$root/.dots-profile" ]; then profile=$(cat "$root/.dots-profile"); fi
case "$profile" in Personal|Wonderful) ;; *) echo 'Usage: ./bootstrap.sh Personal|Wonderful [--dry-run]' >&2; exit 2 ;; esac
dry=false
case "${2:-}" in '') ;; --dry-run) dry=true ;; *) echo 'Unknown option' >&2; exit 2 ;; esac
if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
  echo 'This setup supports Apple Silicon macOS only.' >&2; exit 1
fi
if [ -f "$root/.dots-profile" ] && [ "$(cat "$root/.dots-profile")" != "$profile" ]; then
  echo 'Profile already selected. Review installed apps before changing .dots-profile.' >&2; exit 1
fi
# Keep first-run output readable even before Python is available.
step() {
  if [ -t 1 ] && [ -z "${NO_COLOR+x}" ] && [ "${TERM:-}" != dumb ]; then
    printf '\n\033[36m→ %s\033[0m\n' "$1"
  else
    printf '\n→ %s\n' "$1"
  fi
}
trap 'printf "\n✗ Bootstrap stopped. Fix the error above and rerun the same command to continue.\n" >&2' ERR
printf '\ndots · Set up this Mac · %s\n' "$profile"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/opt/homebrew/sbin:$PATH"
if "$dry"; then
  command -v mise >/dev/null || { echo 'Preview requires mise 2026.10.8 or newer; no prerequisites were installed.' >&2; exit 1; }
  # Trust must be established explicitly by the operator, not silently in a preview.
  echo "Would install Homebrew if missing and install the profile’s packages using mise (Warp through Homebrew). Use dots sync --dry-run after bootstrap for a package reconciliation preview."
  exec mise -C "$root" -E "$profile" bootstrap --only dotfiles,macos-defaults,user,macos-launchd-agents --dry-run
fi
# Never write through the legacy repo's whole-.config symlink.
if [ -L "$HOME/.config" ]; then
  echo '~/.config is a symlink. Migrate it to an ordinary directory first; nothing changed.' >&2; exit 1
fi
step '[1/5] Prepare mise'
if ! command -v mise >/dev/null; then
  version=2026.10.8
  expected=8228699f316dc17931beb86f7a1aac70e4685535430441492ff4e857c72535ad
  temp=$(mktemp -d)
  trap 'rm -rf "$temp"' EXIT
  curl --fail --location --proto '=https' --tlsv1.2 "https://github.com/jdx/mise/releases/download/v$version/mise-v$version-macos-arm64.tar.gz" -o "$temp/mise.tar.gz"
  actual=$(shasum -a 256 "$temp/mise.tar.gz" | awk '{print $1}')
  [ "$actual" = "$expected" ] || { echo 'mise checksum mismatch' >&2; exit 1; }
  tar -xzf "$temp/mise.tar.gz" -C "$temp"
  mkdir -p "$HOME/.local/bin"
  install -m 755 "$temp/mise/bin/mise" "$HOME/.local/bin/mise"
  rm -rf "$temp"
  trap - EXIT
fi
step '[2/5] Save the machine profile and trust configuration'
cd "$root"
mise trust "$root/mise.toml"
mise trust "$root/mise.$profile.toml"
mise trust "$root/config/mise/config.toml"
printf '%s\n' "$profile" > "$root/.dots-profile"
# mise owns package installation; Homebrew is retained for Warp and targeted removal.
step '[3/5] Prepare Homebrew'
if ! command -v brew >/dev/null; then
  temp=$(mktemp -d)
  trap 'rm -rf "$temp"' EXIT
  curl --fail --location --proto '=https' --tlsv1.2 https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh -o "$temp/homebrew-install.sh"
  /bin/bash "$temp/homebrew-install.sh"
  rm -rf "$temp"
  trap - EXIT
fi
step '[4/5] Refresh metadata and prepare installer tools'
/bin/bash "$root/scripts/refresh-packages.sh"
# mas must exist before bootstrap processes App Store entries; uv runs the adapter.
echo "Installing bootstrap prerequisites (uv and mas)..."
mise -E "$profile" bootstrap packages apply --yes --raw brew:uv brew:mas
uv python install 3.13
step '[5/5] Install apps and apply your configuration'
exec "$root/bin/dots" setup
