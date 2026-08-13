"""Turn the exported logo JPEG into a real transparent PNG.

The background-removal export came back as .jpeg, and JPEG cannot store an
alpha channel -- so the transparency checkerboard was flattened into the
picture as actual grey squares. Used as-is, the logo carries a chequered grey
box wherever it is placed.

The two are separable without any hand masking: the mark is intensely
saturated neon, and the checkerboard is pure grey, where R, G and B are equal.
So chroma -- the spread between the channels -- is the mask. It also handles
the glow for free: a glow pixel is grey blended with neon, so its chroma sits
between the two and produces a partial alpha, which is exactly the soft edge
the halo needs. A hard threshold would have cut the glow off with a visible
rectangle around the mark.

Writes both the wide lockup and a square mark for avatars and favicons.
"""

import sys
from pathlib import Path

from PIL import Image

SOURCE = Path(r"C:\Users\Vinayak\Downloads\Remove_background_for_website_2K_202608132330.jpeg")
OUT_DIR = Path(__file__).resolve().parent.parent / "frontend" / "public"

# Below this chroma a pixel is indistinguishable from the grey checkerboard.
FLOOR = 12
# At and above this it is unambiguously part of the mark and fully opaque.
CEILING = 46


def keyed(image: Image.Image) -> Image.Image:
    """Alpha from chroma, so the neon stays and the grey goes."""
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()

    out = Image.new("RGBA", (width, height))
    target = out.load()

    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            chroma = max(r, g, b) - min(r, g, b)

            if chroma <= FLOOR:
                target[x, y] = (r, g, b, 0)
                continue
            if chroma >= CEILING:
                target[x, y] = (r, g, b, 255)
                continue

            # Ramp between the two, which keeps the halo soft.
            alpha = int(255 * (chroma - FLOOR) / (CEILING - FLOOR))
            target[x, y] = (r, g, b, alpha)

    return out


def main() -> None:
    if not SOURCE.exists():
        print(f"Source not found: {SOURCE}")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    original = Image.open(SOURCE)
    print(f"source: {original.size[0]}x{original.size[1]} {original.mode}")

    transparent = keyed(original)

    # Trim to what is actually drawn, so the asset has no dead margin to
    # centre around later.
    box = transparent.getbbox()
    if box:
        transparent = transparent.crop(box)
        print(f"cropped to content: {transparent.size[0]}x{transparent.size[1]}")

    wide = transparent.copy()
    wide.thumbnail((1200, 1200), Image.LANCZOS)
    wide_path = OUT_DIR / "logo.png"
    wide.save(wide_path, "PNG", optimize=True)
    print(f"wrote {wide_path}  {wide.size[0]}x{wide.size[1]}  "
          f"{wide_path.stat().st_size // 1024}KB")

    # The lockup WITHOUT the tagline, for navigation bars.
    #
    # The full lockup is the right artwork on a hero or a share card, and the
    # wrong one in a 34px-tall nav: the tagline lands at about six pixels,
    # which is not small type, it is grey mush. Cropping it away keeps the
    # logo as drawn and drops only the line that cannot be read at that size.
    # A straight horizontal cut cannot do this: the cloud descends lower than
    # the wordmark does, so any line high enough to lose the tagline also
    # slices the base off the mark. Instead the tagline's own region is
    # cleared -- it lives to the RIGHT of the mark and below the wordmark --
    # and the result is re-cropped to whatever is left.
    # The cut line is FOUND, not guessed. A fixed percentage left a ghost of
    # the tagline's glow under the wordmark: neon type carries a halo well
    # above its own letterforms, so any line low enough to spare the "g"
    # descender also kept the top of that halo.
    #
    # Instead, look only at the right-hand side (where the two lines of type
    # are, clear of the mark) and measure ink per row. The wordmark and the
    # tagline are separated by a band of near-nothing; the quietest row in
    # that band is the seam, and cutting there removes the tagline and its
    # halo together while leaving the descenders intact.
    w, h = transparent.size
    alpha = transparent.getchannel("A")
    text_left = int(w * 0.34)

    ink = []
    for y in range(h):
        strip = alpha.crop((text_left, y, w, y + 1))
        ink.append(sum(strip.getdata()))

    peak = max(ink) or 1
    quiet = peak * 0.04

    # Taking the globally quietest row finds the empty space BELOW the
    # tagline, which is quieter than the gap between the lines and cuts
    # nothing. The seam is the first quiet row that still has type under it.
    seam = None
    for y in range(int(h * 0.5), int(h * 0.9)):
        if ink[y] <= quiet and any(v > quiet for v in ink[y + 1:]):
            seam = y
            break
    if seam is None:
        seam = int(h * 0.72)
    print(f"  tagline seam found at y={seam} ({seam / h:.0%} of height)")

    no_tagline = transparent.copy()
    no_tagline.paste((0, 0, 0, 0), (text_left, seam, w, h))
    box_nt = no_tagline.getbbox()
    if box_nt:
        no_tagline = no_tagline.crop(box_nt)
    no_tagline.thumbnail((900, 900), Image.LANCZOS)
    lockup_path = OUT_DIR / "logo-lockup.png"
    no_tagline.save(lockup_path, "PNG", optimize=True)
    print(f"wrote {lockup_path}  {no_tagline.size[0]}x{no_tagline.size[1]}  "
          f"{lockup_path.stat().st_size // 1024}KB")

    # The mark alone, squared, for avatars and the favicon. The cloud sits in
    # roughly the first third of the lockup.
    w, h = transparent.size
    mark = transparent.crop((0, 0, int(w * 0.33), h))
    mark_box = mark.getbbox()
    if mark_box:
        mark = mark.crop(mark_box)

    side = max(mark.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(mark, ((side - mark.size[0]) // 2, (side - mark.size[1]) // 2))
    square.thumbnail((512, 512), Image.LANCZOS)
    mark_path = OUT_DIR / "logo-mark.png"
    square.save(mark_path, "PNG", optimize=True)
    print(f"wrote {mark_path}  {square.size[0]}x{square.size[1]}  "
          f"{mark_path.stat().st_size // 1024}KB")

    # Sanity: a genuinely transparent PNG has both clear and opaque pixels.
    alpha = wide.getchannel("A")
    lo, hi = alpha.getextrema()
    print(f"alpha range {lo}-{hi} "
          f"({'transparent background confirmed' if lo == 0 else 'NO TRANSPARENCY'})")


if __name__ == "__main__":
    main()
