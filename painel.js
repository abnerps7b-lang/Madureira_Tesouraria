// Navegação e indicadores mensais, sem serviços externos.
const main = document.querySelector('main');
const entriesView = document.createElement('section');
entriesView.id = 'entriesView';
for (const node of [...main.children]) {
  if (!['HEADER', 'FOOTER'].includes(node.tagName)) entriesView.append(node);
}
main.querySelector('footer').before(entriesView);
const dashboardView = document.createElement('section');
dashboardView.id = 'dashboardView';
dashboardView.innerHTML = `
<div class="dashboard-head"><div><div class="eyebrow">Visão geral</div><h2>O cuidado com cada contribuição.</h2><p>Acompanhe os resultados da tesouraria, mês a mês.</p></div><label class="month-choice">Mês de referência<input id="dashboardMonth" type="month" required></label></div>
<p id="dashboardError" class="dashboard-error" role="alert"></p>
<div id="dashboardContent">
<div class="dashboard-cards">
 <div class="card"><div class="metric-icon">↶</div><div class="label">Saldo anterior</div><div class="amount" id="dashboardOpening">—</div><div class="sub" id="balanceHelp"></div></div>
 <div class="card total"><div class="metric-icon">◈</div><div class="label">Saldo do mês</div><div class="amount" id="dashBalance">—</div><div class="sub">Saldo anterior + entradas − despesas</div></div>
 <div class="card"><div class="metric-icon">↗</div><div class="label">Entradas do mês</div><div class="amount" id="dashIncome">—</div><div class="sub" id="dashCount">Dízimos e ofertas recebidos</div></div>
 <div class="card"><div class="metric-icon">●</div><div class="label">Dízimos</div><div class="amount" id="dashTithes">—</div><div class="sub" id="dashTitheCount"></div></div>
 <div class="card"><div class="metric-icon" style="color:#c99432">◆</div><div class="label">Ofertas</div><div class="amount" id="dashOffers">—</div><div class="sub" id="dashOfferCount"></div></div>
</div>
<section class="panel average-line" style="margin-bottom:20px"><div><h3>Dizimistas do mês</h3><p>Pessoas que entregaram dízimo no mês selecionado, sem repetir o mesmo código.</p><p>Registros antigos sem código são identificados pelo nome.</p></div><strong id="monthlyContributors" style="font-size:32px;color:#167968">—</strong></section>

<div class="dashboard-grid"><section class="panel"><h3>Evolução das entradas</h3><p class="chart-subtitle">Seis meses até o período selecionado</p><div class="chart-legend"><span><i class="dot"></i>Dízimos</span><span><i class="dot gold"></i>Ofertas</span></div><div id="trendChart" class="trend-chart" aria-label="Entradas nos últimos seis meses"></div><p id="chartDetail" class="chart-detail">Selecione uma barra para consultar o valor.</p></section>
<section class="panel"><h3>Composição das entradas</h3><p class="chart-subtitle">Participação de cada contribuição no mês</p><div class="donut-wrap"><div id="incomeDonut" class="donut" role="img"><div class="donut-center"><strong id="donutCount">0</strong><span>lançamentos</span></div></div></div><div class="split-row"><span><i class="dot"></i>Dízimos</span><strong id="titheShare">—</strong></div><div class="split-row"><span><i class="dot gold"></i>Ofertas</span><strong id="offerShare">—</strong></div></section></div>
<div class="dashboard-average"><section class="panel average-line"><div><h3>Média de dízimos</h3><p>Valor médio por lançamento no mês</p></div><strong id="averageTithe">—</strong></section><section class="panel average-line"><div><h3>Média de ofertas</h3><p>Valor médio por lançamento no mês</p></div><strong id="averageOffer">—</strong></section></div>
<p class="chart-subtitle" id="expensesNote"></p>
</div>`;
entriesView.before(dashboardView);
const initialPanel=document.createElement("section");
initialPanel.className="panel";initialPanel.style.marginBottom="20px";
initialPanel.innerHTML=`<h3>Saldo inicial</h3><p id="entryBalanceHelp" class="chart-subtitle"></p> <form id="initialBalanceForm"><div class="balance-form"><label id="initialMonthLabel">Primeiro mês<input id="initialMonth" type="month" required></label><label>Saldo anterior (R$)<input id="initialBalance" inputmode="decimal" pattern="-?[0-9]+([.,][0-9]{1,2})?" placeholder="0,00" required></label><button id="saveInitial">Salvar saldo inicial</button></div><p id="balanceError" class="error" role="alert"></p></form>`;
entriesView.prepend(initialPanel);
document.querySelector('.sidebar .nav').innerHTML = '<button class="tab-button" id="tabDashboard" aria-selected="true"><span>▦</span>Principal</button><button class="tab-button" id="tabEntries" aria-selected="false"><span>↗</span>Lançamentos de entrada</button>';
document.querySelector('.sidebar .nav').setAttribute('aria-label', 'Abas do sistema');
document.querySelector('#filters').insertAdjacentHTML('afterbegin', '<label class="entry-month">Mês dos lançamentos<input id="entriesMonth" type="month" required></label>');
$('inicio').parentElement.hidden = true;
$('fim').parentElement.hidden = true;
let dashboardRequest = 0, activeTab = 'dashboard';
function monthLabel(mes) { return new Date(Number(mes.slice(0,4)), Number(mes.slice(5,7))-1, 1).toLocaleDateString('pt-BR', {month:'long',year:'numeric'}); }
function selectEntryMonth(mes) {
  $('entriesMonth').value = mes;
  $('inicio').value = mes + '-01';
  const last = new Date(Number(mes.slice(0,4)), Number(mes.slice(5,7)), 0).getDate();
  $('fim').value = mes + '-' + last;
}
selectEntryMonth(today().slice(0,7));
$('dashboardMonth').value = today().slice(0,7);
function selectTab(tab) {
  activeTab = tab;
  dashboardView.hidden = tab !== 'dashboard'; entriesView.hidden = tab !== 'entries';
  $('tabDashboard').setAttribute('aria-selected', String(tab === 'dashboard'));
  $('tabEntries').setAttribute('aria-selected', String(tab === 'entries'));
  main.querySelector('h1').textContent = tab === 'dashboard' ? 'Principal' : 'Lançamentos de entrada';
  if (!$('app').hidden) { if (tab === 'dashboard') loadDashboard(); else refresh(); }
}
$('tabDashboard').onclick = () => selectTab('dashboard');
$('tabEntries').onclick = () => selectTab('entries');
$('entriesMonth').onchange = () => { if ($('entriesMonth').value) {selectEntryMonth($('entriesMonth').value);refresh();} };
$('filters').onsubmit = e => {e.preventDefault();selectEntryMonth($('entriesMonth').value);refresh();};
const originalShow = show;
show = function(logged) { originalShow(logged); if (logged) selectTab('dashboard'); };
const originalRefresh = refresh;
refresh = async function() {
  $('entriesMonth').value = $('inicio').value.slice(0,7);
  await Promise.all([originalRefresh(),loadEntryBalance()]);
  if (activeTab === 'dashboard' && !$('app').hidden) await loadDashboard();
};
function renderCharts(data) {
  const total = data.entradas, count = data.dizimo.quantidade + data.oferta.quantidade;
  const pct = total ? data.dizimo.total / total * 100 : 0;
  $('incomeDonut').style.background = total ? `conic-gradient(#238f7b 0% ${pct}%,#e1b35d ${pct}% 100%)` : '#edf1f5';
  $('incomeDonut').setAttribute('aria-label', total ? `Dízimos ${pct.toFixed(1)}%, ofertas ${(100-pct).toFixed(1)}%` : 'Sem entradas no mês');
  $('donutCount').textContent = count;
  $('titheShare').textContent = total ? pct.toLocaleString('pt-BR',{maximumFractionDigits:1})+'%' : 'Sem entradas';
  $('offerShare').textContent = total ? (100-pct).toLocaleString('pt-BR',{maximumFractionDigits:1})+'%' : 'Sem entradas';
  const max = Math.max(1, ...data.historico.flatMap(r => [r.dizimo,r.oferta]));
  $('trendChart').replaceChildren();
  for (const row of data.historico) {
    const column = document.createElement('div');column.className='chart-month';
    const pair = document.createElement('div');pair.className='bar-pair';
    for (const [kind,label] of [['dizimo','Dízimos'],['oferta','Ofertas']]) {
      const bar = document.createElement('button');bar.type='button';bar.className='chart-bar'+(kind==='oferta'?' offer-bar':'');
      bar.style.height = (row[kind] ? Math.max(2,row[kind]/max*100) : 0)+'%';
      const text = `${monthLabel(row.mes)} · ${label}: ${money(row[kind])}`;
      bar.title=text;bar.setAttribute('aria-label',text);bar.onfocus=bar.onmouseenter=bar.onclick=()=>{$('chartDetail').textContent=text;};
      pair.append(bar);
    }
    const label=document.createElement('small');label.textContent=row.mes.slice(5)+'/'+row.mes.slice(2,4);
    column.append(pair,label);$('trendChart').append(column);
  }
  $('chartDetail').textContent = data.historico.some(r=>r.dizimo+r.oferta) ? 'Selecione uma barra para consultar o valor.' : 'Nenhuma entrada registrada nos últimos seis meses.';
}
async function loadDashboard() {
  const mes=$('dashboardMonth').value, request=++dashboardRequest;
  if(!mes) return;
  $('dashboardContent').classList.add('dashboard-loading');$('dashboardError').textContent='';
  try {
    const data=await api('/api/painel?mes='+encodeURIComponent(mes));if(request!==dashboardRequest)return;
    $('monthlyContributors').textContent = data.dizimistas_quantidade;
    for(const [id,value] of Object.entries({dashBalance:data.saldo_final===null?'—':money(data.saldo_final),dashIncome:money(data.entradas),dashTithes:money(data.dizimo.total),dashOffers:money(data.oferta.total),dashCount:`${data.dizimo.quantidade+data.oferta.quantidade} lançamentos no mês`,dashTitheCount:`${data.dizimo.quantidade} lançamentos`,dashOfferCount:`${data.oferta.quantidade} lançamentos`,averageTithe:data.dizimo.media===null?'—':money(data.dizimo.media),averageOffer:data.oferta.media===null?'—':money(data.oferta.media)}))$(id).textContent=value;
    $('dashBalance').classList.toggle('negative-value',data.saldo_final<0);
    $('dashboardOpening').textContent=data.saldo_anterior===null?'—':money(data.saldo_anterior);
    $('dashboardOpening').classList.toggle('negative-value',data.saldo_anterior<0);
    $('balanceHelp').textContent=!data.configurado?'Configure em Lançamentos de entrada':data.saldo_anterior===null?'Antes do início do controle':mes===data.mes_inicial?'Saldo inicial informado':`Saldo de ${monthLabel(data.mes_anterior)}`;
    $('expensesNote').textContent=`Despesas lançadas no mês: ${money(data.despesas)}. As médias consideram cada lançamento do mês, inclusive ofertas coletivas.`;
    renderCharts(data);
    $('dashboardContent').classList.remove('dashboard-loading');
  } catch(e) {if(request===dashboardRequest)$('dashboardError').textContent='Não foi possível atualizar o painel: '+e.message;}
}
let entryBalanceRequest=0;
async function loadEntryBalance(){
 const request=++entryBalanceRequest;
 $('saveInitial').disabled=true;$('initialBalance').readOnly=true;$('balanceError').textContent='';
 try{
  const data=await api('/api/fechamento?mes='+encodeURIComponent($('entriesMonth').value));
  if(request!==entryBalanceRequest)return;
    $('initialMonthLabel').hidden=data.configurado;$('initialMonth').required=!data.configurado;$('initialMonth').value=data.mes_inicial;
    $('initialBalance').readOnly=data.configurado;$('initialBalance').required=!data.configurado;
    $('initialBalance').value=data.saldo_anterior===null?'':(data.saldo_anterior/100).toFixed(2).replace('.',',');
    $('saveInitial').hidden=data.configurado;$('saveInitial').disabled=data.configurado;

  $('entryBalanceHelp').textContent=data.configurado?'Saldo inicial já informado. O saldo anterior do mês selecionado é automático e está travado.':'Informe o primeiro mês e o saldo anterior uma única vez. Depois de salvar, o valor fica travado.';
 }catch(e){if(request===entryBalanceRequest)$('balanceError').textContent=e.message;}
}
$('dashboardMonth').onchange=loadDashboard;
$('initialBalanceForm').onsubmit=async e=>{
  e.preventDefault();$('saveInitial').disabled=true;$('balanceError').textContent='';
  try {const mes=$('initialMonth').value;await api('/api/saldo-inicial',{mes,valor:cents($('initialBalance').value)});selectEntryMonth(mes);toast('Saldo inicial salvo. Os próximos meses serão calculados automaticamente.');await refresh();}
  catch(e){$('balanceError').textContent=e.message;$('saveInitial').disabled=false;}
};
selectTab('dashboard');
