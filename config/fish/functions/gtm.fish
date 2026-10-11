function gtm --description 'Switch to the default branch of origin'
    set -l branch (git symbolic-ref --quiet --short refs/remotes/origin/HEAD)
    or begin
        echo 'Origin default branch is unknown; run: git remote set-head origin -a' >&2
        return 1
    end
    git switch (string replace 'origin/' '' -- $branch)
end
