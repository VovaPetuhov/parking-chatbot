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
