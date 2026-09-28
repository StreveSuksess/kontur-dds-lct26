"""Create prepared offline call responses using the installed macOS Russian voice."""
from pathlib import Path
import json
import platform
import subprocess
import wave

ROOT = Path(__file__).resolve().parents[2]
CLIPS = {
    'duty_greeting': 'Дежурный на связи. Слушаю ваш доклад.',
    'supervisor_greeting': 'Руководитель смены. Докладывайте обстановку.',
    'report_ack': 'Доклад принят. Информация получена.',
    'repeat_request': 'Повторите, пожалуйста, адрес и какие меры уже приняты.',
}

def main():
    if platform.system() != 'Darwin':
        raise SystemExit('Generation requires macOS say with the installed Milena ru_RU voice. Existing WAV clips are portable.')
    voices = subprocess.check_output(['say', '-v', '?'], text=True)
    if not any(line.startswith('Milena ') and 'ru_RU' in line for line in voices.splitlines()):
        raise SystemExit('Milena ru_RU is not installed; no voice was downloaded or substituted.')
    directory = ROOT / 'frontend/public/audio'
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {'engine': 'macOS say', 'voice': 'Milena', 'locale': 'ru_RU',
                'kind': 'prepared_local_tts', 'male_voice_available': False, 'clips': []}
    for name, text in CLIPS.items():
        target = directory / f'{name}.wav'
        subprocess.run(['say', '-v', 'Milena', '-r', '170', '--data-format=LEI16@22050', '-o', str(target), text], check=True)
        with wave.open(str(target)) as audio:
            duration = audio.getnframes() / audio.getframerate()
            assert audio.getnchannels() == 1 and audio.getsampwidth() == 2
            assert 0.3 <= duration <= 12
            manifest['clips'].append({'id': name, 'url': f'/audio/{name}.wav', 'text': text,
                                      'seconds': round(duration, 3), 'sample_rate': audio.getframerate(),
                                      'channels': 1, 'bits': 16})
    (directory / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(manifest, ensure_ascii=False))

if __name__ == '__main__':
    main()
