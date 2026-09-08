import { SamplerLoader } from "./sampler_loader.js";
import { SamplerEngine } from "./sampler_engine.js";
import { EventScheduler } from "./event_scheduler.js";

export class TrackMixer {
  constructor(baseUrl = "/assets/web-sampler-v1") {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    this.context = new AudioContextClass();
    this.loader = new SamplerLoader(this.context, baseUrl);
    this.engine = new SamplerEngine(this.context, this.loader);
    this.scheduler = new EventScheduler(this.context, this.engine);
    this.gains = new Map();
    this.origin = 0;
  }

  async prepare(trackIds) {
    await this.context.resume();
    const instruments = {};
    for (const trackId of trackIds) {
      instruments[trackId] = await this.loader.loadTrack(trackId);
      if (!this.gains.has(trackId)) {
        const gain = this.context.createGain();
        gain.gain.value = Number(instruments[trackId].defaultGain ?? 0.8);
        gain.connect(this.context.destination);
        this.gains.set(trackId, gain);
      }
    }
    return instruments;
  }

  async play(pack, options = {}) {
    const instruments = await this.prepare((pack.tracks ?? []).map((track) => track.trackId));
    this.origin = this.scheduler.schedule(pack, instruments, this.gains, options);
  }

  position() { return Math.max(0, this.context.currentTime - this.origin); }
  stop() { this.scheduler.stop(); }
  close() { this.stop(); return this.context.close(); }
}
