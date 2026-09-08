# Author: Harry Goddard

import os
import platform
import argparse
import sys
from PIL import Image, ImageDraw, ImageFont, ExifTags, ImageOps
from colorthief import ColorThief
from concurrent.futures import ProcessPoolExecutor, as_completed

# Constants
BORDER_RATIO = 0.1
BOLD_RATIO = 0.05
SUB_RATIO = 0.0275
COURIER_RATIO = 0.02
SECONDARY_TEXT = (0x7A, 0x7A, 0x7A)

# Supported image extensions
IMAGE_EXTENSIONS = ("*.jpg", "*.jpeg", "*.png", "*.tif", "*.tiff", "*.webp")

# Friendly names for camera identifiers commonly written to EXIF.
CAMERA_MODEL_NAMES = {
    ("SONY", "ILCE-6700"): "Sony A6700",
}


def resolve_font_paths():
    """
    Resolve system font paths in a cross-platform way.
    Falls back to Pillow's default font if system fonts are unavailable.
    :return: A dict of font paths for 'bold', 'sub', and 'cour' keys.
    """
    system = platform.system()

    candidates = {
        "Windows": {
            "bold": [
                "C:/Windows/Fonts/arialbd.ttf",
                "C:/Windows/Fonts/arial.ttf",
            ],
            "title": [
                "C:/Windows/Fonts/georgiab.ttf",
                "C:/Windows/Fonts/timesbd.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
            ],
            "sub": ["C:/Windows/Fonts/arial.ttf"],
            "cour": ["C:/Windows/Fonts/cour.ttf"],
        },
        "Darwin": {  # macOS
            "bold": [
                "/System/Library/Fonts/Helvetica.ttc",
                "/Library/Fonts/Arial Bold.ttf",
                "/Library/Fonts/Arial.ttf",
            ],
            "title": [
                "/Library/Fonts/Georgia Bold.ttf",
                "/Library/Fonts/Times New Roman Bold.ttf",
                "/Library/Fonts/Arial Bold.ttf",
            ],
            "sub": [
                "/Library/Fonts/Arial.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
            ],
            "cour": [
                "/Library/Fonts/Courier New.ttf",
                "/System/Library/Fonts/Courier.ttc",
            ],
        },
        "Linux": {
            "bold": [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            ],
            "title": [
                "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/"
                "LiberationSerif-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            ],
            "sub":  [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/"
                "LiberationSans-Regular.ttf",
            ],
            "cour": [
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                "/usr/share/fonts/truetype/liberation/"
                "LiberationMono-Regular.ttf",
            ],
        },
    }

    paths = {}
    font_candidates = candidates.get(system, candidates["Linux"])
    for role, candidate_list in font_candidates.items():
        for path in candidate_list:
            if os.path.exists(path):
                paths[role] = path
                break
        else:
            paths[role] = None

    return paths


def load_font(path, size):
    """
    Load a TrueType font, falling back to Pillow's built-in default
    if unavailable.
    :param path: Path to the .ttf font file, or None.
    :param size: Desired font size in pixels.
    :return: An ImageFont instance.
    """
    if path and os.path.exists(path):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def format_camera_model(make, model):
    """Return a friendly camera name when a known EXIF identifier matches."""
    make = str(make).strip().upper()
    model = str(model).strip()
    return CAMERA_MODEL_NAMES.get((make, model.upper()), model)


def extract_exif_data(exif):
    """
    Extract relevant EXIF data from the image.
    :param exif: The EXIF data from the image.
    :return: A tuple containing focal length, aperture, lens model, ISO,
             exposure, date, shot_time, and camera model.
    """
    foc, ape, lmd, iso = "", "", "", ""
    exp, date, shot_time, mod = "", "", "", ""

    for ifd_id in ExifTags.IFD:
        try:
            ifd = exif.get_ifd(ifd_id)
        except KeyError:
            continue

        for k, v in ifd.items():
            if k not in ExifTags.TAGS:
                continue
            tag_name = ExifTags.TAGS[k]

            try:
                if tag_name == "FocalLength":
                    foc = f"{round(float(v), 1):g}mm"
                elif tag_name == "FNumber":
                    ape = f"f/{round(float(v), 1):g}"
                elif tag_name == "LensModel":
                    lmd = str(v).rstrip("\0").split("|")[0].strip()
                elif tag_name == "ISOSpeedRatings":
                    iso = f"ISO{v}"
                elif tag_name == "ExposureTime":
                    fv = float(v)
                    if fv <= 0:
                        continue
                    if fv >= 1:
                        exp = f"{int(fv)}s"
                    else:
                        den = round(1 / fv)
                        exp = f"1/{den}s"
                elif tag_name == "DateTimeOriginal":
                    parts = str(v).split(" ")
                    if len(parts) == 2:
                        raw_date, candidate_time = parts
                        date_parts = raw_date.split(":")
                        if len(date_parts) == 3:
                            year, month, day = date_parts
                            date = f"{day}/{month}/{year}"
                            shot_time = candidate_time
            except (TypeError, ValueError, ZeroDivisionError):
                continue

    make = ""
    model = ""
    for tid in exif:
        tag = ExifTags.TAGS.get(tid, tid)
        if tag == "Model":
            val = exif.get(tid)
            if val:
                model = str(val).strip()
        elif tag == "Make":
            val = exif.get(tid)
            if val:
                make = str(val).strip()

    mod = format_camera_model(make, model)

    return foc, ape, lmd, iso, exp, date, shot_time, mod


def get_orientation(width, height):
    """
    Classify image orientation as landscape, portrait, or square.
    :param width: Image width in pixels.
    :param height: Image height in pixels.
    :return: One of 'landscape', 'portrait', or 'square'.
    """
    if width > height:
        return "landscape"
    elif height > width:
        return "portrait"
    else:
        return "square"


def calculate_dimensions(maxdim):
    """
    Calculate border thickness and font sizes based on the largest image
    dimension.
    :param maxdim: The maximum dimension (width or height) of the image.
    :return: A tuple of (border, bold_size, sub_size, cour_size).
    """
    border = max(1, int(maxdim * BORDER_RATIO))
    bold = max(1, int(maxdim * BOLD_RATIO))
    sub = max(1, int(maxdim * SUB_RATIO))
    cour = max(1, int(maxdim * COURIER_RATIO))
    return border, bold, sub, cour


def process_image(
    image_path, output_dir, font_paths, title="", add_border=False
):
    """
    Process an image: correct orientation, add a white border, overlay EXIF
    metadata, extract and display a dominant colour palette, then save to a
    subfolder.
    :param image_path: Path to the input image file.
    :param output_dir: Root directory where processed images will be saved.
    :param font_paths: Dict of font file paths keyed by 'bold', 'sub', 'cour'.
    :param title: Optional title to display at the top of the output.
    :param add_border: Whether to draw the inset outer frame.
    """
    base_filename = os.path.basename(image_path)
    filename, ext = os.path.splitext(base_filename)
    new_filename = f"{filename}_PRC{ext}"

    try:
        # Read EXIF before any transpose so orientation data is intact
        with Image.open(image_path) as source:
            exif = source.getexif()
            im_raw = source.convert("RGB")
        im = ImageOps.exif_transpose(im_raw)

        orientation = get_orientation(im.width, im.height)

        save_dir = os.path.join(output_dir, orientation)
        os.makedirs(save_dir, exist_ok=True)

        save_path = os.path.join(save_dir, new_filename)
        if os.path.exists(save_path) and not title and not add_border:
            print(f"Skipping {image_path}, already processed.")
            return

        foc, ape, lmd, iso, exp, date, shot_time, mod = extract_exif_data(exif)

        maxdim = max(im.width, im.height)
        border, bold_size, sub_size, cour_size = calculate_dimensions(maxdim)

        bold_font = load_font(font_paths["bold"], bold_size)
        title_size = max(1, int(bold_size * 0.95))
        title_font = load_font(font_paths["title"], title_size)
        sub_font = load_font(font_paths["sub"], sub_size)
        cour_font = load_font(font_paths["cour"],  cour_size)

        # Keep the palette within the image width, including for portraits.
        num_swatches = 6
        swatch_gap = max(2, border // 20)
        available_width = im.width - swatch_gap * (num_swatches - 1)
        sq = max(1, available_width // num_swatches)
        sqh = max(1, int(sq * 2 / 3))

        header_height = int((BOLD_RATIO + SUB_RATIO) * maxdim)
        nx = im.width + 2 * border
        ny = im.height + 3 * border + header_height + sqh

        nim = Image.new("RGB", (nx, ny), (0xFF, 0xFF, 0xFF))

        img_x = border
        img_y = border + header_height + border // 2
        nim.paste(im, (img_x, img_y))

        d = ImageDraw.Draw(nim)
        d.fontmode = "L"
        frame_inset = max(2, border // 2) if add_border else 0

        if title:
            title_bbox = d.textbbox((0, 0), title, font=title_font)
            title_height = title_bbox[3] - title_bbox[1]
            if add_border:
                title_y = frame_inset // 2
                title_anchor = "mm"
            else:
                title_y = border - title_height // 2 - max(1, border // 12)
                title_anchor = "ms"
            d.text(
                (nx // 2, title_y),
                title,
                font=title_font,
                fill=(0, 0, 0),
                anchor=title_anchor,
            )

        # Camera model (bold) and lens model (sub) — top-left
        text_y = border - d.textbbox((0, 0), "TEST", font=bold_font)[1] // 2
        d.text((border, text_y), mod, font=bold_font, fill=(0, 0, 0))
        text_y += int(BOLD_RATIO * maxdim)
        d.text((border, text_y), lmd, font=sub_font, fill=SECONDARY_TEXT)

        # Shooting parameters — top-right, right-aligned
        rtxt = f"{iso}  {foc}  {ape}  {exp}"
        rtxt += f"\n{shot_time}  {date}" if (shot_time or date) else ""
        right_x = im.width + border
        right_y = int(border + header_height / 2)
        d.text(
            (right_x, right_y),
            rtxt,
            font=cour_font,
            fill=SECONDARY_TEXT,
            anchor="rm",
            align="right",
        )

        # Colour palette swatches — centred below the image
        ct = ColorThief(image_path)
        palette = ct.get_palette(color_count=num_swatches, quality=10)
        swatch_y = img_y + im.height + border // 2
        swatch_width = sq * num_swatches + swatch_gap * (num_swatches - 1)
        swatch_x = border + (im.width - swatch_width) // 2
        for i, colour in enumerate(palette[:num_swatches]):
            swatch_left = swatch_x + i * (sq + swatch_gap)
            coords = (
                swatch_left,
                swatch_y,
                swatch_left + sq - 1,
                swatch_y + sqh - 1,
            )
            d.rectangle(coords, fill=colour)

        if add_border:
            frame_width = max(1, border // 80)
            d.rectangle(
                (
                    frame_inset,
                    frame_inset,
                    nx - frame_inset - 1,
                    ny - frame_inset - 1,
                ),
                outline=(0, 0, 0),
                width=frame_width,
            )

        extension = os.path.splitext(save_path)[1].lower()
        if extension in (".jpg", ".jpeg"):
            nim.save(save_path, quality=100, subsampling=0)
        elif extension == ".webp":
            nim.save(save_path, lossless=True, quality=100)
        else:
            nim.save(save_path)
        print(f"Saved: {save_path}")

    except Exception as e:
        print(f"Error processing {image_path}: {e}")


def process_images_in_parallel(
    image_files, output_dir, title="", add_border=False
):
    """
    Process multiple images concurrently using a process pool.
    :param image_files: List of image file paths.
    :param output_dir: Root directory to save processed images.
    :param title: Optional title to display at the top of each output.
    :param add_border: Whether to draw the inset outer frame.
    """
    if not image_files:
        return

    cpu_count = os.cpu_count() or 1
    max_workers = min(cpu_count, len(image_files))
    print(f"CPU count = {cpu_count}. Processes set to {max_workers}.")

    font_paths = resolve_font_paths()
    print(f"Fonts resolved: { {k: v for k, v in font_paths.items()} }")

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_image = {
            executor.submit(
                process_image,
                f,
                output_dir,
                font_paths,
                title,
                add_border,
            ): f
            for f in image_files
        }
        for future in as_completed(future_to_image):
            image_file = future_to_image[future]
            try:
                future.result()
            except Exception as exc:
                print(f"{image_file} raised an exception: {exc}")


def find_image_files(input_directory):
    """Return supported image files directly inside the input directory."""
    supported_extensions = {
        pattern[2:].lower() for pattern in IMAGE_EXTENSIONS
    }
    image_files = []
    for name in os.listdir(input_directory):
        image_path = os.path.join(input_directory, name)
        extension = os.path.splitext(name)[1].lower().lstrip(".")
        if os.path.isfile(image_path) and extension in supported_extensions:
            image_files.append(image_path)
    return image_files


def main():
    parser = argparse.ArgumentParser(
        description="Add camera metadata and a colour palette to images."
    )
    parser.add_argument(
        "input_directory",
        help="Directory containing the source images",
    )
    parser.add_argument(
        "--title",
        default="",
        help="Optional title to center at the top of each output",
    )
    parser.add_argument(
        "--border",
        action="store_true",
        help="Add a thin inset border around each output",
    )
    args = parser.parse_args()

    input_directory = os.path.abspath(args.input_directory)
    title = args.title.strip()
    if not os.path.isdir(input_directory):
        parser.error(f"input directory does not exist: {args.input_directory}")

    output_directory = os.path.join(input_directory, "Paletised")
    os.makedirs(output_directory, exist_ok=True)

    image_files = find_image_files(input_directory)

    if not image_files:
        print(f"No supported images found in {input_directory}")
        sys.exit(0)

    print(f"Found {len(image_files)} image(s) to process.")
    process_images_in_parallel(
        image_files, output_directory, title, args.border
    )
    print("All images saved.")


if __name__ == "__main__":
    main()
