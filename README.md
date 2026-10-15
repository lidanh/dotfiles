# Lidan's dotfiles

Setup for a clean Apple Silicon Mac: apps, macOS settings, Fish and Starship.

## Install from scratch

1. **Open Terminal and install Apple's command-line tools:**

   ```sh
   xcode-select --install
   ```

   Finish the installation before continuing.

2. **Sign in to the App Store.** Make sure Xcode and Paste are available in your account.

3. **Download the dotfiles:**

   ```sh
   mkdir -p ~/Projects
   git clone https://github.com/lidanh/dotfiles.git ~/Projects/lidan-dotfiles
   cd ~/Projects/lidan-dotfiles
   ```

4. **Choose this Mac's profile and install:**

   Personal Mac:

   ```sh
   ./bootstrap.sh Personal
   ```

   For a work Mac, run `./bootstrap.sh Wonderful` instead.

   Follow password/installer prompts. If `~/Library/LaunchAgents` belongs to root, setup repairs ownership of that directory only. The script installs the tools and apps, applies settings and saves your profile. Packages install one at a time. Failures are listed after the remaining packages are attempted. If interrupted, rerun the same command; completed installs are kept. Some Homebrew packages need Ruby or a source build even though Ruby is not a development runtime in this setup.

5. **Log out and back in, then open Warp.** Use Fish as the shell.

6. **Connect GitHub and check the setup:**

   ```sh
   dots github
   dots check
   ```

   Follow the browser login and SSH-key prompts. Sign in to your apps; install Photoshop/Lightroom through Creative Cloud.

## Daily use

| Command | What it does |
| --- | --- |
| `dots add chrome` | Install, save, commit and push; choose shared or this profile |
| `dots remove slack` | Uninstall and remove from every mise config, then commit and push |
| `dots sync` | Pull, install missing apps, remove previously managed apps deleted from the list, apply settings |
| `dots sync --dry-run` | Preview reconciliation against local files without changing anything |
| `dots setup` | Install missing apps and rerun setup |
| `dots apply` | Apply configuration changes |
| `dots apply --dry-run` | Preview configuration changes |
| `dots check` | Short health summary, differences and next steps |
| `dots check --verbose` | Full diagnostic details |
| `dots update` | Update the configured host packages now |

Examples for adding packages:

```sh
dots add jq                                  # Add a CLI tool
dots add brew-cask:slack                      # Use an exact app token, skipping search
dots add brew-cask:slack --scope Wonderful    # Work Mac only (run on Wonderful)
dots add brew:jq --scope shared               # Both Macs
dots add brew:jq --scope shared --dry-run     # Preview without saving or installing
```

More commands:

```sh
dots setup --dry-run    # Preview the full setup
dots update --dry-run   # Explain which packages the updater handles
dots github             # Connect this Mac to GitHub
dots --help             # Show available commands
```

Before installs and updates, `brew update` runs and mise’s cask metadata is refreshed; downloaded installers are kept. Warp uses the Homebrew cask in `Casks/warp.rb`: the latest official download, with Apple developer signature verification and a checksum exception scoped to Warp. Mise installs normal host packages, checks their state and updates the ones it owns. Warp remains the explicit Homebrew exception. Existing Homebrew-owned apps are left installed and updated through Homebrew; no ownership migration is required.

Your profile is remembered. Host packages also update daily at **11:00 local time**; project dependencies and language runtimes are excluded. App Store updates are handled separately by macOS.

## Where to edit

- **Shared apps and Mac settings:** `mise.toml`. `builtin_display_more_space` applies the More Space HiDPI preset to supported 13-inch Retina / 14-inch / 16-inch MacBook panels only. Run `dots apply` with the lid open and mirroring off; external displays are not configured.
- **Profile additions and Dock order:** `mise.Personal.toml` / `mise.Wonderful.toml`. Dock apps must exist before applying; the list includes current macOS apps such as Apps and iPhone Mirroring.
- **Shell, Git and prompt:** `config/` (symlinked to your home directory)
- **Cursor and Warp preferences:** `config/cursor/` and `config/warp/`; linked by `dots setup` / `dots apply`. Warp cloud sync remains enabled, as on the original Mac.

`dots add` and `dots remove` commit only the affected configuration files and push automatically. Those files must be clean, and your branch must match origin before starting. If push fails, the local commit is kept; fix the connection and run `git push`. For manual edits, commit and push yourself; run `dots sync` on each Mac.

Sync tracks successful installs locally. Its first run does not remove unknown apps; subsequent runs remove only tracked packages that disappeared from the active declarations. Company/manual apps remain untouched. Removing a shared declaration affects both Macs after sync. Removal does not wipe preferences (`--zap` is never used). Mise checks its own installed artifacts and recognizes existing Homebrew receipts. A Homebrew-owned app deleted manually in Finder may need `brew reinstall --cask <token>`. Git, Fish, uv and mas are required by dots. If an app is pinned in the Dock configuration, remove its path there too before applying.

Setup/sync delegates normal installation to mise, so existing mise apps such as Creative Cloud are not converted to Homebrew. If an earlier install was interrupted and no valid record remains, mise may retry it. Targeted removal still uses Homebrew/mas because mise does not support individual removal for all Mac package types. For native mise casks, dots preserves their receipts and verifies recorded artifacts after the vendor uninstall; incomplete removals keep their declarations and remain pending. No broad prune is used.

App settings are a snapshot of the original Mac. Review UI changes with `git diff` before committing; cloud sync may also change Warp settings. Cursor extensions and app sign-ins are not included. Live GUI writes through symlinks have not been verified.

Commands show setup phases, package counters and live update output. `--verbose` shows full commands; `NO_COLOR=1` disables colors. Updates keep a log at `~/Library/Logs/lidan-dotfiles/update.log`.

ChatGPT/Codex appearance and UI preferences live in `config/codex/desktop.toml`. Close the app, run `dots apply` in a separate terminal, then reopen it. These keys merge into `~/.codex/config.toml`; local projects, plugins and MCP settings stay untouched. Edit the repository file to share changes—changes made in the app are not automatically saved back to Git.
