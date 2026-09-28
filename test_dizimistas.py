import json
import base64
import io
from unittest.mock import patch
from PIL import Image
import re
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import Testes as app


class DizimistasTest(unittest.TestCase):
    def test_cadastro_vinculo_e_migracao(self):
        old_db, old_config = app.DB, app.CONFIG
        with tempfile.TemporaryDirectory() as directory:
            app.DB = Path(directory) / 'test.sqlite3'
            app.CONFIG = Path(directory) / 'acesso.json'
            app.CONFIG.write_text('{}')
            with sqlite3.connect(app.DB) as con:
                con.execute('CREATE TABLE entradas (id INTEGER PRIMARY KEY, tipo TEXT, pessoa TEXT, valor INTEGER, data TEXT, forma TEXT, observacao TEXT)')
                con.execute("INSERT INTO entradas VALUES(1,'dizimo','Registro antigo',1000,'2026-09-01','Pix','')")
            con.close()
            app.initialize()
            app.initialize()  # Reiniciar não pode perder dados nem repetir a migração.
            server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            app.SESSIONS['test-session'] = time.time() + 60

            def request(path, body=None, authenticated=True):
                headers = {'X-Requested-With': 'Igreja', 'Content-Type': 'application/json'}
                if authenticated:
                    headers['Cookie'] = 'session=test-session'
                req = Request(f'http://127.0.0.1:{server.server_port}' + path,
                              data=json.dumps(body).encode() if body is not None else None, headers=headers)
                try:
                    response = urlopen(req)
                except HTTPError as error:
                    response = error
                with response:
                    raw = response.read()
                    if response.headers['Content-Type'].startswith('image/'):
                        return response.status, raw
                    content = raw.decode('utf-8-sig')
                    return response.status, json.loads(content) if 'application/json' in response.headers['Content-Type'] else content

            try:
                self.assertEqual(request('/api/dizimistas', authenticated=False)[0], 401)
                self.assertEqual(request('/api/dizimistas', {'codigo': '001', 'nome': 'João da Silva'})[0], 201)
                self.assertEqual(request('/api/dizimistas', {'codigo': '001', 'nome': 'Outro nome'})[0], 409)
                self.assertEqual(request('/api/dizimistas', {'codigo': '', 'nome': 'Nome'})[0], 400)
                self.assertEqual(request('/api/dizimistas?codigo=001')[1]['nome'], 'João da Silva')
                self.assertEqual(request('/api/dizimistas?codigo=999')[0], 404)
                self.assertEqual(request('/api/dizimistas', {'codigo': 'ab-02', 'nome': 'Maria'})[0], 201)
                self.assertEqual(request('/api/dizimistas?codigo=ab-02')[1]['codigo'], 'AB-02')
                entry = dict(tipo='dizimo', codigo='001', pessoa='Nome adulterado', valor=25050,
                             data='2026-09-24', forma='Pix', observacao='')
                self.assertEqual(request('/api/entradas', entry)[0], 201)
                rows = request('/api/entradas')[1]
                self.assertEqual(rows[0]['pessoa'], 'João da Silva')
                self.assertEqual(rows[0]['dizimista_codigo'], '001')
                self.assertEqual(rows[1]['pessoa'], 'Registro antigo')
                self.assertIsNone(rows[1]['dizimista_codigo'])
                entry['codigo'] = '999'
                self.assertEqual(request('/api/entradas', entry)[0], 400)
                entry.update(tipo='oferta', pessoa='', codigo='')
                self.assertEqual(request('/api/entradas', entry)[0], 201)
                self.assertIsNone(request('/api/entradas')[1][0]['dizimista_codigo'])
                csv = request('/api/exportar')[1]
                self.assertIn('Código do dizimista', csv)
                self.assertIn('João da Silva;250,50;Pix;;001', csv)
                self.assertEqual(len(request('/api/dizimistas')[1]), 2)
                self.assertEqual(request('/api/ofertas', authenticated=False)[0], 401)
                status, offer = request('/api/ofertas', {'nome': 'Culto de oração'})
                self.assertEqual(status, 201)
                self.assertEqual(request('/api/ofertas', {'nome': ' CULTO DE ORAÇÃO '})[0], 409)
                self.assertEqual(request('/api/ofertas', {'nome': ' '})[0], 400)
                self.assertEqual(request('/api/ofertas')[1][0]['nome'], 'Culto de oração')
                entry.update(oferta_id=offer['id'], pessoa='Ana <Silva>', valor=2970)
                self.assertEqual(request('/api/entradas', entry)[0], 201)
                self.assertEqual(request('/api/entradas')[1][0]['oferta_nome'], 'Culto de oração')
                entry['oferta_id'] = 999
                self.assertEqual(request('/api/entradas', entry)[0], 400)
                self.assertEqual(request('/api/fechamento?mes=2026-13')[0], 400)
                self.assertIsNone(request('/api/fechamento?mes=2026-09')[1]['saldo_anterior'])
                self.assertEqual(request('/api/saldo-inicial', {'mes':'2026-10','valor':0})[0], 400)
                self.assertEqual(request('/api/saldo-inicial', {'mes':'2026-09','valor':-156})[0], 201)
                self.assertEqual(request('/api/saldo-inicial', {'mes':'2026-09','valor':100})[0], 409)
                def upload_note(color):
                    output = io.BytesIO()
                    Image.new('RGB', (20, 20), color).save(output, format='PNG')
                    encoded = base64.b64encode(output.getvalue()).decode()
                    with patch.object(app, 'read_receipt', return_value={'valor':60000,'descricao':'Alimentos','mensagem':'Confira','texto':'ARROZ 600,00\nTOTAL 600,00'}):
                        status, result = request('/api/notas', {'arquivo':encoded})
                    self.assertEqual(status, 201)
                    self.assertEqual(request('/api/nota?id='+result['id'])[1], output.getvalue())
                    self.assertEqual(request('/api/nota?id='+result['id'], authenticated=False)[0], 401)
                    return result['id'], encoded
                self.assertEqual(request('/api/despesas', {'data':'2026-09-24','descricao':'Sem nota','valor':100})[0], 400)
                self.assertEqual(request('/api/notas', {'arquivo':'invalido'})[0], 400)
                note_id, encoded = upload_note('white')
                expense = {'data':'2026-09-24','descricao':'Energia e manutenção','valor':60000,'nota_id':note_id}
                self.assertEqual(request('/api/despesas', expense)[0], 201)
                self.assertEqual(request('/api/despesas', expense)[0], 409)
                self.assertEqual(request('/api/notas', {'arquivo':encoded})[0], 409)
                self.assertEqual(request('/api/despesas', {'data':'2026-09-24','descricao':'','valor':100})[0], 400)
                self.assertEqual(request('/api/despesas', {'data':'2026-09-24','descricao':'Teste','valor':-100})[0], 400)
                self.assertEqual(request('/api/despesas?mes=2026-09')[1]['total'], 60000)
                self.assertEqual(request('/api/despesas?mes=2026-10')[1]['total'], 0)
                self.assertEqual(request('/api/despesas?mes=2026-09', authenticated=False)[0], 401)
                self.assertIn('CRÉDITO', request('/relatorio-despesas?mes=2026-09')[1])
                self.assertIn('Energia e manutenção', request('/relatorio-despesas?mes=2026-09')[1])
                closing = {'mes': '2026-09'}
                self.assertEqual(request('/api/fechamento', dict(closing, saldo_anterior=999))[0], 400)
                self.assertEqual(request('/api/fechamento', closing)[0], 200)
                self.assertEqual(request('/api/fechamento?mes=2026-09')[1]['despesas'], 60000)
                self.assertEqual(request('/api/fechamento', dict(closing, despesas=-1))[0], 400)
                status, report = request('/relatorio?mes=2026-09')
                self.assertEqual(status, 200)
                self.assertIn('OFERTA - CULTO DE ORAÇÃO / ANA &lt;SILVA&gt;', report)
                report_text = re.sub(r'<[^>]+>', '', report)
                self.assertIn('R$ 260,50', report_text)  # Dízimos, inclusive registro antigo.
                self.assertIn('R$ 280,20', report_text)  # Oferta avulsa e oferta cadastrada.
                self.assertIn('-R$ 60,86', report_text)  # -1,56 + 540,70 - 600,00.
                self.assertLess(report.index('01/09/26'), report.index('24/09/26'))
                self.assertNotIn('JOÃO DA SILVA', request('/relatorio?mes=2026-10')[1])
                self.assertIn('Nenhuma entrada', request('/relatorio?mes=2026-10')[1])
                self.assertEqual(request('/relatorio?mes=2026-09', authenticated=False)[0], 401)
                self.assertEqual(request('/api/fechamento?mes=2026-10')[1]['saldo_anterior'], -6086)
                self.assertEqual(request('/api/fechamento?mes=2027-01')[1]['saldo_anterior'], -6086)
                self.assertIsNone(request('/api/fechamento?mes=2026-08')[1]['saldo_anterior'])
                self.assertEqual(request('/relatorio?mes=2026-08')[0], 409)
                entry.update(oferta_id=offer['id'], data='2026-08-31')
                self.assertEqual(request('/api/entradas', entry)[0], 400)
                entry.update(data='2026-09-30', valor=10000)
                self.assertEqual(request('/api/entradas', entry)[0], 201)
                self.assertEqual(request('/api/fechamento?mes=2027-01')[1]['saldo_anterior'], 3914)
                second_note, _ = upload_note('gray')
                self.assertEqual(request('/api/despesas', {'data':'2026-10-01','descricao':'Água','valor':1000,'nota_id':second_note})[0], 201)
                self.assertEqual(request('/api/fechamento?mes=2027-01')[1]['saldo_anterior'], 2914)
                panel = request('/api/painel?mes=2026-09')[1]
                self.assertEqual(panel['dizimo']['media'], 13025)
                self.assertEqual(panel['oferta']['quantidade'], 3)
                self.assertEqual(len(panel['historico']), 6)
                self.assertEqual(panel['dizimistas_quantidade'], 2)
                repeat = dict(tipo='dizimo', codigo='001', valor=100, data='2026-09-30', forma='Pix')
                self.assertEqual(request('/api/entradas', repeat)[0], 201)
                self.assertEqual(request('/api/painel?mes=2026-09')[1]['dizimistas_quantidade'], 2)
                self.assertEqual(request('/api/painel?mes=2026-10')[1]['dizimistas_quantidade'], 0)
                self.assertEqual(request('/api/painel?mes=2026-10')[1]['oferta']['media'], None)
                saved_expense = request('/api/despesas?mes=2026-09')[1]['registros'][0]
                update = {'id': saved_expense['id'], 'descricao': 'Alimentos para cozinha', 'categoria': 'Alimentação'}
                self.assertEqual(request('/api/despesas/editar', update, authenticated=False)[0], 401)
                self.assertEqual(request('/api/despesas/editar', dict(update, categoria='Inválida'))[0], 400)
                self.assertEqual(request('/api/despesas/editar', dict(update, descricao=''))[0], 400)
                self.assertEqual(request('/api/despesas/editar', update)[0], 200)
                edited = request('/api/despesas?mes=2026-09')[1]['registros'][0]
                self.assertEqual(edited['categoria'], 'Alimentação')
                self.assertEqual(edited['descricao'], update['descricao'])
                self.assertEqual(edited['valor'], saved_expense['valor'])
                self.assertEqual(edited['nota_id'], saved_expense['nota_id'])
                app.initialize()
                self.assertEqual(request('/api/despesas?mes=2026-09')[1]['registros'][0]['categoria'], 'Alimentação')
                # Delete only temporary test data; check subsequent monthly balances.
                for kind, listing in [('entradas', '/api/entradas?inicio=2026-09-01&fim=2026-09-30'),
                                      ('despesas', '/api/despesas?mes=2026-09')]:
                    records = request(listing)[1]
                    record = records[0] if kind == 'entradas' else records['registros'][0]
                    endpoint = '/api/' + kind + '/excluir'
                    payload = {'id': record['id']}
                    before = request('/api/fechamento?mes=2027-01')[1]['saldo_anterior']
                    self.assertEqual(request(endpoint, payload, authenticated=False)[0], 401)
                    for invalid in [None, True, '1', 0, -1, 2**64]:
                        self.assertEqual(request(endpoint, {'id': invalid})[0], 400)
                    self.assertEqual(request(endpoint, payload)[0], 200)
                    self.assertEqual(request(endpoint, payload)[0], 404)
                    delta = -record['valor'] if kind == 'entradas' else record['valor']
                    self.assertEqual(request('/api/fechamento?mes=2027-01')[1]['saldo_anterior'], before + delta)
                    remaining = request(listing)[1]
                    remaining = remaining if kind == 'entradas' else remaining['registros']
                    self.assertNotIn(record['id'], [r['id'] for r in remaining])
                    if kind == 'despesas':
                        self.assertEqual(request('/api/nota?id=' + record['nota_id'])[0], 200)
                        self.assertEqual(request('/api/despesas?mes=2026-09')[1]['total'], 0)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
                app.SESSIONS.pop('test-session', None)
                app.DB, app.CONFIG = old_db, old_config


if __name__ == '__main__':
    unittest.main()
