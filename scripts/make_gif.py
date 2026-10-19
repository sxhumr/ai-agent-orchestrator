"""Stitch the demo frames from capture-media.mjs into docs/media/demo.gif.

uv run --with pillow python scripts/make_gif.py <frames-dir> <out.gif> <ms> [<ms> ...]
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

WIDTH = 960


def main() -> None:
    frames_dir, out, *durations = sys.argv[1:]
    paths = sorted(Path(frames_dir).glob("*.png"))
    if not paths or len(paths) != len(durations):
        sys.exit(f"expected {len(durations)} frames in {frames_dir}, found {len(paths)}")
    frames = []
    for path in paths:
        image = Image.open(path).convert("RGB")
        height = round(image.height * WIDTH / image.width)
        image = image.resize((WIDTH, height), Image.Resampling.LANCZOS)
        # Octree keeps small saturated areas (the violet buttons) that median cut greys out.
        frames.append(image.quantize(colors=256, method=Image.Quantize.FASTOCTREE))
    frames[0].save(
        out,
        save_all=True,
        append_images=frames[1:],
        duration=[int(d) for d in durations],
        loop=0,
        optimize=True,
    )
    print(f"wrote {out} ({Path(out).stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
