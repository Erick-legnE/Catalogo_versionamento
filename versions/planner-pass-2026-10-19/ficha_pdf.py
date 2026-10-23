"""Ficha Técnica Brasil Botões - layout reconstructed from real Fichas.

This template follows the 15 user-supplied reference PDFs (A4):
- Ficha Técnica | Personalização a Laser title and date
- left specification rows / right gray personalization panel + teal stripe
- Simulação da Aplicação with small + large previews
- original company logo/footer tagline

No geometry/perspective/dimensions are fabricated. The representative's preview
is explicitly labeled as an illustrative 2D simulation. ReportLab produces a
one-page PDF directly, without requiring Chrome/Edge on the server.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from io import BytesIO
import os
import re

from PIL import Image, ImageOps, ImageFilter, ImageDraw
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, Color
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from nexa_fonts import ensure_nexa_fonts

PAGE_W, PAGE_H = A4
GRAY = HexColor('#4C585A')
TEAL = HexColor('#00B8C9')
PANEL = HexColor('#D6D9D9')
WHITE = HexColor('#FFFFFF')

PROJECT = Path(__file__).resolve().parent
OFFICIAL_LOGO = PROJECT/'assets'/'logo_brasil_botoes_oficial.png'


def _fonts():
    """Use the real Nexa family supplied by the user (Regular, Bold, Light)."""
    return ensure_nexa_fonts(PROJECT)


def _text(value):
    text = str(value).strip() if value is not None else ''
    return '' if text.upper() in ('NONE','NULL','AUTO','N/A','NAN') else text


def _has_value(value):
    return value is not None and str(value).strip() not in ('', 'NONE', 'NULL', 'AUTO', 'N/A', 'NAN')


def _measurement(value):
    """Display a numeric production measurement consistently in millimetres."""
    value = _text(value)
    if not value:
        return ''
    return value if re.search(r'\bmm\b', value, re.I) else f'{value} mm'


def _item(meta, *names):
    for name in names:
        if isinstance(meta,dict):
            v = _text(meta.get(name))
            if v:
                return v
    return ''


def _top(top:float):
    return PAGE_H - top


def _fit_font(text, font, size, width, minimum=7.1):
    if not text: return size
    while size>minimum and pdfmetrics.stringWidth(text,font,size)>width:
        size-=0.2
    return max(minimum, size)


def _draw_field(c, left, baseline_top, label, val, reg, bold, limit=247):
    size=10.6
    label_full=label+':'
    c.setFont(bold,size)
    c.setFillColor(GRAY)
    c.drawString(left,_top(baseline_top),label_full)
    value_x=left+pdfmetrics.stringWidth(label_full,bold,size)+4
    if val:
        avail=max(36,limit-value_x)
        value_size=_fit_font(val,reg,10.65,avail,7.2)
        # Extra-long customer strings should never overprint the gray panel.
        if pdfmetrics.stringWidth(val,reg,value_size)>avail:
            while val and pdfmetrics.stringWidth(val+'...',reg,value_size)>avail:
                val=val[:-1]
            val=val+'...' if val else ''
        c.setFillColor(TEAL)
        c.setFont(reg,value_size)
        c.drawString(value_x,_top(baseline_top),val)


def _wrap(text:str,font:str,size:float,max_width:float):
    text=str(text)
    pieces=[]
    for para in text.splitlines() or ['']:
        current=''
        for word in para.split():
            test=(current+' '+word).strip()
            if pdfmetrics.stringWidth(test,font,size)<=max_width:
                current=test
            else:
                if current: pieces.append(current)
                if pdfmetrics.stringWidth(word,font,size)>max_width:
                    part=''
                    for char in word:
                        if part and pdfmetrics.stringWidth(part+char,font,size)>max_width:
                            pieces.append(part);part=char
                        else: part+=char
                    current=part
                else: current=word
        if current: pieces.append(current)
    return pieces or ['']


def _detail_label_value(c, y, label, val, reg, bold, max_lines=3):
    """Bulleted line with dark label and cyan value, like the reference sheets."""
    size=10.2
    c.setFillColor(GRAY); c.setFont(reg,size)
    c.drawString(289,_top(y),'-')
    label_x=303
    c.setFont(reg,size)
    c.drawString(label_x,_top(y),label)
    val_x=label_x+pdfmetrics.stringWidth(label,reg,size)+4
    remaining=574-val_x
    first=_wrap(val,reg,size,remaining)
    # First line may wrap narrower than subsequent lines.
    words=val.split()
    built=['']
    first_avail=remaining
    for word in words:
        i=len(built)-1
        target=(built[i]+' '+word).strip()
        width=first_avail if i==0 else 269
        if pdfmetrics.stringWidth(target,reg,size)<=width:
            built[i]=target
        else:
            built.append(word)
    all_lines=[line for line in built if line]
    if not all_lines:all_lines=['']
    visible=all_lines[:max_lines]
    if len(all_lines)>max_lines:
        visible[-1]=visible[-1].rstrip(' .,')+'...'
        while pdfmetrics.stringWidth(visible[-1],reg,size)>269 and len(visible[-1])>4:
            visible[-1]=visible[-1][:-4]+'...'
    c.setFillColor(TEAL); c.setFont(reg,size)
    for i,txt in enumerate(visible):
        c.drawString(val_x if i==0 else label_x,_top(y+15*i),txt)
    return y+15*len(visible)+8


def _normalize_preview(path, is_button):
    with Image.open(path) as raw:
        raw.load()
        im=raw.convert('RGBA')
    if is_button:
        # The frontend canvas draws the circular button at ~74% of width.
        w,h=im.size; rad=min(w,h)*0.37
        cx=w/2;cy=h/2
        rect=(round(cx-rad),round(cy-rad),round(cx+rad),round(cy+rad))
        im=im.crop(rect)
        # The preview canvas has a full square background; remove it outside
        # the physical circle so it can float on clean white, like the samples.
        side=min(im.size)
        im=ImageOps.fit(im,(side,side),method=Image.Resampling.LANCZOS)
        mask=Image.new('L',(side,side),0)
        dr=ImageDraw.Draw(mask)
        dr.ellipse((1,1,side-2,side-2),fill=255)
        im.putalpha(mask)
    im.thumbnail((900,900), Image.Resampling.LANCZOS)
    return im


def _shadow(c,cx,cy,width,height):
    # Soft concentric elliptical shadow rather than pretending this is 3D.
    c.saveState()
    for i in reversed(range(15)):
        a=(i+1)/15
        c.setFillColor(Color(.20,.20,.20,alpha=.013*(1-a*.7)))
        c.ellipse(cx-width*(.75+a*.25)/2, cy-height*(.75+a*.25)/2,
                  cx+width*(.75+a*.25)/2, cy+height*(.75+a*.25)/2,fill=1,stroke=0)
    c.restoreState()


def _draw_image(c, img, x, y, max_w, max_h):
    w,h=img.size
    if w<=0 or h<=0:return
    mult=min(max_w/w,max_h/h)
    w1,h1=w*mult,h*mult
    c.saveState()
    c.setFillAlpha(1)
    c.drawImage(ImageReader(img),x+(max_w-w1)/2,y+(max_h-h1)/2,
                width=w1,height=h1,mask='auto',preserveAspectRatio=True)
    c.restoreState()


def _logo(c,logo_path):
    logo=OFFICIAL_LOGO if OFFICIAL_LOGO.is_file() else Path(logo_path)
    if not logo.is_file():return
    with Image.open(logo) as original:
        im=original.convert('RGBA')
        bb=im.getchannel('A').getbbox()
        if bb:im=im.crop(bb)
        im.thumbnail((900,360),Image.Resampling.LANCZOS)
    _draw_image(c,im,43,_top(806),126,43)


def render_ficha(path:Path, metadata:dict, preview_path:Path,
                 art_paths:list[Path], logo_path:Path, request_id:str):
    """Generate a single-page Ficha PDF, preserving the existing server.py API."""
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    item=metadata.get('item') or {}
    ficha=metadata.get('ficha') or {}
    personalization=metadata.get('personalization') or {}
    assets=personalization.get('assets') or []
    is_button=item.get('type')=='button'
    reg,bold,light=_fonts()

    c=canvas.Canvas(str(path),pagesize=A4,pageCompression=1)
    c.setTitle('Ficha Técnica | Personalização a Laser')
    c.setAuthor('Brasil Botões')

    # Header: exact Nexa glyph widths, no artificial horizontal scaling.
    # Colored segments follow the company reference PDFs.
    baseline=69
    headline_segments=[
        ('Ficha ',bold,GRAY),
        ('Técnica',bold,TEAL),
        (' | Personalização a Laser',light,GRAY),
    ]
    headline_start=41
    nominal_size=27.6
    nominal_width=sum(pdfmetrics.stringWidth(text,font,nominal_size)
                      for text,font,color in headline_segments)
    title_size=min(nominal_size, (PAGE_W-77)*nominal_size/max(nominal_width,1))
    x=headline_start
    for text,font,color in headline_segments:
        c.setFont(font,title_size)
        c.setFillColor(color)
        c.drawString(x,_top(baseline),text)
        x+=pdfmetrics.stringWidth(text,font,title_size)

    now=datetime.now()
    date_text=now.strftime('%d/%m/%y')+'.'
    c.setFont(reg,11.0);c.setFillColor(GRAY)
    left_date=434
    c.drawString(left_date,_top(88),'Data:')
    c.setFillColor(TEAL)
    c.drawString(left_date+31,_top(88),date_text)

    details={
        'Cliente':_item(ficha,'cliente'),
        'Representante':_item(ficha,'representante'),
        'Pedido nº.':'',
        'Referência':_item(item,'reference') if is_button else 'Outro item',
        'Código Personalizado':'',  # Assigned later; do not invent a P code.
        'Tamanho':((_item(item,'size_tam')+'”') if _item(item,'size_tam') and is_button else ''),
        'Diâmetro':_measurement(_item(item,'diametro_mm','diameter_verified_mm','size_tam')),
        'Espessura':_measurement(_item(item,'espessura_final_mm','espessura_mm','thickness_verified_mm')),
        'Material':_item(item,'material'),
        'Cor':_item(item,'color') if is_button else _item(item,'color'),
        'Acabamento':_item(item,'acabamento'),
        'Furação':_item(item,'furacao') or (
            f"{_item(item,'num_furos')}F" if _item(item,'num_furos') else ''
        ),
        'Fundo':_item(item,'fundo'),
        'Pastilha':(
            f"{_item(item,'pastilha_mm')} mm" if _item(item,'pastilha_mm') else ''
        ),
    }
    # Do not add 'mm' to unverified numeric input (the representative supplies TAM).
    for n,(label,v) in enumerate(details.items()):
        _draw_field(c,44,130+14.8*n,label,v,reg,bold)

    # Gray personalization panel with teal stripe, same size/proportions.
    c.setFillColor(TEAL)
    c.rect(270,_top(289),7,171,fill=1,stroke=0)
    c.setFillColor(PANEL)
    c.rect(281,_top(289),296,171,fill=1,stroke=0)
    c.setFillColor(GRAY)
    c.setFont(bold,11.6)
    c.drawString(290,_top(139),'Detalhamento da personalização:')

    y=163
    if assets:
        if len(assets)==1:
            art_name=_item(assets[0],'asset_name') or 'Arte enviada'
            transforms=[]
            if _has_value(assets[0].get('scale')):
                transforms.append(f"escala {_item(assets[0], 'scale')}x")
            if _has_value(assets[0].get('rotation')) or _has_value(assets[0].get('rotation_deg')):
                transforms.append(f"rotação {_item(assets[0], 'rotation', 'rotation_deg')}°")
            if _has_value(assets[0].get('opacity')):
                transforms.append(f"opacidade {_item(assets[0], 'opacity')}%")
            if transforms:
                art_name += ' · ' + ' · '.join(transforms)
            y=_detail_label_value(c,y,'Arte:',art_name,reg,bold,max_lines=2)
        else:
            y=_detail_label_value(c,y,'Arte:',f'{len(assets)} imagens enviadas',reg,bold,max_lines=2)
    else:
        y=_detail_label_value(c,y,'Arte:','Não informada',reg,bold,max_lines=2)

    notes=_item(ficha,'observacoes')
    if not is_button and _item(item,'description'):
        prefix='Item: '+_item(item,'description')
        notes=(prefix+'; '+notes).strip('; ') if notes else prefix
    if notes and y<=245:
        y=_detail_label_value(c,y,'Obs.:',notes,reg,bold,max_lines=max(1,min(3,int((269-y)/15))))
    elif not notes:
        y=_detail_label_value(c,y,'Aplicação:','Conforme simulação.',reg,bold)

    # Image application: faithful large white area, small + large simulations.
    c.setFont(bold,11.4);c.setFillColor(GRAY)
    c.drawString(44,_top(343),'Simulação da Aplicação:')

    im=_normalize_preview(Path(preview_path),is_button)
    # Small left preview, larger right preview - same centers as reference.
    if is_button:
        small_box=(135,_top(654),73,75)
        large_box=(252,_top(654),260,267)
    else:
        small_box=(135,_top(658),73,78)
        large_box=(252,_top(657),260,267)

    _shadow(c,171,_top(654),76,11)
    _shadow(c,381,_top(649),260,34)
    _draw_image(c,im,*small_box)
    _draw_image(c,im,*large_box)

    c.setFillColor(GRAY);c.setFont(bold,10.5)
    c.drawCentredString(171,_top(676),'Prévia Reduzida')
    c.drawCentredString(382,_top(676),'Simulação Ampliada')

    # Footer: supplied logo and original phrase at same A4 coordinates.
    _logo(c,logo_path)
    c.setFillColor(GRAY);c.setFont(bold,12.2)
    c.drawRightString(551,_top(786),'Transformamos o')
    line_parts=[('essencial',TEAL),(' no seu ',GRAY),('diferencial.',TEAL)]
    total=sum(pdfmetrics.stringWidth(t,bold,12.3) for t,_ in line_parts)
    x=551-total
    for text,color in line_parts:
        c.setFillColor(color)
        c.drawString(x,_top(803),text)
        x+=pdfmetrics.stringWidth(text,bold,12.3)

    # Lightweight footnote (kept unobtrusive, above the footer area).
    c.setFillColor(HexColor('#859092'))
    c.setFont(reg,6.8)
    c.drawCentredString(PAGE_W/2,_top(731),
       'Simulação 2D ilustrativa. Dimensões e aparência final sujeitas à validação técnica.')

    c.showPage()
    c.save()
    if not path.is_file() or path.stat().st_size < 1500:
        raise RuntimeError('Falha ao gerar a Ficha Técnica PDF.')
    return path
