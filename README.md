# Image Text Extractor

This script extracts text from all images in the `~/Desktop/ICS-204-small-run` folder using Google Gemini API and saves the extracted text to the `Output` folder.

## Setup

1. Install dependencies:
```bash
pip3 install -r requirements.txt
```

2. Set your Gemini API key:
```bash
export GEMINI_API_KEY='your-api-key-here'
```

## Usage

Run the script:
```bash
python3 image_text_extractor.py
```

## What it does

- Scans the source folder for all image files (jpg, jpeg, png, bmp, tiff, gif, webp)
- Processes each image using Google Gemini 2.0 Flash model
- Extracts text while maintaining original formatting
- Saves each result as a separate text file in the `Output` folder
- Files are named as `[original_filename]_extracted_text.txt`

## Output

Each output file contains:
- Source image filename
- Extracted text content
- Processing timestamp

The script will process all 11 JPG files found in the folder and create corresponding text files in the Output directory.
