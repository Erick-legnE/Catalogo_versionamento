"""Process queued site personalizations in a separate Blender process.

The FastAPI application places a request in ``rendering_3d``.  This worker
claims that request, invokes Blender once per native text layer, and writes the
result back into the request folder.  It is intentionally a separate process:
Blender is a desktop application and must not run inside an HTTP request.

Typical Windows usage:
    $env:AUTOMACAO_BLENDER_EXE = 'C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe'
    $env:AUTOMACAO_BLENDER_BASE_DIR = 'D:\\BrasilBotoesData\\base_blends'
    python scripts\\blender_worker.py --loop
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
STORAGE_ROOT = Path(os.environ.get("AUTOMACAO_STORAGE_DIR", ROOT / "server_data" / "solicitacoes")).resolve()
BLENDER_SCRIPT = Path(os.environ.get("AUTOMACAO_BLENDER_SCRIPT", ROOT / "scripts" / "blender_personalizado.py")).resolve()
BLENDER_EXE = Path(os.environ.get("AUTOMACAO_BLENDER_EXE", "blender")).resolve() if os.environ.get("AUTOMACAO_BLENDER_EXE") else Path("blender")
BASE_DIR = Path(os.environ.get("AUTOMACAO_BLENDER_BASE_DIR", ROOT / "output" / "base_blends")).resolve()
TIMEOUT_SECONDS = max(60, int(os.environ.get("AUTOMACAO_BLENDER_TIMEOUT_SECONDS", "1800")))


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def write_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def manifests(root: Path = STORAGE_ROOT):
    if not root.is_dir():
        return
    for path in root.glob("*/*/*/manifest.json"):
        manifest = read_json(path)
        if manifest and manifest.get("id"):
            yield path.parent, manifest


def text_layers(metadata: dict[str, Any]) -> list[int]:
    personalization = metadata.get("personalization") or {}
    assets = personalization.get("assets") if isinstance(personalization, dict) else []
    return [
        int(asset.get("layer"))
        for asset in assets or []
        if isinstance(asset, dict)
        and asset.get("kind") == "text"
        and str(asset.get("text") or "").strip()
        and str(asset.get("layer") or "").isdigit()
    ]


def resolve_base_blend(metadata: dict[str, Any], base_dir: Path = BASE_DIR) -> Path:
    item = metadata.get("item") or {}
    reference = str(item.get("reference") or "").strip()
    size = str(item.get("size_tam") or "").strip()
    if not reference or not size:
        raise RuntimeError("metadata.item.reference and metadata.item.size_tam are required")
    candidates = [
        base_dir / f"button_{reference}_{size}.blend",
        base_dir / f"base_{reference}_{size}.blend",
        base_dir / f"{reference}_{size}.blend",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise RuntimeError(f"No base Blender file found for reference={reference}, size={size} in {base_dir}")


def build_plan(folder: Path, manifest: dict[str, Any], base_dir: Path = BASE_DIR) -> dict[str, Any]:
    request_path = folder / "solicitacao.json"
    metadata = read_json(request_path)
    if metadata is None:
        raise RuntimeError("solicitacao.json is missing or invalid")
    layers = text_layers(metadata)
    if not layers:
        raise RuntimeError("No native text layers are available for Blender")
    from scripts.blender_personalizado import automation_layer_settings
    layer_contexts = [automation_layer_settings(request_path, layer) for layer in layers]
    return {
        "folder": folder,
        "request_path": request_path,
        "base_blend": resolve_base_blend(metadata, base_dir),
        "layers": layers,
        "layer_contexts": layer_contexts,
        "script": BLENDER_SCRIPT,
    }


def validate_blender_outputs(output: Path, report: Path, render: Path) -> dict[str, Any]:
    """Require the evidence needed before a request can become rendered_3d."""
    if not output.is_file():
        raise RuntimeError(f"Blender did not create the output blend: {output.name}")
    if not report.is_file():
        raise RuntimeError(f"Blender did not create the geometry report: {report.name}")
    if not render.is_file():
        raise RuntimeError(f"Blender did not create the preview render: {render.name}")
    data = read_json(report)
    if not isinstance(data, dict):
        raise RuntimeError(f"The Blender report is missing or invalid: {report.name}")
    if data.get("geometry") == "BOOLEAN":
        diagnostics = data.get("geometry_diagnostics") or {}
        before = int(diagnostics.get("body_vertices_before") or 0)
        after = int(diagnostics.get("body_vertices_after") or 0)
        if after <= before:
            raise RuntimeError("The Boolean report does not prove that the button mesh changed")
        if int(diagnostics.get("boundary_edges") or 0) or int(diagnostics.get("non_manifold_edges") or 0):
            raise RuntimeError("The Boolean report contains invalid topology")
    return data


def append_history(manifest: dict[str, Any], status: str, note: str) -> None:
    history = manifest.get("history") if isinstance(manifest.get("history"), list) else []
    history.append({"at": now(), "status": status, "note": note, "actor": "blender_worker"})
    manifest["history"] = history[-100:]
    manifest["status"] = status
    manifest["updated_at"] = now()


def claim(folder: Path) -> Path | None:
    lock = folder / ".blender.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"pid": os.getpid(), "at": now()}))
        return lock
    except FileExistsError:
        return None


def process(folder: Path, manifest: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    lock = claim(folder)
    if lock is None:
        return {"id": manifest["id"], "skipped": "locked"}
    try:
        plan = build_plan(folder, manifest)
        if dry_run:
            return {"id": manifest["id"], "base_blend": str(plan["base_blend"]), "layers": plan["layers"], "fonts": [context.get("font_source") for context in plan["layer_contexts"]], "dry_run": True}
        blender_dir = folder / "blender"
        blender_dir.mkdir(exist_ok=True)
        current = plan["base_blend"]
        step_reports: list[str] = []
        step_details: list[dict[str, Any]] = []
        for index, layer in enumerate(plan["layers"], start=1):
            output = blender_dir / f"step_{index:02d}.blend"
            report = blender_dir / f"step_{index:02d}.json"
            render = blender_dir / f"step_{index:02d}.png"
            command = [
                str(BLENDER_EXE), "--background", str(current), "--python", str(plan["script"]), "--",
                "--output", str(output), "--automation-json", str(plan["request_path"]),
                "--automation-layer", str(layer), "--report", str(report), "--render", "--preview-camera",
            ]
            completed = subprocess.run(command, cwd=str(folder), text=True, capture_output=True, timeout=TIMEOUT_SECONDS, check=False)
            (blender_dir / f"step_{index:02d}.stdout.txt").write_text(completed.stdout or "", encoding="utf-8")
            (blender_dir / f"step_{index:02d}.stderr.txt").write_text(completed.stderr or "", encoding="utf-8")
            if completed.returncode != 0:
                raise RuntimeError(f"Blender failed for layer {layer} with exit code {completed.returncode}")
            step_details.append(validate_blender_outputs(output, report, render))
            current = output
            step_reports.append(str(report.relative_to(folder)).replace("\\", "/"))

        final_blend = blender_dir / "personalized.blend"
        shutil.copy2(current, final_blend)
        pipeline = manifest.get("pipeline") if isinstance(manifest.get("pipeline"), dict) else {}
        pipeline.update({
            "current_stage": "blender_finished",
            "blender": {
                "status": "ready",
                "blend": str(final_blend.relative_to(folder)).replace("\\", "/"),
                "reports": step_reports,
                "renders": [str((blender_dir / f"step_{index:02d}.png").relative_to(folder)).replace("\\", "/") for index in range(1, len(step_reports) + 1)],
                "steps": step_details,
                "blend_url": f"/api/solicitacoes/{manifest['id']}/blender/personalized.blend",
                "preview_url": f"/api/solicitacoes/{manifest['id']}/blender/step_{len(step_reports):02d}.png",
                "report_url": f"/api/solicitacoes/{manifest['id']}/blender/step_{len(step_reports):02d}.json",
            },
        })
        manifest["pipeline"] = pipeline
        append_history(manifest, "rendered_3d", "Blender gerou o arquivo personalizado e os relatÃ³rios.")
        write_json(folder / "manifest.json", manifest)
        return {"id": manifest["id"], "status": "rendered_3d", "blend": str(final_blend)}
    except Exception as exc:
        manifest["pipeline"] = {**(manifest.get("pipeline") if isinstance(manifest.get("pipeline"), dict) else {}), "current_stage": "blender_failed", "blender": {"status": "error", "message": str(exc)}}
        append_history(manifest, "render_error", f"Falha no Blender: {exc}")
        write_json(folder / "manifest.json", manifest)
        return {"id": manifest.get("id"), "status": "render_error", "error": str(exc)}
    finally:
        lock.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--request-id")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=float(os.environ.get("AUTOMACAO_BLENDER_POLL_SECONDS", "5")))
    args = parser.parse_args()
    if not args.loop and not args.once:
        args.once = True
    while True:
        found = False
        for folder, manifest in manifests():
            if args.request_id and manifest.get("id") != args.request_id:
                continue
            if manifest.get("status") != "rendering_3d":
                continue
            found = True
            print(json.dumps(process(folder, manifest, dry_run=args.dry_run), ensure_ascii=False), flush=True)
        if not args.loop or found or args.dry_run:
            return
        time.sleep(max(0.5, args.poll_seconds))


if __name__ == "__main__":
    main()
