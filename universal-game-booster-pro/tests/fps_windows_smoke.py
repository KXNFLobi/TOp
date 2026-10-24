"""Real ETW integration check against our own 15-second Direct3D fixture."""
from pathlib import Path
import csv
import json
import subprocess
import sys
import threading
import time
import psutil
# Invoked as a script, so include the project directory rather than tests/.
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from booster.fps import OwnedCollector, FrameWindow, collector_path, trace_allowed, REQUIRED_COLUMNS

def main():
    assert sys.platform=='win32','This check needs Windows'
    assert trace_allowed(),'The runner needs ETW capture permissions'
    fixture=subprocess.Popen([str(Path('build/fps_fixture.exe').resolve())])
    collector=None
    try:
        time.sleep(1)
        assert fixture.poll() is None,f'Graphics fixture exited early: {fixture.returncode}'
        collector=OwnedCollector(collector_path(),fixture.pid)
        window=FrameWindow(fixture.pid);errors=[]
        def consume():
            try:
                reader=csv.DictReader(collector.process.stdout)
                assert REQUIRED_COLUMNS.issubset(reader.fieldnames or []),'Unexpected PresentMon CSV columns'
                for row in reader:window.add(row)
            except Exception as exc:errors.append(str(exc))
        reader=threading.Thread(target=consume,daemon=True);reader.start()
        deadline=time.monotonic()+7;sample=None
        while time.monotonic()<deadline:
            if errors:raise AssertionError(errors[0])
            if collector.process.poll() is not None:raise AssertionError('Collector exited before real frames were captured')
            sample=window.sample()
            if sample.fps is not None and sample.frames>=10:break
            time.sleep(.1)
        assert sample and sample.fps is not None and sample.fps>0 and sample.frames>=10,'No real presentation FPS observed'
        detail=collector.stop();collector=None;reader.join(timeout=2)
        assert fixture.poll() is None,'Stopping FPS must never close the graphics application'
        print(json.dumps({'source':'PresentMon ETW','fps':sample.fps,'frames':sample.frames,'game_still_running':True,'stderr':detail}))
    finally:
        if collector:collector.stop()
        # The fixture exits on its own; do not terminate/kill another process.
        fixture.wait(timeout=20)
        assert fixture.returncode==0,'Graphics fixture failed'

if __name__=='__main__':
    try:main()
    except Exception as exc:
        import traceback
        traceback.print_exc()
        message=str(exc).replace('%','%25').replace('\r','%0D').replace('\n','%0A')
        print('::error title=FPS native validation::'+message,flush=True)
        raise SystemExit(1)
