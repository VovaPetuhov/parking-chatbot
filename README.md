# Step #1 - create virtual env
```bash
pyenv install 3.12.9
pyenv local 3.12.9
python3 -m venv .venv
source .venv/bin/activate
```

# Step #2 - install requirements
```bash
pip install -r requirements.txt
```

# Step #2.5 - install MCP dependencies (for file persistence)
```bash
npm install
```

# Step #3 - setup env variables
```bash
cp .env.example .env
```

# Step #4 - init Vector DB
Populating the database 
Currently only *.txt files are supported
You need to add files to the /data folder and run this command
You can also set up environment variables and use DeepLake's cloud vector database,
otherwise local storage will be used.
Use --force to override DB data
```bash
python init_db.py [--force]
```

# Step #5 - run (cli mode)
Use --quiet to disable log output
```bash
python main.py [--quiet]

```

## Evaluation
```bash
python evaluation/rag_eval.py
python -m evaluation.rag_eval
```

## Run tests

```bash
pytest tests/ -v
```

# REST API

```bash
python main_api.py
```

## Swagger UI
```
http://localhost:8000/docs
```

## API Endpoints

### Health Check
```bash
GET /api/health
```

### Chat with Bot
```bash
POST /api/chat
Content-Type: application/json

{
  "message": "What are the working hours?",
  "conversation_id": "optional-session-id"
}
```

### Session Management
- `POST /api/conversations` - Create new conversation
- `GET /api/conversations` - List all conversations
- `GET /api/conversations/{id}` - Get conversation details
- `GET /api/conversations/{id}/history` - Get conversation history
- `DELETE /api/conversations/{id}` - Delete conversation
- `POST /api/conversations/{id}/reset` - Reset conversation

### Human-in-the-Loop (Admin)
- `GET /api/admin/reservations/pending` - List pending reservations
- `GET /api/admin/reservations` - List all reservations
- `GET /api/admin/reservations/{id}` - Get reservation details
- `POST /api/admin/reservations/{id}/approve` - Approve reservation
- `POST /api/admin/reservations/{id}/reject` - Reject reservation
- `GET /api/admin/stats` - Get reservation statistics

### Reservation Status (User)
- `GET /api/reservations/{id}/status` - Check reservation status
- `GET /api/reservations/conversation/{id}` - Get reservation by conversation

# MCP Integration

This project uses MCP to persist confirmed reservations to file storage.

### Quick Start

1. **Configure** in `.env`:
   ```bash
   MCP_ENABLED=true
   MCP_STORAGE_PATH=./storage
   MCP_STORAGE_FILE=confirmed_reservations.txt
   ```
2. **Start API** - MCP integration works automatically
3. **Approve reservation** - it will be written to `./storage/confirmed_reservations.txt`


### File Format
```
Name | Car Number | Period | Approval Time
John Doe | ABC-123 | 2024-01-20 10:00 to 2024-01-25 18:00 | 2024-01-18 15:30:45
```

### Disable MCP

If you don't need file persistence:
```bash
MCP_ENABLED=false
```

# Email Notifications (Optional)

The system can automatically send email notifications to administrators when new parking reservations are created.

## Quick Setup (Gmail)

### 1. Enable 2-Factor Authentication
- Go to: https://myaccount.google.com/security
- Enable "2-Step Verification"

### 2. Create App Password
- Go to: https://myaccount.google.com/apppasswords
- Select "Mail" and "Other (Custom name)"
- Name it: "Parking Chatbot"
- Copy the 16-character password (remove spaces!)

### 3. Configure `.env`
```bash
# Enable email notifications
EMAIL_NOTIFICATIONS_ENABLED=true

# Admin email (where notifications will be sent)
ADMIN_EMAIL=your-email@gmail.com

# SMTP settings for Gmail
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-16-char-app-password-no-spaces
SMTP_USE_TLS=true

# Email sender info
EMAIL_FROM=your-email@gmail.com
EMAIL_FROM_NAME=Parking Bot
```

The system works normally without emails - admins can still check pending reservations via API.
