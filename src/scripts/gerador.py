import os
import json
import re
from pathlib import Path

# Project paths relative to project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = BASE_DIR / "docs"
PASTILHAS_DIR = DOCS_DIR / "imagens" / "pastilhas"


def extract_color_code(color_text: str) -> str | None:
    """
    Extracts standardized color codes (e.g. C003, C060, C1005) from arbitrary strings.
    Matches: 'C003', 'C 003', 'C-003', 'PRETO C003', 'BRANCO C1005'
    """
    if not color_text:
        return None
    match = re.search(r'C\s*[-_]?\s*(\d{3,4})', str(color_text), re.IGNORECASE)
    if match:
        return f"C{match.group(1)}"
    return None


def resolve_image_path(product: dict, relative_depth: str = "../../") -> str:
    """
    Determines image path:
    1. Direct image reference (if file exists)
    2. Pastilha image fallback (if pastilha_CXXXX.png exists)
    3. Default placeholder fallback
    """
    custom_img = str(product.get("imagem", "") or "").strip()
    color_raw = product.get("nome_cor") or product.get("cor") or product.get("codigo_cor", "")
    color_code = extract_color_code(color_raw)

    # 1. Check custom product photo
    if custom_img and custom_img != "null":
        clean_img_path = custom_img.lstrip("/")
        full_path = DOCS_DIR / clean_img_path
        if full_path.exists():
            return f"{relative_depth}{clean_img_path}"

    # 2. Check pastilha fallback
    if color_code:
        pastilha_filename = f"pastilha_{color_code}.png"
        pastilha_full_path = PASTILHAS_DIR / pastilha_filename
        if pastilha_full_path.exists():
            return f"{relative_depth}imagens/pastilhas/{pastilha_filename}"

    # 3. Default placeholder
    return f"{relative_depth}imagens/placeholder.png"


def normalize_catalog_item(item: dict, relative_depth: str = "../../") -> dict:
    """Converts raw product dict into standardized catalog format."""
    color_raw = item.get("nome_cor") or item.get("cor") or item.get("codigo_cor", "")
    color_code = extract_color_code(color_raw)
    resolved_img = resolve_image_path(item, relative_depth=relative_depth)

    return {
        "id": str(item.get("id") or item.get("codigo") or ""),
        "nome": str(item.get("nome") or "Produto Sem Nome"),
        "codigo": str(item.get("codigo") or ""),
        "cor_nome": str(color_raw),
        "cor_codigo": color_code or "",
        "imagem_url": resolved_img,
        "categoria": str(item.get("categoria") or "Geral"),
        "descricao": str(item.get("descricao") or "")
    }


def process_directory_catalogs(target_subdir: str):
    """Processes all subfolders in docs/<target_subdir> (clientes or representantes)."""
    target_path = DOCS_DIR / target_subdir
    if not target_path.exists():
        print(f"[SKIP] Directory not found: {target_path}")
        return

    for folder in target_path.iterdir():
        if folder.is_dir():
            data_file = folder / "produtos.json"
            if data_file.exists():
                try:
                    with open(data_file, "r", encoding="utf-8") as f:
                        raw_items = json.load(f)

                    if isinstance(raw_items, list):
                        processed = [normalize_catalog_item(item, relative_depth="../../") for item in raw_items]
                        with open(data_file, "w", encoding="utf-8") as f:
                            json.dump(processed, f, ensure_ascii=False, indent=2)
                        print(f"[OK] Normalized: docs/{target_subdir}/{folder.name}/produtos.json ({len(processed)} items)")
                except Exception as e:
                    print(f"[ERROR] Failed processing {data_file}: {e}")


if __name__ == "__main__":
    print("Starting catalog build process...")
    process_directory_catalogs("clientes")
    process_directory_catalogs("representantes")
    print("Catalog build finished successfully!")