"""Create six concrete TTF examples for the personalization workflow.

The examples are specimens, not simulated manufacturing results.  Each card
records the source font file and is suitable for comparing the browser/PDF
selection before a live Blender worker is available.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "font_examples_2026-10-23"
PDF_OUTPUT = ROOT / "output" / "pdf" / "font_examples_2026-10-23.pdf"
EXAMPLES = (
    ("Arial", Path(r"C:\Windows\Fonts\arial.ttf"), "ANA"),
    ("Times New Roman", Path(r"C:\Windows\Fonts\times.ttf"), "BRUNO"),
    ("Georgia", Path(r"C:\Windows\Fonts\georgia.ttf"), "CLARA"),
    ("Trebuchet MS", Path(r"C:\Windows\Fonts\trebuc.ttf"), "DAVI"),
    ("Courier New", Path(r"C:\Windows\Fonts\cour.ttf"), "ELISA"),
    ("Bahnschrift", Path(r"C:\Windows\Fonts\bahnschrift.ttf"), "FELIPE"),
)


def make_card(index: int, family: str, font_path: Path, text: str) -> dict:
    if not font_path.is_file():
        raise FileNotFoundError(f"Font unavailable: {font_path}")
    output = OUTPUT / f"{index:02d}_{family.lower().replace(' ', '_')}.png"
    image = Image.new("RGB", (1600, 900), "#f4fbfc")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((70, 70, 1530, 830), radius=48, fill="#ffffff", outline="#00bad2", width=6)
    draw.ellipse((146, 224, 678, 756), fill="#4d5759", outline="#00bad2", width=12)
    font = ImageFont.truetype(str(font_path), 136)
    bbox = draw.textbbox((0, 0), text, font=font)
    width, height = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((412 - width / 2, 490 - height / 2), text, font=font, fill="#ffffff")
    label = ImageFont.truetype(str(Path(r"C:\Windows\Fonts\arialbd.ttf")), 50)
    detail = ImageFont.truetype(str(Path(r"C:\Windows\Fonts\arial.ttf")), 30)
    draw.text((760, 250), f"Example {index}: {family}", font=label, fill="#4d5759")
    draw.text((760, 338), f'Native text: "{text}"', font=detail, fill="#00bad2")
    draw.text((760, 414), "TTF/OTF source retained in request package", font=detail, fill="#4d5759")
    draw.text((760, 466), "3D mode: ENGRAVE - depth: 0.35 mm", font=detail, fill="#4d5759")
    draw.text((760, 518), "Back-face rule: recess 0.20 mm", font=detail, fill="#4d5759")
    draw.text((760, 566), "Colour remains catalogue-derived", font=detail, fill="#4d5759")
    draw.text((760, 644), font_path.name, font=detail, fill="#7a8b8d")
    image.save(output, "PNG")
    return {"index": index, "family": family, "text": text, "font_path": str(font_path), "preview": str(output)}


def make_pdf(records: list[dict]) -> None:
    PDF_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(PDF_OUTPUT), pagesize=(842, 595))
    c.setTitle("Personalization font examples - 2026-10-23")
    for record in records:
        registered = f"FontExample{record['index']}"
        pdfmetrics.registerFont(TTFont(registered, record["font_path"]))
        c.setFillColor(HexColor("#4d5759")); c.setFont("Helvetica-Bold", 22)
        c.drawString(46, 544, f"Font example {record['index']}: {record['family']}")
        c.setFillColor(HexColor("#7a8b8d")); c.setFont("Helvetica", 10)
        c.drawString(46, 522, "Native personalization font specimen - prepared for browser, PDF, and Blender provenance checks")
        c.drawImage(ImageReader(record["preview"]), 46, 70, width=750, height=422, preserveAspectRatio=True, anchor="c")
        c.setFillColor(HexColor("#4d5759")); c.setFont(registered, 26)
        c.drawRightString(796, 35, record["text"])
        c.showPage()
    c.save()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    records = [make_card(index, family, font_path, text) for index, (family, font_path, text) in enumerate(EXAMPLES, start=1)]
    make_pdf(records)
    (OUTPUT / "font_examples_manifest.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"pdf": str(PDF_OUTPUT), "examples": records}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
