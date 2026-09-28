import unittest
from categorias import categorize


class CategoryTests(unittest.TestCase):
    def test_categories_and_ambiguity(self):
        cases = {'Alimentos': 'Alimentação', 'Camisa e calça': 'Vestuário',
                 'Água sanitária': 'Produtos de Limpeza', 'Energia elétrica': 'Energia',
                 'Água e esgoto': 'Água', 'Combustível': 'Transporte',
                 'Medicamentos': 'Saúde', 'Cinema': 'Lazer', 'Material de construção': 'Outros',
                 'Alimentos / Material de limpeza': 'Outros',
                 'Alimentos / Higiene pessoal': 'Outros', 'Água mineral': 'Alimentação',
                 'Despesa conforme nota fiscal': 'Outros'}
        for description, category in cases.items():
            with self.subTest(description=description):
                self.assertEqual(categorize(description), category)
