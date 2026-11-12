# ICS-204 Production Processor

Production-ready Python script for processing ICS-204 incident management forms with robust error handling and handwritten text detection.

## Features

- **Rate Limiting Protection**: Handles 429 errors with exponential backoff and 60-second retries
- **Handwritten Text Detection**: Specialized OCR for handwritten notes, red ink annotations, and corrections
- **Confidence Scoring**: LLM estimates extraction confidence (0-100) with human review flags
- **Resource Gap Analysis**: Automatic flagging of understaffed resources
- **Production Logging**: Comprehensive logging to file and console
- **Structured JSON Output**: Enforced schema with validation

## Environment Setup

1. **Install Dependencies**:
```bash
pip install -r requirements_main.txt
```

2. **Set API Key**:
```bash
export GOOGLE_API_KEY='your-google-api-key-here'
```

3. **Prepare Input**:
   - Place ICS-204 images in `input_forms/` folder
   - Supported formats: `.jpg`, `.jpeg`, `.png`

## Usage

```bash
python3 main.py
```

## Rate Limiting Strategy

The script implements multiple layers of protection against rate limits:

1. **Base Delay**: 30-second pause between each image
2. **Retry Logic**: Up to 3 attempts per image on 429 errors
3. **Graceful Recovery**: 60-second pause on rate limit hits
4. **Error Logging**: Detailed logging of all rate limit events

## Output Files

### Primary Output
- `output/Resource_Analysis.csv` - Main analysis file with all extracted data

### Supporting Files
- `output/Processing_Summary.csv` - Processing statistics
- `ics204_processor.log` - Detailed processing log

## CSV Data Structure

The Resource_Analysis.csv includes:

### Core Fields
- `source_image` - Original image filename
- `incident_name` - Extracted incident name
- `division_group` - Division/group assignment
- `designator` - Resource designator (e.g., "CRW-1")
- `lwd` - Location, Work, Date information
- `leader` - Resource leader name
- `num_persons` - Number of personnel assigned

### Quality & Confidence
- `is_handwritten` - Boolean flag for handwritten text
- `confidence_score` - LLM confidence (0-100)
- `requires_human_review` - Flag for ambiguous/crossed-out text

### Analysis Fields
- `resource_status` - Automated gap analysis:
  - `CRITICAL_NO_PERSONNEL` - 0 personnel
  - `CRITICAL_UNDERSTAFFED` - 1 personnel
  - `CAUTION_MINIMAL` - 2-3 personnel
  - `ADEQUATE` - 4+ personnel
- `processing_timestamp` - When the record was processed

## Handwritten Text Detection

The script is specifically optimized for:

- **Red/Blue Ink Annotations**: Resource replacements, LWD changes
- **Crossed-out Text**: With replacements or corrections
- **Handwritten Modifications**: Personnel changes, new assignments
- **Ambiguous Writing**: Low confidence scoring triggers human review

## Error Handling

### Rate Limiting (429 Errors)
- Automatic detection of quota exceeded errors
- 60-second retry delay with exponential backoff
- Maximum 3 retry attempts per image
- Graceful continuation after rate limit recovery

### Processing Errors
- Individual image failures don't stop processing
- Detailed error logging for troubleshooting
- Statistics tracking of success/failure rates

## Example Output

```csv
source_image,incident_name,division_group,designator,lwd,leader,num_persons,is_handwritten,confidence_score,requires_human_review,resource_status
IMG_4026.jpg,Canyon Fire,Division A,CRW-1,Helibase - Crew Transport,John Smith,3,false,95,false,CAUTION_MINIMAL
IMG_4026.jpg,Canyon Fire,Division A,ENG-2,Line Construction,Jane Doe,1,true,65,true,CRITICAL_UNDERSTAFFED
```

## Monitoring

The script provides real-time progress updates:
- Processing status for each image
- Rate limit warnings and recovery
- Final summary statistics
- Resource status breakdown

## Production Considerations

- **Free Tier Limits**: Designed for Google AI Studio free tier constraints
- **Batch Processing**: Processes one image at a time with delays
- **Recovery**: Can be interrupted and resumed (processed images are skipped)
- **Scalability**: Suitable for small to medium batch sizes (10-50 images)
