#!/usr/bin/env python3
"""Evaluate the independent seed without silently changing its labels or scope.

Run with backend/.venv/bin/python scripts/evaluate_benchmark.py.
This adapter calls the real assessor. It does not implement a second assessor.
"""
import copy
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.assessment import assess, detect_dispatch  # noqa: E402

STATUS_MAP = {'response_started': 'responding', 'works_completed': 'completed', 'declined': 'rejected'}


def adapt(case):
    rules = case['scenario_facts']['exercise_rules']
    snapshot = {
        'response_limit_seconds': 30, 'completion_limit_seconds': 180,
        'expected_statuses': [STATUS_MAP.get(x, x) for x in rules['required_statuses']],
        'required_facts': [{'id': 'dispatch', 'label': 'Направление бригады',
                            'patterns': ['Бригада направлена'], 'critical': True}],
    }
    events, seen = [], set()
    for action in case['learner']['actions']:
        if action['type'] != 'status':
            continue
        key = action.get('event_id', action['id'])
        # API persistence has a unique(session_id, client_event_id) constraint;
        # the assessor receives already deduplicated server events.
        if key in seen:
            continue
        seen.add(key)
        events.append({'id': key, 'kind': 'status_changed', 'elapsed_seconds': action['at_s'],
                       'payload': {'status': STATUS_MAP.get(action['value'], action['value']), 'comment': ''}})
    events.append({'id': 'learner-text', 'kind': 'trainee_message', 'elapsed_seconds': 25,
                   'payload': {'text': case['learner']['text'], 'call_id': 'synthetic'}})
    original = copy.deepcopy(snapshot)
    report = assess(snapshot, events, '2026-09-19T00:00:00+00:00', '2026-09-19T00:00:40+00:00')
    return report, snapshot == original


def main():
    source = ROOT / 'docs/validation-cases.json'
    data = json.loads(source.read_text())
    rows = []
    for case in data['cases']:
        report, unchanged = adapt(case)
        criteria = {c['id']: c for c in report['criteria']}
        for finding in case['expected_findings']:
            cid = finding['criterion_id']
            actual, explanation = None, ''
            if case['mode'] != 'dds_card':
                explanation = 'Путь 112 входит в общее ТЗ, но отсутствует в однопутевом MVP ДДС; адаптер не выдаёт результат для него.'
            elif cid == 'text.dispatch_report':
                detection = detect_dispatch(case['learner']['text'])
                actual = {'review': 'manual_review'}.get(detection.status, detection.status)
                explanation = detection.explanation
            elif cid == 'workflow.sequence':
                actual = criteria['workflow']['status']
                explanation = criteria['workflow']['explanation']
            elif cid == 'evaluation.integrity':
                actual = 'pass' if unchanged else 'fail'
                explanation = 'Реальный assess не изменил снимок рубрики; команда из текста не исполняется.'
            elif cid == 'text.grammar':
                actual = {'review': 'manual_review'}.get(criteria['grammar']['status'], criteria['grammar']['status'])
                explanation = criteria['grammar']['explanation']
            elif cid.startswith('timing.'):
                explanation = 'Набор измеряет first_acceptance; MVP измеряет card_opened. Подмена метрики недопустима.'
            else:
                explanation = 'Отдельный критерий ещё не реализован: нет независимой проверки фактических состояний.'
            rows.append({'case_id': case['id'], 'title': case['title'], 'criterion': cid,
                         'expected': finding['outcome'], 'actual': actual or 'unsupported',
                         'match': actual == finding['outcome'] if actual else None, 'explanation': explanation})
    supported = [r for r in rows if r['match'] is not None]
    counts = Counter((r['expected'], r['actual']) for r in supported)
    result = {
        'generated_at': datetime.now(timezone.utc).isoformat(), 'benchmark_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'status': 'synthetic_development_seed_not_blind_or_methodologist_validated',
        'assertions_total': len(rows), 'assertions_supported': len(supported),
        'exact_matches': sum(r['match'] for r in supported),
        'false_pass': sum(r['actual'] == 'pass' and r['expected'] != 'pass' for r in supported),
        'false_fail': sum(r['actual'] == 'fail' and r['expected'] == 'pass' for r in supported),
        'manual_review': sum(r['actual'] == 'manual_review' for r in supported),
        'confusion': [{'expected': a, 'actual': b, 'count': n} for (a, b), n in sorted(counts.items())],
        'adapter_notes': ['Дедупликация по event_id моделирует серверный unique constraint; отдельно проверяется API tests.',
                          'Только перечисленные findings; общий балл benchmark не задан.',
                          'Unsupported не учитывается как верный ответ. Это не точность на реальных операторах.'],
        'results': rows,
    }
    target = ROOT / 'docs/benchmark-results.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in {'results', 'adapter_notes', 'confusion'}}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
