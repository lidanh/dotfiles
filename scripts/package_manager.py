"""Host package declarations, scoped reconciliation and Git publication.

Mise owns normal installation and status. Existing Homebrew-owned casks keep
their owner; Warp remains a scoped exception. Homebrew/mas provide targeted
uninstallation until mise supports it. Never run a whole-machine prune or zap.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import tomllib

PROTECTED={'brew:uv','brew:mas','brew:fish','brew:git'}
WARP='brew-cask:lidanh/dotfiles/warp'

def split_package(package):
    manager,sep,token=package.partition(':')
    if not sep or manager not in ('brew','brew-cask','mas') or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9@+_.-]*(?:/[A-Za-z0-9][A-Za-z0-9@+_.-]*)*',token):
        raise ValueError('Invalid package token: '+package)
    if manager=='mas' and not token.isdecimal():raise ValueError('Use a numeric App Store ID')
    if manager=='brew' and token.startswith('homebrew/core/'):token=token.removeprefix('homebrew/core/')
    if manager=='brew-cask' and token.startswith('homebrew/cask/'):token=token.removeprefix('homebrew/cask/')
    if token in ('warp','homebrew/cask/warp') and manager=='brew-cask':token='lidanh/dotfiles/warp'
    return manager,token

def canonical(package):
    return ':'.join(split_package(package))

def protected(package):
    manager,token=split_package(package)
    return manager=='brew' and 'brew:'+token.split('/')[-1] in PROTECTED

def atomic_write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.'+path.name,dir=path.parent)
    try:
        with os.fdopen(fd,'w') as stream:stream.write(text)
        if path.exists():os.chmod(name,path.stat().st_mode & 0o777)
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)

def declaration_spans(text):
    """Find assignments/tables using TOML's parser, preserving unrelated text."""
    parsed=tomllib.loads(text)
    declarations=parsed.get('bootstrap',{}).get('packages',{})
    lines=text.splitlines(keepends=True);spans=[];section=False;i=0
    while i<len(lines):
        line=lines[i].strip()
        if line.startswith('['):
            section=False
            try:header=tomllib.loads(line+'\n').get('bootstrap',{}).get('packages')
            except tomllib.TOMLDecodeError:header=None
            if isinstance(header,dict):
                if not header:section=True
                elif len(header)==1:
                    key=next(iter(header));end=i+1
                    while end<len(lines) and not lines[end].lstrip().startswith('['):end+=1
                    spans.append((key,i,end));i=end;continue
        elif section and line and not line.startswith('#'):
            end=i+1
            while True:
                try:entry=tomllib.loads(''.join(lines[i:end]));break
                except tomllib.TOMLDecodeError:
                    end+=1
                    if end>len(lines):raise ValueError('Cannot safely edit package declaration')
            if len(entry)!=1:raise ValueError('Cannot safely split package declaration')
            key=next(iter(entry));spans.append((key,i,end));i=end;continue
        i+=1
    found={k for k,_,_ in spans}
    if set(declarations)!=found:raise ValueError('Unsupported TOML package layout; use [bootstrap.packages]')
    return lines,spans

class Manager:
    def __init__(self,root,profile,state_dir=None):
        self.root=Path(root);self.profile=profile
        self.state=Path(state_dir) if state_dir else Path.home()/'.local/state/lidan-dotfiles'
        self.ledger=self.state/'managed-packages.json'

    def command(self,args,*,dry=False,capture=False,check=True):
        print('+',' '.join(map(str,args)),flush=True)
        if dry:return subprocess.CompletedProcess(args,0,stdout='')
        return subprocess.run(list(map(str,args)),check=check,text=True,capture_output=capture)

    def config_files(self):
        return sorted(p for p in self.root.rglob('*.toml')
                      if '.git' not in p.relative_to(self.root).parts and not p.is_symlink()
                      and (p.name.startswith(('mise.','.mise.')) or (p.name=='config.toml' and p.parent.name=='mise')))

    def desired(self):
        result={}
        for name in ('mise.toml',f'mise.{self.profile}.toml'):
            data=tomllib.loads((self.root/name).read_text()).get('bootstrap',{}).get('packages',{})
            for key,value in data.items():
                if value!='latest' and value!={} and value!={'version':'latest'}:
                    raise ValueError(f'Unsupported host package options for {key}; expected latest')
                result[canonical(key)]=value
        return set(result)

    def declared(self):
        result=set()
        for path in self.config_files():
            for key in tomllib.loads(path.read_text()).get('bootstrap',{}).get('packages',{}):result.add(canonical(key))
        return result

    def load(self):
        if not self.ledger.exists():return set()
        record=json.loads(self.ledger.read_text())
        if record.get('schema')!=1 or record.get('profile')!=self.profile:
            raise ValueError('Managed package state/profile mismatch; refusing automatic removal')
        if not isinstance(record.get('packages'),list):raise ValueError('Invalid managed package state')
        return {canonical(p) for p in record['packages']}

    def save(self,managed):
        self.state.mkdir(parents=True,exist_ok=True,mode=0o700)
        atomic_write(self.ledger,json.dumps({'schema':1,'profile':self.profile,'packages':sorted(managed)},indent=2)+'\n')

    def plan(self):
        desired=self.desired();previous=self.load()
        return sorted(desired),sorted(previous-desired)

    def native_receipts(self,token):
        room=Path('/opt/homebrew/Caskroom')/token.split('/')[-1]
        return [tomllib.loads(p.read_text()) for p in room.glob('*/.mise-cask.toml')]

    def homebrew_present(self,package):
        manager,token=split_package(package)
        if manager=='mas':
            lines=self.command(['mas','list'],capture=True).stdout.splitlines()
            return any(line.split() and line.split()[0]==token for line in lines)
        if manager=='brew-cask':
            room=Path('/opt/homebrew/Caskroom')/token.split('/')[-1]
            return any(p.suffix in ('.rb','.json') for p in room.glob('.metadata/*/*/Casks/*'))
        # A failure to enumerate packages is an error, not proof of absence.
        flag='--cask' if manager=='brew-cask' else '--formula'
        names=self.command(['brew','list',flag,'--full-name'],capture=True).stdout.splitlines()
        return any(n==token or n.split('/')[-1]==token.split('/')[-1] for n in names)

    def mise_command(self,*args):
        binary=shutil.which('mise') or str(Path.home()/'.local/bin/mise')
        return [binary,'-C',str(self.root),'-E',self.profile,'bootstrap','packages',*args]

    def status(self):
        # Let mise validate its receipts/artifacts and recognize Homebrew owners.
        data=json.loads(self.command(self.mise_command('status','--json'),capture=True).stdout)
        result={}
        for manager,group in data.items():
            for package in group['packages']:
                key=canonical(manager+':'+package['package'])
                result[key]=package['state'] if group['available'] else 'unavailable'
        return result

    def present(self,package):
        manager,token=split_package(package)
        if self.homebrew_present(package):return True
        # This union is for removal checks only. Installation/status are left
        # to mise, which checks native artifacts, including self-updating apps.
        return manager=='brew-cask' and bool(self.native_receipts(token))

    def install(self,package,dry=False,upgrade=False):
        manager,token=split_package(package)
        homebrew_owned=manager=='brew-cask' and self.homebrew_present(package)
        if homebrew_owned and not upgrade:
            print('Already installed (Homebrew owner retained):',package);return
        if package==WARP or homebrew_owned:
            if package==WARP:
                self.command(['brew','tap','lidanh/dotfiles','https://github.com/lidanh/dotfiles.git'],dry=dry)
            if upgrade and not homebrew_owned:return
            args=['brew','upgrade' if upgrade else 'install','--cask']
            args+=['--greedy'] if upgrade else ['--adopt']
            self.command([*args,token],dry=dry)
            if not dry and not self.homebrew_present(package):
                raise ValueError(f'{package}: installation did not create a Homebrew record')
            return
        # Explicit package arguments work even before add writes the declaration.
        # Apply is idempotent and understands native mise records; do not force
        # adoption/reinstallation just because Homebrew has no receipt.
        args=self.mise_command('upgrade' if upgrade else 'apply','--yes','--raw',package)
        self.command(args,dry=dry)

    def uninstall(self,package,dry=False):
        manager,token=split_package(package)
        if protected(package):raise ValueError(package+' is required by dots and cannot be removed')
        native=self.native_receipts(token) if manager=='brew-cask' else []
        pending=self.state/'pending-removals'/(''.join(c if c.isalnum() else '_' for c in package)+'.json')
        if pending.exists():native+=json.loads(pending.read_text())
        if native and not dry:atomic_write(pending,json.dumps(native))
        exists=self.present(package)
        if not exists and not native:
            print('Already absent:',package);return
        if manager=='mas':self.command(['mas','uninstall',token],dry=dry)
        else:
            if package==WARP:self.command(['brew','tap','lidanh/dotfiles','https://github.com/lidanh/dotfiles.git'],dry=dry)
            args=['brew','uninstall','--cask' if manager=='brew-cask' else '--formula']
            # Native mise receipts aren't Homebrew receipts. --force allows the
            # vendor cask's uninstall steps to run without inventing metadata.
            if native and not self.homebrew_present(package):args.append('--force')
            self.command([*args,token],dry=dry)
        if not dry:
            if self.present(package):raise ValueError(package+' still has an install record; declaration kept')
            for receipt in native:
                artifacts=set().union(*(receipt.get(key,[]) for key in ('apps','binaries','fonts','completions','generic')))
                for app in artifacts:
                    if Path(app).exists():raise ValueError(f'{app} remains after uninstall; declaration kept')
                for pkg in receipt.get('pkg_ids',[]):
                    if self.command(['pkgutil','--pkg-info',pkg],capture=True,check=False).returncode==0:
                        raise ValueError(f'Installer receipt {pkg} remains; vendor removal needs attention')
            pending.unlink(missing_ok=True)

    def removal_edits(self,package):
        edits={}
        for path in self.config_files():
            text=path.read_text();data=tomllib.loads(text).get('bootstrap',{}).get('packages',{})
            keys={k for k in data if canonical(k)==package}
            if not keys:continue
            lines,spans=declaration_spans(text)
            drop={i for key,start,end in spans if key in keys for i in range(start,end)}
            updated=''.join(line for i,line in enumerate(lines) if i not in drop)
            remaining=tomllib.loads(updated).get('bootstrap',{}).get('packages',{})
            if set(remaining)!=set(data)-keys:raise ValueError('Declaration edit verification failed')
            edits[path]=updated
        return edits

    def addition_edit(self,path,package):
        text=path.read_text();lines,spans=declaration_spans(text)
        data=tomllib.loads(text).get('bootstrap',{}).get('packages',{})
        if any(canonical(k)==package for k in data):return {}
        entry=json.dumps(package)+' = "latest"\n'
        for i,line in enumerate(lines):
            if line.strip()=='[bootstrap.packages]':
                lines.insert(i+1,entry);return {path:''.join(lines)}
        # An empty explicit table works in profile files; subtable-only layouts
        # need a new subtable, rather than redefining the implicit parent.
        return {path:text+'\n[bootstrap.packages.'+json.dumps(package)+']\nversion = "latest"\n'}

    def git_preflight(self,paths):
        branch=self.command(['git','-C',str(self.root),'symbolic-ref','--quiet','--short','HEAD'],capture=True).stdout.strip()
        if not branch:raise ValueError('Checkout a branch before add/remove')
        self.command(['git','-C',str(self.root),'remote','get-url','origin'],capture=True)
        if paths:
            relative=[str(p.relative_to(self.root)) for p in paths]
            self.command(['git','-C',str(self.root),'ls-files','--error-unmatch','--',*relative],capture=True)
            dirty=self.command(['git','-C',str(self.root),'status','--porcelain','--',*relative],capture=True).stdout
            if dirty.strip():raise ValueError('Commit or stash existing edits in affected configuration files before add/remove')
        self.command(['git','-C',str(self.root),'fetch','--no-tags','origin',f'refs/heads/{branch}'],capture=True)
        local=self.command(['git','-C',str(self.root),'rev-parse','HEAD'],capture=True).stdout.strip()
        remote=self.command(['git','-C',str(self.root),'rev-parse','FETCH_HEAD'],capture=True).stdout.strip()
        if local!=remote:raise ValueError('Local branch differs from origin. Pull or publish existing commits before add/remove.')
        return branch

    def publish(self,edits,originals,message,branch):
        if not edits:return
        if any(path.read_text()!=originals[path] for path in edits):
            raise ValueError('Configuration changed during package operation; no edits committed. Retry after reviewing files.')
        for path,text in edits.items():atomic_write(path,text)
        relative=[str(p.relative_to(self.root)) for p in edits]
        try:
            self.command(['git','-C',str(self.root),'commit','--only','-m',message,'--',*relative])
        except subprocess.CalledProcessError as error:
            raise ValueError('Package operation succeeded and files were updated, but commit failed. Review and commit the configuration changes.') from error
        try:self.command(['git','-C',str(self.root),'push','origin',f'HEAD:refs/heads/{branch}'])
        except subprocess.CalledProcessError as error:
            raise ValueError('Package operation and local commit succeeded, but push failed. Resolve the remote issue and run git push; other computers have not received this change.') from error

    def remove(self,package,dry=False):
        package=canonical(package)
        if protected(package):raise ValueError(package+' is required by dots and cannot be removed')
        managed=self.load()
        edits=self.removal_edits(package);originals={p:p.read_text() for p in edits}
        branch=self.git_preflight(edits) if not dry and edits else None
        print('Remove declaration from:',*[str(p.relative_to(self.root)) for p in edits])
        self.uninstall(package,dry=dry)
        if dry:return
        managed.discard(package);self.save(managed)
        self.publish(edits,originals,'Remove '+package,branch)

    def add(self,package,scope,dry=False):
        package=canonical(package)
        managed=self.load()
        path=self.root/('mise.toml' if scope=='shared' else f'mise.{scope}.toml')
        edits=self.addition_edit(path,package);originals={p:p.read_text() for p in edits}
        branch=self.git_preflight(edits) if not dry and edits else None
        self.install(package,dry=dry)
        if dry:
            print('Would declare, commit and push:',package,'in',path);return
        managed.add(package);self.save(managed)
        self.publish(edits,originals,'Add '+package,branch)

    def reconcile(self,dry=False,remove=True):
        desired,removed=self.plan();managed=self.load();failures=[]
        if not self.ledger.exists():print('First sync: establishing managed packages; no untracked apps will be removed.')
        if not remove:removed=[]
        forbidden={p for p in removed if protected(p)}
        if forbidden:raise ValueError('Required dots dependencies cannot be removed: '+', '.join(sorted(forbidden)))
        print('Ensure installed:',', '.join(desired));print('Remove:',', '.join(removed) or '(none)')
        for action,items in [('install',desired),('uninstall',removed)]:
            # Never start removals after a failed installation phase.
            if action=='uninstall' and failures:break
            for package in items:
                try:
                    getattr(self,action)(package,dry=dry)
                    if not dry:
                        managed.add(package) if action=='install' else managed.discard(package)
                        self.save(managed)
                except (ValueError,OSError,subprocess.CalledProcessError) as error:
                    if isinstance(error,subprocess.CalledProcessError) and error.returncode in (130,-2):raise KeyboardInterrupt
                    failures.append(package);print('FAILED:',package,str(error),flush=True)
        if failures:raise ValueError('Packages needing attention: '+', '.join(failures)+'. Successful operations were saved; rerun to retry.')

if __name__=='__main__':
    import argparse
    import sys
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--profile',required=True)
    parser.add_argument('action',choices=['upgrade'])
    parser.add_argument('package')
    args=parser.parse_args()
    try:Manager(args.root,args.profile).install(canonical(args.package),upgrade=True)
    except (ValueError,OSError,subprocess.SubprocessError) as error:
        print(error,file=sys.stderr);sys.exit(1)
