"""Author-defined training suggestions, never assignment or emergency readiness.

Only completed, sufficiently reviewed attempts are eligible. Teacher overall score
corrections do not resolve individual rubric findings; those cannot become skill
labels without explicit criterion-level adjudication.
"""
from .expert_review import trusted_score, trusted_criteria
from .schemas import STATUSES

POLICY_VERSION = 'author-v2'
MIN_SAMPLE_SIZE = 3
WINDOW_SIZE = 10
UNIVERSAL_SERVICES = {'Учебная ДДС', 'Все службы', 'универсальная'}
BUILTIN_TITLES = {
    'reaction': 'Открытие карточки',
    'duration': 'Первый статус с текстом',
    'workflow': 'Действия с карточкой',
    'outgoing_call': 'Исходящий доклад должностному лицу',
}


def service_compatible(scenario_service, student_service):
    return scenario_service == student_service or scenario_service in UNIVERSAL_SERVICES or student_service == 'Учебная ДДС'


def _contacts(data):
    contacts = data.get('contacts', [])
    if not isinstance(contacts, list):
        return {}
    valid = {}
    for contact in contacts:
        if not isinstance(contact, dict):
            continue
        cid, phone = contact.get('id'), contact.get('phone')
        if (isinstance(cid, str) and cid and isinstance(phone, str) and phone.isdecimal() and len(phone) in {3, 4}
                and all(isinstance(contact.get(field), str) and contact[field].strip()
                        for field in ('name', 'role', 'greeting', 'reply'))):
            if cid in valid or any(old['phone'] == phone for old in valid.values()):
                return {}  # Ambiguous identity cannot explain a causal requirement.
            valid[cid] = contact
    return valid


def _fact(data, cid, title):
    facts = data.get('required_facts', [])
    if not isinstance(facts, list):
        return None
    matches = [f for f in facts if isinstance(f, dict) and isinstance(f.get('id'), str) and 'fact:' + f['id'] == cid]
    if len(matches) != 1 or matches[0].get('label') != title:
        return None
    fact = matches[0]
    patterns = fact.get('patterns')
    if not isinstance(patterns, list) or not patterns or any(not isinstance(p, str) or not p.strip() for p in patterns):
        return None
    confirmations = fact.get('confirmed_by_contact_ids', [])
    if (not isinstance(confirmations, list)
            or any(not isinstance(c, str) or not c for c in confirmations)
            or len(set(confirmations)) != len(confirmations)):
        return None
    contacts = _contacts(data)
    if any(cid not in contacts for cid in confirmations):
        return None
    return fact


def _has_builtin(data, cid):
    if cid in {'reaction', 'duration'}:
        field, upper = ('response_limit_seconds', 3600) if cid == 'reaction' else ('completion_limit_seconds', 86400)
        value = data.get(field)
        return type(value) is int and 1 <= value <= upper
    if cid == 'workflow':
        statuses = data.get('expected_statuses')
        return isinstance(statuses, list) and bool(statuses) and all(isinstance(s, str) and s in STATUSES for s in statuses)
    if cid == 'outgoing_call':
        return bool(_contacts(data))
    return False


def matched_criteria(data, weak, snapshots):
    """Match observable rubric presence, not pedagogical equivalence.

    All failing snapshots must explain the old criterion. Unknown provenance and
    malformed causal links fail closed. Only historical criterion identities leave
    this function; candidate facts, contacts and thresholds stay private.
    """
    matched = []
    for item in weak:
        cid, title = item['criterion_id'], item['title']
        sources = [snapshots.get(sid) for sid in item['evidence_session_ids']]
        if not sources or any(not isinstance(source, dict) for source in sources):
            continue
        if cid.startswith('fact:'):
            old_facts = [_fact(source, cid, title) for source in sources]
            candidate = _fact(data, cid, title)
            if candidate is None or any(fact is None for fact in old_facts):
                continue
            if any(fact.get('confirmed_by_contact_ids') for fact in old_facts) and not candidate.get('confirmed_by_contact_ids'):
                continue
        elif (BUILTIN_TITLES.get(cid) != title or not _has_builtin(data, cid)
              or not all(_has_builtin(source, cid) for source in sources)):
            continue
        matched.append({'criterion_id': cid, 'title': title})
    return matched


def recommend(student, attempts, stopped_ids, scenarios):
    """Pure function; attempts must already be scoped to the requesting user.

    The recent window is ordered by finish date, not arbitrary database order.
    No learner narrative or hidden scenario rubric appears in the returned data.
    """
    eligible = [r for r in attempts if r.status in {'submitted', 'reviewed'} and r.id not in stopped_ids
                and r.finished_at and trusted_score(r.report) is not None
                and service_compatible((r.snapshot if isinstance(r.snapshot, dict) else {}).get('service'), student.service)]
    eligible.sort(key=lambda r: (r.finished_at, r.id), reverse=True)
    sample = eligible[:WINDOW_SIZE]
    result = {
        'student_id': student.id, 'student_name': student.name,
        'status': 'insufficient_data', 'sample_size': len(sample), 'eligible_count': len(eligible),
        'proposed_level': None, 'average_score': None, 'weak_skills': [],
        'evidence_session_ids': [r.id for r in sample],
        'classroom': {'student_service': student.service,
                      'compatibility_rule': 'Та же служба; универсальный сценарий; либо профиль ученика «Учебная ДДС».',
                      'compatible_scenario_count': sum(service_compatible(s.data.get('service'), student.service) for s in scenarios)},
        'teacher_decides': True, 'suggested_scenarios': [],
        'scenario_selection_reason': 'Для подбора упражнений пока недостаточно проверенных попыток.',
        'unmatched_criteria': [],
        'criterion_evidence_attempts': 0,
        'reason': f'Недостаточно данных: {len(sample)} из {MIN_SAMPLE_SIZE} завершённых проверенных попыток по совместимому профилю службы. Уровень не определён.',
    }
    if len(sample) < MIN_SAMPLE_SIZE:
        return result
    scores = [trusted_score(r.report) for r in sample]
    mean = sum(scores) / len(scores)
    counts = {}
    critical_failures = 0
    for row in sample:
        report = row.report
        criteria = trusted_criteria(report)
        if criteria:
            result['criterion_evidence_attempts'] += 1
        seen = set()
        for criterion in criteria:
            key = (criterion.get('id'), criterion.get('title'))
            if not all(isinstance(x, str) and x for x in key) or key in seen:
                continue
            seen.add(key)
            item = counts.setdefault(key, {'criterion_id': key[0], 'title': key[1], 'failed': 0, 'total': 0, 'evidence_session_ids': []})
            item['total'] += 1
            if criterion['status'] == 'fail':
                item['failed'] += 1
                item['evidence_session_ids'].append(row.id)
                critical_failures += bool(criterion.get('critical'))
    # Repeated evidence only. One miss is discussed in its report, not a stable skill label.
    weak = [{**item, 'failure_rate': round(item['failed'] / item['total'], 3)} for item in counts.values()
            if item['failed'] >= 2 and item['total'] >= MIN_SAMPLE_SIZE and item['failed'] / item['total'] >= .5]
    weak.sort(key=lambda item: (-item['failure_rate'], -item['failed'], item['criterion_id'], item['title']))
    if mean < 60 or critical_failures:
        level = 'basic'
        explanation = 'Есть подтверждённая критическая ошибка либо средний балл ниже 60: предложено повторение базовых упражнений.'
    elif mean >= 85 and not weak:
        level = 'advanced'
        explanation = 'Средний балл не ниже 85, подтверждённых критических ошибок и повторяющихся слабых критериев в доступных данных нет: можно обсудить усложнение.'
    else:
        level = 'intermediate'
        explanation = 'Средний балл не ниже 60; условия предложения продвинутого уровня не выполнены: предложены упражнения средней сложности.'
    result.update(status='recommendation', average_score=round(mean, 2), proposed_level=level, weak_skills=weak,
                  reason=f'Авторская политика {POLICY_VERSION}, последние {len(sample)} проверенных попыток. {explanation} Решение принимает преподаватель; это не оценка готовности к реальным ЧС.')
    if result['criterion_evidence_attempts'] < len(sample):
        result['reason'] += ' Часть общих оценок подтверждена/исправлена преподавателем без подтверждения отдельных критериев; по ним слабые навыки не выводятся.'
    compatible = [s for s in scenarios if service_compatible(s.data.get('service'), student.service) and s.data.get('difficulty') == level]
    snapshots = {row.id: row.snapshot for row in sample}
    candidates = []
    for scenario in compatible:
        matches = matched_criteria(scenario.data, weak, snapshots) if weak else []
        if weak and not matches:
            continue
        candidates.append({'id': scenario.id, 'title': scenario.data['title'], 'service': scenario.data['service'],
                           'difficulty': scenario.data['difficulty'], 'matched_criteria': matches,
                           'selection_basis': 'rubric_match' if weak else 'profile_level'})
    candidates.sort(key=lambda candidate: (-len(candidate['matched_criteria']), candidate['title'], candidate['id']))
    result['suggested_scenarios'] = candidates[:5]
    covered = {(c['criterion_id'], c['title']) for s in candidates[:5] for c in s['matched_criteria']}
    result['unmatched_criteria'] = [{'criterion_id': c['criterion_id'], 'title': c['title']} for c in weak
                                    if (c['criterion_id'], c['title']) not in covered]
    if not weak:
        result['scenario_selection_reason'] = ('Подборка по профилю службы и предложенному уровню; повторяющихся подтверждённых слабых критериев нет.'
                                               if candidates else 'Для профиля службы и предложенного уровня доступных утверждённых упражнений нет.')
    elif not candidates:
        result['scenario_selection_reason'] = 'Среди доступных упражнений этого профиля и уровня не найдено проверяемого совпадения с подтверждёнными слабыми критериями.'
    else:
        result['scenario_selection_reason'] = (f'В показанных упражнениях найдено совпадение рубрики для {len(covered)} из {len(weak)} подтверждённых слабых критериев. '
                                               'Совпадение не доказывает равную сложность или перенос навыка; назначение определяет преподаватель.')
    return result
