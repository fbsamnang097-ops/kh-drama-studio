import test from "node:test";
import assert from "node:assert/strict";
import { scheduleVoices } from "./voiceSchedule.js";

test("voice, subtitle, and character keep the same segment after a delayed clip", () => {
  const rows = [
    { id: 11, start: 0, end: 1, km: "ប្រយោគទីមួយ", char: "男主", audio: "/one.mp3", audio_duration: 3 },
    { id: 12, start: 1, end: 2, km: "ប្រយោគទីពីរ", char: "女主", audio: "/two.mp3", audio_duration: 0.5 },
  ];
  const { scheduled, segments } = scheduleVoices(rows);
  assert.equal(scheduled[0].segment.id, 11);
  assert.equal(scheduled[1].segment.id, 12);
  assert.equal(scheduled[1].start, 3);
  assert.equal(segments[1].start, 3);
  assert.equal(segments[1].km, "ប្រយោគទីពីរ");
  assert.equal(segments[1].char, "女主");
});

test("gently speeds up a clip only when it fits within the safe limit", () => {
  const { scheduled } = scheduleVoices([
    { id: 1, start: 0, end: 1, audio: "a.mp3", audio_duration: 2 },
    { id: 2, start: 2, end: 3, audio: "b.mp3", audio_duration: 0.5 },
  ]);
  assert.ok(scheduled[0].tempo > 1);
  assert.ok(scheduled[0].tempo <= 1.15);
  assert.equal(scheduled[0].end, 1.97);
  assert.equal(scheduled[1].start, 2);
});
