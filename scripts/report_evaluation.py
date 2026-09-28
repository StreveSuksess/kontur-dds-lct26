#!/usr/bin/env python3
"""Validate the synthetic benchmark artifact and render its claim-level report.

Run after scripts/evaluate_benchmark.py. Use --check to verify a checked-in report.
"""

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/validation-cases.json'
RESULT = ROOT / 'docs/benchmark-results.json'
REPORT = ROOT / 'docs/evaluation-report.md'


def load_and_validate(source=SOURCE, result=RESULT):
    source_bytes = source.read_bytes()
    seed = json.loads(source_bytes)
    benchmark = json.loads(result.read_text())
    if hashlib.sha256(source_bytes).hexdigest() != benchmark['benchmark_sha256']:
        raise ValueError('benchmark-results.json is stale for validation-cases.json')

    claims = [(case['id'], case['mode'], finding['criterion_id'], finding['outcome'])
              for case in seed['cases'] for finding in case['expected_findings']]
    rows = benchmark['results']
    if len(claims) != len(rows) or len(rows) != benchmark['assertions_total']:
        raise ValueError('claim count differs between seed and results')
    for (case_id, mode, criterion, expected), row in zip(claims, rows):
        if (row['case_id'], row['criterion'], row['expected']) != (case_id, criterion, expected):
            raise ValueError(f'claim order or label changed at {case_id}/{criterion}')
        actual = row['actual']
        if actual not in {'pass', 'fail', 'manual_review', 'unsupported'}:
            raise ValueError(f'unknown result: {actual}')
        if row['match'] != (None if actual == 'unsupported' else actual == expected):
            raise ValueError(f'inconsistent match flag at {case_id}/{criterion}')
        row['mode'] = mode
    supported = [row for row in rows if row['actual'] != 'unsupported']
    if benchmark['assertions_supported'] != len(supported):
        raise ValueError('supported claim count differs from rows')
    if benchmark['exact_matches'] != sum(row['match'] is True for row in supported):
        raise ValueError('exact match count differs from rows')
    return seed, benchmark, rows


def metrics(rows):
    total = len(rows)
    supported = [r for r in rows if r['actual'] != 'unsupported']
    decisive = [r for r in supported if r['actual'] in {'pass', 'fail'}]
    return {
        'total': total,
        'supported': len(supported),
        'unsupported': total - len(supported),
        'exact': sum(r['match'] is True for r in supported),
        'manual_review': sum(r['actual'] == 'manual_review' for r in supported),
        'decisive': len(decisive),
        'decisive_exact': sum(r['match'] is True for r in decisive),
    }


def fraction(numerator, denominator):
    return f'{numerator}/{denominator} ({numerator / denominator:.1%})' if denominator else '—'


def render(source, benchmark, rows):
    m = metrics(rows)
    by_mode = defaultdict(list)
    by_criterion = defaultdict(list)
    for row in rows:
        by_mode[row['mode']].append(row)
        by_criterion[row['criterion']].append(row)

    lines = [
        '# Оценка синтетического набора', '',
        'Этот отчёт строится по `docs/validation-cases.json` и `docs/benchmark-results.json`; единица измерения — отдельное ожидаемое утверждение (`expected_finding`), а не попытка ученика или общий балл.', '',
        f'Источник: {len(source["cases"])} синтетических случаев, {m["total"]} утверждений. SHA-256 исходного набора: `{benchmark["benchmark_sha256"]}`.', '',
        '| Показатель | Результат | Смысл |', '| --- | ---: | --- |',
        f'| Покрытие утверждений | {fraction(m["supported"], m["total"])} | Адаптер вернул статус, отличный от `unsupported`. |',
        f'| Точное совпадение при покрытии | {fraction(m["exact"], m["supported"])} | Статус в точности равен синтетической метке, включая `manual_review`. |',
        f'| Точный решительный ответ | {fraction(m["decisive_exact"], m["decisive"])} | Только ответы `pass`/`fail`; показатель условен на этих {m["decisive"]} ответах. |',
        f'| Передано на ручную проверку | {fraction(m["manual_review"], m["supported"])} | `manual_review` — явное воздержание от автоматического pass/fail. |',
        f'| Неподдержанные утверждения | {fraction(m["unsupported"], m["total"])} | Для них точность не измерена. |',
        '',
        f'Знаменатели различаются намеренно. `manual_review` учитывается в покрытии, но не считается решительным ответом. `unsupported` исключён из точности и не считается правильным ответом. Поэтому точность на покрытых утверждениях нельзя переносить на все {m["total"]} утверждений или на реальных операторов.', '',
        '## По учебному пути', '',
        '| Путь | Утверждений | Покрыто | Точно при покрытии | Ручная проверка | Неподдержано |',
        '| --- | ---: | ---: | ---: | ---: | ---: |',
    ]
    for mode in sorted(by_mode):
        s = metrics(by_mode[mode])
        lines.append(f'| `{mode}` | {s["total"]} | {fraction(s["supported"], s["total"])} | {fraction(s["exact"], s["supported"])} | {s["manual_review"]} | {s["unsupported"]} |')
    lines += ['', '## По критерию', '',
              '| Критерий | Утверждений | Покрыто | Точно при покрытии | Ручная проверка | Неподдержано |',
              '| --- | ---: | ---: | ---: | ---: | ---: |']
    for criterion in sorted(by_criterion):
        s = metrics(by_criterion[criterion])
        lines.append(f'| `{criterion}` | {s["total"]} | {fraction(s["supported"], s["total"])} | {fraction(s["exact"], s["supported"])} | {s["manual_review"]} | {s["unsupported"]} |')

    errors = [r for r in rows if r['match'] is False]
    lines += ['', '## Расхождения', '']
    for row in errors:
        lines.append(f'- `{row["case_id"]}` / `{row["criterion"]}`: ожидалось `{row["expected"]}`, получено `{row["actual"]}`. {row["explanation"]}')
    if not errors:
        lines.append('В покрытых утверждениях расхождений нет.')

    lines += ['', '## Границы вывода', '',
              '- Набор создан для разработки, не размечен независимо методистом и не является слепой или репрезентативной выборкой. Отдельные случаи и правила были сконструированы специально для проверки реализации.',
              '- Путь `create_112` входит в общее письменное ТЗ и подтверждён уточнениями организатора, но отсутствует в текущем MVP ДДС. Его неподдержанные утверждения показывают пробел продукта, а не отмену требований.',
              '- `timing.first_acceptance` — синтетическая метрика набора. По последнему ответу заказчика для ДДС 30 секунд отсчитываются до открытия карточки, а первая запись статуса **и текста** должна появиться до трёх минут. Адаптер не подменяет эти условия друг другом.',
              '- Текущий прогон не измеряет согласованность экспертов, точность на реальных журналах, учебный эффект, скорость преподавателя или перенос навыка. Для этих выводов нужны независимая разметка и пилот по `docs/pilot-protocol.md`.',
              '', '## Повторение', '',
              'Из корня проекта после установки backend-зависимостей:', '',
              '```sh', 'backend/.venv/bin/python scripts/evaluate_benchmark.py',
              'python3 scripts/report_evaluation.py',
              'python3 scripts/report_evaluation.py --check', '```', '',
              'Первый скрипт вызывает действующий `app.assessment.assess` через адаптер и пересоздаёт JSON; второй сверяет метки и SHA-256 исходного набора, затем строит этот Markdown. `--check` проверяет, что отчёт совпадает с рассчитанным содержимым. Дата генерации JSON не участвует в метриках.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='fail if report is missing or stale')
    args = parser.parse_args()
    report = render(*load_and_validate())
    if args.check:
        if not REPORT.exists() or REPORT.read_text() != report:
            parser.exit(1, 'evaluation report is missing or stale\n')
        print('evaluation report is current')
    else:
        REPORT.write_text(report)
        print(f'wrote {REPORT}')


if __name__ == '__main__':
    main()
