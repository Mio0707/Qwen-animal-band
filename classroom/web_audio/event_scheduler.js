export class EventScheduler {
  constructor(context, samplerEngine) {
    this.context = context;
    this.samplerEngine = samplerEngine;
    this.sources = new Set();
  }

  schedule(pack, instruments, destinations, { offsetSec = 0, isTrackActive = () => true } = {}) {
    this.stop();
    const secondsPerBeat = 60 / Number(pack.bpm || 96);
    const offsetBeat = offsetSec / secondsPerBeat;
    const origin = this.context.currentTime - offsetSec;
    for (const track of pack.tracks ?? []) {
      const instrument = instruments[track.trackId];
      const destination = destinations.get(track.trackId);
      if (!instrument || !destination) continue;
      for (const event of track.events ?? []) {
        const beat = Number(event.startBeat);
        if (beat < offsetBeat || !isTrackActive(track.trackId, beat)) continue;
        const source = this.samplerEngine.schedule(track.trackId, instrument, event, destination, origin + beat * secondsPerBeat, secondsPerBeat);
        if (source) { this.sources.add(source); source.addEventListener("ended", () => this.sources.delete(source), { once: true }); }
      }
    }
    return origin;
  }

  stop() {
    for (const source of this.sources) { try { source.stop(); } catch {} }
    this.sources.clear();
  }
}
