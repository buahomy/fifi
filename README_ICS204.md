# ICS-204 Form Extractor

This script extracts structured data from ICS-204 Work Assignment Forms using Google Gemini API and converts the nested JSON data into clean Excel/CSV spreadsheets.

## Features

- **Structured JSON Extraction**: Uses Gemini API with predefined schema to extract ICS-204 form data
- **Data Flattening**: Converts nested JSON into flat table structure for analysis
- **Multiple Output Formats**: Generates Excel, CSV, and JSON files
- **Status Analysis**: Automatically flags critical resource assignments (personnel < 2)
- **Comprehensive Data**: Extracts incident header, resources, work assignments, communications, and approval info

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
python3 ics204_extractor.py
```

## Output Files

The script generates several output files in the `/Output` folder:

### Individual Files (per image)
- `[filename]_extracted.json` - Raw extracted JSON data

### Combined Files (all images)
- `ICS_204_Combined_Analysis.xlsx` - Excel spreadsheet with flattened data
- `ICS_204_Combined_Analysis.csv` - CSV version of the flattened data
- `all_extracted_ics204.json` - Combined JSON data from all images

## Data Structure

The flattened table includes these columns:
- **Source Info**: source_image, incident_name, operational_period
- **Personnel**: div_group_supervisor, branch_director, operations_chief
- **Resources**: resource_designator, resource_leader, num_persons, drop_off, pick_up
- **Work Details**: task, purpose, end_state, special_instructions
- **Communications**: comm_function, comm_channel, frequencies
- **Approval**: prepared_by, approved_by, approval_date, approval_time
- **Status**: CRITICAL (personnel < 2), OK, NO_PERSONNEL, COMMUNICATION

## Analysis Features

- **Critical Resource Detection**: Automatically flags assignments with less than 2 personnel
- **Summary Statistics**: Shows total images, records, and critical resources
- **Communication Records**: Separate entries for communication plan items
- **Resource Tracking**: One row per resource assignment with full context

## Processing

The script will:
1. Process all 11 JPG images in the source folder
2. Extract structured JSON data using Gemini API
3. Flatten nested data into tabular format
4. Generate analysis-ready Excel/CSV files
5. Provide summary statistics and status flags
