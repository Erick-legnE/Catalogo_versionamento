from pathlib import Path

# Define root directory relative to this script
BASE_DIR = Path(__file__).resolve().parent.parent

# --- INPUT PATHS ---
DATA_DIR = BASE_DIR / "data"
SRC_DIR = BASE_DIR / "src"

EXCEL_FILE = DATA_DIR / "estoque.xlsx"
USUARIOS_FILE = SRC_DIR / "usuarios.json"
TEMPLATE_REP = SRC_DIR / "templates" / "template_representante_index_2.html"

# --- OUTPUT PATHS (dist/) ---
DIST_DIR = BASE_DIR / "dist"
SUBSITES_INDEX_OUTPUT = DIST_DIR / "subsites_index.json"
REPRESENTANTES_OUTPUT_DIR = DIST_DIR / "representantes"

# Always ensure target folders exist before writing files
DIST_DIR.mkdir(parents=True, exist_ok=True)
REPRESENTANTES_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Example writing to dist:
# with open(SUBSITES_INDEX_OUTPUT, "w", encoding="utf-8") as f:
#     json.dump(subsites_data, f)