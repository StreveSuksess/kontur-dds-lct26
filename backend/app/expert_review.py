"""Effective findings and conservative trust, without modifying the rule report."""
import copy
from math import isfinite


def valid_score(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and 0 <= value <= 100


def effective_criteria(report):
    """Return independent copies with only explicit expert statuses/evidence applied."""
    decisions = report.get('criterion_reviews') or {}
    result = []
    for original in report.get('criteria', []):
        criterion = copy.deepcopy(original)
        decision = decisions.get(criterion.get('id'))
        if isinstance(decision, dict) and decision.get('status') in {'pass','fail','review'}:
            criterion['status'] = decision['status']
            criterion['points'] = criterion.get('max_points', 0) if decision['status'] == 'pass' else 0
            if 'evidence_ids' in decision:
                criterion['evidence_ids'] = list(decision['evidence_ids'])
        result.append(criterion)
    return result


def expert_summary(report):
    criteria = effective_criteria(report)
    return {'score':sum(c.get('points', c.get('max_points', 0) if c.get('status') == 'pass' else 0) for c in criteria),
            'max_score':report.get('max_score', 100),
            'requires_review':any(c.get('status') == 'review' for c in criteria),
            'critical_errors':sum(bool(c.get('critical')) for c in criteria if c.get('status') == 'fail')}


def current_teacher_review(report):
    review = report.get('teacher_review')
    if report.get('teacher_review_stale') or not isinstance(review, dict):
        return None
    if not valid_score(review.get('score')) or not str(review.get('comment', '')).strip():
        return None
    if report.get('criterion_reviews') and review.get('criterion_revision', 0) != report.get('criterion_review_revision', 0):
        return None
    return review


def trusted_score(report):
    if not isinstance(report, dict) or report.get('teacher_review_stale'):
        return None
    review = current_teacher_review(report)
    if report.get('criterion_reviews'):
        # Adjudication is intermediate until the teacher explicitly confirms its revision.
        return review['score'] if review else None
    if review:
        return review['score']
    if report.get('requires_review') is False and valid_score(report.get('score')):
        return report['score']
    return None


def trusted_criteria(report):
    """Only definite, positive-weight evidence; overall corrections imply no facts."""
    if trusted_score(report) is None:
        return []
    decisions = report.get('criterion_reviews') or {}
    review = current_teacher_review(report)
    original_trusted = report.get('requires_review') is False and (not review or review['score'] == report.get('score'))
    result = []
    for criterion in effective_criteria(report):
        decision = decisions.get(criterion.get('id'))
        explicit = isinstance(decision, dict) and decision.get('status') in {'pass','fail'}
        # A teacher's explicit "review" overrides even a previously definite rule finding.
        if not explicit and (decision is not None or not original_trusted):
            continue
        if criterion.get('status') not in {'pass','fail'} or criterion.get('max_points', 0) <= 0:
            continue
        result.append(criterion)
    return result
