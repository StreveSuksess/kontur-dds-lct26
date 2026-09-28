#!/usr/bin/env python3
"""Narrated montage of actual prototype screenshots, explicitly not a screencast.

Requires macOS say/Milena, FFmpeg and pdftoppm. Use a prepared local environment
with imageio-ffmpeg to discover its bundled FFmpeg, or pass --ffmpeg explicitly.
No downloads, shell execution, browser automation or model calls are performed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import wave

ROOT = Path(__file__).resolve().parents[1]
WATERMARK = 'Монтаж реальных экранов прототипа'
SCENES = [
    ('01-intro', 'Видеодемонстрация по реальным экранам', 1, None,
     'Контур ДДС — учебный тренажёр для диспетчеров. Это видеодемонстрация по реальным экранам работающего прототипа: монтаж отдельных учебных примеров, а не непрерывная запись действий. Все карточки, пользователи и номера синтетические. По уточнению заказчика, учащийся получает готовую карточку происшествия, делает исходящий доклад и фиксирует реагирование. Именно этот цикл лежит в основе нашего решения.'),
    ('02-teacher', 'Преподаватель: назначение и контроль', None, 'teacher-overview.png',
     'Работа начинается в кабинете преподавателя. Здесь видны назначения, текущие состояния попыток и задания, ожидающие разбора. Преподаватель выбирает утверждённый сценарий и назначает его учащемуся. Начатая попытка сохраняет свою версию задания: дальнейшее редактирование сценария не меняет её условия задним числом. Показанные счётчики относятся к демонстрационным данным. Они не являются результатами учебного пилота или доказательством улучшения подготовки.'),
    ('03-scenario', 'Сценарий: черновик → проверка → назначение', None, 'scenario-review.png',
     'В редакторе преподаватель задаёт адрес, описание происшествия, ожидаемые действия и критерии. Локальная языковая модель может предложить черновик формулировки. На этом реальном экране один такой запрос занял около трёх с половиной секунд. Это отдельный замер, а не гарантия скорости. Перед сохранением преподаватель проверяет факты и требования. Модель не должна подменять неизвестность утверждением, что пострадавших нет, или менять адрес задания.'),
    ('04-workspace', 'Учащийся: карточка → исходящий доклад → статусы', None, 'workspace-viewport.png',
     'Учащийся работает в интерфейсе, повторяющем предоставленную структуру автоматизированного рабочего места. Рядом с карточкой находятся журнал и учебный телефон. Номер выбирается из справочника сценария. После соединения учащийся передаёт доклад, получает учебный ответ и отмечает только фактически подтверждённые изменения. Неверный номер и порядок событий различаются. Телефон программный: выхода на реальные экстренные номера нет. Аппаратную телефонию в этом прототипе мы не заявляем.'),
    ('04b-observation', 'Преподаватель видит контекст сохранённой работы', None, 'teacher-observation.png',
     'Преподаватель может открыть наблюдение за текущей попыткой: увидеть карточку, таймеры и сохранённый сервером черновик. Черновик явно отделён от совершённых действий. Его наличие не означает, что учащийся отправил доклад или выполнил нужный шаг. Это помогает разбирать ход работы, сохраняя различие между намерением и подтверждённым событием.'),
    ('05-ai', 'Локальное распознавание: проверить перед отправкой', None, 'asr-draft.png',
     'Речь распознаётся локально, а текст предлагается учащемуся для проверки перед отправкой. В браузере загрузка одного учебного аудиофайла дала редактируемый результат распознавания примерно за две секунды. В записи другой учебный случай: поэтому текст оставлен черновиком, без вставки и отправки. Этот замер не проверяет живой микрофон в шумном классе. Маленькая языковая модель дала лишь три верных смысловых ответа из шести синтетических примеров. Поэтому она не определяет итоговую оценку, а её предложения требуют проверки.'),
    ('06-evidence', 'Разбор: ожидание, действие и связанное событие', None, 'report-evidence.png',
     'После завершения появляется разбор. Для критерия можно сопоставить ожидаемое и фактическое действие, прочитать пояснение и перейти к событию журнала. Один показанный учебный прогон получил сто баллов, но это не общая точность системы. Преподаватель видит основания результата и сохраняет окончательное решение за собой. Ошибка распознавания или спорная интерпретация не должны автоматически превращаться в ошибку учащегося. Преподавательская корректировка сохраняется с объяснением.'),
    ('07-verification', 'Что измерено — и чего эти цифры не доказывают', 8, None,
     'В короткой нагрузочной проверке сто разных учётных записей выполнили триста запросов чтения без ошибок. Девяносто пятый процентиль времени ответа составил около четырёхсот семнадцати миллисекунд. Двести событий двадцати попыток сохранились полностью. Это проверка программного интерфейса, а не одновременный урок со звуком. В синтетическом наборе совпали двадцать семь из двадцати восьми поддержанных утверждений; ещё двадцать утверждений не поддержаны. Эти числа не равны точности оценки профессиональной готовности.'),
    ('08-pilot', 'Следующий шаг: методистская проверка и учебный пилот', 10, None,
     'Следующий шаг — согласовать критерии с методистом, проверить работу на компьютерах учебного центра и провести настоящий учебный пилот. Проверяемая цель — сократить время преподавателя на корректный разбор на двадцать процентов без ухудшения выявления критических ошибок. Пока это цель, а не достигнутый эффект. В поставке есть исходники, документация, презентация и готовая браузерная сборка. Локальные модели и зависимости готовятся отдельно под целевую машину.'),
]


def run(args: list[str]) -> None:
    subprocess.run(args, check=True)


def executable(explicit: str | None, name: str) -> str:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise SystemExit(f'{name} executable not found: {path}')
        return str(path)
    found = shutil.which(name)
    if found:
        return found
    if name == 'ffmpeg':
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            pass
    if name == 'pdftoppm':
        candidate = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/pdftoppm'
        if candidate.is_file():
            return str(candidate)
    raise SystemExit(f'Install {name} in a prepared environment or pass --{name}. No automatic download occurs.')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe_duration(ffmpeg: str, path: Path) -> float:
    result = subprocess.run([ffmpeg, '-hide_banner', '-i', str(path)], capture_output=True, text=True)
    match = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', result.stderr)
    if not match:
        raise RuntimeError('Could not determine final container duration')
    hours, minutes, seconds = map(float, match.groups())
    return hours * 3600 + minutes * 60 + seconds


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg')
    parser.add_argument('--pdftoppm')
    parser.add_argument('--rate', type=int, default=205, help='macOS say words per minute')
    parser.add_argument('--output', type=Path, default=ROOT / 'deliverables/kontur-dds-demo-montage.mp4')
    parser.add_argument('--work-dir', type=Path, default=ROOT / 'runtime/demo-video')
    args = parser.parse_args()
    if not 140 <= args.rate <= 220:
        parser.error('--rate must be between 140 and 220')
    voices = subprocess.check_output(['say', '-v', '?'], text=True)
    if not any(line.startswith('Milena ') and 'ru_RU' in line for line in voices.splitlines()):
        raise SystemExit('Installed Milena ru_RU voice is required; none was downloaded or substituted.')
    ffmpeg, pdftoppm = executable(args.ffmpeg, 'ffmpeg'), executable(args.pdftoppm, 'pdftoppm')
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    pdf = ROOT / 'deliverables/kontur-dds-defense-v1.pdf'
    watermark = work / 'watermark.txt'
    watermark.write_text(WATERMARK, encoding='utf-8')
    font = '/System/Library/Fonts/Supplemental/Arial.ttf'
    if not Path(font).is_file():
        raise SystemExit('Arial font unavailable; supply an installed Unicode-capable macOS environment.')
    # Relative filter file names avoid filter-expression injection through workspace paths.
    old_cwd = Path.cwd()
    os.chdir(work)
    chapters, cursor = [], 0.0
    try:
        for key, title, page, screenshot, narration in SCENES:
            print(f'Preparing {key}', flush=True)
            if page:
                source = pdf
                frame = work / f'{key}-source.png'
                run([pdftoppm, '-f', str(page), '-singlefile', '-scale-to', '1920', '-png', str(pdf), str(frame.with_suffix(''))])
            else:
                source = ROOT / 'deliverables/assets' / str(screenshot)
                frame = source
            if not frame.is_file():
                raise SystemExit(f'Missing real source asset: {frame}')
            text_file = work / f'{key}.txt'
            text_file.write_text(narration, encoding='utf-8')
            title_file = work / f'{key}-title.txt'
            title_file.write_text(title, encoding='utf-8')
            audio = work / f'{key}.wav'
            run(['say', '-v', 'Milena', '-r', str(args.rate), '-f', str(text_file), '--data-format=LEI16@22050', '-o', str(audio)])
            with wave.open(str(audio)) as wav:
                audio_duration = wav.getnframes() / wav.getframerate()
            duration = round(audio_duration + 0.5, 3)
            video = work / f'{key}.mp4'
            # Metadata strips sit outside the proportionally scaled, unretouched source.
            vf = ('scale=1920:924:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:78+(924-ih)/2:color=0x203538,setsar=1,'
                  f'drawtext=fontfile={font}:textfile={title_file.name}:fontsize=38:fontcolor=white:x=54:y=21,'
                  f'drawtext=fontfile={font}:textfile=watermark.txt:fontsize=35:fontcolor=0xdce7dd:x=54:y=1017')
            run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-loop', '1', '-framerate', '24', '-i', str(frame),
                 '-i', str(audio), '-vf', vf, '-af', 'apad', '-t', str(duration), '-c:v', 'libx264', '-preset', 'veryfast',
                 '-tune', 'stillimage', '-crf', '21', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000', '-b:a', '128k',
                 '-movflags', '+faststart', str(video)])
            chapters.append({'id': key, 'title': title, 'start_seconds': round(cursor, 3), 'duration_seconds': duration,
                             'narration_seconds': round(audio_duration, 3), 'narration': narration,
                             'source': str(source.relative_to(ROOT)), 'source_sha256': sha(source), 'pdf_page': page})
            cursor += duration
        if cursor > 240:
            raise SystemExit(f'Narration is too long ({cursor:.1f}s); increase --rate and regenerate. Final video was not written.')
        concat = work / 'concat.txt'
        concat.write_text(''.join(f"file '{item['id']}.mp4'\n" for item in chapters), encoding='utf-8')
        run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '1', '-i', str(concat),
             '-c', 'copy', '-movflags', '+faststart', '-metadata', 'title=Контур ДДС — Видеодемонстрация по реальным экранам',
             '-metadata', f'comment={WATERMARK}. Не непрерывный скринкаст.', str(output)])
        actual_duration = probe_duration(ffmpeg, output)
        if not 0 < actual_duration <= 240:
            raise RuntimeError(f'Final container duration outside the promised limit: {actual_duration:.2f}s')
        # Decode every frame/audio packet to catch container and encoder failures.
        run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-i', str(output), '-f', 'null', '-'])
        for chapter in chapters:
            run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-ss', str(chapter['start_seconds'] + 1),
                 '-i', str(output), '-frames:v', '1', str(work / f"{chapter['id']}-inspection.png")])
        version = subprocess.check_output([ffmpeg, '-version'], text=True).splitlines()[0]
        receipt = {'title': 'Видеодемонстрация по реальным экранам', 'kind': 'narrated_static_screenshot_montage',
                   'continuous_screencast': False, 'continuous_screencast_pending': True, 'watermark': WATERMARK,
                   'voice': 'macOS say / Milena ru_RU', 'narration_is_synthetic': True, 'speech_rate': args.rate,
                   'ffmpeg': version, 'width': 1920, 'height': 1080, 'fps': 24, 'estimated_duration_seconds': round(cursor, 3),
                   'actual_duration_seconds': actual_duration,
                   'sha256': sha(output), 'bytes': output.stat().st_size, 'full_decode_passed': True, 'chapters': chapters}
        (ROOT / 'docs/demo-video-validation.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'output': str(output), 'seconds': round(cursor, 3), 'bytes': output.stat().st_size}, ensure_ascii=False))
    finally:
        os.chdir(old_cwd)


if __name__ == '__main__':
    main()
