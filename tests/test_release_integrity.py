import json
from pathlib import Path
import shutil
import tempfile
import unittest
from scripts.validate_release_integrity import check_progress, check_presentation

ROOT = Path(__file__).resolve().parents[1]


class ReleaseIntegrityTests(unittest.TestCase):
    def test_partial_owner_progress(self):
        check_progress()

    def test_old_pending_projection_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'results').mkdir()
            for name in ['status.json', 'owner-review-progress.json']:
                shutil.copy2(ROOT / 'results' / name, root / 'results' / name)
            path = root / 'results/status.json'
            value = json.loads(path.read_text(encoding='utf-8'))
            value['owner_review']['actual_answers_recorded'] = False
            path.write_text(json.dumps(value), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'stale owner progress'):
                check_progress(root)

    def test_changed_page_invalidates_visual_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            review = json.loads((ROOT / 'results/presentation-review.json').read_text(encoding='utf-8'))
            for name in ['results/presentation-review.json', *review['artifact_sha256']]:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / name, target)
            with (root / 'site/index.html').open('a', encoding='utf-8') as stream:
                stream.write('<p>Unreviewed change</p>')
            with self.assertRaisesRegex(ValueError, 'stale presentation evidence'):
                check_presentation(root)
