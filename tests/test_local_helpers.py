"""Offline behavioral checks. No browser, SDK import or provider calls."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHAT = ROOT / 'skills' / 'chat-delegate' / 'scripts' / 'prepare_packet.py'
DS = ROOT / 'skills' / 'deepseek-delegate' / 'scripts'


class LocalHelpers(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name).resolve()

    def command(self, script, *args):
        return subprocess.run([sys.executable, '-X', 'utf8', str(script), *map(str, args)],
                              capture_output=True, encoding='utf-8')

    def packet(self, output):
        return self.command(CHAT, '--source', self.project / 'source.md',
                            '--instruction-file', self.project / 'instruction.txt',
                            '--chat-target', 'offline-test', '--output-dir', output)

    def test_packet_preserves_bom_crlf_and_chinese_body(self):
        body = '中文材料\r\n数字 123\r\n'.encode('utf-8')
        (self.project / 'source.md').write_bytes(b'\xef\xbb\xbf' + body)
        (self.project / 'instruction.txt').write_text('检查材料。', encoding='utf-8')
        output = self.project / 'packet'
        result = self.packet(output)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
        source = manifest['sources'][0]
        attachment = (output / 'attachment.md').read_bytes()
        self.assertEqual(attachment[source['attachment_content_byte_start']:
                                    source['attachment_content_byte_end']], body)
        self.assertEqual(source['source_sha256'], hashlib.sha256(b'\xef\xbb\xbf' + body).hexdigest())
        self.assertNotIn(str(self.project), attachment.decode('utf-8'))
        self.assertEqual(manifest['status'], 'PREPARED_NOT_SENT')
        self.assertFalse(manifest['settings_verified'])
        self.assertFalse(manifest['message_sent'])

    def test_packet_refuses_to_overwrite_previous_round(self):
        (self.project / 'source.md').write_text('原文', encoding='utf-8')
        (self.project / 'instruction.txt').write_text('指令', encoding='utf-8')
        output = self.project / 'packet'
        self.assertEqual(self.packet(output).returncode, 0)
        original = {p.name: p.read_bytes() for p in output.iterdir()}
        (self.project / 'source.md').write_text('新原文', encoding='utf-8')
        self.assertNotEqual(self.packet(output).returncode, 0)
        self.assertEqual(original, {p.name: p.read_bytes() for p in output.iterdir()})

    def prepare(self, *extra):
        return self.command(DS / 'prepare_task.py', '--project-root', self.project,
                            '--conversation-key', 'offline-conversation', '--task-id', 'review',
                            '--title', '离线检查', *extra)

    def test_deepseek_prepare_snapshots_and_preserves_session(self):
        source = self.project / 'input.txt'
        source.write_text('任务原文', encoding='utf-8')
        result = self.prepare('--input', source)
        self.assertEqual(result.returncode, 0, result.stderr)
        metadata = json.loads(result.stdout)
        snapshot = Path(metadata['input_manifest'][0]['snapshot'])
        self.assertEqual(snapshot.read_bytes(), source.read_bytes())
        self.assertEqual(metadata['reasoning_effort'], 'max')
        self.assertEqual(metadata['execution_status'], 'NOT_RUN')
        self.assertIsNone(metadata['codex_conversation_id'])
        resumed = self.prepare('--input', source)
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(json.loads(resumed.stdout)['session_id'], metadata['session_id'])

    def test_deepseek_rejects_input_outside_project(self):
        with tempfile.TemporaryDirectory() as external:
            source = Path(external) / 'outside.txt'
            source.write_text('external', encoding='utf-8')
            result = self.prepare('--input', source)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((self.project / 'deepseek_tasks').exists())

    def test_deepseek_rejects_model_and_reasoning_drift(self):
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        metadata = json.loads(result.stdout)
        task_file = Path(metadata['task_directory']) / 'task.json'
        original = task_file.read_bytes()
        self.assertNotEqual(self.prepare('--model', 'different-model').returncode, 0)
        self.assertNotEqual(self.prepare('--reasoning-effort', 'low').returncode, 0)
        self.assertEqual(task_file.read_bytes(), original)

    @unittest.skipUnless(shutil.which('pwsh'), 'PowerShell 7 is required')
    def test_launcher_requires_own_credential_before_starting(self):
        task = self.project / 'task'
        task.mkdir()
        (task / 'task.json').write_text('{}', encoding='utf-8')
        env = {k: v for k, v in os.environ.items() if k.upper() != 'DEEPSEEK_API_KEY'}
        result = subprocess.run([shutil.which('pwsh'), '-NoProfile', '-File',
                                 str(DS / 'Start-Delegate.ps1'), '-TaskDirectory', str(task),
                                 '-PythonPath', sys.executable, '-Serve'],
                                env=env, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'Set DEEPSEEK_API_KEY locally', result.stderr)
        self.assertEqual(sorted(p.name for p in task.iterdir()), ['task.json'])


if __name__ == '__main__':
    unittest.main()
