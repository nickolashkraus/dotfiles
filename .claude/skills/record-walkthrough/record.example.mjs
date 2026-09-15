// Reference recorder for the record-walkthrough skill. Copy to the runner
// worktree as `record.tmp.mjs`, adapt SECTIONS, run, then delete the copy.
// This variant uses manual auth (headful window, user logs in themselves);
// for the Admin App swap the login-wait for the forged-cookie setup in
// SKILL.md and set `headless: true`.
//
// Run from a worktree whose node_modules has puppeteer-core v24+
// (page.screencast), e.g. admin-app-fe-next/dev:
//   node record.tmp.mjs
import fs from 'fs';
import puppeteer from 'puppeteer-core';

const OUT = process.env.WALKTHROUGH_OUT ?? '/tmp/walkthrough';
const BASE = 'https://my.dev.functionhealth.com';
fs.mkdirSync(OUT, {recursive: true});

const browser = await puppeteer.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: false,
  userDataDir: `${OUT}/profile`,
  defaultViewport: {width: 1280, height: 800},
  args: ['--window-size=1296,920', '--no-first-run', '--no-default-browser-check'],
});
const page = (await browser.pages())[0];

// Manual auth: open the login page and wait for the user. The screencast
// starts only after login, so credentials never appear in the video.
await page.goto(`${BASE}/login`, {waitUntil: 'domcontentloaded'});
console.log('WAITING_FOR_LOGIN');
const deadline = Date.now() + 300000;
let loggedIn = false;
while (Date.now() < deadline) {
  await new Promise(r => setTimeout(r, 1500));
  if (!page.url().includes('/login')) {
    const ud = await page
      .evaluate(() => Boolean(localStorage.getItem('userData')))
      .catch(() => false);
    if (ud) {
      loggedIn = true;
      break;
    }
  }
}
if (!loggedIn) {
  console.log('LOGIN_TIMEOUT');
  await browser.close();
  process.exit(1);
}
console.log('LOGIN_DETECTED');
await new Promise(r => setTimeout(r, 3000));

// Headless/headful Chrome under CDP renders no OS cursor; inject one so
// clicks are visible. Re-run after every full navigation (document resets).
const installCursor = async () => {
  await page.evaluate(() => {
    if (document.getElementById('__cursor')) return;
    const c = document.createElement('div');
    c.id = '__cursor';
    Object.assign(c.style, {
      position: 'fixed',
      width: '18px',
      height: '18px',
      borderRadius: '50%',
      background: 'rgba(255,140,0,0.9)',
      border: '2px solid white',
      zIndex: 2147483647,
      pointerEvents: 'none',
      left: '0px',
      top: '0px',
      transform: 'translate(-50%,-50%)',
    });
    document.body.appendChild(c);
    document.addEventListener(
      'mousemove',
      e => {
        c.style.left = `${e.clientX}px`;
        c.style.top = `${e.clientY}px`;
      },
      true
    );
  });
};

let mx = 640;
let my = 400;
const glide = async (x, y, steps = 28) => {
  for (let i = 1; i <= steps; i++) {
    await page.mouse.move(mx + ((x - mx) * i) / steps, my + ((y - my) * i) / steps);
    await new Promise(r => setTimeout(r, 16));
  }
  mx = x;
  my = y;
};

const findBox = (selectorList, text) =>
  page.evaluate(
    (sel, t) => {
      const el = [...document.querySelectorAll(sel)].find(
        e => e.childElementCount === 0 && e.textContent.trim() === t
      );
      if (!el) return null;
      const row = el.closest('[class*="GroupRow"],a,button') || el.parentElement;
      row.scrollIntoView({behavior: 'smooth', block: 'center'});
      const r = row.getBoundingClientRect();
      return {x: r.x + r.width / 2, y: r.y + r.height / 2};
    },
    selectorList,
    text
  );

const offsets = {};
const recorder = await page.screencast({path: `${OUT}/rec.webm`});
const t0 = Date.now();
const mark = n => {
  offsets[n] = Date.now() - t0;
};

// SECTIONS: one mark per narration segment; pace each beat with idles.
mark('s1');
await page
  .goto(`${BASE}/account`, {waitUntil: 'networkidle2', timeout: 45000})
  .catch(() => {});
await installCursor();
await new Promise(r => setTimeout(r, 5000));

const rowBox = await findBox('div,span,h1,h2,h3,h4', 'Kraus Family');
await new Promise(r => setTimeout(r, 2500));
if (rowBox) {
  await glide(rowBox.x, rowBox.y);
  await new Promise(r => setTimeout(r, 1500));
}

mark('s2');
if (rowBox) await page.mouse.click(rowBox.x, rowBox.y);
await new Promise(r => setTimeout(r, 4000));
await installCursor();

mark('s3');
const invBox = await page.evaluate(() => {
  const el = [...document.querySelectorAll('div,span')].find(
    e => e.childElementCount === 0 && e.textContent.includes('family-qa')
  );
  if (!el) return null;
  el.scrollIntoView({behavior: 'smooth', block: 'center'});
  const r = el.getBoundingClientRect();
  return {x: r.x + r.width / 2, y: r.y + r.height / 2};
});
await new Promise(r => setTimeout(r, 1500));
if (invBox) await glide(invBox.x, invBox.y);
await new Promise(r => setTimeout(r, 5000));

mark('end');
await recorder.stop();
fs.writeFileSync(`${OUT}/offsets.json`, JSON.stringify(offsets));
await browser.close();
console.log('DONE', JSON.stringify(offsets));
