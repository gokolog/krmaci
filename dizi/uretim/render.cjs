// Kullanım: node render.cjs [cikti.mp4] [ses.mp3]
// Chromium ile bolum01.html'i kare kare çizer, ffmpeg ile MP4 yapar (ses varsa ekler).
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const out = path.resolve(process.argv[2] || 'bolum01.mp4');
const audio = process.argv[3] && fs.existsSync(process.argv[3]) ? path.resolve(process.argv[3]) : null;
const FPS = 30, DUR = 30;

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 540, height: 960 }, deviceScaleFactor: 2 });
  await page.goto('file://' + path.join(__dirname, 'bolum01.html') + '?render');
  await page.waitForTimeout(500);
  const args = ['-y', '-f', 'image2pipe', '-framerate', String(FPS), '-i', '-'];
  if (audio) args.push('-i', audio);
  args.push('-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-vf', 'scale=1080:1920');
  if (audio) args.push('-c:a', 'aac', '-b:a', '192k', '-shortest');
  args.push('-t', String(DUR), out);
  const ff = spawn('ffmpeg', args, { stdio: ['pipe', 'ignore', 'inherit'] });
  const canvas = await page.$('#c');
  for (let i = 0; i < FPS * DUR; i++) {
    await page.evaluate((t) => window.draw(t), i / FPS);
    const buf = await canvas.screenshot({ type: 'jpeg', quality: 92 });
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
  }
  ff.stdin.end();
  await new Promise((r) => ff.on('close', r));
  await browser.close();
  console.log('Hazır:', out, audio ? '(sesli)' : '(sessiz)');
})();
