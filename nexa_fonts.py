"""Register the user's licensed Nexa OTF fonts for ReportLab, in memory.

Nexa fonts are NOT bundled with this project. Put your existing Nexa ZIP next
 to server.py or set NEXA_FONT_ZIP to its location. The fonts never need to be
 extracted to disk, and the converted font bytes stay inside the Python process.
"""
from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path
from threading import Lock
import os
import zipfile

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont as RLTTFont
from fontTools.ttLib import TTFont as FontToolsTTFont
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen

_REQUIRED = {
    'NexaRegular': 'Nexa-Regular.otf',
    'NexaBold': 'Nexa Bold.otf',
    'NexaLight': 'Nexa-Light.otf',
}
FONT_NAMES = tuple(_REQUIRED)
_LOCK = Lock()


def _find_archive(project_dir: Path) -> Path:
    env = os.environ.get('NEXA_FONT_ZIP', '').strip().strip('"')
    if env:
        archive = Path(env).expanduser()
        if not archive.is_file():
            raise RuntimeError(f'NEXA_FONT_ZIP apontou para arquivo inexistente: {archive}')
        return archive
    for name in ('Nexa.zip', 'nexa.zip', 'zipbomb.zip', 'FONTES_NEXA.zip'):
        path = project_dir / name
        if path.is_file():
            return path
    raise RuntimeError(
        'Fontes Nexa não encontradas. Copie seu ZIP original das fontes Nexa '
        '(zipbomb.zip ou Nexa.zip) para a mesma pasta de server.py, '
        'ou configure NEXA_FONT_ZIP. O programa não inclui arquivos de fontes.'
    )


def _convert_cff_to_truetype(data: bytes, style: str) -> bytes:
    font = FontToolsTTFont(BytesIO(data), lazy=False)
    if 'glyf' in font and 'CFF ' not in font:
        return data
    if 'CFF ' not in font:
        raise RuntimeError(f'Formato de fonte não reconhecido: {style}')
    units = font['head'].unitsPerEm
    builder = FontBuilder(units, isTTF=True)
    glyph_order = font.getGlyphOrder()
    builder.setupGlyphOrder(glyph_order)
    builder.setupCharacterMap(font.getBestCmap() or {})
    glyph_set = font.getGlyphSet()
    glyphs = {}
    for glyph_name in glyph_order:
        pen = TTGlyphPen(glyph_set)
        pen_quadratic = Cu2QuPen(pen, max_err=1.0, reverse_direction=True)
        glyph_set[glyph_name].draw(pen_quadratic)
        glyphs[glyph_name] = pen.glyph()
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics({g:font['hmtx'].metrics[g] for g in glyph_order})
    hhea = font['hhea']
    builder.setupHorizontalHeader(ascent=hhea.ascent,descent=hhea.descent,lineGap=hhea.lineGap)
    builder.setupNameTable({
        'familyName':'Nexa-local','styleName':style,
        'uniqueFontIdentifier':'Nexa-local '+style,
        'fullName':'Nexa-local '+style,
        'psName':'Nexa-local-'+style.replace(' ','')
    })
    os2 = font['OS/2']
    builder.setupOS2(
        sTypoAscender=os2.sTypoAscender,
        sTypoDescender=os2.sTypoDescender,
        sTypoLineGap=os2.sTypoLineGap,
        usWinAscent=os2.usWinAscent,
        usWinDescent=os2.usWinDescent
    )
    builder.setupPost()
    builder.setupMaxp()
    out = BytesIO()
    builder.save(out)
    font.close()
    return out.getvalue()


@lru_cache(maxsize=4)
def _load_fonts(archive_path: str):
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(names)>80:
            raise RuntimeError('Arquivo ZIP de fontes tem entradas demais.')
        for name in _REQUIRED.values():
            if name not in names:
                raise RuntimeError(f'Fonte obrigatória {name} não está no ZIP.')
            info=archive.getinfo(name)
            if info.file_size>2_000_000 or info.compress_size<1:
                raise RuntimeError(f'Tamanho suspeito para a fonte {name}.')
        # Read only these 3 named files, with explicit limits; never extract archive.
        blobs={}
        for style,name in _REQUIRED.items():
            with archive.open(name) as stream:
                content=stream.read(2_000_001)
            if len(content)>2_000_000:
                raise RuntimeError(f'Fonte {name} excedeu limite de segurança.')
            blobs[style]=_convert_cff_to_truetype(content,style)
        return blobs


def ensure_nexa_fonts(project_dir: Path) -> tuple[str,str,str]:
    """Returns registered (Regular,Bold,Light) ReportLab face names."""
    if all(name in pdfmetrics.getRegisteredFontNames() for name in FONT_NAMES):
        return FONT_NAMES
    with _LOCK:
        if all(name in pdfmetrics.getRegisteredFontNames() for name in FONT_NAMES):
            return FONT_NAMES
        archive=_find_archive(Path(project_dir))
        blobs=_load_fonts(str(archive.resolve()))
        for name,blob in blobs.items():
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(RLTTFont(name,BytesIO(blob)))
    return FONT_NAMES
