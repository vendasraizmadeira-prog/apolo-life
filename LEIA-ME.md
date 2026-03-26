# 🏋️ Apolo Life — Sistema de Avaliação Física
**by Apolo CT**

Sistema web completo para gerenciar avaliações físicas dos alunos, com upload automático de PDFs do AvanutriAvaBio-360.

---

## ✅ Requisitos

- **Python 3.8+** com os pacotes: `tornado`, `bcrypt`, `pyjwt`, `pdfplumber`
- Verificar com: `python3 --version`

---

## 🚀 Como Rodar Localmente

```bash
# 1. Entrar na pasta do projeto
cd apolo-life

# 2. Iniciar o servidor
python3 server.py

# 3. Abrir no navegador
# http://localhost:3000
```

**Login padrão do admin:**
- Email: `admin@apoloct.com`
- Senha: `admin123`

> ⚠️ Mude a senha do admin após o primeiro acesso!

---

## ☁️ Deploy em Produção (Railway / Render / VPS)

### Railway (recomendado - gratuito)
1. Crie conta em [railway.app](https://railway.app)
2. Novo projeto → "Deploy from GitHub"
3. Crie um arquivo `requirements.txt` na pasta com:
   ```
   tornado==6.1
   bcrypt==3.2.0
   PyJWT==2.3.0
   pdfplumber==0.11.9
   ```
4. Crie um `Procfile` com: `web: python3 server.py`
5. Defina variável de ambiente: `DB_PATH=/data/apolo-life.db`

### VPS (Ubuntu)
```bash
# Instalar dependências
pip3 install tornado bcrypt PyJWT pdfplumber

# Rodar em background
nohup python3 server.py &

# Ou usar systemd para auto-iniciar
```

---

## 📋 Funcionalidades

### Painel Admin (`/admin.html`)
- **Visão Geral** — estatísticas e avaliações recentes
- **Clientes** — criar, editar, excluir alunos; ver histórico de avaliações
- **Upload PDF** — enviar PDF do AvanutriAvaBio-360, extração automática de todos os dados

### Dashboard do Aluno (`/dashboard.html`)
- Visualização completa da composição corporal
- Análise segmentar (braços, tronco, pernas) — massa magra e gordura
- Gráficos de evolução (quando há múltiplas avaliações)
- Badges com TMB, índice apendicular e idade metabólica
- Trocar senha diretamente no painel

---

## 📊 Dados Extraídos Automaticamente do PDF

| Métrica | Descrição |
|---|---|
| Peso | kg |
| % Gordura | percentual de gordura corporal |
| Massa de Gordura | kg |
| Massa Livre de Gordura | kg |
| Água Corporal | litros |
| IMC | índice de massa corporal |
| Massa Muscular Esquelética | kg |
| Gordura Visceral | nível |
| TMB | taxa metabólica basal (kcal) |
| Índice Apendicular | kg/m² |
| Idade Metabólica | anos |
| Proteína / Minerais | kg |
| Água Intra/Extracelular | litros |
| Segmentar magra | braços, tronco, pernas |
| Segmentar gordura | braços, tronco, pernas |

---

## 🔐 Segurança

- Senhas criptografadas com bcrypt
- Autenticação via JWT (token válido por 7 dias)
- Cada aluno acessa apenas seus próprios dados
- Troque o `JWT_SECRET` no servidor para produção

---

## ⚙️ Variáveis de Ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `PORT` | 3000 | Porta do servidor |
| `JWT_SECRET` | `apolo-life-secret-2024` | Chave secreta JWT (mude em produção!) |
| `DB_PATH` | `apolo-life.db` | Caminho do banco de dados SQLite |

---

*Apolo Life © 2024 — Desenvolvido para Apolo CT*
