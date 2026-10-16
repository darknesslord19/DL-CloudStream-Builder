import json, os, subprocess, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
class GeneratorTests(unittest.TestCase):
    def test_generator_writes_provider(self):
        with tempfile.TemporaryDirectory() as td:
            analysis = Path(td) / 'analysis.json'
            analysis.write_text(json.dumps({'pagesParsed': 3, 'wordpressDetected': True}), encoding='utf-8')
            env = os.environ.copy(); env.update({'SITE_URL':'https://example.org','PLUGIN_NAME':'Demo Site','PACKAGE_NAME':'com.example.demo','CONTENT_TYPE':'movie_tv'})
            subprocess.run(['python', str(ROOT/'engine/generate_provider.py'), '--analysis', str(analysis), '--out', str(Path(td)/'src')], cwd=td, env=env, check=True, capture_output=True, text=True)
            sources = list((Path(td)/'src').rglob('*.kt'))
            self.assertEqual(len(sources), 1)
            content = sources[0].read_text(encoding='utf-8')
            for token in ('class DemoSitePlugin', 'override suspend fun search', 'override suspend fun loadLinks', 'https://example.org'):
                self.assertIn(token, content)
    def test_invalid_package_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            analysis = Path(td) / 'analysis.json'; analysis.write_text('{}', encoding='utf-8')
            env = os.environ.copy(); env.update({'SITE_URL':'https://example.org','PACKAGE_NAME':'bad package'})
            p = subprocess.run(['python', str(ROOT/'engine/generate_provider.py'), '--analysis', str(analysis), '--out', str(Path(td)/'src')], cwd=td, env=env, capture_output=True, text=True)
            self.assertNotEqual(p.returncode, 0)
if __name__ == '__main__': unittest.main()
