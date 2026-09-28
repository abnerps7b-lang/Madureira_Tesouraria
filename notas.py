"""Leitura local de comprovantes. Sugestões sempre precisam de conferência."""
import base64
import binascii
import hashlib
import io
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import unicodedata
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

OCR_SLOTS = threading.BoundedSemaphore(2)
MAX_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 24000000


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.upper()) if not unicodedata.combining(c))


def extract_receipt(text):
    lines = [normalize(line).strip() for line in text.splitlines() if line.strip()]
    candidates = []
    for index, line in enumerate(lines):
        if re.search(r'SUBTOTAL|SUB TOTAL|TRIBUT|IMPOST|ITENS|ITEM|QUANT|TROCO|DESCONT|ACRESC', line):
            continue
        rank = 3 if re.search(r'(TOTAL|VALOR)\s+A\s+PAGAR', line) else 2 if 'VALOR TOTAL' in line else 1 if re.search(r'\bTOTAL\b', line) else 0
        if not rank:
            continue
        values = re.findall(r'(?<![\d.,])(?:\d{1,3}(?:\.\d{3})+|\d+)[,.]\d{2}(?!\d)', line)
        if not values and index + 1 < len(lines) and re.fullmatch(r'(?:R\$\s*)?[\d., ]+', lines[index + 1]):
            values = re.findall(r'(?:\d{1,3}(?:\.\d{3})+|\d+)[,.]\d{2}', lines[index + 1])
        if len(values) == 1:
            value = values[0]
            digits = value.replace('.', '').replace(',', '') if ',' in value else value.replace('.', '')
            cents = int(digits)
            if 0 < cents <= 999999999:
                candidates.append((rank, cents))
    best = max((rank for rank, _ in candidates), default=0)
    totals = {value for rank, value in candidates if rank == best}
    total = next(iter(totals)) if len(totals) == 1 else None
    def line_amounts(pattern):
        values = []
        for line in lines:
            if re.search(pattern, line):
                matches = re.findall(r'(?<![\d.,])(?:\d{1,3}(?:\.\d{3})+|\d+)[,.]\s*\d{2}(?!\d)', line)
                if len(matches) == 1:
                    values.append(int(re.sub(r'\D', '', matches[0])))
        return values
    gross = line_amounts(r'TOTAL BRUTO|SUB\s*TOTAL')
    discounts = line_amounts(r'(?:TOTAL|JOTAL|LOTA.) (?:DE|E) DESCONT')
    payments = line_amounts(r'CART[AÃ]O DE (?:DEBITO|CREDITO)|\bPIX\b')
    corroborated = len(gross) == len(discounts) == len(payments) == 1 and gross[0] - discounts[0] == payments[0] and payments[0] > 0
    if corroborated:
        total = payments[0]
    elif total is not None and len(payments) == 1 and payments[0] != total:
        total = None
    # Não classificar usando propaganda ou o nome do estabelecimento no cabeçalho.
    item_lines = [line for line in lines if re.search(r'\d', line) and not re.search(r'TOTAL|CNPJ|CPF|TRIBUT|TROCO|PAGAMENTO|CHAVE|CONSUMIDOR', line)]
    items = '\n'.join(item_lines)
    categories = {
        'Vestuário': ['CAMISA', 'CALCA', 'VESTIDO', 'SAPATO', 'UNIFORME', 'ROUPA'],
        'Saúde': ['MEDICAMENTO', 'MEDICAMENTOS', 'CONSULTA', 'EXAME', 'REMÉDIO'],
        'Lazer': ['CINEMA', 'PASSEIO', 'RECREACAO', 'BRINQUEDO'],
        'Energia': ['ENERGIA ELETRICA', 'CONSUMO KWH'],
        'Água': ['AGUA E ESGOTO', 'SANEAMENTO'],
        'Transporte': ['PASSAGEM', 'PEDAGIO', 'TAXI', 'UBER'],
        'Alimentos': ['ARROZ', 'FEIJAO', 'ACUCAR', 'CAFE', 'LEITE', 'PAO', 'PAES', 'CARNE', 'FRANGO', 'BISCOITO', 'MACARRAO', 'FARINHA', 'BANANA', 'TOMATE', 'OVOS', 'MANTEIGA', 'QUEIJO', 'SUCO', 'REFRIGERANTE', 'ALIMENTOS', 'BISC', 'TAPIOCA', 'PATE', 'AMENDOIM', 'MUCAR ELA', 'MUSSARELA'],
        'Higiene pessoal': ['SABUN', 'SABONETE', 'CR DENT', 'DESODORANTE', 'DEO AER'],
        'Material de limpeza': ['DETERGENTE', 'SABAO', 'DESINFETANTE', 'ALVEJANTE', 'VASSOURA', 'ESPONJA', 'AGUA SANITARIA', 'LIMPADOR'],
        'Material de construção': ['CIMENTO', 'ARGAMASSA', 'TIJOLO', 'TINTA', 'PARAFUSO', 'AREIA', 'CANO', 'TELHA'],
        'Combustível': ['GASOLINA', 'ETANOL', 'DIESEL'],
        'Material de escritório': ['CANETA', 'PAPEL A4', 'TONER', 'CARTUCHO', 'GRAMPEADOR'],
    }
    found = [label for label, words in categories.items() if any(re.search(r'\b' + word + r'\b', items) for word in words)]
    description = ' / '.join(found) if found else 'Despesa conforme nota fiscal'
    return {'valor': total, 'descricao': description,
            'conferido': corroborated,
            'mensagem': 'Confira o total e a descrição sugeridos antes de salvar.' if total is not None else 'Não foi possível identificar um total único. Digite o valor e confira a descrição.'}


def validate_image(encoded):
    if not isinstance(encoded, str) or len(encoded) > (MAX_BYTES * 4 // 3 + 8):
        raise ValueError('Envie uma foto de até 8 MB.')
    try:
        raw = base64.b64decode(encoded, validate=True)
        if not raw or len(raw) > MAX_BYTES:
            raise ValueError('Envie uma foto de até 8 MB.')
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in ('JPEG', 'PNG', 'WEBP') or image.width * image.height > MAX_PIXELS:
                    raise ValueError('Use uma foto JPG, PNG ou WebP de até 24 megapixels.')
                mime = Image.MIME[image.format]
                image.verify()
    except (binascii.Error, UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValueError('A foto está inválida. Envie um arquivo JPG, PNG ou WebP.') from error
    return raw, mime, hashlib.sha256(raw).hexdigest()


def read_receipt_local(raw):
    executable = shutil.which('tesseract') or r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    text, error = '', ''
    if not Path(executable).is_file():
        error = 'Leitura automática indisponível neste computador. A nota foi anexada; preencha os campos manualmente.'
    elif not OCR_SLOTS.acquire(blocking=False):
        error = 'Leitor ocupado. A nota foi anexada; preencha os campos manualmente.'
    else:
        try:
            with tempfile.TemporaryDirectory(prefix='nota-ocr-') as directory:
                path = Path(directory) / 'leitura.png'
                with Image.open(io.BytesIO(raw)) as original:
                    # Cópia temporária para OCR; o anexo original fica intacto.
                    image = ImageOps.exif_transpose(original).convert('RGB')
                    image.thumbnail((2800, 4000))
                    image.save(path)
                language_path = Path(__file__).parent / 'tessdata'
                language_args = ['--tessdata-dir', str(language_path), '-l', 'por'] if (language_path / 'por.traineddata').exists() else ['-l', 'eng']
                def run_ocr(mode):
                    result = subprocess.run([executable, str(path), 'stdout', *language_args, '--psm', str(mode)],
                                            capture_output=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    if result.returncode:
                        raise RuntimeError('OCR failed')
                    return result.stdout.decode('utf-8', errors='replace')[:30000]
                text = run_ocr(6)
                if extract_receipt(text)['valor'] is None:
                    # Localiza a faixa clara de papel, evitando ler o fundo da foto.
                    sample = image.convert('L').resize((120, 160))
                    columns = [sum(sample.getpixel((x,y)) > 150 for y in range(16,136))/120 for x in range(120)]
                    runs, start = [], None
                    for x, value in enumerate(columns + [0]):
                        if value > .6 and start is None:
                            start = x
                        if value <= .6 and start is not None:
                            runs.append((start, x)); start = None
                    if runs:
                        left, right = max(runs, key=lambda pair: pair[1]-pair[0])
                        if 25 <= right-left <= 105:
                            image = image.crop((max(0,int(left/120*image.width)-12),0,min(image.width,int(right/120*image.width)+12),image.height))
                    image = ImageOps.autocontrast(image.convert('L'))
                    scale = min(2, 4000 / max(image.size))
                    image = image.resize((int(image.width*scale), int(image.height*scale)))
                    image.save(path)
                    improved = run_ocr(3)
                    if extract_receipt(improved)['valor'] is not None or len(improved) > len(text):
                        text = improved
        except (OSError, subprocess.TimeoutExpired, RuntimeError):
            error = 'Não foi possível ler a foto. A nota foi anexada; confira a imagem e preencha os campos manualmente.'
        finally:
            OCR_SLOTS.release()
    suggestion = extract_receipt(text)
    if error:
        suggestion['mensagem'] = error
    suggestion['texto'] = text
    suggestion['versao'] = 2
    return suggestion


def read_receipt(raw):
    from notas_ia import api_key, analyze
    if api_key():
        try:
            with Image.open(io.BytesIO(raw)) as image:
                mime = Image.MIME[image.format]
            return analyze(raw, mime)
        except (RuntimeError, ValueError, OSError) as error:
            message = 'A análise por IA não foi concluída: ' + str(error)
    else:
        message = 'IA não ativada: configure sua chave no computador do sistema. Foi usada apenas a leitura local.'
    local = read_receipt_local(raw)
    local.update(fonte='ocr', versao=3, mensagem=message + ' ' + local['mensagem'])
    return local
