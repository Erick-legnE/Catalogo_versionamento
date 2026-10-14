#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Atualiza APENAS os índices de imagens de docs/produtos.json.

Não exige Excel e nunca remove fotos. Não altera outros campos do produto.

Uso:
    py atualizar_imagens_catalogo.py             # simular e diagnosticar
    py atualizar_imagens_catalogo.py --write     # gravar com backup
    py atualizar_imagens_catalogo.py --import-root --write  # copiar de imagens/ raiz

Coloque este script ao lado de server.py, na raiz do projeto.
As imagens publicadas ficam em docs/imagens/, inclusive pastilhas/.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

EXT = {'.jpg','.jpeg','.png','.webp'}
VARIANT_ORDER = {'':0, 'frente':1, 'front':1, 'lat':2, 'lado':2, 'verso':3, 'back':3, 'detalhe':4}


def color_code(raw: object) -> str:
    value = str(raw or '').strip().upper().replace(' ', '')
    if not value: return ''
    if value.startswith('C'): value = value[1:]
    if value.isdigit():
        n = int(value)
        return f'C{n:03}' if n < 1000 else f'C{n}'
    return ''


def priority(p: str, base: str = ''):
    stem = Path(p).stem.casefold()
    if base and stem == base: return (0, p.casefold())
    suffix = stem.rsplit('_',1)[-1]
    return (VARIANT_ORDER.get(suffix, 5), p.casefold())


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def is_prefix(stem: str, base: str) -> bool:
    return stem == base or stem.startswith(base+'_')


def scan_docs(folder: Path):
    found = []
    if folder.exists():
        for p in folder.rglob('*'):
            if p.is_file() and p.suffix.lower() in EXT:
                found.append(p)
    return sorted(found, key=lambda p:str(p).casefold())


def scan_pastilha_json(json_path: Path, media_dir: Path):
    out=defaultdict(list)
    if not json_path.is_file(): return out
    source=read_json(json_path)
    if not isinstance(source,list): return out
    for item in source:
        if not isinstance(item,dict): continue
        code=color_code(item.get('cor_codigo'))
        if not code: continue
        imgs=item.get('imagens') or []
        if isinstance(imgs,str): imgs=[imgs]
        for filename in imgs:
            value=str(filename).replace('\\','/').strip().removeprefix('./')
            if value.startswith('docs/'): value=value[5:]
            if value.startswith('imagens/'): value=value[8:]
            candidate=(media_dir/value).resolve()
            if candidate.is_file() and candidate.is_relative_to(media_dir.resolve()):
                rel=candidate.relative_to(media_dir.resolve()).as_posix()
                if rel not in out[code]: out[code].append(rel)
    return out


def main():
    parser=argparse.ArgumentParser(description='Reindexa fotos de docs/imagens para o catálogo sem Excel.')
    parser.add_argument('--project',type=Path,default=Path(__file__).resolve().parent,help='Raiz do projeto, pasta onde está server.py')
    parser.add_argument('--write',action='store_true',help='Gravar produtos.json depois de mostrar o diagnóstico')
    parser.add_argument('--import-root',action='store_true',help='Copiar fotos de imagens/ (raiz) para docs/imagens/ (não move/apaga)')
    parser.add_argument('--force-empty',action='store_true',help='Permitir gravar mesmo se docs/imagens estiver vazia')
    args=parser.parse_args()
    root=args.project.resolve()
    docs=root/'docs'
    media=docs/'imagens'
    prod=docs/'produtos.json'
    if not prod.is_file(): parser.error(f'Não achei {prod}. Execute ao lado de server.py ou passe --project.')

    if args.import_root:
        source=root/'imagens'
        if not source.is_dir():
            parser.error(f'--import-root: pasta de origem não encontrada: {source}')
        n=0
        for image in scan_docs(source):
            dst=media/image.relative_to(source)
            dst.parent.mkdir(parents=True,exist_ok=True)
            if not dst.exists() or dst.stat().st_size!=image.stat().st_size:
                shutil.copy2(image,dst)
                n+=1
        print(f'Fotos copiadas/atualizadas da pasta raiz: {n} (originais preservados)')

    images=scan_docs(media)
    products=read_json(prod)
    if not isinstance(products,list): parser.error('O produtos.json não é uma lista.')

    products_media=[p for p in images if 'pastilhas' not in p.relative_to(media).parts]
    color_fallback=scan_pastilha_json(docs/'pastilhas.json',media)
    detected_pastilha=re.compile(r'^pastilhas?_?(C\d+)(?:_(?:frente|verso|lado|lat|detalhe))?$',re.I)
    for p in images:
        if 'pastilhas' not in p.relative_to(media).parts: continue
        m=detected_pastilha.match(p.stem)
        if m:
            code=color_code(m.group(1))
            rel=p.relative_to(media).as_posix()
            if rel not in color_fallback[code]: color_fallback[code].append(rel)

    for values in color_fallback.values(): values.sort(key=priority)
    prefix_idx=defaultdict(list)
    for p in products_media:
        prefix_idx[p.stem.casefold().split('_',1)[0]].append(p)

    matched_files=set()
    stats=Counter()
    changed=0
    for item in products:
        base=str(item.get('imagem_base') or '').strip().casefold()
        if not base:
            base=f"{item.get('referencia','')}_{item.get('cor_codigo','')}_{item.get('furacao','')}".casefold()
        refprefix=base.split('_',1)[0]
        found=[]
        for p in prefix_idx.get(refprefix,[]):
            if is_prefix(p.stem.casefold(),base):
                rel=p.relative_to(media).as_posix()
                found.append(rel)
                matched_files.add(str(p.resolve()))
        found=sorted(dict.fromkeys(found),key=lambda rel:priority(rel,base))
        fallback=color_fallback.get(color_code(item.get('cor_codigo')),[])
        before=(item.get('imagens'),item.get('pastilha_fallback'),item.get('tipo_imagem'))
        if found:
            item.update(imagens=found,pastilha_fallback=fallback,tem_foto=True,tem_imagem=True,
                        usa_pastilha=False,tipo_imagem='produto',aviso_imagem='Foto do produto')
            stats['foto_real']+=1
        elif fallback:
            item.update(imagens=fallback,pastilha_fallback=fallback,tem_foto=False,tem_imagem=True,
                        usa_pastilha=True,tipo_imagem='pastilha',aviso_imagem='Amostra de cor (pastilha)')
            stats['pastilha']+=1
        else:
            item.update(imagens=[],pastilha_fallback=[],tem_foto=False,tem_imagem=False,
                        usa_pastilha=False,tipo_imagem='sem_imagem',aviso_imagem='Sem foto')
            stats['sem_imagem']+=1
        after=(item.get('imagens'),item.get('pastilha_fallback'),item.get('tipo_imagem'))
        if before!=after: changed+=1

    print('\n--- Diagnóstico de imagens ---')
    print(f'Projeto:                     {root}')
    print(f'Fotos encontradas em docs/: {len(images)}')
    print(f'Produtos no JSON:           {len(products)}')
    print(f'Com foto real:              {stats["foto_real"]}')
    print(f'Somente pastilha:           {stats["pastilha"]}')
    print(f'Sem foto:                   {stats["sem_imagem"]}')
    print(f'Produtos com índice mudado: {changed}')

    unmatched=[p for p in products_media if str(p.resolve()) not in matched_files]
    print(f'Fotos de produto sem correspondência exata: {len(unmatched)}')
    for p in unmatched[:12]: print('  -',p.relative_to(media))

    if not args.write:
        print('\nSIMULAÇÃO: nada foi modificado. Use --write para atualizar produtos.json.')
        return
    if not images and not args.force_empty:
        print('\nERRO: docs/imagens está vazia/ausente. Não alterei o JSON. Copie as fotos primeiro.',file=sys.stderr)
        sys.exit(2)
    backup=root/'backups'
    backup.mkdir(parents=True,exist_ok=True)
    backup_name=backup / f'produtos_{dt.datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    shutil.copy2(prod,backup_name)
    tmp=prod.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(products,ensure_ascii=False,indent=2),encoding='utf-8')
    tmp.replace(prod)
    report=root/'relatorio_imagens_sem_correspondencia.csv'
    with report.open('w',newline='',encoding='utf-8-sig') as handle:
        writer=csv.writer(handle)
        writer.writerow(['arquivo_em_docs_imagens','observacao'])
        writer.writerows((p.relative_to(media).as_posix(),'Não corresponde ao padrão imagem_base dos produtos') for p in unmatched)
    print('\nATUALIZADO: ',prod)
    print('Backup em:  ',backup_name)
    print('Relatório em:',report)
    print('Recarregue o Catálogo com Ctrl+F5.')

if __name__=='__main__': main()
