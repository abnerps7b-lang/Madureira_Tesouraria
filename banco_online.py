"""PostgreSQL persistente para Vercel; nenhuma cópia temporária do banco."""
import os
import sqlite3
import threading
from decimal import Decimal
from contextlib import contextmanager


class StorageUnavailable(RuntimeError):
    pass


def database_url():
    return os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')


SCHEMA = '''
CREATE TABLE IF NOT EXISTS dizimistas(codigo TEXT PRIMARY KEY,nome TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ofertas(id BIGSERIAL PRIMARY KEY,nome TEXT NOT NULL,chave TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS notas(id TEXT PRIMARY KEY,sha256 TEXT NOT NULL UNIQUE,mime TEXT NOT NULL,imagem BYTEA NOT NULL,sugestao TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS entradas(id BIGSERIAL PRIMARY KEY,tipo TEXT NOT NULL CHECK(tipo IN ('dizimo','oferta')),pessoa TEXT NOT NULL,valor BIGINT NOT NULL CHECK(valor>0),data TEXT NOT NULL,forma TEXT NOT NULL,observacao TEXT NOT NULL,dizimista_codigo TEXT REFERENCES dizimistas(codigo),oferta_id BIGINT REFERENCES ofertas(id),oferta_nome TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS despesas(id BIGSERIAL PRIMARY KEY,data TEXT NOT NULL,descricao TEXT NOT NULL,valor BIGINT NOT NULL CHECK(valor>0),categoria TEXT NOT NULL DEFAULT 'Outros',nota_id TEXT REFERENCES notas(id));
CREATE UNIQUE INDEX IF NOT EXISTS despesa_nota_unica ON despesas(nota_id) WHERE nota_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS fechamentos(mes TEXT PRIMARY KEY,saldo_anterior BIGINT NOT NULL,despesas BIGINT NOT NULL CHECK(despesas>=0));
CREATE TABLE IF NOT EXISTS saldo_inicial(id INTEGER PRIMARY KEY CHECK(id=1),mes TEXT NOT NULL,valor BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS migracoes(nome TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS sessoes(token TEXT PRIMARY KEY,expira BIGINT NOT NULL,credencial TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tentativas_login(chave TEXT PRIMARY KEY,inicio BIGINT NOT NULL,quantidade INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS entradas_data ON entradas(data);
CREATE INDEX IF NOT EXISTS despesas_data ON despesas(data);
'''
_ready = set()
_lock = threading.Lock()


class Row(dict):
    def __getitem__(self, key):
        return list(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


def row_factory(cursor):
    names = [column.name for column in cursor.description] if cursor.description else []
    return lambda values: Row(zip(names, (int(v) if isinstance(v, Decimal) and v == v.to_integral_value() else v for v in values)))


class Connection:
    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, params=()):
        # Only application-owned SQL reaches this adapter; values stay parameterized.
        if sql == 'BEGIN IMMEDIATE':
            # Serializes dependent financial writes, including initial balance checks.
            return self.raw.execute('SELECT pg_advisory_xact_lock(481726)')
        sql = sql.replace('nome COLLATE NOCASE', 'lower(nome)')
        if sql.startswith('INSERT OR IGNORE INTO notas'):
            sql = sql.replace('INSERT OR IGNORE', 'INSERT', 1) + ' ON CONFLICT DO NOTHING'
        return self.raw.execute(sql.replace('?', '%s'), params)


@contextmanager
def connect_online():
    url = database_url()
    if not url:
        raise StorageUnavailable('Banco online não configurado. Conecte PostgreSQL e defina DATABASE_URL na Vercel.')
    import psycopg
    try:
        with psycopg.connect(url, connect_timeout=10, prepare_threshold=None, row_factory=row_factory) as raw:
            with _lock:
                if url not in _ready:
                    raw.execute('SELECT pg_advisory_xact_lock(481725)')
                    for statement in SCHEMA.split(';'):
                        if statement.strip():
                            raw.execute(statement)
                    raw.commit()
                    _ready.add(url)
            yield Connection(raw)
    except psycopg.IntegrityError:
        raise sqlite3.IntegrityError('Conflito de integridade no banco online.') from None
    except psycopg.Error:
        # Do not expose connection strings, credentials or SQL parameters in responses.
        raise StorageUnavailable('Não foi possível acessar o banco online. Confira DATABASE_URL e a disponibilidade do PostgreSQL.') from None
