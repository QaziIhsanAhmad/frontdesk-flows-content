// Usage: node rec2.js scenarios/<id>.json  -> writes takes/<id>/{nframes,fframes,meta.json,ndv_*.png}
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const sleep = ms => new Promise(r => setTimeout(r, ms));
const SC = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const OUT = path.join(__dirname, 'takes4k', SC.id);
const WFID = SC.workflowIdFile ? fs.readFileSync(SC.workflowIdFile, 'utf8').trim() : fs.readFileSync('/home/claude/n8n/prodid', 'utf8').trim();
const HOOK = SC.hookPath || 'clinic-enquiry';

async function screencast(page, dir, t0, log) {
  fs.mkdirSync(dir, { recursive: true });
  const cdp = await page.context().newCDPSession(page); let i = 0;
  cdp.on('Page.screencastFrame', f => {
    const n = String(i++).padStart(5, '0');
    fs.writeFileSync(path.join(dir, n + '.jpg'), Buffer.from(f.data, 'base64'));
    log.push((Date.now() - t0) / 1000);
    cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }).catch(() => {});
  });
  return { start: (w, h) => cdp.send('Page.startScreencast', { format: 'jpeg', quality: 92, maxWidth: w, maxHeight: h, everyNthFrame: 1 }),
           stop: () => cdp.send('Page.stopScreencast').catch(() => {}), cdp };
}

(async () => {
  fs.rmSync(OUT, { recursive: true, force: true }); fs.mkdirSync(OUT, { recursive: true });
  // sandbox state
  fs.writeFileSync('/home/claude/sandbox/ai_mode.json', JSON.stringify(SC.ai));
  for (const f of fs.readdirSync('/home/claude/sandbox/mail')) fs.unlinkSync('/home/claude/sandbox/mail/' + f);
  const t0 = Date.now(); const meta = { marks: {}, nodeTimes: {}, rects: {} };
  const mark = k => { meta.marks[k] = (Date.now() - t0) / 1000; };

  // --- n8n browser ---
  const bA = await chromium.launch();
  const cA = await bA.newContext({ viewport: { width: 3840, height: 2400 }, colorScheme: 'dark', storageState: path.join(__dirname, 'state.json') });
  const pA = await cA.newPage();
  await pA.goto('http://localhost:5678/workflow/' + WFID);
  await sleep(4500);
  await pA.evaluate(() => { for (const e of document.querySelectorAll('a,div,span')) { if (/^Star\s*[\d,]+$/.test((e.innerText||'').trim()) && e.getBoundingClientRect().y < 60) { (e.closest('a')||e).style.visibility='hidden'; } } });
  const col = await pA.$('#collapse-change-button'); if (col) await col.click();
  await sleep(600);
  await pA.mouse.click(1900, 300); await pA.keyboard.press('1'); await sleep(800);
  const getR = () => pA.evaluate(() => [...document.querySelectorAll('[data-test-id="canvas-node"]')].map(e => { const b = (e.querySelector('[data-test-id="canvas-default-node"],[data-test-id="canvas-trigger-node"]') || e).getBoundingClientRect(); return [b.x, b.y, b.width, b.height]; }));
  for (let i = 0; i < 12; i++) {
    const R = await getR(); const xs = R.map(r => r[0]), xe = R.map(r => r[0] + r[2]), ys = R.map(r => r[1]), ye = R.map(r => r[1] + r[3]);
    const cx = (Math.min(...xs) + Math.max(...xe)) / 2, cy = (Math.min(...ys) + Math.max(...ye)) / 2;
    const w = Math.max(...xe) - Math.min(...xs), h = Math.max(...ye) - Math.min(...ys), nw = R[0][2];
    if (nw >= (SC.nodePx || 175) || w * 1.12 > 3700 || h * 1.12 > 2150) break;
    await pA.keyboard.down('Control'); await pA.mouse.move(cx, cy); await pA.mouse.wheel(0, -60); await pA.keyboard.up('Control'); await sleep(250);
    const R2 = await getR(); const w2 = Math.max(...R2.map(r => r[0] + r[2])) - Math.min(...R2.map(r => r[0]));
    if (w2 > 3700 || Math.min(...R2.map(r => r[0])) < 40 || Math.max(...R2.map(r => r[0] + r[2])) > 3800) { await pA.keyboard.down('Control'); await pA.mouse.wheel(0, 60); await pA.keyboard.up('Control'); await sleep(250); break; }
  }
  // re-centre the graph
  { const R = await getR(); const cx = (Math.min(...R.map(r => r[0])) + Math.max(...R.map(r => r[0] + r[2]))) / 2, cy = (Math.min(...R.map(r => r[1])) + Math.max(...R.map(r => r[1] + r[3]))) / 2;
    await pA.mouse.move(cx, cy); await pA.mouse.down({ button: 'middle' }).catch(() => {}); await pA.mouse.up({ button: 'middle' }).catch(() => {}); }
  await sleep(700);
  meta.rects = await pA.evaluate(() => Object.fromEntries([...document.querySelectorAll('[data-test-id="canvas-node"]')].map(e => {
    const box = e.querySelector('[data-test-id="canvas-default-node"],[data-test-id="canvas-trigger-node"]') || e;
    const r = box.getBoundingClientRect(); return [e.dataset.nodeName, [r.x, r.y, r.width, r.height]]; })));
  const sA = await screencast(pA, path.join(OUT, 'nframes'), t0, meta.nlog = []);
  await sA.start(3840, 2400);
  await pA.evaluate(() => { window.__nt = {}; setInterval(() => { for (const e of document.querySelectorAll('[data-test-id="canvas-node"]')) { const n = e.dataset.nodeName;
      for (const st of ['running', 'success']) { if (e.querySelector('[data-test-id="canvas-node-status-' + st + '"]') && !window.__nt[n + ':' + st]) window.__nt[n + ':' + st] = Date.now(); } } }, 30); });
  await sleep(1200); mark('canvas');
  await pA.mouse.move(1300, 260);
  if (!SC.manual) await pA.click('[data-test-id="execute-workflow-button"]');
  await sleep(1200); mark('listening');

  // --- form browser ---
  const bB = await chromium.launch();
  const pB = await (await bB.newContext({ viewport: { width: 1080, height: 2100 } })).newPage();
  if (SC.formPage) {
    await pB.goto('http://harbourlinephysio.test/' + SC.formPage + (SC.formPage.includes('?') ? '&' : '?') + 'hook=' + encodeURIComponent('http://localhost:5678/webhook-test/' + HOOK));
  } else if (SC.page) {
    await pB.goto('http://harbourlinephysio.test/' + SC.page + '&hook=' + encodeURIComponent('http://localhost:5678/webhook-test/' + HOOK));
  } else {
    await pB.goto('http://harbourlinephysio.test/?hook=' + encodeURIComponent('http://localhost:5678/webhook-test/' + HOOK) + (SC.reveal ? '&reveal=1' : ''));
  }
  await pB.evaluate(() => { document.documentElement.style.zoom = '2'; });
  await pB.evaluate(() => document.fonts.ready); await sleep(400);
  const sB = await screencast(pB, path.join(OUT, 'fframes'), t0, meta.flog = []);
  await sB.start(1080, 2100);
  await sleep(500); mark('form_start');
  const SEND = SC.manual ? 'h1' : (SC.page ? '#act' : '#send');
  if (SC.page) {
    await sleep(1400);
  } else {
    const F = SC.form;
    for (const k of ['name', 'email', 'phone', 'message']) {
      if (!F[k]) continue;
      await pB.click('#' + k); await pB.keyboard.type(F[k], { delay: k === 'message' ? 18 : 30 });
      await sleep(150);
    }
    if (F.website) { if (SC.reveal) { await pB.click('#website'); await pB.keyboard.type(F.website, { delay: 25 }); } else { await pB.evaluate(v => { document.getElementById('website').value = v; }, F.website); } mark('honeypot_filled'); }
  }
  await sleep(350); mark('submit');
  meta.sendRect = await pB.evaluate(s => { const r = document.querySelector(s).getBoundingClientRect(); return [r.x*2, r.y*2, r.width*2, r.height*2]; }, SEND);
  if (SC.manual) { await pA.click('[data-test-id="execute-workflow-button"]'); }
  if (SC.approve) {
    let url = null;
    for (let k = 0; k < 120 && !url; k++) {
      await sleep(250);
      for (const f of fs.readdirSync('/home/claude/sandbox/mail')) {
        const m = JSON.parse(fs.readFileSync('/home/claude/sandbox/mail/' + f));
        const mm = /(http\S+\?approve=yes)/.exec(m.text || ''); if (mm && m.at * 1000 > t0) url = mm[1];
      }
    }
    await sleep(SC.approveDelay || 1800); mark('approve');
    if (url) await fetch(url).catch(() => {});
    await pA.waitForFunction(n => window.__nt && window.__nt[n + ':success'], SC.lastNode, { timeout: 30000 }).catch(() => {});
  }
  else await pB.click(SEND);
  if (!SC.manual) await pB.waitForFunction(() => { const o = document.getElementById('ok'); return o && getComputedStyle(o).display === 'block'; }, null, { timeout: 30000 }).catch(() => {});
  mark('form_reply');
  // wait for execution to finish
  await pA.waitForFunction(() => /executed successfully|Problem in node|Workflow execution finished|Waiting/i.test(document.body.innerText) && (window.__nt && Object.keys(window.__nt).some(k=>k.endsWith(':success'))), null, { timeout: SC.doneTimeout || 30000 }).catch(() => {});
  if (SC.settle) await sleep(SC.settle);
  mark('done');
  await sleep(1800);
  await sB.stop(); await sA.stop();
  const nt = await pA.evaluate(() => window.__nt);
  for (const [k, v] of Object.entries(nt)) meta.nodeTimes[k] = (v - t0) / 1000;
  meta.formReplyText = await pB.evaluate(() => document.getElementById('ok')?.textContent || '');
  await bB.close();

  // --- hi-dpi panels ---
  await pA.setViewportSize({ width: 1280, height: 800 });
  const cdp = await cA.newCDPSession(pA);
  await sleep(800); await pA.mouse.click(700, 120); await pA.keyboard.press('1'); await sleep(600);
  for (const [node, file] of (SC.panels || [])) {
    await pA.getByText(node, { exact: true }).first().dblclick(); await sleep(1600);
    if (SC.panelTab) { const t = pA.getByText(SC.panelTab, { exact: true }); if (await t.count()) await t.last().click().catch(() => {}); await sleep(300); }
    const shot = await cdp.send('Page.captureScreenshot', { format: 'png', clip: { x: 0, y: 0, width: 1280, height: 800, scale: 2.5 } });
    fs.writeFileSync(path.join(OUT, file), Buffer.from(shot.data, 'base64'));
    await pA.keyboard.press('Escape'); await sleep(600);
  }
  await bA.close();
  const mails = fs.readdirSync('/home/claude/sandbox/mail').sort().map(f => JSON.parse(fs.readFileSync('/home/claude/sandbox/mail/' + f)));
  meta.mails = mails.map(m => ({ ...m, rel: m.at - t0 / 1000 }));
  try { meta.aiRequest = JSON.parse(fs.readFileSync('/home/claude/sandbox/ai_last.json', 'utf8')); } catch (e) {}
  fs.writeFileSync(path.join(OUT, 'meta.json'), JSON.stringify(meta, null, 1));
  console.log(JSON.stringify({ marks: meta.marks, nodeTimes: meta.nodeTimes, mails: meta.mails.map(m => [m.subject, m.rel.toFixed(2)]) }, null, 1));
})();
