import test from "node:test";
import assert from "node:assert/strict";
import {
  displayScore,
  isReviewFinal,
  needsReview,
  reportLabel,
  sessionLabel,
  firstCardDecision,
  firstStatusWithText,
} from "../frontend/src/reportState.ts";

const criterion = { id: "fact:address", status: "review" };
function report(patch = {}) {
  return {
    score: 60,
    requires_review: true,
    criteria: [criterion],
    teacher_review: null,
    ...patch,
  };
}

test("partial expert decision is provisional until overall confirmation", () => {
  const current = report({
    criterion_reviews: { "fact:address": { status: "pass" } },
    expert_assessment: { score: 80 },
  });
  assert.equal(displayScore(current), 80);
  assert.equal(isReviewFinal(current), false);
  assert.equal(needsReview(current), true);
  assert.match(reportLabel(current), /итог не подтверждён/);
});

test("new criterion decision makes an older overall result stale", () => {
  const previous = { score: 95 };
  const current = report({
    teacher_review: previous,
    teacher_review_stale: true,
    expert_assessment: { score: 80 },
  });
  assert.equal(displayScore(current), 80);
  assert.equal(isReviewFinal(current), false);
  assert.equal(needsReview(current), true);
  assert.match(reportLabel(current), /повторно/);
});

test("confirmed overall score does not silently resolve remaining uncertain criteria", () => {
  const current = report({ teacher_review: { score: 90 } });
  assert.equal(displayScore(current), 90);
  assert.equal(isReviewFinal(current), true);
  assert.match(reportLabel(current), /остались спорные критерии/);
});

test("teacher-stopped attempt stays visibly interrupted after overall review", () => {
  assert.equal(
    sessionLabel({ status: "reviewed", events: [{ kind: "teacher_stopped" }] }),
    "Прервано · итог проверен",
  );
});

test("opening or mentioning acceptance does not create a card decision", () => {
  assert.equal(
    firstCardDecision([
      { kind: "card_opened", elapsed_seconds: 2, payload: {} },
      {
        kind: "trainee_message",
        elapsed_seconds: 3,
        payload: { text: "Карточка принята" },
      },
      {
        kind: "status_changed",
        elapsed_seconds: 4,
        payload: { status: "responding" },
      },
    ]),
    null,
  );
  assert.equal(firstCardDecision([]), null);
});

test("first acceptance or rejection is taken from preserved event order, including zero", () => {
  const rejected = {
    id: "decision",
    kind: "status_changed",
    elapsed_seconds: 0,
    payload: { status: "rejected" },
  };
  const accepted = {
    id: "later",
    kind: "status_changed",
    elapsed_seconds: 40,
    payload: { status: "accepted" },
  };
  assert.equal(firstCardDecision([rejected, accepted]), rejected);
  assert.equal(firstCardDecision([accepted, rejected]), accepted);
  assert.equal(firstCardDecision([rejected]).elapsed_seconds, 0);
});

test("first update needs an actual saved status and nonblank text", () => {
  const events = [
    { kind: "trainee_message", elapsed_seconds: 1, payload: { text: "Принято" } },
    { kind: "status_changed", elapsed_seconds: 2, payload: { status: "accepted", comment: "  " } },
    { kind: "status_changed", elapsed_seconds: 3, payload: { status: "responding", comment: "Бригада направлена" } },
  ];
  assert.equal(firstStatusWithText(events), events[2]);
  assert.equal(firstStatusWithText(events.slice(0, 2)), null);
});
