import type { Event, Report, Session } from "./types";
import { SESSION_LABELS } from "./types.ts";

export function sessionLabel(session: Session): string {
  if (session.events.some((event) => event.kind === "teacher_stopped"))
    return session.status === "reviewed"
      ? "Прервано · итог проверен"
      : "Прервано преподавателем";
  return SESSION_LABELS[session.status];
}

// A decision is an explicit saved status action, separate from opening or text.
export function firstCardDecision(events: Event[]): Event | null {
  return (
    events.find(
      (event) =>
        event.kind === "status_changed" &&
        (event.payload.status === "accepted" ||
          event.payload.status === "rejected"),
    ) ?? null
  );
}

export function firstStatusWithText(events: Event[]): Event | null {
  return (
    events.find(
      (event) =>
        event.kind === "status_changed" &&
        typeof event.payload.comment === "string" &&
        event.payload.comment.trim().length > 0,
    ) ?? null
  );
}

export function isReviewFinal(report: Report): boolean {
  return !!report.teacher_review && !report.teacher_review_stale;
}

export function displayScore(report: Report): number {
  return isReviewFinal(report)
    ? report.teacher_review!.score
    : (report.expert_assessment?.score ?? report.score);
}

export function needsReview(report: Report): boolean {
  if (isReviewFinal(report)) return false;
  return (
    !!report.teacher_review_stale ||
    Object.keys(report.criterion_reviews ?? {}).length > 0 ||
    report.requires_review
  );
}

export function reportLabel(report: Report): string {
  if (report.teacher_review_stale) return "Нужно подтвердить итог повторно";
  if (isReviewFinal(report)) {
    const unresolved = report.criteria.some(
      (criterion) =>
        (report.criterion_reviews?.[criterion.id]?.status ??
          criterion.status) === "review",
    );
    return unresolved
      ? "Итог подтверждён · остались спорные критерии"
      : "Итог подтверждён преподавателем";
  }
  if (Object.keys(report.criterion_reviews ?? {}).length > 0)
    return "Разбор сохранён · итог не подтверждён";
  return report.requires_review
    ? "Нужна проверка преподавателя"
    : "Первичная оценка";
}

export const CRITERION_LABELS = {
  pass: "Выполнено",
  fail: "Не выполнено",
  review: "Требует проверки",
};
