# -*- coding: utf-8 -*-
"""
GERADOR DE SUB-SITES E CATÁLOGOS SEGMENTADOS - BRASIL BOTÕES
- Formata os nomes de exibição (limpa sufixos jurídicos e aplica Title Case).
- Gera sub-sites diretamente na Raiz para manter URLs limpas.
"""

from datetime import datetime
import os
import re
import glob
import json
import shutil
import secrets
import string
import unicodedata
from pathlib import Path

import openpyxl

# ======================= CONFIGURAÇÃO DE CAMINHOS DINÂMICOS =======================
# Sobe 3 níveis (src/scripts/gerador.py -> src/scripts -> src -> RAIZ)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

BUILD_VERSION = datetime.now().strftime("%Y%m%d_%H%M%S")

# Caminhos de Entrada
PLANILHA_CLIENTES = BASE_DIR / "data" / "ESTOQUES PROJETO V2 - Clientes_teste.xlsm"
ABA_CLIENTES = "Cliente"
LINHA_CABECALHO = 11

TABELA_CORES = BASE_DIR / "apoio" / "tabela_cores_final.xlsx"
PASTA_IMAGENS = BASE_DIR / "dist" / "imagens"
PASTA_PASTILHAS = BASE_DIR / "dist" / "pastilhas"

# Templates em src/templates/
TEMPLATE_REP = BASE_DIR / "src" / "templates" / "template_representante_index.html"
TEMPLATE_CLI = BASE_DIR / "src" / "templates" / "template_cliente_index.html"

# Saídas DIRETAMENTE NA RAIZ (para URLs limpas)
PASTA_REPRESENTANTES = BASE_DIR / "representantes"
PASTA_CLIENTES = BASE_DIR / "clientes"
PASTA_MODELOS = BASE_DIR / "modelos"
PASTA_CORES = BASE_DIR / "cores"

ARQUIVO_USUARIOS = BASE_DIR / "usuarios.json"
ARQUIVO_VITRINE = BASE_DIR / "subsites_index.json"
LINK_CATALOGO_GERAL = "https://brasilbotoes.github.io/catalogo"

# Limite mínimo de produtos para gerar página
LIMITE_MINIMO_REP = 1
LIMITE_MINIMO_CLI = 1
LIMITE_MINIMO_MODELO = 1
LIMITE_MINIMO_COR_FAMILIA = 1

PALAVRAS_IGNORAR_SLUG = {
    "LTDA", "EIRELI", "ME", "EPP", "SA", "S/A", "CIA", "COMERCIO",
    "COMERCIAL", "REPRESENTACOES", "REPRESENTACAO", "INDUSTRIA",
    "INDUSTRIAL", "DISTRIBUIDORA", "IMPORTACAO", "EXPORTACAO",
    "DE", "DO", "DA", "DOS", "DAS", "E", "S", "A"
}

EXTENSOES_VALIDAS = [".jpg", ".jpeg", ".png", ".webp"]
# ==============================================================


def formatar_nome_exibicao(texto):
    """
    Limpa jargões jurídicos/fiscais e formata os nomes para exibição elegante.
    Exemplo: 'ELIAN INDUSTRIA TEXTIL LTDA.' -> 'Elian Têxtil'
             'VISON REPRESENTACOES LTDA' -> 'Vison Representações'
    """
    if not texto:
        return ""

    t = str(texto).strip()

    # 1. Remove termos jurídicos e operacionais pesados
    padroes_remover = [
        r"\bEM RECUPERA[CÇ][AÃ]O JUDICIAL\b.*",
        r"\bOUCC\d*\b",
        r"\bLTDA\.?\b",
        r"\bEIRELI\b",
        r"\bS/?A\.?\b",
        r"\bM\.?E\.?\b",
        r"\bE\.?P\.?P\.?\b",
        r"\bIND[UÚ]STRIA E COM[EÉ]RCIO DE CONFEC[CÇ][OÕ]ES\b",
        r"\bIND[UÚ]STRIA E COM[EÉ]RCIO\b",
        r"\bIND\.? E COM\.?\b",
        r"\bIND\.?\b",
        r"\bCOM\.?\b",
        r"\bDE ARTIGOS DO VESTU[AÁ]RIO\b",
        r"\bDO VESTU[AÁ]RIO\b",
        r"\bCOMERCIO DE AVIAMENTOS\b",
        r"\bREPRESENTA[CÇ][OÕ]ES TEXTEIS\b",
    ]

    for p in padroes_remover:
        t = re.sub(p, "", t, flags=re.IGNORECASE)

    # Limpa pontuações e espaços extras nas pontas
    t = re.sub(r"[\s\-\.]+$", "", t)
    t = re.sub(r"^[\s\-\.]+", "", t)
    t = re.sub(r"\s+", " ", t).strip()

    if not t:
        t = str(texto).strip()

    # 2. Formatação inteligente de caixa (Title Case)
    palavras_minusculas = {"de", "da", "do", "das", "dos", "e"}
    siglas_maiusculas = {"V2", "CH3", "GS2", "DRC", "AMC", "CVI", "IB", "RQ", "PS", "DK", "MPL", "TNG", "A.M.C."}

    partes = t.split()
    partes_formatadas = []

    for i, word in enumerate(partes):
        w_upper = word.upper()
        w_clean = re.sub(r"[^\w]", "", w_upper)

        if w_clean in siglas_maiusculas or w_upper in siglas_maiusculas:
            partes_formatadas.append(w_upper)
        elif i > 0 and word.lower() in palavras_minusculas:
            partes_formatadas.append(word.lower())
        else:
            partes_formatadas.append(word.capitalize())

    res = " ".join(partes_formatadas)

    # Restaura acentuação em palavras comuns
    substituicoes = {
        "Textil": "Têxtil",
        "Confeccoes": "Confecções",
        "Confeccao": "Confecção",
        "Representacoes": "Representações",
        "Representacao": "Representação",
        "Cia": "Cia.",
    }
    for k, v in substituicoes.items():
        res = re.sub(rf"\b{k}\b", v, res)

    return res


def safe_get(row, idx):
    if idx is not None and 0 <= idx < len(row):
        return row[idx]
    return None


def limpar_texto(valor):
    if valor is None:
        return ""
    return " ".join(str(valor).strip().upper().split())


def gerar_slug_curto(texto):
    if not texto:
        return ""
    texto_nfkd = unicodedata.normalize('NFKD', str(texto))
    texto_ascii = texto_nfkd.encode('ascii', 'ignore').decode('utf-8').upper()
    palavras = re.findall(r'[A-Z0-9]+', texto_ascii)
    significativas = [p for p in palavras if p not in PALAVRAS_IGNORAR_SLUG]
    if not significativas:
        significativas = palavras
    return "-".join(significativas[:2]).lower()


def cor_formatada(cor_raw):
    try:
        return str(int(str(cor_raw).strip())).zfill(3)
    except (ValueError, TypeError):
        return str(cor_raw).strip() if cor_raw is not None else ""


def carregar_tabela_cores(caminho):
    cores = {}
    if not os.path.exists(caminho):
        return cores
    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    ws = wb.active
    headers = None
    for row in ws.iter_rows(min_row=1, max_row=1, values_only=True):
        headers = [str(h).strip() if h else "" for h in row]
        break
    if not headers:
        return cores

    idx = {h: i for i, h in enumerate(headers)}
    for row in ws.iter_rows(min_row=2, values_only=True):
        codigo = safe_get(row, idx.get("cor_codigo"))
        if codigo is None:
            continue
        codigo_fmt = cor_formatada(codigo)
        cores[codigo_fmt] = {
            "nome": safe_get(row, idx.get("cor_nome")),
            "familia": safe_get(row, idx.get("cor_familia")),
            "hex": safe_get(row, idx.get("cor_hex")),
        }
    return cores


def buscar_foto_pastilha(cor_fmt):
    """Procura por uma foto de amostra/pastilha correspondente ao código da cor (somente frente)."""
    if not cor_fmt:
        return None

    cod_c = f"C{cor_fmt}"
    padroes_nome = [
        f"{cod_c}_frente",
        f"{cod_c}_FRENTE",
        f"{cod_c}",
        f"{cor_fmt}_frente",
        f"{cor_fmt}",
        f"pastilha_{cod_c}",
        f"pastilha_{cor_fmt}",
    ]

    pastas_busca = [PASTA_PASTILHAS, PASTA_IMAGENS]

    for pasta in pastas_busca:
        if not pasta.is_dir():
            continue
        for nome in padroes_nome:
            for ext in EXTENSOES_VALIDAS:
                candidato = pasta / f"{nome}{ext}"
                if candidato.exists():
                    return os.path.relpath(candidato, BASE_DIR).replace("\\", "/")
    return None


def buscar_foto(modelo, cor_fmt, ting, furos):
    """
    1. Tenta encontrar a foto do botão específico.
    2. Se não encontrar, tenta buscar a foto da pastilha/cor (frente).
    3. Se nenhuma existir, retorna None.
    """
    # 1. Busca foto do modelo do botão
    if PASTA_IMAGENS.is_dir():
        base = f"{modelo}_C{cor_fmt}"
        if ting:
            base += f"+{ting}"
        base += f"_{furos}"

        for ext in EXTENSOES_VALIDAS:
            candidato = PASTA_IMAGENS / (base + ext)
            if candidato.exists():
                return os.path.relpath(candidato, BASE_DIR).replace("\\", "/")

        padrao = str(PASTA_IMAGENS / (base + ".*"))
        achados = glob.glob(padrao)
        if achados:
            return os.path.relpath(achados[0], BASE_DIR).replace("\\", "/")

    # 2. Fallback: Busca foto da pastilha/cor
    return buscar_foto_pastilha(cor_fmt)

def ler_produtos():
    print(f"Lendo planilha de Clientes em: {PLANILHA_CLIENTES}")
    wb = openpyxl.load_workbook(PLANILHA_CLIENTES, read_only=True, data_only=True, keep_vba=False)
    ws = wb[ABA_CLIENTES]

    headers = None
    for row in ws.iter_rows(min_row=LINHA_CABECALHO, max_row=LINHA_CABECALHO, values_only=True):
        headers = [str(h).strip().upper() if h else "" for h in row]
        break

    def col(nomes):
        if not headers:
            return None
        for n in nomes:
            if n in headers:
                return headers.index(n)
        return None

    idx_codred = col(["CÓD. RED.", "COD. RED.", "CODRED"])
    idx_modelo = col(["MODELO", "REFERENCIA"])
    idx_tamanho = col(["TAMANHO"])
    idx_cor = col(["COR"])
    idx_ting = col(["TING.", "TING"])
    idx_desccor = col(["DESC. COR", "DESCCOR"])
    idx_furos = col(["FUROS"])
    idx_acabam = col(["ACABAM.", "ACABAMENTO"])
    idx_material = col(["MATERIAL"])
    idx_descr = col(["DESCR.", "DESCRICAO"])
    idx_qtd = col(["QTD SALDO", "SALDO"])
    idx_um = col(["UM"])

    idx_rep = col(["REPRESENTANTE", "REP", "DESC"])
    if idx_rep is None:
        idx_rep = 12

    idx_cliente = col(["CLIENTE", "CLI", "OBS"])
    if idx_cliente is None:
        idx_cliente = 13

    cores = carregar_tabela_cores(TABELA_CORES)

    produtos_por_rep = {}
    produtos_por_cli = {}
    produtos_por_modelo = {}
    produtos_por_cor_familia = {}
    relatorio = []

    for row in ws.iter_rows(min_row=LINHA_CABECALHO + 1, values_only=True):
        codred = safe_get(row, idx_codred)
        if codred is None:
            continue

        rep_raw = safe_get(row, idx_rep) or ""
        cli_raw = safe_get(row, idx_cliente) or ""

        rep = limpar_texto(rep_raw)
        cli = limpar_texto(cli_raw)

        modelo_val = safe_get(row, idx_modelo)
        modelo = str(modelo_val).strip() if modelo_val is not None else ""

        cor_raw = safe_get(row, idx_cor)
        cor_fmt = cor_formatada(cor_raw) if cor_raw is not None else ""

        ting_raw = safe_get(row, idx_ting)
        ting = str(ting_raw).strip() if ting_raw not in (None, "", "SIM") else None

        furos_val = safe_get(row, idx_furos)
        furos = str(furos_val).strip() if furos_val is not None else ""

        foto = buscar_foto(modelo, cor_fmt, ting, furos)
        info_cor = cores.get(cor_fmt, {})
        cor_familia = info_cor.get("familia") or "OUTROS"

        desc_cor_val = safe_get(row, idx_desccor)
        tamanho_val = safe_get(row, idx_tamanho)
        um_val = safe_get(row, idx_um)

        produto = {
            "cod_red": str(codred),
            "modelo": modelo,
            "tamanho": str(tamanho_val).strip() if tamanho_val is not None else None,
            "cor_codigo": f"C{cor_fmt}",
            "tingimento": ting,
            "cor_nome": desc_cor_val if desc_cor_val else info_cor.get("nome"),
            "cor_familia": cor_familia,
            "cor_hex": info_cor.get("hex"),
            "furacao": furos,
            "acabamento": safe_get(row, idx_acabam),
            "material": safe_get(row, idx_material),
            "descricao": safe_get(row, idx_descr),
            "qtd_saldo": safe_get(row, idx_qtd),
            "unidade": um_val if um_val not in (None, "") else None,
            "cliente": formatar_nome_exibicao(cli),
            "representante": formatar_nome_exibicao(rep),
            "foto": foto,
        }

        if rep:
            produtos_por_rep.setdefault(rep, []).append(produto)
        if cli:
            produtos_por_cli.setdefault(cli, []).append(produto)
        if modelo:
            produtos_por_modelo.setdefault(modelo, []).append(produto)
        if cor_familia:
            produtos_por_cor_familia.setdefault(cor_familia, []).append(produto)

        relatorio.append({
            "representante": rep,
            "cliente": cli,
            "modelo": modelo,
            "cod_red": produto["cod_red"],
            "cor": produto["cor_codigo"],
            "foto_encontrada": "SIM" if foto else "NAO",
        })

    return {
        "representantes": produtos_por_rep,
        "clientes": produtos_por_cli,
        "modelos": produtos_por_modelo,
        "cores": produtos_por_cor_familia,
        "relatorio": relatorio
    }


def gerar_senha_aleatoria(tamanho=8):
    caracteres = string.ascii_letters + string.digits
    return ''.join(secrets.choice(caracteres) for _ in range(tamanho))


def gerenciar_autenticacao(slugs_map, nomes_exibicao, tipo_entidade="representante"):
    usuarios_dict = {}
    if ARQUIVO_USUARIOS.exists():
        try:
            with open(ARQUIVO_USUARIOS, "r", encoding="utf-8") as f:
                dados = json.load(f)
                for item in dados:
                    usuarios_dict[item["slug"]] = item
        except Exception:
            usuarios_dict = {}

    for raw_nome, slug in sorted(slugs_map.items()):
        nome_clean = nomes_exibicao.get(raw_nome, raw_nome)
        if slug in usuarios_dict:
            usuarios_dict[slug]["nome"] = nome_clean
            usuarios_dict[slug]["tipo"] = tipo_entidade
        else:
            user_id = f"user_{len(usuarios_dict) + 1:03d}"
            usuarios_dict[slug] = {
                "id": user_id,
                "nome": nome_clean,
                "slug": slug,
                "username": slug,
                "password": gerar_senha_aleatoria(8),
                "tipo": tipo_entidade,
                "ativo": True
            }

    lista_usuarios = list(usuarios_dict.values())
    ARQUIVO_USUARIOS.parent.mkdir(parents=True, exist_ok=True)
    with open(ARQUIVO_USUARIOS, "w", encoding="utf-8") as f:
        json.dump(lista_usuarios, f, ensure_ascii=False, indent=2)

    return usuarios_dict


def obter_template_html(tipo_entidade):
    template_path = TEMPLATE_CLI if tipo_entidade == "clientes" else TEMPLATE_REP
    if template_path.exists():
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    if TEMPLATE_REP.exists():
        with open(TEMPLATE_REP, "r", encoding="utf-8") as f:
            return f.read()
    print(f"[ERRO CRÍTICO] Nenhum template encontrado em {template_path}")
    return None


def preparar_pasta_limpa(pasta):
    """Limpa pastas antigas para evitar arquivos/folders órfãos."""
    if pasta.exists():
        shutil.rmtree(pasta)
    pasta.mkdir(parents=True, exist_ok=True)


def gerar_paginas(produtos_map, tipo_entidade="representantes", limite_minimo=1):
    payload_produtos = {
    "version": BUILD_VERSION,
    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "entidade_id": dados_auth.get("id", slug),
    "entidade_nome": nome_exibicao,
    "tipo": tipo_entidade,
    "total_produtos": len(produtos),
    "produtos": produtos
    }

    with open(pasta_destino / "produtos.json", "w", encoding="utf-8") as f:
        json.dump(payload_produtos, f, ensure_ascii=False, indent=2)

    if template_html:
        html = template_html.replace("{{REPRESENTANTE}}", nome_exibicao)
        html = html.replace("{{CLIENTE}}", nome_exibicao)
        html = html.replace("{{NOME_ENTIDADE}}", nome_exibicao)
        html = html.replace("{{LINK_CATALOGO_GERAL}}", LINK_CATALOGO_GERAL)
        html = html.replace("{{REPRESENTANTE_ID}}", str(dados_auth.get("id", "")))
        html = html.replace("{{BUILD_VERSION}}", BUILD_VERSION)  # <--- ADD THIS LINE

    with open(pasta_destino / "index.html", "w", encoding="utf-8") as f:
        f.write(html)
        
    template_html = obter_template_html(tipo_entidade)
    pasta_raiz_tipo = BASE_DIR / tipo_entidade
    preparar_pasta_limpa(pasta_raiz_tipo)

    entidades_filtradas = {
        nome: prods for nome, prods in produtos_map.items()
        if len(prods) >= limite_minimo
    }

    slugs_map = {}
    nomes_exibicao = {}
    slugs_usados = set()

    for raw_nome in entidades_filtradas.keys():
        nome_limpo = formatar_nome_exibicao(raw_nome)
        nomes_exibicao[raw_nome] = nome_limpo

        base = gerar_slug_curto(raw_nome)
        slug = base
        c = 2
        while slug in slugs_usados:
            slug = f"{base}-{c}"
            c += 1
        slugs_usados.add(slug)
        slugs_map[raw_nome] = slug

    mapa_usuarios = gerenciar_autenticacao(slugs_map, nomes_exibicao, tipo_entidade) if tipo_entidade in ("representantes", "clientes") else {}
    links = []

    for raw_nome, produtos in entidades_filtradas.items():
        slug = slugs_map[raw_nome]
        nome_exibicao = nomes_exibicao[raw_nome]
        dados_auth = mapa_usuarios.get(slug, {})

        pasta_destino = pasta_raiz_tipo / slug
        pasta_destino.mkdir(parents=True, exist_ok=True)

        payload_produtos = {
            "entidade_id": dados_auth.get("id", slug),
            "entidade_nome": nome_exibicao,
            "tipo": tipo_entidade,
            "total_produtos": len(produtos),
            "produtos": produtos
        }

        with open(pasta_destino / "produtos.json", "w", encoding="utf-8") as f:
            json.dump(payload_produtos, f, ensure_ascii=False, indent=2)

        if template_html:
            html = template_html.replace("{{REPRESENTANTE}}", nome_exibicao)
            html = html.replace("{{CLIENTE}}", nome_exibicao)
            html = html.replace("{{NOME_ENTIDADE}}", nome_exibicao)
            html = html.replace("{{LINK_CATALOGO_GERAL}}", LINK_CATALOGO_GERAL)
            html = html.replace("{{REPRESENTANTE_ID}}", str(dados_auth.get("id", "")))

            with open(pasta_destino / "index.html", "w", encoding="utf-8") as f:
                f.write(html)

        links.append((nome_exibicao, slug, len(produtos)))
        print(f"  -> [{tipo_entidade.upper()}] {nome_exibicao} ({slug}): {len(produtos)} produtos + index.html")

    return links


def exportar_indice_vitrine(links_rep, links_cli, links_mod, links_cor):
    vitrine = []

    for nome, slug, qtd in links_rep:
        vitrine.append({
            "nome": nome,
            "slug": slug,
            "tipo": "representante",
            "badge": "Representante",
            "qtd": qtd,
            "url": f"representantes/{slug}/index.html"
        })

    for nome, slug, qtd in links_cli:
        vitrine.append({
            "nome": nome,
            "slug": slug,
            "tipo": "cliente",
            "badge": "Cliente Especial",
            "qtd": qtd,
            "url": f"clientes/{slug}/index.html"
        })

    for nome, slug, qtd in links_mod:
        vitrine.append({
            "nome": f"Modelo {nome}",
            "slug": slug,
            "tipo": "modelo",
            "badge": "Modelo / Linha",
            "qtd": qtd,
            "url": f"modelos/{slug}/index.html"
        })

    for nome, slug, qtd in links_cor:
        vitrine.append({
            "nome": f"Família {nome}",
            "slug": slug,
            "tipo": "cor",
            "badge": "Família de Cor",
            "qtd": qtd,
            "url": f"cores/{slug}/index.html"
        })

    with open(ARQUIVO_VITRINE, "w", encoding="utf-8") as f:
        json.dump(vitrine, f, ensure_ascii=False, indent=2)
    print(f"\nÍndice de vitrine atualizado com sucesso em:\n -> {ARQUIVO_VITRINE}")


def main():
    dados = ler_produtos()
    relatorio = dados["relatorio"]

    print(f"\n--- 1. GERANDO SUB-SITES DE REPRESENTANTES ---")
    links_rep = gerar_paginas(dados["representantes"], tipo_entidade="representantes", limite_minimo=LIMITE_MINIMO_REP)

    print(f"\n--- 2. GERANDO SUB-SITES DE CLIENTES ---")
    links_cli = gerar_paginas(dados["clientes"], tipo_entidade="clientes", limite_minimo=LIMITE_MINIMO_CLI)

    print(f"\n--- 3. GERANDO CATÁLOGOS POR MODELOS ---")
    links_mod = gerar_paginas(dados["modelos"], tipo_entidade="modelos", limite_minimo=LIMITE_MINIMO_MODELO)

    print(f"\n--- 4. GERANDO CATÁLOGOS POR FAMÍLIAS DE CORES ---")
    links_cor = gerar_paginas(dados["cores"], tipo_entidade="cores", limite_minimo=LIMITE_MINIMO_COR_FAMILIA)

    print("\n--- 5. EXPORTANDO ÍNDICE DE VITRINE ---")
    exportar_indice_vitrine(links_rep, links_cli, links_mod, links_cor)

    sem_foto = sum(1 for l in relatorio if l["foto_encontrada"] == "NAO")
    print("\n================ RESUMO DO PROCESSAMENTO ================")
    print(f"Total de itens na planilha : {len(relatorio)}")
    print(f"Itens sem foto vinculada   : {sem_foto}")
    print(f"Sub-sites de Reps gerados  : {len(links_rep)}")
    print(f"Sub-sites Clientes gerados : {len(links_cli)}")
    print(f"Sub-sites Modelos gerados  : {len(links_mod)}")
    print(f"Sub-sites Cores gerados    : {len(links_cor)}")
    print("========================================================")


if __name__ == "__main__":
    main()