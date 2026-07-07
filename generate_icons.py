"""
Generates properly-sized PWA icons from the existing Z Padel logo.
Run this from your project root: python generate_icons.py
"""
from PIL import Image
import os

SOURCE = r"app\static\images\logo\Zpadel.jpeg"
OUT_DIR = r"app\static\images\icons"

os.makedirs(OUT_DIR, exist_ok=True)

sizes = [192, 512]

img = Image.open(SOURCE).convert("RGBA")

for size in sizes:
    resized = img.resize((size, size), Image.LANCZOS)
    out_path = os.path.join(OUT_DIR, f"icon-{size}.png")
    resized.save(out_path, "PNG")
    print(f"Saved {out_path} ({size}x{size})")

# Maskable version: pad the logo so it sits within the "safe zone"
# Maskable icons need ~20% padding since OS may crop to a circle/rounded shape
maskable_size = 512
padding_ratio = 0.2
inner_size = int(maskable_size * (1 - padding_ratio))
canvas = Image.new("RGBA", (maskable_size, maskable_size), (10, 47, 107, 255))  # brand-blue-deep bg
logo_resized = img.resize((inner_size, inner_size), Image.LANCZOS)
offset = ((maskable_size - inner_size) // 2, (maskable_size - inner_size) // 2)
canvas.paste(logo_resized, offset, logo_resized)
maskable_path = os.path.join(OUT_DIR, "icon-512-maskable.png")
canvas.save(maskable_path, "PNG")
print(f"Saved {maskable_path} (512x512 maskable)")

print("\nDone. Update manifest.json icon paths to /static/images/icons/")