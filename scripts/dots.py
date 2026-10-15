#!/usr/bin/env python3
"""Small adapters around mise bootstrap; no third-party Python dependencies."""
import argparse
from contextlib import contextmanager
import datetime
import fcntl
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import stat
import sys
import tomllib
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from package_manager import Manager, canonical
from display import configure as configure_display
from check_report import check as report_check
PROFILES = ('Personal', 'Wonderful')

def load_profile(root=ROOT):
    try:
        profile = (root / '.dots-profile').read_text().strip()
    except FileNotFoundError:
        raise ValueError('Choose this machine once: ./bootstrap.sh Personal (or Wonderful)') from None
    if profile not in PROFILES:
        raise ValueError('Invalid saved profile; expected Personal or Wonderful')
    return profile

def packages(root, profile):
    result = {}
    for name in ['mise.toml', f'mise.{profile}.toml']:
        result.update(tomllib.loads((root / name).read_text())['bootstrap']['packages'])
    return result

def matches(query, catalog):
    query = query.casefold()
    exact = [p for p in catalog if query in (p.casefold(), p.split(':',1)[1].casefold())]
    return sorted(exact or [p for p in catalog if query in p.casefold()])

def choose(options, title):
    if not options:
        raise ValueError('No matching packages found. Use the official Homebrew token.')
    if len(options) == 1:
        return options[0]
    print(title)
    for i, option in enumerate(options, 1): print(f'  {i}. {option}')
    answer = input('Number: ').strip()
    if not answer.isdecimal() or not 1 <= int(answer) <= len(options):
        raise ValueError('No selection made; nothing changed')
    return options[int(answer)-1]

def run(args, *, dry=False, capture=False, check=True, timeout=None, quiet=False):
    if not quiet:print('+', ' '.join(map(str, args)), flush=True)
    if dry: return subprocess.CompletedProcess(args, 0, stdout='')
    return subprocess.run(list(map(str,args)), text=True, capture_output=capture,
                          check=check, timeout=timeout)

def mise(profile, *args):
    binary = shutil.which('mise') or str(Path.home()/'.local/bin/mise')
    return [binary, '-C', str(ROOT), '-E', profile, *args]

def symlink_parent(target, home):
    for parent in target.parents:
        if parent == home: break
        if parent.is_symlink(): return parent
    return None

def preflight_links():
    config = tomllib.loads((ROOT/'mise.toml').read_text())
    conflicts = []
    for target in config['dotfiles']:
        parent = symlink_parent(Path(target).expanduser(), Path.home())
        if parent: conflicts.append(str(parent))
    if conflicts:
        raise ValueError('Parent directories are symlinks: '+', '.join(sorted(set(conflicts)))+
                         '. Migrate these directories first; refusing to write into the old repository.')

def status_commands():
    return [ ['dotfiles','status'],
             ['bootstrap','macos','defaults','status'],
             ['bootstrap','macos','launchd-agents','status'], ['bootstrap','user','status'] ]

def check_machine(profile, verbose=False):
    return report_check(profile,
                        native=lambda command:run(mise(profile,*command),capture=True,check=False,quiet=True),
                        preflight=preflight_links,system=lambda:system(profile,check_only=True,verbose=verbose),
                        manager=Manager(ROOT,profile),verbose=verbose)

def refresh_packages(dry=False):
    run(['/bin/bash',str(ROOT/'scripts/refresh-packages.sh')],dry=dry)

def install_packages(profile, dry=False):
    Manager(ROOT,profile).reconcile(dry=dry,remove=False)

def catalog():
    items=[]
    for manager,resource,field in [('brew','formula','name'),('brew-cask','cask','token')]:
        request=urllib.request.Request(f'https://formulae.brew.sh/api/{resource}.json', headers={'User-Agent':'lidan-dotfiles'})
        with urllib.request.urlopen(request,timeout=60) as response:
            items.extend(f'{manager}:{item[field]}' for item in json.load(response))
    return items

def add_package(profile, query, scope=None, dry=False):
    if query.startswith(('brew:', 'brew-cask:', 'mas:')):
        package=query
        if any(c.isspace() for c in query) or not query.split(':',1)[1]:
            raise ValueError('Invalid package token')
    else:
        package=choose(matches(query,catalog()),'Select package')
    if scope is None:
        scope=choose(['shared',profile], 'Install for which machines?')
    if scope not in ('shared',profile):
        raise ValueError('Scope must be shared or the current machine profile')
    shared=tomllib.loads((ROOT/'mise.toml').read_text())['bootstrap']['packages']
    if canonical(package) in {canonical(p) for p in shared}:scope='shared'
    Manager(ROOT,profile).add(package,scope,dry=dry)


def update_packages(profile, background=False, dry=False):
    state=Path.home()/'.local/state/lidan-dotfiles'
    if dry:
        print('Would upgrade declared brew/brew-cask packages for',profile,
              '(mise packages and existing Homebrew-owned casks). Refreshes metadata first. No App Store/runtime upgrades.')
        return 0
    state.mkdir(parents=True,exist_ok=True,mode=0o700)
    # flock releases automatically after a crash; interactive and scheduled updates share the lock.
    with (state/'update.lock').open('w') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: print('An update is already running.'); return 0
        stamp=datetime.datetime.now().astimezone().isoformat()
        log_dir=Path.home()/'Library/Logs/lidan-dotfiles';log_dir.mkdir(parents=True,exist_ok=True)
        log_path=log_dir/'update.log'
        if log_path.exists() and log_path.stat().st_size > 2_000_000:
            log_path.replace(log_dir/'update.previous.log')
        errors=[]
        with log_path.open('a') as log:
            log.write(f'\n=== {stamp} {profile} ===\n');log.flush()
            def execute(command):
                log.write('+ '+' '.join(command)+'\n');log.flush()
                try:
                    result=subprocess.run(command, stdin=subprocess.DEVNULL if background else None,
                                          stdout=log,stderr=log,timeout=3600)
                    if result.returncode: errors.append(' '.join(command))
                except (OSError,subprocess.TimeoutExpired) as error: errors.append(str(error))
            execute(['/bin/bash',str(ROOT/'scripts/refresh-packages.sh')])
            if not errors:
                for package in sorted(Manager(ROOT,profile).desired()):
                    if package.startswith(('brew:','brew-cask:')):
                        execute([sys.executable,str(ROOT/'scripts/package_manager.py'),
                                 '--root',str(ROOT),'--profile',profile,'upgrade',package])
        report={'time':stamp,'profile':profile,'ok':not errors,'failures':errors,'log':str(log_path)}
        tmp=state/'update.json.tmp';tmp.write_text(json.dumps(report,indent=2)+'\n');tmp.replace(state/'update.json')
        if errors:
            print(f'Update needs attention: {log_path}',file=sys.stderr)
            if background:
                subprocess.run(['osascript','-e','display notification "Some packages need attention. Run dots check." with title "Dotfiles update"'],check=False)
        else: print('Update finished:',log_path)
        return int(bool(errors))

def read_defaults(domain):
    p=subprocess.run(['defaults','export',domain,'-'],capture_output=True)
    if p.returncode: return {}
    return plistlib.loads(p.stdout)

def system(profile, dry=False, check_only=False, verbose=False):
    """Only settings unsupported by native mise defaults live here."""
    failed=False
    def ensure(label, matches, command):
        nonlocal failed
        if matches:return
        failed=True
        print('DIFF:',label)
        if not check_only:run(command,dry=dry)
    name=tomllib.loads((ROOT/f'mise.{profile}.toml').read_text())['vars']['computer_name']
    power_config=tomllib.loads((ROOT/'mise.toml').read_text())['vars']
    if power_config.get('builtin_display_more_space',False):
        failed |= configure_display(dry=dry,check_only=check_only,verbose=verbose)
    for kind in ['ComputerName','LocalHostName','HostName']:
        actual=subprocess.run(['scutil','--get',kind],capture_output=True,text=True)
        ensure(f'{kind} → {name}',actual.returncode==0 and actual.stdout.strip()==name,
               ['sudo','scutil','--set',kind,name])
    power=subprocess.check_output(['pmset','-g','custom'],text=True,stderr=subprocess.PIPE)
    section=None;values={}
    for line in power.splitlines():
        if line.strip().endswith('Power:'):section='c' if 'AC' in line else 'b'
        parts=line.split()
        if section and len(parts)==2:values[(section,parts[0])]=parts[1]
    for source,key,value in [('c','displaysleep',power_config['ac_display_sleep']),('c','sleep',power_config['ac_sleep']),('b','displaysleep',power_config['battery_display_sleep']),('b','sleep',power_config['battery_sleep']),('b','lessbright',power_config['battery_dim'])]:
        # No battery power section means this machine does not expose battery settings.
        if source=='b' and not any(k[0]=='b' for k in values):continue
        ensure(f'power {source} {key} → {value}',values.get((source,key))==str(value),
               ['sudo','pmset','-'+source,key,str(value)])
    library=Path.home()/'Library'
    ensure('Library visible',not (library.stat().st_flags & 0x8000),['chflags','nohidden',str(library)])
    reset={'NSGlobalDomain':['com.apple.keyboard.fnState','AppleActionOnDoubleClick'],
           'com.apple.dock':['showhidden','expose-animation-duration']}
    for domain,keys in reset.items():
        current=read_defaults(domain)
        for key in keys:ensure(f'{domain}/{key} → OS default',key not in current,['defaults','delete',domain,key])
    for domain,key,value in [('com.apple.finder','NewWindowTargetPath',Path.home().as_uri()+'/'),
                             ('com.apple.screencapture','location',str(Path.home()/'Desktop'))]:
        ensure(f'{domain}/{key} → {value}',read_defaults(domain).get(key)==value,
               ['defaults','write',domain,key,'-string',value])
    sources=read_defaults('com.apple.HIToolbox').get('AppleEnabledInputSources',[])
    for label,identifier in [('ABC',252),('Hebrew',-18432)]:
        value={'InputSourceKind':'Keyboard Layout','KeyboardLayout ID':identifier,'KeyboardLayout Name':label}
        xml=plistlib.dumps(value).decode();xml=xml[xml.index('<dict>'):xml.index('</dict>')+7]
        ensure(f'input source {label}',any(s.get('KeyboardLayout ID')==identifier for s in sources),
               ['defaults','write','com.apple.HIToolbox','AppleEnabledInputSources','-array-add',xml])
    return failed

def prepare_launch_agents(dry=False):
    """Repair only the observed root-owned user LaunchAgents directory."""
    home=Path.home()
    directory=home/'Library/LaunchAgents'
    if directory.is_symlink() or symlink_parent(directory,home):
        raise ValueError(f'{directory}: refusing to change ownership through a symlink')
    try:metadata=directory.stat()
    except FileNotFoundError:return  # mise creates an absent directory as the current user.
    if not stat.S_ISDIR(metadata.st_mode):
        raise ValueError(f'{directory} is not a directory')
    uid=os.getuid()
    if uid==0:raise ValueError('Run dots as your login user, not with sudo')
    if metadata.st_uid==0:
        print(f'Repairing root-owned {directory}; files inside are left unchanged.',flush=True)
        run(['sudo','chown',str(uid),str(directory)],dry=dry)
    elif metadata.st_uid!=uid:
        raise ValueError(f'{directory} has unexpected owner UID {metadata.st_uid}; refusing to take it over')
    if not dry and not os.access(directory,os.W_OK|os.X_OK):
        raise ValueError(f'{directory} is still not writable; inspect its permissions and ACL with ls -ldeO@')

def apply(profile, setup=False, dry=False):
    preflight_links()
    prepare_launch_agents(dry=dry)
    # Store pre-change preferences locally, never in the repository.
    if not dry:
        stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        backup=Path.home()/'.local/state/lidan-dotfiles/backups'/stamp
        backup.mkdir(parents=True,mode=0o700)
        cfg=tomllib.loads((ROOT/'mise.toml').read_text())['bootstrap']['macos']
        domains=set(cfg.get('defaults',{}))|{'NSGlobalDomain','com.apple.symbolichotkeys','com.apple.HIToolbox'}
        for domain in domains:
            (backup/(domain+'.plist')).write_bytes(plistlib.dumps(read_defaults(domain)))
        (backup/'power.txt').write_text(subprocess.check_output(['pmset','-g','custom'],text=True,stderr=subprocess.PIPE))
    if setup:
        install_packages(profile,dry=dry)
        parts='dotfiles,macos-defaults,user,macos-launchd-agents'
    else:parts='dotfiles,macos-defaults,macos-launchd-agents'
    command=mise(profile,'bootstrap','--only',parts)
    if dry:command.append('--dry-run')
    run(command)
    system(profile,dry=dry)
    if setup:
        run(mise(profile,'install','node@24','go@1.26'),dry=dry)
    print('Open a new Fish session after setup. Log out/in for preferences to take effect.')

def github_setup(dry=False):
    run(['gh','auth','login','--hostname','github.com','--git-protocol','ssh','--web'],dry=dry)
    print('gh can generate and upload a new machine SSH key during login. Keep private keys local.')
    run(['gh','auth','status','--hostname','github.com'],dry=dry)
    # gh's SSH preference does not change the HTTPS origin used for the initial clone.
    origin = run(['git','-C',str(ROOT),'remote','get-url','origin'],capture=True)
    if origin.stdout.strip() in ('https://github.com/lidanh/dotfiles',
                                  'https://github.com/lidanh/dotfiles.git'):
        run(['git','-C',str(ROOT),'remote','set-url','origin',
             'git@github.com:lidanh/dotfiles.git'],dry=dry)

@contextmanager
def package_lock(dry=False):
    if dry:
        yield;return
    state=Path.home()/'.local/state/lidan-dotfiles'
    state.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (state/'update.lock').open('w') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('Another dots package operation is running; retry afterward') from None
        yield

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['add','remove','sync','check','update','apply','setup','system','github'])
    parser.add_argument('package',nargs='?')
    parser.add_argument('--scope',choices=['shared',*PROFILES])
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--background',action='store_true')
    parser.add_argument('--verbose',action='store_true',help='Show full diagnostics for check')
    args=parser.parse_args()
    profile=load_profile()
    if args.command=='sync':
        before=run(['git','-C',str(ROOT),'rev-parse','HEAD'],capture=True).stdout.strip()
        run(['git','-C',str(ROOT),'pull','--ff-only'],dry=args.dry_run)
        after=run(['git','-C',str(ROOT),'rev-parse','HEAD'],capture=True).stdout.strip()
        if before!=after:os.execv(sys.executable,[sys.executable,*sys.argv])
    if args.command in ('add','remove','setup','sync'):
        with package_lock(args.dry_run):
            if args.command!='remove':refresh_packages(dry=args.dry_run)
            if args.command=='add':
                if not args.package:parser.error('add requires a package name')
                add_package(profile,args.package,args.scope,args.dry_run)
            elif args.command=='remove':
                if not args.package:parser.error('remove requires a package name')
                manager=Manager(ROOT,profile)
                package=(canonical(args.package) if ':' in args.package else
                         choose(matches(args.package,manager.declared()|manager.load()),'Select package to remove'))
                manager.remove(package,dry=args.dry_run)
            elif args.command=='sync':
                Manager(ROOT,profile).reconcile(dry=args.dry_run)
                apply(profile,dry=args.dry_run)
            else:apply(profile,setup=True,dry=args.dry_run)
    elif args.command=='check':return check_machine(profile,verbose=args.verbose)
    elif args.command=='update':return update_packages(profile,args.background,args.dry_run)
    elif args.command=='apply':apply(profile,dry=args.dry_run)
    elif args.command=='system':system(profile,args.dry_run)
    elif args.command=='github':github_setup(args.dry_run)
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,OSError,subprocess.SubprocessError,EOFError) as error:
        print(f'dots: {error}',file=sys.stderr);sys.exit(1)
    except KeyboardInterrupt:sys.exit(130)
