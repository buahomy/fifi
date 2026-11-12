#!/usr/bin/env python3
"""
Production-ready ICS-204 Form Processor
Extracts structured data from ICS-204 incident management forms using Gemini API
Outputs CSV for resource gap analysis with handwritten text detection
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
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ics204_processor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class ICS204Processor:
    """Production-ready ICS-204 form processor with robust error handling"""
    
    def __init__(self):
        """Initialize the processor with API client and configuration"""
        # Read API key from environment variable
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            logger.error("Error: GOOGLE_API_KEY environment variable not set")
            logger.error("Please set your Google API key: export GOOGLE_API_KEY='your-api-key-here'")
            sys.exit(1)
        
        # Initialize Gemini client
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-3.1-pro"
        
        # Define paths
        self.input_folder = Path("input_forms")
        self.output_folder = Path("output")
        
        # Ensure folders exist
        self.input_folder.mkdir(exist_ok=True)
        self.output_folder.mkdir(exist_ok=True)
        
        # Rate limiting configuration
        self.base_delay = 30  # Base delay between requests
        self.retry_delay = 60  # Delay for 429 errors
        self.max_retries = 3   # Maximum retry attempts
        
        # Data storage
        self.all_resources = []
        self.processing_stats = {
            'total_images': 0,
            'successful': 0,
            'failed': 0,
            'requires_review': 0,
            'handwritten_detected': 0
        }
    
    def get_image_files(self):
        """Find all image files in the input folder"""
        image_extensions = ['.jpg', '.jpeg', '.png']
        image_files = []
        
        for ext in image_extensions:
            image_files.extend(self.input_folder.glob(f"*{ext}"))
            image_files.extend(self.input_folder.glob(f"*{ext.upper()}"))
        
        logger.info(f"Found {len(image_files)} image files to process")
        return sorted(image_files)
    
    def extract_ics204_data_with_retry(self, image_path):
        """Extract data from image with robust retry logic for rate limiting"""
        for attempt in range(self.max_retries):
            try:
                return self.extract_ics204_data(image_path)
            
            except Exception as e:
                error_msg = str(e)
                
                # Check for rate limiting error (429)
                if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                    if attempt < self.max_retries - 1:
                        logger.warning(f"Rate limit hit for {image_path.name}. Attempt {attempt + 1}/{self.max_retries}")
                        logger.warning(f"Pausing for {self.retry_delay} seconds before retry...")
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        logger.error(f"Max retries exceeded for {image_path.name} due to rate limiting")
                        return {"error": "Rate limit exceeded after max retries", "details": error_msg}
                
                # Handle other errors
                else:
                    logger.error(f"Error processing {image_path.name}: {error_msg}")
                    return {"error": "Processing failed", "details": error_msg}
        
        return {"error": "Max retries exceeded"}
    
    def extract_ics204_data(self, image_path):
        """Extract structured ICS-204 data from image using Gemini API"""
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
            
            # Create content with image and specialized OCR prompt
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text="""You are an expert data extraction OCR system specializing in ICS-204 incident management forms. 

Your task is to extract all data from this ICS-204 form with special attention to:

1. **HANDWRITTEN NOTES**: Pay special attention to any handwritten text, especially:
   - Resource replacements or modifications written in red/blue ink
   - New LWD (Location, Work, Date) annotations
   - Personnel changes or additions
   - Any crossed-out text with replacements

2. **CONFIDENCE ASSESSMENT**: For each extracted resource, provide:
   - A confidence score (0-100) for your extraction accuracy
   - A boolean flag `requires_human_review` if:
     * Text is ambiguous or unclear
     * Handwriting is difficult to read
     * Text is crossed out or has corrections
     * Confidence score is below 80%

3. **ACCURACY FOCUS**: 
   - Extract exact designator codes (e.g., "CRW-1", "ENG-2")
   - Capture complete LWD information
   - Note any handwritten modifications to personnel counts
   - Preserve leader names exactly as written

Please structure your response as valid JSON following the provided schema. If you cannot find certain information, use null or empty strings as appropriate."""),
                        types.Part.from_bytes(data=img_buffer.getvalue(), mime_type="image/jpeg"),
                    ],
                ),
            ]
            
            # Define structured output schema
            generate_content_config = types.GenerateContentConfig(
                top_p=0.1,
                thinking_config=types.ThinkingConfig(
                    thinking_level="HIGH",
                ),
                response_mime_type="application/json",
                response_schema=genai.types.Schema(
                    type=genai.types.Type.OBJECT,
                    required=["incident_name", "division_group", "resources"],
                    properties={
                        "incident_name": genai.types.Schema(
                            type=genai.types.Type.STRING,
                        ),
                        "division_group": genai.types.Schema(
                            type=genai.types.Type.STRING,
                        ),
                        "resources": genai.types.Schema(
                            type=genai.types.Type.ARRAY,
                            items=genai.types.Schema(
                                type=genai.types.Type.OBJECT,
                                properties={
                                    "designator": genai.types.Schema(
                                        type=genai.types.Type.STRING,
                                    ),
                                    "lwd": genai.types.Schema(
                                        type=genai.types.Type.STRING,
                                    ),
                                    "leader": genai.types.Schema(
                                        type=genai.types.Type.STRING,
                                    ),
                                    "num_persons": genai.types.Schema(
                                        type=genai.types.Type.INTEGER,
                                    ),
                                    "is_handwritten": genai.types.Schema(
                                        type=genai.types.Type.BOOLEAN,
                                    ),
                                    "confidence_score": genai.types.Schema(
                                        type=genai.types.Type.INTEGER,
                                    ),
                                    "requires_human_review": genai.types.Schema(
                                        type=genai.types.Type.BOOLEAN,
                                    ),
                                },
                            ),
                        ),
                    },
                ),
            )
            
            # Generate content
            logger.info(f"Processing {image_path.name} with {self.model}")
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=generate_content_config,
            )
            
            # Parse JSON response
            try:
                extracted_data = json.loads(response.text)
                logger.info(f"Successfully extracted data from {image_path.name}")
                return extracted_data
            except json.JSONDecodeError:
                logger.warning(f"Could not parse JSON response for {image_path.name}")
                return {"error": "JSON parsing failed", "raw_response": response.text}
            
        except Exception as e:
            logger.error(f"Error in extract_ics204_data for {image_path.name}: {str(e)}")
            raise
    
    def process_extracted_data(self, extracted_data, image_filename):
        """Process extracted data and add to resource list"""
        if "error" in extracted_data:
            logger.error(f"Skipping {image_filename} due to extraction error")
            return
        
        # Extract basic information
        incident_name = extracted_data.get("incident_name", "Unknown")
        division_group = extracted_data.get("division_group", "Unknown")
        resources = extracted_data.get("resources", [])
        
        # Process each resource
        for resource in resources:
            # Create flattened record
            record = {
                "source_image": image_filename,
                "incident_name": incident_name,
                "division_group": division_group,
                "designator": resource.get("designator", ""),
                "lwd": resource.get("lwd", ""),
                "leader": resource.get("leader", ""),
                "num_persons": resource.get("num_persons", 0),
                "is_handwritten": resource.get("is_handwritten", False),
                "confidence_score": resource.get("confidence_score", 0),
                "requires_human_review": resource.get("requires_human_review", False),
                "processing_timestamp": datetime.now().isoformat()
            }
            
            # Add resource gap analysis
            num_persons = record["num_persons"]
            if num_persons == 0:
                record["resource_status"] = "CRITICAL_NO_PERSONNEL"
            elif num_persons < 2:
                record["resource_status"] = "CRITICAL_UNDERSTAFFED"
            elif num_persons < 4:
                record["resource_status"] = "CAUTION_MINIMAL"
            else:
                record["resource_status"] = "ADEQUATE"
            
            # Add to master list
            self.all_resources.append(record)
            
            # Update statistics
            if record["is_handwritten"]:
                self.processing_stats["handwritten_detected"] += 1
            if record["requires_human_review"]:
                self.processing_stats["requires_review"] += 1
        
        logger.info(f"Processed {len(resources)} resources from {image_filename}")
    
    def export_to_csv(self):
        """Export all processed data to CSV file"""
        if not self.all_resources:
            logger.warning("No data to export")
            return
        
        # Create DataFrame
        df = pd.DataFrame(self.all_resources)
        
        # Define output file path
        csv_path = self.output_folder / "Resource_Analysis.csv"
        
        # Export to CSV
        df.to_csv(csv_path, index=False)
        logger.info(f"Exported {len(df)} records to {csv_path}")
        
        # Also export a summary statistics file
        summary_path = self.output_folder / "Processing_Summary.csv"
        summary_df = pd.DataFrame([self.processing_stats])
        summary_df.to_csv(summary_path, index=False)
        logger.info(f"Exported processing summary to {summary_path}")
        
        return csv_path
    
    def run_processing(self):
        """Main processing loop"""
        logger.info("Starting ICS-204 form processing")
        logger.info(f"Input folder: {self.input_folder}")
        logger.info(f"Output folder: {self.output_folder}")
        
        # Get all image files
        image_files = self.get_image_files()
        self.processing_stats["total_images"] = len(image_files)
        
        if not image_files:
            logger.error(f"No image files found in {self.input_folder}")
            return
        
        # Process each image
        for i, image_path in enumerate(image_files, 1):
            logger.info(f"\n=== Processing {i}/{len(image_files)}: {image_path.name} ===")
            
            try:
                # Extract data with retry logic
                extracted_data = self.extract_ics204_data_with_retry(image_path)
                
                # Process the extracted data
                self.process_extracted_data(extracted_data, image_path.name)
                
                # Update success counter
                if "error" not in extracted_data:
                    self.processing_stats["successful"] += 1
                else:
                    self.processing_stats["failed"] += 1
                
                # Rate limiting: pause between requests
                if i < len(image_files):  # Don't sleep after the last image
                    logger.info(f"Pausing for {self.base_delay} seconds before next image...")
                    time.sleep(self.base_delay)
            
            except KeyboardInterrupt:
                logger.info("Processing interrupted by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error processing {image_path.name}: {str(e)}")
                self.processing_stats["failed"] += 1
                continue
        
        # Export results
        csv_path = self.export_to_csv()
        
        # Print final summary
        self.print_summary()
        
        return csv_path
    
    def print_summary(self):
        """Print processing summary"""
        logger.info("\n" + "="*60)
        logger.info("PROCESSING SUMMARY")
        logger.info("="*60)
        logger.info(f"Total images processed: {self.processing_stats['total_images']}")
        logger.info(f"Successful extractions: {self.processing_stats['successful']}")
        logger.info(f"Failed extractions: {self.processing_stats['failed']}")
        logger.info(f"Total resources extracted: {len(self.all_resources)}")
        logger.info(f"Handwritten text detected: {self.processing_stats['handwritten_detected']}")
        logger.info(f"Requires human review: {self.processing_stats['requires_review']}")
        
        # Resource status breakdown
        if self.all_resources:
            status_counts = {}
            for record in self.all_resources:
                status = record.get("resource_status", "UNKNOWN")
                status_counts[status] = status_counts.get(status, 0) + 1
            
            logger.info("\nResource Status Breakdown:")
            for status, count in status_counts.items():
                logger.info(f"  {status}: {count}")
        
        logger.info("="*60)


def main():
    """Main entry point"""
    logger.info("ICS-204 Form Processor - Production Version")
    logger.info(f"Started at: {datetime.now().isoformat()}")
    
    try:
        # Create processor instance
        processor = ICS204Processor()
        
        # Run processing
        csv_file = processor.run_processing()
        
        if csv_file:
            logger.info(f"\n✅ Processing complete! Resource analysis saved to: {csv_file}")
        else:
            logger.error("\n❌ Processing failed. Check logs for details.")
    
    except KeyboardInterrupt:
        logger.info("\n⚠️ Processing interrupted by user")
    except Exception as e:
        logger.error(f"\n💥 Fatal error: {str(e)}")
        sys.exit(1)
    
    logger.info(f"Finished at: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
