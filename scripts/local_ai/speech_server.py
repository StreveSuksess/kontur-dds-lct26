#!/usr/bin/env python3
"""Loopback-only offline Whisper. Raw WAV/WebM bytes, no remote model lookup."""
import argparse
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from socketserver import TCPServer
from pathlib import Path
import threading
import time

MAX_BYTES = 10 * 1024 * 1024
MAX_SECONDS = 120


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=11435)
    parser.add_argument('--model', default='research/models/openai/small.pt')
    parser.add_argument('--threads', type=int, default=4)
    args = parser.parse_args()
    import av
    import numpy as np
    import torch
    import whisper
    model_path = Path(args.model).resolve(strict=True)
    torch.set_num_threads(args.threads)
    model = whisper.load_model(str(model_path), device='cpu')
    gate = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, payload):
            raw = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path != '/health':
                return self.respond(404, {'error': 'not_found'})
            self.respond(200, {'status': 'ok', 'model': 'whisper-small', 'device': 'cpu',
                              'offline': True, 'busy': gate.locked(), 'max_seconds': MAX_SECONDS,
                              'max_bytes': MAX_BYTES, 'language': 'ru'})

        def do_POST(self):
            if self.path != '/transcribe':
                return self.respond(404, {'error': 'not_found'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                return self.respond(400, {'error': 'invalid_content_length'})
            if not 0 < size <= MAX_BYTES:
                return self.respond(413, {'error': 'audio_size_out_of_range'})
            if self.headers.get('Content-Type', '').split(';')[0] not in ('audio/wav', 'audio/x-wav', 'audio/webm', 'audio/ogg', 'audio/mp4', 'application/octet-stream'):
                return self.respond(415, {'error': 'send_raw_audio_bytes'})
            if not gate.acquire(blocking=False):
                return self.respond(429, {'error': 'speech_engine_busy'})
            started = time.monotonic()
            try:
                self.connection.settimeout(20)
                raw = self.rfile.read(size)
                if len(raw) != size:
                    return self.respond(400, {'error': 'incomplete_audio'})
                chunks, samples = [], 0
                with av.open(io.BytesIO(raw)) as container:
                    resampler = av.AudioResampler(format='fltp', layout='mono', rate=16000)
                    for frame in container.decode(audio=0):
                        for decoded in resampler.resample(frame):
                            part = decoded.to_ndarray().reshape(-1)
                            samples += len(part)
                            if samples > MAX_SECONDS * 16000:
                                return self.respond(413, {'error': 'audio_too_long'})
                            chunks.append(part)
                    for decoded in resampler.resample(None):
                        chunks.append(decoded.to_ndarray().reshape(-1))
                audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
                duration = len(audio) / 16000
                if duration > MAX_SECONDS:
                    return self.respond(413, {'error': 'audio_too_long'})
                if duration < .1:
                    return self.respond(400, {'error': 'audio_too_short'})
                if np.sqrt(np.mean(audio ** 2)) < .0001:
                    result = {'text': '', 'segments': []}
                else:
                    result = model.transcribe(audio, language='ru', fp16=False, temperature=0,
                        beam_size=3, condition_on_previous_text=False, verbose=None)
                self.respond(200, {'text': result['text'].strip(), 'language': 'ru',
                    'duration_seconds': round(duration, 3), 'latency_seconds': round(time.monotonic()-started, 3),
                    'model': 'whisper-small', 'mode': 'local_asr', 'requires_human_review': True,
                    'segments': [{k: s[k] for k in ('start', 'end', 'text')} for s in result['segments']]})
            except (ValueError, OSError, av.error.FFmpegError) as error:
                self.respond(400, {'error': 'invalid_audio', 'detail': type(error).__name__})
            except Exception as error:
                self.respond(500, {'error': 'transcription_failed', 'detail': type(error).__name__})
            finally:
                gate.release()

        def log_message(self, format, *values):
            # Do not log uploaded speech or personal information.
            print(format % values, flush=True)

    class LoopbackServer(ThreadingHTTPServer):
        def server_bind(self):
            # Offline loopback service: avoid HTTPServer's potentially blocking
            # getfqdn/DNS lookup when corporate DNS is unavailable.
            TCPServer.server_bind(self)
            self.server_name = 'localhost'
            self.server_port = self.server_address[1]

    server = LoopbackServer(('127.0.0.1', args.port), Handler)
    print(f'Whisper ready on http://127.0.0.1:{args.port}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
