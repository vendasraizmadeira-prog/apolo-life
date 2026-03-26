# 🚀 Guia de Deploy — Apolo Life

Existem 3 opções para colocar o sistema online. Recomendo o **Railway** por ser o mais fácil.

---

## ✅ OPÇÃO 1 — Railway (RECOMENDADO)
**Gratuito até $5/mês de uso · Mais fácil · Online em 5 minutos**

### Passo a passo:

**1. Criar conta no GitHub (se não tiver)**
- Acesse: https://github.com
- Clique em "Sign up" e crie uma conta gratuita

**2. Criar repositório no GitHub**
- Clique em "New repository"
- Nome: `apolo-life`
- Deixe "Private" (recomendado) ✓
- Clique em "Create repository"

**3. Fazer upload dos arquivos**
- Na página do repositório, clique em "uploading an existing file"
- Arraste TODOS os arquivos da pasta `apolo-life` (menos a pasta `uploads/`)
- Clique em "Commit changes"

**4. Criar conta no Railway**
- Acesse: https://railway.app
- Clique em "Start a New Project"
- Faça login com sua conta do GitHub

**5. Deploy**
- Clique em "Deploy from GitHub repo"
- Selecione o repositório `apolo-life`
- Railway detecta automaticamente que é Python
- Aguarde o build (1-2 minutos)

**6. Configurar variáveis de ambiente**
- No painel do Railway, clique em "Variables"
- Adicione:
  - `JWT_SECRET` = (qualquer texto longo, ex: `ApoloCT@2024#SenhaSegura!`)
  - `PORT` = `3000`

**7. Abrir o site**
- Clique em "Settings" → "Generate Domain"
- Seu site estará em algo como: `apolo-life-production.up.railway.app`

---

## ✅ OPÇÃO 2 — Render
**Gratuito (dorme após 15min sem uso) · Fácil**

### Passo a passo:

1. Faça o upload dos arquivos no GitHub (igual ao passo 1-3 acima)
2. Acesse: https://render.com → "New Web Service"
3. Conecte ao GitHub e selecione o repositório
4. Configure:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python server.py`
5. Adicione variável: `JWT_SECRET` = (texto seguro)
6. Clique em "Create Web Service"

> ⚠️ No plano gratuito o Render "adormece" o site após 15 minutos sem acesso.
> O primeiro acesso depois pode demorar ~30 segundos para acordar.

---

## ✅ OPÇÃO 3 — VPS Próprio (Hostinger / DigitalOcean)
**~R$20/mês · Mais controle · Requer mais conhecimento técnico**

Se você já tem um servidor Linux (Ubuntu):

```bash
# 1. Instalar Python e dependências
sudo apt update && sudo apt install python3 python3-pip -y
pip3 install tornado bcrypt PyJWT pdfplumber

# 2. Copiar os arquivos para o servidor (via FTP ou SCP)
# 3. Rodar o servidor permanentemente
nohup python3 server.py &

# Ou instalar como serviço (para reiniciar automaticamente)
# Crie /etc/systemd/system/apolo-life.service
```

---

## 🔐 Após o Deploy — Configurações Importantes

1. **Mude a senha do admin** imediatamente após o primeiro login
   - Acesse o sistema → clique no ícone de cadeado → "Alterar Senha"

2. **Mude o JWT_SECRET** nas variáveis de ambiente para algo único e seguro

3. **Domínio personalizado** (ex: `apoloct.com.br`):
   - No Railway/Render, vá em Settings → Custom Domain
   - Aponte seu domínio para o endereço gerado

---

## 📱 Compartilhar com os alunos

Após o deploy, você terá uma URL como:
`https://apolo-life-production.up.railway.app`

- Envie essa URL para cada aluno junto com o email e senha criados no admin
- Os alunos acessam pelo celular ou computador, sem instalar nada
- Funciona em qualquer dispositivo com navegador

---

*Dúvidas? Entre em contato com a equipe Apolo CT.*
