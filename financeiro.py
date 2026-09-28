"""Saldos encadeados e indicadores, sempre calculados em centavos."""
from datetime import date
from relatorio import month_bounds


def shift_month(mes, offset):
    year, month = map(int, mes.split('-'))
    year, month = divmod(year * 12 + month - 1 + offset, 12)
    return f'{year:04d}-{month + 1:02d}'


def first_month(con):
    row = con.execute("SELECT MIN(mes) FROM (SELECT substr(data,1,7) mes FROM entradas UNION ALL SELECT substr(data,1,7) FROM despesas UNION ALL SELECT mes FROM fechamentos) AS meses").fetchone()
    return row[0] or date.today().strftime('%Y-%m')


def closing_for(con, mes):
    start, end = month_bounds(mes)
    initial = con.execute('SELECT mes,valor FROM saldo_inicial WHERE id=1').fetchone()
    expenses = con.execute('SELECT COALESCE(SUM(valor),0) FROM despesas WHERE data BETWEEN ? AND ?', (start, end)).fetchone()[0]
    income = con.execute('SELECT COALESCE(SUM(valor),0) FROM entradas WHERE data BETWEEN ? AND ?', (start, end)).fetchone()[0]
    opening = None
    if initial and mes >= initial['mes']:
        past_income = con.execute('SELECT COALESCE(SUM(valor),0) FROM entradas WHERE data>=? AND data<?', (initial['mes']+'-01', start)).fetchone()[0]
        past_expenses = con.execute('SELECT COALESCE(SUM(valor),0) FROM despesas WHERE data>=? AND data<?', (initial['mes']+'-01', start)).fetchone()[0]
        opening = initial['valor'] + past_income - past_expenses
    return dict(mes=mes, saldo_anterior=opening, despesas=expenses, entradas=income,
                saldo_final=None if opening is None else opening + income - expenses,
                configurado=initial is not None, mes_inicial=initial['mes'] if initial else first_month(con),
                mes_anterior=shift_month(mes, -1))


def dashboard(con, mes):
    result = closing_for(con, mes)
    start, end = month_bounds(mes)
    rows = con.execute('SELECT tipo,valor,data,pessoa,dizimista_codigo FROM entradas WHERE data BETWEEN ? AND ?', (start, end)).fetchall()
    # Códigos distinguem homônimos; registros antigos sem código usam o nome.
    names = {}
    for member in con.execute('SELECT codigo,nome FROM dizimistas'):
        names.setdefault(' '.join(member['nome'].casefold().split()), set()).add(member['codigo'])
    contributors = set()
    for row in rows:
        if row['tipo'] != 'dizimo':
            continue
        name = ' '.join(row['pessoa'].casefold().split())
        matches = names.get(name, set())
        code = row['dizimista_codigo'] or (next(iter(matches)) if len(matches) == 1 else None)
        contributors.add(('codigo', code) if code else ('nome', name))
    result['dizimistas_quantidade'] = len(contributors)
    for kind in ('dizimo', 'oferta'):
        values = [r['valor'] for r in rows if r['tipo'] == kind]
        result[kind] = {'total': sum(values), 'quantidade': len(values), 'media': sum(values) / len(values) if values else None}
    series = []
    for offset in range(-5, 1):
        month = shift_month(mes, offset)
        a, b = month_bounds(month)
        totals = {r['tipo']: r['total'] for r in con.execute('SELECT tipo,SUM(valor) total FROM entradas WHERE data BETWEEN ? AND ? GROUP BY tipo', (a, b))}
        series.append({'mes': month, 'dizimo': totals.get('dizimo', 0), 'oferta': totals.get('oferta', 0)})
    result['historico'] = series
    return result
