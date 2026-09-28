"""Teste isolado do lote e edição, sem chamadas externas de OCR/IA."""
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from playwright.sync_api import sync_playwright, expect
import Testes as app


def main():
    with tempfile.TemporaryDirectory() as folder:
        app.DB = Path(folder) / 'test.db'
        app.CONFIG = Path(folder) / 'config.json'
        app.CONFIG.write_text('{}')
        app.initialize()
        with app.connect() as con:
            con.execute("INSERT INTO despesas(data,descricao,valor,categoria) VALUES('2026-09-15','Registro anterior',500,'Outros')")
        app.SESSIONS['batch-test'] = time.time() + 600
        files = []
        for i, color in enumerate(['red', 'blue', 'green']):
            file = Path(folder) / f'nota{i}.png'
            Image.new('RGB', (500, 500), color).save(file)
            files.append(str(file))
        server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with patch.object(app, 'read_receipt', return_value={'valor': 1234, 'descricao': 'Alimentos', 'mensagem': 'Confira os dados.'}), sync_playwright() as p:
                browser = p.chromium.launch(channel='msedge', headless=True)
                page = browser.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                url = f'http://127.0.0.1:{server.server_port}'
                page.context.add_cookies([{'name': 'session', 'value': 'batch-test', 'url': url}])
                page.goto(url)
                page.locator('#tabExpenses').click()
                page.locator('#batchFiles').set_input_files(files[:2])
                expect(page.locator('#batchStatus')).to_contain_text('Leitura concluída')
                for index, day in enumerate(['2026-09-20', '2026-09-01']):
                    row = page.locator('#batchRows tr').nth(index)
                    expect(row.locator('select')).to_have_value('Alimentação')
                    row.locator('input[type=date]').fill(day)
                    row.get_by_role('button', name='Salvar nota').click()
                    expect(row).to_contain_text('Salva')
                expect(page.locator('#expenseRows tr')).to_have_count(3)
                expect(page.locator('#expenseRows tr').first).to_contain_text('01/09/2026')
                page.locator('#expenseRows tr').first.get_by_role('button', name='Editar', exact=True).click()
                page.locator('#editExpenseDescription').fill('Almoço comunitário')
                page.locator('#editCategoryLabel select').select_option('Outros')
                page.locator('#saveExpenseEdit').click()
                expect(page.locator('#expenseRows tr').first).to_contain_text('Almoço comunitário')
                expect(page.locator('#expenseRows tr').first).to_contain_text('Outros')
                page.locator('#batchFiles').set_input_files(files[2])
                expect(page.locator('#batchRows tr')).to_have_count(3)
                expect(page.locator('#batchStatus')).to_contain_text('Leitura concluída')
                row = page.locator('#batchRows tr').last
                row.locator('input[type=date]').fill('2026-09-25')
                row.get_by_role('button', name='Salvar nota').click()
                expect(page.locator('#expenseRows tr')).to_have_count(4)
                page.reload()
                page.locator('#tabExpenses').click()
                page.locator('#expenseMonth').fill('2026-09')
                page.locator('#expenseMonth').dispatch_event('change')
                expect(page.locator('#expenseRows tr')).to_have_count(4)
                expect(page.locator('#expenseRows')).to_contain_text('Almoço comunitário')
                assert not errors, errors
                browser.close()
                print('OK: lote, categorias, ordem cronologica, edicao e persistencia.')
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    main()
