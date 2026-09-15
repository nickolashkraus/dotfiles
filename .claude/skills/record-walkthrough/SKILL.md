---
name: record-walkthrough
description: >
  Record a narrated product walkthrough video (MP4) or demo GIF of a web
  app using headless Puppeteer screencast, edge-tts narration, and ffmpeg
  muxing. Covers scripted auth for the FH Admin App, cursor injection,
  narration sync via wall-clock offsets, and the gotchas that bit prior
  runs (screencast timestamp drift, audio clipping, segment overflow).
  TRIGGER when: user wants a walkthrough video, demo recording, narrated
  screencast, or demo GIF of a web UI.
disable-model-invocation: false
allowed-tools: Bash, Read, Write
---

Produce a narrated walkthrough MP4 (or silent GIF) of a web app. The
pipeline: record a headless Puppeteer screencast, generate TTS narration
segments, then mux with ffmpeg using per-section wall-clock offsets.

Do NOT use the Chrome extension's `gif_creator` for this. It captures one
frame per action (max 50), which produces a slideshow, not a recording.

## Step 1: Record the Screencast

Start from `record.example.mjs` in this skill's directory: copy it into
the runner worktree as `record.tmp.mjs`, adapt the SECTIONS block, and
run it from there (it needs the worktree's `node_modules` for
`puppeteer-core`). Delete the copy when done. Key elements:

- Launch headless Chrome via `puppeteer-core` with
  `executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google
  Chrome'`, viewport 1280x800.
- Record with `const recorder = await page.screencast({ path:
  `${OUT}/rec.webm` })` and `await recorder.stop()` at the end.
- Inject a fake cursor so clicks are visible (headless renders no
  cursor): a fixed-position `div#__cursor` (18px orange circle, white
  border, `z-index: 2147483647`, `pointer-events: none`) that tracks
  `mousemove`.
- Move the mouse with a `glide(x, y, steps)` helper (interpolated
  `page.mouse.move` at ~16ms per step) so motion looks human.
- Click elements by text with the `::-p-text()` selector, e.g.
  `page.$$('button ::-p-text(Save)')`.
- For narrated videos, record per-section wall-clock offsets: `const t0
  = Date.now()` right after `screencast()` starts, `mark('s1')` at each
  section boundary, write `offsets.json` at the end. These offsets place
  the narration segments in Step 3.
- Pace each section to its narration length (~2-5s of idle or scroll per
  beat). Smooth scrolls via `page.evaluate(() => window.scrollTo({ top,
  behavior: 'smooth' }))`.

### Scripted Auth (FH Admin App)

The Admin App (Dev) accepts a forged session cookie, so no interactive
login is needed:

- `token` cookie: `zlib.deflateSync(Buffer.from(jwt)).toString('base64')`
  where `jwt` is `GRAPHQL_AUTH_TOKEN` from the worktree's `.env.local`
  (Dev superuser JWT). Matches `compressToken` in
  `src/lib/cookieTokenHelpers.ts` (values over ~3800 chars get chunked
  into `token.0`..`token.9`; a 1440-char JWT fits unchunked).
- `appVersion` cookie: set to the currently deployed version (footer of
  the deployed app). Without it, the Statsig force-logout middleware in
  `src/proxy.ts` redirects to `/logout?newVersion=true`.

Set both with `browser.setCookie(...)` before `page.goto`. Never drive a
real login; credential entry is prohibited.

### Manual Auth (FH Member App and Other Apps)

The member app (`my.dev.functionhealth.com`) has no forgeable cookie,
and extracting its session token (`localStorage.userData`) from a
logged-in browser is blocked by the permission classifier. Do not fight
either constraint. Launch Puppeteer **headful** with a fresh
`userDataDir` in the scratchpad, open the login page, and poll until the
user has logged in themselves (URL off `/login` and
`localStorage.getItem('userData')` non-null, ~5 min deadline). Only then
start `page.screencast`, so credentials never appear in the video. Tell
the user a window is waiting for their login, and run the script with
`run_in_background` since it blocks on them. The target repo may lack
`node_modules`; any worktree with a recent `puppeteer-core` works as the
runner (e.g. `admin-app-fe-next/dev`, v24+ for `page.screencast`).

## Step 2: Generate Narration

Write one text file per section (`seg1.txt`..`segN.txt`), then:

```
uvx edge-tts --voice en-US-AriaNeural --pitch=-12Hz --rate=-4% \
  --file segN.txt --write-media nsegN.mp3
```

- `en-US-AriaNeural` at `-12Hz` pitch and `-4%` rate is the approved
  warm/low register. Never clone a real person's voice.
- edge-tts sends the text to Microsoft's service; flag this to the user
  if the narration text is sensitive.
- macOS `say` is the offline fallback, but only compact voices are
  installed (Samantha is the best of them); quality is noticeably worse.
- Measure each segment: `ffprobe -v error -show_entries format=duration
  -of csv=p=0 nsegN.mp3`. If a segment is longer than its slot (next
  section offset minus its own), shift the following segment's delay to
  avoid overlap, or trim the script text.

## Step 3: Mux Narration onto Video

Two corrections are mandatory before placing audio:

1. **Retime the video to wall clock.** Screencast timestamps drift (a
   prior run produced 94.9s of video for 87.6s of wall clock, ~8% long),
   so wall-clock offsets drift out of sync by the end. Compute `ratio
   = wallclock_duration / ffprobe_video_duration` and prepend
   `setpts=PTS*<ratio>` to the video filter chain.
2. **Loudness-normalize, never naive gain.** `volume=2.2` after `amix`
   clipped at 0.0 dB. Use `loudnorm`.

```
ffmpeg -i rec.webm -i nseg1.mp3 ... -i nseg5.mp3 -filter_complex \
  "[0:v]setpts=PTS*<ratio>[v];\
   [1:a]adelay=<ms1>:all=1[a1];...;[5:a]adelay=<ms5>:all=1[a5];\
   [a1][a2][a3][a4][a5]amix=inputs=5:normalize=0,\
   loudnorm=I=-16:TP=-1.5:LRA=11[a]" \
  -map "[v]" -map "[a]" -c:v libx264 -pix_fmt yuv420p -c:a aac out.mp4
```

- `adelay` values are the `offsets.json` marks (ms), adjusted for any
  overflow shifts from Step 2.
- Verify loudness with `-af volumedetect`: target mean around -17 dB and
  max at or below -1.0 dB. If the max still reads ~0 dB after `loudnorm`,
  append `alimiter=limit=0.84:level=0`. The `level=0` is mandatory, since
  alimiter's default auto-level boosts output right back to full scale.
  A residual few tenths of a dB above the ceiling is AAC encoder
  overshoot and acceptable.
- A segment that outruns the video: extend the tail instead of trimming
  the script, via `tpad=stop_mode=clone:stop_duration=<s>` after
  `setpts` (freezes the last frame as an outro).
- Verify sync by extracting frames at 2-3 narration boundaries
  (`ffmpeg -ss <t> -frames:v 1`) and checking the screen matches the
  narration beat.

## GIF Variant (Silent, for PRs)

```
ffmpeg -i rec.webm -filter_complex \
  "setpts=PTS/2,fps=15,scale=720:-1:flags=lanczos,split[s0][s1];\
   [s0]palettegen=max_colors=128[p];\
   [s1][p]paletteuse=dither=bayer:bayer_scale=5" out.gif
```

- `setpts=PTS/2` plays at 2x; drop it for real time.
- Homebrew ffmpeg rejects `-vsync`; use `-fps_mode vfr` if needed.
- 15 fps at 720px with 128 colors keeps a ~10s GIF near 1 MB.

## Cleanup

Delete `record.tmp.mjs` from the worktree and confirm intermediates
(webm, mp3, txt, offsets.json) stayed in the scratchpad. Deliver the
final MP4/GIF to `~/Downloads` and send it with SendUserFile.
