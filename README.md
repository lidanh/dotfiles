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

   Follow password/installer prompts. The script installs the tools and apps, applies settings and saves your profile. If interrupted, rerun the same command.

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
| `dots add chrome` | Find, install and save a package; choose shared or this profile |
| `dots setup` | Install missing apps and rerun setup |
| `dots apply` | Apply configuration changes |
| `dots apply --dry-run` | Preview configuration changes |
| `dots check` | Show missing setup, differences and update results |
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

Your profile is remembered. Host packages also update daily at **11:00 local time**; project dependencies and language runtimes are excluded. App Store updates are handled separately by macOS.

## Where to edit

- **Shared apps and Mac settings:** `mise.toml`
- **Profile additions:** `mise.Personal.toml` / `mise.Wonderful.toml`
- **Shell, Git and prompt:** `config/` (symlinked to your home directory)
- **Cursor and Warp preferences:** `config/cursor/` and `config/warp/`; linked by `dots setup` / `dots apply`. Warp cloud sync remains enabled, as on the original Mac.

Commit and push changes. On the other Mac, pull the repo and run `dots setup`.

App settings are a snapshot of the original Mac. Review UI changes with `git diff` before committing; cloud sync may also change Warp settings. Cursor extensions and app sign-ins are not included. Live GUI writes through symlinks have not been verified.
