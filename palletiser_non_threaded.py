import sys
import os
import glob
from PIL import Image, ImageDraw, ImageFont, ExifTags, ImageOps
from colorthief import ColorThief

# Constants
MODE = 1
BORDER_RATIO = 0.1
BOLD_RATIO = 0.05
SUB_RATIO = 0.0275
COURIER_RATIO = 0.02
EXTENDED_RATIO = 2 * BORDER_RATIO + BOLD_RATIO + SUB_RATIO

def extract_exif_data(exif):
    """
    Extract relevant EXIF data from the image.
    :param exif: The EXIF data from the image.
    :return: A tuple containing focal length, aperture, lens model, ISO, exposure, date, time, and camera model.
    """
    foc, ape, lmd, iso, exp, date, time, mod = "", "", "", "", "", "", "", ""

    # Loop through the EXIF IFDs
    for ifd_id in ExifTags.IFD:
        try:
            ifd = exif.get_ifd(ifd_id)
        except KeyError:
            continue

        for k, v in ifd.items():
            if k not in ExifTags.TAGS:
                continue
            if ExifTags.TAGS[k] == "FocalLength":
                foc = f"{v}mm".strip()
            if ExifTags.TAGS[k] == "ApertureValue":
                ape = f"f/{round(float(v), 2)}".strip()
            if ExifTags.TAGS[k] == "LensModel":
                lmd = v.rstrip("\0").split("|")[0]
            if ExifTags.TAGS[k] == "ISOSpeedRatings":
                iso = f"ISO{v}"
            if ExifTags.TAGS[k] == "ExposureTime":
                den = int(1 / float(v))
                exp = f"1/{den}"
            if ExifTags.TAGS[k] == "DateTimeOriginal":
                (raw_date, time) = v.split(" ")
                # Convert date from YYYY:MM:DD to DD/MM/YYYY
                year, month, day = raw_date.split(":")
                date = f"{day}/{month}/{year}"

    # Extract camera model from EXIF
    for tid in exif:
        tag = ExifTags.TAGS.get(tid, tid)
        dat = exif.get(tid)
        if tag == "Model":
            mod = dat.strip()
            break

    return foc, ape, lmd, iso, exp, date, time, mod


def calculate_dimensions(im, maxdim):
    """
    Calculate various font sizes and border dimensions based on image size.
    :param im: The PIL image object.
    :param maxdim: The maximum dimension (width or height) of the image.
    :return: A tuple of calculated border, bold, sub, and courier font sizes.
    """
    border = int(maxdim * BORDER_RATIO)
    bold = int(maxdim * BOLD_RATIO)
    sub = int(maxdim * SUB_RATIO)
    cour = int(maxdim * COURIER_RATIO)
    return border, bold, sub, cour


def process_image(image_path, output_dir):
    """
    Process the image, add a border, extract EXIF data, and save a new image with EXIF information and color palette.
    :param image_path: Path to the input image file.
    :param output_dir: Directory where the processed image will be saved.
    """
    im = Image.open(image_path).convert("RGB")
    im = ImageOps.exif_transpose(im)  # Handle EXIF rotation
    exif = im.getexif()

    # Extract EXIF data
    foc, ape, lmd, iso, exp, date, time, mod = extract_exif_data(exif)

    maxdim = max(im.size[0], im.size[1])
    border, bold, sub, cour = calculate_dimensions(im, maxdim)

    # Load fonts
    bold_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", bold)
    sub_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", sub)
    cour_font = ImageFont.truetype("C:/Windows/Fonts/cour.ttf", cour)

    # Create new image with additional space for EXIF data and palette
    if MODE == 1:
        sq = im.size[0] // 6
        sqh = int(sq * 2 / 3)
        nx = im.size[0] + 2 * border
        ny = im.size[1] + int(3 * border) + int((BOLD_RATIO + SUB_RATIO) * maxdim) + sqh

        nim = Image.new("RGB", (nx, ny), (0xff, 0xff, 0xff))  # White background

        # Paste the original image into the new one
        offy = border + int((BOLD_RATIO + SUB_RATIO) * maxdim) + border // 2
        nim.paste(im, (border, offy))

        d = ImageDraw.Draw(nim)
        d.fontmode = "L"

        # Add text with EXIF data
        offy = border - d.textbbox((0, 0), "TEST", font=bold_font)[1] // 2
        d.text((border, offy), mod, font=bold_font, fill=(0, 0, 0))
        offy += BOLD_RATIO * maxdim
        d.text((border, offy), lmd, font=sub_font, fill=(0xa0, 0xa0, 0xa0))

        # Add right-side EXIF data text
        rtxt = f"{iso} {foc} {ape} {exp}\n{time} {date}"
        offx = im.size[0] + border
        offy = border + (BOLD_RATIO + SUB_RATIO) * maxdim // 2
        d.text((offx, offy), rtxt, font=cour_font, fill=(0xa0, 0xa0, 0xa0), anchor="rm", align="right")

        # Get color palette from the image
        ct = ColorThief(image_path)
        palette = ct.get_palette(color_count=6, quality=2)

        # Draw the palette as colored rectangles at the bottom
        offy = border + int((BOLD_RATIO + SUB_RATIO) * maxdim) + border // 2 + im.size[1] + border // 2
        for x in range(6):
            coords = (border + x * sq, offy, border + (x + 1) * sq, offy + sqh)
            d.rectangle(coords, fill=palette[x])

        # Save the processed image in the output directory
        base_filename = os.path.basename(image_path)
        filename, ext = os.path.splitext(base_filename)
        new_filename = f"{filename}_PRC{ext}"
        save_path = os.path.join(output_dir, new_filename)
        nim.save(save_path)
        print(f"Processed and saved: {save_path}")


if __name__ == "__main__":
    # Ensure a directory path is provided
    if len(sys.argv) < 2:
        print("No directory given")
        exit(1)

    input_directory = sys.argv[1]
    output_directory = os.path.join(input_directory, "Paletted")

    # Create the output directory if it doesn't exist
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    # Process all image files in the directory (JPEG and PNG formats)
    image_files = glob.glob(os.path.join(input_directory, "*.jpg")) + glob.glob(os.path.join(input_directory, "*.png"))

    for image_file in image_files:
        process_image(image_file, output_directory)

    print("All images saved.")
