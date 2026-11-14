# Platform specs

Checked on 2026-10-10. Platforms change their limits: when a number here disagrees with the platform's help page, the help page wins; update this file.

## LinkedIn document post (PDF)

- Upload: PDF, PPT, PPTX, DOC, DOCX. Max 100 MB, max 300 pages (LinkedIn Help, "Share a document"). Aim for under 15 MB so the upload and the viewer stay fast.
- Page ratio: 4:5 (1080x1350 px pages, 810x1012.5 pt) and 1:1 are both shown full width in the feed; 4:5 takes more screen.
- The PDF is shown page by page; links inside it are not clickable in the feed: put links in the first comment.
- Document title: set it in the upload dialog (the PDF title metadata is the deck `meta.title`).
- Post text: 3000 characters max; about the first 210 show before "see more" on desktop, fewer on mobile, so the thesis goes in the first 125.
- Alt text: LinkedIn does not take per-page alt text on documents; put a short description in the post or the first comment when the slides carry information a screen reader would miss.

## Instagram carousel (images)

- Up to 20 images per carousel. JPEG or PNG; JPEG sRGB recommended (Instagram recompresses everything).
- Sizes: 1080x1350 (4:5, portrait, the most screen) or 1080x1080 (1:1). All images of one carousel take the ratio of the first.
- The profile grid shows a 3:4 crop of portrait posts: keep the cover's key element out of the outer 45 px left and right.
- Caption: 2200 characters max, 30 hashtags max (3 to 5 recommended), about 125 characters show before "more". Links in captions are not clickable: "link in bio".
- Alt text per image: available under Advanced settings when posting; keep it short and factual.

## Video variant (animate.py)

Checked on 2026-10-12.

- LinkedIn native video: MP4 among other containers, 3 s to 15 min, 75 KB to 5 GB, 256x144 to 4096x2304 px, ratio 1:2.4 to 2.4:1, 10 to 60 fps, 192 kbit/s to 30 Mbit/s; keep text and logos off the edges (LinkedIn Help, "Troubleshooting video sharing": https://www.linkedin.com/help/linkedin/answer/a548372). `animate.py` checks duration, bitrate and weight against these limits.
- Instagram: a 4:5 video posts to the feed, a 9:16 video is a Reel. The Reels interface covers the top (account name), the bottom (caption, audio, buttons) and the right edge (action rail). Organic Reels guides keep text out of about the top 220 px and the bottom 430 px of a 1080x1920 frame (https://www.xyla.ai/tools/social-media-sizes); Meta's ads guidance asks for 14 % top, 35 % bottom and 6 % on each side (summarised with the Meta Help Center references at https://adsuploader.com/blog/meta-ads-safe-zones). `--safe reels` (default for 9:16) uses 220, 430 and 90 px; `--safe ads` uses 269, 672 and 65 px.
- Encoding written by `animate.py`: H.264 High, yuv420p, BT.709 tags, 30 fps constant, CRF 18, keyframe every 2 s, `moov` atom first (`+faststart`, playback starts before the download ends), AAC 192 kbit/s 48 kHz stereo when `--music` is given.

## What render.py produces

| File | Spec |
|------|------|
| `export/slide-NN.png` | exact 1080x1350 (or 1080x1080), sRGB profile, lossless, for archives and other tools |
| `export/slide-NN.jpg` | 1080 wide, quality 88, 4:4:4 chroma (sharp text), progressive, sRGB profile: the Instagram files |
| `export/carousel.pdf` | one page per slide, page size from the CSS (`@page`), vector text with embedded fonts, backgrounds printed: the LinkedIn file |
