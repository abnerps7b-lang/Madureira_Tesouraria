"""Relatório mensal de entradas, em formato A4."""
import calendar
from datetime import date
from html import escape
import re


def render_expenses(mes, rows, logo=False):
    page = render_report(mes, {'saldo_anterior': 0, 'despesas': 0}, [], logo=logo)
    title = re.search(r'<title>(.*?)</title>', page).group(1)
    lines = []
    for row in rows:
        day = date.fromisoformat(row['data']).strftime('%d/%m/%y')
        lines.append(f'<tr><td class="date">{day}</td><td>{escape(row["descricao"])}</td>'
                     f'<td class="value"><span class="accounting"><span>R$</span><span>{money(row["valor"])[3:]}</span></span></td></tr>')
    if not rows:
        lines.append('<tr><td colspan="3" class="empty">Nenhuma despesa registrada neste mês.</td></tr>')
    total = sum(r['valor'] for r in rows)
    table = f'''<table><colgroup><col style="width:17%"><col style="width:63%"><col style="width:20%"></colgroup>
<thead><tr class="title"><td>XA</td><td>{title}</td><td>CRÉDITO</td></tr>
<tr><th>Data</th><th>Descrição</th><th>R$</th></tr></thead><tbody>{''.join(lines)}</tbody></table>
<table style="break-inside:avoid"><colgroup><col style="width:80%"><col style="width:20%"></colgroup><tr><th>Total de despesas do mês</th><td class="value"><span class="accounting"><span>R$</span><strong>{money(total)[3:]}</strong></span></td></tr></table>'''
    start = page.index('<table>')
    end = page.index('<div class="signatures">', start)
    page = page[:start] + table + page[end:]
    return page.replace('todas as entradas', 'todas as despesas').replace('Fechamento mensal da tesouraria', 'Lançamentos de despesas — fechamento mensal')


def month_bounds(mes):
    if not isinstance(mes, str) or not re.fullmatch(r'\d{4}-\d{2}', mes):
        raise ValueError('Selecione um mês válido.')
    try:
        year, month = map(int, mes.split('-'))
        date(year, month, 1)
    except ValueError:
        raise ValueError('Selecione um mês válido.') from None
    return f'{mes}-01', f'{mes}-{calendar.monthrange(year, month)[1]:02d}'


def money(value):
    number = f'{abs(value) // 100:,}'.replace(',', '.') + f',{abs(value) % 100:02d}'
    return ('-R$ ' if value < 0 else 'R$ ') + number


def render_report(mes, closing, rows, logo=False):
    month_bounds(mes)
    months = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    title = f'Movimento financeiro - {months[int(mes[5:]) - 1]} - {mes[:4]}'
    balance = closing['saldo_anterior']
    tithes = sum(r['valor'] for r in rows if r['tipo'] == 'dizimo')
    offers = sum(r['valor'] for r in rows if r['tipo'] == 'oferta')
    total = tithes + offers
    end_balance = balance + total - closing['despesas']
    def amount(value):
        negative = value is not None and value < 0
        number = money(abs(value)).removeprefix('R$ ') if value is not None else '—'
        sign = '<span class="sign">-</span>' if negative else ''
        return (f'<span class="accounting{" negative" if negative else ""}">'
                f'<span class="currency">{sign}R$ </span><span class="number">{number}</span></span>')
    lines = [f'<tr><td></td><td>Saldo mês anterior</td><td class="value">{amount(balance)}</td><td class="value">{amount(None)}</td></tr>']
    for row in rows:
        offer = row['tipo'] == 'oferta'
        description = row['pessoa']
        if offer:
            description = 'OFERTA - ' + (row['oferta_nome'] or 'OFERTA AVULSA')
            if row['pessoa'] != 'Não identificado':
                description += ' / ' + row['pessoa']
        day = date.fromisoformat(row['data']).strftime('%d/%m/%y')
        lines.append(f'<tr class="{"offer" if offer else "tithe"}"><td class="date">{day}</td><td>{escape(description.upper())}</td>'
                     f'<td class="value">{amount(row["valor"] if not offer else None)}</td>'
                     f'<td class="value">{amount(row["valor"] if offer else None)}</td></tr>')
    if not rows:
        lines.append('<tr><td colspan="4" class="empty">Nenhuma entrada registrada neste mês.</td></tr>')
    summary = ''.join(f'<tr><td>{label}</td><td class="value">{amount(value)}</td></tr>' for label, value in [
        ('Saldo anterior', balance), ('Dízimos do mês', tithes), ('Ofertas do mês', offers),
        ('Total do mês', total), ('Despesas do mês', closing['despesas']), ('Saldo do mês', end_balance)])
    logo_html = '<img src="/logo.png" alt="AD Piracicaba — Ministério Madureira" class="report-logo">' if logo else ''
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#eef1f5;font:12px Arial,sans-serif;color:#111}}
.toolbar{{max-width:210mm;margin:20px auto;display:flex;gap:16px;align-items:center;padding:0 12px}}
button,a{{font:14px Arial;padding:12px 18px;border-radius:8px;background:#167968;color:white;border:0;text-decoration:none;cursor:pointer}}
.paper{{background:white;width:210mm;min-height:280mm;margin:20px auto;padding:12mm;box-shadow:0 3px 20px #0002}}
.church{{text-align:center;font-size:12px;margin-bottom:12px;line-height:1.6;break-inside:avoid}}.report-logo{{display:block;width:24mm;height:24mm;object-fit:contain;margin:0 auto 5px}}h1{{font-size:14px;margin:0}}
table{{width:100%;border-collapse:collapse;table-layout:fixed}}td,th{{border:1px solid #222;padding:3px 5px;overflow-wrap:anywhere}}
th{{font-size:11px}}.title td{{padding:7px 5px}}.title td:first-child,.title td:last-child{{font-size:18px}}
.title td:nth-child(2){{text-align:center;font-size:12px}}.title td:last-child{{text-align:right}}
.value{{text-align:right;white-space:nowrap}}.offer td:nth-child(2),.offer td:nth-child(4),.negative{{color:#c72323}}
.accounting{{display:flex;justify-content:space-between;align-items:baseline;gap:4px;font-variant-numeric:tabular-nums}}
.currency{{position:relative;flex-shrink:0;text-align:left}}.sign{{position:absolute;right:100%}}.number{{text-align:right}}.date{{text-align:center;white-space:nowrap}}
.summary{{margin-top:12px;width:100%;break-inside:avoid}}.summary th{{font-size:12px}}.summary tr:last-child{{font-weight:bold}}
.grand{{margin-top:8px;text-align:right;font-weight:bold}}.empty{{text-align:center;padding:20px}}
.signatures{{display:flex;gap:40px;margin-top:45px;break-inside:avoid}}.signatures span{{flex:1;text-align:center;border-top:1px solid #333;padding-top:6px}}
.hint{{max-width:210mm;margin:auto;color:#536678;padding:0 12px;font-size:13px}}
thead{{display:table-header-group}}tr{{break-inside:avoid}}@page{{size:A4 portrait;margin:12mm}}
@media(max-width:800px){{.paper{{width:100%;padding:15px}}.toolbar{{flex-wrap:wrap}}}}
@media print{{body{{background:white}}.toolbar,.hint{{display:none}}.paper{{width:100%;min-height:0;margin:0;padding:0;box-shadow:none}}*{{print-color-adjust:exact;-webkit-print-color-adjust:exact}}}}
</style></head><body><div class="toolbar"><button onclick="window.print()">Imprimir / Salvar PDF</button><a href="/">Voltar ao sistema</a></div>
<p class="hint">Imprima em A4, orientação retrato. Desative os cabeçalhos e rodapés do navegador. O relatório inclui todas as entradas do mês selecionado.</p>
<article class="paper"><div class="church">{logo_html}<strong>ASSEMBLEIA DE DEUS — MINISTÉRIO DE MADUREIRA</strong><br>Fechamento mensal da tesouraria</div>
<table><colgroup><col style="width:17%"><col style="width:51%"><col style="width:16%"><col style="width:16%"></colgroup>
<thead><tr class="title"><td>DÉBITO</td><td>{title}</td><td colspan="2">CAI</td></tr>
<tr><th>Data</th><th>Descrição / contribuinte</th><th>Dízimos (R$)</th><th>Ofertas (R$)</th></tr></thead><tbody>{''.join(lines)}</tbody></table>
<table class="summary"><colgroup><col style="width:84%"><col style="width:16%"></colgroup><thead><tr><th colspan="2">Resumo</th></tr></thead><tbody>{summary}</tbody></table>
<p class="grand">Total de entradas do mês: {money(total)}</p>
<div class="signatures"><span>Tesouraria</span><span>Responsável pela conferência</span></div></article></body></html>'''
