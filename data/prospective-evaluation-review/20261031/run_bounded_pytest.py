"""Run every pytest file with its own deadline; deadlines are failures, never skips/passes."""
import concurrent.futures
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import xml.etree.ElementTree as ET

repo = Path.cwd()
output = repo / 'data/prospective-evaluation-review/20261031/per-file'
output.mkdir()
files = sorted((repo / 'backend/tests').rglob('test_*.py'))
environment = {'PATH': '/usr/bin:/bin', 'PYTHONPATH': str(repo / 'backend/src') + ':' + str(repo / 'backend'), 'PYTHONNOUSERSITE': '1', 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}

def run(path):
    name = str(path.relative_to(repo)).replace('/', '__')
    start = time.monotonic()
    deadline = False
    with (output / (name + '.log')).open('w') as log:
        command = [str(repo / '.venv/bin/pytest'), str(path.relative_to(repo)), '-q', '-o', 'faulthandler_timeout=30', '--junitxml=' + str(output / (name + '.xml'))]
        with subprocess.Popen(command, cwd=repo, env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True) as process:
            try:
                code = process.wait(timeout=90)
            except subprocess.TimeoutExpired:
                deadline = True
                os.killpg(process.pid, signal.SIGINT)
                try:
                    code = process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    code = process.wait()
    counts = {}
    xml = output / (name + '.xml')
    if xml.exists():
        suites = list(ET.parse(xml).getroot().iter('testsuite'))
        counts = {key: sum(int(s.attrib.get(key, 0)) for s in suites) for key in ('tests', 'failures', 'errors', 'skipped')}
    return {'file': str(path.relative_to(repo)), 'exit_code': code, 'deadline_exceeded': deadline, 'seconds': round(time.monotonic() - start, 2), **counts}

start = time.monotonic()
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    rows = list(pool.map(run, files))
receipt = {'all_files_attempted': len(rows) == len(files), 'file_count': len(files), 'seconds': round(time.monotonic() - start, 2), 'complete_suite_pass': all(r['exit_code'] == 0 and not r['deadline_exceeded'] for r in rows), 'results': rows}
(output.parent / 'per-file-summary.json').write_text(json.dumps(receipt, indent=2))
print(json.dumps({key: value for key, value in receipt.items() if key != 'results'}), flush=True)
