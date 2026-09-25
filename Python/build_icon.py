from PIL import Image, ImageDraw, ImageFilter
import math

def create_app_icon():
    size = 512
    # Create high-res RGBA image
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Outer Glow / Background Circle
    padding = 24
    bbox = [padding, padding, size - padding, size - padding]
    
    # Outer dark rounded square / disc
    corner_r = 110
    draw.rounded_rectangle(bbox, radius=corner_r, fill=(18, 20, 26, 255), outline=(0, 180, 216, 255), width=10)

    # Inner subtle glow circle
    inner_bbox = [padding + 16, padding + 16, size - padding - 16, size - padding - 16]
    draw.rounded_rectangle(inner_bbox, radius=corner_r - 10, fill=(24, 28, 38, 255), outline=(46, 196, 182, 180), width=4)

    # Accent speed stripes in background (subtle cyber lines)
    for y_offset in range(140, 380, 48):
        draw.line([(80, y_offset), (140, y_offset)], fill=(0, 180, 216, 60), width=4)
        draw.line([(372, y_offset), (432, y_offset)], fill=(0, 180, 216, 60), width=4)

    # Central Accelerated Download Arrow + Lightning Bolt
    # 1. Base download chevron / arrow
    arrow_pts = [
        (256, 380),  # Arrow tip bottom
        (150, 260),  # Left tip
        (205, 260),  # Left inner corner
        (205, 120),  # Top left
        (307, 120),  # Top right
        (307, 260),  # Right inner corner
        (362, 260),  # Right tip
    ]
    # Draw arrow shadow
    shadow_arrow = [(x, y + 8) for x, y in arrow_pts]
    draw.polygon(shadow_arrow, fill=(0, 0, 0, 120))
    # Draw arrow body
    draw.polygon(arrow_pts, fill=(0, 150, 199, 255), outline=(0, 180, 216, 255))

    # 2. Electric Lightning Bolt overlay (glowing yellow/cyan)
    bolt_pts = [
        (265, 100),
        (220, 240),
        (265, 240),
        (235, 390),
        (305, 220),
        (260, 220),
        (285, 100),
    ]
    # Bolt glow shadow
    bolt_shadow = [(x + 2, y + 4) for x, y in bolt_pts]
    draw.polygon(bolt_shadow, fill=(0, 0, 0, 160))
    # Bolt fill
    draw.polygon(bolt_pts, fill=(255, 214, 10, 255), outline=(255, 255, 255, 230))

    # Bottom speed base line / tray
    tray_pts = [
        (140, 415),
        (140, 440),
        (372, 440),
        (372, 415),
    ]
    draw.line(tray_pts[:2], fill=(46, 196, 182, 255), width=12)
    draw.line(tray_pts[1:3], fill=(46, 196, 182, 255), width=12)
    draw.line(tray_pts[2:], fill=(46, 196, 182, 255), width=12)

    # Save PNG versions
    png_path = "Python/gui/assets/app_icon.png"
    img.save(png_path, "PNG")
    print(f"Saved PNG to {png_path}")

    # Save multi-size ICO
    ico_path = "Python/gui/assets/app_icon.ico"
    icon_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(ico_path, format="ICO", sizes=icon_sizes)
    print(f"Saved multi-resolution ICO to {ico_path}")

create_app_icon()