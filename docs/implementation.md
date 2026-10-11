# Dotfiles implementation plan

Approved design: mise bootstrap, Fish, Starship, selective symlinks, Personal/Wonderful overlays, saved machine profile, dots add/check/update/apply, daily background package upgrades, Git rebase, per-machine GitHub SSH authentication. Node/Go use mise; Python and isolated automation use uv. No application installation or host preference changes during development.

## Tasks
- [x] Declare shared packages, profile extras, approved macOS preferences and individual symlinks in mise TOML.
- [x] Build dots dispatcher and persistent profile selection. Unknown/missing profiles must fail before mutations. All subprocess arguments use arrays, never shell interpolation.
- [x] Implement package resolution and scope choice, scoped upgrades, read-only diagnostics and system supplements. Test ambiguous package names, failure propagation, owner separation and dry-run safety.
- [x] Add Fish abbreviations, Starship and Git config; provide GitHub setup without copying credentials.
- [x] Validate TOML with actual mise 2026.10.8, run isolated tests and dry-run both profiles. Write operator README and inspect final repository.

## Boundaries
The destination is a worktree of the existing lidanh/dotfiles repository on codex/modern-dotfiles, based on origin/master. The original checkout and its uncommitted changes remain intact. Existing host credentials, shell files and app data remain untouched. Package ownership stays with Homebrew for its existing casks. Native mise package support is used for new installations. System app updates and runtime version upgrades are not included in the daily job.

## Verification
Run `python3 -m unittest discover -s tests -v`, shell syntax checks, mise tasks validation and both profile dry-runs using isolated mise cache/state directories. Check actual package tokens against Homebrew metadata. Do not infer successful real installation from a dry run.

## Verification results (2026-10-11)

Eighteen tests and Bash syntax checks passed. Isolated entry-point tests cover both profiles, prerequisite ordering and failures, profile persistence, legacy symlink rejection, preview safety and literal argument forwarding. Actual mise 2026.10.8 validated eight tasks in both profiles and completed full native bootstrap dry-runs for Personal and Wonderful. Native symlink deployment was applied twice only under a temporary HOME: first created links, second reported no changes. Homebrew package metadata was checked; Azure CLI is now declared as a cask. All review findings (ownership detection, runtime auto-install during checks and same-token formula/cask routing) were fixed and regression-tested. The fresh HTTPS clone now switches to SSH after GitHub login; failed background updates cause `dots check` to fail. Interactive setup tasks explicitly retain terminal input.

No real app installation, login shell change, launch agent loading, macOS preference application or GitHub authentication was performed. Third-party installer interaction and Fish execution remain untested on this host (Fish is not installed). Existing-machine conflicts require a separate migration before application.
