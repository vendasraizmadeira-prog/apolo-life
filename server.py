#!/usr/bin/env python3
"""
Apolo Life - Sistema de Avaliação Física
Backend: Python + Tornado + SQLite + JWT + pdfplumber
"""

import os, json, re, sqlite3, hashlib, base64, asyncio
from datetime import datetime, timedelta
import tornado.web, tornado.ioloop, tornado.escape
import bcrypt, jwt, pdfplumber
import io

PORT = int(os.environ.get('PORT', 3000))
JWT_SECRET = os.environ.get('JWT_SECRET', 'apolo-life-secret-2024')
# Use /tmp for DB when running locally (avoids filesystem restrictions); override with env var for production
_default_db = os.environ.get('DB_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'apolo-life.db'))
# Fallback to /tmp if the default path is not writable
try:
    open(_default_db, 'a').close()
    DB_PATH = _default_db
except OSError:
    DB_PATH = '/tmp/apolo-life.db'
    print(f'⚠️  Using temporary DB at {DB_PATH} (set DB_PATH env var for persistence)')

# ── Database ──────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'client',
            phone TEXT,
            birth_date TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            last_login TEXT
        );

        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            assessment_date TEXT,
            weight REAL, body_fat_pct REAL, fat_mass REAL, lean_mass REAL,
            body_water REAL, bmi REAL, skeletal_muscle REAL, visceral_fat INTEGER,
            bmr INTEGER, metabolic_age INTEGER, appendicular_index REAL,
            protein REAL, minerals REAL, intra_water REAL, extra_water REAL,
            lean_arm_right REAL, lean_arm_left REAL, lean_trunk REAL,
            lean_leg_right REAL, lean_leg_left REAL,
            fat_arm_right REAL, fat_arm_left REAL, fat_trunk REAL,
            fat_leg_right REAL, fat_leg_left REAL,
            height REAL, sex TEXT, age INTEGER, raw_data TEXT, notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (client_id) REFERENCES users(id)
        );
    """)
    conn.commit()

    # Default admin
    existing = c.execute("SELECT id FROM users WHERE role='admin' LIMIT 1").fetchone()
    if not existing:
        pw = bcrypt.hashpw(b'admin123', bcrypt.gensalt()).decode()
        c.execute("INSERT INTO users (name, email, password_hash, role) VALUES (?,?,?,?)",
                  ('Administrador', 'admin@apoloct.com', pw, 'admin'))
        conn.commit()
        print('✅ Admin padrão criado: admin@apoloct.com / admin123')
    conn.close()

# ── JWT ───────────────────────────────────────────────────────────────────────
def make_token(user_id, role, name):
    payload = {
        'id': user_id, 'role': role, 'name': name,
        'exp': datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def verify_token(token):
    return jwt.decode(token, JWT_SECRET, algorithms=['HS256'])

# ── PDF Parser (AvanutriAvaBio-360) ───────────────────────────────────────────
# Based on actual pdfplumber text extraction format:
# Numbers come BEFORE the label in most cases (chart range values then actual value after label)
# e.g.: "41,6 52,3...\nPeso (kg)\n93,8\n"
def parse_avanutri_pdf(pdf_bytes):
    data = {}
    def to_num(s):
        if not s: return None
        try: return float(str(s).strip().replace(',', '.'))
        except: return None

    text = ''
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text += (page.extract_text() or '') + '\n'

    # ── Header ────────────────────────────────────────────────────────────
    m = re.search(r'Nome:\s*(.+?)\s+Estatura:\s*([\d,]+)m\s+Data:\s*([\d\/]+)', text)
    if m:
        data['name'] = m.group(1).strip()
        data['height'] = to_num(m.group(2))
        data['assessment_date'] = m.group(3)

    m = re.search(r'Sexo:\s*(Masculino|Feminino)', text)
    if m: data['sex'] = m.group(1)

    m = re.search(r'Idade:\s*(\d+)', text)
    if m: data['age'] = int(m.group(1))

    # ── Main Metrics (Análise Global Resumida) ────────────────────────────
    # Format: "...range numbers...\nPeso (kg)\n93,8\n"
    m = re.search(r'Peso \(kg\)\n([\d,]+)', text)
    if m: data['weight'] = to_num(m.group(1))

    # "Gordura 23,4" (on same line as "Gordura")
    m = re.search(r'^Gordura ([\d,]+)$', text, re.MULTILINE)
    if m: data['body_fat_pct'] = to_num(m.group(1))

    # "Massa de Gordura ...\n(kg) 22,0"
    m = re.search(r'^\(kg\) ([\d,]+)$', text, re.MULTILINE)
    if m: data['fat_mass'] = to_num(m.group(1))

    # "Massa Livre de ...\nGordura (kg) 66,3"
    m = re.search(r'^Gordura \(kg\) ([\d,]+)$', text, re.MULTILINE)
    if m: data['lean_mass'] = to_num(m.group(1))

    # "...\nÁgua Corporal (L)\n48,5"
    m = re.search(r'[AÁ]gua Corporal \(L\)\n([\d,]+)', text)
    if m: data['body_water'] = to_num(m.group(1))

    # "...\nIMC\n27,7"
    m = re.search(r'\nIMC\n([\d,]+)', text)
    if m: data['bmi'] = to_num(m.group(1))

    # ── Additional Data ───────────────────────────────────────────────────
    # BMR: "2.072 kcal\nBasal" (number is on prev line before "Basal")
    m = re.search(r'([\d.]+) kcal\nBasal', text)
    if m:
        try: data['bmr'] = int(m.group(1).replace('.', ''))
        except: pass

    # Appendicular index: "9,69 kg/m²\nÍndice"
    m = re.search(r'([\d,]+) kg/m[²2]', text)
    if m: data['appendicular_index'] = to_num(m.group(1))

    # Metabolic age: "29 anos\nMetabólica"
    m = re.search(r'(\d+) anos\nMetab', text)
    if m: data['metabolic_age'] = int(m.group(1))

    # Visceral fat: "Nível 9" in "Taxa Metabólica Nível 9 BD..."
    m = re.search(r'N[ií]vel (\d+)', text)
    if m: data['visceral_fat'] = int(m.group(1))

    # ── Segmental Analysis ────────────────────────────────────────────────
    # Text format (lean+fat side by side):
    # "Braço Braço Braço Braço\n4,4kg 4,5kg 0,8kg 0,7kg\n"
    # "66,3kg\n70,7%\nTronco Tronco\n33,5kg 16,3kg\n"
    # "Perna Perna Perna Perna\n12,1kg 11,9kg 2,0kg 2,2kg"

    m = re.search(r'Bra[çc]o Bra[çc]o Bra[çc]o Bra[çc]o\n([\d,]+)kg ([\d,]+)kg ([\d,]+)kg ([\d,]+)kg', text)
    if m:
        data['lean_arm_right'] = to_num(m.group(1))
        data['lean_arm_left']  = to_num(m.group(2))
        data['fat_arm_right']  = to_num(m.group(3))
        data['fat_arm_left']   = to_num(m.group(4))

    # Trunk: "Tronco Tronco\n33,5kg 16,3kg"
    m = re.search(r'Tronco Tronco\n([\d,]+)kg ([\d,]+)kg', text)
    if m:
        data['lean_trunk'] = to_num(m.group(1))
        data['fat_trunk']  = to_num(m.group(2))

    # Legs: "Perna Perna Perna Perna\n12,1kg 11,9kg 2,0kg 2,2kg"
    m = re.search(r'Perna Perna Perna Perna\n([\d,]+)kg ([\d,]+)kg ([\d,]+)kg ([\d,]+)kg', text)
    if m:
        data['lean_leg_right'] = to_num(m.group(1))
        data['lean_leg_left']  = to_num(m.group(2))
        data['fat_leg_right']  = to_num(m.group(3))
        data['fat_leg_left']   = to_num(m.group(4))

    # ── History section (latest = last value on each line) ────────────────
    # Format: "prev_val curr_val\nLabel\n"  OR  "curr_val\nLabel\n" (single assessment)
    def get_hist(pattern):
        m = re.search(pattern, text, re.IGNORECASE)
        if not m: return None
        vals = m.group(1).strip().split()
        return to_num(vals[-1])  # take the last (most recent) value

    sk = get_hist(r'([\d,]+ [\d,]+)\nMassa Muscular\nEsquel')
    if sk: data['skeletal_muscle'] = sk

    intra = get_hist(r'([\d,]+ [\d,]+)\n[AÁ]gua Intracelular')
    if intra: data['intra_water'] = intra

    extra = get_hist(r'([\d,]+ [\d,]+)\n[AÁ]gua\nExtracelular')
    if extra: data['extra_water'] = extra

    prot = get_hist(r'([\d,]+ [\d,]+)\nProte[íi]na \(kg\)')
    if prot: data['protein'] = prot

    mins = get_hist(r'([\d,]+ [\d,]+)\nMinerais \(kg\)')
    if mins: data['minerals'] = mins

    return data

# ── Base Handler ──────────────────────────────────────────────────────────────
class BaseHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header('Content-Type', 'application/json')
        self.set_header('Access-Control-Allow-Origin', '*')
        self.set_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
        self.set_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')

    def options(self, *args):
        self.set_status(204)
        self.finish()

    def get_current_user(self):
        auth = self.request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '): return None
        try:
            return verify_token(auth[7:])
        except:
            return None

    def require_auth(self):
        user = self.get_current_user()
        if not user:
            self.set_status(401)
            self.write({'error': 'Token inválido ou não fornecido'})
            return None
        return user

    def require_admin(self):
        user = self.require_auth()
        if user and user.get('role') != 'admin':
            self.set_status(403)
            self.write({'error': 'Acesso restrito ao administrador'})
            return None
        return user

    def json_body(self):
        try: return json.loads(self.request.body)
        except: return {}

    def row_to_dict(self, row):
        if row is None: return None
        return dict(row)

    def rows_to_list(self, rows):
        return [dict(r) for r in rows]

# ── Auth ──────────────────────────────────────────────────────────────────────
class LoginHandler(BaseHandler):
    def post(self):
        body = self.json_body()
        email = body.get('email', '').strip().lower()
        password = body.get('password', '').encode()
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        conn.close()
        if not user or not bcrypt.checkpw(password, user['password_hash'].encode()):
            self.set_status(401)
            self.write({'error': 'Email ou senha inválidos'})
            return
        conn = get_db()
        conn.execute("UPDATE users SET last_login=datetime('now') WHERE id=?", (user['id'],))
        conn.commit()
        conn.close()
        token = make_token(user['id'], user['role'], user['name'])
        self.write({'token': token, 'user': {'id': user['id'], 'name': user['name'], 'email': user['email'], 'role': user['role']}})

class MeHandler(BaseHandler):
    def get(self):
        user = self.require_auth()
        if not user: return
        conn = get_db()
        u = conn.execute('SELECT id, name, email, role, phone, birth_date, created_at, last_login FROM users WHERE id=?', (user['id'],)).fetchone()
        conn.close()
        self.write(self.row_to_dict(u))

    def put(self):
        user = self.require_auth()
        if not user: return
        body = self.json_body()
        current = body.get('current', '').encode()
        new_pwd = body.get('newPassword', '').encode()
        conn = get_db()
        u = conn.execute('SELECT password_hash FROM users WHERE id=?', (user['id'],)).fetchone()
        if not bcrypt.checkpw(current, u['password_hash'].encode()):
            self.set_status(400); self.write({'error': 'Senha atual incorreta'}); conn.close(); return
        new_hash = bcrypt.hashpw(new_pwd, bcrypt.gensalt()).decode()
        conn.execute('UPDATE users SET password_hash=? WHERE id=?', (new_hash, user['id']))
        conn.commit(); conn.close()
        self.write({'success': True})

# ── Clients ───────────────────────────────────────────────────────────────────
class ClientsHandler(BaseHandler):
    def get(self):
        user = self.require_admin()
        if not user: return
        conn = get_db()
        rows = conn.execute("""
            SELECT u.id, u.name, u.email, u.phone, u.created_at, u.last_login,
            COUNT(a.id) as assessment_count, MAX(a.assessment_date) as last_assessment
            FROM users u LEFT JOIN assessments a ON a.client_id=u.id
            WHERE u.role='client' GROUP BY u.id ORDER BY u.name
        """).fetchall()
        conn.close()
        self.write(json.dumps(self.rows_to_list(rows)))

    def post(self):
        user = self.require_admin()
        if not user: return
        body = self.json_body()
        name = body.get('name', '').strip()
        email = body.get('email', '').strip().lower()
        password = body.get('password', '')
        if not name or not email or not password:
            self.set_status(400); self.write({'error': 'Nome, email e senha são obrigatórios'}); return
        conn = get_db()
        if conn.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone():
            self.set_status(400); self.write({'error': 'Email já cadastrado'}); conn.close(); return
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        cur = conn.execute('INSERT INTO users (name, email, password_hash, role, phone, birth_date) VALUES (?,?,?,?,?,?)',
                           (name, email, pw_hash, 'client', body.get('phone'), body.get('birth_date')))
        conn.commit(); conn.close()
        self.write({'id': cur.lastrowid, 'name': name, 'email': email})

class ClientHandler(BaseHandler):
    def get(self, client_id):
        user = self.require_auth()
        if not user: return
        cid = int(client_id)
        if user['role'] != 'admin' and user['id'] != cid:
            self.set_status(403); self.write({'error': 'Acesso negado'}); return
        conn = get_db()
        c = conn.execute('SELECT id, name, email, phone, birth_date, created_at FROM users WHERE id=?', (cid,)).fetchone()
        conn.close()
        if not c: self.set_status(404); self.write({'error': 'Cliente não encontrado'}); return
        self.write(self.row_to_dict(c))

    def put(self, client_id):
        user = self.require_admin()
        if not user: return
        body = self.json_body()
        cid = int(client_id)
        conn = get_db()
        if body.get('password'):
            pw_hash = bcrypt.hashpw(body['password'].encode(), bcrypt.gensalt()).decode()
            conn.execute('UPDATE users SET name=?,email=?,phone=?,birth_date=?,password_hash=? WHERE id=?',
                         (body['name'], body['email'], body.get('phone'), body.get('birth_date'), pw_hash, cid))
        else:
            conn.execute('UPDATE users SET name=?,email=?,phone=?,birth_date=? WHERE id=?',
                         (body['name'], body['email'], body.get('phone'), body.get('birth_date'), cid))
        conn.commit(); conn.close()
        self.write({'success': True})

    def delete(self, client_id):
        user = self.require_admin()
        if not user: return
        cid = int(client_id)
        conn = get_db()
        conn.execute('DELETE FROM assessments WHERE client_id=?', (cid,))
        conn.execute('DELETE FROM users WHERE id=?', (cid,))
        conn.commit(); conn.close()
        self.write({'success': True})

# ── Assessments ───────────────────────────────────────────────────────────────
class AssessmentsHandler(BaseHandler):
    def get(self, client_id):
        user = self.require_auth()
        if not user: return
        cid = int(client_id)
        if user['role'] != 'admin' and user['id'] != cid:
            self.set_status(403); self.write({'error': 'Acesso negado'}); return
        conn = get_db()
        rows = conn.execute('SELECT * FROM assessments WHERE client_id=? ORDER BY assessment_date DESC', (cid,)).fetchall()
        conn.close()
        self.write(json.dumps(self.rows_to_list(rows)))

    def post(self, client_id):
        user = self.require_admin()
        if not user: return
        cid = int(client_id)
        body = self.json_body()
        conn = get_db()
        cur = conn.execute("""
            INSERT INTO assessments (client_id, assessment_date, weight, body_fat_pct, fat_mass, lean_mass,
            body_water, bmi, skeletal_muscle, visceral_fat, bmr, metabolic_age, appendicular_index,
            protein, minerals, intra_water, extra_water, lean_arm_right, lean_arm_left, lean_trunk,
            lean_leg_right, lean_leg_left, fat_arm_right, fat_arm_left, fat_trunk, fat_leg_right, fat_leg_left,
            height, sex, age, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (cid, body.get('assessment_date'), body.get('weight'), body.get('body_fat_pct'),
              body.get('fat_mass'), body.get('lean_mass'), body.get('body_water'), body.get('bmi'),
              body.get('skeletal_muscle'), body.get('visceral_fat'), body.get('bmr'), body.get('metabolic_age'),
              body.get('appendicular_index'), body.get('protein'), body.get('minerals'),
              body.get('intra_water'), body.get('extra_water'), body.get('lean_arm_right'),
              body.get('lean_arm_left'), body.get('lean_trunk'), body.get('lean_leg_right'),
              body.get('lean_leg_left'), body.get('fat_arm_right'), body.get('fat_arm_left'),
              body.get('fat_trunk'), body.get('fat_leg_right'), body.get('fat_leg_left'),
              body.get('height'), body.get('sex'), body.get('age'), body.get('notes')))
        conn.commit(); conn.close()
        self.write({'id': cur.lastrowid})

class AssessmentPDFHandler(BaseHandler):
    def post(self, client_id):
        user = self.require_admin()
        if not user: return
        cid = int(client_id)

        files = self.request.files.get('pdf', [])
        if not files:
            self.set_status(400); self.write({'error': 'Nenhum arquivo enviado'}); return

        pdf_bytes = files[0]['body']
        notes = self.get_argument('notes', '')

        try:
            parsed = parse_avanutri_pdf(pdf_bytes)
        except Exception as e:
            self.set_status(500); self.write({'error': f'Erro ao processar PDF: {str(e)}'}); return

        conn = get_db()
        try:
            cur = conn.execute("""
                INSERT INTO assessments (client_id, assessment_date, weight, body_fat_pct, fat_mass, lean_mass,
                body_water, bmi, skeletal_muscle, visceral_fat, bmr, metabolic_age, appendicular_index,
                protein, minerals, intra_water, extra_water, lean_arm_right, lean_arm_left, lean_trunk,
                lean_leg_right, lean_leg_left, fat_arm_right, fat_arm_left, fat_trunk, fat_leg_right, fat_leg_left,
                height, sex, age, raw_data, notes)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (cid, parsed.get('assessment_date'), parsed.get('weight'), parsed.get('body_fat_pct'),
                  parsed.get('fat_mass'), parsed.get('lean_mass'), parsed.get('body_water'), parsed.get('bmi'),
                  parsed.get('skeletal_muscle'), parsed.get('visceral_fat'), parsed.get('bmr'),
                  parsed.get('metabolic_age'), parsed.get('appendicular_index'), parsed.get('protein'),
                  parsed.get('minerals'), parsed.get('intra_water'), parsed.get('extra_water'),
                  parsed.get('lean_arm_right'), parsed.get('lean_arm_left'), parsed.get('lean_trunk'),
                  parsed.get('lean_leg_right'), parsed.get('lean_leg_left'), parsed.get('fat_arm_right'),
                  parsed.get('fat_arm_left'), parsed.get('fat_trunk'), parsed.get('fat_leg_right'),
                  parsed.get('fat_leg_left'), parsed.get('height'), parsed.get('sex'), parsed.get('age'),
                  json.dumps(parsed), notes or None))
            conn.commit()
            self.write({'id': cur.lastrowid, 'parsed': parsed})
        except Exception as e:
            self.set_status(500); self.write({'error': str(e)})
        finally:
            conn.close()

class AssessmentDeleteHandler(BaseHandler):
    def delete(self, assess_id):
        user = self.require_admin()
        if not user: return
        conn = get_db()
        conn.execute('DELETE FROM assessments WHERE id=?', (int(assess_id),))
        conn.commit(); conn.close()
        self.write({'success': True})

# ── Stats ─────────────────────────────────────────────────────────────────────
class StatsHandler(BaseHandler):
    def get(self):
        user = self.require_admin()
        if not user: return
        conn = get_db()
        total_clients = conn.execute("SELECT COUNT(*) FROM users WHERE role='client'").fetchone()[0]
        total_assessments = conn.execute("SELECT COUNT(*) FROM assessments").fetchone()[0]
        recent = conn.execute("""
            SELECT a.id, u.name, a.assessment_date, a.weight, a.body_fat_pct
            FROM assessments a JOIN users u ON u.id=a.client_id
            ORDER BY a.created_at DESC LIMIT 5
        """).fetchall()
        conn.close()
        self.write({'totalClients': total_clients, 'totalAssessments': total_assessments,
                    'recentAssessments': self.rows_to_list(recent)})

# ── App ───────────────────────────────────────────────────────────────────────
def make_app():
    static_path = os.path.join(os.path.dirname(__file__), 'public')
    return tornado.web.Application([
        (r'/api/auth/login', LoginHandler),
        (r'/api/me', MeHandler),
        (r'/api/me/password', MeHandler),
        (r'/api/clients', ClientsHandler),
        (r'/api/clients/(\d+)', ClientHandler),
        (r'/api/clients/(\d+)/assessments', AssessmentsHandler),
        (r'/api/clients/(\d+)/assessments/pdf', AssessmentPDFHandler),
        (r'/api/assessments/(\d+)', AssessmentDeleteHandler),
        (r'/api/stats', StatsHandler),
        (r'/(.*)', tornado.web.StaticFileHandler, {
            'path': static_path,
            'default_filename': 'index.html'
        }),
    ])

async def main():
    init_db()
    app = make_app()
    app.listen(PORT)
    print(f'\n🏋️  Apolo Life - Sistema de Avaliação Física')
    print(f'🌐 Acesse: http://localhost:{PORT}')
    print(f'👤 Admin: admin@apoloct.com / admin123\n')
    await asyncio.Event().wait()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
