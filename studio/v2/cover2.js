const {chromium}=require('playwright');const [,,out,k,h,b,img]=process.argv;
(async()=>{const br=await chromium.launch({args:['--allow-file-access-from-files']});const p=await br.newPage({viewport:{width:1080,height:1920}});
await p.goto('file://'+__dirname+'/cover2.html?'+new URLSearchParams({k,h,b,img:'file://'+img}));await p.evaluate(()=>document.fonts.ready);await p.waitForTimeout(400);
await p.screenshot({path:out,type:'jpeg',quality:94});await br.close();})();
