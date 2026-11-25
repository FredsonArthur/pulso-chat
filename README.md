# pulso-chat

Chat em tempo real com suporte a múltiplas salas, troca de mensagens instantâneas e monitoramento de presença (online/offline).

## Stack
- **Backend:** Python + FastAPI + WebSockets
- **Frontend:** HTML5, CSS3 e JavaScript puro

## Como executar localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
Acesse http://127.0.0.1:8000 no navegador.
```