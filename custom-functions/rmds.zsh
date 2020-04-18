function rmds() {
  sudo find $1 -name ".DS_Store" -depth -exec rm {} \;
}

function rmgit() {
  sudo find $1 -name ".git" -depth -exec rm -rf {} \;
}

function rmsvn() {
  sudo find $1 -name ".svn" -depth -exec rm -rf {} \;
}