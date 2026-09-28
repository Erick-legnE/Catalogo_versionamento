import os
import json
import re
from pathlib import Path

# Base directories based on project structure
BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "docs"
DATA_DIR = BASE_DIR / "data"

PASTILHAS_DIR = DOCS_DIR / "imagens" / "pastilhas"

def extract_color_code(color_text: str) -> str | None:
    """Extracts standard code (e.g. C003, C1005) from arbitrary color string."""
    if not color_text:
        return None
    match = re.search(r'C\s*[-_]?\s*(\d{3,4})', str(color_text), re.IGNORECASE)
    if match:
        return f"C{match.group(1)}"
    return None

def resolve_image_path(product: dict, base_relative_depth: str = "../../") -> str:
    """
    Determines image path for custom photo vs. pastilha fallback.
    `base_relative_depth` handles relative links from nested subfolders (e.g. docs/clientes/cliente-a/).
    """
    custom_img = product.get("imagem", "").strip()
    color_raw = product.get("nome_cor") or product.get("cor") or product.get("codigo_cor", "")
    color_code = extract_color_code(color_raw)

    # 1. Check if custom image exists
    if custom_img:
        custom_full_path = DOCS_DIR / custom_img.lstrip("/")
        if custom_full_path.exists():
            return f"{base_relative_depth}{custom_img.lstrip('/')}"

    # 2. Fallback to pastilha image by code
    if color_code:
        pastilha_filename = f"pastilha_{color_code}.png"
        pastilha_full_path = PASTILHAS_DIR / pastilha_filename
        if pastilha_full_path.exists():
            return f"{base_relative_depth}imagens/pastilhas/{pastilha_filename}"

    # 3. Default placeholder
    return f"{base_relative_depth}imagens/placeholder.png"

def normalize_catalog(items: list[dict], relative_depth: str = "../../") -> list[dict]:
    """Ensures uniform data schema across Clientes and Representantes."""
    normalized = []
    for item in items:
        color_code = extract_color_code(item.get("nome_cor") or item.get("cor", ""))
        img_url = resolve_image_path(item, base_relative_depth=relative_depth)
        
        normalized.append({
            "id": item.get("id") or item.get("codigo"),
            "nome": item.get("nome", "Produto Sem Nome"),
            "codigo": item.get("codigo", ""),
            "cor_nome": item.get("nome_cor") or item.get("cor", ""),
            "cor_codigo": color_code or "",
            "imagem_url": img_url,
            "categoria": item.get("categoria", "Geral"),
            "descricao": item.get("descricao", "")
        })
    return normalized

def build_data():
    """Builds and updates JSON outputs for both clientes and representantes."""
    # Build for Clientes
    clientes_dir = DOCS_DIR / "clientes"
    if clientes_dir.exists():
        for client_folder in clientes_dir.iterdir():
            if client_folder.is_dir():
                data_file = client_folder / "produtos.json"
                if data_file.exists():
                    with open(data_file, "r", encoding="utf-8") as f:
                        raw_data = json.load(f)
                    processed = normalize_catalog(raw_data, relative_depth="../../")
                    with open(data_file, "w", encoding="utf-8") as f:
                        json.dump(processed, f, ensure_ascii=False, indent=2)
                    print(f"[OK] Updated Clientes catalog: {client_folder.name}")

    # Build for Representantes
    reps_dir = DOCS_DIR / "representantes"
    if reps_dir.exists():
        for rep_folder in reps_dir.iterdir():
            if rep_folder.is_dir():
                data_file = rep_folder / "produtos.json"
                if data_file.exists():
                    with open(data_file, "r", encoding="utf-8") as f:
                        raw_data = json.load(f)
                    processed = normalize_catalog(raw_data, relative_depth="../../")
                    with open(data_file, "w", encoding="utf-8") as f:
                        json.dump(processed, f, ensure_ascii=False, indent=2)
                    print(f"[OK] Updated Representantes catalog: {rep_folder.name}")

if __name__ == "__main__":
    build_data()