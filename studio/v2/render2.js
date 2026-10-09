const { chromium } = require('playwright'); const fs=require('fs'), path=require('path'), cp=require('child_process');
const id=process.argv[2], only=process.argv[3];
const W=path.join(__dirname,'work',id); const {D,frames}=JSON.parse(fs.readFileSync(path.join(W,'render.json')));
(async()=>{
  const b=await chromium.launch({args:['--allow-file-access-from-files']}); const p=await b.newPage({viewport:{width:1080,height:1920}});
  await p.goto('file://'+__dirname+'/stage2.html'); await p.evaluate(()=>document.fonts.ready);
  if(only){ for(const T of only.split(',').map(Number)){ const f=frames[Math.min(frames.length-1,Math.round(T*30))]; await p.evaluate(([T,D])=>render(T,D),[f.T,{...D,fsrc:f.fsrc,nsrc:f.nsrc,realT:f.realT}]); await p.screenshot({path:path.join(W,`prev_${T}.png`)}); } await b.close(); return; }
  const fd=path.join(W,'frames'); fs.rmSync(fd,{recursive:true,force:true}); fs.mkdirSync(fd);
  for(let i=0;i<frames.length;i++){ const f=frames[i]; await p.evaluate(([T,D])=>render(T,D),[f.T,{...D,fsrc:f.fsrc,nsrc:f.nsrc,realT:f.realT}]);
    await p.screenshot({path:path.join(fd,String(i).padStart(5,'0')+'.jpg'),type:'jpeg',quality:92}); }
  await b.close();
  const out=path.join(__dirname,'out',id+'.mp4');
  cp.execFileSync('ffmpeg',['-v','error','-y','-framerate','30','-i',path.join(fd,'%05d.jpg'),'-i',path.join(W,'mix_norm.wav'),'-shortest','-c:v','libx264','-crf','18','-preset','medium','-pix_fmt','yuv420p','-profile:v','high','-maxrate','4500k','-bufsize','9000k','-g','60','-r','30','-c:a','aac','-b:a','128k','-ar','44100','-movflags','+faststart',out]);
  console.log('wrote',out,frames.length);
})();
