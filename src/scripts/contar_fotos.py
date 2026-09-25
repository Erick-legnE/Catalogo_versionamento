# -*- coding: utf-8 -*-
"""
CONTAR_FOTOS - BRASIL BOTOES
=============================
Le o produtos.json (gerado pelo gerar_json.py) e mostra quantos
dos produtos ativos ja tem foto e quantos ainda faltam.

COMO USAR:
  1. Coloque este arquivo na MESMA pasta do produtos.json
     (a pasta do catalogo: "Catálogo Pronta Entrega")
  2. Rode: python contar_fotos.py
"""

import json
from pathlib import Path

ARQUIVO_JSON = Path(__file__).parent / "produtos.json"

def main():
    if not ARQUIVO_JSON.exists():
        print(f"[ERRO] Nao encontrei {ARQUIVO_JSON}")
        return

    with open(ARQUIVO_JSON, encoding="utf-8") as f:
        produtos = json.load(f)

    com_foto = [p for p in produtos if p.get("imagens")]
    sem_foto = [p for p in produtos if not p.get("imagens")]

    print("=" * 52)
    print(f"  Total de produtos ativos: {len(produtos)}")
    print(f"  Com foto:                 {len(com_foto)}")
    print(f"  SEM foto:                 {len(sem_foto)}")
    print("=" * 52)

    if sem_foto:
        # Salva lista dos que faltam foto, pra facilitar priorizar
        saida = Path(__file__).parent / "produtos_sem_foto.txt"
        with open(saida, "w", encoding="utf-8") as f:
            for p in sem_foto:
                f.write(f"{p.get('reduzido','')}\t{p.get('referencia','')}\t"
                         f"{p.get('cor_codigo','')}\t{p.get('cor_nome','')}\n")
        print(f"\n  Lista dos produtos SEM foto salva em: {saida.name}")
        print("  (colunas: codigo reduzido / referencia / cor codigo / cor nome)")

if __name__ == "__main__":
    main()
