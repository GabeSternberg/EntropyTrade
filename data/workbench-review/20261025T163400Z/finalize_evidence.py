"""Recheck this attempt's protected exports and refresh the reviewable source snapshot.

Run from the checkout with .venv/bin/python. Reads Git; never stages, commits, merges,
pushes, opens credentials or changes supervisor controls. No browser success is inferred.
The ignored workflow workspace is required for full artifact rechecking.
"""

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from entropytrade.data.sources import file_hash
from entropytrade.families.public import forward_data
from entropytrade.features.registry import scientific_hash

REPO = Path(__file__).resolve().parents[3]
ROOT = Path(__file__).resolve().parent
WORKSPACE = REPO / 'data/cache' / ('workbench-browser-review-' + ROOT.name)


def write(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO)


files = sorted({
    *REPO.glob('backend/**/*.py'),
    *REPO.glob('configs/**/*.json'),
    *REPO.glob('frontend/**/*'),
    *(REPO / name for name in (
        'Makefile', 'pyproject.toml', 'uv.lock', 'README.md', 'STATUS.md',
        'docs/workbench.md', 'docs/roadmap.md',
    )),
})
hashes = {p.relative_to(REPO).as_posix(): file_hash(p) for p in files if p.is_file()}
source = {
    'recorded_at': datetime.now(UTC).isoformat(),
    'branch': git('branch', '--show-current').decode().strip(),
    'base_commit': git('rev-parse', 'HEAD').decode().strip(),
    'new_commit': None,
    'scope': 'Python sources/tests, local frontend, JSON configs, build/dependencies and current status/roadmap/workbench docs; no credentials or supervisor controls',
    'files': hashes,
    'source_tree_sha256': scientific_hash(hashes),
}
write('source-state.json', source)

scope = ['backend', 'configs', 'frontend', 'docs', 'README.md', 'STATUS.md', 'Makefile', 'pyproject.toml', 'uv.lock']
patch = git('diff', '--binary', 'HEAD', '--', *scope)
new = git('ls-files', '--others', '--exclude-standard', '-z', '--', *scope).decode().split('\0')
new = sorted(p for p in new if p)
for name in new:
    result = subprocess.run(
        ['git', 'diff', '--no-index', '--binary', '--', '/dev/null', name],
        cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    assert result.returncode == 1, result.stderr
    patch += result.stdout
(ROOT / 'source.patch').write_bytes(patch)
checked = subprocess.run(
    ['git', 'apply', '--reverse', '--check', str(ROOT / 'source.patch')],
    cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
)
(ROOT / 'source-patch-check.log').write_bytes(checked.stdout)
assert checked.returncode == 0, checked.stdout
whitespace = subprocess.run(
    ['git', 'diff', '--check'], cwd=REPO, stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT, check=False,
)
(ROOT / 'final-diff-check.log').write_bytes(whitespace.stdout)
assert whitespace.returncode == 0, whitespace.stdout
write('handoff.json', {
    'recorded_at': datetime.now(UTC).isoformat(),
    'branch': source['branch'], 'base_commit': source['base_commit'], 'new_commit': None,
    'new_source_files': new, 'source_patch_bytes': len(patch),
    'source_patch_sha256': file_hash(ROOT / 'source.patch'),
    'reverse_patch_check_exit_code': checked.returncode,
    'final_diff_check_exit_code': whitespace.returncode,
    'commit_deferred': 'Explicit current user instruction reserves all Git mutations for the supervisor; no staging or commit attempted',
    'commit_reproduction_verified': False,
})

runs = []
receipt = json.loads((ROOT / 'receipt.json').read_text())
for command in receipt['commands']:
    assert file_hash(ROOT / command['log']) == command['sha256']
for command in json.loads((ROOT / 'checks.json').read_text())['commands']:
    assert command['exit_code'] == 0
    assert file_hash(ROOT / command['log']) == command['sha256']
for run in receipt['runs']:
    folder = ROOT / run['label']
    review = json.loads((folder / 'review.json').read_text())
    workspace = REPO / run['workspace'] if run.get('workspace') else WORKSPACE
    original = workspace / 'runs' / run['job_id']
    assert json.loads((original / 'review.json').read_text()) == review
    assert not review['final_holdout_evaluated']
    assert all(p['split'] == 'validation' for p in review['probabilities'])
    assert (folder / 'report.txt').read_text() == review['report']
    for artifact in review['artifacts']:
        path = original / 'workflow' / artifact['path']
        assert file_hash(path) == artifact['sha256']
        assert path.stat().st_size == artifact['bytes']
    if run['data_kind'] == 'real':
        assert not review['probabilities'] and review['probability_count'] == 0
        assert all(c['forecast_metrics'] is None and not c['scenarios'] for c in review['candidates'])
    else:
        assert review['reasoning'] == 'offline_mock'
        control = next(c for c in review['candidates'] if c['candidate_id'] == 'negative-control')
        assert len(control['scenarios']) == 3
        assert all(s['fill_count'] == 0 for s in control['scenarios'])
    public = None
    if (folder / 'public').exists():
        manifest = json.loads((folder / 'public/manifest.json').read_text())
        for name, digest in manifest['checksums'].items():
            assert file_hash(folder / 'public' / name) == digest
        data = forward_data(folder / 'public')
        assert data.dataset_version == review['lineage']['dataset']
        assert data.feature_version == review['lineage']['feature_version']
        capture = data.provenance['capture']
        assert all(e['failed_at'] for e in capture['failures'])
        public = {
            'manifest_checksums_verified': True,
            'dataset': data.dataset_version, 'feature_version': data.feature_version,
            'receipts': len(capture['receipts']), 'contracts': len(data.samples),
            'observations': capture['observations'], 'failures': len(capture['failures']),
            'universe_complete': capture['universe_complete'],
        }
        summary = review['acquisition']
        assert summary['receipt_count'] == len(capture['receipts'])
        assert summary['listed_contracts'] == capture['listed_contracts']
        assert summary['observations'] == capture['observations']
        assert summary['failure_count'] == len(capture['failures'])
        assert summary['headline'] in review['report']
        assert all(f in review['report'] for f in summary['failure_summaries'])
        assert summary['evaluation_limit'] in review['report']
        if capture['family'] == 'bitcoin':
            assert all(not c['rules_known'] and not c['settlement_sources']
                       and c['settlement_basis'] == 'unresolved'
                       for c in data.provenance['contracts'])
    runs.append({
        'job_id': run['job_id'], 'label': run['label'],
        'protected_projection_verified': True, 'browser_verified': False,
        'review_sha256': file_hash(folder / 'review.json'),
        'report_sha256': file_hash(folder / 'report.txt'),
        'workflow_artifacts_verified': len(review['artifacts']), 'public_copy': public,
    })
assert all(file_hash(REPO / name) == digest for name, digest in hashes.items())
write('artifact-verification.json', {
    'recorded_at': datetime.now(UTC).isoformat(),
    'status': 'full_checks_and_http_workflows_passed_browser_acceptance_blocked',
    'source_files_verified': len(hashes),
    'source_manifest_sha256': file_hash(ROOT / 'source-state.json'),
    'workflow_artifacts_verified': sum(r['workflow_artifacts_verified'] for r in runs),
    'runs': runs,
    'limitations': [
        'Actual listeners, HTTP workflows and public ingestion passed; browser access was unavailable',
        'HTTP exports and worker exports are not browser downloads; no visual acceptance claimed',
        'Both successful public captures are forward ingestion, not empirical evaluation',
        'No local commit attempted: all Git mutations and commit-based reproduction belong to the supervisor',
    ],
})
print(f"Verified {len(hashes)} source files and {sum(r['workflow_artifacts_verified'] for r in runs)} workflow artifacts")
