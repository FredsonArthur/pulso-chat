# pulso-chat

Aplicação leve de chat em tempo real com **FastAPI**, **WebSockets**, **SQLite** e frontend em **HTML/CSS/JS puro** (sem frameworks externos ou etapas de build).

## Funcionalidades

- **Autenticação e Sessão:** cadastro e login de usuários com hash de senha (`PBKDF2-HMAC-SHA256`) e persistência de sessões em SQLite.
- **Lobby de Salas:** visualização das salas das quais o usuário participa, criação de novas salas e acesso rápido às conversas.
- **Mensagens em Tempo Real:** troca de mensagens instantâneas via WebSocket com histórico persistido no SQLite.
- **Conversas Diretas (1:1):** abertura de canais privados entre dois usuários cadastrados com isolamento de histórico.
- **Presença Online/Offline:** acompanhamento em tempo real de usuários conectados na aplicação e na conversa ativa.

## Estrutura do Projeto

```text
pulso-chat/
├── app/
│   ├── __init__.py
│   ├── main.py       # Rotas HTTP, endpoints WebSocket e inicialização da aplicação
│   ├── manager.py    # Gerenciamento de conexões WebSocket, salas e presença
│   ├── storage.py    # Persistência em SQLite (usuários, sessões, salas, membros e mensagens)
│   └── auth.py       # Hash e verificação de senhas
├── static/
│   └── index.html    # Interface web (login/cadastro, lobby, salas e conversas 1:1)
├── requirements.txt
├── .gitignore
├── LICENSE
└── README.md
```
Como Executar Localmente

Crie e ative o ambiente virtual:

    python3 -m venv .venv
    source .venv/bin/activate

Instale as dependências:

    pip install -r requirements.txt

Inicie o servidor:
    
    uvicorn app.main:app --reload