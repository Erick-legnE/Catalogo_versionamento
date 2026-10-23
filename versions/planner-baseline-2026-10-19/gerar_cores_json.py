#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Atualiza data/cores_catalogo.json a partir de Cores1.xlsx.

Uso:
    py gerar_cores_json.py "Cores1.xlsx"

Não altera o Excel e não exige pacotes além do Python padrão.
Esta versão lê só a aba COD, registra estimativas ilustrativas e mantém
cores_overrides.json (validações manuais) intacto.
"""
from pathlib import Path
from xml.etree import ElementTree as ET
from collections import Counter
import argparse, zipfile, json, re, unicodedata, collections

NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
DOC_REL='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG_REL='http://schemas.openxmlformats.org/package/2006/relationships'

def iter_cod_rows(xlsx):
    with zipfile.ZipFile(xlsx) as z:
        wb=ET.fromstring(z.read('xl/workbook.xml'))
        sheets=wb.find(f'{{{NS}}}sheets')
        entry=next((s for s in sheets if s.attrib.get('name')=='COD'),None)
        if entry is None: raise ValueError('Aba COD não encontrada no XLSX')
        rid=entry.attrib[f'{{{DOC_REL}}}id']
        rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        target=next((r.attrib['Target'] for r in rels if r.attrib.get('Id')==rid),None)
        if not target: raise ValueError('COD sheet XML não encontrado')
        path=target.lstrip('/') if target.startswith('/') else 'xl/'+target.lstrip('/')
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            tree=ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in tree.findall(f'{{{NS}}}si'):
                shared.append(''.join(t.text or '' for t in si.iter(f'{{{NS}}}t')))
        root=ET.fromstring(z.read(path))
        for row in root.iter(f'{{{NS}}}row'):
            values=['']*4
            for cell in row.findall(f'{{{NS}}}c'):
                column=re.match('[A-Z]+',cell.attrib.get('r',''))
                if not column:continue
                letters=column.group(0)
                idx=0
                for letter in letters:idx=idx*26+ord(letter)-64
                idx-=1
                if idx not in range(4): continue
                if cell.attrib.get('t')=='inlineStr':
                    inline=cell.find(f'{{{NS}}}is')
                    val=''.join(n.text or '' for n in inline.iter(f'{{{NS}}}t')) if inline is not None else ''
                else:
                    node=cell.find(f'{{{NS}}}v')
                    val=node.text or '' if node is not None else ''
                    if cell.attrib.get('t')=='s': val=shared[int(val)]
                values[idx]=val
            if values[0] and re.fullmatch(r'C\d{1,6}',str(values[0]).upper().strip()):
                yield dict(codigo=str(values[0]).upper().strip(),descricao=values[1] or '',observacao=values[2] or '',observacao_extra=values[3] or '')

PALETTE=[
 ('PRETO','#282c33'),('BRANCO','#f2f0e8'),('OFF WHITE','#ece8d9'),('OFFWHITE','#ece8d9'),
 ('MARFIM','#e8d9ae'),('LEITOSO','#ddd9c8'),('BEGE','#c9aa7b'),('CREME','#dfcdb0'),
 ('NATURAL','#b5a78f'),('CARAMELO','#a8753d'),('CAFE','#5c4036'),('MARROM','#774830'),
 ('CHOCOLATE','#4d2c25'),('DOURADO','#b9944c'),('OURO VELHO','#9c7444'),
 ('PRATA','#a4a6a8'),('ALUMINIO','#a7aeb1'),('CINZA ESCURO','#595f69'),('CINZA CLARO','#c6c9ce'),('CINZA','#898b90'),
 ('ROSA FLUOR','#ff4fa7'),('ROSA','#d982a4'),('PINK','#ed4b9e'),('MAGENTA','#cd3289'),
 ('ROXO FLUOR','#a54df1'),('LILAS','#b497d6'),('VIOLETA','#8358b5'),('ROXO','#663d8f'),
 ('AZUL MARINHO','#233960'),('MARINHO','#233960'),('AZUL CELESTE','#79bce7'),('AZUL CLARO','#8fb9da'),('AZUL ESCURO','#254772'),('AZUL ROYAL','#3562ba'),('AZUL','#527ba9'),
 ('VERDE MILITAR','#627047'),('VERDE MUSGO','#637547'),('VERDE BANDEIRA','#238c51'),('VERDE FLUOR','#79e54b'),('VERDE CLARO','#abd68c'),('VERDE ESCURO','#335b48'),('VERDE','#65976b'),
 ('AMARELO FLUOR','#f5ef34'),('AMARELADO','#e5c674'),('AMARELO','#e9c64b'),
 ('LARANJA FLUOR','#fe852e'),('LARANJA','#e98b3b'),('CORAL','#ee8273'),
 ('VERMELHO FLUOR','#fc4742'),('VERMELHO','#ac4146'),('VINHO','#753846'),('BORDO','#7b3541'),
 ('PEROLADO','#e5e0d8'),('MADREPEROLA','#e2d9ce'),('OSSO','#dbccb2'),
]
# Longest phrase first and word boundary search: keep foreground color extraction conservative.
PALETTE=sorted(PALETTE,key=lambda a:-len(a[0]))
STOPWORDS={'COR','PANTONE','PT','TAM','CM','MM'}

def normalize(s):
 s=unicodedata.normalize('NFKD',str(s or '')).upper()
 s=''.join(c for c in s if not unicodedata.combining(c))
 return re.sub(r'\s+',' ',s)

def names_in(text):
 found=[]; spans=[]
 for name,hexc in PALETTE:
  for m in re.finditer(r'(?<![A-Z0-9])'+re.escape(name)+r'(?![A-Z0-9])',text):
   if any(max(m.start(),a)<min(m.end(),b) for a,b in spans):continue
   found.append((m.start(),name,hexc)); spans.append((m.start(),m.end()))
 found.sort()
 return [dict(name=n,hex=h) for _,n,h in found]

def classify(row):
 desc=normalize(row['descricao']); obs=normalize(row['observacao']); extra=normalize(row['observacao_extra'])
 # Descriptions usually authoritative; comments support but sometimes refer to different materials.
 text=' '.join((desc,obs,extra))
 found=names_in(text)
 vals=[]; seen=set()
 for n in found:
  if n['hex'] not in seen:
   vals.append(n);seen.add(n['hex'])
 if len(vals)>4:vals=vals[:4]
 kind='unknown'; effects=[]; method='sem cor reconhecível'; confidence='unknown'
 borda='BORDA' in text
 side='FUNDO' in text or 'MEIO' in text
 multi=re.search(r'\b(DUAS|DOIS|TRES|03|02|2|3)\s*CAMADAS?\b',text) is not None or (len(vals)>=2 and bool(re.search(r'[A-Z]{3,}\s*/\s*[A-Z]{3,}',desc)))
 percent_mix=bool(re.search(r'\d+(?:[.,]\d+)?\s*%',text) and re.search(r'[/+]',desc) and len(vals)>=2)
 patterns={'tortoise':('TARTARUG','CASCO'), 'wood':('MADEIRA','MADERA'), 'marble':('MESCLAD','RAJAD','MARMORIZ','MARMORE','ONDULAD','MANCHAD','GOTAS','IMITACAO DE OSSO'), 'gradient':('DEGRADE','DEGRAD'), 'glitter':('GLITTER','PURPURINA','BRILHO METALIZADO')}
 matched=[k for k,keys in patterns.items() if any(q in text for q in keys)]
 if 'GLITTER' in text or 'FURTA COR' in text:effects.append('glitter' if 'GLITTER' in text else 'iridescent')
 if 'FLUOR' in text or 'NEON' in text:effects.append('neon')
 if 'TRANSP' in text:effects.append('translucent')
 if 'PEROLAD' in text or 'MADREPEROLA' in text:effects.append('pearl')
 if 'tortoise' in matched:
  kind='tortoise';method='textura tartaruga ilustrativa';confidence='estimated'
  if not vals:vals=[dict(name='âmbar estimado',hex='#a16d35'),dict(name='marrom escuro estimado',hex='#322923')]
 elif 'wood' in matched:
  kind='wood';method='textura madeira ilustrativa';confidence='estimated'
  if not vals:vals=[dict(name='madeira estimada',hex='#ac7a46'),dict(name='veios estimados',hex='#5a3f2a')]
 elif 'marble' in matched:
  kind='marble';method='mesclado/rajado ilustrativo';confidence='estimated' if vals else 'low'
  if len(vals)==1:vals.append(dict(name='variação aproximada',hex='#e8dac4' if vals[0]['hex']!='#f2f0e8' else '#555259'))
 elif 'gradient' in matched:
  kind='gradient';method='degradê aproximado';confidence='estimated' if vals else 'low'
 elif percent_mix:
  kind='layered';method='mistura percentual ilustrativa';confidence='estimated'
 elif borda and side:
  kind='border_core';method='borda/fundo interpretados do texto';confidence='estimated' if len(vals)>=2 else 'low'
 elif multi or (len(vals)>=2 and (' + ' in desc or '+' in obs)):
  kind='layered';method='camadas ilustrativas';confidence='estimated' if len(vals)>=2 else 'low'
 elif 'TRANSP' in text and not vals:
  kind='transparent';method='transparência estilizada';confidence='estimated'
 elif vals:
  kind='solid';method='palavra de cor no cadastro';confidence='estimated'
 else:
  kind='unknown';method='descrição insuficiente para inferir cor';confidence='unknown'
 # if special mixes are mentioned but have no palette data, do not fabricate exact colors
 if not vals and kind in ('layered','border_core','gradient'):
  kind='unknown';confidence='unknown';method='camadas descritas sem cores identificáveis'
 # Isolate explicit BORDA and FUNDO when available rather than using accidental occurrence order.
 if kind=='border_core':
  bm=re.search(r'BORDA\s+(.*?)(?:\s*/\s*|\s+FUNDO\b|\s+MEIO\b|$)',text)
  fm=re.search(r'FUNDO\s+(.*?)(?:\s*/\s*|\s+BORDA\b|\s+MEIO\b|$)',text)
  if bm and fm:
   a=names_in(bm.group(1)); b=names_in(fm.group(1))
   if a and b: vals=[a[0],b[0]]+ [p for p in vals if p['hex'] not in (a[0]['hex'],b[0]['hex'])]
 return {'kind':kind,'palette':[v['hex'] for v in vals[:4]],'color_names':[v['name'] for v in vals[:4]],'effects':effects,'confidence':confidence,'method':method}

def main():
    parser=argparse.ArgumentParser(description='Regenera as prévias ilustrativas de Cores1.xlsx')
    parser.add_argument('xlsx',type=Path)
    args=parser.parse_args()
    if not args.xlsx.is_file(): parser.error('XLSX não encontrado')
    dst=Path(__file__).resolve().parent/'docs'/'data'
    dst.mkdir(parents=True,exist_ok=True)
    entries={}; duplicates=[]
    for row in iter_cod_rows(args.xlsx):
        code=row['codigo']
        row['preview']=classify(row)
        if code in entries:
            duplicates.append({'codigo':code,'duplicated_description':row['descricao'],'first_description':entries[code]['descricao']})
            continue
        entries[code]=row
    stats={'codes':len(entries),'types':dict(Counter(v['preview']['kind'] for v in entries.values())),
           'confidence':dict(Counter(v['preview']['confidence'] for v in entries.values())),
           'duplicates':len(duplicates),'source_sheet':'COD','source_file':args.xlsx.name}
    full={'version':1,'source':args.xlsx.name+' / COD',
          'notice':'Prévia ilustrativa estimada pelas descrições; não é RGB real. Fotos existentes têm prioridade.',
          'stats':stats,'colors':entries}
    (dst/'cores_catalogo.json').write_text(json.dumps(full,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    (dst/'cores_review.json').write_text(json.dumps({'duplicate_codes':duplicates,
        'needs_review':[{'codigo':k,'descricao':v['descricao'],'observacao':v['observacao']} for k,v in entries.items()
                         if v['preview']['confidence'] in ('unknown','low')]},ensure_ascii=False,indent=2),encoding='utf-8')
    print('JSON gerado:',dst/'cores_catalogo.json')
    print('Cores:',len(entries),'· Revisar:',sum(v['preview']['confidence'] in ('unknown','low') for v in entries.values()))
    print('Overrides manuais NÃO foram alterados.')

if __name__=='__main__':main()
