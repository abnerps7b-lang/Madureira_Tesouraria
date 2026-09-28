# Financeiro da igreja

Sistema da Assembleia de Deus Ministério de Madureira, feito com Python 3.10 ou superior. A leitura de notas usa Pillow e Tesseract instalados neste computador.

## Iniciar

1. Instale o Python caso ainda não esteja disponível, marcando a opção de adicionar ao PATH.
2. Abra o terminal nesta pasta e execute `python Testes.py` (ou `py Testes.py`).
3. No primeiro uso, crie a senha do administrador no terminal. A digitação da senha fica oculta.
4. Abra http://localhost:8000 e entre com a senha criada.

Para acessar pelo celular ou outro computador na mesma rede Wi-Fi, use `http://IP-DO-COMPUTADOR:8000`. O programa mostra os IPs detectados ao iniciar. Você também pode executar `ipconfig` e procurar o endereço IPv4 do adaptador Wi-Fi/Ethernet conectado. Se o Windows solicitar, permita o Python no firewall apenas para redes privadas. Mantenha o computador ligado e o programa aberto.

## Uso

Clique em **Dizimistas** para cadastrar o código e o nome de cada pessoa. O código é único e pode ter até 30 letras, números, hífens ou sublinhados. Zeros iniciais são mantidos: `001` é diferente de `1`. Letras são convertidas para maiúsculas. A lista permite buscar pelo código ou nome.

Em **Nova entrada**, selecione dízimo e digite o código cadastrado: o nome será carregado automaticamente. Informe a data, o valor e o pagamento, depois salve. Para ofertas, o nome continua opcional. Digite valores como `150,50`, sem separador de milhares. O código também aparece no histórico e no CSV. Registros anteriores ao cadastro são preservados, sem vínculo automático por nome.

Clique em **Cadastrar ofertas** para guardar nomes como “Culto de oração e ensino”, “Santa Ceia” ou “Oferta do mês”. Em **Nova entrada → Oferta**, selecione o nome cadastrado e informe data, valor e, se houver, o nome do ofertante. O mesmo nome de oferta pode ser usado em vários lançamentos e meses. Ofertas avulsas continuam disponíveis.

O sistema abre na aba **Principal**, no mês atual. Ela mostra saldo, entradas, totais e médias de dízimos e ofertas por lançamento, evolução dos últimos seis meses e participação de cada tipo nas entradas. Selecione outro mês para consultar os indicadores. Meses sem lançamentos não têm média e aparecem com “—”.

Na aba **Lançamentos de entrada**, informe o **primeiro mês** e o **saldo inicial** uma única vez (use sinal negativo se necessário). Depois de salvar, esse cadastro fica travado. O card de consulta do saldo anterior permanece na aba **Principal**. O saldo anterior de cada mês será o saldo final do mês anterior, incluindo os meses sem movimento. Lançamentos retroativos e mudanças nas despesas recalculam os saldos seguintes. O mês inicial deve incluir todo o histórico já registrado; não é possível lançar entradas anteriores a ele. Os dados antigos são mantidos, mas os antigos saldos manuais de fechamento são substituídos no cálculo pela nova sequência automática. É necessário configurar o saldo inicial para gerar relatórios.

Na aba **Lançamentos de entrada**, use o filtro por **mês** e tipo para consultar os registros. **Exportar CSV** gera uma planilha com os registros e totais conforme o filtro aplicado.

Em **Fechamento mensal / PDF**, selecione o mês. O total das despesas é calculado pelos lançamentos. O saldo anterior é automático e não pode ser alterado nessa tela. Use **Lançamentos de despesas → Nova despesa** para informar data, descrição livre e valor. Cada registro é avulso, sem recorrência automática. A aba permite filtrar por mês e imprimir um relatório A4 com cabeçalho XA / CRÉDITO e total mensal. Os saldos do painel e dos meses seguintes são atualizados automaticamente. Totais manuais dos fechamentos anteriores foram preservados como despesas identificadas como migradas; não os lance novamente. Clique em **Salvar e visualizar relatório**. O documento inclui todas as entradas daquele mês, independentemente do filtro de tipo do painel, em ordem de data, com dízimos e ofertas separados e ofertas em vermelho. O resumo calcula saldo anterior + dízimos + ofertas − despesas. Alterações nos lançamentos são refletidas ao gerar o relatório novamente.

Na página do relatório, clique em **Imprimir / Salvar PDF**. Use papel A4, orientação retrato e desative os cabeçalhos e rodapés do navegador. Relatórios longos continuam em outras páginas com repetição dos títulos das colunas.

## Notas anexadas às despesas

### Ativar a análise por IA

Abra **Configurar IA.cmd** nesta pasta e informe a chave da sua conta da API OpenAI no terminal. A digitação fica oculta. A chave é salva na variável `OPENAI_API_KEY` do usuário do Windows, nunca no código, banco de dados ou navegador. Não envie sua chave pelo chat. Depois atualize a página; a tela de nova despesa informa se a IA está configurada.

A integração usa a API Responses com `gpt-5.4`, imagem em resolução original e saída estruturada. Cada nova análise por IA faz duas leituras independentes, cobradas pela conta da API, e envia a foto ao serviço da OpenAI. A chave exige acesso ao modelo e saldo/limites disponíveis. O sistema compara as leituras e confere subtotal, descontos, acréscimos, pagamento, troco e soma dos itens quando esses dados forem legíveis. Divergências impedem o preenchimento automático do total. Isso reduz erros, mas não garante exatidão: confira a foto antes de salvar.

As requisições usam `store: false`. A foto original e a análise permanecem no banco local. Se não houver chave ou a API falhar, o sistema avisa e usa o OCR local; não apresenta esse resultado como análise de IA. **Ler nota novamente** refaz a análise e pode gerar nova cobrança. Notas ainda não vinculadas, antes lidas por OCR, são reanalisadas por IA ao serem enviadas após a ativação.

Referências oficiais: [entrada de imagens](https://developers.openai.com/api/docs/guides/images-vision), [saída estruturada](https://developers.openai.com/api/docs/guides/structured-outputs), [modelo configurado](https://developers.openai.com/api/docs/models/gpt-5.4).

Em **Lançamentos de despesas → Nova despesa**, anexe uma foto JPG, PNG ou WebP de até 8 MB e 24 megapixels. O anexo é obrigatório para novos lançamentos. Os registros antigos permanecem disponíveis sem anexo.

O sistema sugere o total e uma descrição baseada nos produtos reconhecidos, como Alimentos, Material de limpeza, Material de construção, Combustível ou Material de escritório. Confira os dados antes de salvar: fotos borradas, abreviações ou formatos diferentes podem impedir a leitura correta. Se o total não for identificado, preencha manualmente; a nota continua anexada. Campos que você já preencheu não são substituídos. A data é informada manualmente.

A descrição permanece livre para complementar. Na lista, **Ver nota anexada** abre a imagem original, com acesso restrito à sessão autenticada. Uma foto já vinculada não pode ser usada em outra despesa. As imagens ficam dentro de `financeiro.sqlite3`, junto dos demais dados, e são incluídas nas cópias desse banco. Fotos enviadas e ainda não vinculadas também ficam armazenadas.

Para preparar outro computador: execute `python -m pip install -r requirements.txt`, instale o [Tesseract para Windows](https://tesseract-ocr.github.io/tessdoc/Installation.html) e mantenha o arquivo `tessdata/por.traineddata` do projeto. A ferramenta de OCR não envia notas a serviços externos.

## Logotipo da igreja

Salve o logotipo original como `logo.png` nesta mesma pasta. O sistema exibirá a imagem na tela de acesso, na identificação da igreja e no relatório mensal, preservando suas proporções. Basta atualizar a página depois de salvar o arquivo.

## Publicação na Vercel

Consulte [VERCEL.md](VERCEL.md) para conectar PostgreSQL, configurar as variáveis, publicar e importar os registros locais. Na Vercel, dados e sessões ficam no PostgreSQL; não há SQLite temporário. O banco remoto começa vazio até a importação. A leitura automática das notas usa a API; sem chave, os dados são preenchidos manualmente.

## Armazenamento local

Na aba **Lançamentos de despesas**, a seção **Adicionar notas em lote** permite selecionar várias fotos. Aguarde a leitura, informe a data, confira os valores e clique em **Salvar nota** em cada linha. Falhas em uma foto não interrompem as demais; a linha informa como tentar novamente. Linhas ainda não salvas devem ser conferidas antes de atualizar ou fechar a página.

A tabela mensal mostra **Data, Descrição, Categoria e Valor**, da data mais antiga para a mais recente. Novas notas são acrescentadas às despesas já salvas. Use o filtro de mês para consultar outros períodos. O botão **Editar** permite mudar a descrição e a categoria sem alterar o valor ou a nota anexada.

Categorias disponíveis: Alimentação, Vestuário, Produtos de Limpeza, Energia, Água, Transporte, Saúde, Lazer e Outros. A sugestão considera a descrição identificada na nota; casos sem correspondência clara ou mistos recebem Outros. A classificação é uma sugestão e pode ser corrigida antes ou depois de salvar. Ajustes manuais ficam gravados no banco e são preservados ao reiniciar.

Os registros ficam em `financeiro.sqlite3`, na mesma pasta. A configuração de senha fica em `acesso.json`, contendo apenas sal e hash da senha. Com o programa encerrado, faça cópias periódicas dos dois arquivos para um local protegido. O sistema usa uma única conta administrativa, com sessão de oito horas; entradas e despesas podem ser excluídas pelo botão Excluir em cada linha, após confirmação. A exclusão é definitiva e recalcula os totais e saldos dos meses seguintes. Cadastros e notas anexadas são preservados.

Esta versão atende à rede local de confiança por HTTP. Para disponibilizar na internet, use hospedagem com HTTPS e configuração de acesso adequada; não exponha diretamente a porta 8000 no roteador. Os dados financeiros e nomes dos contribuintes devem ficar acessíveis apenas às pessoas autorizadas.
