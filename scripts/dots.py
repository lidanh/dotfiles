#!/usr/bin/env python3
"""Small adapters around mise bootstrap; no third-party Python dependencies."""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tomllib
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
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

def run(args, *, dry=False, capture=False, check=True, timeout=None):
    print('+', ' '.join(map(str, args)), flush=True)
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
    return [ ['bootstrap','packages','status'], ['dotfiles','status'],
             ['bootstrap','macos','defaults','status'],
             ['bootstrap','macos','launchd-agents','status'], ['bootstrap','user','status'] ]

def check_machine(profile):
    failed = False
    print(f'Machine profile: {profile}')
    try: preflight_links()
    except ValueError as error: print('CONFLICT:', error); failed = True
    for command in status_commands():
        result = run(mise(profile, *command, '--missing'), check=False)
        failed |= result.returncode != 0
    failed |= system(profile, check_only=True)
    last = Path.home()/'.local/state/lidan-dotfiles/update.json'
    if last.exists():
        try:
            report = json.loads(last.read_text())
            print('Last update:', json.dumps(report, indent=2))
            failed |= report.get('ok') is not True
        except (ValueError, AttributeError):
            print('Last update: unreadable status; run dots update to retry')
            failed = True
    else:
        print('Last update: not run yet')
    return int(failed)

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
    if package in shared: scope='shared'
    file=ROOT/('mise.toml' if scope=='shared' else f'mise.{profile}.toml')
    command=mise(profile,'bootstrap','packages','use','--path',str(file),package)
    if dry: command.append('--dry-run')
    run(command)
    print('Declaration stays in Git even if a later install needs retrying. Commit and push when ready.')

def homebrew_owned_casks(caskroom=Path('/opt/homebrew/Caskroom')):
    # Both managers share Caskroom. Only Homebrew keeps installed cask definitions here.
    result=set()
    for definition in caskroom.glob('*/.metadata/*/*/Casks/*'):
        if definition.suffix in ('.json','.rb'):
            result.add(definition.parents[4].name)
    return result

def upgrade_groups(configured, homebrew_casks):
    legacy=[p.split(':',1)[1] for p in configured if p.startswith('brew-cask:') and p.split(':',1)[1] in homebrew_casks]
    native=[p for p in configured if p.startswith(('brew:','brew-cask:')) and p not in {'brew-cask:'+name for name in legacy}]
    return native,legacy

def update_packages(profile, background=False, dry=False):
    state=Path.home()/'.local/state/lidan-dotfiles'
    if dry:
        print('Would upgrade declared brew/brew-cask packages for',profile,
              '(Homebrew-owned casks through brew; other packages through mise). No App Store/runtime upgrades.')
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
            brew=shutil.which('brew')
            native,legacy=upgrade_groups(packages(ROOT,profile),homebrew_owned_casks())
            if legacy and not brew:
                errors.append('Homebrew is required to upgrade its existing casks: '+', '.join(legacy))
                legacy=[]
            # Each package has its own exit status: a privileged cask failure cannot hide the rest.
            for package in native:
                execute(mise(profile,'bootstrap','packages','upgrade','--yes',package))
            if legacy:
                execute([brew,'update'])
                for package in legacy: execute([brew,'upgrade','--cask',package])
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

def system(profile, dry=False, check_only=False):
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
    for kind in ['ComputerName','LocalHostName','HostName']:
        actual=subprocess.run(['scutil','--get',kind],capture_output=True,text=True)
        ensure(f'{kind} → {name}',actual.returncode==0 and actual.stdout.strip()==name,
               ['sudo','scutil','--set',kind,name])
    power=subprocess.check_output(['pmset','-g','custom'],text=True)
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

def apply(profile, setup=False, dry=False):
    preflight_links()
    # Store pre-change preferences locally, never in the repository.
    if not dry:
        stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        backup=Path.home()/'.local/state/lidan-dotfiles/backups'/stamp
        backup.mkdir(parents=True,mode=0o700)
        cfg=tomllib.loads((ROOT/'mise.toml').read_text())['bootstrap']['macos']
        domains=set(cfg.get('defaults',{}))|{'NSGlobalDomain','com.apple.symbolichotkeys','com.apple.HIToolbox'}
        for domain in domains:
            (backup/(domain+'.plist')).write_bytes(plistlib.dumps(read_defaults(domain)))
        (backup/'power.txt').write_text(subprocess.check_output(['pmset','-g','custom'],text=True))
    if setup:
        run(mise(profile,'bootstrap','packages','apply','brew:uv','brew:mas'),dry=dry)
        parts='packages,dotfiles,macos-defaults,user,macos-launchd-agents'
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

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['add','check','update','apply','setup','system','github'])
    parser.add_argument('package',nargs='?')
    parser.add_argument('--scope',choices=['shared',*PROFILES])
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--background',action='store_true')
    args=parser.parse_args()
    profile=load_profile()
    if args.command=='add':
        if not args.package:parser.error('add requires a package name')
        add_package(profile,args.package,args.scope,args.dry_run)
    elif args.command=='check':return check_machine(profile)
    elif args.command=='update':return update_packages(profile,args.background,args.dry_run)
    elif args.command in ('apply','setup'):apply(profile,args.command=='setup',args.dry_run)
    elif args.command=='system':system(profile,args.dry_run)
    elif args.command=='github':github_setup(args.dry_run)
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,OSError,subprocess.SubprocessError,EOFError) as error:
        print(f'dots: {error}',file=sys.stderr);sys.exit(1)
    except KeyboardInterrupt:sys.exit(130)
