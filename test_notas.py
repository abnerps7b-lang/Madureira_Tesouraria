import unittest
from notas import extract_receipt, validate_image


class ReceiptTest(unittest.TestCase):
    def test_total_and_items(self):
        result = extract_receipt('ARROZ 1 25,00\nLEITE 2 15,00\nSUBTOTAL 50,00\nDESCONTO 10,00\nTOTAL A PAGAR R$ 40,00\nDINHEIRO 100,00\nTROCO 60,00')
        self.assertEqual(result['valor'], 4000)
        self.assertEqual(result['descricao'], 'Alimentos')

    def test_ambiguous_or_missing_total(self):
        self.assertIsNone(extract_receipt('TOTAL 10,00\nTOTAL 20,00')['valor'])
        self.assertIsNone(extract_receipt('SUBTOTAL 99,00\nTOTAL DE TRIBUTOS 10,00\nTOTAL ITENS 2,00')['valor'])
        self.assertEqual(extract_receipt('VALOR TOTAL\nR$ 1.234,56')['valor'], 123456)

    def test_mixed_categories(self):
        self.assertEqual(extract_receipt('ARROZ 25,00\nDETERGENTE 3,50')['descricao'], 'Alimentos / Material de limpeza')

    def test_total_confirmed_by_discount_and_payment(self):
        result = extract_receipt('Total bruto de itens 182,43\nTotal E descontos/acréscimos sobre item 1,00\nTOTAL R 191,43\nCartão de Débito 181.43')
        self.assertEqual(result['valor'], 18143)
        self.assertTrue(result['conferido'])
        self.assertIsNone(extract_receipt('TOTAL 161,43\nCartão de Débito 181,43')['valor'])

    def test_invalid_photo(self):
        with self.assertRaises(ValueError):
            validate_image('PHNjcmlwdD4=')


if __name__ == '__main__':
    unittest.main()
