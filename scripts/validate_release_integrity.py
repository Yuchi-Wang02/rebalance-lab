#!/usr/bin/env python3
"""Check dated presentation evidence and owner progress without private inputs."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(root, name):
    return json.loads((root / name).read_text(encoding='utf-8'))


def check_progress(root=ROOT):
    status = read(root, 'results/status.json')
    progress = read(root, 'results/owner-review-progress.json')
    for key in ['actual_answers_recorded', 'checkpoint_1', 'checkpoint_2', 'checkpoint_3']:
        require(status['owner_review'][key] == progress[key], 'stale owner progress projection')
    require(status['owner_presentation_ready'] == progress['owner_presentation_ready'], 'owner readiness mismatch')
    require(not progress['owner_mastery_verified'] and not progress['owner_presentation_ready'], 'deferred owner checks remain incomplete')
    require(not progress['owner_notebook_execution_verified'] and not progress['independent_external_reviewer'], 'unobserved review cannot be inferred')
    require(bool(progress['deferred']) and progress['actual_answers_recorded'], 'partial review evidence must be explicit')
    return status


def check_presentation(root=ROOT):
    review = read(root, 'results/presentation-review.json')
    require(review['reviewer'] == 'AI assistant' and not review['independent_human_review'], 'visual review provenance')
    for name, digest in review['artifact_sha256'].items():
        actual = hashlib.sha256((root / name).read_bytes()).hexdigest()
        require(actual == digest, f'stale presentation evidence: {name}')
    return review


def check(root=ROOT):
    check_progress(root)
    check_presentation(root)
    release = read(root, 'results/validation-release.json')
    for name, digest in release['artifact_sha256'].items():
        actual = hashlib.sha256((root / name).read_bytes()).hexdigest()
        require(actual == digest, f'stale release artifact: {name}')
    require(not release['release_scope']['raw_vendor_data'] and not release['release_scope']['private_owner_material'], 'public release exclusions')
    print('PASS: dated presentation evidence, partial owner review and release artifacts agree.')


if __name__ == '__main__':
    check()
