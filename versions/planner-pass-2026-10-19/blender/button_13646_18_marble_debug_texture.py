"""Button Texture Pipeline — STAGE D v2: photographic exterior, 3D marble cuts, softer exposure tint.

Blender 4.3+/5.x; NumPy (Blender bundled). No OpenCV, Pillow, or AI inside Blender.
Fresh shader implementation: NEVER copies/reuses the old v7 shader node trees.

Inputs: saved Button_3D with dxf_y_min/max, dxf_surface_type and Button_Texture;
side photo (required); front/back photos (REQUIRED for Stage C);
optional layer recipe JSON. Stage D preserves the photographs on exterior faces and adds 3D procedural marbling for MARBLED materials.

Stage D v2 defaults to PHOTO with gentler cut exposure, while MARBLE_3D remains available for diagnostics.
Run in Blender > Scripting > Open > Run Script, or:
  blender --background "path/to/pochat.blend" --python "path/to/button_texture_stage_c_photographic.py"

Stage D modes:
  PHOTO        - real face/side photographs with local-Y cut material (default)
  EXPOSURE     - black for photo-preserved areas, white when layer-depth threshold crossed
  LAYER_IDS    - flat bright physical layer IDs (same as Stage B)
  LAYER_COLORS - true-Y estimated physical colors without the photos
  Y_GRADIENT   - diagnostic local-Y greyscale
  SEMANTIC     - face semantic regions
  MARBLE_3D    - show only the procedural 3D marble / physical material

For SOLID/LAYERED, Stage D behaves like Stage C. For MARBLED, the physical cut material is generated procedurally in 3D from the detected palette and approximate source pattern scale.

Exposure limitation: a final mesh cannot always prove whether a low-Y FRONT
polygon came from an original DXF relief or a later boolean cut. In Stage C
exposure is defined by physically crossing out of the photographed outer
material layer. The procedural f(t) is always continuous and independent
of UV V, including the shading of hole walls.
"""

import bpy
import json
import math
import os
from collections import Counter

import numpy as np

# ============================================================================
# ONE USER CONFIG BLOCK — edit here, not in the functions below
# ============================================================================
BUTTON_OBJECT_NAME = 'Button_3D'
UV_MAP_NAME = 'Button_Texture'
SURFACE_ATTRIBUTE_NAME = 'dxf_surface_type'
COLOR_CODE = 'C2622'
IMAGE_DIRECTORY = r''                   # optional folder with photos
FRONT_IMAGE_PATH = 'C:\\Users\\Aprendiz Financeiro\\Downloads\\Erick\\Fotos\\fotos_o_frente_verso\\C2622 - Frente.png'
VERSO_IMAGE_PATH = 'C:\\Users\\Aprendiz Financeiro\\Downloads\\Erick\\Fotos\\fotos_o_frente_verso\\C2622 - Verso.png'
SIDE_IMAGE_PATH = 'C:\\Users\\Aprendiz Financeiro\\Downloads\\Erick\\Fotos\\button_results\\pastilhas_C2622_lado_clean.png'
LAYER_RECIPE_JSON_PATH = r''             # optional JSON with {"C2667": {"layers": ...}}

FRONT_FLIP_U = False
FRONT_FLIP_V = False
VERSO_FLIP_U = True
VERSO_FLIP_V = False
SIDE_FLIP_U = False
SIDE_FLIP_V = False                   # manually reverse auto-detected Y orientation
SIDE_ORIENTATION = 'AUTO'              # AUTO, START_IS_BACK, START_IS_FRONT
SIDE_CROP_OVERRIDE = None             # (left, top, right, bottom) in 0..1; if needed

DEBUG_MODE = 'MARBLE_3D'
USE_EMISSION = True                   # unlit diagnostic modes; PHOTO uses Principled BSDF
MAX_ANALYSIS_IMAGE_DIMENSION = 1100    # downsample via NumPy strides for huge photos
SAMPLE_U_COUNT = 150
SAMPLE_Y_COUNT = 112
MIN_ALPHA = 0.95                      # prevents partial background transparency
IGNORE_END_U_FRACTION = 0.12          # avoid glare, hand and strip ends
WHITE_L_THRESHOLD = 92.0              # reject sparse bright glare, NOT white layers
WHITE_CHROMA_THRESHOLD = 9.0
GLARE_MAX_ROW_FRACTION = 0.32
SEGMENT_MIN_FRACTION = 0.07
MAX_LAYERS = 7
MIN_LAYER_DE = 10.0
CHANGE_POINT_PENALTY = 3300.0         # row-Lab SSE for each additional layer
SOLID_BETWEEN_RMS_MAX = 8.5
SOLID_WITHIN_RMS_MAX = 12.0
MARBLE_WITHIN_RMS_MIN = 10.0
# A marbled top band can coexist with a solid dark bottom band. A global
# variance ratio alone would mistake this for ordinary LAYERED material.
MARBLE_ROW_P80_DE_THRESHOLD = 18.0
MARBLE_ROW_MIN_FRACTION = 0.17
MARBLE_ROW_MIN_STREAK = 0.14
LAYER_COHERENCE_RATIO_MIN = 0.95       # between-row variance / within-row variance
PATTERN_PALETTE_COUNT = 3
Y_RANGE_TOLERANCE = 1e-4
FAIL_ON_SEMANTIC_MISMATCH = True

# ------------------- STAGE C PHOTOGRAPHIC SHADING -------------------
# The original face pixels are always kept if local Y lies in the outer layer.
# Once a recess crosses that layer's inner boundary, blend the original PHOTO
# toward the material physically exposed at t, with some photo micro-detail.
# 0.0 = never recolor front/back; 1.0 = layer color with photo luminance detail.
RECESSED_FACE_LAYER_STRENGTH = 0.35  # v2: less dramatic recoloring on exposed front/back ONLY; hole walls remain physical
PHOTO_MICRODETAIL_STRENGTH = 0.24  # preserve surface texture without changing layer identity
EXPOSURE_EDGE_FEATHER_T = 0.032    # v2: softer FRONT/VERSO photo-to-cut boundary, normalized t
LAYER_EDGE_FEATHER_T = 0.015       # visual softness between material layer colors
SIDE_PHOTO_LAYER_TINT = 0.03      # 0.0 gives exact side photo; keep small
FRONT_ROUGHNESS = 0.48
VERSO_ROUGHNESS = 0.48
SIDE_ROUGHNESS = 0.53
INTERIOR_ROUGHNESS = 0.61

# ------------------- STAGE D PROCEDURAL MARBLING -------------------
# Used ONLY when the detected/overridden material class is MARBLED.
# The shader uses Object coordinates so holes and faca cuts reveal a coherent
# continuous pattern rather than a flat color band.
MARBLE_COORD_SCALE_MULTIPLIER = 1.00   # global size correction for 3D pattern
MARBLE_DISTORTION = 0.85               # how much the veins wobble
MARBLE_FINE_NOISE_SCALE = 2.20         # relative fine-noise frequency
MARBLE_FINE_NOISE_STRENGTH = 0.25      # blend of secondary breakup
MARBLE_WAVE_SCALE = 1.45               # bands/veins density
MARBLE_WAVE_DISTORT = 4.5              # Blender wave distortion amount
MARBLE_PALETTE_SHARPNESS = 0.18        # 0=smooth mix, 1=sharper palette edges
MARBLE_CANDIDATE_LAYER_BLEND = 0.28    # preserve coarse Y-bias if candidate layers exist
MARBLE_SIDE_TINT = 0.08                # gentle tie between photographed side and 3D marble
MARBLE_PREVIEW_ROUGHNESS = 0.52        # debug-preview roughness for full procedural marble

# Pixel alignment: Blender builder uses planar X/Z UV for faces.
# Optional (u_min, v_min, u_max, v_max) sample window for photo textures.
FRONT_CROP_OVERRIDE = None
VERSO_CROP_OVERRIDE = None

# For SIDE, generate a rectified internal Blender image from the cleaned PNG.
# This is still the *real photo*, not a reconstructed color-band image.
SIDE_RECTIFIED_WIDTH = 768
SIDE_RECTIFIED_HEIGHT = 256
SIDE_SOURCE_U_RANGE = (0.10, 0.90)  # ignore unreliable photographed ends
SIDE_SOURCE_V_RANGE = (0.025, 0.975)
SAVE_PACK_IMAGES = True            # pack 3 photos + generated strip in saved .blend

# Re-runs replace all canonical slot materials transactionally and remove BTEX_* attributes.
REMOVE_LEGACY_V7_METADATA = True
GENERATE_FACE_CENTER_ATTRIBUTE = True   # BTEX_face_mid_t; informational ONLY
AUTO_SAVE_HEADLESS = True
OUTPUT_BLEND_PATH = 'C:\\Users\\Aprendiz Financeiro\\Downloads\\Erick\\site\\versions\\planner-pass-2026-10-19\\blender\\button_13646_18_marble_debug_textured.blend'
WRITE_JSON_REPORT = True
OUTPUT_REPORT_PATH = 'C:\\Users\\Aprendiz Financeiro\\Downloads\\Erick\\site\\versions\\planner-pass-2026-10-19\\blender\\button_13646_18_marble_debug_texture_report.json'

SLOT_NAMES = (
    'BTN_FRONT_EXTERNAL', 'BTN_VERSO_EXTERNAL',
    'BTN_SIDE_EXTERNAL', 'BTN_INTERIOR_CUT',
)
SEMANTIC_COLORS = (
    (0.95, 0.18, 0.13, 1.0), (0.12, 0.35, 0.95, 1.0),
    (0.15, 0.85, 0.33, 1.0), (0.95, 0.68, 0.10, 1.0),
)
LAYER_ID_COLORS = (
    (0.95, 0.14, 0.20, 1.0), (0.10, 0.77, 0.93, 1.0),
    (0.97, 0.76, 0.10, 1.0), (0.57, 0.25, 0.95, 1.0),
    (0.25, 0.88, 0.40, 1.0), (0.99, 0.41, 0.15, 1.0),
    (0.82, 0.39, 0.65, 1.0),
)
# ============================================================================

PREFIX = '[BUTTON TEX D]'


def log(message):
    print(f'{PREFIX} {message}', flush=True)


def clamp01(a):
    return np.clip(a, 0.0, 1.0)


def srgb_to_lab(rgb):
    """Vectorized D65 CIELAB conversion; input sRGB numbers in [0,1]."""
    rgb = clamp01(np.asarray(rgb, dtype=np.float64))
    lin = np.where(rgb <= 0.04045, rgb / 12.92,
                   np.power((rgb + 0.055) / 1.055, 2.4))
    x = (0.4124564 * lin[..., 0] + 0.3575761 * lin[..., 1]
         + 0.1804375 * lin[..., 2]) / 0.95047
    y = (0.2126729 * lin[..., 0] + 0.7151522 * lin[..., 1]
         + 0.0721750 * lin[..., 2])
    z = (0.0193339 * lin[..., 0] + 0.1191920 * lin[..., 1]
         + 0.9503041 * lin[..., 2]) / 1.08883
    xyz = np.stack((x, y, z), axis=-1)
    e = 216.0 / 24389.0
    k = 24389.0 / 27.0
    f = np.where(xyz > e, np.cbrt(xyz), (k * xyz + 16.0) / 116.0)
    return np.stack((116 * f[..., 1] - 16,
                     500 * (f[..., 0] - f[..., 1]),
                     200 * (f[..., 1] - f[..., 2])), axis=-1)


def lab_to_srgb(lab):
    """Convert one or multiple D65 Lab colors back to DISPLAY sRGB."""
    lab = np.asarray(lab, dtype=np.float64)
    fy = (lab[..., 0] + 16.0) / 116.0
    fx = fy + lab[..., 1] / 500.0
    fz = fy - lab[..., 2] / 200.0
    d = 6.0 / 29.0
    f = np.stack((fx, fy, fz), axis=-1)
    xyz = np.where(f > d, f ** 3, 3.0 * d * d * (f - 4.0 / 29.0))
    xyz = xyz * np.array([0.95047, 1.0, 1.08883])
    lin = np.stack((
        3.2404542 * xyz[..., 0] - 1.5371385 * xyz[..., 1] - 0.4985314 * xyz[..., 2],
       -0.9692660 * xyz[..., 0] + 1.8760108 * xyz[..., 1] + 0.0415560 * xyz[..., 2],
        0.0556434 * xyz[..., 0] - 0.2040259 * xyz[..., 1] + 1.0572252 * xyz[..., 2],
    ), axis=-1)
    lin = clamp01(lin)
    return clamp01(np.where(lin <= 0.0031308, 12.92 * lin,
                           1.055 * np.power(lin, 1.0 / 2.4) - 0.055))


def srgb_to_scene_linear(rgb):
    rgb = clamp01(np.asarray(rgb, dtype=np.float64))
    return np.where(rgb <= 0.04045, rgb/12.92,
                    np.power((rgb+0.055)/1.055, 2.4))


def rgb_hex(rgb):
    a = (np.rint(clamp01(rgb) * 255)).astype(int)
    return '#{:02X}{:02X}{:02X}'.format(*a[:3])


def lab_de(a, b):
    return float(np.linalg.norm(np.asarray(a) - np.asarray(b)))


def trimmed_lab(labs, trim=0.80):
    labs = np.asarray(labs, dtype=np.float64)
    if len(labs) == 0:
        raise ValueError('No material pixels remain after masking.')
    med = np.median(labs, axis=0)
    if len(labs) < 8:
        return med
    distance = np.linalg.norm(labs - med, axis=1)
    keep = distance <= np.quantile(distance, trim)
    return np.median(labs[keep], axis=0) if np.count_nonzero(keep) else med


def image_arrays(image):
    """Blender image -> (top-down RGBA). Non-Color prevents sRGB->linear sampling."""
    w, h = (int(v) for v in image.size)
    if w < 2 or h < 2:
        raise RuntimeError(f'Image {image.name!r} has invalid size {w}x{h}')
    rgba = np.empty(w * h * 4, dtype=np.float32)
    image.pixels.foreach_get(rgba)
    a = rgba.reshape(h, w, 4)[::-1, :, :].copy()
    jump = max(1, int(math.ceil(max(w, h) / max(64, MAX_ANALYSIS_IMAGE_DIMENSION))))
    return a[::jump, ::jump, :]


def load_photo(path, label):
    if not os.path.isfile(path):
        raise FileNotFoundError(f'{label} photograph not found: {path}')
    img = bpy.data.images.load(path, check_existing=True)
    try:
        img.colorspace_settings.name = 'Non-Color'
    except Exception as exc:
        log(f'WARNING: could not set Non-Color for Lab sampling: {exc}')
    arr = image_arrays(img)
    log(f'{label}: {os.path.basename(path)} | source={img.size[0]}x{img.size[1]} '
        f'| analysis={arr.shape[1]}x{arr.shape[0]}')
    return arr


def search_directories():
    roots = []
    if IMAGE_DIRECTORY:
        roots.append(bpy.path.abspath(IMAGE_DIRECTORY))
    if FRONT_IMAGE_PATH or VERSO_IMAGE_PATH or SIDE_IMAGE_PATH:
        for x in (FRONT_IMAGE_PATH, VERSO_IMAGE_PATH, SIDE_IMAGE_PATH):
            if x:
                roots.append(os.path.dirname(bpy.path.abspath(x)))
    if bpy.data.filepath:
        roots.append(os.path.dirname(bpy.data.filepath))
    if '__file__' in globals():
        roots.append(os.path.dirname(os.path.abspath(__file__)))
    roots.append(os.getcwd())
    return list(dict.fromkeys(os.path.normpath(x) for x in roots if x))


def resolve_photo(explicit, patterns, required):
    if explicit:
        path = bpy.path.abspath(explicit)
        if not os.path.isfile(path):
            raise FileNotFoundError(f'Configured image does not exist: {path}')
        return path
    for root in search_directories():
        for pattern in patterns:
            path = os.path.join(root, pattern)
            if os.path.isfile(path):
                return path
    if required:
        raise FileNotFoundError(
            f'No SIDE image found for {COLOR_CODE}. Set SIDE_IMAGE_PATH or '
            f'put the PNG alongside your .blend / .py. Search dirs: {search_directories()}')
    return None


def photo_paths():
    side = resolve_photo(SIDE_IMAGE_PATH, [
        f'pastilhas_{COLOR_CODE}_lado_clean.png',
        f'pastilhas_{COLOR_CODE}_lado_clean(1).png',
        f'pastilhas_{COLOR_CODE}_lado.png', f'{COLOR_CODE}_lado.png',
    ], True)
    front = resolve_photo(FRONT_IMAGE_PATH, [
        f'pastilha_{COLOR_CODE}.png', f'pastilha_{COLOR_CODE}_frente.png',
        f'pastilhas_{COLOR_CODE}_frente.png', f'{COLOR_CODE} - Frente.png',
    ], False)
    verso = resolve_photo(VERSO_IMAGE_PATH, [
        f'pastilha_{COLOR_CODE}_verso.png', f'pastilha_{COLOR_CODE}_fundo.png',
        f'pastilhas_{COLOR_CODE}_verso.png', f'{COLOR_CODE} - Verso.png',
    ], False)
    if front is None or verso is None:
        raise FileNotFoundError('Stage C requires FRONT and VERSO PNGs. Set image paths explicitly or put them alongside .blend.')
    return side, front, verso


def robust_face_color(rgba):
    h, w = rgba.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w]
    center = ((xs - (w-1)*.5) / (w*.5))**2 + ((ys - (h-1)*.5) / (h*.5))**2 < .4**2
    valid = center & (rgba[..., 3] > .90)
    if np.count_nonzero(valid) < 50:
        valid = rgba[..., 3] > .9
    if np.count_nonzero(valid) < 20:
        return None
    return trimmed_lab(srgb_to_lab(rgba[..., :3][valid]), 0.85)


def strip_mask(rgba):
    h, w = rgba.shape[:2]
    alpha = rgba[..., 3]
    # For cleaned PNGs transparency is a much better foreground indicator than RGB.
    mask = alpha >= MIN_ALPHA
    amount = np.count_nonzero(mask)
    if 100 < amount < 0.75 * h * w:
        return mask, 'alpha'
    # Fallback for fully opaque PNGs: subtract a border background color in Lab.
    lab = srgb_to_lab(rgba[..., :3])
    border = np.concatenate((lab[:max(2, h//16)].reshape(-1,3),
                             lab[-max(2, h//16):].reshape(-1,3),
                             lab[:, :max(2,w//16)].reshape(-1,3),
                             lab[:, -max(2,w//16):].reshape(-1,3)), axis=0)
    bg = trimmed_lab(border[::max(1, len(border)//3000)])
    delta = np.linalg.norm(lab - bg[None, None, :], axis=2)
    mask = (delta > 14.0) & (alpha > .05)
    if np.count_nonzero(mask) < 150:
        raise RuntimeError('Cannot reliably isolate side strip: use transparent PNG or SIDE_CROP_OVERRIDE.')
    log('WARNING: foreground estimated from border. White material may be confused with background; '
        'a cleaned transparent side PNG is strongly preferred.')
    return mask, 'background-Lab'


def strip_frame(rgba):
    h, w = rgba.shape[:2]
    mask, origin = strip_mask(rgba)
    if SIDE_CROP_OVERRIDE is not None:
        x0, y0, x1, y1 = (float(v) for v in SIDE_CROP_OVERRIDE)
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise ValueError('SIDE_CROP_OVERRIDE must be left, top, right, bottom in [0,1].')
        mask &= (np.arange(h)[:, None] >= y0*h) & (np.arange(h)[:, None] < y1*h)
        mask &= (np.arange(w)[None, :] >= x0*w) & (np.arange(w)[None, :] < x1*w)
    yy, xx = np.where(mask)
    if len(xx) < 150:
        raise RuntimeError('Less than 150 valid material pixels; cannot analyze side image.')
    pts = np.column_stack((xx.astype(np.float64), yy.astype(np.float64)))
    ctr = np.median(pts, axis=0)
    centered = pts - ctr
    # PCA major direction; robust trimming makes isolated alpha artifacts less harmful.
    for _ in range(2):
        cov = centered.T @ centered / max(1, len(centered))
        values, vecs = np.linalg.eigh(cov)
        major = vecs[:, int(np.argmax(values))]
        major /= max(np.linalg.norm(major), 1e-12)
        minor = np.array([-major[1], major[0]])
        p_major = centered @ major
        p_minor = centered @ minor
        bound_major = np.quantile(p_major, [.015, .985])
        bound_minor = np.quantile(p_minor, [.025, .975])
        sel = ((p_major >= bound_major[0]) & (p_major <= bound_major[1])
               & (p_minor >= bound_minor[0]) & (p_minor <= bound_minor[1]))
        pts = pts[sel]
        ctr = np.median(pts, axis=0)
        centered = pts - ctr
    if (abs(major[0]) >= abs(major[1]) and major[0] < 0) or \
       (abs(major[1]) > abs(major[0]) and major[1] < 0):
        major = -major
    minor = np.array([-major[1], major[0]])
    p_major = centered @ major
    p_minor = centered @ minor
    u0, u1 = np.quantile(p_major, [.008, .992])
    v0, v1 = np.quantile(p_minor, [.008, .992])
    if (u1-u0) < 1.4*(v1-v0):
        log('WARNING: strip aspect ratio is low. Automatic PCA orientation may be unreliable.')
    ctr = ctr + major*((u0+u1)*.5) + minor*((v0+v1)*.5)
    au = major*(u1-u0)*1.005
    av = minor*(v1-v0)*1.005
    if SIDE_FLIP_U:
        au = -au
    log(f'STRIP detection={origin}, center(px)={np.round(ctr, 1).tolist()}, '
        f'long-axis(px)={np.round(au,1).tolist()}, thickness-axis(px)={np.round(av,1).tolist()}, '
        f'aspect={np.linalg.norm(au)/max(np.linalg.norm(av),1):.2f}')
    return ctr, au, av


def bilinear_rgba(rgba, x, y):
    h, w = rgba.shape[:2]
    within = (x >= 0) & (x <= w - 1) & (y >= 0) & (y <= h - 1)
    x = np.clip(x, 0, w-1)
    y = np.clip(y, 0, h-1)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0+1, w-1), np.minimum(y0+1, h-1)
    dx, dy = (x-x0)[..., None], (y-y0)[..., None]
    sampled = (rgba[y0,x0]*(1-dx)*(1-dy) + rgba[y0,x1]*dx*(1-dy)
               + rgba[y1,x0]*(1-dx)*dy + rgba[y1,x1]*dx*dy)
    sampled[..., 3] *= within
    return sampled


def sample_strip(rgba, frame):
    ctr, au, av = frame
    u = np.linspace(IGNORE_END_U_FRACTION, 1-IGNORE_END_U_FRACTION, SAMPLE_U_COUNT)
    v = np.linspace(.018, .982, SAMPLE_Y_COUNT)
    uu, vv = np.meshgrid(u, v)
    px = ctr[0] + (uu-.5)*au[0] + (vv-.5)*av[0]
    py = ctr[1] + (uu-.5)*au[1] + (vv-.5)*av[1]
    samples = bilinear_rgba(rgba, px, py)
    good = samples[...,3] >= MIN_ALPHA
    log(f'ROI sampled material: {np.count_nonzero(good)}/{good.size} samples '
        f'({np.mean(good)*100:.1f}% valid before glare rejection).')
    if np.mean(good) < .30:
        raise RuntimeError('Side strip ROI poorly covered by valid pixels. '
                           'Check mask/strip orientation; set SIDE_CROP_OVERRIDE if necessary.')
    return samples, good


def row_profile(samples, good):
    labs = srgb_to_lab(samples[..., :3])
    n = labs.shape[0]
    rows = []
    spreads = []
    valid_rows = []
    accepted = []
    for i in range(n):
        p = labs[i][good[i]]
        if len(p) < max(7, int(.16*SAMPLE_U_COUNT)):
            rows.append([np.nan]*3)
            spreads.append(np.nan)
            valid_rows.append(False)
            continue
        chroma = np.linalg.norm(p[:,1:], axis=1)
        white = (p[:,0] > WHITE_L_THRESHOLD) & (chroma < WHITE_CHROMA_THRESHOLD)
        if np.mean(white) <= GLARE_MAX_ROW_FRACTION and np.any(~white):
            p = p[~white]
        center_l = np.median(p[:,0])
        high_glare = p[:,0] > center_l+19
        if np.mean(high_glare) < GLARE_MAX_ROW_FRACTION and np.count_nonzero(~high_glare)>6:
            p = p[~high_glare]
        representative = trimmed_lab(p)
        d = np.linalg.norm(p-representative, axis=1)
        d = d[d <= np.quantile(d, .85)] if len(d)>7 else d
        spread = float(np.mean(d*d)) if len(d) else 0.0
        rows.append(representative)
        spreads.append(spread)
        valid_rows.append(True)
        accepted.append(p)
    rows = np.asarray(rows, dtype=np.float64)
    spreads = np.asarray(spreads, dtype=np.float64)
    valid_rows = np.asarray(valid_rows, dtype=bool)
    if np.count_nonzero(valid_rows) < .63*n:
        raise RuntimeError(f'Only {np.count_nonzero(valid_rows)}/{n} valid thickness rows; '
                           'cannot classify physical layers. Check SIDE_CROP_OVERRIDE.')
    xi = np.arange(n)
    for channel in range(3):
        rows[:,channel] = np.interp(xi, xi[valid_rows], rows[valid_rows,channel])
    within_sq = float(np.median(spreads[valid_rows]))
    smoothed = rows.copy()
    for i in range(1, n-1):
        smoothed[i] = np.median(rows[max(0,i-2):min(n,i+3)], axis=0)
    mid = trimmed_lab(smoothed)
    between_sq = float(np.mean(np.sum((smoothed-mid)**2, axis=1)))
    return smoothed, np.vstack(accepted), within_sq, between_sq


def determine_orientation(rows, front_lab, verso_lab):
    """Return rows ordered back->front. Print both assignment costs."""
    start = trimmed_lab(rows[:max(5, len(rows)//9)])
    end = trimmed_lab(rows[-max(5,len(rows)//9):])
    forward_cost = reverse_cost = None
    if front_lab is not None and verso_lab is not None:
        forward_cost = lab_de(start, verso_lab) + lab_de(end, front_lab)
        reverse_cost = lab_de(start, front_lab) + lab_de(end, verso_lab)
        log(f'Orientation costs ΔE76: START=BACK {forward_cost:.2f}; '
            f'START=FRONT {reverse_cost:.2f}; margin={abs(forward_cost-reverse_cost):.2f}')
    flip = False
    if SIDE_ORIENTATION == 'START_IS_FRONT':
        flip = True
        source = 'manual: START_IS_FRONT'
    elif SIDE_ORIENTATION == 'START_IS_BACK':
        source = 'manual: START_IS_BACK'
    elif SIDE_ORIENTATION == 'AUTO':
        if forward_cost is None:
            source = 'AUTO not possible: missing front/back image; assumed START_IS_BACK'
            log('WARNING: side thickness orientation UNVERIFIED. Set SIDE_ORIENTATION manually.')
        else:
            flip = reverse_cost < forward_cost
            source = 'AUTO using photo similarity'
            if abs(forward_cost-reverse_cost) < 7.5:
                log('WARNING: FRONT and VERSO colors are too similar for reliable '
                    'orientation. Verify with distinct face photos or manual override.')
    else:
        raise ValueError('SIDE_ORIENTATION must be AUTO, START_IS_BACK, START_IS_FRONT.')
    if SIDE_FLIP_V:
        flip = not flip
        source += ' + SIDE_FLIP_V'
    log(f'Orientation decision: {source}; reverse_source_rows={flip}; '
        f't=0 BACK from {"source END" if flip else "source START"}, '
        f't=1 FRONT from {"source START" if flip else "source END"}.')
    return flip


def segment_rows(rows):
    """Contiguous piecewise-constant Lab fit: dynamic programming with min width."""
    n = len(rows)
    min_width = max(2, int(math.ceil(n*SEGMENT_MIN_FRACTION)))
    kmax = min(MAX_LAYERS, n//min_width)
    pref = np.vstack([np.zeros(3), np.cumsum(rows, axis=0)])
    pref_sq = np.r_[0.0, np.cumsum(np.sum(rows*rows, axis=1))]

    def sse(a,b):
        length = b-a
        c = pref[b]-pref[a]
        return max(0.0,float(pref_sq[b]-pref_sq[a] - np.dot(c,c)/length))

    dp = np.full((kmax+1,n+1),np.inf)
    prev = np.full((kmax+1,n+1),-1,dtype=int)
    dp[0,0]=0.0
    for k in range(1,kmax+1):
        for end in range(k*min_width,n+1):
            for start in range((k-1)*min_width,end-min_width+1):
                cost=dp[k-1,start]+sse(start,end)
                if cost < dp[k,end]:
                    dp[k,end]=cost
                    prev[k,end]=start
    candidates=[(float(dp[k,n]+(k-1)*CHANGE_POINT_PENALTY),k,float(dp[k,n]))
                for k in range(1,kmax+1) if np.isfinite(dp[k,n])]
    objective,k_best,sse_best=min(candidates)
    bounds=[]
    at=n
    for k in range(k_best,0,-1):
        before=int(prev[k,at]);bounds.append((before,at));at=before
    bounds.reverse()
    # Merge adjacent small-difference segments; do not merge distant equal colors.
    done=[]
    for a,b in bounds:
        if done and lab_de(trimmed_lab(rows[done[-1][0]:done[-1][1]]),
                           trimmed_lab(rows[a:b])) < MIN_LAYER_DE:
            done[-1]=(done[-1][0],b)
        else:
            done.append((a,b))
    layers=[]
    for a,b in done:
        col=trimmed_lab(rows[a:b])
        layers.append({'t':[float(a/n),float(b/n)],'lab':col.tolist(),
                       'rgb':lab_to_srgb(col).tolist(), 'hex':rgb_hex(lab_to_srgb(col))})
    log('Contiguous segmentation: '+', '.join(f'k={k} cost={v:.0f} SSE={s:.0f}'
        for v,k,s in candidates))
    log(f'Selected {k_best} raw segment(s), {len(layers)} after adjacent-color merging '
        f'| objective={objective:.1f}, SSE={sse_best:.1f}')
    return layers


def kmeans_palette(labs):
    """Deterministic k-means; return representative Lab and relative proportions."""
    labs = np.asarray(labs,dtype=np.float64)
    if len(labs)>7500:
        labs=labs[np.linspace(0,len(labs)-1,7500).astype(int)]
    k=min(PATTERN_PALETTE_COUNT,len(labs))
    med=np.median(labs,axis=0)
    centers=[med]
    for _ in range(1,k):
        distance=np.min(np.stack([np.sum((labs-c)**2,axis=1) for c in centers]),axis=0)
        centers.append(labs[int(np.argmax(distance))])
    centers=np.asarray(centers)
    for _ in range(18):
        ids=np.argmin(np.sum((labs[:,None,:]-centers[None,:,:])**2,axis=2),axis=1)
        new=np.asarray([np.median(labs[ids==i],axis=0) if np.any(ids==i)
                        else centers[i] for i in range(k)])
        if np.max(np.abs(new-centers))<.15:
            centers=new;break
        centers=new
    ids=np.argmin(np.sum((labs[:,None,:]-centers[None,:,:])**2,axis=2),axis=1)
    palette=[]
    for i,c in enumerate(centers):
        f=float(np.mean(ids==i))
        if f < .04: continue
        palette.append({'lab':c.tolist(),'rgb':lab_to_srgb(c).tolist(),
                        'hex':rgb_hex(lab_to_srgb(c)),'fraction':f})
    return sorted(palette,key=lambda e:-e['fraction'])


def estimate_pattern_pixels(samples, good, strip_length):
    """Rough U-axis spatial scale from same-row Lab changes; NOT a 3D scale."""
    labs=srgb_to_lab(samples[...,:3])
    row_i=len(labs)//2
    mask=good[row_i]
    if np.count_nonzero(mask)<20:
        return None
    x=labs[row_i][mask]
    d=np.linalg.norm(np.diff(x,axis=0),axis=1)
    if len(d)<8:return None
    strong=d>max(6.5,float(np.median(d))*1.8)
    positions=np.flatnonzero(strong)
    if len(positions)<3:return None
    runs=np.diff(positions)
    return round(float(np.median(runs)*strip_length/max(1,SAMPLE_U_COUNT)),1)


def detect_contiguous_marbling(samples, good):
    """Find an extended Y band with heterogeneous colors along circumference U.

    A genuine marbled band may occupy only the upper 25% of a button, while a
    solid dark lower band makes global inter-row variance artificially large.
    Use a ROBUST 80th-percentile in-row ΔE and require persistence over Y,
    rather than making a decision from isolated highlights/scratches.
    """
    labs = srgb_to_lab(samples[..., :3])
    spread = []
    for row, mask in zip(labs, good):
        colors = row[mask]
        if len(colors) < 12:
            spread.append(0.0)
            continue
        med = np.median(colors, axis=0)
        distance = np.linalg.norm(colors-med, axis=1)
        spread.append(float(np.percentile(distance, 80)))
    spread = np.asarray(spread, dtype=np.float64)
    textured = spread >= MARBLE_ROW_P80_DE_THRESHOLD
    longest = now = 0
    for state in textured:
        now = now+1 if state else 0
        longest = max(longest, now)
    coverage = float(np.mean(textured))
    streak = longest / max(1, len(textured))
    detected = coverage >= MARBLE_ROW_MIN_FRACTION and streak >= MARBLE_ROW_MIN_STREAK
    return {'row_p80_de_p90': float(np.percentile(spread, 90)),
            'textured_row_fraction':coverage,
            'longest_textured_y_streak_fraction':streak,
            'sustained_marbling':bool(detected)}


def classify_photo(rows, all_labs, within_sq, between_sq, samples, good, frame):
    layers=segment_rows(rows)
    between=math.sqrt(max(0,between_sq));within=math.sqrt(max(0,within_sq))
    ratio=between_sq/max(within_sq,1.0)
    contrast=max((lab_de(a['lab'],b['lab']) for a,b in zip(layers,layers[1:])),default=0.0)
    marble=detect_contiguous_marbling(samples,good)
    log(f'CLASS STATS between_row_variance={between_sq:.2f} (RMS ΔE={between:.2f}); '
        f'within_row_variance={within_sq:.2f} (RMS ΔE={within:.2f}); '
        f'variance_ratio={ratio:.3f}; segmented_contrast_ΔE={contrast:.2f}')
    log(f'MARBLE STATS in-row ΔE80 p90={marble["row_p80_de_p90"]:.2f}; '
        f'fraction of textured Y rows={marble["textured_row_fraction"]:.1%}; '
        f'longest contiguous textured Y band={marble["longest_textured_y_streak_fraction"]:.1%}')
    if marble['sustained_marbling']:
        kind='MARBLED'
    elif (len(layers)>1 and contrast>=MIN_LAYER_DE and
        (ratio>=LAYER_COHERENCE_RATIO_MIN or between>16)):
        kind='LAYERED'
    elif (within>=MARBLE_WITHIN_RMS_MIN and
          (ratio<LAYER_COHERENCE_RATIO_MIN or len(layers)<=1)):
        kind='MARBLED'
    elif between<=SOLID_BETWEEN_RMS_MAX and within<=SOLID_WITHIN_RMS_MAX:
        kind='SOLID'
    elif within>=MARBLE_WITHIN_RMS_MIN:
        kind='MARBLED'
    elif len(layers)>1 and contrast>=MIN_LAYER_DE:
        kind='LAYERED'
    else:
        kind='SOLID'
    notes=[]
    if len(layers)>1 and .6<=ratio<1.6:
        notes.append('weak inter/intra variance separation')
    if kind=='SOLID' and between>12:
        notes.append('possibly continuous lighting gradient')
    if kind=='MARBLED' and len(layers)>1:
        notes.append('pattern plus physical layer candidates: keep band boundaries for Stage D')
    if notes:
        log('WARNING: classification needs visual review: '+ '; '.join(notes))
    overall=trimmed_lab(all_labs)
    if kind=='SOLID':
        output=[{'t':[0.0,1.0], 'lab':overall.tolist(),
                 'rgb':lab_to_srgb(overall).tolist(), 'hex':rgb_hex(lab_to_srgb(overall))}]
    elif kind=='LAYERED':
        output=layers
    else:
        output=[{'t':[0.0,1.0], 'lab':overall.tolist(),
                 'rgb':lab_to_srgb(overall).tolist(), 'hex':rgb_hex(lab_to_srgb(overall))}]
        log('MARBLED: whole-strip palette preserved; not reduced to 1D row colors.')
    palette=kmeans_palette(all_labs) if kind=='MARBLED' else []
    pattern=estimate_pattern_pixels(samples,good,np.linalg.norm(frame[1])) if kind=='MARBLED' else None
    return {'class':kind,'layers':output,'candidate_layers':layers,
            'palette':palette,'pattern_scale_source_px':pattern,
            'metrics':{'between_row_variance':between_sq,'within_row_variance':within_sq,
                       'between_rms_de':between,'within_rms_de':within,
                       'variance_ratio':ratio,'segmented_contrast_de':contrast,**marble},
            'confidence_notes':notes,'source':'photo'}


def parse_recipe(path, code):
    if not path:
        return None
    with open(bpy.path.abspath(path),'r',encoding='utf-8') as f:
        doc=json.load(f)
    record=doc.get(code)
    if record is None:
        log(f'Recipe JSON has no {code}; auto detection will be used.')
        return None
    raw=record.get('layers')
    if not isinstance(raw,list) or not raw:
        raise ValueError(f'Recipe {code} must have a non-empty layers array.')
    parsed=[]
    for i,item in enumerate(raw):
        t=item['t'];val=item['color']
        if len(t)!=2 or not (0<=float(t[0])<float(t[1])<=1):
            raise ValueError(f'Recipe layer {i} has invalid t: {t}')
        if not isinstance(val,str) or len(val)!=7 or not val.startswith('#'):
            raise ValueError(f'Recipe layer {i} needs six-digit #RRGGBB.')
        rgb=np.array([int(val[j:j+2],16)/255.0 for j in (1,3,5)])
        parsed.append({'t':[float(t[0]),float(t[1])], 'lab':srgb_to_lab(rgb).tolist(),
                       'rgb':rgb.tolist(),'hex':val.upper()})
    parsed.sort(key=lambda l:l['t'][0])
    for i,layer in enumerate(parsed):
        expected=0 if i==0 else parsed[i-1]['t'][1]
        if abs(layer['t'][0]-expected)>1e-4:
            raise ValueError('Recipe must cover [0,1] without gaps or overlaps.')
    if abs(parsed[-1]['t'][1]-1)>1e-4:
        raise ValueError('Recipe must end at t=1.')
    log(f'RECIPE OVERRIDE: {code} has {len(parsed)} contiguous layers. Photo classification skipped.')
    return {'class':'LAYERED' if len(parsed)>1 else 'SOLID','layers':parsed,
            'candidate_layers':parsed,'palette':[], 'pattern_scale_source_px':None,
            'metrics':{},'confidence_notes':[],'source':'recipe'}


def analyze_images():
    side_path,front_path,verso_path=photo_paths()
    log('Photo paths: '+str({'side':side_path,'front':front_path,'verso':verso_path}))
    side=load_photo(side_path,'SIDE')
    front_lab=robust_face_color(load_photo(front_path,'FRONT')) if front_path else None
    verso_lab=robust_face_color(load_photo(verso_path,'VERSO')) if verso_path else None
    frame=strip_frame(side)
    samples,good=sample_strip(side,frame)
    rows,palette_pixels,within_sq,between_sq=row_profile(samples,good)
    reverse=determine_orientation(rows,front_lab,verso_lab)
    if reverse:
        rows=rows[::-1].copy()
        samples=samples[::-1].copy()
        good=good[::-1].copy()
    recipe=parse_recipe(LAYER_RECIPE_JSON_PATH,COLOR_CODE)
    outcome=recipe if recipe is not None else classify_photo(
        rows,palette_pixels,within_sq,between_sq,samples,good,frame)
    log(f'CLASSIFICATION: {COLOR_CODE} => {outcome["class"]} [{outcome["source"]}]')
    for i,layer in enumerate(outcome['layers']):
        log(f'  LAYER[{i}] t={layer["t"][0]:.3f}..{layer["t"][1]:.3f} '
            f'Lab={tuple(round(v,1) for v in layer["lab"])} '
            f'RGB={tuple(round(v,3) for v in layer["rgb"])} {layer["hex"]}')
    if outcome['class']=='MARBLED' and len(outcome['candidate_layers'])>1:
        for i,layer in enumerate(outcome['candidate_layers']):
            log(f'  MARBLE BAND CANDIDATE[{i}] t={layer["t"][0]:.3f}..{layer["t"][1]:.3f} '
                f'{layer["hex"]} (NOT flattened; Stage D will model patterns)')
    for i,color in enumerate(outcome['palette']):
        log(f'  MARBLE PALETTE[{i}] {color["hex"]} '
            f'weight={color["fraction"]:.2%} Lab={tuple(round(v,1) for v in color["lab"])}')
    if outcome['class']=='MARBLED':
        log(f'  MARBLE source pattern scale (approx px): {outcome["pattern_scale_source_px"]}')
        log('  STAGE C PREVIEW: uniform overall material color only; 3D marbling comes in Stage D.')
    outcome['side_path']=side_path
    outcome['front_path']=front_path
    outcome['verso_path']=verso_path
    outcome['orientation_reverse_source_rows']=reverse
    outcome['strip_frame_px']={
        'center':frame[0].tolist(),
        'axis_u':frame[1].tolist(),
        'axis_v':frame[2].tolist(),
    }
    return outcome


def require_geometry():
    obj=bpy.data.objects.get(BUTTON_OBJECT_NAME)
    if obj is None or obj.type!='MESH':
        raise RuntimeError(f"Open a saved .blend containing mesh '{BUTTON_OBJECT_NAME}'.")
    if obj.mode != 'OBJECT':
        raise RuntimeError('Switch Button_3D to Object Mode before running.')
    if 'dxf_y_min' not in obj or 'dxf_y_max' not in obj:
        raise RuntimeError('dxf_y_min and dxf_y_max are REQUIRED. No UV/guess fallback.')
    ymin,ymax=float(obj['dxf_y_min']),float(obj['dxf_y_max'])
    if ymax<=ymin:
        raise RuntimeError('dxf_y_max must exceed dxf_y_min.')
    mesh=obj.data
    if mesh.uv_layers.get(UV_MAP_NAME) is None:
        raise RuntimeError(f'Missing builder UV map {UV_MAP_NAME!r}.')
    attr=mesh.attributes.get(SURFACE_ATTRIBUTE_NAME)
    if attr is None or attr.domain!='FACE' or attr.data_type!='INT':
        raise RuntimeError('Builder dxf_surface_type must be FACE/INT.')
    minv=min(v.co.y for v in mesh.vertices)
    maxv=max(v.co.y for v in mesh.vertices)
    if max(abs(minv-ymin),abs(maxv-ymax))>Y_RANGE_TOLERANCE:
        raise RuntimeError('Y metadata inconsistent with local vertex bounds.')
    counts=Counter(p.material_index for p in mesh.polygons)
    sem=Counter(int(attr.data[p.index].value) for p in mesh.polygons)
    mismatches=sum(int(p.material_index!=int(attr.data[p.index].value))
                   for p in mesh.polygons)
    if mismatches and FAIL_ON_SEMANTIC_MISMATCH:
        raise RuntimeError(f'{mismatches} semantic/material slot disagreements!')
    if any(idx not in range(4) for idx in counts):
        raise RuntimeError(f'Unexpected material indices: {counts}')
    log(f'MESH: {len(mesh.vertices)} verts; {len(mesh.polygons)} faces; '
        f'{len(mesh.loops)} loops; UVs={[x.name for x in mesh.uv_layers]}')
    log(f'TRUE Y: {ymin:.7f}..{ymax:.7f} => {ymax-ymin:.7f} thickness')
    log(f'FACE COUNTS indices={dict(counts)} semantic={dict(sem)} mismatches={mismatches}')
    mean_front=np.mean([v.co.y for p in mesh.polygons if p.material_index==0
                        for v in (mesh.vertices[i] for i in p.vertices)])
    mean_verso=np.mean([v.co.y for p in mesh.polygons if p.material_index==1
                        for v in (mesh.vertices[i] for i in p.vertices)])
    if mean_front<=mean_verso:
        raise RuntimeError('Builder orientation is not FRONT +Y / VERSO -Y!')
    log(f'ORIENTATION: +Y FRONT mean={mean_front:.5f}; '
        f'-Y BACK mean={mean_verso:.5f}; t=(localY-ymin)/(ymax-ymin)')
    return obj,ymin,ymax,counts



# ============================================================================
# STAGE C: deterministic cleanup, pixel rectification, photographed shaders
# ============================================================================

def cleanup_pipeline_metadata(obj):
    """Remove pipeline-owned mesh metadata ONLY AFTER successful shader installation.

    This function NEVER touches geometry, builder UVs, canonical materials or
    material slots. Node creation failures must not erase working materials.
    """
    mesh=obj.data
    removed=[]
    for attr in list(mesh.attributes):
        if attr.name.startswith('BTEX_') or attr.name in ('tex_exposure_mask','texture_exposure_mask'):
            removed.append(attr.name)
            mesh.attributes.remove(attr)
    log(f'CLEAN attributes: {removed or "none"}')
    removed=[]
    for key in list(obj.keys()):
        if key.startswith('btex_') or (REMOVE_LEGACY_V7_METADATA and key in (
            'texture_script_version','texture_front_image','texture_verso_image',
            'texture_side_image','texture_side_auto_detect')):
            removed.append(key)
            del obj[key]
    log(f'CLEAN metadata: {removed or "none"}')
    # Stage B and Stage C created assets can now be removed if unreferenced.
    for img in list(bpy.data.images):
        if (img.name.startswith('BTEX_') or
                img.name.endswith('_ROBUST_TRUE_Y_LAYER_PROFILE')) and img.users==0:
            bpy.data.images.remove(img)
    for mat in list(bpy.data.materials):
        if ((mat.name.startswith('BTEX_PREVIOUS_') or
             mat.name.startswith('BTEX_STAGING_C_')) and mat.users==0):
            bpy.data.materials.remove(mat)


def create_staged_materials(ymin,ymax,outcome,photos):
    """Construct ALL four new shaders on detached materials first.

    If ANY node fails (unsupported Blender version, missing socket, etc.),
    remove detached materials and leave existing Button_3D slots UNTOUCHED.
    """
    staged=[]
    try:
        for i,name in enumerate(SLOT_NAMES):
            mat=bpy.data.materials.new('BTEX_STAGING_C_'+str(i))
            staged.append(mat)
            mat.use_nodes=True
            mat.node_tree.nodes.clear()
            mat.diffuse_color=SEMANTIC_COLORS[i]
            if DEBUG_MODE=='PHOTO':
                build_photographic_material(mat,i,ymin,ymax,outcome,photos)
            elif DEBUG_MODE=='EXPOSURE':
                build_exposure_debug(mat,i,ymin,ymax,outcome)
            else:
                make_plain_debug(mat,i,ymin,ymax,outcome)
            if (not any(n.bl_idname=='ShaderNodeOutputMaterial'
                        for n in mat.node_tree.nodes)):
                raise RuntimeError(f'Missing material output in staged slot {i} ({name}).')
            log(f'PREFLIGHT PASS: staged shader slot {i} {name} '
                f'({len(mat.node_tree.nodes)} nodes)')
        return staged
    except Exception:
        for mat in staged:
            if mat.name in bpy.data.materials and mat.users==0:
                bpy.data.materials.remove(mat)
        log('ABORT: staged shader creation failed; PREVIOUS BUTTON MATERIALS PRESERVED.')
        raise


def install_staged_materials(obj,staged):
    """Commit previously validated materials without changing material indices.

    Material swapping happens only after ALL four shaders built successfully.
    Roll back material assignment if a slot operation fails. Canonical slot
    material names are retained for compatibility with the DXF builder.
    """
    mesh=obj.data
    if len(staged)!=4 or len(mesh.materials)<4:
        raise RuntimeError('Need four staged materials and four original mesh slots.')
    previous=[mesh.materials[i] for i in range(4)]
    # Avoid overwriting materials used elsewhere, while explaining the tradeoff.
    for old in previous:
        if old and old.users>1:
            log(f'INFO: Old material {old.name!r} has {old.users} users; '
                'it will be renamed, but its node tree remains intact for other users.')
    owners={name:bpy.data.materials.get(name) for name in SLOT_NAMES}
    original_names={mat:mat.name for mat in owners.values() if mat is not None}
    old_links=[obj.material_slots[i].link for i in range(4)]
    try:
        # Free canonical names, then install the fully built replacements.
        for name,old in owners.items():
            if old is not None:
                old.name='BTEX_PREVIOUS_'+name
        for i,(new,name) in enumerate(zip(staged,SLOT_NAMES)):
            new.name=name
            obj.material_slots[i].link='DATA'
            mesh.materials[i]=new
        log('COMMIT: all four complete shader trees installed in canonical slots.')
    except Exception:
        # Put material references back BEFORE restoring their names.
        for i,old in enumerate(previous):
            try:
                mesh.materials[i]=old
                obj.material_slots[i].link=old_links[i]
            except Exception:
                pass
        for new in staged:
            try:
                new.name='BTEX_STAGING_C_ROLLBACK'
            except Exception:
                pass
        for old,name in original_names.items():
            try:
                old.name=name
            except Exception:
                pass
        for new in staged:
            try:
                if new.users==0:
                    bpy.data.materials.remove(new)
            except Exception:
                pass
        log('ROLLBACK: material installation failed; attempted to restore old slots.')
        raise
    # Only orphaned old canonical materials are removed. Other objects remain
    # connected to any prior material they still use.
    for old in set(x for x in previous if x is not None):
        if old.users==0:
            bpy.data.materials.remove(old)
    log('CLEAN: unused prior material datablocks removed; geometry untouched.')


def audit_exposure_centers(obj, outcome, ymin, ymax):
    """Informational face-center attribute; NOT used to drive pixel color."""
    mesh=obj.data
    attr=mesh.attributes.new('BTEX_exposure_estimate', 'FLOAT', 'FACE')
    layers=(outcome['candidate_layers'] if (outcome.get('class')=='MARBLED' and outcome.get('candidate_layers')) else outcome['layers'])
    front_min=layers[-1]['t'][0]
    back_max=layers[0]['t'][1]
    per_region=Counter()
    for face in mesh.polygons:
        t=float(np.clip((face.center.y-ymin)/(ymax-ymin),0,1))
        if face.material_index==0:
            value=1.0 if t < front_min else 0.0
        elif face.material_index==1:
            value=1.0 if t > back_max else 0.0
        elif face.material_index==3:
            value=1.0
        else:
            value=0.0
        attr.data[face.index].value=value
        if value:
            per_region[face.material_index]+=1
    log(f'EXPOSURE AUDIT (FACE CENTERS only): counts={dict(per_region)} '
        f'front inner boundary t={front_min:.4f}, back inner boundary t={back_max:.4f}')
    log('CAUTION: original shaped DXF face relief vs new boolean cut is not uniquely '
        'recoverable from final mesh. Exposed means crossing a physical layer boundary.')


def ensure_valid_crop(crop, label):
    if crop is None:
        return (0.0,0.0,1.0,1.0)
    if len(crop)!=4:
        raise ValueError(f'{label} crop needs 4 floats (u0,v0,u1,v1).')
    u0,v0,u1,v1=map(float,crop)
    if not (0 <= u0 < u1 <= 1 and 0 <= v0 < v1 <= 1):
        raise ValueError(f'{label} crop must lie in [0,1] with increasing bounds.')
    return (u0,v0,u1,v1)


def make_true_y_nodes(nodes,links,ymin,ymax):
    """Geometry Position [world] -> transform [object] -> local Y -> t."""
    position=nodes.new('ShaderNodeNewGeometry');position.location=(-1650,-530)
    position.label='Geometry Position (world, never UV V)'
    local=nodes.new('ShaderNodeVectorTransform');local.location=(-1435,-530)
    local.vector_type='POINT';local.convert_from='WORLD';local.convert_to='OBJECT'
    local.label='WORLD -> OBJECT (true mesh local Y)'
    links.new(position.outputs['Position'],local.inputs['Vector'])
    split=nodes.new('ShaderNodeSeparateXYZ');split.location=(-1215,-530)
    links.new(local.outputs['Vector'],split.inputs['Vector'])
    sub=nodes.new('ShaderNodeMath');sub.operation='SUBTRACT';sub.location=(-1000,-530)
    sub.inputs[1].default_value=float(ymin)
    links.new(split.outputs['Y'],sub.inputs[0])
    div=nodes.new('ShaderNodeMath');div.operation='DIVIDE';div.location=(-780,-530)
    div.inputs[1].default_value=float(ymax-ymin)
    links.new(sub.outputs[0],div.inputs[0])
    return div.outputs[0]


def make_layer_ramp(nodes,links,t_socket,layers,ids=False):
    """Color vs per-fragment local Y. Feathered physical transitions (t units)."""
    ramp=nodes.new('ShaderNodeValToRGB');ramp.location=(-490,-460)
    ramp.label='Physical material at TRUE local Y'
    elements=ramp.color_ramp.elements
    ramp.color_ramp.interpolation='LINEAR'
    colors=[(LAYER_ID_COLORS[i % len(LAYER_ID_COLORS)] if ids else
             tuple(srgb_to_scene_linear(layer['rgb']))+(1.0,))
            for i,layer in enumerate(layers)]
    # Always have 2 elements. For n>1, at each layer interface put two
    # colors separated by FEATHER_T. Both extremes are fixed at t=0 and t=1.
    elements[0].position=0.0
    elements[0].color=colors[0]
    elements[1].position=1.0
    elements[1].color=colors[-1]
    if len(layers)>1:
        bounds=[float(layer['t'][1]) for layer in layers[:-1]]
        for i,b in enumerate(bounds):
            left_gap=b-(bounds[i-1] if i>0 else 0.0)
            right_gap=(bounds[i+1] if i+1<len(bounds) else 1.0)-b
            half=0.5*min(max(0.0,LAYER_EDGE_FEATHER_T),left_gap*.75,right_gap*.75)
            # Debug layer IDs should be genuinely hard-separated.
            if ids: half=0.00005
            low=max(1e-5,b-half)
            high=min(1-1e-5,b+half)
            if high-low<2e-5:
                high=min(1-1e-5,low+2e-5)
            l=elements.new(low);l.color=colors[i]
            r=elements.new(high);r.color=colors[i+1]
    links.new(t_socket,ramp.inputs['Fac'])
    return ramp.outputs['Color']


def math_node(nodes,links,operation,first,second=None,value=None,location=(0,0),label=''):
    node=nodes.new('ShaderNodeMath')
    node.operation=operation
    node.location=location
    node.label=label
    if first is not None:
        links.new(first,node.inputs[0])
    if second is not None:
        links.new(second,node.inputs[1])
    if value is not None:
        node.inputs[1].default_value=float(value)
    return node.outputs[0]


def mix_colors(nodes,links,factor,c1,c2,location=(100,100),label=''):
    node=nodes.new('ShaderNodeMixRGB');node.blend_type='MIX';node.location=location
    node.label=label
    if isinstance(factor,(float,int)):
        node.inputs['Fac'].default_value=float(factor)
    else:
        links.new(factor,node.inputs['Fac'])
    links.new(c1,node.inputs['Color1'])
    links.new(c2,node.inputs['Color2'])
    return node.outputs['Color']


def image_from_path(path):
    path=bpy.path.abspath(path)
    img=bpy.data.images.load(path,check_existing=True)
    # Photo textures need sRGB input color management, unlike analysis samples.
    img.colorspace_settings.name='sRGB'
    return img


def make_uv_photo(nodes,links,img,flip_u,flip_v,crop,label):
    crop=ensure_valid_crop(crop,label)
    u0,v0,u1,v1=crop
    uv=nodes.new('ShaderNodeUVMap');uv.uv_map=UV_MAP_NAME
    uv.location=(-1660,350);uv.label=f'{label}: only photo positioning uses UV'
    mapping=nodes.new('ShaderNodeMapping');mapping.location=(-1420,350)
    mapping.vector_type='POINT'
    mapping.inputs['Location'].default_value[0]=(u1 if flip_u else u0)
    mapping.inputs['Location'].default_value[1]=(v1 if flip_v else v0)
    mapping.inputs['Scale'].default_value[0]=(u0-u1 if flip_u else u1-u0)
    mapping.inputs['Scale'].default_value[1]=(v0-v1 if flip_v else v1-v0)
    links.new(uv.outputs['UV'],mapping.inputs['Vector'])
    tex=nodes.new('ShaderNodeTexImage');tex.location=(-1180,350)
    tex.label=f'{label}: original external face photograph'
    tex.image=img;tex.interpolation='Linear';tex.extension='EXTEND'
    links.new(mapping.outputs['Vector'],tex.inputs['Vector'])
    return tex.outputs['Color']


def generated_rectified_side(outcome):
    """Retain side photo pixels but straighten the physical band for exact t mapping."""
    source=bpy.data.images.load(outcome['side_path'],check_existing=True)
    source.colorspace_settings.name='Non-Color'
    # Match the proven Stage B classifier's unconverted source pixels.
    rgba=image_arrays(source)  # normalized analysis image, top-down
    frame=outcome['strip_frame_px']
    ctr=np.asarray(frame['center'],dtype=np.float64)
    au=np.asarray(frame['axis_u'],dtype=np.float64)
    av=np.asarray(frame['axis_v'],dtype=np.float64)
    w=int(SIDE_RECTIFIED_WIDTH);h=int(SIDE_RECTIFIED_HEIGHT)
    if w<16 or h<16:
        raise ValueError('SIDE_RECTIFIED_WIDTH/HEIGHT must be >=16')
    u0,u1=SIDE_SOURCE_U_RANGE;v0,v1=SIDE_SOURCE_V_RANGE
    if not (0<=u0<u1<=1 and 0<=v0<v1<=1):
        raise ValueError('SIDE_SOURCE_U/V_RANGE should be increasing in [0,1].')
    us=np.linspace(u0,u1,w)
    ts=np.linspace(0,1,h)
    src_v=1.0-ts if outcome['orientation_reverse_source_rows'] else ts
    uu,vv=np.meshgrid(us,v0+src_v*(v1-v0))
    x=ctr[0]+(uu-.5)*au[0]+(vv-.5)*av[0]
    y=ctr[1]+(uu-.5)*au[1]+(vv-.5)*av[1]
    rect=bilinear_rgba(rgba,x,y)
    alpha=rect[...,3]
    invalid=alpha<.80
    # Preserve all the photograph's pixel detail wherever the mask is reliable.
    # If a tiny gap survives cleanup, use the nearest good photo sample in that row
    # rather than interpolating the white transparent background over a material.
    for row in range(h):
        good=np.flatnonzero(~invalid[row])
        if len(good):
            bad=np.flatnonzero(invalid[row])
            if len(bad):
                near=np.searchsorted(good,bad)
                left=good[np.clip(near-1,0,len(good)-1)]
                right=good[np.clip(near,0,len(good)-1)]
                take=np.where(abs(bad-left)<=abs(bad-right),left,right)
                rect[row,bad,:3]=rect[row,take,:3]
        else:
            # An entire unreliable row should be visible in the audit, not white.
            col=outcome['layers'][0]['rgb']
            rect[row,:,0:3]=col
    rect[...,3]=1.0
    log(f'SIDE PHOTO: rectification {w}x{h}, originally invalid samples '
        f'{np.mean(invalid):.1%} (filled from neighbors), Y t = BACK->FRONT')
    # rect rows were intentionally generated in ascending true t: row 0=t=0.
    # Blender images store bottom row first, so write these rows AS IS.
    lin=srgb_to_scene_linear(rect[...,:3])
    pixels=np.empty((h,w,4),dtype=np.float32)
    pixels[...,:3]=lin.astype(np.float32)
    pixels[...,3]=1.0
    image_name='BTEX_'+COLOR_CODE+'_SIDE_RECTIFIED'
    img=bpy.data.images.get(image_name)
    if img is None:
        img=bpy.data.images.new(image_name,width=w,height=h,alpha=True,float_buffer=True)
    elif (int(img.size[0]),int(img.size[1])) != (w,h):
        img.scale(w,h)
    img.colorspace_settings.name='Non-Color'  # pixels are already scene-linear
    img.pixels.foreach_set(pixels.reshape(-1))
    img.update()
    if SAVE_PACK_IMAGES:
        try:
            img.pack()
        except Exception as exc:
            log(f'INFO: Generated side image is stored in .blend; explicit pack not available: {exc}')
    return img


def make_cylindrical_side_photo(nodes,links,side_img,t_socket):
    uv=nodes.new('ShaderNodeUVMap');uv.uv_map=UV_MAP_NAME
    uv.location=(-1650,380);uv.label='Wrap circumference using builder U only'
    separate=nodes.new('ShaderNodeSeparateXYZ');separate.location=(-1415,380)
    links.new(uv.outputs['UV'],separate.inputs['Vector'])
    u=separate.outputs['X']
    # strip_frame already applied SIDE_FLIP_U when rectifying the source.
    # Do not flip again at texture lookup (otherwise two flips cancel).
    xyz=nodes.new('ShaderNodeCombineXYZ');xyz.location=(-980,360)
    links.new(u,xyz.inputs['X'])
    links.new(t_socket,xyz.inputs['Y'])
    tex=nodes.new('ShaderNodeTexImage');tex.location=(-760,370)
    tex.image=side_img;tex.interpolation='Linear';tex.extension='REPEAT'
    tex.label='Actual cleaned side photograph, remapped to true local Y'
    links.new(xyz.outputs['Vector'],tex.inputs['Vector'])
    return tex.outputs['Color']


def make_exposure(nodes,links,t_socket,layer_boundary,side):
    """Per fragment exposure: crossing beyond original external material layer."""
    edge=max(0.0001,float(EXPOSURE_EDGE_FEATHER_T))
    cut=nodes.new('ShaderNodeMapRange');cut.location=(-260,-110)
    cut.interpolation_type='SMOOTHSTEP'
    cut.clamp=True
    links.new(t_socket,cut.inputs['Value'])
    cut.inputs['From Min'].default_value=float(layer_boundary)-edge*.5
    cut.inputs['From Max'].default_value=float(layer_boundary)+edge*.5
    if side=='FRONT':
        cut.inputs['To Min'].default_value=1.0
        cut.inputs['To Max'].default_value=0.0
    elif side=='VERSO':
        cut.inputs['To Min'].default_value=0.0
        cut.inputs['To Max'].default_value=1.0
    else:
        raise ValueError(f'Unknown face side: {side}')
    cut.label=f'{side} exposure when crossing exterior layer threshold'
    return cut.outputs['Result']


def add_photo_detail(nodes,links,photo_socket,layer_socket):
    """Tint with the real layer while keeping light photographic microstructure."""
    bw=nodes.new('ShaderNodeRGBToBW');bw.location=(-490,100)
    links.new(photo_socket,bw.inputs['Color'])
    diff=nodes.new('ShaderNodeMath');diff.operation='SUBTRACT';diff.location=(-290,130)
    links.new(bw.outputs['Val'],diff.inputs[0]);diff.inputs[1].default_value=.5
    scale=nodes.new('ShaderNodeMath');scale.operation='MULTIPLY';scale.location=(-90,140)
    scale.inputs[1].default_value=float(PHOTO_MICRODETAIL_STRENGTH)
    links.new(diff.outputs[0],scale.inputs[0])
    add=nodes.new('ShaderNodeMath');add.operation='ADD';add.location=(105,140)
    add.inputs[1].default_value=1.0
    links.new(scale.outputs[0],add.inputs[0])
    tinted=nodes.new('ShaderNodeMixRGB');tinted.blend_type='MULTIPLY'
    tinted.inputs['Fac'].default_value=1.0;tinted.location=(310,150)
    links.new(layer_socket,tinted.inputs['Color1'])
    links.new(add.outputs[0],tinted.inputs['Color2'])
    tinted.label='Layer material + microstructure from real face photograph'
    return tinted.outputs['Color']


def attach_shader(nodes,links,color_socket,roughness,emission=False):
    output=nodes.new('ShaderNodeOutputMaterial');output.location=(1150,60)
    if emission:
        e=nodes.new('ShaderNodeEmission');e.location=(900,60)
        links.new(color_socket,e.inputs['Color'])
        links.new(e.outputs['Emission'],output.inputs['Surface'])
    else:
        shader=nodes.new('ShaderNodeBsdfPrincipled');shader.location=(870,60)
        shader.inputs['Roughness'].default_value=float(roughness)
        links.new(color_socket,shader.inputs['Base Color'])
        links.new(shader.outputs['BSDF'],output.inputs['Surface'])




def make_palette_ramp_from_colors(nodes, factor_socket, palette, label='Marble palette'):
    """Return ColorRamp color output from palette list with stored fractions."""
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.label = label
    ramp.location = (260, -720)
    ramp.color_ramp.interpolation = 'LINEAR'
    elems = ramp.color_ramp.elements
    if not palette:
        elems[0].color = (0.2,0.2,0.2,1.0)
        elems[1].color = (0.85,0.85,0.85,1.0)
        return ramp.outputs['Color'], ramp
    # ensure number of elements matches palette length
    while len(elems) > len(palette):
        elems.remove(elems[-1])
    while len(elems) < len(palette):
        elems.new(0.5)
    total = sum(max(float(c.get('fraction', 0.0)), 1e-5) for c in palette)
    cumulative = 0.0
    for i, p in enumerate(palette):
        frac = max(float(p.get('fraction', 0.0)), 1e-5) / total
        pos = 0.0 if i == 0 else (1.0 if i == len(palette)-1 else min(0.999, max(0.001, cumulative + frac * 0.5)))
        cumulative += frac
        elems[i].position = pos
        rgb = tuple(srgb_to_scene_linear(p['rgb'])) + (1.0,)
        elems[i].color = rgb
    return ramp.outputs['Color'], ramp


def make_marble_color(nodes, links, t_socket, ymin, ymax, outcome):
    """3D procedural color for MARBLED materials using Object coordinates.

    Uses detected palette + approximate source pattern scale. The pattern is
    continuous in 3D object space, so cuts/holes remain coherent.
    """
    palette = outcome.get('palette') or []
    if not palette:
        # fallback to stage-C physical ramp behavior
        return make_layer_ramp(nodes, links, t_socket, outcome['layers'])

    frame = outcome.get('strip_frame_px', {})
    axis_v = np.asarray(frame.get('axis_v', [0.0, 1.0]), dtype=np.float64)
    thickness_px = max(1.0, float(np.linalg.norm(axis_v)))
    pattern_px = float(outcome.get('pattern_scale_source_px') or max(8.0, thickness_px * 0.22))
    object_units_per_px = max(1e-6, float((ymax - ymin)) / thickness_px)
    pattern_obj = max(1e-5, pattern_px * object_units_per_px * float(MARBLE_COORD_SCALE_MULTIPLIER))
    noise_scale = max(0.01, 1.0 / pattern_obj)
    log(f'MARBLE 3D: thickness_px={thickness_px:.2f}, source_pattern_px={pattern_px:.2f}, object_scale≈{pattern_obj:.5f}, noise_scale≈{noise_scale:.3f}')

    texcoord = nodes.new('ShaderNodeTexCoord'); texcoord.location = (-1520, -760)
    texcoord.label = 'Object coordinates for coherent 3D cut pattern'

    mapping = nodes.new('ShaderNodeMapping'); mapping.location = (-1320, -760)
    try:
        mapping.vector_type = 'POINT'
    except Exception:
        pass
    mapping.inputs['Scale'].default_value = (noise_scale, noise_scale * 0.85, noise_scale)
    links.new(texcoord.outputs['Object'], mapping.inputs['Vector'])

    distort = nodes.new('ShaderNodeTexNoise'); distort.location = (-1110, -910)
    distort.inputs['Scale'].default_value = max(0.05, noise_scale * 0.55)
    distort.inputs['Detail'].default_value = 6.0
    distort.inputs['Roughness'].default_value = 0.58
    distort.inputs['Distortion'].default_value = 0.0

    fine = nodes.new('ShaderNodeTexNoise'); fine.location = (-1110, -650)
    fine.inputs['Scale'].default_value = max(0.08, noise_scale * float(MARBLE_FINE_NOISE_SCALE))
    fine.inputs['Detail'].default_value = 8.0
    fine.inputs['Roughness'].default_value = 0.62
    fine.inputs['Distortion'].default_value = 0.1

    wave = nodes.new('ShaderNodeTexWave'); wave.location = (-820, -770)
    try:
        wave.wave_type = 'BANDS'
        wave.bands_direction = 'DIAGONAL'
    except Exception:
        pass
    wave.inputs['Scale'].default_value = float(MARBLE_WAVE_SCALE)
    wave.inputs['Distortion'].default_value = float(MARBLE_WAVE_DISTORT)
    wave.inputs['Detail'].default_value = 2.0
    wave.inputs['Detail Scale'].default_value = 1.0
    wave.inputs['Detail Roughness'].default_value = 0.5

    links.new(mapping.outputs['Vector'], distort.inputs['Vector'])
    links.new(mapping.outputs['Vector'], fine.inputs['Vector'])
    links.new(mapping.outputs['Vector'], wave.inputs['Vector'])

    mixf = nodes.new('ShaderNodeMixRGB'); mixf.blend_type = 'MIX'; mixf.location = (-520, -740)
    mixf.inputs['Fac'].default_value = float(MARBLE_FINE_NOISE_STRENGTH)
    links.new(wave.outputs['Fac'], mixf.inputs['Color1'])
    links.new(fine.outputs['Fac'], mixf.inputs['Color2'])

    # Distortion mask gently steers the palette factor without breaking continuity.
    bw = nodes.new('ShaderNodeRGBToBW'); bw.location = (-350, -650)
    links.new(mixf.outputs['Color'], bw.inputs['Color'])
    math_add = nodes.new('ShaderNodeMath'); math_add.operation = 'ADD'; math_add.location = (-120, -745)
    math_add.use_clamp = True
    links.new(bw.outputs['Val'], math_add.inputs[0])
    mul = nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.location = (-520, -905)
    mul.inputs[1].default_value = float(MARBLE_DISTORTION) * 0.35
    links.new(distort.outputs['Fac'], mul.inputs[0])
    links.new(mul.outputs[0], math_add.inputs[1])

    # Optional coarse Y-bias so a dark base layer and marbled upper layer can coexist.
    if outcome.get('candidate_layers') and len(outcome['candidate_layers']) > 1:
        coarse = make_layer_ramp(nodes, links, t_socket, outcome['candidate_layers'])
    else:
        coarse = None

    palette_socket, palette_ramp = make_palette_ramp_from_colors(nodes, math_add.outputs[0], palette, 'Stage D palette from side photo')
    links.new(math_add.outputs[0], palette_ramp.inputs['Fac'])

    if coarse is not None and MARBLE_CANDIDATE_LAYER_BLEND > 0.0:
        palette_socket = mix_colors(nodes, links, float(MARBLE_CANDIDATE_LAYER_BLEND), coarse, palette_socket,
            (520, -690), 'Coarse Y candidate bands blended with 3D marble')
    return palette_socket


def make_physical_material_color(nodes, links, t_socket, ymin, ymax, outcome, ids=False):
    """Unified physical material source: bands for SOLID/LAYERED, 3D marble for MARBLED."""
    kind = outcome.get('class', 'SOLID')
    if ids:
        layers = outcome['candidate_layers'] if (kind == 'MARBLED' and outcome.get('candidate_layers')) else outcome['layers']
        return make_layer_ramp(nodes, links, t_socket, layers, True)
    if kind == 'MARBLED':
        return make_marble_color(nodes, links, t_socket, ymin, ymax, outcome)
    return make_layer_ramp(nodes, links, t_socket, outcome['layers'])

def make_plain_debug(mat,slot,ymin,ymax,outcome):
    """Stage B/C proof modes retained; Stage D adds full marble preview."""
    nt=mat.node_tree;nodes=nt.nodes;links=nt.links
    if DEBUG_MODE=='SEMANTIC':
        rgb=nodes.new('ShaderNodeRGB');rgb.outputs[0].default_value=SEMANTIC_COLORS[slot]
        attach_shader(nodes,links,rgb.outputs[0],.5,True)
        return
    t=make_true_y_nodes(nodes,links,ymin,ymax)
    if DEBUG_MODE=='Y_GRADIENT':
        ramp=nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].color=(0,0,0,1)
        ramp.color_ramp.elements[1].color=(1,1,1,1)
        links.new(t,ramp.inputs['Fac'])
        color=ramp.outputs['Color']
    elif DEBUG_MODE=='MARBLE_3D':
        # Full physical material only; very useful for verifying 3D continuity.
        color=make_physical_material_color(nodes,links,t,ymin,ymax,outcome,False)
    elif DEBUG_MODE in ('LAYER_IDS','LAYER_COLORS'):
        color=make_physical_material_color(nodes,links,t,ymin,ymax,outcome,DEBUG_MODE=='LAYER_IDS')
    else:
        raise ValueError(f'Invalid diagnostic mode: {DEBUG_MODE}')
    attach_shader(nodes,links,color,MARBLE_PREVIEW_ROUGHNESS if DEBUG_MODE=='MARBLE_3D' else .5,True)



def build_photographic_material(mat,slot,ymin,ymax,outcome,photos):
    nt=mat.node_tree;nodes=nt.nodes;links=nt.links
    t=make_true_y_nodes(nodes,links,ymin,ymax)
    phys=make_physical_material_color(nodes,links,t,ymin,ymax,outcome)
    if slot==3:
        attach_shader(nodes,links,phys,INTERIOR_ROUGHNESS)
        if outcome.get('class')=='MARBLED':
            log('SHADER interior: procedural 3D marbling from palette/object coordinates.')
        else:
            log('SHADER interior: pure physical f(true local Y) (no photo or UV V).')
        return
    if slot==2:
        side=make_cylindrical_side_photo(nodes,links,photos['side'],t)
        tint = MARBLE_SIDE_TINT if outcome.get('class')=='MARBLED' else SIDE_PHOTO_LAYER_TINT
        if tint>0:
            side=mix_colors(nodes,links,tint,side,phys,
                (490,350),'Gentle physical-material tint on side photograph')
        attach_shader(nodes,links,side,SIDE_ROUGHNESS)
        if outcome.get('class')=='MARBLED':
            log(f'SHADER SIDE: real rectified side photo, tied lightly to 3D marble (blend {tint:.2f})')
        else:
            log(f'SHADER SIDE: real rectified SIDE photo U=angle, V=trueY; blend material {tint:.2f}')
        return
    front=slot==0
    raw=make_uv_photo(nodes,links,photos['front'] if front else photos['verso'],
        FRONT_FLIP_U if front else VERSO_FLIP_U,
        FRONT_FLIP_V if front else VERSO_FLIP_V,
        FRONT_CROP_OVERRIDE if front else VERSO_CROP_OVERRIDE,
        'FRONT' if front else 'VERSO')
    layers=(outcome['candidate_layers'] if (outcome.get('class')=='MARBLED' and outcome.get('candidate_layers'))
            else outcome['layers'])
    boundary=(float(layers[-1]['t'][0]) if front else float(layers[0]['t'][1]))
    exposed=make_exposure(nodes,links,t,boundary,'FRONT' if front else 'VERSO')
    factor=math_node(nodes,links,'MULTIPLY',exposed,
        value=RECESSED_FACE_LAYER_STRENGTH,location=(90,-135),label='Expose tint strength')
    tinted=add_photo_detail(nodes,links,raw,phys)
    mixed=mix_colors(nodes,links,factor,raw,tinted,(640,50),
        'Untouched photo -> physically exposed material with photo detail')
    attach_shader(nodes,links,mixed,FRONT_ROUGHNESS if front else VERSO_ROUGHNESS)
    if outcome.get('class')=='MARBLED':
        log(f'SHADER {"FRONT" if front else "VERSO"}: exact face photo, procedural 3D marble when exposed, threshold t={boundary:.4f}, strength={RECESSED_FACE_LAYER_STRENGTH:.2f}')
    else:
        log(f'SHADER {"FRONT" if front else "VERSO"}: exact face photo, exposure threshold t={boundary:.4f}, strength={RECESSED_FACE_LAYER_STRENGTH:.2f}')



def build_exposure_debug(mat,slot,ymin,ymax,outcome):
    nt=mat.node_tree;nodes=nt.nodes;links=nt.links
    if slot in (2,3):
        node=nodes.new('ShaderNodeRGB')
        node.outputs[0].default_value=(1,1,1,1) if slot==3 else (0,0,0,1)
        attach_shader(nodes,links,node.outputs[0],.5,True)
        return
    t=make_true_y_nodes(nodes,links,ymin,ymax)
    layers=(outcome['candidate_layers'] if (outcome.get('class')=='MARBLED' and outcome.get('candidate_layers')) else outcome['layers'])
    boundary=(layers[-1]['t'][0] if slot==0 else layers[0]['t'][1])
    exposed=make_exposure(nodes,links,t,boundary,'FRONT' if slot==0 else 'VERSO')
    # ShaderNodeCombineRGB does NOT exist in Blender 5.0.1! A COLOR RAMP
    # explicitly converts the exposure scalar into grayscale without relying
    # on implicit float->color node conversions.
    ramp=nodes.new('ShaderNodeValToRGB')
    ramp.label='EXPOSURE: BLACK=photograph; WHITE=deeper physical material'
    ramp.location=(130,120)
    ramp.color_ramp.interpolation='LINEAR'
    ramp.color_ramp.elements[0].position=0.0
    ramp.color_ramp.elements[0].color=(0.0,0.0,0.0,1.0)
    ramp.color_ramp.elements[1].position=1.0
    ramp.color_ramp.elements[1].color=(1.0,1.0,1.0,1.0)
    links.new(exposed,ramp.inputs['Fac'])
    attach_shader(nodes,links,ramp.outputs['Color'],.5,True)


def write_report(outcome,source_blend):
    if not WRITE_JSON_REPORT:
        return
    if OUTPUT_REPORT_PATH:
        path=bpy.path.abspath(OUTPUT_REPORT_PATH)
    elif source_blend:
        root=os.path.splitext(source_blend)[0]
        suffix='_stage_d_'+COLOR_CODE
        path=(root+'_report.json' if root.endswith(suffix) else root+suffix+'_report.json')
    else:
        log('No .blend path; report skipped (set OUTPUT_REPORT_PATH if desired).')
        return
    os.makedirs(os.path.dirname(os.path.abspath(path)),exist_ok=True)
    with open(path,'w',encoding='utf-8') as f:
        json.dump({'color_code':COLOR_CODE,'debug_mode':DEBUG_MODE,
                   'recess_tint_strength':RECESSED_FACE_LAYER_STRENGTH,
                   'layer_feather_t':LAYER_EDGE_FEATHER_T,
                   'marble_coord_scale_multiplier': MARBLE_COORD_SCALE_MULTIPLIER,
                   'marble_distortion': MARBLE_DISTORTION,
                   **outcome},f,
                  indent=2,ensure_ascii=False)
    log(f'JSON REPORT: {path}')


def save_if_requested(source_blend):
    if not OUTPUT_BLEND_PATH and not (AUTO_SAVE_HEADLESS and bpy.app.background):
        log('UI: not auto-saving .blend; use File > Save As when satisfied.')
        return
    if OUTPUT_BLEND_PATH:
        path=bpy.path.abspath(OUTPUT_BLEND_PATH)
    elif source_blend:
        base=os.path.splitext(source_blend)[0]
        # Ensure deterministic output path on re-runs; do not append _stage_c twice.
        suffix='_stage_d_'+COLOR_CODE
        path=(base if base.endswith(suffix) else base+suffix)+'.blend'
    else:
        log('No source .blend path; set OUTPUT_BLEND_PATH for headless save.')
        return
    if not path.lower().endswith('.blend'):
        raise RuntimeError('OUTPUT_BLEND_PATH must end with .blend.')
    os.makedirs(os.path.dirname(os.path.abspath(path)),exist_ok=True)
    if SAVE_PACK_IMAGES:
        # Do not pack all images in the scene; only the three external sources,
        # plus this run's rectified side photo.
        for path0 in photo_paths():
            img=bpy.data.images.load(path0,check_existing=True)
            if not img.packed_file:
                try:
                    img.pack()
                except Exception as exc:
                    log(f'WARNING: Could not pack photo {img.name}: {exc}')
    bpy.ops.wm.save_as_mainfile(filepath=path)
    log(f'HEADLESS SAVE: {path}')


def main():
    log(f'START Stage D color={COLOR_CODE}, mode={DEBUG_MODE}, Blender={bpy.app.version_string}')
    source=bpy.data.filepath
    obj,ymin,ymax,before=require_geometry()
    # Preflight image analysis BEFORE destructive cleanup so error preserves scene.
    outcome=analyze_images()
    if DEBUG_MODE not in ('PHOTO','EXPOSURE','LAYER_IDS','LAYER_COLORS','Y_GRADIENT','SEMANTIC','MARBLE_3D'):
        raise ValueError('DEBUG_MODE invalid.')
    if not (0<=RECESSED_FACE_LAYER_STRENGTH<=1 and 0<=SIDE_PHOTO_LAYER_TINT<=1):
        raise ValueError('Texture blend strength must lie in [0,1].')
    # Do not touch previous shader nodes/materials until the new four graphs
    # have built successfully. This also recovers from a previous failed run.
    photos={}
    if DEBUG_MODE=='PHOTO':
        photos['front']=image_from_path(outcome['front_path'])
        photos['verso']=image_from_path(outcome['verso_path'])
        photos['side']=generated_rectified_side(outcome)
    staged=create_staged_materials(ymin,ymax,outcome,photos)
    install_staged_materials(obj,staged)
    cleanup_pipeline_metadata(obj)
    audit_exposure_centers(obj,outcome,ymin,ymax)
    after=Counter(p.material_index for p in obj.data.polygons)
    if after!=before:
        raise RuntimeError(f'Face counts changed: before {before} / after {after}')
    obj['btex_pipeline_stage']='D_MARBLE_3D'
    obj['btex_color_code']=COLOR_CODE
    obj['btex_detected_class']=outcome['class']
    obj['btex_debug_mode']=DEBUG_MODE
    obj['btex_layer_data_json']=json.dumps(outcome['layers'])
    obj['btex_y_min']=ymin
    obj['btex_y_max']=ymax
    log(f'FACE AUDIT: unchanged={dict(after)}')
    log('PASS: independent true-Y is per-fragment Geometry -> local Y.')
    log('PASS: two-phase shader build: existing material slots untouched until preflight success.')
    if outcome['class']=='MARBLED':
        log('PASS: MARBLED materials now use palette-driven OBJECT-space procedural shading for cuts and interior walls.')
    if DEBUG_MODE=='PHOTO':
        log('VIEWPORT: select Material Preview or Rendered. Real FRONT/VERSO photos, SIDE wraps rectified real photo, holes display physical f(t).')
    elif DEBUG_MODE=='EXPOSURE':
        log('EXPOSURE VIEW: white=reached deeper than external material layer; black=still within photo layer. This is a depth estimate, not cut provenance.')
    elif DEBUG_MODE=='MARBLE_3D':
        log('DEBUG VIEW: MARBLE_3D = physical material only. Verify that holes/faca cuts continue the same pattern coherently.')
    else:
        log(f'DEBUG VIEW: {DEBUG_MODE} (same identification as Stage B).')
    write_report(outcome,source)
    save_if_requested(source)
    log('STAGE D COMPLETE')


if __name__ == '__main__':
    main()
