# Package reconciliation implementation plan

Goal: dots add/remove commit and push their declaration edits; dots sync pulls and reconciles this machine's managed packages and applies settings. No install alias.

Design: keep declarations in mise TOML, route package operations to Homebrew/mas. Persist successful managed-package membership locally. Sync removes only previously managed declarations no longer desired. First run establishes membership, never infers deletion from all installed apps. Removal searches all repository TOML package declarations, including inactive profiles. Use ordinary uninstall without zap or dependency overrides. Existing mise casks use Homebrew's explicit forced-uninstall compatibility path only with a native receipt, checking recorded installed artifacts afterward. Installation uses adoption and reports conflicts rather than overwriting apps.

- [x] Add tested declaration editing, local ledger, scoped reconciliation, and Homebrew/mas adapter.
- [x] Add Git preflight, isolated commits, automatic pushes with actionable partial-failure output.
- [x] Integrate dispatcher/tasks/bootstrap/update/check and Warp declaration; preserve profile and config behavior.
- [x] Verify isolated failure/retry/dry-run behavior, document migration limits, review and publish.

Constraints: Python standard library; never apply setup/install/uninstall on the development host. Protect bootstrap dependencies. No broad prune, forced Git push, app-data cleanup, or automatic removal in background updates. Never claim a real machine migration was tested based on mocks. Failed removals remain pending in local state; failed installs cannot claim success. Staged or unstaged edits in affected files must be resolved before add/remove; unrelated files never enter generated commits.

Validation: 47 isolated unit/integration tests passed, including real temporary Git repositories and a rejecting remote hook. Bash syntax and git diff checks passed. Mise 2026.10.8 validated all 10 tasks for Personal and Wonderful with isolated state. No fresh-machine installation or native vendor uninstaller was tested. Dock entries require manual removal; receipt-based presence cannot repair app bundles deleted manually in Finder.

## Correction: restore mise ownership (2026-10-16)

The initial Homebrew installer migration reran installers for existing native mise casks. Restore native mise apply/status/upgrade for normal packages. Keep Homebrew-owned casks in place with their original updater; keep the existing explicit Warp exception. Retain targeted Homebrew/mas removal because mise 2026.10.8 cannot remove arbitrary individual Mac packages; do not use broad prune. Git publication and managed-only reconciliation stay unchanged.

Verified with real mise 2026.10.8 in isolated temporary prefixes: Creative Cloud native and Homebrew receipt fixtures both report installed, and apply --dry-run reports already installed. No actual app installation/removal was tested. Warp's public metadata key avoids custom-tap Ruby requirements during status; canonical routing still installs/updates the signed custom Homebrew cask.
