import copy
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import notas_ia as ai


def receipt():
    return dict(legivel=True, moeda='BRL', total=18143, subtotal=18243, desconto=100,
                acrescimo=0, pagamento=18143, troco=0, confianca_total='alta',
                evidencia_total='TOTAL R$ 181,43', categorias=['Alimentos', 'Higiene pessoal'],
                itens=[{'descricao':'Produtos alimentícios e higiene','total':18243}],
                itens_completos=True, observacoes='')


class VisionTest(unittest.TestCase):
    def test_independent_agreement(self):
        with patch.object(ai, 'extract', side_effect=[receipt(), receipt()]) as read:
            result = ai.analyze(b'photo', 'image/png')
        self.assertEqual(read.call_count, 2)
        self.assertEqual(result['valor'], 18143)
        self.assertEqual(result['descricao'], 'Alimentos / Higiene pessoal')
        self.assertTrue(result['conferido'])

    def test_disagreement_and_calculation_fail_closed(self):
        for changed in [dict(total=18144), dict(subtotal=20000), dict(pagamento=18200),
                        dict(confianca_total='baixa'), dict(moeda='outra'), dict(evidencia_total='TOTAL 191,43')]:
            second = dict(receipt(), **changed)
            with patch.object(ai, 'extract', side_effect=[receipt(), second]):
                self.assertIsNone(ai.analyze(b'photo', 'image/png')['valor'])

    def test_category_disagreement(self):
        second = dict(receipt(), categorias=['Alimentos'])
        with patch.object(ai, 'extract', side_effect=[receipt(), second]):
            result=ai.analyze(b'photo', 'image/png')
        self.assertEqual(result['descricao'], 'Alimentos')
        self.assertIn('Revise a descrição', result['mensagem'])

    def test_responses_api_contract(self):
        response={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(receipt())}]}]}
        with patch.object(ai,'api_key',return_value='test-only-key'), patch.object(ai,'urlopen',return_value=io.BytesIO(json.dumps(response).encode())) as call:
            result=ai.extract(b'photo','image/png')
        payload=json.loads(call.call_args.args[0].data)
        self.assertFalse(payload['store'])
        self.assertTrue(payload['text']['format']['strict'])
        self.assertEqual(payload['input'][0]['content'][1]['detail'],'original')
        self.assertEqual(result['total'],18143)

    def test_api_failure_and_invalid_output(self):
        with patch.object(ai,'api_key',return_value='test-only-key'), patch.object(ai,'urlopen',side_effect=HTTPError('url',429,'limit',{},None)):
            with self.assertRaisesRegex(RuntimeError,'limite'):
                ai.extract(b'photo','image/png')
        malformed=copy.deepcopy(receipt());malformed['total']='18143'
        with self.assertRaises(ValueError):
            ai.validate(malformed)


if __name__=='__main__':
    unittest.main()
