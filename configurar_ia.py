"""Configuração local: não registra nem exibe a chave."""
import getpass
import json
import winreg
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from notas_ia import MODEL


def main():
    print('Ativar leitura de notas por IA (OpenAI).')
    print('Crie sua chave em https://platform.openai.com/api-keys')
    print('As fotos serão enviadas à API. Cada análise faz duas leituras cobradas pela sua conta.')
    key = getpass.getpass('Cole a chave (não será exibida): ').strip()
    if not key:
        print('Configuração cancelada.'); return
    try:
        request = Request('https://api.openai.com/v1/models/' + MODEL, headers={'Authorization': 'Bearer ' + key})
        with urlopen(request, timeout=20) as response:
            json.load(response)
    except (HTTPError, URLError, TimeoutError):
        print('Não foi possível validar o acesso. Confira a chave, a internet e as permissões da conta.'); return
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, 'Environment') as registry:
        winreg.SetValueEx(registry, 'OPENAI_API_KEY', 0, winreg.REG_SZ, key)
    print('Chave configurada no usuário do Windows. Atualize a página do sistema.')
    print('A leitura real também depende de saldo e limites disponíveis na conta da API.')


if __name__ == '__main__':
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print('\nCancelado.')
    input('Pressione Enter para fechar...')
