import test from "node:test";
import assert from "node:assert/strict";
import { scheduleVoices, sourceOffsetAt, voiceAtTime, voiceRequestMatches } from "./voiceSchedule.js";

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

test("does not play dialogue while paused and seeks audio to the matching subtitle offset", () => {
  const item = { start: 4, end: 8, tempo: 1.1, segment: { id: 7, audio: "line.mp3" } };
  assert.equal(voiceAtTime([item], 6, false), null);
  assert.equal(voiceAtTime([item], 6, true), item);
  assert.equal(sourceOffsetAt(item, 6), 2.2);
});

test("rejects a late TTS response after its translation or character assignment changed", () => {
  const request = { text: "អត្ថបទចាស់", char: "男主", charId: "cast-1", castVoice: "voice-a" };
  const current = { km: "អត្ថបទថ្មី", char: "女主", char_id: "cast-1" };
  assert.equal(voiceRequestMatches(current, request, "voice-b"), false);
  assert.equal(voiceRequestMatches({ km: request.text, char: request.char, char_id: request.charId }, request, "voice-a"), true);
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
