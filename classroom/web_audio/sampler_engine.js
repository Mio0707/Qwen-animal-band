export class SamplerEngine {
  constructor(context, loader) { this.context = context; this.loader = loader; }

  schedule(trackId, instrument, event, destination, when, secondsPerBeat) {
    const anchor = this.loader.nearestSample(instrument, Number(event.midi));
    if (!anchor) return null;
    const shift = Number(event.midi) - Number(anchor.midi);
    const maxShift = Number(instrument.maxPitchShiftSemitones ?? 0);
    if (instrument.mode !== "one_shot" && Math.abs(shift) > maxShift) return null;
    const source = this.context.createBufferSource();
    const envelope = this.context.createGain();
    source.buffer = this.loader.buffer(trackId, anchor.midi);
    source.playbackRate.value = instrument.mode === "one_shot" ? 1 : 2 ** (shift / 12);
    const velocity = Math.max(0, Math.min(127, Number(event.velocity ?? 90))) / 127;
    const duration = Math.max(0.03, Number(event.durationBeats ?? 0.25) * secondsPerBeat);
    const attack = Math.max(0.001, Number(instrument.attackSec ?? 0.002));
    const release = Math.max(0.01, Number(instrument.releaseSec ?? 0.04));
    envelope.gain.setValueAtTime(0.0001, when);
    envelope.gain.exponentialRampToValueAtTime(Math.max(0.0001, velocity), when + attack);
    envelope.gain.setValueAtTime(Math.max(0.0001, velocity), Math.max(when + attack, when + duration - release));
    envelope.gain.exponentialRampToValueAtTime(0.0001, when + duration);
    source.connect(envelope).connect(destination);
    source.start(when);
    source.stop(when + duration + 0.03);
    return source;
  }
}
