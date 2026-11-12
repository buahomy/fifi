#!/usr/bin/env python3
"""
Image Text Extractor using Google Gemini API
Extracts text from all images in the source folder and saves to Output folder
"""

import os
import sys
from pathlib import Path
from google import genai
from google.genai import types
from PIL import Image
import io


def extract_text_from_image(client, image_path):
    """Extract text from a single image using Gemini API"""
    try:
        # Read and process the image
        with Image.open(image_path) as img:
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Save to bytes buffer
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='JPEG')
            img_buffer.seek(0)
        
        # Create content with image
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text="Extract all text from this image. Provide the text exactly as it appears, maintaining the original formatting and structure."),
                    types.Part.from_bytes(data=img_buffer.getvalue(), mime_type="image/jpeg"),
                ],
            ),
        ]
        
        generate_content_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_level="HIGH",
            ),
        )
        
        # Generate content
        response = client.models.generate_content(
            model="gemini-3.1-pro-preview",
            contents=contents,
            config=generate_content_config,
        )
        
        return response.text
        
    except Exception as e:
        print(f"Error processing {image_path}: {str(e)}")
        return f"Error: {str(e)}"


def main():
    # Check for API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set")
        print("Please set your Gemini API key: export GEMINI_API_KEY='your-api-key-here'")
        sys.exit(1)
    
    # Initialize Gemini client
    client = genai.Client(api_key=api_key)
    
    # Define paths
    source_folder = Path("/Users/aiden/Desktop/ICS-204-small-run")
    output_folder = source_folder / "Output"
    
    # Ensure output folder exists
    output_folder.mkdir(exist_ok=True)
    
    # Find all image files
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif', '.webp'}
    image_files = []
    
    for ext in image_extensions:
        image_files.extend(source_folder.glob(f"*{ext}"))
        image_files.extend(source_folder.glob(f"*{ext.upper()}"))
    
    if not image_files:
        print(f"No image files found in {source_folder}")
        return
    
    print(f"Found {len(image_files)} image files to process...")
    
    # Process each image
    for i, image_path in enumerate(image_files, 1):
        print(f"\nProcessing {i}/{len(image_files)}: {image_path.name}")
        
        # Extract text
        extracted_text = extract_text_from_image(client, image_path)
        
        # Save to output file
        output_filename = image_path.stem + "_extracted_text.txt"
        output_path = output_folder / output_filename
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"Extracted text from: {image_path.name}\n")
                f.write("=" * 50 + "\n\n")
                f.write(extracted_text)
                f.write("\n\n" + "=" * 50 + "\n")
                f.write(f"Processing completed at: {__import__('datetime').datetime.now()}\n")
            
            print(f"✓ Text saved to: {output_path}")
            
        except Exception as e:
            print(f"✗ Error saving text for {image_path.name}: {str(e)}")
    
    print(f"\nProcessing complete! All extracted text files saved to: {output_folder}")


if __name__ == "__main__":
    main()
