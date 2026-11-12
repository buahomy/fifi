#!/usr/bin/env python3
"""
ICS-204 Form Extractor with JSON Structured Output
Extracts structured data from ICS-204 images using Gemini API and exports to Excel/CSV
"""

import os
import sys
import json
import time
import pandas as pd
from pathlib import Path
from google import genai
from google.genai import types
from PIL import Image
import io
from datetime import datetime

BASE_DELAY = 30
RETRY_DELAY = 60
MAX_RETRIES = 3


def extract_ics204_data_with_retry(client, image_path):
    """Extract data from image with retry logic for rate limiting"""
    for attempt in range(MAX_RETRIES):
        try:
            return extract_ics204_data(client, image_path)

        except Exception as e:
            error_msg = str(e)

            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                if attempt < MAX_RETRIES - 1:
                    print(f"Rate limit hit for {image_path.name}. Attempt {attempt + 1}/{MAX_RETRIES}")
                    print(f"Pausing for {RETRY_DELAY} seconds before retry...")
                    time.sleep(RETRY_DELAY)
                    continue
                print(f"Max retries exceeded for {image_path.name} due to rate limiting")
                return {"error": "Rate limit exceeded after max retries", "details": error_msg}

            print(f"Error processing {image_path.name}: {error_msg}")
            return {"error": "Processing failed", "details": error_msg}

    return {"error": "Max retries exceeded"}


def image_to_jpeg_bytes(image_source):
    """Convert a file path or raw bytes into JPEG bytes for Gemini API."""
    if isinstance(image_source, (str, Path)):
        img = Image.open(image_source)
    else:
        img = Image.open(io.BytesIO(image_source))

    with img:
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='JPEG')
        img_buffer.seek(0)
        return img_buffer.getvalue()


def extract_ics204_data(client, image_path):
    """Extract structured ICS-204 data from image using Gemini API"""
    try:
        img_bytes = image_to_jpeg_bytes(image_path)
        return _extract_ics204_from_media(client, img_bytes, "image/jpeg", Path(image_path).name)
    except Exception as e:
        print(f"Error in extract_ics204_data for {Path(image_path).name}: {str(e)}")
        raise


def extract_ics204_data_from_bytes(client, file_bytes, filename="upload"):
    """Extract structured ICS-204 data from uploaded file bytes (PNG, JPG, or PDF)."""
    try:
        media_bytes, mime_type = prepare_file_for_gemini(file_bytes, filename)
        return _extract_ics204_from_media(client, media_bytes, mime_type, filename)
    except Exception as e:
        print(f"Error in extract_ics204_data_from_bytes for {filename}: {str(e)}")
        raise


def prepare_file_for_gemini(file_bytes, filename):
    """Return (bytes, mime_type) for Gemini — PDF as-is, images converted to JPEG."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return file_bytes, "application/pdf"
    return image_to_jpeg_bytes(file_bytes), "image/jpeg"


def _extract_ics204_from_media(client, media_bytes, mime_type, filename):
    """Core Gemini extraction logic shared by path and bytes entry points."""
    try:
        
        # Create content with image and structured extraction prompt
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text="""Extract all data from this ICS-204 Work Assignment Form and structure it as JSON. 
                    Please carefully read all fields including incident header, resources assigned, work assignments, communications plan, and approval section.
                    If a field is empty or not visible, use null or empty string as appropriate."""),
                    types.Part.from_bytes(data=media_bytes, mime_type=mime_type),
                ],
            ),
        ]
        
        generate_content_config = types.GenerateContentConfig(
            top_p=0.1,
            thinking_config=types.ThinkingConfig(
                thinking_level="HIGH",
            ),
            response_mime_type="application/json",
            response_schema=genai.types.Schema(
                type = genai.types.Type.OBJECT,
                required = ["incident_header", "resources_assigned", "work_assignments"],
                properties = {
                    "incident_header": genai.types.Schema(
                        type = genai.types.Type.OBJECT,
                        properties = {
                            "incident_name": genai.types.Schema(
                                type = genai.types.Type.STRING,
                            ),
                            "operational_period": genai.types.Schema(
                                type = genai.types.Type.STRING,
                            ),
                            "date_from": genai.types.Schema(
                                type = genai.types.Type.STRING,
                            ),
                            "date_to": genai.types.Schema(
                                type = genai.types.Type.STRING,
                            ),
                            "branch": genai.types.Schema(
                                type = genai.types.Type.STRING,
                            ),
                            "division_group": genai.types.Schema(
                                type = genai.types.Type.STRING,
                            ),
                        },
                    ),
                    "operations_personnel": genai.types.Schema(
                        type = genai.types.Type.OBJECT,
                        properties = {
                            "div_group_supervisor": genai.types.Schema(
                                type = genai.types.Type.STRING,
                            ),
                            "branch_director": genai.types.Schema(
                                type = genai.types.Type.STRING,
                            ),
                            "air_attack_supervisor": genai.types.Schema(
                                type = genai.types.Type.STRING,
                            ),
                            "operations_chief": genai.types.Schema(
                                type = genai.types.Type.STRING,
                            ),
                        },
                    ),
                    "resources_assigned": genai.types.Schema(
                        type = genai.types.Type.ARRAY,
                        items = genai.types.Schema(
                            type = genai.types.Type.OBJECT,
                            properties = {
                                "designator": genai.types.Schema(
                                    type = genai.types.Type.STRING,
                                ),
                                "lwd": genai.types.Schema(
                                    type = genai.types.Type.STRING,
                                ),
                                "leader": genai.types.Schema(
                                    type = genai.types.Type.STRING,
                                ),
                                "num_persons": genai.types.Schema(
                                    type = genai.types.Type.INTEGER,
                                ),
                                "drop_off": genai.types.Schema(
                                    type = genai.types.Type.STRING,
                                ),
                                "pick_up": genai.types.Schema(
                                    type = genai.types.Type.STRING,
                                ),
                            },
                        ),
                    ),
                    "work_assignments": genai.types.Schema(
                        type = genai.types.Type.OBJECT,
                        properties = {
                            "task": genai.types.Schema(
                                type = genai.types.Type.STRING,
                            ),
                            "purpose": genai.types.Schema(
                                type = genai.types.Type.STRING,
                            ),
                            "end_state": genai.types.Schema(
                                type = genai.types.Type.STRING,
                            ),
                        },
                    ),
                    "special_instructions": genai.types.Schema(
                        type = genai.types.Type.STRING,
                    ),
                    "communications_plan": genai.types.Schema(
                        type = genai.types.Type.ARRAY,
                        items = genai.types.Schema(
                            type = genai.types.Type.OBJECT,
                            properties = {
                                "function": genai.types.Schema(
                                    type = genai.types.Type.STRING,
                                ),
                                "channel": genai.types.Schema(
                                    type = genai.types.Type.STRING,
                                ),
                                "rx_frequency": genai.types.Schema(
                                    type = genai.types.Type.STRING,
                                ),
                                "rx_tone": genai.types.Schema(
                                    type = genai.types.Type.STRING,
                                ),
                                "tx_frequency": genai.types.Schema(
                                    type = genai.types.Type.STRING,
                                ),
                                "tx_tone": genai.types.Schema(
                                    type = genai.types.Type.STRING,
                                ),
                                "mode": genai.types.Schema(
                                    type = genai.types.Type.STRING,
                                ),
                            },
                        ),
                    ),
                    "approval": genai.types.Schema(
                        type = genai.types.Type.OBJECT,
                        properties = {
                            "prepared_by": genai.types.Schema(
                                type = genai.types.Type.STRING,
                            ),
                            "approved_by": genai.types.Schema(
                                type = genai.types.Type.STRING,
                            ),
                            "date": genai.types.Schema(
                                type = genai.types.Type.STRING,
                            ),
                            "time": genai.types.Schema(
                                type = genai.types.Type.STRING,
                            ),
                        },
                    ),
                },
            ),
        )
        
        # Generate content
        response = client.models.generate_content(
            model="gemini-3.1-pro-preview",
            contents=contents,
            config=generate_content_config,
        )
        
        # Parse JSON response
        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            print(f"Warning: Could not parse JSON response for {filename}")
            return {"error": "JSON parsing failed", "raw_response": response.text}

    except Exception as e:
        print(f"Error in _extract_ics204_from_media for {filename}: {str(e)}")
        raise


def flatten_ics204_data(data, image_filename):
    """Flatten the nested JSON data into a flat table structure"""
    flattened_records = []
    
    # Get incident header info
    incident_header = data.get("incident_header", {})
    incident_name = incident_header.get("incident_name", "Unknown")
    operational_period = incident_header.get("operational_period", "")
    date_from = incident_header.get("date_from", "")
    date_to = incident_header.get("date_to", "")
    branch = incident_header.get("branch", "")
    division_group = incident_header.get("division_group", "")
    
    # Get operations personnel
    ops_personnel = data.get("operations_personnel", {})
    div_group_supervisor = ops_personnel.get("div_group_supervisor", "")
    branch_director = ops_personnel.get("branch_director", "")
    air_attack_supervisor = ops_personnel.get("air_attack_supervisor", "")
    operations_chief = ops_personnel.get("operations_chief", "")
    
    # Get work assignments
    work_assignments = data.get("work_assignments", {})
    task = work_assignments.get("task", "")
    purpose = work_assignments.get("purpose", "")
    end_state = work_assignments.get("end_state", "")
    
    # Get special instructions
    special_instructions = data.get("special_instructions", "")
    
    # Get approval info
    approval = data.get("approval", {})
    prepared_by = approval.get("prepared_by", "")
    approved_by = approval.get("approved_by", "")
    approval_date = approval.get("date", "")
    approval_time = approval.get("time", "")
    
    # Process resources assigned (create one record per resource)
    resources = data.get("resources_assigned", [])
    if not resources:
        # Create a single record if no resources found
        record = {
            "source_image": image_filename,
            "incident_name": incident_name,
            "operational_period": operational_period,
            "date_from": date_from,
            "date_to": date_to,
            "branch": branch,
            "division_group": division_group,
            "div_group_supervisor": div_group_supervisor,
            "branch_director": branch_director,
            "air_attack_supervisor": air_attack_supervisor,
            "operations_chief": operations_chief,
            "resource_designator": "",
            "resource_lwd": "",
            "resource_leader": "",
            "num_persons": 0,
            "drop_off": "",
            "pick_up": "",
            "task": task,
            "purpose": purpose,
            "end_state": end_state,
            "special_instructions": special_instructions,
            "prepared_by": prepared_by,
            "approved_by": approved_by,
            "approval_date": approval_date,
            "approval_time": approval_time,
            "status": "NO_RESOURCES"
        }
        flattened_records.append(record)
    else:
        for resource in resources:
            record = {
                "source_image": image_filename,
                "incident_name": incident_name,
                "operational_period": operational_period,
                "date_from": date_from,
                "date_to": date_to,
                "branch": branch,
                "division_group": division_group,
                "div_group_supervisor": div_group_supervisor,
                "branch_director": branch_director,
                "air_attack_supervisor": air_attack_supervisor,
                "operations_chief": operations_chief,
                "resource_designator": resource.get("designator", ""),
                "resource_lwd": resource.get("lwd", ""),
                "resource_leader": resource.get("leader", ""),
                "num_persons": resource.get("num_persons", 0),
                "drop_off": resource.get("drop_off", ""),
                "pick_up": resource.get("pick_up", ""),
                "task": task,
                "purpose": purpose,
                "end_state": end_state,
                "special_instructions": special_instructions,
                "prepared_by": prepared_by,
                "approved_by": approved_by,
                "approval_date": approval_date,
                "approval_time": approval_time,
                "status": "OK"
            }
            # Add status analysis
            num_persons = resource.get("num_persons", 0)
            if num_persons < 2:
                record["status"] = "CRITICAL"
            elif num_persons == 0:
                record["status"] = "NO_PERSONNEL"
            else:
                record["status"] = "OK"
            
            flattened_records.append(record)
    
    # Process communications plan (create separate records)
    comm_plan = data.get("communications_plan", [])
    for comm in comm_plan:
        record = {
            "source_image": image_filename,
            "incident_name": incident_name,
            "operational_period": operational_period,
            "date_from": date_from,
            "date_to": date_to,
            "branch": branch,
            "division_group": division_group,
            "div_group_supervisor": div_group_supervisor,
            "branch_director": branch_director,
            "air_attack_supervisor": air_attack_supervisor,
            "operations_chief": operations_chief,
            "resource_designator": "",
            "resource_lwd": "",
            "resource_leader": "",
            "num_persons": 0,
            "drop_off": "",
            "pick_up": "",
            "task": task,
            "purpose": purpose,
            "end_state": end_state,
            "special_instructions": special_instructions,
            "prepared_by": prepared_by,
            "approved_by": approved_by,
            "approval_date": approval_date,
            "approval_time": approval_time,
            "comm_function": comm.get("function", ""),
            "comm_channel": comm.get("channel", ""),
            "comm_rx_frequency": comm.get("rx_frequency", ""),
            "comm_rx_tone": comm.get("rx_tone", ""),
            "comm_tx_frequency": comm.get("tx_frequency", ""),
            "comm_tx_tone": comm.get("tx_tone", ""),
            "comm_mode": comm.get("mode", ""),
            "status": "COMMUNICATION"
        }
        flattened_records.append(record)
    
    return flattened_records


def main():
    # Check for API key
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY environment variable not set")
        print("Please set your Google API key: export GOOGLE_API_KEY='your-api-key-here'")
        sys.exit(1)
    
    # Initialize Gemini client
    client = genai.Client(api_key=api_key)
    
    # Define paths (aligned with main.py)
    source_folder = Path("input_forms")
    output_folder = Path("output")
    
    # Ensure folders exist
    source_folder.mkdir(exist_ok=True)
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
    
    # Process all images and collect flattened data
    all_flattened_records = []
    extracted_json_data = {}
    
    for i, image_path in enumerate(image_files, 1):
        print(f"\nProcessing {i}/{len(image_files)}: {image_path.name}")
        
        # Extract structured data with retry logic
        extracted_data = extract_ics204_data_with_retry(client, image_path)
        
        # Save raw JSON
        json_filename = image_path.stem + "_extracted.json"
        json_path = output_folder / json_filename
        
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(extracted_data, f, indent=2, ensure_ascii=False)
            
            print(f"✓ JSON saved to: {json_path}")
            
            if "error" not in extracted_data:
                # Flatten the data
                flattened_records = flatten_ics204_data(extracted_data, image_path.name)
                all_flattened_records.extend(flattened_records)
            
            # Store for combined JSON
            extracted_json_data[image_path.stem] = extracted_data
            
        except Exception as e:
            print(f"✗ Error saving JSON for {image_path.name}: {str(e)}")
        
        # Rate limiting: pause between requests
        if i < len(image_files):
            print(f"Pausing for {BASE_DELAY} seconds before next image...")
            time.sleep(BASE_DELAY)
    
    # Create combined Excel file
    if all_flattened_records:
        df = pd.DataFrame(all_flattened_records)
        
        # Export to Excel
        excel_path = output_folder / "ICS_204_Combined_Analysis.xlsx"
        df.to_excel(excel_path, index=False)
        print(f"\n✓ Combined Excel file saved to: {excel_path}")
        
        # Export to CSV
        csv_path = output_folder / "ICS_204_Combined_Analysis.csv"
        df.to_csv(csv_path, index=False)
        print(f"✓ Combined CSV file saved to: {csv_path}")
        
        # Save combined JSON
        combined_json_path = output_folder / "all_extracted_ics204.json"
        with open(combined_json_path, 'w', encoding='utf-8') as f:
            json.dump(extracted_json_data, f, indent=2, ensure_ascii=False)
        print(f"✓ Combined JSON file saved to: {combined_json_path}")
        
        # Print summary statistics
        print(f"\n=== SUMMARY ===")
        print(f"Total images processed: {len(image_files)}")
        print(f"Total flattened records: {len(all_flattened_records)}")
        print(f"Critical resources (personnel < 2): {len([r for r in all_flattened_records if r.get('status') == 'CRITICAL'])}")
        print(f"Resources with no personnel: {len([r for r in all_flattened_records if r.get('status') == 'NO_PERSONNEL'])}")
        print(f"Communication records: {len([r for r in all_flattened_records if r.get('status') == 'COMMUNICATION'])}")
        
    else:
        print("\nNo data extracted from any images.")
    
    print(f"\nProcessing complete! All files saved to: {output_folder}")


if __name__ == "__main__":
    main()
