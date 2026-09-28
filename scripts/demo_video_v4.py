#!/usr/bin/env python3
"""Narrated montage of slides and actual prototype screenshots, not a screencast.

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
WATERMARK = 'Монтаж реальных экранов и схем. Не скринкаст'
SCENES = [
    ('01-intro', 'Контур ДДС: учебный прототип', 1, None, 'schema',
     'Контур ДДС — учебный тренажёр диспетчерской работы. Перед вами озвученная видеопрезентация: монтаж слайдов и отдельных снимков прототипа, а не непрерывная запись действий. Все люди, карточки и номера в примерах синтетические. Пилот с настоящими учащимися ещё не проводился.'),
    ('02-scope', 'Два пути письменного задания', 2, None, 'schema',
     'Письменное задание включает первичный путь сто двенадцать и работу профильной ДДС. Основной прототип тренирует ДДС на готовой карточке. Для сто двенадцать добавлено текстовое упражнение: ученик читает вводную, заполняет поля и выбирает службы. Сейчас есть два синтетических случая. Входящий голос и передача карточки в ДДС пока отсутствуют. На слайде показана схема границ.'),
    ('02b-intake', 'Ученик заполняет учебную карточку 112', None, 'rc4-intake112-student.png', 'screen_crop',
     'Это кадр браузерного прототипа: ученик заполняет поля по синтетической вводной и выбирает службы. Снимок показывает форму до отправки; следующий кадр иллюстрирует отдельное состояние разбора. Монтаж не является непрерывной записью одной попытки. Проверка смысла свободного текста остаётся за преподавателем.'),
    ('02c-intake-review', 'Преподаватель разбирает карточку 112', None, 'rc4-intake112-review.png', 'screen_crop',
     'Это отдельный кадр преподавательского разбора синтетической карточки. Браузерная проверка дала семь из девяти точных совпадений, а два свободных поля направила на проверку преподавателю. Он сохранил заключение, состояние стало «Разобрано». Это проверка функции, а не методистская оценка качества эталона или реальный учебный пилот.'),
    ('03-timing', 'Первые действия и учебные сроки', 3, None, 'schema',
     'Сроки разделены. За тридцать секунд нужно открыть поступившую карточку. За три минуты нужно впервые сохранить статус вместе с содержательным текстом. Это настраиваемые параметры упражнения, не универсальный норматив для всех служб. Завершение всей попытки — отдельный этап. Состояние «В работе» видно в интерфейсе. Здесь показана схема правил, а не запись выполнения.'),
    ('04-scenario', 'Преподаватель проверяет сценарий', None, 'rc3-preview-desktop.png', 'screen',
     'На этом снимке прототипа преподаватель просматривает учебный сценарий перед утверждением. Видны контакт, учебный номер, приветствие и ответ собеседника. Даже когда черновик помогает подготовить модель, преподаватель проверяет факты и рубрику. Длинный текст на снимке — специально созданный тест интерфейса, а не образец хорошего сценария.'),
    ('05-queue', 'Две карточки поступили одновременно', None, 'rc4-queue-two-cards.png', 'screen_crop',
     'На этом кадре браузерного прототипа ученик видит две одновременно доставленные карточки. У каждой уже идёт время от поступления, даже пока она ждёт открытия. Преподаватель отправил заранее назначенные карточки одной операцией. Это синтетическая проверка интерфейса, не занятие реального класса.'),
    ('05b-workspace-queue', 'Очередь видна из рабочего места', None, 'rc4-workspace-queue.png', 'screen_crop',
     'В рабочем месте открыта одна карточка, а другая остаётся в очереди. Верхняя строка напоминает, что время другой карточки продолжает идти. Ученик может переключаться между ними. Это отдельный снимок того же учебного механизма; монтаж не показывает непрерывную работу оператора.'),
    ('06-workspace', 'Рабочее место ДДС', None, 'workspace-viewport.png', 'older_screen',
     'Это реальный снимок более раннего состояния учебного рабочего места ДДС. Ученик получает готовую карточку, видит журнал и программный телефон. Он набирает учебный номер, передаёт доклад и фиксирует только подтверждённые изменения. Это не действующая система сто двенадцать и не аппаратная телефония. Снимок не показывает новую очередь.'),
    ('07-review', 'Преподаватель разбирает результат', 6, None, 'schema',
     'Автоматические правила сохраняют исходный вывод по каждому критерию вместе с событиями. Преподаватель может отдельно указать свой исход и причину, затем подтвердить общий результат. Новая правка требует повторного разбора. На слайде схема механизма. Удобство и экономию времени преподавателей ещё не измеряли.'),
    ('08-evaluation', 'Покрытие синтетического набора', 9, None, 'schema',
     'В авторском синтетическом наборе сорок восемь проверяемых утверждений. Текущий оценщик поддерживает двадцать восемь; из них двадцать семь совпали с авторской разметкой. По оставшимся двадцати он не выдаёт результата. Это покрытие разработки, а не точность на всех случаях и не проверка на реальных операторах. Ранний короткий тест программного интерфейса также не доказывает работу целого класса.'),
    ('09-pilot', 'Что ещё предстоит проверить', 11, None, 'schema',
     'Следующий шаг — согласовать рубрику с методистами и провести учебный пилот на целевых компьютерах. Двадцать процентов экономии времени корректного разбора — заранее заданная цель, пока без результата. Официальные слайды шаблона ЛЦТ с седьмого по одиннадцатый нам недоступны, поэтому эта презентация не подтверждает соответствие официальному шаблону. Полный продуктовый эффект ещё нужно измерить.'),
]
CROPS = {
    '02b-intake': (700, 550, 0, 0),
    '02c-intake-review': (700, 480, 0, 0),
    '05-queue': (700, 480, 0, 0),
    '05b-workspace-queue': (700, 480, 0, 0),
}



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
    parser.add_argument('--output', type=Path, default=ROOT / 'deliverables/kontur-dds-demo-v4.mp4')
    parser.add_argument('--work-dir', type=Path, default=ROOT / 'runtime/demo-video-v4')
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
    pdf = ROOT / 'deliverables/kontur-dds-defense-v3.pdf'
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
        for key, title, page, screenshot, source_kind, narration in SCENES:
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
            scene_label = work / f'{key}-label.txt'
            scene_label.write_text('Схема функции, не запись экрана' if source_kind == 'schema' else ('Снимок раннего прототипа' if source_kind == 'older_screen' else ('Фрагмент экрана RC4, кадрировано' if source_kind == 'screen_crop' else 'Снимок прототипа')), encoding='utf-8')
            audio = work / f'{key}.wav'
            run(['say', '-v', 'Milena', '-r', str(args.rate), '-f', str(text_file), '--data-format=LEI16@22050', '-o', str(audio)])
            with wave.open(str(audio)) as wav:
                audio_duration = wav.getnframes() / wav.getframerate()
            duration = round(audio_duration + 0.5, 3)
            video = work / f'{key}.mp4'
            # Metadata strips sit outside the proportionally scaled, unretouched source.
            crop = CROPS.get(key)
            crop_filter = f'crop={crop[0]}:{crop[1]}:{crop[2]}:{crop[3]},' if crop else ''
            vf = (crop_filter + 'scale=1920:924:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:78+(924-ih)/2:color=0x203538,setsar=1,'
                  f'drawtext=fontfile={font}:textfile={title_file.name}:fontsize=38:fontcolor=white:x=54:y=21,'
                  f'drawtext=fontfile={font}:textfile=watermark.txt:fontsize=29:fontcolor=0xdce7dd:x=54:y=1000,'
                  f'drawtext=fontfile={font}:textfile={scene_label.name}:fontsize=25:fontcolor=0xdce7dd:x=54:y=1040')
            run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-loop', '1', '-framerate', '24', '-i', str(frame),
                 '-i', str(audio), '-vf', vf, '-af', 'apad', '-t', str(duration), '-c:v', 'libx264', '-preset', 'veryfast',
                 '-tune', 'stillimage', '-crf', '21', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000', '-b:a', '128k',
                 '-movflags', '+faststart', str(video)])
            chapters.append({'id': key, 'title': title, 'start_seconds': round(cursor, 3), 'duration_seconds': duration,
                             'narration_seconds': round(audio_duration, 3), 'narration': narration,
                             'source': str(source.relative_to(ROOT)), 'source_sha256': sha(source), 'pdf_page': page, 'source_kind': source_kind,
                             'source_crop_pixels': crop})
            cursor += duration
        if cursor > 300:
            raise SystemExit(f'Narration is too long ({cursor:.1f}s); increase --rate and regenerate. Final video was not written.')
        concat = work / 'concat.txt'
        concat.write_text(''.join(f"file '{item['id']}.mp4'\n" for item in chapters), encoding='utf-8')
        run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '1', '-i', str(concat),
             '-c', 'copy', '-movflags', '+faststart', '-metadata', 'title=Контур ДДС — Видеопрезентация v4',
             '-metadata', f'comment={WATERMARK}. Не непрерывный скринкаст.', str(output)])
        actual_duration = probe_duration(ffmpeg, output)
        if not 0 < actual_duration <= 300:
            raise RuntimeError(f'Final container duration outside the promised limit: {actual_duration:.2f}s')
        # Decode every frame/audio packet to catch container and encoder failures.
        run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-i', str(output), '-f', 'null', '-'])
        for chapter in chapters:
            run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-ss', str(chapter['start_seconds'] + 1),
                 '-i', str(output), '-frames:v', '1', str(work / f"{chapter['id']}-inspection.png")])
        version = subprocess.check_output([ffmpeg, '-version'], text=True).splitlines()[0]
        receipt = {'title': 'Контур ДДС — Видеопрезентация v4', 'kind': 'narrated_slide_and_screenshot_montage',
                   'continuous_screencast': False, 'continuous_screencast_pending': False, 'watermark': WATERMARK,
                   'voice': 'macOS say / Milena ru_RU', 'narration_is_synthetic': True, 'speech_rate': args.rate,
                   'ffmpeg': version, 'width': 1920, 'height': 1080, 'fps': 24, 'estimated_duration_seconds': round(cursor, 3),
                   'actual_duration_seconds': actual_duration,
                   'sha256': sha(output), 'bytes': output.stat().st_size, 'full_decode_passed': True, 'chapters': chapters}
        (ROOT / 'docs/demo-video-v4-validation.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'output': str(output), 'seconds': round(cursor, 3), 'bytes': output.stat().st_size}, ensure_ascii=False))
    finally:
        os.chdir(old_cwd)


if __name__ == '__main__':
    main()
