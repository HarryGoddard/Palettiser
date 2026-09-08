# Palettiser

Palettiser is a Python script that processes images by adding camera details and a color palette to the bottom of the images. It supports both portrait and landscape images and ensures that portrait images fit Instagram's 4:5 aspect ratio with a blurred background.

## Features

- Extracts and displays EXIF data (camera model, focal length, aperture, ISO, exposure time, date, and time).
- Adds a color palette extracted from the image.
- Supports portrait, landscape, and square images.
- Supports JPEG, PNG, TIFF, and WebP input images.
- Supports an optional centered title on each output image.
- Supports an optional inset border around each output image.
- Processes images in parallel using multiprocessing.

## Requirements

- Python 3.x
- Pillow
- colorthief

## Installation

1. Download the release, or clone the repository:
    ```sh
    git clone https://github.com/HarryGoddard/Palettiser.git
    cd Palettiser
    ```

2. Install the required dependencies:
    ```sh
    pip install -r requirements.txt
    ```

## Usage

1. Place your images in a directory.

2. Run the script with the directory path as an argument:
    ```sh
    python main.py path/to/your/images
    ```

    Replace `path/to/your/images` with the actual path to the directory containing your images.

    To add a title such as `Porto` to every output image:

    ```sh
    python main.py path/to/your/images --title "Porto"
    ```

    Add the optional inset border with `--border`, or combine both options:

    ```sh
    python main.py path/to/your/images --title "Porto" --border
    ```

3. The processed images will be saved in a subdirectory named `Paletised` within the input directory, organized into `landscape` and `portrait` subfolders.

## Example

### Before

#### Landscape
<img src="examples/before_landscape.jpg" alt="Before Landscape" width="300">

#### Portrait
<img src="examples/before_portrait.jpg" alt="Before Portrait" width="300">

### After

#### Landscape
<img src="examples/after_landscape.jpg" alt="After Landscape" width="300">

#### Portrait
<img src="examples/after_portrait.jpg" alt="After Portrait" width="300">

## Note(s)

Processed images are saved in `Paletised/landscape`, `Paletised/portrait`, or `Paletised/square` inside the input directory. The output keeps the source file extension and adds `_PRC` to the filename.

## License

This project is licensed under the Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0) License - see the [LICENSE](LICENSE) file for details.
