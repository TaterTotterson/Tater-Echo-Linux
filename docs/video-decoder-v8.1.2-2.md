# Tater video decoder 8.1.2-2 — Echo 5 input candidate

This ARMv7 FFmpeg build adds the bounded H.264 Annex-B copy output, `framecrc`
timestamp output, `h264_mp4toannexb` and `h264_metadata` filters required by
Tater's optional hardware playback path. Existing software decoding, RTSP
Digest-only handling, limited protocols and decoder/license pairing remain.
It is a development input, not an installable satellite firmware release.

## Source, reproducibility and license

- FFmpeg 8.1.2 upstream source is included as `ffmpeg-8.1.2.tar.xz`, with
  SHA-256 `464beb5e7bf0c311e68b45ae2f04e9cc2af88851abb4082231742a74d97b524c`.
- Tater's source/build recipe is Tater Echo Linux commit
  `4377ee9523137ec425072b70496625293b67dc39`:
  `tools/build_video_decoder.py`, `build-inputs/video-decoder.json` and
  `platforms/show/tools/linux/build-ffmpeg.sh`. Its accompanying tracked-source
  archive includes those scripts, patches/configure flags and repository notices.
- The builder is the existing public immutable ARMv7 firmware builder recorded
  in the JSON lock. Additional Alpine development packages have exact versions;
  the complete resulting package inventory is included. The build is fresh,
  refuses stale output directories and fails on output digest/size drift.
- FFmpeg retains LGPL-2.1-or-later and its upstream notices. See the accompanying
  `FFMPEG-LGPL-2.1.txt`, upstream source `LICENSE.md` and per-file notices.
  Tater's repository license does not relicense FFmpeg.
- To rebuild, pull the lock's builder reference and run
  `python3 tools/build_video_decoder.py --source-tar /path/to/ffmpeg-8.1.2.tar.xz
  --output /path/to/new-output`. The manual **Build hardware-capable video
  decoder** workflow performs the same build.

Output SHA-256 is
`770eba6e8f637fc311ea39cc5eaededb1e836604095386ecd7a6c22ba8086c72`,
4,336,264 bytes. A network-disabled ARMv7 generated-only test copied 15 MP4
frames to Annex-B H.264 and produced monotonic `framecrc` timestamps. The test
uses no camera, device recording, private runtime or credential. Final installed
media/stream regressions remain part of Echo 5 hardware qualification.
