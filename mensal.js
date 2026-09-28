// Cadastros de ofertas e fechamento mensal.
const offersButton = document.createElement('button');
offersButton.className = 'secondary';
offersButton.textContent = 'Cadastrar ofertas';
$('members').after(offersButton);
document.querySelector('header .actions').style.flexWrap = 'wrap';
$('print').textContent = 'Fechamento mensal / PDF';

document.body.insertAdjacentHTML('beforeend', `
<dialog id="offersDialog">
  <h2>Nomes das ofertas</h2>
  <p>Cadastre, por exemplo, Culto de oração e ensino, Santa Ceia ou Oferta do mês.</p>
  <form id="offerForm">
    <label style="margin-top:20px">Nome da oferta
      <input id="offerName" maxlength="120" required placeholder="Ex.: Culto evangelístico">
    </label>
    <p id="offerError" class="error" role="alert"></p>
    <div class="formactions"><button type="button" class="secondary" id="closeOffers">Fechar</button><button id="saveOffer">Cadastrar oferta</button></div>
  </form>
  <div class="tablewrap" style="max-height:260px;margin-top:20px"><table><thead><tr><th>Ofertas cadastradas</th></tr></thead><tbody id="offerRows"></tbody></table></div>
</dialog>
<dialog id="closingDialog">
  <h2>Fechamento mensal</h2>
  <p>Gere o relatório completo de dízimos e ofertas, no modelo de impressão da tesouraria.</p>
  <form id="closingForm">
    <div class="formgrid">
      <label class="wide">Mês do relatório<input id="closingMonth" type="month" required></label>
      <label>Saldo anterior automático (R$)<input id="openingBalance" readonly placeholder="Configure na aba Lançamentos de entrada"></label>
      <label>Despesas do mês (R$)<input id="monthExpenses" readonly placeholder="0,00"></label>
    </div>
    <p style="font-size:12px">O saldo anterior e as despesas são automáticos. Registre as despesas na aba Lançamentos de despesas.</p>
    <p id="closingError" class="error" role="alert"></p>
    <div class="formactions"><button type="button" class="secondary" id="closeClosing">Cancelar</button><button id="generateReport">Salvar e visualizar relatório</button></div>
  </form>
</dialog>`);

$('personLabel').insertAdjacentHTML('beforebegin', `
<label class="wide" id="offerLabel" hidden>Nome da oferta
  <select id="offerSelect"><option value="">Oferta avulsa / sem categoria</option></select>
  <span>Cadastre os nomes pelo botão “Cadastrar ofertas” na tela principal.</span>
</label>`);

async function loadOffers() {
  const offers = await api('/api/ofertas');
  const selected = $('offerSelect').value;
  $('offerSelect').replaceChildren(new Option('Oferta avulsa / sem categoria', ''));
  $('offerRows').replaceChildren();
  for (const offer of offers) {
    $('offerSelect').add(new Option(offer.nome, String(offer.id)));
    const tr = document.createElement('tr'), td = document.createElement('td');
    td.textContent = offer.nome;
    td.style.textAlign = 'left';
    tr.append(td);
    $('offerRows').append(tr);
  }
  $('offerSelect').value = selected;
  if (!offers.length) {
    const tr = document.createElement('tr'), td = document.createElement('td');
    td.className = 'empty'; td.textContent = 'Nenhuma oferta cadastrada.';
    tr.append(td); $('offerRows').append(tr);
  }
}
const previousResetContributor = resetContributor;
resetContributor = function () {
  previousResetContributor();
  $('offerLabel').hidden = $('tipo').value !== 'oferta';
  $('offerSelect').value = '';
};
$('tipo').onchange = resetContributor;
const previousNewEntry = $('new').onclick;
$('new').onclick = async () => {
  previousNewEntry();
  $('save').disabled = true;
  try { await loadOffers(); }
  catch (e) { $('entryError').textContent = e.message; }
  finally { $('save').disabled = false; }
};
offersButton.onclick = async () => {
  $('offerForm').reset(); $('offerError').textContent = '';
  $('offersDialog').showModal();
  try { await loadOffers(); } catch (e) { $('offerError').textContent = e.message; }
};
$('closeOffers').onclick = () => $('offersDialog').close();
$('offerForm').onsubmit = async e => {
  e.preventDefault(); $('saveOffer').disabled = true; $('offerError').textContent = '';
  try {
    await api('/api/ofertas', {nome: $('offerName').value});
    $('offerForm').reset(); await loadOffers();
    toast('Nome da oferta cadastrado.'); $('offerName').focus();
  } catch (e) { $('offerError').textContent = e.message; }
  finally { $('saveOffer').disabled = false; }
};

let closingRequest = 0;
async function loadClosing() {
  const request = ++closingRequest;
  $('generateReport').disabled = true;
  $('openingBalance').disabled = $('monthExpenses').disabled = true;
  $('openingBalance').value = $('monthExpenses').value = '';
  $('closingError').textContent = 'Carregando valores do mês…';
  try {
    const data = await api('/api/fechamento?mes=' + encodeURIComponent($('closingMonth').value));
    if (request !== closingRequest) return;
    $('openingBalance').value = data.saldo_anterior === null ? '' : (data.saldo_anterior / 100).toFixed(2).replace('.', ',');
    $('monthExpenses').value = (data.despesas / 100).toFixed(2).replace('.', ',');
    $('closingError').textContent = data.saldo_anterior === null ? 'Configure o saldo inicial na aba Lançamentos de entrada e escolha um mês a partir do início do controle.' : '';
    $('generateReport').disabled = data.saldo_anterior === null;
    $('openingBalance').disabled = $('monthExpenses').disabled = false;
  } catch (e) { if (request === closingRequest) $('closingError').textContent = e.message; }
}
$('print').onclick = () => {
  $('closingMonth').value = $('inicio').value.slice(0, 7) || today().slice(0, 7);
  $('closingDialog').showModal(); loadClosing();
};
$('closingMonth').onchange = loadClosing;
$('closeClosing').onclick = () => $('closingDialog').close();
function cents(value) {
  const normalized = value.trim().replace(',', '.');
  if (!/^-?\d+(\.\d{1,2})?$/.test(normalized)) throw Error('Informe valores como 150,50, sem separador de milhares.');
  const parts = normalized.replace('-', '').split('.');
  return (normalized.startsWith('-') ? -1 : 1) * (Number(parts[0]) * 100 + Number((parts[1] || '').padEnd(2, '0')));
}
$('closingForm').onsubmit = async e => {
  e.preventDefault(); $('generateReport').disabled = true;
  const mes = $('closingMonth').value;
  $('closingMonth').disabled = true;
  try {
    await api('/api/fechamento', {mes});
    location.assign('/relatorio?mes=' + encodeURIComponent(mes));
  } catch (e) { $('closingError').textContent = e.message; }
  finally { $('generateReport').disabled = false; $('closingMonth').disabled = false; }
};
