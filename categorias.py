"""Categorias consistentes, com Outros para descrições ambíguas ou mistas."""
import re
import unicodedata

CATEGORIES = ['Alimentação', 'Vestuário', 'Produtos de Limpeza', 'Energia', 'Água',
              'Transporte', 'Saúde', 'Lazer', 'Outros']
KEYWORDS = [
    'alimentacao alimentos alimento arroz feijao leite carne pao refeicao restaurante cafe',
    'vestuario roupa roupas camisa calca vestido sapato uniforme',
    'limpeza detergente desinfetante sabao vassoura alvejante',
    'energia eletricidade eletrica luz',
    'esgoto saneamento',
    'transporte combustivel gasolina diesel etanol onibus taxi uber pedagio passagem',
    'saude medicamento medicamentos farmacia consulta hospital exame remedio',
    'lazer cinema passeio recreacao brinquedo ingresso',
]


def categorize(description):
    if '/' in description:
        categories = {categorize(part) for part in description.split('/')}
        return categories.pop() if len(categories) == 1 else 'Outros'
    text = ''.join(c for c in unicodedata.normalize('NFKD', description.lower()) if not unicodedata.combining(c))
    words = set(re.findall(r'[a-z]+', text))
    if 'agua' in words and not words.intersection({'sanitaria', 'mineral', 'coco'}):
        words.add('saneamento')
    if 'agua sanitaria' in text:
        words.add('limpeza')
    if 'agua mineral' in text or 'agua de coco' in text:
        words.add('alimentos')
    matches = [CATEGORIES[i] for i, terms in enumerate(KEYWORDS) if words.intersection(terms.split())]
    return matches[0] if len(matches) == 1 else 'Outros'
