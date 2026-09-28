"""Financeiro da igreja. Execute: py Testes.py (Python 3.10+)."""
import csv
from contextlib import contextmanager
import getpass
import hashlib
import hmac
import io
import json
import os
import re
from pathlib import Path
import secrets
import socket
import sqlite3
import time
from functools import wraps
from datetime import date
from http.cookies import SimpleCookie, CookieError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from relatorio import month_bounds, render_report, render_expenses
from financeiro import closing_for, dashboard, first_month
from notas import validate_image, read_receipt
from notas_ia import status as ai_status, api_key
from categorias import CATEGORIES, categorize
from banco_online import database_url, connect_online, StorageUnavailable
import sessoes_online

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'financeiro.sqlite3'
CONFIG = ROOT / 'acesso.json'
SESSIONS = {}
ATTEMPTS = {}


def online():
    return bool(os.environ.get('VERCEL') or database_url())


def handle_errors(method):
    @wraps(method)
    def wrapped(self):
        try:
            return method(self)
        except StorageUnavailable as error:
            return self.reply(503, {'error': str(error)})
        except sqlite3.IntegrityError:
            return self.reply(409, {'error': 'Registro em conflito. Atualize a lista e confira se já foi cadastrado.'})
        except Exception as error:
            self.log_error('Falha em %s: %s', method.__name__, type(error).__name__)
            return self.reply(500, {'error': 'Falha interna do servidor. Consulte os logs da hospedagem.'})
    return wrapped


@contextmanager
def connect():
    if online():
        with connect_online() as con:
            yield con
        return
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    try:
        with con:
            yield con
    finally:
        con.close()


def initialize():
    if online():
        with connect_online():
            pass
        return
    with connect() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS entradas (
            id INTEGER PRIMARY KEY, tipo TEXT NOT NULL CHECK(tipo IN ('dizimo','oferta')),
            pessoa TEXT NOT NULL, valor INTEGER NOT NULL CHECK(valor > 0),
            data TEXT NOT NULL, forma TEXT NOT NULL, observacao TEXT NOT NULL)''')
        con.execute('''CREATE TABLE IF NOT EXISTS dizimistas (
            codigo TEXT PRIMARY KEY, nome TEXT NOT NULL)''')
        if 'dizimista_codigo' not in [r['name'] for r in con.execute('PRAGMA table_info(entradas)')]:
            con.execute('ALTER TABLE entradas ADD COLUMN dizimista_codigo TEXT REFERENCES dizimistas(codigo)')
        con.execute('CREATE TABLE IF NOT EXISTS ofertas (id INTEGER PRIMARY KEY, nome TEXT NOT NULL, chave TEXT NOT NULL UNIQUE)')
        columns = [r['name'] for r in con.execute('PRAGMA table_info(entradas)')]
        if 'oferta_id' not in columns:
            con.execute('ALTER TABLE entradas ADD COLUMN oferta_id INTEGER REFERENCES ofertas(id)')
        if 'oferta_nome' not in columns:
            con.execute("ALTER TABLE entradas ADD COLUMN oferta_nome TEXT NOT NULL DEFAULT ''")
        con.execute('''CREATE TABLE IF NOT EXISTS fechamentos (
            mes TEXT PRIMARY KEY, saldo_anterior INTEGER NOT NULL, despesas INTEGER NOT NULL CHECK(despesas >= 0))''')
        con.execute('CREATE TABLE IF NOT EXISTS saldo_inicial (id INTEGER PRIMARY KEY CHECK(id=1), mes TEXT NOT NULL, valor INTEGER NOT NULL)')
        con.execute('CREATE TABLE IF NOT EXISTS despesas (id INTEGER PRIMARY KEY, data TEXT NOT NULL, descricao TEXT NOT NULL, valor INTEGER NOT NULL CHECK(valor>0))')
        if 'categoria' not in [r['name'] for r in con.execute('PRAGMA table_info(despesas)')]:
            con.execute("ALTER TABLE despesas ADD COLUMN categoria TEXT NOT NULL DEFAULT 'Outros'")
            for row in con.execute('SELECT id,descricao FROM despesas').fetchall():
                con.execute('UPDATE despesas SET categoria=? WHERE id=?', (categorize(row['descricao']), row['id']))
        con.execute('''CREATE TABLE IF NOT EXISTS notas (
            id TEXT PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE, mime TEXT NOT NULL,
            imagem BLOB NOT NULL, sugestao TEXT NOT NULL)''')
        if 'nota_id' not in [r['name'] for r in con.execute('PRAGMA table_info(despesas)')]:
            con.execute('ALTER TABLE despesas ADD COLUMN nota_id TEXT REFERENCES notas(id)')
        con.execute('CREATE UNIQUE INDEX IF NOT EXISTS despesa_nota_unica ON despesas(nota_id) WHERE nota_id IS NOT NULL')
        con.execute('CREATE TABLE IF NOT EXISTS migracoes (nome TEXT PRIMARY KEY)')
        if not con.execute("SELECT 1 FROM migracoes WHERE nome='despesas_individuais'").fetchone():
            for row in con.execute('SELECT mes,despesas FROM fechamentos WHERE despesas>0').fetchall():
                con.execute('INSERT INTO despesas(data,descricao,valor) VALUES(?,?,?)',
                            (month_bounds(row['mes'])[1], 'Total de despesas informado no fechamento anterior (migrado)', row['despesas']))
            con.execute("INSERT INTO migracoes VALUES('despesas_individuais')")
    if not CONFIG.exists():
        print('Primeiro acesso: crie a senha do administrador (mínimo 8 caracteres).')
        while True:
            password = getpass.getpass('Senha: ')
            if len(password) >= 8 and password == getpass.getpass('Confirme a senha: '):
                break
            print('As senhas devem coincidir e ter pelo menos 8 caracteres.')
        salt = secrets.token_hex(16)
        CONFIG.write_text(json.dumps({'salt': salt, 'hash': digest(password, salt)}))


def digest(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600000).hex()


def verify_password(password):
    configured = os.environ.get('ADMIN_PASSWORD')
    if configured is not None:
        if len(configured) < 12:
            raise RuntimeError('Configure ADMIN_PASSWORD com pelo menos 12 caracteres nas variáveis de ambiente e faça um novo deploy.')
        return hmac.compare_digest(hashlib.sha256(password.encode()).digest(),
                                   hashlib.sha256(configured.encode()).digest())
    if online():
        raise RuntimeError('Login não configurado: adicione ADMIN_PASSWORD nas variáveis de ambiente da Vercel e faça um novo deploy.')
    try:
        config = json.loads(CONFIG.read_text(encoding='utf-8'))
        if not isinstance(config, dict) or not isinstance(config.get('salt'), str) or not isinstance(config.get('hash'), str):
            raise ValueError('Configuração inválida')
        return hmac.compare_digest(digest(password, config['salt']), config['hash'])
    except (OSError, ValueError, TypeError):
        raise RuntimeError('Configuração de acesso indisponível. Configure ADMIN_PASSWORD ou inicie o aplicativo local para configurar a senha.') from None


def normalize_code(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,30}', value.strip()):
        raise ValueError('Informe um código de até 30 letras, números, hífens ou sublinhados.')
    return value.strip().upper()


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, body, content_type='application/json; charset=utf-8', headers=None):
        if not isinstance(body, (str, bytes)):
            body = json.dumps(body, ensure_ascii=False)
        if isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def authenticated(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
            token = cookie['session'].value
        except (KeyError, CookieError):
            return False
        if online():
            return sessoes_online.authenticated(token)
        return SESSIONS.get(token, 0) > time.time()

    @handle_errors
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/':
            page = (ROOT / 'index.html').read_text(encoding='utf-8')
            page = page.replace('<head>', '<head><script>window.ONLINE_HOSTING=' + ('true' if os.environ.get('VERCEL') else 'false') + ';</script>', 1)
            if (ROOT / 'logo.png').is_file():
                page = page.replace('<span class="symbol">✦</span>',
                    '<img class="church-logo" src="/logo.png" alt="AD Piracicaba — Ministério Madureira">')
            return self.reply(200, page, 'text/html; charset=utf-8')
        if parsed.path == '/logo.png':
            logo = ROOT / 'logo.png'
            if logo.is_file():
                return self.reply(200, logo.read_bytes(), 'image/png')
            return self.reply(404, {'error': 'Logotipo não disponível.'})
        if parsed.path == '/mensal.js':
            return self.reply(200, (ROOT / 'mensal.js').read_bytes(), 'text/javascript; charset=utf-8')
        if parsed.path in ('/painel.js', '/painel.css', '/despesas.js'):
            return self.reply(200, (ROOT / parsed.path[1:]).read_bytes(),
                              'text/javascript; charset=utf-8' if parsed.path.endswith('.js') else 'text/css; charset=utf-8')
        if parsed.path == '/api/session':
            return self.reply(200, {'authenticated': self.authenticated()})
        if not self.authenticated():
            return self.reply(401, {'error': 'Entre com sua senha.'})
        if parsed.path == '/api/ia-status':
            return self.reply(200, ai_status())
        if parsed.path == '/api/nota':
            note_id = parse_qs(parsed.query).get('id', [''])[0]
            with connect() as con:
                note = con.execute('SELECT imagem,mime FROM notas WHERE id=?', (note_id,)).fetchone()
            if not note:
                return self.reply(404, {'error': 'Nota não encontrada.'})
            return self.reply(200, note['imagem'], note['mime'], {'Content-Disposition': 'inline'})
        if parsed.path in ('/api/despesas', '/relatorio-despesas'):
            mes = parse_qs(parsed.query).get('mes', [''])[0]
            try:
                inicio, fim = month_bounds(mes)
            except ValueError as error:
                return self.reply(400, {'error': str(error)})
            with connect() as con:
                rows = [dict(r) for r in con.execute('SELECT * FROM despesas WHERE data BETWEEN ? AND ? ORDER BY data,id', (inicio, fim))]
            if parsed.path == '/api/despesas':
                return self.reply(200, {'mes': mes, 'registros': rows, 'total': sum(r['valor'] for r in rows)})
            return self.reply(200, render_expenses(mes, rows, logo=(ROOT / 'logo.png').is_file()), 'text/html; charset=utf-8')
        if parsed.path == '/api/ofertas':
            with connect() as con:
                return self.reply(200, [dict(r) for r in con.execute('SELECT id,nome FROM ofertas ORDER BY nome')])
        if parsed.path in ('/api/fechamento', '/api/painel', '/relatorio'):
            mes = parse_qs(parsed.query).get('mes', [''])[0]
            try:
                inicio, fim = month_bounds(mes)
            except ValueError as error:
                return self.reply(400, {'error': str(error)})
            with connect() as con:
                if parsed.path == '/api/painel':
                    return self.reply(200, dashboard(con, mes))
                closing = closing_for(con, mes)
                rows = [dict(r) for r in con.execute('SELECT * FROM entradas WHERE data >= ? AND data <= ? ORDER BY data, id', (inicio, fim))]
            if parsed.path == '/api/fechamento':
                return self.reply(200, closing)
            if closing['saldo_anterior'] is None:
                return self.reply(409, {'error': 'Configure o saldo inicial na aba Lançamentos de entrada e escolha um mês a partir do mês inicial.'})
            return self.reply(200, render_report(mes, closing, rows, logo=(ROOT / 'logo.png').is_file()), 'text/html; charset=utf-8')
        if parsed.path == '/api/dizimistas':
            params = parse_qs(parsed.query, keep_blank_values=True)
            with connect() as con:
                if 'codigo' in params:
                    try:
                        codigo = normalize_code(params['codigo'][0])
                    except ValueError as error:
                        return self.reply(400, {'error': str(error)})
                    row = con.execute('SELECT * FROM dizimistas WHERE codigo = ?', (codigo,)).fetchone()
                    if row is None:
                        return self.reply(404, {'error': 'Código não cadastrado. Cadastre o dizimista primeiro.'})
                    return self.reply(200, dict(row))
                return self.reply(200, [dict(r) for r in con.execute('SELECT * FROM dizimistas ORDER BY nome COLLATE NOCASE, codigo')])
        if parsed.path not in ('/api/entradas', '/api/exportar'):
            return self.reply(404, {'error': 'Não encontrado.'})
        params = parse_qs(parsed.query)
        clauses, values = [], []
        for key, expression in [('inicio', 'data >= ?'), ('fim', 'data <= ?'), ('tipo', 'tipo = ?')]:
            if params.get(key, [''])[0]:
                clauses.append(expression)
                values.append(params[key][0])
        query = 'SELECT * FROM entradas' + (' WHERE ' + ' AND '.join(clauses) if clauses else '')
        with connect() as con:
            rows = [dict(row) for row in con.execute(query + ' ORDER BY data DESC, id DESC', values)]
        if parsed.path == '/api/entradas':
            return self.reply(200, rows)
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        writer.writerow(['Data', 'Tipo', 'Contribuinte', 'Valor (R$)', 'Pagamento', 'Observação', 'Código do dizimista', 'Nome da oferta'])
        def safe(value):
            value = str(value)
            return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value
        for row in rows:
            writer.writerow([row['data'], 'Dízimo' if row['tipo'] == 'dizimo' else 'Oferta', safe(row['pessoa']),
                             f"{row['valor'] / 100:.2f}".replace('.', ','), row['forma'], safe(row['observacao']), safe(row['dizimista_codigo'] or ''), safe(row['oferta_nome'])])
        for kind, label in [('dizimo', 'Total dízimos'), ('oferta', 'Total ofertas')]:
            writer.writerow(['', label, '', f"{sum(r['valor'] for r in rows if r['tipo'] == kind) / 100:.2f}".replace('.', ',')])
        writer.writerow(['', 'Total geral', '', f"{sum(r['valor'] for r in rows) / 100:.2f}".replace('.', ',')])
        return self.reply(200, '\ufeff' + output.getvalue(), 'text/csv; charset=utf-8',
                          {'Content-Disposition': 'attachment; filename="relatorio-entradas.csv"'})

    @handle_errors
    def do_POST(self):
        if self.headers.get('X-Requested-With') != 'Igreja':
            return self.reply(403, {'error': 'Requisição não autorizada.'})
        try:
            if self.path == '/api/notas' and not self.authenticated():
                return self.reply(401, {'error': 'Entre com sua senha para anexar a nota.'})
            size = int(self.headers.get('Content-Length', 0))
            note_limit = 4_400_000 if os.environ.get('VERCEL') else 12 * 1024 * 1024
            if not 0 < size <= (note_limit if self.path == '/api/notas' else 10000):
                raise ValueError('Requisição inválida.')
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError('Requisição inválida.')
            if self.path == '/api/login':
                ip = self.client_address[0]
                if os.environ.get('VERCEL'):
                    ip = self.headers.get('x-vercel-forwarded-for', ip).split(',')[0].strip()
                if online() and not sessoes_online.allow_attempt(ip):
                    return self.reply(429, {'error': 'Muitas tentativas. Aguarde 5 minutos.'})
                recent = [t for t in ATTEMPTS.get(ip, []) if t > time.time() - 300]
                ATTEMPTS[ip] = recent
                if len(recent) >= 10:
                    return self.reply(429, {'error': 'Muitas tentativas. Aguarde 5 minutos.'})
                try:
                    valid_password = verify_password(str(data.get('senha', '')))
                except RuntimeError as error:
                    return self.reply(503, {'error': str(error)})
                if not valid_password:
                    recent.append(time.time())
                    return self.reply(401, {'error': 'Senha incorreta.'})
                ATTEMPTS.pop(ip, None)
                if online():
                    sessoes_online.reset_attempts(ip)
                    token = sessoes_online.create_session()
                else:
                    token = secrets.token_urlsafe(32)
                    SESSIONS[token] = time.time() + 28800
                secure = '; Secure' if os.environ.get('VERCEL') else ''
                return self.reply(200, {'ok': True}, headers={'Set-Cookie': f'session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800{secure}'})
            if not self.authenticated():
                return self.reply(401, {'error': 'Sua sessão expirou. Entre novamente.'})
            if self.path in ('/api/entradas/excluir', '/api/despesas/excluir'):
                record_id = data.get('id')
                if type(record_id) is not int or not 0 < record_id <= 9223372036854775807:
                    raise ValueError('Informe um lançamento válido para excluir.')
                table = {'/api/entradas/excluir': 'entradas', '/api/despesas/excluir': 'despesas'}[self.path]
                with connect() as con:
                    cursor = con.execute(f'DELETE FROM {table} WHERE id = ?', (record_id,))
                    removed = cursor.rowcount
                if not removed:
                    return self.reply(404, {'error': 'Lançamento não encontrado ou já excluído.'})
                return self.reply(200, {'ok': True})
            if self.path == '/api/logout':
                cookie = SimpleCookie(self.headers.get('Cookie', ''))
                if online():
                    sessoes_online.logout(cookie['session'].value)
                else:
                    SESSIONS.pop(cookie['session'].value, None)
                return self.reply(200, {'ok': True}, headers={'Set-Cookie': 'session=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict'})
            if self.path == '/api/ofertas':
                nome = data.get('nome')
                if not isinstance(nome, str) or not 1 <= len(nome.strip()) <= 120:
                    raise ValueError('Informe um nome de oferta de até 120 caracteres.')
                nome = ' '.join(nome.split())
                try:
                    with connect() as con:
                        cursor = con.execute('INSERT INTO ofertas(nome,chave) VALUES(?,?) RETURNING id', (nome, nome.casefold()))
                        offer_id = cursor.fetchone()['id']
                except sqlite3.IntegrityError:
                    return self.reply(409, {'error': 'Esta oferta já está cadastrada.'})
                return self.reply(201, {'id': offer_id, 'nome': nome})
            if self.path == '/api/saldo-inicial':
                mes, valor = data.get('mes'), data.get('valor')
                month_bounds(mes)
                if type(valor) is not int or abs(valor) > 999999999:
                    raise ValueError('Informe um saldo inicial válido.')
                with connect() as con:
                    con.execute('BEGIN IMMEDIATE')
                    if con.execute('SELECT 1 FROM saldo_inicial').fetchone():
                        return self.reply(409, {'error': 'O saldo inicial já foi definido e está travado.'})
                    if mes > first_month(con):
                        raise ValueError('O mês inicial não pode ser posterior ao primeiro mês registrado.')
                    con.execute('INSERT INTO saldo_inicial(id,mes,valor) VALUES(1,?,?)', (mes, valor))
                return self.reply(201, {'ok': True})
            if self.path == '/api/notas':
                raw, mime, fingerprint = validate_image(data.get('arquivo'))
                with connect() as con:
                    existing = con.execute('SELECT id,sugestao FROM notas WHERE sha256=?', (fingerprint,)).fetchone()
                    if existing and con.execute('SELECT 1 FROM despesas WHERE nota_id=?', (existing['id'],)).fetchone():
                        return self.reply(409, {'error': 'Esta foto já está vinculada a uma despesa.'})
                cached = json.loads(existing['sugestao']) if existing else {}
                if existing and not data.get('reanalisar') and cached.get('versao', 0) >= 3 and cached.get('valor') is not None and cached.get('fonte') == ('ia' if api_key() else 'ocr'):
                    return self.reply(200, {'id': existing['id'], **cached, 'categoria': categorize(cached.get('descricao', ''))})
                suggestion = read_receipt(raw)
                with connect() as con:
                    con.execute('INSERT OR IGNORE INTO notas VALUES(?,?,?,?,?)',
                                (secrets.token_hex(16), fingerprint, mime, raw, json.dumps(suggestion, ensure_ascii=False)))
                    note = con.execute('SELECT id,sugestao FROM notas WHERE sha256=?', (fingerprint,)).fetchone()
                    con.execute('UPDATE notas SET sugestao=? WHERE id=?', (json.dumps(suggestion, ensure_ascii=False), note['id']))
                return self.reply(201, {'id': note['id'], **suggestion, 'categoria': categorize(suggestion.get('descricao', ''))})
            if self.path == '/api/despesas/editar':
                record_id, description, category = data.get('id'), data.get('descricao'), data.get('categoria')
                if type(record_id) is not int or not 0 < record_id <= 9223372036854775807:
                    raise ValueError('Lançamento inválido.')
                if not isinstance(description, str) or not 1 <= len(description.strip()) <= 500 or category not in CATEGORIES:
                    raise ValueError('Informe uma descrição e uma categoria válida.')
                with connect() as con:
                    changed = con.execute('UPDATE despesas SET descricao=?,categoria=? WHERE id=?', (description.strip(), category, record_id)).rowcount
                return self.reply(200 if changed else 404, {'ok': True} if changed else {'error': 'Despesa não encontrada.'})
            if self.path == '/api/despesas':
                dia, descricao, valor = data.get('data'), data.get('descricao'), data.get('valor')
                if not isinstance(dia, str) or date.fromisoformat(dia).isoformat() != dia:
                    raise ValueError('Informe uma data válida.')
                if not isinstance(descricao, str) or not 1 <= len(descricao.strip()) <= 500:
                    raise ValueError('Informe uma descrição de até 500 caracteres.')
                if type(valor) is not int or not 1 <= valor <= 999999999:
                    raise ValueError('Informe um valor positivo de até R$ 9.999.999,99.')
                category = data.get('categoria', categorize(descricao))
                if category not in CATEGORIES:
                    raise ValueError('Categoria inválida.')
                with connect() as con:
                    con.execute('BEGIN IMMEDIATE')
                    note_id = data.get('nota_id')
                    if not isinstance(note_id, str) or not con.execute('SELECT 1 FROM notas WHERE id=?', (note_id,)).fetchone():
                        raise ValueError('Anexe a foto da nota antes de salvar a despesa.')
                    if con.execute('SELECT 1 FROM despesas WHERE nota_id=?', (note_id,)).fetchone():
                        return self.reply(409, {'error': 'Esta nota já está vinculada a uma despesa.'})
                    initial = con.execute('SELECT mes FROM saldo_inicial WHERE id=1').fetchone()
                    if initial and dia[:7] < initial['mes']:
                        raise ValueError('A data não pode ser anterior ao mês inicial do sistema.')
                    con.execute('INSERT INTO despesas(data,descricao,valor,nota_id,categoria) VALUES(?,?,?,?,?)', (dia, descricao.strip(), valor, note_id, category))
                return self.reply(201, {'ok': True})
            if self.path == '/api/fechamento':
                mes = data.get('mes')
                month_bounds(mes)
                if 'despesas' in data:
                    raise ValueError('O total de despesas é automático. Use a aba Lançamentos de despesas.')
                if 'saldo_anterior' in data:
                    raise ValueError('O saldo anterior é automático. Configure o primeiro saldo na aba Lançamentos de entrada.')
                with connect() as con:
                    con.execute('BEGIN IMMEDIATE')
                    closing = closing_for(con, mes)
                    saldo, despesas = closing['saldo_anterior'], closing['despesas']
                    if saldo is None:
                        raise ValueError('Configure o saldo inicial na aba Lançamentos de entrada e selecione um mês válido.')
                    con.execute('''INSERT INTO fechamentos(mes,saldo_anterior,despesas) VALUES(?,?,?)
                        ON CONFLICT(mes) DO UPDATE SET saldo_anterior=excluded.saldo_anterior, despesas=excluded.despesas''', (mes, saldo, despesas))
                return self.reply(200, {'ok': True})
            if self.path == '/api/dizimistas':
                codigo = normalize_code(data.get('codigo'))
                nome = data.get('nome')
                if not isinstance(nome, str) or not 1 <= len(nome.strip()) <= 120:
                    raise ValueError('Informe um nome de até 120 caracteres.')
                try:
                    with connect() as con:
                        con.execute('INSERT INTO dizimistas(codigo,nome) VALUES(?,?)', (codigo, nome.strip()))
                except sqlite3.IntegrityError:
                    return self.reply(409, {'error': 'Este código já está cadastrado. Utilize outro código.'})
                return self.reply(201, {'codigo': codigo, 'nome': nome.strip()})
            if self.path != '/api/entradas':
                return self.reply(404, {'error': 'Não encontrado.'})
            tipo = data.get('tipo')
            valor = data.get('valor')
            pessoa = str(data.get('pessoa', '')).strip()
            forma = data.get('forma')
            dia = str(data.get('data', ''))
            obs = str(data.get('observacao', '')).strip()
            if tipo not in ('dizimo', 'oferta') or forma not in ('Pix', 'Dinheiro', 'Transferência', 'Cartão'):
                raise ValueError('Selecione o tipo e a forma de pagamento.')
            if type(valor) is not int or not 1 <= valor <= 999999999:
                raise ValueError('Informe um valor válido, de até R$ 9.999.999,99.')
            if date.fromisoformat(dia).isoformat() != dia:
                raise ValueError('Data inválida.')
            codigo = None
            oferta_id, oferta_nome = None, ''
            if tipo == 'oferta' and data.get('oferta_id') is not None:
                oferta_id = data['oferta_id']
                if type(oferta_id) is not int:
                    raise ValueError('Selecione uma oferta cadastrada.')
                with connect() as con:
                    oferta = con.execute('SELECT nome FROM ofertas WHERE id = ?', (oferta_id,)).fetchone()
                if oferta is None:
                    raise ValueError('Oferta não cadastrada.')
                oferta_nome = oferta['nome']
            if tipo == 'dizimo':
                codigo = normalize_code(data.get('codigo'))
                with connect() as con:
                    dizimista = con.execute('SELECT nome FROM dizimistas WHERE codigo = ?', (codigo,)).fetchone()
                if dizimista is None:
                    raise ValueError('Código não cadastrado. Cadastre o dizimista primeiro.')
                pessoa = dizimista['nome']
            if len(pessoa) > 120 or len(obs) > 500:
                raise ValueError('Nome ou observação muito longo.')
            with connect() as con:
                con.execute('BEGIN IMMEDIATE')
                initial = con.execute('SELECT mes FROM saldo_inicial WHERE id=1').fetchone()
                if initial and dia[:7] < initial['mes']:
                    raise ValueError('A data não pode ser anterior ao mês inicial do sistema.')
                con.execute('INSERT INTO entradas(tipo,pessoa,valor,data,forma,observacao,dizimista_codigo,oferta_id,oferta_nome) VALUES(?,?,?,?,?,?,?,?,?)',
                            (tipo, pessoa or 'Não identificado', valor, dia, forma, obs, codigo, oferta_id, oferta_nome))
            self.reply(201, {'ok': True})
        except (ValueError, TypeError) as error:
            self.reply(400, {'error': str(error) or 'Dados inválidos.'})


if __name__ == '__main__':
    initialize()
    port = int(os.environ.get('PORT', '8000'))
    print(f'Abra neste computador: http://localhost:{port}')
    print('Na mesma rede, use http://IP-DESTE-COMPUTADOR:' + str(port))
    print('IPs detectados: ' + ', '.join(socket.gethostbyname_ex(socket.gethostname())[2]))
    print('Mantenha este terminal aberto. Para encerrar, pressione Ctrl+C.')
    server = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
