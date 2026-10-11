#!/usr/bin/env python3
"""Install Warp through Homebrew's scoped latest-release cask in this repository."""
import argparse
import shutil
import subprocess
import sys

TAP='lidanh/dotfiles'
CASK=TAP+'/warp'

def run(command, dry=False, **kwargs):
    print('+',' '.join(command),flush=True)
    if dry:return subprocess.CompletedProcess(command,0,stdout='')
    return subprocess.run(command,check=kwargs.pop('check',True),**kwargs)

def install(dry=False, update=False):
    brew=shutil.which('brew')
    if not brew and not dry:raise ValueError('Homebrew is missing; rerun ./bootstrap.sh with your saved profile.')
    brew=brew or 'brew'
    installed=run([brew,'list','--cask','warp'],dry=dry,capture_output=True,text=True,check=False)
    if update and not dry and installed.returncode:
        print('Warp is not managed by Homebrew yet; run dots setup.');return
    run([brew,'tap',TAP,'https://github.com/lidanh/dotfiles.git'],dry=dry)
    if update or (not dry and installed.returncode==0):
        run([brew,'upgrade','--cask','--greedy',CASK],dry=dry)
    else:
        try:
            run([brew,'install','--cask','--adopt',CASK],dry=dry)
        except subprocess.CalledProcessError:
            print('If Homebrew reports an existing, different Warp.app, move that app out of /Applications and rerun setup. Your ~/.warp settings are separate.',file=sys.stderr)
            raise

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--update',action='store_true')
    args=parser.parse_args()
    try:install(args.dry_run,args.update)
    except (ValueError,OSError,subprocess.SubprocessError) as error:
        print('Warp:',error,file=sys.stderr);sys.exit(1)
    except KeyboardInterrupt:sys.exit(130)
