"""Read-only, concise machine health report; raw diagnostics are opt-in."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import re
import subprocess

COMMANDS=[('Dotfiles',['dotfiles','status']),
          ('Mac preferences',['bootstrap','macos','defaults','status']),
          ('Update schedule',['bootstrap','macos','launchd-agents','status']),
          ('Login shell',['bootstrap','user','status'])]
ERRORS=(ValueError,OSError,subprocess.SubprocessError,KeyError,TypeError,AttributeError)

def short(value,limit=180):
    text=' '.join(str(value).split())
    return text if len(text)<=limit else text[:limit-3]+'...'

def records(group,key):
    if group['available'] is not True:raise ValueError(group.get('reason','unavailable'))
    rows=group[key]
    if not isinstance(rows,list) or any(not isinstance(row,dict) for row in rows):raise ValueError('unexpected status format')
    return rows

def check(profile,*,native,preflight,system,manager,report_path=None,verbose=False):
    print(f'dots check · {profile}',flush=True)
    good=[];issues=[];notes=[];actions=[];details=[]
    def issue(text,action=None):
        issues.append(short(text))
        if action and action not in actions:actions.append(action)
    def unknown(label,error):
        diagnostic=str(error)
        for stream in ('stdout','stderr'):
            value=getattr(error,stream,None)
            if value:diagnostic+='\n'+str(value)
        details.append((label+' error',diagnostic))
        message=f'command exited {error.returncode}' if isinstance(error,subprocess.CalledProcessError) else short(error,120)
        issue(f'Could not check {label}: {message}','dots check --verbose')
    def quiet_call(label,fn):
        output=io.StringIO()
        try:
            with redirect_stdout(output),redirect_stderr(output):return fn()
        finally:
            if output.getvalue():details.append((label,output.getvalue().strip()))
    try:quiet_call('Symlink preflight',preflight)
    except ERRORS as error:unknown('symlink safety',error)
    for label,command in COMMANDS:
        try:
            result=native([*command,'--json'])
            details.append((label,(result.stdout or '')+(result.stderr or '')))
            if result.returncode:raise ValueError(result.stderr or f'command exited {result.returncode}')
            data=json.loads(result.stdout)
            if label=='Dotfiles':
                files=data['files'];edits=data['edits'];orphans=data.get('orphaned',[])
                if not all(isinstance(rows,list) for rows in (files,edits,orphans)):raise ValueError('unexpected dotfiles status format')
                bad=[r for r in files+edits if r['state'] not in ('applied','tracked','absent')]+orphans
                if bad:
                    for row in bad[:4]:issue(f'Dotfile {row.get("target",row.get("path","unknown"))}: {row["state"]}',
                                             'dots check --verbose' if row['state'].startswith('orphaned') else 'dots apply')
                    if len(bad)>4:issue(f'{len(bad)-4} more dotfile differences','dots check --verbose')
                else:good.append(f'Dotfiles ({len(files)+len(edits)})')
            elif label=='Mac preferences':
                rows=records(data['macos_defaults'],'entries');bad=[r for r in rows if r['state']!='set']
                typed=[];other=[]
                for row in bad:
                    domain=row['domain'];value=row['value'];current=row['current']
                    if domain in ('com.apple.AppleMultitouchTrackpad','com.apple.driver.AppleBluetoothMultitouch.trackpad') and isinstance(value,bool) and current==f'{int(value)} (integer; expected boolean)':typed.append(row)
                    else:other.append(row)
                if typed:issue(f'Trackpad: {len(typed)} settings stored as 0/1 instead of false/true (values agree).','dots check --verbose')
                for row in other[:5]:
                    if row['domain']=='com.apple.dock' and row['key']=='persistent-apps' and isinstance(row['value'],list):
                        issue(f'Dock: app list/order differs; current {row["current"]}, expected {len(row["value"])} items.','dots apply')
                    else:issue(f'{row["domain"]} / {row["key"]}: {row["state"]}; current {short(row["current"],45)}, expected {short(json.dumps(row["value"]),45)}','dots apply')
                if len(other)>5:issue(f'{len(other)-5} more Mac preference differences','dots check --verbose')
                if not bad:good.append(f'Mac preferences ({len(rows)})')
            elif label=='Update schedule':
                rows=records(data['launchd'],'agents');bad=[r for r in rows if r['state']!='loaded']
                for row in bad:issue(f'Update service {row["name"]}: {row["state"]}','dots apply')
                if not bad:good.append('Update schedule')
            else:
                row=data['login_shell']
                if row['available'] is not True:raise ValueError(row.get('reason','unavailable'))
                if row['state']!='set':issue(f'Login shell: {row["state"]}; expected {row["shell"]}','dots setup')
                else:good.append('Login shell')
        except ERRORS as error:unknown(label,error)
    try:
        desired=manager.desired();states=quiet_call('Package status',manager.status)
        details.append(('Package states',json.dumps(states,indent=2)))
        bad=[p for p in sorted(desired) if states.get(p)!='installed']
        for package in bad[:5]:issue(f'Package {package}: {states.get(package,"unknown")}','dots setup')
        if len(bad)>5:issue(f'{len(bad)-5} more packages need attention','dots check --verbose')
        if not bad:good.append(f'Packages ({len(desired)})')
        pending=manager.load()-desired
        if pending:issue('Pending removal: '+', '.join(sorted(pending)),'dots sync')
    except ERRORS as error:unknown('packages',error)
    output=io.StringIO()
    try:
        with redirect_stdout(output),redirect_stderr(output):different=system()
        lines=[line.removeprefix('DIFF: ').strip() for line in output.getvalue().splitlines() if line.startswith(('DIFF:','DEFERRED:'))]
        if different:
            for line in (lines or ['Additional Mac settings differ'])[:5]:issue(line,'dots apply')
            if len(lines)>5:issue(f'{len(lines)-5} more system differences','dots check --verbose')
        else:good.append('System settings')
    except ERRORS as error:unknown('system settings',error)
    details.append(('System settings',output.getvalue()))
    path=Path(report_path) if report_path is not None else Path.home()/'.local/state/lidan-dotfiles/update.json'
    if path.exists():
        try:
            update=json.loads(path.read_text());details.append(('Last update',json.dumps(update,indent=2)))
            if not isinstance(update,dict) or not isinstance(update.get('ok'),bool):raise ValueError('invalid update report')
            stamp=short(update.get('time','unknown time'),40)
            failures=update.get('failures',[])
            if not isinstance(failures,list):raise ValueError('invalid failures list')
            if update['ok'] and not failures:notes.append(f'Last update: successful ({stamp}).')
            else:
                names=[]
                for failure in failures:
                    packages=re.findall(r'(?:brew-cask|brew|mas):[\w./@+-]+',str(failure))
                    names.extend(p.split(':',1)[1] for p in packages)
                summary=', '.join(dict.fromkeys(names)) if names else f'{len(failures) or "unknown"} operation(s)'
                issue(f'Last update ({stamp}) failed: {summary}.','dots update')
                if update.get('log'):notes.append('Update log: '+short(str(update['log']).replace(str(Path.home()),'~')))
        except ERRORS as error:unknown('last update',error)
    else:notes.append('Automatic updates: no run recorded yet.')
    print('Needs attention.' if issues else 'All checked settings match.')
    if good:print('OK: '+' · '.join(good))
    for item in issues:print('! '+item)
    for note in notes:print(note)
    next_actions=[a for a in actions if a!='dots check --verbose']
    if next_actions:print('Next: '+'; '.join(next_actions))
    if not verbose:print('Full details: dots check --verbose')
    else:
        print('\nDiagnostics:')
        for label,body in details:print(f'\n[{label}]\n{body.strip()}')
    return int(bool(issues))
