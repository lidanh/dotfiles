function wixssh() {
  ssh $1.wixprod.net -p 41278
}

function wixnpm() {
  if [[ $(npm config get registry) == "https://registry.npmjs.org/"  ]]; then
      npm config set registry http://repo.dev.wix/artifactory/api/npm/npm-repos
      echo "set npm registry to wix: http://repo.dev.wix/artifactory/api/npm/npm-repos"
  else
      npm config set registry https://registry.npmjs.org/
      echo "set npm registry to default: https://registry.npmjs.org/"
  fi
}

function wixmvn() {
  if [[ -f ~/.m2/settings.xml  ]]; then
      mv ~/.m2/settings.xml ~/.m2/wixbackup.xml
      echo "WIX maven settings: off"
  else
      mv ~/.m2/wixbackup.xml ~/.m2/settings.xml
      echo "WIX maven settings: on"
  fi
}

function fixeventim() {
  git checkout master
  git pull
  git nuke fix-eventim
  git checkout -b fix-eventim
}
