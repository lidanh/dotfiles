"""Mirror new log output during interactive updates without changing child stdin."""
from contextlib import contextmanager
import codecs
import sys
import threading
import time

@contextmanager
def follow_log(log, label, *, interval=0.1, heartbeat=15):
    log.flush()
    stop=threading.Event()
    output=sys.stdout
    with open(log.name,'rb') as reader:
        reader.seek(0,2)
        def follow():
            decoder=codecs.getincrementaldecoder('utf-8')(errors='replace')
            last=time.monotonic();started=last
            while True:
                done=stop.is_set()
                data=reader.read()
                if data:
                    output.write(decoder.decode(data));output.flush()
                    last=time.monotonic()
                elif not done and time.monotonic()-last>=heartbeat:
                    output.write(f'\nStill running: {label} ({int(time.monotonic()-started)}s elapsed)\n');output.flush()
                    last=time.monotonic()
                if done:
                    output.write(decoder.decode(b'',final=True));output.flush()
                    return
                stop.wait(interval)
        worker=threading.Thread(target=follow,daemon=True)
        worker.start()
        try:yield
        finally:
            log.flush();stop.set();worker.join()
