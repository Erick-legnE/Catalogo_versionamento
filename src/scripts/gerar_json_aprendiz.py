"""
gerar_json_aprendiz.py — Catálogo Digital Brasil Botões
Lê ESTOQUES PROJETO V2 - Saldos2_teste.xlsm e tabela_cores_final.xlsx
Gera dist/produtos.json e copia imagens para dist/imagens/
"""

import json
import os
import re
import shutil
from pathlib import Path

import openpyxl

# ─── CAMINHOS DINÂMICOS (SUBINDO 3 NÍVEIS DE src/scripts/ ATÉ A RAIZ DO PROJETO) ───
BASE_DIR = Path(__file__).resolve().parent.parent.parent

PLANILHA = BASE_DIR / "data" / "ESTOQUES PROJETO V2 - Saldos2_teste.xlsm"
TABELA_CORES = BASE_DIR / "apoio" / "tabela_cores_final.xlsx"
PASTA_FOTOS_ORIGEM = BASE_DIR / "imagens"
PASTA_IMAGENS = BASE_DIR / "dist" / "imagens"
PASTA_PASTILHAS = BASE_DIR / "dist" / "pastilhas"
ARQUIVO_JSON = BASE_DIR / "dist" / "produtos.json"

# ─── HELPERS ──────────────────────────────────────────────────────────────────

FAMILIAS_PALAVRAS_CHAVE = {
    "Branco":     ["branco"],
    "Bege":       ["bege", "creme", "marfim", "areia"],
    "Marrom":     ["marrom", "caramelo", "chocolate", "café", "cafe", "conhaque"],
    "Preto":      ["preto"],
    "Cinza":      ["cinza", "grafite", "chumbo"],
    "Azul":       ["azul", "marinho", "royal", "turquesa"],
    "Verde":      ["verde", "oliva", "militar"],
    "Amarelo":    ["amarelo", "canário", "canario", "mostarda"],
    "Vermelho":   ["vermelho", "vinho", "bordô", "bordo"],
    "Rosa":       ["rosa", "pink", "fúcsia", "fucsia"],
    "Laranja":    ["laranja"],
    "Roxo":       ["roxo", "lilás", "lilas", "violeta"],
    "Dourado":    ["dourado", "ouro"],
    "Prata":      ["prata", "prateado", "metálico", "metalico"],
    "Multicolor": ["multicolor", "mesclado", "mescla"],
    "Natural":    ["natural"],
}

def inferir_familia_por_nome(nome):
    nome_lower = str(nome or "").strip().lower()
    if not nome_lower:
        return None
    for familia, palavras in FAMILIAS_PALAVRAS_CHAVE.items():
        for palavra in palavras:
            if palavra in nome_lower:
                return familia
    return None


def normalizar_cor(codigo):
    codigo = str(codigo).strip()
    if codigo.upper().startswith("C"):
        return codigo.upper()
    codigo_num = codigo.lstrip("0") or "0"
    try:
        return f"C{int(codigo_num):03d}"
    except ValueError:
        return f"C{codigo}"


def montar_localizacao(corredor, caixa):
    corredor = str(corredor or "").strip()
    caixa = str(caixa or "").strip()
    if not corredor and not caixa:
        return ""
    partes = []
    if corredor:
        partes.append(f"Corredor {corredor}")
    if caixa:
        try:
            caixa_fmt = f"{int(caixa):03d}"
        except ValueError:
            caixa_fmt = caixa
        partes.append(f"Caixa {caixa_fmt}")
    return " / ".join(partes)


def montar_prefixo_imagem(modelo, cor_codigo, ting):
    modelo = str(modelo).strip()
    cor = normalizar_cor(cor_codigo)
    ting = str(ting).strip() if ting else ""
    if ting:
        return f"{modelo}_{cor}+{ting}"
    return f"{modelo}_{cor}"


def buscar_imagens(prefixo_com_furacao):
    encontrados = []
    if not PASTA_FOTOS_ORIGEM.exists():
        return encontrados

    prefixo_lower = prefixo_com_furacao.lower()
    for arquivo in PASTA_FOTOS_ORIGEM.iterdir():
        if not arquivo.is_file():
            continue
        nome = arquivo.stem.lower()
        ext = arquivo.suffix.lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        if nome == prefixo_lower or nome.startswith(prefixo_lower + "_"):
            PASTA_IMAGENS.mkdir(parents=True, exist_ok=True)
            destino = PASTA_IMAGENS / arquivo.name
            if not destino.exists():
                shutil.copy2(arquivo, destino)
            encontrados.append(arquivo.name)

    def ordem(nome):
        n = nome.lower()
        if "_frente" in n:
            return 1
        if "_verso" in n:
            return 2
        if "_lado" in n or "_lat" in n:
            return 3
        if "_detalhe" in n:
            return 4
        return 0

    encontrados.sort(key=ordem)
    return encontrados


def buscar_pastilha_fallback(cor_raw):
    """Busca e copia a pastilha da cor para dist/imagens/ caso a foto do botão não exista."""
    if not cor_raw:
        return []

    cor_fmt = str(cor_raw).strip().zfill(3)
    cod_c = f"C{cor_fmt}"

    padroes = [f"{cod_c}_frente", f"{cod_c}", f"{cor_fmt}_frente", f"{cor_fmt}"]
    pastas = [PASTA_PASTILHAS, PASTA_FOTOS_ORIGEM]

    for pasta in pastas:
        if not pasta.exists():
            continue
        for padrao in padroes:
            for ext in (".jpg", ".jpeg", ".png", ".webp"):
                candidato = pasta / f"{padrao}{ext}"
                if candidato.exists():
                    PASTA_IMAGENS.mkdir(parents=True, exist_ok=True)
                    destino = PASTA_IMAGENS / candidato.name
                    if not destino.exists():
                        shutil.copy2(candidato, destino)
                    return [candidato.name]
    return []


def carregar_tabela_cores():
    tabela = {}
    if not TABELA_CORES.exists():
        print(f"  [AVISO] tabela_cores_final.xlsx não encontrada em {TABELA_CORES}")
        return tabela
    wb = openpyxl.load_workbook(TABELA_CORES, read_only=True, data_only=True)
    ws = wb.active
    headers = None
    for row in ws.iter_rows(values_only=True):
        if headers is None:
            headers = [str(h).strip().lower() if h else "" for h in row]
            continue
        if not row[0]:
            continue
        linha = dict(zip(headers, row))
        codigo = str(linha.get("cor_codigo", "")).strip().upper()
        if codigo:
            tabela[codigo] = {
                "nome": str(linha.get("cor_nome", "") or "").strip(),
                "familia": str(linha.get("cor_familia", "") or "").strip(),
                "hex": str(linha.get("cor_hex", "") or "").strip(),
            }
    return tabela


def main():
    print("=" * 52)
    print("  Brasil Botões — Gerando catálogo")
    print("=" * 52)

    if not PLANILHA.exists():
        print(f"\n[ERRO] Planilha não encontrada no caminho:\n  {PLANILHA}")
        raise SystemExit(1)

    print(f"\n[1/4] Carregando planilha de estoques...")
    print(f"      Caminho: {PLANILHA}")
    wb = openpyxl.load_workbook(PLANILHA, read_only=True, keep_vba=True, data_only=True)

    print("\n[2/4] Carregando tabela de cores...")
    tabela_cores = carregar_tabela_cores()

    PASTA_IMAGENS.mkdir(parents=True, exist_ok=True)
    ARQUIVO_JSON.parent.mkdir(parents=True, exist_ok=True)

    print("\n[3/4] Processando produtos e imagens...")
    ws_est = wb["Estoque"] if "Estoque" in wb.sheetnames else wb.active
    headers = None
    dados_encontrados = False
    produtos = []
    imagens_copiadas = 0
    inativos_ignorados = 0
    sem_foto_ignorados = 0

    for row in ws_est.iter_rows(values_only=True):
        if not dados_encontrados:
            if row[0] == "SEQ.":
                headers = [str(h).strip() if h else "" for h in row]
                dados_encontrados = True
            continue

        if not row[0] or not str(row[0]).strip().isdigit():
            continue

        linha = dict(zip(headers, row))

        cod_red = str(linha.get("CÓD. RED.", "") or "").strip()
        modelo  = str(linha.get("MODELO", "") or "").strip()
        tamanho = str(linha.get("TAMANHO", "") or "").strip()
        cor_raw = str(linha.get("COR", "") or "").strip()
        ting    = str(linha.get("TING.", "") or "").strip()
        desc_cor= str(linha.get("DESC. COR", "") or "").strip()
        furos   = str(linha.get("FUROS", "") or "").strip()
        acabam  = str(linha.get("ACABAM.", "") or "").strip()
        obs     = str(linha.get("OBS", "") or "").strip()
        material= str(linha.get("MATERIAL", "") or "").strip()
        situacao= str(linha.get("SITUAÇÃO", "") or linha.get("SITUACAO", "") or "Ativo").strip()

        if situacao.strip().lower() != "ativo":
            inativos_ignorados += 1
            continue

        saldo   = linha.get("QTD SALDO")
        um      = str(linha.get("UM", "") or "").strip()
        descr   = str(linha.get("DESCR.", "") or "").strip()
        corredor= str(linha.get("CORR", "") or "").strip()
        caixa   = str(linha.get("CX", "") or "").strip()

        try:
            qtd = float(saldo) if saldo is not None else 0
        except (TypeError, ValueError):
            qtd = 0

        cor_codigo = normalizar_cor(cor_raw) if cor_raw else ""
        ref_tabela = tabela_cores.get(cor_codigo, {})
        
        if desc_cor:
            cor_nome = desc_cor
            cor_familia = inferir_familia_por_nome(desc_cor) or ref_tabela.get("familia", "")
        else:
            cor_nome = ref_tabela.get("nome", "")
            cor_familia = ref_tabela.get("familia", "")
        cor_hex = ref_tabela.get("hex", "")

        prefixo = montar_prefixo_imagem(modelo, cor_raw, ting)
        prefixo_furacao = f"{prefixo}_{furos}" if furos else prefixo
        
        imagens = buscar_imagens(prefixo_furacao)
        if not imagens:
            imagens = buscar_pastilha_fallback(cor_raw)

        tem_foto = bool(imagens)
        if imagens:
            imagens_copiadas += len(imagens)
        else:
            sem_foto_ignorados += 1

        imagem_base = prefixo_furacao
        localizacao = montar_localizacao(corredor, caixa)

        produto = {
            "reduzido": cod_red,
            "referencia": modelo,
            "descricao": descr,
            "tamanho": tamanho,
            "cor_codigo": cor_codigo,
            "cor_nome": cor_nome,
            "cor_familia": cor_familia,
            "cor_hex": cor_hex,
            "tingimento": ting,
            "furacao": furos,
            "acabamento": acabam,
            "material": material,
            "obs": obs,
            "saldo": qtd,
            "unidade": um,
            "localizacao": localizacao,
            "imagem_base": imagem_base,
            "imagens": imagens,
            "tem_foto": tem_foto,
        }
        produtos.append(produto)

    print(f"\n[4/4] Gravando dist/produtos.json...")
    with open(ARQUIVO_JSON, "w", encoding="utf-8") as f:
        json.dump(produtos, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*52}")
    print(f"  Concluído! {len(produtos)} produtos exportados.")
    print(f"  - Imagens encontradas/copiadas: {imagens_copiadas}")
    print(f"  - Produtos sem foto: {sem_foto_ignorados}")
    print(f"  - Produtos inativos ignorados: {inativos_ignorados}")
    print(f"{'='*52}\n")


if __name__ == "__main__":
    main()