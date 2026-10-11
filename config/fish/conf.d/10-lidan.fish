fish_add_path --path $HOME/.local/bin /opt/homebrew/bin /opt/homebrew/sbin
if command -q mise
    if status is-interactive
        mise activate fish | source
    else
        mise activate fish --shims | source
    end
end
if not status is-interactive
    return
end
if command -q starship
    starship init fish | source
end
abbr -a gp 'git push origin HEAD'
abbr -a gl 'git pull --prune'
abbr -a gd 'git diff'
abbr -a gc 'git commit'
abbr -a gca 'git commit -a'
abbr -a gco 'git checkout'
abbr -a gb 'git branch'
abbr -a gst 'git status -sb'
abbr -a gac 'git add -A; and git commit -m'
abbr -a glog 'git log --graph --oneline --decorate'
abbr -a gcb 'git branch --show-current | pbcopy'
abbr -a d docker
abbr -a d-c 'docker compose'
abbr -a ll 'ls -lh'
abbr -a la 'ls -lah'
# Personal machine-only additions stay outside Git.
if test -f $HOME/.config/fish/local.fish
    source $HOME/.config/fish/local.fish
end
