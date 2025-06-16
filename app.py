#!/usr/bin/env python3
import os
import json
import base64
import logging
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from openai import OpenAI
from dotenv import load_dotenv
from google.cloud import storage
from google.cloud import firestore
from google.cloud import secretmanager
from functools import wraps

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def require_api_key(func):
    """Simple API key check using the X-API-Key header."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        api_key = request.headers.get("X-API-Key")
        expected_key = os.getenv("API_KEY")
        if expected_key and api_key != expected_key:
            return jsonify({"status": "error", "error": "Invalid API key"}), 401
        return func(*args, **kwargs)

    return wrapper


def query_firestore_with_subcollection(
    collection_name: str,
    subcollection_name: str,
    collection_filters: dict,
    subcollection_filters: dict,
):
    """Query Firestore collection and include filtered subcollection docs."""

    db = firestore.Client()

    query = db.collection(collection_name)
    for field, value in collection_filters.items():
        query = query.where(field, "==", value)

    collection_docs = query.stream()
    results = []

    for doc in collection_docs:
        doc_data = {"id": doc.id, **doc.to_dict()}

        sub_query = doc.reference.collection(subcollection_name)
        for field, value in subcollection_filters.items():
            sub_query = sub_query.where(field, "==", value)

        sub_docs = sub_query.stream()
        sub_data = [{"id": s.id, **s.to_dict()} for s in sub_docs]

        if not subcollection_filters or sub_data:
            doc_data[subcollection_name] = sub_data
            results.append(doc_data)

    return results

# Supported file extensions
ALLOWED_EXTENSIONS = {'.txt', '.pdf', '.doc', '.docx', '.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp'}
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp'}

# AI prompt template - Email and attachment processing
PROMPT_TEMPLATE = """### You are an expert assistant for extracting structured data from emails and attachments.

Given one or more emails (with or without attachments), your task is to analyze the content and return a JSON response strictly conforming to the following schema and requirements.

## Standard Response Format (Always Conform to This Template)

{
  "MAIL_ID_1": {
    "Summary": "One-paragraph summary of the email and its purpose.",
    "ActionItems": [
      "List actionable items for the user based on the email and its attachments."
    ],
    "Urgency": "Low | Medium | High",
    "files": {
      "FILE_ID_1": {
        "Type": "...",
        "sender": "...",
        "received_date": "...",
        "Summary": "...",
        "Details": "...",
        "tags": ["..."],
        "Urgency": "Low | Medium | High",
        // Include any other relevant fields found in the document, such as:
        // "ActionRequired": "...",
        // "Amount": "...",
        // "PaymentDetails": { ... },
        // Additional context-dependent fields as present in the source (e.g., "Authority", "Store", "Reference", etc.)
      }
      // More file_id entries as needed
    }
    // The 'files' key is optional and present only if the mail has one or more attachments.
  },
  // More mail_id entries as needed

  "calendar_add_details": [
    {
      "date": "YYYY-MM-DD",
      "time": "HH:mm",
      "action": "...",
      "source_mail_id": "...",
      "source_file_id": "...",  // or null if not applicable
      "execution_details": {
        // Relevant structured fields for this event/action, e.g.:
        // "amount": "...",
        // "reference": "...",
        // "location": "...",
        // "meeting_link": "...",
        // Dynamic fields as appropriate for the context
      }
    }
    // More entries as needed
  ]
}

## Field Explanations

### Per Email (MAIL_ID object):

- Summary: One-paragraph, human-readable summary of the email's contents and its purpose.
- ActionItems: List of actionable tasks or required follow-ups for the user.
- Urgency: "Low", "Medium", or "High"—the overall priority.
- files: (Optional; only if there are attachments)
  An object where each key is a unique file ID. Each file object includes:
  - Type (required): Nature/type of the document (e.g., Invoice, Bill, Tax Notice).
  - sender (required): Who sent or authored the attachment.
  - received_date (required): When the attachment was received or dated.
  - Summary (required): Short summary of the attachment.
  - Details (required): Detailed description of the attachment.
  - tags (required): Array of relevant tags.
  - Urgency (required): "Low", "Medium", or "High".
  - ActionRequired, Amount, PaymentDetails: (Include if available)—and any other relevant fields found in the attachment, using the same field names and data types.

### Per Calendar Entry (calendar_add_details array):

Each entry must include:
- date: Date of the event/action (format: YYYY-MM-DD).
- time: Time of the event/action (format: HH:mm or as in examples).
- action: Human-readable description of the event/action.
- source_mail_id: The mail ID this entry was derived from.
- source_file_id: The file ID this entry was derived from, or null if not from an attachment.
- execution_details: Object of relevant, structured fields (amount, reference, location, meeting link, etc.), as appropriate for the action.

## General Rules

- Always conform to the above JSON schema.
- All required fields must be present (if no data, use "NA", null, or empty arrays/objects as appropriate).
- Always include calendar_add_details as an array (even if empty).
- Omit the files object if the email has no attachments.
- Never output text or explanation outside the JSON.
- Extract any additional relevant fields present in the input and include them at the correct level, using the source field name and data type.
- Maintain field order, spelling, and types as in the schema and examples.

Your instructions:
- Always conform to the Standard Response Format and field rules.
- Never include any text outside the required JSON.
- Include any and all relevant fields found in the input, following the schema.
- Maintain field order, spelling, and structure.
"""

def is_allowed_file(filename):
    """Check if file extension is allowed"""
    return any(filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS)

def is_image_file(filename):
    """Check if file is an image"""
    return any(filename.lower().endswith(ext) for ext in IMAGE_EXTENSIONS)

def process_file_content(file):
    """Process uploaded file and return content"""
    try:
        filename = secure_filename(file.filename)
        
        if not is_allowed_file(filename):
            return None, f"File type not supported: {filename}"
        
        # Read file content
        file_content = file.read()
        
        if is_image_file(filename):
            # Encode images as base64
            content = base64.b64encode(file_content).decode('utf-8')
        else:
            # Try to decode text files
            try:
                content = file_content.decode('utf-8')
            except UnicodeDecodeError:
                return None, f"Could not decode file as UTF-8 text: {filename}"
        
        return {
            'filename': filename,
            'content': content,
            'is_image': is_image_file(filename)
        }, None
        
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        return None, str(e)

def analyze_documents_with_openai(mail_id, files_data):
    """Analyze email and documents using OpenAI API"""
    try:
        messages = [
            {"role": "system", "content": "You are a helpful assistant for email and document data extraction."},
            {"role": "user", "content": PROMPT_TEMPLATE}
        ]
        
        # Prepare content for analysis
        email_content = f"Mail ID: {mail_id}\n\n"
        
        if files_data:
            email_content += f"This email has {len(files_data)} attachment(s):\n\n"
            
            for i, file_data in enumerate(files_data, 1):
                filename = file_data['filename']
                content = file_data['content']
                is_image = file_data['is_image']
                
                email_content += f"Attachment {i}: {filename}\n"
                
                if is_image:
                    # For images, we'll include them as base64 in the message
                    messages.append({
                        "role": "user", 
                        "content": [
                            {"type": "text", "text": f"Attachment: {filename}"},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{content}"}}
                        ]
                    })
                else:
                    email_content += f"Content: {content}\n\n"
        else:
            email_content += "This email has no attachments.\n"
        
        # Add the email content to messages
        messages.append({
            "role": "user", 
            "content": email_content
        })
        
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",  # Using the more cost-effective model
            messages=messages,
            max_tokens=4000,
            temperature=0
        )
        
        extracted_data = json.loads(response.choices[0].message.content)
        
        return {
            'mail_id': mail_id,
            'extracted_data': extracted_data,
            'status': 'success'
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse OpenAI response as JSON for mail {mail_id}: {e}")
        return {
            'mail_id': mail_id,
            'extracted_data': {},
            'status': 'error',
            'error': f"JSON parsing error: {str(e)}"
        }
    except Exception as e:
        logger.error(f"OpenAI API error for mail {mail_id}: {e}")
        return {
            'mail_id': mail_id,
            'extracted_data': {},
            'status': 'error',
            'error': str(e)
        }

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'service': 'File Processing Service'}), 200


@app.route('/collections/<collection>/subcollections/<subcollection>', methods=['GET'])
@require_api_key
def query_collection_with_subcollection_route(collection, subcollection):
    """Query Firestore collection along with a subcollection."""

    try:
        collection_filters = {}
        subcollection_filters = {}
        for key, value in request.args.items():
            if key.startswith('collection_'):
                field = key[len('collection_'):]
                collection_filters[field] = value
            elif key.startswith('subcollection_'):
                field = key[len('subcollection_'):]
                subcollection_filters[field] = value

        results = query_firestore_with_subcollection(
            collection_name=collection,
            subcollection_name=subcollection,
            collection_filters=collection_filters,
            subcollection_filters=subcollection_filters,
        )

        return jsonify({'status': 'success', 'data': results}), 200

    except Exception as e:
        logger.error(f'Error querying Firestore: {e}')
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/process', methods=['POST'])
def process_files():
    """Main endpoint to process email with attachments"""
    try:
        # Get mail_id from form data or generate one
        mail_id = request.form.get('mail_id', 'mail_001')
        
        # Check if files were uploaded (optional for this new format)
        files_data = []
        if 'files' in request.files:
            files = request.files.getlist('files')
            
            for file in files:
                if file.filename == '':
                    continue
                    
                logger.info(f"Processing attachment: {file.filename}")
                
                # Process file content
                file_data, error = process_file_content(file)
                if error:
                    logger.error(f"Error processing {file.filename}: {error}")
                    continue
                
                files_data.append(file_data)
        
        # Analyze email and attachments with OpenAI
        logger.info(f"Analyzing mail {mail_id} with {len(files_data)} attachments")
        analysis_result = analyze_documents_with_openai(mail_id, files_data)
        
        return jsonify({
            'status': 'completed',
            'mail_id': mail_id,
            'total_attachments': len(files_data),
            'result': analysis_result
        }), 200
        
    except Exception as e:
        logger.error(f"Error in process_files: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/', methods=['GET'])
def index():
    """Simple index page with usage instructions"""
    return jsonify({
        'service': 'Email & Document Processing Service',
        'version': '2.0-simplified-email',
        'endpoints': {
            'GET /health': 'Health check',
            'POST /process': 'Process email with attachments (multipart/form-data with optional "files" field and optional "mail_id")',
            'GET /collections/<collection>/subcollections/<subcollection>': 'Query a Firestore collection and include its subcollection documents',
            'GET /': 'This help page'
        },
        'supported_formats': list(ALLOWED_EXTENSIONS),
        'max_file_size': '16MB',
        'usage': {
            'curl_example': 'curl -X POST -F "mail_id=001" -F "files=@invoice.pdf" http://localhost:8080/process',
            'form_fields': {
                'mail_id': 'Optional - unique identifier for the email (default: mail_001)',
                'files': 'Optional - one or more attachment files'
            }
        }
    }), 200

if __name__ == '__main__':
    # Validate required environment variables
    if not os.getenv('OPENAI_API_KEY'):
        logger.error("OPENAI_API_KEY environment variable is required")
        exit(1)
    
    port = int(os.getenv('PORT', 8080))
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    
    logger.info(f"Starting File Processing Service on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug) 