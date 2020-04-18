function wixssh() {
  ssh $1.wixprod.net -p 41278
}

alias npmpublic="npm config set registry https://registry.npmjs.org/ && npm config get registry"
alias npmprivate="npm config set registry http://npm.dev.wixpress.com && npm config get registry"

function wixmvn() {
  if [[ -f ~/.m2/settings.xml  ]]; then
      mv ~/.m2/settings.xml ~/.m2/wixbackup.xml
      echo "WIX maven settings: off"
  else
      mv ~/.m2/wixbackup.xml ~/.m2/settings.xml
      echo "WIX maven settings: on"
  fi
}

function revertbabel() {
  git checkout master
  git pull
  git nuke revertbabel
  git checkout -b revertbabel
  git revert $1 --no-edit
  git commit --allow-empty -m "#automerge"
  git push origin revertbabel
  open https://github.com/wix-private/wixos/pull/new/revertbabel
}

function bazelfulltest {
  bazel test --config=ut-only $1 && bazel test --config=it $1
}

function bazeladd3rd {
  bazel run @bazel_tooling//define_maven_deps $1
}