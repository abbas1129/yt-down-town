"""Regression checks and real ffmpeg composition tests; no paid API calls."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

import yt_dlp
from core.scanner import scan_channel, _shorts_tab_url
from core.downloader import download_video
from core.elevenlabs_client import generate_voiceover
from core.media import find_ffmpeg, probe, render_composite, extract_audio
from core.workflow import job_folder, save_job, save_script, artifact, load_jobs, prepare_video


class WorkflowTests(unittest.TestCase):
    def test_preparation_creates_no_separate_source_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            metadata = {'id': 'aaaaaaaaaaa', 'title': 'Example', 'url': 'https://youtube.com/shorts/aaaaaaaaaaa', 'view_count': 10000000}
            folder = job_folder(root, metadata['id'])
            def download(url, output, title, log):
                path = output / 'source.mp4'
                path.write_bytes(b'video with audio')
                return path
            def transcribe(video_id, source, output, title, **kwargs):
                self.assertEqual(source.name, 'source.mp4')
                path = output / 'transcript.txt'
                path.write_text('Source transcript', encoding='utf-8')
                return path
            with patch('core.workflow.download_video', side_effect=download), patch('core.workflow.generate_transcript', side_effect=transcribe):
                job = prepare_video(root, metadata)
            self.assertNotIn('audio', job)
            self.assertFalse((folder / 'source_audio.wav').exists())
            self.assertEqual(sorted(p.name for p in folder.iterdir()), ['job.json', 'script.txt', 'source.mp4', 'transcript.txt'])

    def test_shorts_only_and_domain_validation(self):
        self.assertEqual(_shorts_tab_url('https://www.youtube.com/@Example/videos?x=1'),
                         'https://www.youtube.com/@Example/shorts')
        for value in ['https://youtube.com.attacker.test/@x', 'https://youtube.com/watch?v=abcdefghijk']:
            with self.assertRaises(ValueError):
                _shorts_tab_url(value)

    def test_scan_failure_is_not_empty_success(self):
        with patch('core.scanner.yt_dlp.YoutubeDL') as fake:
            fake.return_value.__enter__.return_value.extract_info.side_effect = yt_dlp.utils.DownloadError('network failed')
            with self.assertRaisesRegex(RuntimeError, 'network failed'):
                scan_channel('https://youtube.com/@Example', 5_000_000)

    def test_scan_sorts_filters_and_deduplicates(self):
        rows = [{'id': 'aaaaaaaaaaa', 'title': 'A', 'view_count': 5_000_000},
                {'id': 'bbbbbbbbbbb', 'title': 'B', 'view_count': 12_000_000},
                {'id': 'ccccccccccc', 'title': 'C', 'view_count': 4_999_999}]
        with patch('core.scanner.yt_dlp.YoutubeDL') as fake:
            fake.return_value.__enter__.return_value.extract_info.return_value = {'entries': rows + [rows[0]]}
            all_rows, qualified = scan_channel('https://youtube.com/@Example', 5_000_000)
        self.assertEqual(len(all_rows), 3)
        self.assertEqual([v['id'] for v in qualified], ['bbbbbbbbbbb', 'aaaaaaaaaaa'])

    def test_failed_download_never_returns_old_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = Path(tmp) / 'source.mp4'
            old.write_bytes(b'existing video')
            with patch('core.downloader.yt_dlp.YoutubeDL') as fake, patch('core.downloader.find_ffmpeg', return_value='ffmpeg'):
                fake.return_value.__enter__.return_value.download.side_effect = yt_dlp.utils.DownloadError('failed')
                with self.assertRaises(yt_dlp.utils.DownloadError):
                    download_video('https://youtube.com/watch?v=aaaaaaaaaaa', tmp, 'source')
            self.assertEqual(old.read_bytes(), b'existing video')

    def test_script_edit_invalidates_downstream_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = job_folder(root, 'aaaaaaaaaaa')
            job = {'id': 'aaaaaaaaaaa', 'title': 'A', 'voice': 'old.mp3', 'final': 'old.mp4'}
            save_script(folder, job, 'New words')
            self.assertNotIn('voice', job)
            self.assertNotIn('final', job)
            self.assertEqual(load_jobs(root)[0]['script'], 'script.txt')
            self.assertEqual(artifact(folder, job, 'script').read_text().strip(), 'New words')

    def test_api_error_does_not_leak_key_or_write_audio(self):
        with tempfile.TemporaryDirectory() as tmp, patch('core.elevenlabs_client.requests.post') as post:
            post.return_value = Mock(status_code=401)
            with self.assertRaisesRegex(RuntimeError, 'API key') as err:
                generate_voiceover('hello', 'private-secret-value', 'voiceID', Path(tmp))
            self.assertNotIn('private-secret-value', str(err.exception))
            self.assertEqual(list(Path(tmp).glob('*.mp3')), [])


@unittest.skipUnless(find_ffmpeg(), 'ffmpeg not installed')
class MediaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source.mp4'
        self.face = self.root / 'face.mp4'
        self.voice = self.root / 'voice.mp3'
        self.ffmpeg = find_ffmpeg()
        self.run_ffmpeg(['-f','lavfi','-i','color=c=red:s=180x320:r=30:d=1',
                         '-f','lavfi','-i','sine=frequency=200:duration=1',
                         '-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(self.source)])
        self.run_ffmpeg(['-f','lavfi','-i','color=c=blue:s=320x180:r=30:d=0.5',
                         '-c:v','libx264','-pix_fmt','yuv420p',str(self.face)])
        self.run_ffmpeg(['-f','lavfi','-i','sine=frequency=900:duration=1.5','-c:a','libmp3lame',str(self.voice)])

    def run_ffmpeg(self, args):
        subprocess.run([self.ffmpeg,'-y','-v','error',*args],check=True,capture_output=True,timeout=45)

    def tearDown(self):
        self.tmp.cleanup()

    def test_render_layouts_and_audio_replacement(self):
        import numpy as np
        for layout, shape in [('below',(540,960)),('overlay',(540,960)),('beside',(960,540))]:
            out = self.root / f'{layout}.mp4'
            progress = []
            render_composite(self.source,self.voice,self.face,out,layout,True,'preserve',True,progress.append)
            info = probe(out)
            video = next(s for s in info['streams'] if s['codec_type']=='video')
            self.assertEqual((video['width'],video['height']),shape)
            self.assertAlmostEqual(info['duration'],1.5,delta=0.15)
            self.assertEqual(progress[-1],1.0)
            raw = subprocess.run([self.ffmpeg,'-v','error','-i',str(out),'-t','0.4','-f','f32le','-ac','1','-ar','16000','pipe:1'],capture_output=True,check=True).stdout
            samples = np.frombuffer(raw,dtype=np.float32)
            spectrum = np.abs(np.fft.rfft(samples))
            freq = np.fft.rfftfreq(len(samples),1/16000)[spectrum.argmax()]
            self.assertAlmostEqual(freq,900,delta=10)  # source tone at 200 Hz must be absent
            self.assertLess(spectrum[int(200*len(samples)/16000)],spectrum.max()*0.05)

    def test_fit_timing_full_resolution_and_extract_audio(self):
        out = self.root / 'final.mp4'
        render_composite(self.source,self.voice,self.face,out,'below',False,'fit',False)
        info = probe(out)
        video = next(s for s in info['streams'] if s['codec_type']=='video')
        self.assertEqual((video['width'],video['height']),(1080,1920))
        self.assertAlmostEqual(info['duration'],1.5,delta=0.15)
        audio = extract_audio(self.source,self.root/'source.wav')
        self.assertAlmostEqual(probe(audio)['duration'],1,delta=0.15)

    def test_voice_request_and_cache(self):
        with patch('core.elevenlabs_client.requests.post') as post:
            post.return_value = Mock(status_code=200,content=self.voice.read_bytes(),headers={'Content-Type':'audio/mpeg'})
            path = generate_voiceover('Hello', 'private-key', 'voiceID', self.root)
            again = generate_voiceover('Hello', 'private-key', 'voiceID', self.root)
            self.assertEqual(path,again)
            self.assertEqual(post.call_count,1)
            self.assertEqual(post.call_args.kwargs['json']['text'],'Hello')
            self.assertEqual(post.call_args.kwargs['headers']['xi-api-key'],'private-key')


if __name__ == '__main__':
    unittest.main()
