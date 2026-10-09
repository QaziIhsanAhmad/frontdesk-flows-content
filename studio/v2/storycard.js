const {chromium}=require('playwright');const fs=require('fs');
const cards=JSON.parse(fs.readFileSync(process.argv[2]));
(async()=>{const b=await chromium.launch({args:['--allow-file-access-from-files']});const p=await b.newPage({viewport:{width:1080,height:1920}});
for(const c of cards){await p.goto('file://'+__dirname+'/story.html?'+new URLSearchParams(c.q));await p.evaluate(()=>document.fonts.ready);await p.waitForTimeout(300);
await p.screenshot({path:'stories/'+c.id+'.jpg',type:'jpeg',quality:92});}
await b.close();})();
