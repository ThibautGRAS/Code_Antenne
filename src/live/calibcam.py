import os
import glob
import time
import math
import cv2
import numpy as np

# =========================
# CONFIG
# =========================
CAM_INDEX = 0
CHESSBOARD_SIZE = (9, 6)   # coins internes (cols, rows)
SQUARE_SIZE_M = 0.025      # 25 mm

IMAGES_DIR = "images"
CALIB_NPZ = "calib_camera.npz"
CALIB_YAML = "calib_camera.yaml"

SUBPIX_CRIT = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-3)

# =========================
# UTILS
# =========================
def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def build_object_points(chessboard_size, square_size):
    cols, rows = chessboard_size
    objp = np.zeros((rows * cols, 3), np.float32)
    objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)
    objp *= float(square_size)
    return objp

def compute_fov_from_K(K, image_size):
    w, h = image_size
    fx = K[0, 0]
    fy = K[1, 1]
    hfov = 2.0 * math.degrees(math.atan(w / (2.0 * fx)))
    vfov = 2.0 * math.degrees(math.atan(h / (2.0 * fy)))
    return hfov, vfov

def save_yaml(path, K, dist, image_size, rms, hfov, vfov):
    fs = cv2.FileStorage(path, cv2.FILE_STORAGE_WRITE)
    fs.write("image_width", int(image_size[0]))
    fs.write("image_height", int(image_size[1]))
    fs.write("camera_matrix", K)
    fs.write("distortion_coefficients", dist)
    fs.write("reprojection_error_rms", float(rms))
    fs.write("hfov_deg", float(hfov))
    fs.write("vfov_deg", float(vfov))
    fs.release()

def draw_border(img, color_bgr, thickness=14):
    h, w = img.shape[:2]
    cv2.rectangle(img, (0, 0), (w - 1, h - 1), color_bgr, thickness)

def clamp01(x):
    return max(0.0, min(1.0, float(x)))

def quality_score(corners, image_shape):
    """
    Score 0-100:
    - area_score: surface du quadrilatère des coins / surface image (cap à ~40%)
    - center_score: distance au centre (plus proche = mieux)
    - skew_score: rapport des côtés (plus proche de 1 = mieux)
    """
    h, w = image_shape[:2]
    pts = corners.reshape(-1, 2)

    # 4 coins extrêmes (indices OpenCV: rangés par lignes)
    cols, rows = CHESSBOARD_SIZE
    tl = pts[0]
    tr = pts[cols - 1]
    bl = pts[(rows - 1) * cols]
    br = pts[(rows - 1) * cols + (cols - 1)]

    quad = np.array([tl, tr, br, bl], dtype=np.float32)  # ordre polygon
    area = float(cv2.contourArea(quad))
    img_area = float(w * h)
    area_ratio = area / (img_area + 1e-12)

    # area score: 0 -> 0, 0.40 -> 1 (cap)
    area_score = clamp01(area_ratio / 0.40)

    # center score
    quad_center = quad.mean(axis=0)
    img_center = np.array([w / 2.0, h / 2.0], dtype=np.float32)
    dist = float(np.linalg.norm(quad_center - img_center))
    max_dist = float(np.linalg.norm(img_center))  # coin
    center_score = 1.0 - clamp01(dist / (max_dist + 1e-12))

    # skew score: compare longueurs des 4 côtés
    def seg_len(a, b):
        return float(np.linalg.norm(a - b))

    top = seg_len(tl, tr)
    bottom = seg_len(bl, br)
    left = seg_len(tl, bl)
    right = seg_len(tr, br)

    # ratios proches de 1 => bon
    r1 = min(top, bottom) / (max(top, bottom) + 1e-12)
    r2 = min(left, right) / (max(left, right) + 1e-12)
    skew_score = clamp01(0.5 * (r1 + r2))

    # pondérations (à ajuster si tu veux)
    score = 100.0 * (0.45 * area_score + 0.35 * center_score + 0.20 * skew_score)

    details = {
        "area_ratio": area_ratio,
        "area_score": area_score,
        "center_score": center_score,
        "skew_score": skew_score,
    }
    return float(score), details

# =========================
# CALIBRATION MODE
# =========================
def calibrate_from_folder():
    images = sorted(glob.glob(os.path.join(IMAGES_DIR, "*.png")) +
                    glob.glob(os.path.join(IMAGES_DIR, "*.jpg")) +
                    glob.glob(os.path.join(IMAGES_DIR, "*.jpeg")))

    if len(images) < 5:
        print(f"[CALIB] Pas assez d'images ({len(images)}). Vise 10-20.")
        return

    objp = build_object_points(CHESSBOARD_SIZE, SQUARE_SIZE_M)
    objpoints, imgpoints = [], []
    image_size = None
    used = 0

    print(f"[CALIB] Lecture {len(images)} images dans {IMAGES_DIR}/ ...")
    for path in images:
        img = cv2.imread(path)
        if img is None:
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if image_size is None:
            image_size = (gray.shape[1], gray.shape[0])

        found, corners = cv2.findChessboardCorners(
            gray, CHESSBOARD_SIZE,
            flags=cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
        )
        if not found:
            continue

        corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), SUBPIX_CRIT)
        objpoints.append(objp.copy())
        imgpoints.append(corners2)
        used += 1

    if used < 5:
        print(f"[CALIB] Trop peu d'images valides ({used}).")
        return

    rms, K, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, image_size, None, None)
    hfov, vfov = compute_fov_from_K(K, image_size)

    print("\n=== RESULTATS ===")
    print(f"RMS: {rms:.4f}")
    print("K:\n", K)
    print("dist:\n", dist.ravel())
    print(f"HFOV: {hfov:.2f} deg | VFOV: {vfov:.2f} deg")

    np.savez(
        CALIB_NPZ,
        camera_matrix=K,
        dist_coeffs=dist,
        image_size=np.array(image_size, dtype=np.int32),
        rms=np.array([rms], dtype=np.float64),
        hfov_deg=np.array([hfov], dtype=np.float64),
        vfov_deg=np.array([vfov], dtype=np.float64),
        chessboard_size=np.array(CHESSBOARD_SIZE, dtype=np.int32),
        square_size=np.array([SQUARE_SIZE_M], dtype=np.float64),
    )
    save_yaml(CALIB_YAML, K, dist, image_size, rms, hfov, vfov)

    print(f"[CALIB] Sauvé: {CALIB_NPZ}")
    print(f"[CALIB] Sauvé: {CALIB_YAML}\n")

# =========================
# CAPTURE MODE
# =========================
def capture_images():
    ensure_dir(IMAGES_DIR)

    cap = cv2.VideoCapture(CAM_INDEX)
    if not cap.isOpened():
        raise RuntimeError(f"Impossible d'ouvrir la caméra index={CAM_INDEX}")

    ok, frame = cap.read()
    if not ok:
        cap.release()
        raise RuntimeError("Impossible de lire une frame caméra.")

    print("Touches: c=capture (UNIQUEMENT si damier OK) | k=calib | q=quit")

    img_count = len(glob.glob(os.path.join(IMAGES_DIR, "calib_*.png")))

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        display = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        found, corners = cv2.findChessboardCorners(
            gray, CHESSBOARD_SIZE,
            flags=cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
        )

        note_txt = "Quality: --"
        detail_txt = ""

        if found:
            corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), SUBPIX_CRIT)
            cv2.drawChessboardCorners(display, CHESSBOARD_SIZE, corners2, found)

            q, det = quality_score(corners2, display.shape)
            note_txt = f"Quality: {q:5.1f} / 100"
            detail_txt = f"area={det['area_ratio']*100:4.1f}%  center={det['center_score']*100:4.0f}%  skew={det['skew_score']*100:4.0f}%"

            draw_border(display, (0, 255, 0))  # vert
            status = "Chessboard: OK"
            status_color = (0, 255, 0)
        else:
            draw_border(display, (0, 0, 255))  # rouge
            status = "Chessboard: NOT FOUND"
            status_color = (0, 0, 255)

        cv2.putText(display, status, (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, status_color, 2)
        cv2.putText(display, note_txt, (20, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        if detail_txt:
            cv2.putText(display, detail_txt, (20, 115),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        cv2.putText(display, f"Saved: {img_count}", (20, 150),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        cv2.putText(display, "Keys: c=capture(OK only)  k=calib  q=quit", (20, display.shape[0]-25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        cv2.imshow("Camera calibration - preview", display)
        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            break

        elif key == ord('c'):
            if not found:
                print("[CAPTURE] Refus: chessboard non detecte.")
                continue

            ts = time.strftime("%Y%m%d_%H%M%S")
            fname = os.path.join(IMAGES_DIR, f"calib_{ts}_{img_count:04d}.png")
            cv2.imwrite(fname, frame)
            img_count += 1
            print(f"[CAPTURE] saved: {fname}")

        elif key == ord('k'):
            cap.release()
            cv2.destroyAllWindows()
            calibrate_from_folder()
            cap = cv2.VideoCapture(CAM_INDEX)
            if not cap.isOpened():
                print("Re-ouverture caméra impossible. Fin.")
                break

    cap.release()
    cv2.destroyAllWindows()

# =========================k
# MAIN
# =========================
if __name__ == "__main__":
    ensure_dir(IMAGES_DIR)
    capture_images()
