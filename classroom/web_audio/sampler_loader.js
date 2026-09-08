export class SamplerLoader {
  constructor(context, baseUrl = "/assets/web-sampler-v1") {
    this.context = context;
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.library = null;
    this.buffers = new Map();
  }

  async loadLibrary() {
    if (this.library) return this.library;
    const response = await fetch(`${this.baseUrl}/sample-library.json`);
    if (!response.ok) throw new Error("Web Sampler 音色表读取失败");
    this.library = await response.json();
    return this.library;
  }

  async loadTrack(trackId) {
    const library = await this.loadLibrary();
    const instrument = library.instruments?.[trackId];
    if (!instrument) throw new Error(`Web Sampler 缺少 ${trackId}`);
    await Promise.all(instrument.samples.map(async (sample) => {
      const key = `${trackId}:${sample.midi}`;
      if (this.buffers.has(key)) return;
      const response = await fetch(`${this.baseUrl}/${sample.path}`);
      if (!response.ok) throw new Error(`音色读取失败：${sample.path}`);
      const buffer = await this.context.decodeAudioData((await response.arrayBuffer()).slice(0));
      this.buffers.set(key, buffer);
    }));
    return instrument;
  }

  nearestSample(instrument, targetMidi) {
    return instrument.samples.reduce((best, sample) =>
      !best || Math.abs(sample.midi - targetMidi) < Math.abs(best.midi - targetMidi) ? sample : best, null);
  }

  buffer(trackId, midi) { return this.buffers.get(`${trackId}:${midi}`); }
}
