import { measureWindow, resolveMeasureStarts, alignmentCoverage } from "../../classroom/core/measure-alignment.js";
import { buildLessonSegments } from "../../classroom/core/lesson-segments.js";
import { loadMeasureAlignment, loadOriginalAudio, saveMeasureAlignment } from "./adapters/local_workspace_adapter.js";

function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" })[c]); }
function fmt(seconds) { const value=Math.max(0,Number(seconds)||0),m=Math.floor(value/60),s=value-m*60; return `${String(m).padStart(2,"0")}:${s.toFixed(2).padStart(5,"0")}`; }
function once(target,eventName,timeoutMs=4000){return new Promise((resolve,reject)=>{let timer=null;const finish=(v,e=false)=>{target.removeEventListener(eventName,onEvent);target.removeEventListener("error",onError);if(timer)clearTimeout(timer);e?reject(v):resolve(v);};const onEvent=()=>finish(true);const onError=()=>finish(new Error("音频无法读取。"),true);target.addEventListener(eventName,onEvent,{once:true});target.addEventListener("error",onError,{once:true});timer=setTimeout(()=>finish(new Error(`等待音频 ${eventName} 超时。`),true),timeoutMs);});}

export async function createScoreMeasureAlignmentTool(container,{songId,score,onStateChange}={}){
  if(!container||!songId)return null;
  let currentScore=score,song=null,value={schemaVersion:"2.0.0",songId,calibration:null,anchors:[],segments:[]},draftCalibration=null,segmentOverrides=new Map();
  let audio=null,canvas=null,status=null,current=null,calibrationList=null,previewList=null,frame=null,previewStopAt=null,activePreview=null,previewRequestId=0,peaks=[],decodedDuration=0,originalAudioUrl="";
  const teachingSegments=()=>buildLessonSegments(currentScore);
  const calibration=()=>draftCalibration??value.calibration??null;
  const completeCalibration=()=>{const c=calibration();return Boolean(c&&c.startSec!=null&&c.endSec!=null&&Number.isFinite(Number(c.startSec))&&Number.isFinite(Number(c.endSec))&&Number(c.endSec)>Number(c.startSec));};
  const alignment=()=>{const firstSegmentId=referenceSegment()?.segmentId;return {schemaVersion:"2.0.0",songId,calibration:completeCalibration()?{startMeasure:Number(calibration().startMeasure),endMeasure:Number(calibration().endMeasure),startSec:Number(calibration().startSec),endSec:Number(calibration().endSec)}:null,anchors:[],segments:[...segmentOverrides.values()].filter((item)=>item.segmentId!==firstSegmentId).map((item)=>({...item,source:item.source||"teacher"}))};};
  const ready=()=>!originalAudioUrl||alignmentCoverage(currentScore,alignment()).ready;
  const notify=()=>onStateChange?.({required:Boolean(originalAudioUrl),ready:ready(),calibrationReady:completeCalibration()});
  function duration(){return Number(audio?.duration||decodedDuration||0);}
  function referenceSegment(){return teachingSegments()[0]??null;}
  function clearSegmentOverrides(){segmentOverrides=new Map();}
  function predictedSegments(){
    const c=calibration();if(!c||c.startSec==null||c.endSec==null||Number(c.endSec)<=Number(c.startSec))return [];
    const durationSec=Number(c.endSec)-Number(c.startSec),measureCount=Math.max(1,Number(c.endMeasure)-Number(c.startMeasure)+1),measureSec=durationSec/measureCount,baseStart=Number(c.startSec),baseMeasure=Number(c.startMeasure);
    const predicted=[];for(const seg of teachingSegments()){const override=segmentOverrides.get(seg.segmentId);if(override){predicted.push({...seg,startSec:Number(override.startSec),endSec:Number(override.endSec),source:override.source||"teacher"});continue;}predicted.push({...seg,startSec:baseStart+(seg.startMeasure-baseMeasure)*measureSec,endSec:baseStart+(seg.endMeasure-baseMeasure+1)*measureSec,source:"derived"});}return predicted;
  }
  function wavePoint(sec){const d=duration();return d?Math.max(0,Math.min(1,Number(sec)/d)):0;}
  function draw(){
    if(!canvas)return;const rect=canvas.getBoundingClientRect(),ratio=globalThis.devicePixelRatio||1,w=Math.max(1,Math.floor(rect.width*ratio)),h=Math.max(1,Math.floor(rect.height*ratio));if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}const ctx=canvas.getContext("2d");ctx.setTransform(ratio,0,0,ratio,0,0);const width=rect.width,height=rect.height;ctx.clearRect(0,0,width,height);ctx.fillStyle="#f7f5f1";ctx.fillRect(0,0,width,height);const mid=height/2;
    ctx.strokeStyle="#d6d1c7";ctx.beginPath();ctx.moveTo(0,mid);ctx.lineTo(width,mid);ctx.stroke();
    if(peaks.length){ctx.strokeStyle="#756e62";ctx.lineWidth=1;for(let x=0;x<width;x++){const idx=Math.min(peaks.length-1,Math.floor(x/width*peaks.length)),p=peaks[idx]??0;ctx.beginPath();ctx.moveTo(x,mid-p*(height*.42));ctx.lineTo(x,mid+p*(height*.42));ctx.stroke();}}
    const c=calibration();if(c?.startSec!=null){const x=wavePoint(c.startSec)*width;ctx.fillStyle="#3478f6";ctx.fillRect(x-1,0,2,height);ctx.fillText("开始",Math.min(width-34,x+4),14);}if(c?.endSec!=null){const x=wavePoint(c.endSec)*width;ctx.fillStyle="#e05a3f";ctx.fillRect(x-1,0,2,height);ctx.fillText("结束",Math.max(4,x-34),14);}
    for(const seg of predictedSegments()){const sx=wavePoint(seg.startSec)*width,ex=wavePoint(seg.endSec)*width;ctx.fillStyle=seg.source==="teacher"?"rgba(52,120,246,.15)":"rgba(59,153,99,.10)";ctx.fillRect(sx,0,Math.max(1,ex-sx),height);ctx.strokeStyle=seg.source==="teacher"?"#3478f6":"#3b9963";ctx.strokeRect(sx+.5,1,Math.max(0,ex-sx-1),height-2);}
    if(audio&&duration()){const x=wavePoint(audio.currentTime)*width;ctx.fillStyle="#111";ctx.fillRect(x-1,0,2,height);}
  }
  async function decodeWaveform(){try{const res=await fetch(originalAudioUrl);const buf=await res.arrayBuffer();const Ctx=globalThis.AudioContext||globalThis.webkitAudioContext;if(!Ctx)return;const ctx=new Ctx();const decoded=await ctx.decodeAudioData(buf.slice(0));decodedDuration=decoded.duration;const data=decoded.getChannelData(0),buckets=1000,step=Math.max(1,Math.floor(data.length/buckets));peaks=[];for(let i=0;i<data.length;i+=step){let max=0;for(let j=i;j<Math.min(data.length,i+step);j++)max=Math.max(max,Math.abs(data[j]));peaks.push(max);}await ctx.close();draw();}catch(error){const node=container.querySelector("[data-measure-waveform-error]");if(node)node.textContent=`波形解码失败：${error.message}`;}}
  async function seekTo(sec){if(!audio)return;audio.pause();audio.currentTime=Math.max(0,Math.min(duration()||Number.MAX_SAFE_INTEGER,Number(sec)||0));draw();}
  function finishPreview({pause=true}={}){previewStopAt=null;activePreview=null;if(pause&&audio&&!audio.paused)audio.pause();}
  function stopPreviewIfNeeded(){if(previewStopAt!=null&&audio&&audio.currentTime>=previewStopAt-.015){audio.currentTime=Math.min(previewStopAt,duration()||previewStopAt);finishPreview({pause:true});draw();}}
  function loop(){if(frame)cancelAnimationFrame(frame);const tick=()=>{stopPreviewIfNeeded();draw();if(audio&&!audio.paused)frame=requestAnimationFrame(tick);else frame=null;};frame=requestAnimationFrame(tick);}
  async function playSegment(seg){if(!audio||!seg)return;const id=++previewRequestId;finishPreview({pause:true});await seekTo(seg.startSec);if(id!==previewRequestId)return;previewStopAt=Number(seg.endSec);activePreview=seg.segmentId;await audio.play();loop();}
  async function persistAlignment(button){const payload=alignment();if(!payload.calibration)throw new Error("请先标记一个完整的小节段。 ");button.disabled=true;button.textContent="正在保存…";try{value=await saveMeasureAlignment(songId,payload);draftCalibration=value.calibration?{...value.calibration}:null;const firstSegmentId=referenceSegment()?.segmentId;segmentOverrides=new Map((value.segments??[]).filter((item)=>item.segmentId!==firstSegmentId).map((item)=>[item.segmentId,{...item}]));rebuild();notify();}finally{button.disabled=false;button.textContent="保存小节核对";}}
  function rebuild(){if(!calibrationList||!previewList)return;const seg=referenceSegment(),c=calibration();calibrationList.innerHTML=seg?`<div class="measure-anchor-row"><b>${escapeHtml(seg.label)}</b><span>简谱 ${seg.startMeasure}–${seg.endMeasure} 小节</span><span>开始 <strong>${c?.startSec!=null?fmt(c.startSec):"未标记"}</strong></span><span>结束 <strong>${c?.endSec!=null?fmt(c.endSec):"未标记"}</strong></span></div>`:"<small>没有可校准的教学小节段。</small>";const predicted=predictedSegments();previewList.innerHTML=predicted.length?predicted.map((item,index)=>`<div class="measure-preview-row" data-segment-id="${escapeHtml(item.segmentId)}"><div><b>${escapeHtml(item.label)}</b><small>简谱 ${item.startMeasure}–${item.endMeasure} 小节</small></div><label>开始 <input type="number" step="0.01" min="0" value="${Number(item.startSec).toFixed(3)}" data-segment-start ${index===0?"disabled":""}></label><label>结束 <input type="number" step="0.01" min="0" value="${Number(item.endSec).toFixed(3)}" data-segment-end ${index===0?"disabled":""}></label><button class="button secondary" type="button" data-preview-segment>试听</button><span class="segment-source">${item.source==="teacher"?"人工":"自动"}</span></div>`).join(""):"<small>先标记第一个小节段的开始和结束，系统才会自动推算后面。</small>";previewList.querySelectorAll("[data-segment-id]").forEach((row,index)=>{const segId=row.dataset.segmentId,seg=predicted.find((item)=>item.segmentId===segId);row.querySelector("[data-preview-segment]")?.addEventListener("click",()=>playSegment(seg));if(index===0)return;const start=row.querySelector("[data-segment-start]"),end=row.querySelector("[data-segment-end]");const apply=()=>{const a=Number(start.value),b=Number(end.value);if(!Number.isFinite(a)||!Number.isFinite(b)||b<=a)return;segmentOverrides.set(segId,{segmentId:segId,startMeasure:seg.startMeasure,endMeasure:seg.endMeasure,startSec:a,endSec:b,source:"teacher"});rebuild();draw();notify();};start?.addEventListener("change",apply);end?.addEventListener("change",apply);});status.textContent=ready()?"已完成":"请人工框定第一个小节段";status.classList.toggle("ready",ready());draw();notify();}
  async function mount(){value=await loadMeasureAlignment(songId)??value;const firstSegmentId=referenceSegment()?.segmentId;segmentOverrides=new Map((value.segments??[]).filter((item)=>item.segmentId!==firstSegmentId).map((item)=>[item.segmentId,{...item}]));draftCalibration=value.calibration?{...value.calibration}:null;originalAudioUrl=await loadOriginalAudio(songId);if(!originalAudioUrl){container.innerHTML=`<div class="alignment-heading"><div><span>原曲小节核对</span><h3>上传歌曲音频后，在这里核对小节时间</h3><p>当前歌曲没有原始音频，因此无需进行波形对齐。</p></div><strong class="alignment-status muted">无音频</strong></div>`;notify();return;}const segment=referenceSegment();container.innerHTML=`<div class="alignment-heading"><div><span>原曲小节核对</span><h3>人工框定一个完整小节段，再自动推算后面</h3><p>简谱 BPM 只作谱面信息，不再用于音频切分。请在波形上找到 <b>${escapeHtml(segment?.label??"第一个教学段")}</b> 的真实开始和结束；系统按这段真实时长推算后续分段，确认后可逐段人工微调。</p></div><strong class="alignment-status" data-measure-alignment-status>请人工框定第一个小节段</strong></div>
    <audio controls preload="metadata" src="${escapeHtml(originalAudioUrl)}" data-measure-alignment-audio></audio>
    <div class="measure-waveform-wrap"><canvas data-measure-waveform aria-label="歌曲波形图"></canvas><div class="measure-waveform-meta"><span>当前时间 <b data-measure-current-time>00:00.00</b></span><span data-measure-waveform-error></span></div></div>
    <div class="measure-anchor-toolbar"><button class="button secondary" type="button" data-mark-calibration-start>① 当前时间 = 本段开始</button><button class="button secondary" type="button" data-mark-calibration-end>② 当前时间 = 本段结束</button><button class="button primary" type="button" data-save-measure-alignment>保存小节核对</button></div>
    <div class="measure-anchor-list" data-measure-calibration-list></div>
    <div class="measure-preview-block"><div><b>自动推算的小节段</b><small>每一段与简谱里确认的教学分段完全一致；可逐段微调开始和结束时间，不能跨越相邻小节段。</small></div><div class="measure-preview-list" data-measure-preview-list></div></div>`;
    audio=container.querySelector("[data-measure-alignment-audio]");canvas=container.querySelector("[data-measure-waveform]");status=container.querySelector("[data-measure-alignment-status]");current=container.querySelector("[data-measure-current-time]");calibrationList=container.querySelector("[data-measure-calibration-list]");previewList=container.querySelector("[data-measure-preview-list]");rebuild();
    canvas.addEventListener("click",async event=>{if(!duration())return;++previewRequestId;finishPreview({pause:true});const rect=canvas.getBoundingClientRect(),desired=Math.max(0,Math.min(duration(),(event.clientX-rect.left)/rect.width*duration()));await seekTo(desired).catch(()=>{});});
    function mark(which){const seg=referenceSegment();if(!seg)return;draftCalibration={startMeasure:seg.startMeasure,endMeasure:seg.endMeasure,...(draftCalibration??{})};draftCalibration[which]=Number(audio.currentTime.toFixed(3));clearSegmentOverrides();if(which==="startSec"&&Number.isFinite(draftCalibration.endSec)&&draftCalibration.endSec<=draftCalibration.startSec)draftCalibration.endSec=null;if(which==="endSec"&&(!Number.isFinite(draftCalibration.startSec)||draftCalibration.endSec<=draftCalibration.startSec)){alert("结束时间必须晚于开始时间。");draftCalibration.endSec=null;}rebuild();draw();notify();}
    container.querySelector("[data-mark-calibration-start]").addEventListener("click",()=>mark("startSec"));container.querySelector("[data-mark-calibration-end]").addEventListener("click",()=>mark("endSec"));
    container.querySelector("[data-save-measure-alignment]").addEventListener("click",async event=>{if(!completeCalibration()){alert("请先标记这个小节段的开始和结束。");return;}try{await persistAlignment(event.currentTarget);}catch(error){alert(error.message);}});
    audio.addEventListener("loadedmetadata",()=>{rebuild();draw();});audio.addEventListener("timeupdate",()=>{current.textContent=fmt(audio.currentTime);stopPreviewIfNeeded();draw();});audio.addEventListener("ended",()=>finishPreview({pause:false}));audio.addEventListener("play",loop);audio.addEventListener("pause",()=>{if(frame)cancelAnimationFrame(frame);frame=null;draw();});addEventListener("resize",draw,{passive:true});decodeWaveform();
  }
  await mount();
  return {
    updateScore(nextScore){
      currentScore=nextScore;
      const seg=referenceSegment();
      if(draftCalibration&&seg){draftCalibration.startMeasure=seg.startMeasure;draftCalibration.endMeasure=seg.endMeasure;}
      rebuild();draw();
    },
    invalidateStructure(){
      value={schemaVersion:"2.0.0",songId,calibration:null,anchors:[],segments:[]};
      draftCalibration=null;
      segmentOverrides=new Map();
      rebuild();draw();notify();
    },
    required(){return Boolean(originalAudioUrl);},
    ready,
    alignment
  };
}
