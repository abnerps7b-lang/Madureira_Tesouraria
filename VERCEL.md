# Publicar na Vercel

O aplicativo usa PostgreSQL quando DATABASE_URL ou POSTGRES_URL está configurada, ou quando roda na Vercel. Sem conexão configurada, retorna uma mensagem de configuração; nunca cria um SQLite temporário na nuvem. Localmente, sem essas variáveis, continua usando financeiro.sqlite3.

## 1. Banco persistente

No projeto da Vercel, abra Storage / Marketplace, crie um PostgreSQL (por exemplo Neon) e conecte ao projeto. Configure a conexão fornecida pelo provedor como **DATABASE_URL** ou **POSTGRES_URL**, em Production. Prefira a conexão com pooling e TLS fornecida pelo provedor. Não publique a URL no GitHub nem a envie por mensagens.

As tabelas são criadas na primeira conexão, com proteção contra inicializações simultâneas. Entradas, despesas, cadastros, notas anexadas, sessões e limites de login ficam no PostgreSQL. Um banco recém-criado começa vazio.

## 2. Variáveis de ambiente

Em Settings → Environment Variables:

| Nome | Valor |
| --- | --- |
| DATABASE_URL | Conexão PostgreSQL fornecida pela integração; POSTGRES_URL também é aceita |
| ADMIN_PASSWORD | Sua senha de acesso, com pelo menos 12 caracteres |
| OPENAI_API_KEY | Opcional: sua chave para análise das fotos por IA |

Use bancos separados para Production e Preview se habilitar ambos. Nunca use o banco de produção para testes automatizados. Alterações nas variáveis exigem novo deploy. Não é necessário enviar acesso.json. Trocar ADMIN_PASSWORD invalida as sessões anteriores no novo deploy; Sair revoga a sessão no banco.

## 3. Deploy

Envie as alterações ao GitHub. Na Vercel: raiz `./`, preset Python, Build Command e Output Directory padrão. As dependências e Python 3.12 estão definidos em pyproject.toml. Deixe o Install Command padrão para a Vercel usar uv. O ponto de entrada é Testes:Handler; vercel.json define até 300 segundos para processamento das notas. O processamento continua limitado à duração da requisição e não é uma fila em segundo plano.

Não envie financeiro.sqlite3, acesso.json ou arquivos .env: .gitignore e .vercelignore os excluem.

## 4. Trazer os registros locais

O deploy não copia os registros locais automaticamente. Antes de lançar dados na nuvem, instale requirements.txt localmente e configure DATABASE_URL apenas no ambiente do terminal, com a conexão do banco de destino. Faça uma cópia de segurança do SQLite.

Execute `python migrar_para_postgres.py` para conferir quantidades e confirmar que o destino está vazio. Depois execute `python migrar_para_postgres.py --aplicar` para importar. A origem é aberta somente para leitura e copiada de forma consistente; a gravação no destino é transacional. Uma falha desfaz a importação. Cadastros, valores, datas, saldo inicial e fotos são preservados. A senha é a configurada em ADMIN_PASSWORD; sessões locais não são importadas.

O importador recusa um destino que já tenha registros financeiros. Não apague dados da nuvem para contornar essa proteção. Arquivos de fotos grandes importados podem exigir download por ferramenta de banco devido ao limite de resposta da Vercel.

## 5. Conferência após publicar

Entre, navegue entre as abas, registre um lançamento de conferência e verifique se permanece após sair e entrar. Confira totais e meses posteriores. Verifique anexos, relatório para impressão e exclusão antes de usar o sistema para o fechamento real.

A leitura automática online usa OPENAI_API_KEY; Tesseract não é instalado na Vercel. Sem chave ou se a IA falhar, o anexo é salvo para preenchimento manual. Fotos de até 8 MB são aceitas no seletor; acima de 3 MB são reduzidas no navegador antes do envio e a versão compactada fica anexada. Cada foto é enviada separadamente, inclusive no lote. Mantenha a página aberta até conferir e salvar os resultados.

## Diagnóstico

- Banco não configurado: confira DATABASE_URL/POSTGRES_URL no ambiente do deploy e publique novamente.
- Login não configurado: confira ADMIN_PASSWORD (12 caracteres ou mais).
- Falha de conexão: confira a integração, disponibilidade, TLS e credenciais do PostgreSQL.
- Resposta inválida: confira os Runtime Logs da Vercel; não publique segredos junto dos logs.

Documentação: https://vercel.com/docs/marketplace-storage e https://vercel.com/docs/functions/limitations
