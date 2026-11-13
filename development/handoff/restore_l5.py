#!/usr/bin/env python3
"""Restore this one interrupted L5 run into a clean clone; never execute it."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile


RUN = '20261113T063709_7f21ba4a'
REQUEST = 'v0-l5-continuity-20261113T063510Z-a187c3d5'
BRANCH = 'cwi/' + RUN
HEAD = '2e3e7b3e95714e9aa08d84b1d11f7bea01707105'
PIPELINE = '5bc0fbb04ad4e104f252f0dbd61361f62f3085d5'
BUNDLE = Path(__file__).resolve().parent


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args],
                                   text=True, stderr=subprocess.PIPE).strip()


def restore(repo):
    repo = repo.resolve()
    pipeline = repo / 'coding_pipeline'
    run = pipeline / 'logs' / RUN
    manager = pipeline / 'logs/manager' / REQUEST
    if run.exists() or manager.exists():
        raise ValueError('Run or manager directory already exists; preserve it and inspect its state.')
    if Path(git(repo, 'rev-parse', '--show-toplevel')) != repo:
        raise ValueError('Specify the project Git root.')
    if git(repo, 'branch', '--show-current') != 'main':
        raise ValueError('Restore with the accepted main branch checked out.')
    if git(repo, 'status', '--porcelain=v1', '--untracked-files=all'):
        raise ValueError('The target must be clean; preserve uncommitted work before restoring.')
    if git(pipeline, 'rev-parse', 'HEAD') != PIPELINE:
        raise ValueError('Wrong pipeline revision; check out the recorded 5bc0fbb revision first.')
    if git(pipeline, 'status', '--porcelain=v1', '--untracked-files=all'):
        raise ValueError('The pipeline checkout must be clean.')
    if subprocess.run(['git', '-C', str(repo), 'check-ignore', '--quiet', 'coding_pipeline/']).returncode:
        raise ValueError('The nested coding_pipeline directory must remain ignored.')
    git(repo, 'cat-file', '-e', HEAD + '^{commit}')
    git(repo, 'merge-base', '--is-ancestor', 'e13e275222d0da03228352aeac1b538b06036029', 'main')
    branch_exists = subprocess.run(['git', '-C', str(repo), 'show-ref', '--verify', '--quiet',
                                    'refs/heads/' + BRANCH]).returncode == 0
    if branch_exists and git(repo, 'rev-parse', BRANCH) != HEAD:
        raise ValueError('The L5 branch has changed; do not overwrite it.')

    archive = BUNDLE / 'l5/checkpoint.tar.gz'
    contents = json.loads((BUNDLE / 'CONTENTS.json').read_text())
    record = next(item for item in contents['files'] if item['file'] == 'l5/checkpoint.tar.gz')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != record['sha256']:
        raise ValueError('Checkpoint checksum mismatch; use the intact committed handoff.')
    files = {}
    with tarfile.open(archive, 'r:gz') as tar:
        for member in tar.getmembers():
            path = PurePosixPath(member.name)
            if (not member.isfile() or path.is_absolute() or '..' in path.parts
                    or not path.parts or path.parts[0] != 'run' or len(path.parts) < 2):
                raise ValueError('Unexpected checkpoint archive member.')
            files[Path(*path.parts[1:])] = tar.extractfile(member).read()
    state = json.loads(files[Path('state.json')])
    if (state['last_approved_commit'] != HEAD or state['status'] != 'interrupted'
            or state['phase'] != 'final' or state['sessions']):
        raise ValueError('The archive does not describe the expected stopped L5 checkpoint.')

    # Historical request/configuration and test records stay unchanged in the archive.
    # Only the active checkpoint's operational paths and next test interpreter move.
    old_run = state['run_dir']
    state.update(target=str(repo), run_dir=str(run), worktree=str(run / 'worktree'))
    for stage in ['baseline', 'final']:
        for result in state.get(stage, {}).get('results', []):
            result['output_path'] = result['output_path'].replace(old_run + '/', str(run) + '/', 1)
    for command in state['commands']:
        command[0] = sys.executable

    for path, data in files.items():
        dest = run / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    (run / 'state.json').write_text(json.dumps(state, indent=2) + '\n')
    if not branch_exists:
        git(repo, 'branch', BRANCH, HEAD)
    git(repo, 'worktree', 'add', str(run / 'worktree'), BRANCH)
    worktree = run / 'worktree'
    common = Path(git(repo, 'rev-parse', '--git-common-dir'))
    if not common.is_absolute():
        common = repo / common
    owner = Path(git(worktree, 'rev-parse', '--absolute-git-dir')) / 'cwi-owner.json'
    owner.write_text(json.dumps({'target': str(repo), 'worktree': str(worktree),
                                 'common': str(common.resolve()), 'branch': BRANCH}) + '\n')
    manager.mkdir(parents=True)
    for name in ['request.md', 'config.toml']:
        shutil.copyfile(BUNDLE / 'l5' / name, manager / name)
    (manager / 'receipt.json').write_text(json.dumps({
        'run_id': RUN, 'request_id': REQUEST, 'target': str(repo), 'status': 'interrupted'
    }, indent=2) + '\n')
    relocation = {'run_id': RUN, 'archive_sha256': digest, 'original_run_dir': old_run,
                  'restored_run_dir': str(run), 'python': sys.executable,
                  'source_head': HEAD, 'execution_started': False,
                  'note': 'Historical evidence and frozen configuration remain in the tracked handoff.'}
    (run / 'restoration.json').write_text(json.dumps(relocation, indent=2) + '\n')
    print(json.dumps(relocation, indent=2))
    print('Restored interrupted/final. No tests, model calls, merges or pushes were started.')
    print('Read development/handoff/README.md before any resume; the saved run has auto_merge=true.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repository', type=Path, help='Fresh, clean research_pipeline clone on main')
    args = parser.parse_args()
    try:
        restore(args.repository)
    except (ValueError, OSError, subprocess.CalledProcessError, tarfile.TarError) as error:
        detail = error.stderr.strip() if isinstance(error, subprocess.CalledProcessError) else str(error)
        print('Restore stopped: ' + detail, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
