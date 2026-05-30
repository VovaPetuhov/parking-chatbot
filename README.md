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

## Health Check
```bash
GET /api/health
```

## Send Message
```bash
POST /api/chat
Content-Type: application/json

{
  "message": "What are the working hours?",
  "conversation_id": "optional-session-id"
}
```
