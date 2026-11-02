// Audit responsive: ogni pagina x larghezza x lingua. Uso: node tools/audit_responsive.js http://localhost:8765/ [--shots dir]
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const fs = require('fs');
const B = process.argv[2]; const SHOTS = process.argv.includes('--shots') ? process.argv[process.argv.indexOf('--shots') + 1] : null;
const WIDTHS = [360, 390, 768, 1024, 1280, 1440];
const schede = fs.readdirSync(process.env.SITE_DIR + '/progetti').filter(f => f.endsWith('.html')).sort();
const pick = [schede[0], schede[Math.floor(schede.length / 2)], schede.reduce((a, b) => (a.length >= b.length ? a : b))];
const PAGES = [['home', ''], ['elenco', 'opere/'], ['dati', 'dati/'], ['tutorial', 'guida/'], ['coding', 'guida/costruisci/'], ['metodo', 'metodo/'], ...pick.map((f, i) => ['scheda' + (i + 1), 'progetti/' + f])];
(async () => {
  const b = await chromium.launch({ args: ['--no-sandbox'] }); const res = []; const problemi = [];
  for (const lang of ['', 'en/']) for (const [nome, u] of PAGES) for (const w of WIDTHS) {
    const p = await (await b.newContext({ viewport: { width: w, height: 800 } })).newPage();
    const err = []; p.on('pageerror', e => err.push(String(e))); p.on('console', m => { if (m.type() === 'error') err.push(m.text()); });
    const r = await p.goto(B + lang + u);
    const o = await p.evaluate((w) => {
      const out = [];
      const vis = e => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
      if (document.documentElement.scrollWidth > innerWidth + 1) out.push('scroll orizzontale pagina');
      const inScroll = e => { for (let a = e.parentElement; a; a = a.parentElement) { const ov = getComputedStyle(a).overflowX; if ((ov === 'auto' || ov === 'scroll') && a !== document.documentElement && a !== document.body) return true; } return false; };
      let fuori = 0, ex = '';
      document.querySelectorAll('body *').forEach(e => { if (!vis(e) || inScroll(e) || e.closest('svg')) return; const r = e.getBoundingClientRect(); if (r.right > innerWidth + 1 || r.left < -1) { fuori++; ex = ex || e.tagName + '.' + e.className; } });
      if (fuori) out.push('elementi fuori schermo: ' + fuori + ' (' + ex + ')');
      let tag = '';
      document.querySelectorAll('.card,.btn,.avv,.tag,.passi a,.build,.hero,.vuoto,.lista li,dd,td,th').forEach(e => { if (!vis(e) || inScroll(e)) return; if (e.scrollWidth > e.clientWidth + 2 && getComputedStyle(e).overflowX === 'visible' && e.tagName !== 'TD' && e.tagName !== 'TH') tag = tag || 'testo oltre il riquadro: ' + e.tagName + '.' + e.className; });
      if (tag) out.push(tag);
      // barra
      const row = document.querySelector('header.top .w.nav'); const items = [row.querySelector('b'), ...row.querySelectorAll('nav a'), ...[...row.querySelectorAll('a.lingua')]].filter(e => e && vis(e));
      const cy = items.map(e => { const r = e.getBoundingClientRect(); return r.top + r.height / 2; });
      const righe = Math.max(...cy) - Math.min(...cy) > 14;
      const hh = document.querySelector('header.top').offsetHeight;
      if (w >= 900 && righe) out.push('barra su piu righe');
      if (w < 900 && hh > 150) out.push('barra troppo alta: ' + hh);
      // tocco
      if (w <= 768) { const bad = []; document.querySelectorAll('nav a,.btn,button,select,input,.passi a,.cerca button').forEach(e => { if (!vis(e) || inScroll(e)) return; const h = e.getBoundingClientRect().height; if (h < 36) bad.push(e.tagName + '.' + e.className + ':' + Math.round(h)); }); if (bad.length) out.push('bersagli piccoli: ' + bad.slice(0, 3).join(', ')); }
      // leggibilita
      let small = 0; document.querySelectorAll('main p,main li,main td,main dd,main dt,main span,main a').forEach(e => { if (vis(e) && parseFloat(getComputedStyle(e).fontSize) < 12.5) small++; });
      if (small) out.push('testo sotto 12.5px: ' + small);
      document.querySelectorAll('svg.sch-o,svg.sch-v').forEach(s => { if (!vis(s)) return; const k = s.getBoundingClientRect().width / s.viewBox.baseVal.width; if (13 * k < 11) out.push('schema: testo ' + (13 * k).toFixed(1) + 'px'); });
      document.querySelectorAll('svg').forEach(sv => { if (!vis(sv)) return; sv.querySelectorAll('g.bx').forEach(g => { const rb = g.querySelector('rect').getBBox(); g.querySelectorAll('text').forEach(t => { const tb = t.getBBox(); if (tb.x + tb.width > rb.x + rb.width - 6 || tb.x < rb.x) out.push('schema: testo fuori riquadro: ' + t.textContent.slice(0, 30)); }); }); });
      // tabelle: dentro contenitore scorrevole
      document.querySelectorAll('table').forEach(t => { if (!inScroll(t) && t.getBoundingClientRect().right > innerWidth + 1) out.push('tabella fuori contenitore'); });
      return out;
    }, w);
    if (r.status() !== 200) o.push('HTTP ' + r.status()); if (err.length) o.push('errori console: ' + err[0]);
    if (SHOTS && ['home', 'scheda3'].includes(nome) && (w === 360 || w === 1024)) await p.screenshot({ path: `${SHOTS}/${lang ? 'en' : 'it'}_${nome}_${w}.png` });
    res.push({ lang: lang ? 'EN' : 'IT', nome, w, ok: o.length === 0, o }); if (o.length) problemi.push(`${lang ? 'EN' : 'IT'} ${nome} ${w}: ${o.join(' | ')}`);
    await p.context().close();
  }
  // tabella
  for (const lang of ['IT', 'EN']) { console.log('\n' + lang + '  pagina       ' + WIDTHS.join('  ')); for (const [nome] of PAGES) console.log('   ' + nome.padEnd(11) + '  ' + WIDTHS.map(w => (res.find(r => r.lang === lang && r.nome === nome && r.w === w).ok ? 'OK ' : 'KO ').padStart(4)).join(' ')); }
  console.log('\nPROBLEMI: ' + problemi.length); problemi.forEach(x => console.log(' - ' + x));
  fs.writeFileSync(process.env.AUDIT_OUT || '/dev/null', JSON.stringify(res)); await b.close(); process.exit(problemi.length ? 1 : 0);
})();
