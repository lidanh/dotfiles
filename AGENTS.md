# Working on this repository

- Support Apple Silicon macOS only. Keep Personal and Wonderful overlays separate.
- Shared packages belong in mise.toml; work-only additions in mise.Wonderful.toml.
- Use native mise bootstrap features first. Keep supplemental Python stdlib-only and shell scripts small.
- Never read/copy credentials, tokens, private SSH keys, app databases, caches or entire ~/.config trees into Git.
- Do not apply this repository to the host, install apps, or load LaunchAgents merely to test a change. Use isolated test directories and dry-runs.
- Preserve subprocess arguments as lists. Diagnostic/preview paths must not auto-install runtimes.
- Run `python3 -m unittest discover -s tests -v`, `bash -n bootstrap.sh bin/dots` and `mise tasks validate`.
- Record material validation limits. Do not equate a dry-run with a tested fresh-machine installation.
