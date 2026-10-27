// Mirror backend/subs.py:schedule_voice_clips for synchronized preview and timeline timing.
export function voiceAtTime(schedule, currentTime, isPlaying = true) {
  if (!isPlaying) return null;
  return schedule.find((item) => item.durationKnown !== false && currentTime >= item.start && currentTime < item.end) || null;
}

export function sourceOffsetAt(item, currentTime) {
  return Math.max(0, (currentTime - item.start) * item.tempo);
}

export function voiceRequestMatches(segment, request, currentVoice = "") {
  return segment.km === request.text &&
    (segment.char || "") === (request.char || "") &&
    (segment.char_id || "") === (request.charId || "") &&
    (currentVoice || "") === (request.castVoice || "");
}

export function scheduleVoices(rows) {
  const ordered = rows.map((segment, index) => ({ segment, index }))
    .filter(({ segment }) => segment.audio)
    .sort((a, b) => (Number(a.segment.start) || 0) - (Number(b.segment.start) || 0) || a.index - b.index);
  const scheduled = [];
  let previousEnd = 0;

  ordered.forEach(({ segment, index }, pos) => {
    const start = Math.max(0, Number(segment.start) || 0);
    const durationKnown = Number(segment.audio_duration) > 0;
    const sourceDuration = durationKnown
      ? Number(segment.audio_duration)
      : Math.max(0, (Number(segment.end) || start) - start);
    const scheduledStart = Math.max(start, previousEnd);
    let tempo = 1;
    let duration = sourceDuration;

    if (pos + 1 < ordered.length) {
      const nextStart = Math.max(0, Number(ordered[pos + 1].segment.start) || 0);
      const target = nextStart - scheduledStart - 0.03;
      if (target > 0 && sourceDuration > target) {
        const factor = sourceDuration / target;
        if (factor <= 1.15) {
          tempo = factor;
          duration = target;
        }
      }
    }

    const item = { segment, index, start: scheduledStart, end: scheduledStart + duration, duration, tempo, durationKnown };
    scheduled.push(item);
    previousEnd = item.end;
  });

  const byIndex = new Map(scheduled.map((item) => [item.index, item]));
  return {
    scheduled,
    segments: rows.map((segment, index) => {
      const item = byIndex.get(index);
      return item ? { ...segment, start: item.start, end: item.end } : segment;
    }),
  };
}
