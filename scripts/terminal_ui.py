"""Small, dependency-free terminal presentation; no ANSI in redirected output."""
from contextlib import contextmanager
import os
from pathlib import Path
import shlex
import sys
import time

COLORS={'info':'36','ok':'32','warn':'33','error':'31','muted':'2'}

def line(text,kind='info',*,stream=None):
    stream=stream or sys.stdout
    color=stream.isatty() and 'NO_COLOR' not in os.environ and os.environ.get('TERM')!='dumb'
    print(f'\033[{COLORS[kind]}m{text}\033[0m' if color else text,file=stream,flush=True)

def heading(command,profile,dry=False):
    line(f'\ndots · {command} · {profile}'+(' · PREVIEW' if dry else ''))

def command(args,*,dry=False,capture=False):
    if dry or os.environ.get('DOTS_VERBOSE')=='1':
        line(('Preview: ' if dry else '  $ ')+shlex.join(list(map(str,args))),'muted')
    elif not capture:
        executable=Path(str(args[0])).name
        line(f'  › Running {executable}…','muted')

@contextmanager
def stage(label, *, verify=False):
    line(f'\n→ {label}')
    start=time.monotonic()
    try:yield
    except BaseException:
        line(f'✗ {label} stopped','error',stream=sys.stderr)
        raise
    else:
        if verify:line(f'• {label} phase ended; dots check verifies the final state.','muted')
        else:line(f'✓ {label} ({time.monotonic()-start:.0f}s)','ok')
