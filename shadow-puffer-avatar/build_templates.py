"""Shadow Puffer avatar: draws the Roblox classic clothing templates.

Writes, to out/ next to this script:
  shirt_template.png  585x559  black quilted puffer jacket with hood collar and zip
  pants_template.png  585x559  black baggy cargo pants with folds, black shoes
  face_decal.png      256x256  transparent face: round black glasses, calm eyes
  preview_front.png   front view of the blocky avatar assembled from the above

Run:  python3 build_templates.py [out_dir]

Layout follows Roblox's official 585x559 Shirt/Pants template. Transparent pixels
show the avatar's skin, so the lower part of each sleeve is left clear for hands.
"""

import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out"))
os.makedirs(OUT, exist_ok=True)

# Palette (same values as the design system's tokens.json)
JACKET = (22, 22, 24, 255)        # jacket-black
JACKET_HI = (44, 44, 48, 255)     # jacket-sheen: top of each puffer baffle
QUILT = (8, 8, 9, 255)            # quilt-seam
ZIP = (70, 70, 74, 255)           # zip-metal
PANTS = (18, 18, 20, 255)         # pants-black
PANTS_FOLD = (34, 34, 37, 255)    # pants-fold
SHOE = (12, 12, 12, 255)          # shoe-black
SKIN = (204, 178, 149, 255)       # skin
FRAME = (14, 14, 14, 255)         # glasses-frame
LENS = (255, 255, 255, 60)        # lens-glint
EYE = (24, 20, 18, 255)

W, H = 585, 559

# Official template rects: (x, y, w, h)
TORSO = {"up": (231, 8, 128, 64), "L": (165, 74, 64, 128), "F": (231, 74, 128, 128),
         "R": (361, 74, 64, 128), "B": (427, 74, 128, 128), "down": (231, 204, 128, 64)}
RIGHT_LIMB = {"up": (217, 289, 64, 64), "L": (19, 355, 64, 128), "B": (85, 355, 64, 128),
              "R": (151, 355, 64, 128), "F": (217, 355, 64, 128), "down": (217, 485, 64, 64)}
LEFT_LIMB = {"up": (308, 289, 64, 64), "F": (308, 355, 64, 128), "L": (374, 355, 64, 128),
             "B": (440, 355, 64, 128), "R": (506, 355, 64, 128), "down": (308, 485, 64, 64)}

BAFFLE = 16      # quilt pitch in px (the jacket's horizontal tube height)
HAND = 26        # px at the bottom of each sleeve left clear for the hand


def rect(d, r, fill):
    x, y, w, h = r
    d.rectangle([x, y, x + w - 1, y + h - 1], fill=fill)


def puffer(d, r, top_offset=0):
    """Fill r with puffer baffles: a lighter band at each tube's top, a seam under it."""
    x, y, w, h = r
    rect(d, r, JACKET)
    yy = y + top_offset
    while yy < y + h:
        d.rectangle([x, max(y, yy), x + w - 1, min(y + h - 1, yy + 3)], fill=JACKET_HI)
        seam = yy + BAFFLE - 2
        if y <= seam < y + h:
            d.rectangle([x, seam, x + w - 1, min(y + h - 1, seam + 1)], fill=QUILT)
        yy += BAFFLE


def shirt():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for face, r in TORSO.items():
        if face in ("up", "down"):
            rect(d, r, JACKET)
        else:
            puffer(d, r, top_offset=22)  # first 22px = hood collar
    # Hood collar: thick rolled band around the neck on front, back and sides
    for face in ("F", "B", "L", "R"):
        x, y, w, h = TORSO[face]
        rect(d, (x, y, w, 22), JACKET_HI)
        rect(d, (x, y + 20, w, 3), QUILT)
    # Top face: hood bunched behind the neck
    x, y, w, h = TORSO["up"]
    d.rounded_rectangle([x + 8, y + 6, x + w - 9, y + h - 7], radius=14, fill=JACKET_HI)
    d.rounded_rectangle([x + 34, y + 18, x + w - 35, y + h - 19], radius=8, fill=QUILT)
    # Bottom hem band
    x, y, w, h = TORSO["F"]
    for face in ("F", "B", "L", "R"):
        fx, fy, fw, fh = TORSO[face]
        rect(d, (fx, fy + fh - 10, fw, 10), QUILT)
        rect(d, (fx, fy + fh - 9, fw, 2), JACKET_HI)
    # Front zip, zip pull and small chest logo
    cx = x + w // 2
    rect(d, (cx - 2, y + 4, 4, h - 8), ZIP)
    rect(d, (cx - 1, y + 4, 2, h - 8), QUILT)
    rect(d, (cx + 2, y + 26, 4, 10), ZIP)
    rect(d, (x + 82, y + 34, 18, 8), JACKET_HI)
    rect(d, (x + 84, y + 36, 14, 4), ZIP)
    # Sleeves: puffer to the wrist, cuff, then clear for the hand
    for limb in (RIGHT_LIMB, LEFT_LIMB):
        rect(d, limb["up"], JACKET)
        x, y, w, h = limb["up"]
        rect(d, (x, y + h - 4, w, 4), QUILT)
        for face in ("F", "B", "L", "R"):
            x, y, w, h = limb[face]
            puffer(d, (x, y, w, h - HAND), top_offset=0)
            rect(d, (x, y + h - HAND - 8, w, 8), QUILT)      # ribbed cuff
            rect(d, (x, y + h - HAND - 6, w, 2), JACKET_HI)
        # "down" (palm side of the hand) stays clear
    return img


def pants():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Torso part of pants: waistband + seat, only the lower half
    for face in ("F", "B", "L", "R"):
        x, y, w, h = TORSO[face]
        rect(d, (x, y + 96, w, 32), PANTS)
        rect(d, (x, y + 96, w, 6), PANTS_FOLD)
    rect(d, TORSO["down"], PANTS)
    # Legs: baggy, stacked folds at the ankle, black shoes at the bottom
    for limb in (RIGHT_LIMB, LEFT_LIMB):
        rect(d, limb["up"], PANTS)
        rect(d, limb["down"], SHOE)
        for face, r in limb.items():
            if face in ("up", "down"):
                continue
            x, y, w, h = r
            rect(d, r, PANTS)
            # Knee crease and ankle stacking
            d.line([x + 8, y + 44, x + w - 14, y + 50], fill=PANTS_FOLD, width=3)
            for i, fy in enumerate((y + 78, y + 88, y + 97)):
                d.line([x + 4 + i * 3, fy, x + w - 6, fy + 4 - i * 2], fill=PANTS_FOLD, width=2)
            # Side cargo pocket on outer faces
            if (limb is RIGHT_LIMB and face == "R") or (limb is LEFT_LIMB and face == "L"):
                d.rectangle([x + 12, y + 54, x + w - 13, y + 76], outline=PANTS_FOLD, width=2)
            rect(d, (x, y + h - 14, w, 14), SHOE)
            rect(d, (x, y + h - 4, w, 4), (30, 30, 30, 255))  # sole
    return img


def face():
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for cx in (88, 168):
        # Lens fill, eye, frame
        d.ellipse([cx - 30, 98, cx + 30, 146], fill=LENS)
        d.ellipse([cx - 7, 112, cx + 7, 132], fill=EYE)
        d.ellipse([cx - 30, 98, cx + 30, 146], outline=FRAME, width=7)
        d.line([cx - 18, 106, cx - 8, 104], fill=(255, 255, 255, 140), width=3)  # glint
    d.line([118, 116, 138, 116], fill=FRAME, width=6)       # bridge
    d.line([58, 112, 36, 108], fill=FRAME, width=6)         # temples
    d.line([198, 112, 220, 108], fill=FRAME, width=6)
    d.line([62, 86, 108, 82], fill=EYE, width=6)            # flat, unbothered brows
    d.line([148, 82, 194, 86], fill=EYE, width=6)
    d.line([116, 186, 140, 186], fill=EYE, width=4)         # small neutral mouth
    return img


def crop(img, r):
    x, y, w, h = r
    return img.crop((x, y, x + w, y + h))


def preview(shirt_img, pants_img, face_img):
    """Front view: head 2x1x1 style block, torso 2x2, limbs 1x2 (template px scale)."""
    S = 2
    pv = Image.new("RGBA", (64 * 4 * S + 80, 64 * 6 * S + 120), (240, 240, 242, 255))
    ox, oy = 40, 40
    body = Image.new("RGBA", (256, 384), (0, 0, 0, 0))
    # skin base
    skin_torso = Image.new("RGBA", (128, 128), SKIN)
    skin_limb = Image.new("RGBA", (64, 128), SKIN)
    for (px, py, layer) in ((64, 128, skin_torso), (0, 128, skin_limb), (192, 128, skin_limb),
                            (64, 256, skin_limb), (128, 256, skin_limb)):
        body.alpha_composite(layer, (px, py))
    # head
    hd = ImageDraw.Draw(body)
    hd.rounded_rectangle([80, 16, 175, 127], radius=22, fill=SKIN)
    body.alpha_composite(face_img.resize((96, 96)), (80, 28))
    # messy black hair cap
    hd.rounded_rectangle([72, 0, 183, 52], radius=24, fill=(16, 16, 16, 255))
    for hx in range(74, 182, 14):
        hd.polygon([(hx, 40), (hx + 14, 40), (hx + 4, 68)], fill=(16, 16, 16, 255))
    # pants under shirt
    body.alpha_composite(crop(pants_img, TORSO["F"]), (64, 128))
    body.alpha_composite(crop(pants_img, RIGHT_LIMB["F"]), (64, 256))
    body.alpha_composite(crop(pants_img, LEFT_LIMB["F"]), (128, 256))
    body.alpha_composite(crop(shirt_img, TORSO["F"]), (64, 128))
    body.alpha_composite(crop(shirt_img, RIGHT_LIMB["F"]), (0, 128))
    body.alpha_composite(crop(shirt_img, LEFT_LIMB["F"]), (192, 128))
    pv.alpha_composite(body.resize((256 * S // 2 * 2, 384 * S // 2 * 2), Image.NEAREST), (ox, oy))
    return pv


if __name__ == "__main__":
    s, p, f = shirt(), pants(), face()
    s.save(os.path.join(OUT, "shirt_template.png"))
    p.save(os.path.join(OUT, "pants_template.png"))
    f.save(os.path.join(OUT, "face_decal.png"))
    preview(s, p, f).save(os.path.join(OUT, "preview_front.png"))
    print("wrote", OUT)
