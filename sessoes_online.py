"""Sessões revogáveis e limite de login compartilhados entre instâncias."""
import hashlib
import os
import secrets
import time
from banco_online import connect_online


def credential():
    return hashlib.sha256(os.environ.get('ADMIN_PASSWORD', '').encode()).hexdigest()


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def create_session():
    token = secrets.token_urlsafe(32)
    with connect_online() as con:
        con.execute('DELETE FROM sessoes WHERE expira<=?', (int(time.time()),))
        con.execute('INSERT INTO sessoes(token,expira,credencial) VALUES(?,?,?)',
                    (token_hash(token), int(time.time()) + 28800, credential()))
    return token


def authenticated(token):
    if not os.environ.get('ADMIN_PASSWORD') or len(token) > 128:
        return False
    with connect_online() as con:
        return bool(con.execute('SELECT 1 FROM sessoes WHERE token=? AND expira>? AND credencial=?',
                                (token_hash(token), int(time.time()), credential())).fetchone())


def logout(token):
    with connect_online() as con:
        con.execute('DELETE FROM sessoes WHERE token=?', (token_hash(token),))


def allow_attempt(ip):
    now = int(time.time())
    key = token_hash(ip)
    with connect_online() as con:
        con.execute('DELETE FROM tentativas_login WHERE inicio<?', (now - 300,))
        row = con.execute('''INSERT INTO tentativas_login(chave,inicio,quantidade) VALUES(?,?,1)
            ON CONFLICT(chave) DO UPDATE SET quantidade=tentativas_login.quantidade+1
            RETURNING quantidade''', (key, now)).fetchone()
        return row['quantidade'] <= 10


def reset_attempts(ip):
    with connect_online() as con:
        con.execute('DELETE FROM tentativas_login WHERE chave=?', (token_hash(ip),))
