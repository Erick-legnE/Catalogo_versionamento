from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request, Body
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from ficha_pdf import render_ficha
from fastapi.staticfiles import StaticFiles
import auth_store as auth
from urllib.parse import quote, unquote
from PIL import Image, UnidentifiedImageError

BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR / "docs"

# Development default:
#   <site>/server_data/solicitacoes
#
# Override on the server machine if wanted:
#   set AUTOMACAO_STORAGE_DIR=D:\BrasilBotoesData\solicitacoes
def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


STORAGE_ROOT = Path(
    os.environ.get(
        "AUTOMACAO_STORAGE_DIR",
        BASE_DIR / "server_data" / "solicitacoes",
    )
).resolve()
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_MB = _env_int("AUTOMACAO_MAX_UPLOAD_MB", 30, 1, 100)
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
MAX_TOTAL_UPLOAD_MB = _env_int("AUTOMACAO_MAX_TOTAL_UPLOAD_MB", 120, 1, 250)
MAX_TOTAL_UPLOAD_BYTES = MAX_TOTAL_UPLOAD_MB * 1024 * 1024
MAX_METADATA_BYTES = 256 * 1024
MAX_BODY_BYTES = MAX_TOTAL_UPLOAD_BYTES + 5 * 1024 * 1024
MAX_ART_FILES = 12
Image.MAX_IMAGE_PIXELS = 20_000_000

IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
IMAGE_FORMATS = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}

app = FastAPI(
    title="Brasil Botões - Automação API",
    version="1.0.0",
)


@app.middleware('http')
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'no-referrer')
    response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    if os.environ.get('AUTOMACAO_HTTPS', '0') == '1':
        response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    return response


def _safe_text(value: Any, max_len: int = 180) -> str:
    return str(value or "").strip()[:max_len]


def _safe_slug(value: Any, fallback: str = "sem-id") -> str:
    value = _safe_text(value, 90).lower()
    value = re.sub(r"[^a-z0-9_-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-_")
    return value or fallback


def _new_request_id(metadata: dict[str, Any]) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    item = metadata.get("item") or {}

    if item.get("type") == "button":
        ref = _safe_slug(item.get("reference"), "sem-ref")
        tam = _safe_slug(item.get("size_tam"), "sem-tam")
        cor = _safe_slug(item.get("color"), "sem-cor")
        identity = f"ref-{ref}_tam-{tam}_{cor}"
    else:
        identity = "outro-item"

    return f"{stamp}_{identity}_{uuid.uuid4().hex[:8]}"


def _new_request_folder(request_id: str) -> Path:
    now = datetime.now()
    folder = (
        STORAGE_ROOT
        / f"{now.year:04d}"
        / f"{now.month:02d}"
        / request_id
    )
    folder.mkdir(parents=True, exist_ok=False)
    return folder


def _find_request_folder(request_id: str) -> Path | None:
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,180}", request_id):
        return None

    if not STORAGE_ROOT.exists():
        return None

    for year in STORAGE_ROOT.iterdir():
        if not year.is_dir():
            continue
        for month in year.iterdir():
            if not month.is_dir():
                continue
            candidate = month / request_id
            if candidate.is_dir():
                return candidate

    return None


async def _save_upload(
    upload: UploadFile,
    folder: Path,
    base_name: str,
    allowed_types: dict[str, str],
) -> dict[str, Any]:
    content_type = (upload.content_type or "").lower()
    extension = allowed_types.get(content_type)

    if extension is None:
        allowed = ", ".join(sorted(allowed_types))
        raise HTTPException(
            status_code=415,
            detail=(
                f"Tipo de arquivo não permitido: {content_type!r}. "
                f"Permitidos: {allowed}"
            ),
        )

    final_name = base_name + extension
    final_path = folder / final_name

    sha = hashlib.sha256()
    total = 0

    fd, tmp_name = tempfile.mkstemp(
        prefix=base_name + "_",
        suffix=".part",
        dir=folder,
    )
    os.close(fd)
    tmp_path = Path(tmp_name)

    try:
        with tmp_path.open("wb") as output:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break

                total += len(chunk)

                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            f"Arquivo {upload.filename!r} excede "
                            f"{MAX_UPLOAD_MB} MB."
                        ),
                    )

                sha.update(chunk)
                output.write(chunk)

        expected_format = IMAGE_FORMATS.get(content_type)
        try:
            with Image.open(tmp_path) as image:
                if image.format != expected_format:
                    raise HTTPException(
                        status_code=415,
                        detail="O conteúdo do arquivo não corresponde ao tipo informado.",
                    )
                image.verify()
            with Image.open(tmp_path) as image:
                image.load()
                if image.width < 1 or image.height < 1:
                    raise HTTPException(status_code=415, detail="Imagem vazia ou inválida.")
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
            raise HTTPException(status_code=415, detail="Arquivo de imagem inválido.") from exc

        tmp_path.replace(final_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    return {
        "filename": final_name,
        "original_filename": _safe_text(upload.filename),
        "content_type": content_type,
        "size_bytes": total,
        "sha256": sha.hexdigest(),
    }


def _public_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": manifest["id"],
        "created_at": manifest["created_at"],
        "updated_at": manifest.get("updated_at", manifest["created_at"]),
        "status": manifest["status"],
        "metadata": manifest["metadata"],
        "files": manifest["files"],
        "history": manifest.get("history", []),
        "workflow": manifest.get("workflow", {}),
    }


REQUEST_STATUSES = {
    "pdf_ready",
    "in_review",
    "approved",
    "rejected",
    "production_ready",
    "rendering_3d",
    "rendered_3d",
    "render_error",
}


def _read_manifest(folder: Path) -> dict[str, Any] | None:
    path = folder / "manifest.json"
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


_CATALOG_CACHE: dict[str, Any] = {}


def _catalog_json(relative_path: str, default: Any) -> Any:
    if relative_path in _CATALOG_CACHE:
        return _CATALOG_CACHE[relative_path]
    try:
        value = json.loads((BASE_DIR / relative_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        value = default
    _CATALOG_CACHE[relative_path] = value
    return value


def _catalog_ref(value: Any) -> str:
    return re.sub(r"^0+(?=\d)", "", _safe_text(value, 80))


def _catalog_color(value: Any) -> str:
    code = re.sub(r"\s+", "", _safe_text(value, 80)).upper()
    if code and not code.startswith("C") and code.isdigit():
        code = "C" + code
    return code


def _has_value(value: Any) -> bool:
    return value is not None and str(value).strip() not in ("", "AUTO", "N/A", "NULL")


def _complete_button_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    item = metadata.get("item") or {}
    if item.get("type") != "button":
        return metadata

    item = dict(item)
    ref = _catalog_ref(item.get("reference"))
    size = _safe_text(item.get("size_tam"), 20)
    color = _catalog_color(item.get("color"))
    refs = _catalog_json("docs/data/referencias_consistem.json", {}).get("references", {})
    products = _catalog_json("docs/produtos.json", [])
    colors = _catalog_json("docs/data/cores_catalogo.json", {}).get("colors", {})
    ref_data = refs.get(ref) if isinstance(refs, dict) else None
    size_data = (ref_data or {}).get("by_size", {}).get(size, {}) if isinstance(ref_data, dict) else {}
    exact = next((row for row in products if _catalog_ref(row.get("referencia")) == ref
                  and _safe_text(row.get("tamanho"), 20) == size
                  and _catalog_color(row.get("cor_codigo")) == color), None)
    color_data = colors.get(color) if isinstance(colors, dict) else None

    completed: dict[str, dict[str, Any]] = {}

    def fill(field: str, value: Any, source: str):
        if _has_value(value) and not _has_value(item.get(field)):
            item[field] = value
            completed[field] = {"value": value, "source": source}

    for field in (
        "fundo", "pastilha_mm", "espessura_final_mm", "broca_mm",
        "distancia_furos_mm", "num_furos", "acabamento",
    ):
        fill(field, size_data.get(field), "referencias_consistem:by_size")

    if size_data.get("num_furos") and not _has_value(item.get("furacao")):
        fill("furacao", f"{size_data['num_furos']}F", "referencias_consistem:by_size")

    if isinstance(exact, dict):
        for field in ("material", "acabamento", "furacao", "cor_nome", "cor_familia", "tingimento", "obs"):
            fill(field, exact.get(field), "produtos.json:exact_reference_size_color")
        if _has_value(exact.get("reduzido")):
            fill("source_reduzido", exact.get("reduzido"), "produtos.json:exact_reference_size_color")

    if isinstance(color_data, dict):
        fill("color_description", color_data.get("descricao"), "cores_catalogo.json")
        fill("color_observation", color_data.get("observacao"), "cores_catalogo.json")
        preview = color_data.get("preview") or {}
        fill("color_preview_kind", preview.get("kind"), "cores_catalogo.json:preview")
        fill("color_preview_confidence", preview.get("confidence"), "cores_catalogo.json:preview")

    result = dict(metadata)
    result["item"] = item
    result["technical_completion"] = {
        "reference_known": bool(ref_data),
        "size_known": bool(size_data),
        "exact_product_found": bool(exact),
        "color_known": bool(color_data),
        "filled_fields": completed,
    }
    return result


def _iter_request_manifests():
    if not STORAGE_ROOT.exists():
        return
    for manifest_path in STORAGE_ROOT.glob("*/*/*/manifest.json"):
        manifest = _read_manifest(manifest_path.parent)
        if manifest and manifest.get("id"):
            yield manifest_path.parent, manifest


def _write_manifest(folder: Path, manifest: dict[str, Any]) -> None:
    target = folder / "manifest.json"
    temporary = folder / "manifest.json.part"
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary, target)



# Access is checked by the server, never from the browser's JSON/sessionStorage.
# The portal and its logo are intentionally available to unauthenticated users.
PAGES={
 'catalogo_geral.html':'catalogo',
 'pastilhas.html':'pastilhas',
 'automacao.html':'automacao',
 'solicitacoes.html':'automacao',
 'cores_preview.html':'cores_preview',
 'admin_usuarios.html':'admin',
}
PRIVATE_FILES={'usuarios.json','facas.json','facas.example.json'}
PUBLIC_FILES = {'logo_simbolo.jpeg', 'favicon.ico', 'produtos.json'}
PUBLIC_PREFIXES = ('css/', 'js/', 'imagens/')
PUBLIC_AREA_PATHS = {
    'catalogo_geral.html': 'catalogo',
    'produtos.json': 'catalogo',
}
PROTECTED_DATA_AREAS = {
    'pastilhas.json': ('pastilhas',),
    'data/cores_catalogo.json': ('cores_preview', 'automacao', 'pastilhas'),
    'data/cores_overrides.json': ('cores_preview', 'automacao'),
    'data/pastilhas_fotos_index.json': ('pastilhas', 'automacao', 'cores_preview'),
    'data/hole_patterns.json': ('pastilhas', 'automacao', 'cores_preview'),
    'data/ref_hole_map.json': ('automacao',),
}

def current_user(request: Request):
    return auth.get_session(request.cookies.get(auth.COOKIE))[0]

def must_login(request: Request):
    user=current_user(request)
    if not user: raise HTTPException(401,'Faça login para continuar.')
    return user

def must_admin(request: Request):
    user=must_login(request)
    if not auth.has(user,'admin'): raise HTTPException(403,'Permissão de administrador necessária.')
    return user

def can_open_subsite(user, area, slug):
    if auth.has(user,'subsites'): return True
    return user and user.get('role')==area and str(user.get('slug'))==slug

def can_open_area(user, area):
    if area == 'pastilhas' and user and user.get('role') in ('representante', 'cliente'):
        return False
    return auth.has(user, area)

@app.middleware('http')
async def enforce_access(request: Request, call_next):
    path=unquote(request.url.path).lstrip('/')
    if '\x00' in path or '\\' in path or any(part == '..' for part in path.split('/')):
        return JSONResponse({'detail':'Caminho inválido.'}, status_code=400)
    if path.startswith('api/'):
        if path in ('api/health','api/auth/login','api/auth/me','api/auth/logout'):
            return await call_next(request)
        if path.startswith('api/admin/'):
            if not auth.has(current_user(request),'admin'):
                return JSONResponse({'detail':'Acesso administrativo negado.'},status_code=403)
            if request.method in ('POST','PUT','PATCH','DELETE'):
                _,session=auth.get_session(request.cookies.get(auth.COOKIE))
                if not session or request.headers.get('X-CSRF-Token')!=session['csrf']:
                    return JSONResponse({'detail':'Token CSRF inválido.'},status_code=403)
            return await call_next(request)
        is_request_api = (
            path == 'api/solicitacoes'
            or path.startswith('api/solicitacoes/')
            or path.startswith('api/fichas/')
        )
        if is_request_api:
            user=current_user(request)
            if not auth.has(user,'automacao'):
                return JSONResponse({'detail':'Acesso à Automação negado.'},status_code=403)
            if request.method in ('POST','PUT','PATCH','DELETE'):
                _,session=auth.get_session(request.cookies.get(auth.COOKIE))
                if not session or request.headers.get('X-CSRF-Token')!=session['csrf']:
                    return JSONResponse({'detail':'Token CSRF inválido.'},status_code=403)
            if request.method=='GET':
                segments=path.split('/')
                if len(segments)>2 and segments[2] not in ('export',):
                    folder=_find_request_folder(segments[2])
                    if folder and (folder/'manifest.json').is_file():
                        try: owner=json.loads((folder/'manifest.json').read_text(encoding='utf-8')).get('owner_user_id')
                        except Exception: owner=None
                        if owner!=user['id'] and not auth.has(user,'admin'):
                            return JSONResponse({'detail':'Esta solicitação pertence a outro usuário.'},status_code=403)
            return await call_next(request)
        return JSONResponse({'detail':'Endpoint indisponível.'},status_code=404)
    # Reject attempts to fetch credentials directly, regardless of hosting mistakes.
    if path in PRIVATE_FILES or path.endswith('/usuarios.json') or path.endswith('/usuarios.json.part'):
        return JSONResponse({'detail':'Arquivo privado.'},status_code=404)
    if path in ('','index.html') or path in PUBLIC_FILES or path in PUBLIC_AREA_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES):
        area = PUBLIC_AREA_PATHS.get(path)
        user = current_user(request) if area else None
        if user and not can_open_area(user, area):
            return JSONResponse({'detail':'Você não tem permissão para acessar esta área.'},status_code=403)
        return await call_next(request)
    user=current_user(request)
    if not user:
        if path.endswith('.html') or path in PAGES:
            return RedirectResponse('/index.html?next='+quote('/'+path,safe=''),status_code=303)
        return JSONResponse({'detail':'Faça login.'},status_code=401)
    required_areas = PROTECTED_DATA_AREAS.get(path)
    if required_areas is not None:
        if not any(can_open_area(user, area) for area in required_areas):
            return JSONResponse({'detail':'Você não tem permissão para acessar estes dados.'},status_code=403)
        return await call_next(request)
    if path.startswith('representantes/') or path.startswith('clientes/'):
        bits=path.split('/')
        category='representante' if bits[0]=='representantes' else 'cliente'
        if len(bits)<2 or not can_open_subsite(user,category,bits[1]):
            return JSONResponse({'detail':'Catálogo restrito.'},status_code=403)
        return await call_next(request)
    area=PAGES.get(path)
    if not area:
        if path.startswith('data/') or path.startswith('js/') or path.startswith('imagens/') or path.startswith('pastilhas/'):
            if not any(auth.has(user,x) for x in ('catalogo','pastilhas','automacao','cores_preview')):
                return JSONResponse({'detail':'Sem permissão para os dados.'},status_code=403)
        # other images/CSS/fonts are covered by login
        return await call_next(request)
    if not can_open_area(user,area):
        return JSONResponse({'detail':'Você não tem permissão para acessar esta área.'},status_code=403)
    return await call_next(request)

LOGIN_ATTEMPTS={}
DUMMY_PASSWORD_HASH = auth.password_hash('invalid-login-placeholder')

@app.post('/api/auth/login')
def auth_login(request:Request, payload:dict=Body(...)):
    username=str(payload.get('username','')).strip()
    password=str(payload.get('password',''))
    ip=request.client.host if request.client else 'local'
    if len(username) > 64 or len(password) > 512:
        raise HTTPException(401,'Usuário ou senha incorretos.')
    # Small dev-server rate limit; replace with proxy/distributed control in production.
    now=time.time()
    rate_key=f'{ip}:{username.casefold()}'
    attempted=[t for t in LOGIN_ATTEMPTS.get(rate_key,[]) if now-t<300]
    if len(attempted)>=15: raise HTTPException(429,'Muitas tentativas. Aguarde 5 minutos.')
    user=auth.find_user(username,auth.load_users()['usuarios'])
    stored_hash=user.get('password_hash','') if user else DUMMY_PASSWORD_HASH
    valid=bool(user and user.get('ativo') and auth.verify_password(password,stored_hash))
    if not valid:
        LOGIN_ATTEMPTS[rate_key]=attempted+[now]
        raise HTTPException(401,'Usuário ou senha incorretos.')
    LOGIN_ATTEMPTS.pop(rate_key,None)
    token,csrf=auth.create_session(user)
    response=JSONResponse({'user':auth.safe_user(user),'csrf':csrf})
    response.set_cookie(auth.COOKIE,token,httponly=True,samesite='lax',secure=os.environ.get('AUTOMACAO_HTTPS','0')=='1',max_age=auth.LIFETIME,path='/')
    return response

@app.get('/api/auth/me')
def auth_me(request:Request):
    user,session=auth.get_session(request.cookies.get(auth.COOKIE))
    if not user: raise HTTPException(401,'Não autenticado.')
    return {'user':auth.safe_user(user),'csrf':session['csrf']}

@app.post('/api/auth/logout')
def auth_logout(request:Request):
    auth.destroy_session(request.cookies.get(auth.COOKIE))
    response=JSONResponse({'ok':True})
    response.delete_cookie(auth.COOKIE,path='/')
    return response

@app.get('/api/admin/usuarios')
def admin_list_users(request:Request):
    must_admin(request)
    users=auth.load_users()['usuarios']
    return {'usuarios':[auth.safe_user(u) for u in users],'areas':list(auth.AREAS),'roles':list(auth.ROLE_DEFAULTS)}

@app.post('/api/admin/usuarios')
def admin_modify_users(request:Request, payload:dict=Body(...)):
    actor=must_admin(request)
    action=payload.get('action','update')
    db=auth.load_users()
    users=db['usuarios']
    if action=='create':
        username=str(payload.get('username','')).strip()
        password=str(payload.get('password',''))
        role=payload.get('role','funcionario')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', username) or len(password)<8 or len(password)>512:
            raise HTTPException(400,'Informe usuário e senha com ao menos 8 caracteres.')
        if auth.find_user(username,users): raise HTTPException(409,'Usuário já existe.')
        if role not in auth.ROLE_DEFAULTS: raise HTTPException(400,'Perfil inválido.')
        user={'id':'u_'+uuid.uuid4().hex,'nome':str(payload.get('nome') or username)[:100],
              'username':username,'slug':str(payload.get('slug') or '')[:100],
              'password_hash':auth.password_hash(password),'role':role,
              'permissoes':list(auth.ROLE_DEFAULTS[role]),'ativo':True}
        users.append(user)
    elif action=='update':
        user=next((u for u in users if u['id']==payload.get('id')),None)
        if not user: raise HTTPException(404,'Usuário não encontrado.')
        role=payload.get('role',user['role'])
        permissions=payload.get('permissoes',user.get('permissoes',[]))
        if role not in auth.ROLE_DEFAULTS: raise HTTPException(400,'Perfil inválido.')
        if not isinstance(permissions,list) or any(p not in auth.AREAS for p in permissions):
            raise HTTPException(400,'Permissões inválidas.')
        active=bool(payload.get('ativo',user.get('ativo',True)))
        if user['id']==actor['id'] and (not active or 'admin' not in permissions):
            raise HTTPException(400,'Você não pode retirar seu próprio acesso administrativo.')
        was_active_admin=bool(user.get('ativo') and 'admin' in user.get('permissoes',[]))
        will_be_active_admin=bool(active and 'admin' in permissions)
        if was_active_admin and not will_be_active_admin:
            active_admins=sum(1 for row in users if row.get('ativo') and 'admin' in row.get('permissoes',[]))
            if active_admins <= 1:
                raise HTTPException(400,'Mantenha pelo menos um administrador ativo.')
        if payload.get('password') and len(str(payload['password']))>512:
            raise HTTPException(400,'Nova senha muito longa.')
        user.update(role=role,permissoes=sorted(set(permissions)),ativo=active)
        if payload.get('nome') is not None:user['nome']=str(payload['nome'])[:100]
        if payload.get('password'):
            if len(str(payload['password']))<8: raise HTTPException(400,'Nova senha muito curta.')
            user['password_hash']=auth.password_hash(str(payload['password']))
    else:raise HTTPException(400,'Ação desconhecida.')
    auth.save_users(db)
    return {'ok':True}

@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "automacao",
        "max_upload_mb": MAX_UPLOAD_MB,
        "max_total_upload_mb": MAX_TOTAL_UPLOAD_MB,
    }


@app.post("/api/solicitacoes/export")
@app.post("/api/fichas/export")
async def export_request(
    request: Request,
    metadata: str = Form(...),
    preview: UploadFile | None = File(None),
    art_files: list[UploadFile] | None = File(None),
    other_base: UploadFile | None = File(None),
) -> dict[str, Any]:
    content_length = request.headers.get('content-length')
    if content_length and content_length.isdigit() and int(content_length) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail='O envio excede o limite total permitido.')
    if len(metadata.encode('utf-8')) > MAX_METADATA_BYTES:
        raise HTTPException(status_code=413, detail='Metadados da solicitação muito grandes.')
    try:
        parsed = json.loads(metadata)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"metadata JSON inválido: {exc.msg}",
        )

    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=400,
            detail="metadata precisa ser um objeto JSON.",
        )

    item = parsed.get("item")
    if not isinstance(item, dict):
        raise HTTPException(
            status_code=400,
            detail="metadata.item ausente ou inválido.",
        )

    if item.get("type") not in ("button", "other"):
        raise HTTPException(status_code=400, detail="Tipo de item inválido.")
    if item.get("type") == "button":
        if not all(str(item.get(k) or "").strip() for k in ("reference", "size_tam", "color")):
            raise HTTPException(status_code=400, detail="Informe referência, TAM e cor.")
        parsed = _complete_button_metadata(parsed)
        item = parsed["item"]
    if preview is None:
        raise HTTPException(status_code=400, detail="Prévia PNG obrigatória para gerar a Ficha.")
    if item.get("type") == "other" and other_base is None:
        raise HTTPException(status_code=400, detail="Outro item exige imagem base.")
    if not art_files:
        raise HTTPException(status_code=400, detail="Envie pelo menos uma arte da personalização.")
    if len(art_files) > MAX_ART_FILES:
        raise HTTPException(status_code=400, detail=f"Máximo de {MAX_ART_FILES} artes por ficha.")
    owner_user = must_login(request)
    request_id = _new_request_id(parsed)
    folder = _new_request_folder(request_id)
    files: dict[str, Any] = {}
    total_upload_bytes = 0

    try:
        if preview is not None:
            files["preview"] = await _save_upload(
                preview,
                folder,
                "preview",
                {"image/png": ".png"},
            )
            total_upload_bytes += files['preview']['size_bytes']

        if other_base is not None:
            files["other_base"] = await _save_upload(
                other_base,
                folder,
                "item_base",
                IMAGE_TYPES,
            )
            total_upload_bytes += files['other_base']['size_bytes']

        saved_arts = []
        for index, upload in enumerate(art_files or [], start=1):
            saved = await _save_upload(
                upload,
                folder,
                f"arte_{index:02d}",
                IMAGE_TYPES,
            )
            saved["layer"] = index
            saved_arts.append(saved)
            total_upload_bytes += saved['size_bytes']
            if total_upload_bytes > MAX_TOTAL_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail='O total de arquivos excede o limite permitido.')

        if saved_arts:
            files["artes"] = saved_arts

        created_at = datetime.now().astimezone().isoformat(
            timespec="seconds"
        )

        # O PDF é gerado antes de afirmar sucesso. Não depende de Blender.
        preview_path = folder / files["preview"]["filename"]
        artwork_paths = [folder / row["filename"] for row in saved_arts]
        pdf_path = folder / "ficha_tecnica.pdf"
        render_ficha(
            pdf_path,
            metadata=parsed,
            preview_path=preview_path,
            art_paths=artwork_paths,
            logo_path=DOCS_DIR / "logo_simbolo.jpeg",
            request_id=request_id,
        )
        html_path = folder / "ficha_tecnica.html"
        if html_path.is_file():
            files["ficha_html"] = {
                "filename": "ficha_tecnica.html",
                "content_type": "text/html; charset=utf-8",
                "size_bytes": html_path.stat().st_size,
                "sha256": hashlib.sha256(html_path.read_bytes()).hexdigest(),
            }
        digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        files["ficha_pdf"] = {
            "filename": "ficha_tecnica.pdf",
            "content_type": "application/pdf",
            "size_bytes": pdf_path.stat().st_size,
            "sha256": digest,
        }

        manifest = {
            "schema_version": 2,
            "owner_user_id": owner_user["id"],
            "id": request_id,
            "created_at": created_at,
            "updated_at": created_at,
            "status": "pdf_ready",
            "metadata": parsed,
            "files": files,
            "workflow": {
                "stage": "pdf_ready",
                "assigned_to": None,
            },
            "history": [{
                "at": created_at,
                "status": "pdf_ready",
                "note": "Ficha PDF gerada e solicitação recebida.",
                "actor": owner_user.get("nome") or owner_user.get("username"),
            }],
            "pipeline": {
                "current_stage": "ficha_pdf_generated",
                "ficha_pdf": "ready",
            },
        }

        # Stable machine-readable input for future Blender worker.
        (folder / "solicitacao.json").write_text(
            json.dumps(
                parsed,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        _write_manifest(folder, manifest)

        return {
            **_public_manifest(manifest),
            "relative_storage_path": str(
                folder.relative_to(STORAGE_ROOT)
            ).replace("\\", "/"),
            "pdf_url": f"/api/solicitacoes/{request_id}/pdf",
        }

    except Exception:
        # No partially-saved request packages.
        shutil.rmtree(folder, ignore_errors=True)
        raise


@app.get("/api/solicitacoes")
def list_requests(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
) -> dict[str, Any]:
    user = must_login(request)
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))
    wanted_status = str(status or "").strip()
    if wanted_status and wanted_status not in REQUEST_STATUSES:
        raise HTTPException(status_code=400, detail="Status de solicitação inválido.")

    rows: list[dict[str, Any]] = []
    is_admin = auth.has(user, "admin")
    for folder, manifest in _iter_request_manifests():
        if manifest.get("owner_user_id") != user["id"] and not is_admin:
            continue
        if wanted_status and manifest.get("status") != wanted_status:
            continue
        row = _public_manifest(manifest)
        row["pdf_url"] = (
            f"/api/solicitacoes/{manifest['id']}/pdf"
            if (folder / "ficha_tecnica.pdf").is_file()
            else None
        )
        rows.append(row)

    rows.sort(
        key=lambda row: row.get("updated_at") or row.get("created_at") or "",
        reverse=True,
    )
    total = len(rows)
    return {
        "items": rows[offset:offset + limit],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.patch("/api/solicitacoes/{request_id}")
def update_request(
    request_id: str,
    request: Request,
    payload: dict = Body(...),
) -> dict[str, Any]:
    actor = must_admin(request)
    folder = _find_request_folder(request_id)
    manifest = _read_manifest(folder) if folder else None
    if folder is None or manifest is None:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada.")

    requested_status = payload.get("status")
    new_status = (
        str(requested_status).strip()
        if requested_status is not None
        else str(manifest.get("status") or "pdf_ready")
    )
    if new_status not in REQUEST_STATUSES:
        raise HTTPException(status_code=400, detail="Status de solicitação inválido.")

    note = _safe_text(payload.get("note"), 2000)
    assigned_to = payload.get("assigned_to")
    if assigned_to is not None:
        assigned_to = _safe_text(assigned_to, 120) or None
    if requested_status is None and not note and assigned_to is None:
        raise HTTPException(status_code=400, detail="Informe status, observação ou responsável.")

    changed_at = datetime.now().astimezone().isoformat(timespec="seconds")
    workflow = manifest.get("workflow")
    if not isinstance(workflow, dict):
        workflow = {}
    workflow["stage"] = new_status
    if assigned_to is not None or "assigned_to" in payload:
        workflow["assigned_to"] = assigned_to

    history = manifest.get("history")
    if not isinstance(history, list):
        history = []
    history.append({
        "at": changed_at,
        "status": new_status,
        "note": note,
        "actor": actor.get("nome") or actor.get("username"),
    })

    manifest["status"] = new_status
    manifest["updated_at"] = changed_at
    manifest["workflow"] = workflow
    manifest["history"] = history[-100:]
    pipeline = manifest.get("pipeline")
    if not isinstance(pipeline, dict):
        pipeline = {}
    pipeline["current_stage"] = new_status
    manifest["pipeline"] = pipeline
    _write_manifest(folder, manifest)

    return {
        **_public_manifest(manifest),
        "pdf_url": f"/api/solicitacoes/{request_id}/pdf"
        if (folder / "ficha_tecnica.pdf").is_file()
        else None,
    }


@app.get("/api/solicitacoes/{request_id}")
def get_request(request_id: str) -> dict[str, Any]:
    folder = _find_request_folder(request_id)

    if folder is None:
        raise HTTPException(
            status_code=404,
            detail="Solicitação não encontrada.",
        )

    manifest_path = folder / "manifest.json"

    if not manifest_path.is_file():
        raise HTTPException(
            status_code=500,
            detail="Solicitação sem manifest.json.",
        )

    manifest = _read_manifest(folder)
    if manifest is None:
        raise HTTPException(status_code=500, detail="Manifesto inválido.")

    return {
        **_public_manifest(manifest),
        "pdf_url": f"/api/solicitacoes/{request_id}/pdf" if (folder / "ficha_tecnica.pdf").is_file() else None,
        "relative_storage_path": str(
            folder.relative_to(STORAGE_ROOT)
        ).replace("\\", "/"),
    }


@app.get("/api/solicitacoes/{request_id}/pdf")
def get_ficha_pdf(request_id: str, download: int = 0):
    folder = _find_request_folder(request_id)
    if folder is None or not (folder / "ficha_tecnica.pdf").is_file():
        raise HTTPException(status_code=404, detail="Ficha PDF não encontrada.")
    path = folder / "ficha_tecnica.pdf"
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": ("attachment" if download else "inline") + '; filename="ficha_tecnica.pdf"'},
    )


@app.get("/api/solicitacoes/{request_id}/files/{filename}")
def download_request_file(
    request_id: str,
    filename: str,
):
    folder = _find_request_folder(
        request_id
    )

    if folder is None:
        raise HTTPException(
            status_code=404,
            detail="Solicitação não encontrada.",
        )

    # Basename-only: blocks ../ path traversal.
    if Path(filename).name != filename:
        raise HTTPException(
            status_code=400,
            detail="Nome de arquivo inválido.",
        )

    target = (folder / filename).resolve()

    if (
        target.parent != folder.resolve()
        or not target.is_file()
    ):
        raise HTTPException(
            status_code=404,
            detail="Arquivo não encontrado.",
        )

    return FileResponse(
        target,
        filename=target.name,
    )


# API routes are declared before this catch-all static mount.
app.mount(
    "/",
    StaticFiles(
        directory=DOCS_DIR,
        html=True,
    ),
    name="site",
)


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get(
        "AUTOMACAO_HOST",
        "127.0.0.1",
    )
    port = int(
        os.environ.get(
            "AUTOMACAO_PORT",
            "8000",
        )
    )

    print("=" * 72)
    print("BRASIL BOTOES - CATALOGO + AUTOMACAO SERVER")
    print(f"Site:    http://{host}:{port}/")
    print(f"Autom.:  http://{host}:{port}/automacao.html")
    print(f"Storage: {STORAGE_ROOT}")
    print("CTRL+C para encerrar.")
    print("=" * 72)

    uvicorn.run(
        app,
        host=host,
        port=port,
    )
