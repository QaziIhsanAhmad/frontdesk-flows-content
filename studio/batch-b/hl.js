const {chromium}=require(require.resolve('playwright', { paths: [__dirname, process.env.STUDIO_DIR || '/home/claude/studio'] }));
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1080,height:1920}});
await p.goto('file://'+__dirname+'/hl.html');
for(const [k,a,l,u] of [['demos','#22d3ee','Demos','Real n8n runs, step by step'],['bookings','#34d17f','Bookings','Enquiries answered day and night'],['reminders','#f5a623','Reminders','Fewer no-shows, zero staff time'],['sample','#c084fc','Free Sample','DM “FLOW” to get the workflow']]){await p.evaluate(([k,a,l,u])=>draw(k,a,l,u),[k,a,l,u]);await p.locator('#c').screenshot({path:__dirname+'/hl-'+k+'.jpg',type:'jpeg',quality:95});}
await b.close();})();
