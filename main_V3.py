import os
import shutil
import zipfile
import py7zr
import rarfile
import tempfile
from PIL import Image
from datetime import datetime


COUNTS = {
    "Character": 0,
    "Clothing": 0,
    "Scene": 0,
    "Mod": 0,
    "Extra": 0,
    "Archives": 0,
    "Errors": 0,
    "TotalFiles": 0
}

LOG_PATH = None

SORTED_ROOT = None


# ==================================================
# LOGGING
# ==================================================

def create_log_file(sorted_files_dir):
    os.makedirs(sorted_files_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = os.path.join(
        sorted_files_dir,
        f"sort_log_{timestamp}.txt"
    )

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("=== Koikatsu Sort Session ===\n")

    return log_path

def log_message(message):
    if LOG_PATH is None:
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


# ==================================================
# FOLDER/FILE HELPERS
# ==================================================

def setup_sorted_folders(base_dir):
    sorted_root = os.path.join(base_dir, "sorted_files")

    folders = {
        "Character": os.path.join(sorted_root, "chara"),
        "Clothing": os.path.join(sorted_root, "cloth"),
        "Scene": os.path.join(sorted_root, "scene"),
        "Mod": os.path.join(sorted_root, "mod"),
        "Extra": os.path.join(sorted_root, "extra"),
    }

    for path in folders.values():
        os.makedirs(path, exist_ok=True)

    return sorted_root, folders

def unique_path(folder, filename):
    name, ext = os.path.splitext(filename)
    counter = 1
    dest = os.path.join(folder, filename)

    while os.path.exists(dest):
        dest = os.path.join(folder, f"{name}({counter}){ext}")
        counter += 1

    return dest


# ==================================================
# DETECT CARD TYPE
# ==================================================

def detect_koikatsu_card_type(path):
    width = height = None
    try:
        with Image.open(path) as img:
            width, height = img.size
    except Exception:
        pass

    try:
        with open(path, "rb") as f:
            data = f.read()
    except Exception:
        return "Unknown"

    score = {
        "Scene": 0,
        "Character": 0,
        "Clothing": 0
    }

    if b"KoiKatuScene" in data or b"KoikatuScene" in data:
        score["Scene"] += 4

    if b"<constraints" in data or b"<itemInfo" in data:
        score["Scene"] += 3

    if b"KoiKatuClothes" in data:
        score["Clothing"] += 4

    if b"KoiKatuChara" in data or b"KoikatuChara" in data:
        score["Character"] += 3

    chara_count = (
        data.count(b"KoiKatuChara") +
        data.count(b"KoikatuChara")
    )

    if chara_count >= 2:
        score["Scene"] += 4

    if width is not None and height is not None:
        if (width, height) == (320, 180):
            score["Scene"] += 3
        if (width, height) in [(252, 352), (252, 353), (504, 704)]:
            score["Character"] += 1

    filename = os.path.basename(path).upper()
    if filename.startswith("KKSCENE_"):
        score["Scene"] += 1

    card_type = max(score, key=score.get)
    if score[card_type] == 0:
        return "Unknown"

    return card_type


# ==================================================
# ARCHIVE EXTRACTION
# ==================================================

def extract_archive(path, temp_dir):
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            z.extractall(temp_dir)

    elif path.lower().endswith(".7z"):
        with py7zr.SevenZipFile(path, mode="r") as z:
            z.extractall(temp_dir)

    elif path.lower().endswith(".rar"):
        with rarfile.RarFile(path) as r:
            r.extractall(temp_dir)


# ==================================================
# CORE SCAN LOGIC
# ==================================================

def scan_path(path, output_dirs):
    if os.path.normpath(path).startswith(SORTED_ROOT):
        return
    
    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            for f in files:
                scan_path(os.path.join(root, f), output_dirs)
        return

    lower = path.lower()
    filename = os.path.basename(path)

    # ---- ZIPMOD ----
    if lower.endswith(".zipmod"):
        dest = unique_path(output_dirs["Mod"], filename)
        shutil.copy2(path, dest)
        COUNTS["Mod"] += 1
        COUNTS["TotalFiles"] += 1
        return

    # ---- ARCHIVES ----
    if lower.endswith((".zip", ".7z", ".rar")):
        COUNTS["Archives"] += 1
        with tempfile.TemporaryDirectory() as tmp:
            try:
                extract_archive(path, tmp)
                scan_path(tmp, output_dirs)
            except Exception:
                dest = unique_path(output_dirs["Extra"], filename)
                shutil.copy2(path, dest)
                COUNTS["Errors"] += 1
        return

    # ---- PNG CARD ----
    if lower.endswith(".png"):
        card_type = detect_koikatsu_card_type(path)

        if card_type == "Character":
            dest_dir = output_dirs["Character"]
        elif card_type == "Clothing":
            dest_dir = output_dirs["Clothing"]
        elif card_type == "Scene":
            dest_dir = output_dirs["Scene"]
        else:
            dest_dir = output_dirs["Extra"]

        dest = unique_path(dest_dir, filename)
        shutil.copy2(path, dest)
        COUNTS[card_type] += 1
        COUNTS["TotalFiles"] += 1
        return

    # ---- EVERYTHING ELSE ----
    dest = unique_path(output_dirs["Extra"], filename)
    shutil.copy2(path, dest)
    COUNTS["Extra"] += 1
    COUNTS["TotalFiles"] += 1


# ==================================================
# ENTRY POINT
# ==================================================

if __name__ == "__main__":
    source_dir = input("Enter folder to scan: ").strip()
    # base_dir = input("Enter base output directory: ").strip()
    base_dir = source_dir

    if not os.path.isdir(source_dir):
        print("Invalid source folder")
        exit()

    if not os.path.isdir(base_dir):
        print("Invalid output base folder")
        exit()

    sorted_root, output_dirs = setup_sorted_folders(base_dir)
    SORTED_ROOT = os.path.normpath(sorted_root)
    LOG_PATH = create_log_file(sorted_root)

    print("Please wait, files are being scanned...")

    scan_path(source_dir, output_dirs)

    log_message("=== Summary ===")
    log_message(f"Total files processed: {COUNTS['TotalFiles']}")
    log_message(f"Character cards: {COUNTS['Character']}")
    log_message(f"Clothing cards: {COUNTS['Clothing']}")
    log_message(f"Scene cards: {COUNTS['Scene']}")
    log_message(f"Mod files (.zipmod): {COUNTS['Mod']}")
    log_message(f"Extra files: {COUNTS['Extra']}")
    log_message(f"Archives processed: {COUNTS['Archives']}")
    log_message(f"Errors: {COUNTS['Errors']}")
    log_message("=== Sort completed successfully ===")

    log_message("Sort completed successfully")
    print("\nDone. Files sorted into 'sorted_files' folder.")
