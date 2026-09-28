"""Importa uma cópia consistente do SQLite em um PostgreSQL vazio."""
import argparse
import sqlite3
from pathlib import Path
from banco_online import connect_online, database_url

TABLES = ['dizimistas', 'ofertas', 'notas', 'entradas', 'despesas', 'fechamentos', 'saldo_inicial', 'migracoes']


def migrate(source, apply=False):
    path = Path(source).resolve()
    if not path.is_file():
        raise ValueError('Banco local não encontrado.')
    if not database_url():
        raise ValueError('Defina DATABASE_URL no ambiente deste terminal; não coloque a conexão no código.')
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as original, sqlite3.connect(':memory:') as snapshot:
        original.backup(snapshot)
        snapshot.row_factory = sqlite3.Row
        records = {table: snapshot.execute(f'SELECT * FROM {table}').fetchall() for table in TABLES}
        with connect_online() as target:
            target.execute('BEGIN IMMEDIATE')
            target.execute('LOCK TABLE ' + ','.join(TABLES) + ' IN ACCESS EXCLUSIVE MODE')
            if any(target.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in TABLES):
                raise ValueError('O destino já contém dados. A importação exige um banco vazio e não sobrescreve registros.')
            counts = {table: len(rows) for table, rows in records.items()}
            if not apply:
                return counts
            for table, rows in records.items():
                allowed = {r['column_name'] for r in target.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=?", (table,))}
                for row in rows:
                    columns = list(row.keys())
                    # Both schemas are owned by this application; validate local identifiers.
                    if not set(columns) <= allowed:
                        raise ValueError('Estrutura local incompatível. Atualize o aplicativo antes de importar.')
                    target.execute(f"INSERT INTO {table}({','.join(columns)}) VALUES({','.join('?' for _ in columns)})", tuple(row))
            for table in ['ofertas', 'entradas', 'despesas']:
                target.execute(f"SELECT setval(pg_get_serial_sequence('{table}','id'),COALESCE(MAX(id),1),MAX(id) IS NOT NULL) FROM {table}")
            for table, count in counts.items():
                if target.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] != count:
                    raise ValueError('Falha na conferência da importação.')
            return counts


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--banco', default='financeiro.sqlite3')
    parser.add_argument('--aplicar', action='store_true', help='Confirma a cópia dos registros para o banco vazio.')
    args = parser.parse_args()
    try:
        for table, count in migrate(args.banco, args.aplicar).items():
            print(f'{table}: {count} registros')
        print('Importação concluída.' if args.aplicar else 'Conferência concluída. Use --aplicar para copiar os dados.')
    except Exception as error:
        print('Importação não concluída:', str(error) if isinstance(error, (ValueError, RuntimeError)) else type(error).__name__)
        raise SystemExit(1)
