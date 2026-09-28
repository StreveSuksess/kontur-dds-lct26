#!/usr/bin/env python3
"""Offline macOS speech synthesis, exposed only to the local application proxy."""
import argparse
import json
import platform
import shutil
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from socketserver import TCPServer

MAX_TEXT = 1999
MAX_BYTES = 16384
TIMEOUT = 20
VOICE = "Milena"


def availability():
    if platform.system() != "Darwin":
        return False, "macos_required", None, None
    say, convert = shutil.which("say"), shutil.which("afconvert")
    if not say or not convert:
        return False, "system_speech_tools_missing", say, convert
    try:
        voices = subprocess.run([say, "-v", "?"], capture_output=True,
                                text=True, timeout=5, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return False, "voice_list_unavailable", say, convert
    if not any(line.split() and line.split()[0] == VOICE for line in voices.splitlines()):
        return False, "milena_voice_missing", say, convert
    return True, None, say, convert


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=11436)
    args = parser.parse_args()
    available, reason, say, convert = availability()
    gate = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, payload):
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            if status == 429:
                self.send_header("Retry-After", "1")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path != "/health":
                return self.respond(404, {"error": "not_found"})
            self.respond(200, {"status": "ok" if available else "unavailable",
                               "available": available, "reason": reason,
                               "engine": "macos-say", "voice": VOICE,
                               "platform": platform.system(), "offline": True,
                               "busy": gate.locked(), "max_text_chars": MAX_TEXT,
                               "timeout_seconds": TIMEOUT})

        def do_POST(self):
            if self.path != "/synthesize":
                return self.respond(404, {"error": "not_found"})
            if not available:
                return self.respond(503, {"error": reason})
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                return self.respond(415, {"error": "send_application_json"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self.respond(400, {"error": "invalid_content_length"})
            if not 0 < size <= MAX_BYTES:
                return self.respond(413, {"error": "body_size_out_of_range"})
            try:
                self.connection.settimeout(5)
                raw = self.rfile.read(size)
                if len(raw) != size:
                    return self.respond(400, {"error": "incomplete_body"})
                payload = json.loads(raw)
            except (ValueError, UnicodeDecodeError, TimeoutError):
                return self.respond(400, {"error": "invalid_json"})
            text = payload.get("text") if isinstance(payload, dict) else None
            if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
                return self.respond(422, {"error": "text_must_contain_1_to_1999_characters"})
            if any(ord(char) < 32 and char not in "\n\r\t" for char in text):
                return self.respond(422, {"error": "text_contains_control_characters"})
            if not gate.acquire(blocking=False):
                return self.respond(429, {"error": "speech_engine_busy"})
            started = time.monotonic()
            try:
                with tempfile.TemporaryDirectory(prefix="dds-tts-") as directory:
                    folder = Path(directory)
                    source, aiff, wav = folder / "text.txt", folder / "speech.aiff", folder / "speech.wav"
                    # Plain file input; neither teacher text nor paths enter a shell.
                    source.write_text(text, encoding="utf-8")
                    subprocess.run([say, "-v", VOICE, "-f", str(source), "-o", str(aiff)],
                                   check=True, timeout=TIMEOUT, capture_output=True)
                    remaining = TIMEOUT - (time.monotonic() - started)
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired("speech synthesis", TIMEOUT)
                    subprocess.run([convert, "-f", "WAVE", "-d", "LEI16", str(aiff), str(wav)],
                                   check=True, timeout=remaining, capture_output=True)
                    audio = wav.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(audio)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Synthesis-Seconds", f"{time.monotonic() - started:.3f}")
                self.end_headers()
                self.wfile.write(audio)
            except subprocess.TimeoutExpired:
                self.respond(504, {"error": "synthesis_timeout"})
            except (OSError, subprocess.CalledProcessError):
                self.respond(503, {"error": "synthesis_failed"})
            finally:
                gate.release()

        def log_message(self, format, *args):
            # Request paths/status only. Do not log learner or scenario text.
            super().log_message(format, *args)

    class LoopbackServer(ThreadingHTTPServer):
        def server_bind(self):
            # HTTPServer normally resolves the host via getfqdn. This service
            # needs no DNS and must start even when corporate DNS is offline.
            TCPServer.server_bind(self)
            self.server_name = "localhost"
            self.server_port = self.server_address[1]

    server = LoopbackServer(("127.0.0.1", args.port), Handler)
    print(f"Local TTS: http://127.0.0.1:{args.port} ({'ready' if available else reason})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
