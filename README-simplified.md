# Email & Document Processing Service - Simplified

A streamlined AI-powered email and document analysis service that extracts structured data from emails and their attachments, focusing on actionable insights and calendar events.

## 🚀 Features

- **Email Processing**: Analyze emails with or without attachments
- **AI-Powered Analysis**: Uses OpenAI GPT-4 for intelligent data extraction  
- **Action Item Extraction**: Identifies tasks and deadlines from email content
- **Calendar Integration**: Generates calendar events from email content
- **Real-time Processing**: Immediate results without batch processing delays
- **Structured Output**: JSON response with mail summaries, action items, and calendar details

## ⚡ Quick Start

### 1. Setup Environment
```bash
# Copy environment template
cp env-example.txt .env

# Add your OpenAI API key
echo "OPENAI_API_KEY=your_actual_api_key_here" > .env
```

### 2. Run Locally
```bash
# Install dependencies
pip install -r requirements-simplified.txt

# Run the service
python app.py
```

### 3. Test the Service
```bash
# Health check
curl http://localhost:8080/health

# Process email without attachments
curl -X POST -F "mail_id=test_001" http://localhost:8080/process

# Process email with attachment
curl -X POST -F "mail_id=test_002" -F "files=@document.pdf" http://localhost:8080/process
```

## 🐳 Docker Deployment

```bash
# Build image
docker build -f Dockerfile-simplified -t fps-simplified .

# Run container
docker run -p 8080:8080 -e OPENAI_API_KEY=your_key fps-simplified
```

## ☁️ Cloud Run Deployment

```bash
# Set your OpenAI API key
export OPENAI_API_KEY=your_key_here

# Deploy to Google Cloud Run
./deploy-simplified.sh
```

## 📝 API Usage

### Process Email with Attachments
```bash
POST /process
Content-Type: multipart/form-data

# Email without attachments
curl -X POST -F "mail_id=email_001" http://localhost:8080/process

# Email with single attachment
curl -X POST -F "mail_id=email_002" -F "files=@invoice.pdf" http://localhost:8080/process

# Email with multiple attachments  
curl -X POST -F "mail_id=email_003" -F "files=@doc1.pdf" -F "files=@receipt.jpg" http://localhost:8080/process
```

### Response Format
```json
{
  "status": "completed",
  "mail_id": "email_002",
  "total_attachments": 1,
  "result": {
    "mail_id": "email_002",
    "status": "success",
    "extracted_data": {
      "email_002": {
        "Summary": "Invoice from ACME Corp for consulting services requiring payment by Feb 15th.",
        "ActionItems": [
          "Pay invoice INV-2024-001 by February 15th, 2024",
          "Verify services rendered in January 2024"
        ],
        "Urgency": "Medium",
        "files": {
          "email_002-01": {
            "Type": "Invoice",
            "sender": "ACME Corp",
            "received_date": "2024-01-15",
            "Summary": "Consulting services invoice for January 2024",
            "Details": "Invoice #INV-2024-001 for $1,250 due February 15th",
            "tags": ["Invoice", "Payment", "Consulting", "February2024"],
            "Urgency": "Medium",
            "Amount": "1250.00 USD",
            "PaymentDetails": {
              "Deadline": "2024-02-15",
              "Reference": "INV-2024-001"
            }
          }
        }
      },
      "calendar_add_details": [
        {
          "date": "2024-02-15",
          "time": "09:00",
          "action": "Pay ACME Corp invoice",
          "source_mail_id": "email_002",
          "source_file_id": "email_002-01",
          "execution_details": {
            "amount": "1250.00 USD",
            "reference": "INV-2024-001"
          }
        }
      ]
    }
  }
}
```

## 🔧 Configuration

| Environment Variable | Required | Default | Description |
|---------------------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | Your OpenAI API key |
| `PORT` | No | 8080 | Port to run the service |
| `DEBUG` | No | false | Enable debug logging |

## 📊 Supported File Types

- **Text**: .txt, .pdf, .doc, .docx
- **Images**: .png, .jpg, .jpeg, .bmp, .gif, .tiff, .webp
- **Max Size**: 16MB per file

## 📬 API Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `mail_id` | No | Unique identifier for the email (default: mail_001) |
| `files` | No | One or more attachment files |

## 🎯 What's Simplified

Compared to the original service, this version removes:
- ❌ Pub/Sub message handling
- ❌ Google Cloud Storage dependencies  
- ❌ Firestore database
- ❌ Secret Manager
- ❌ Batch processing complexity
- ❌ Multiple web frameworks
- ❌ Complex deployment dependencies

While keeping all the core AI functionality with email focus:
- ✅ Email content analysis
- ✅ Action item extraction
- ✅ Calendar event generation
- ✅ Attachment processing
- ✅ Structured data extraction
- ✅ Multi-format file support
- ✅ Cloud deployment ready
- ✅ RESTful API 