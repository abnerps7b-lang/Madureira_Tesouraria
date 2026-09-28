const expensesView=document.createElement('section');expensesView.id='expensesView';expensesView.hidden=true;
async function encodeReceipt(file){
 if(file.size>8*1024*1024)throw Error('Selecione uma foto de até 8 MB.');
 let source=file;
 if(window.ONLINE_HOSTING&&file.size>3*1024*1024){
  const bitmap=await createImageBitmap(file),canvas=document.createElement('canvas');
  const scale=Math.min(1,2800/Math.max(bitmap.width,bitmap.height));
  canvas.width=Math.round(bitmap.width*scale);canvas.height=Math.round(bitmap.height*scale);
  const context=canvas.getContext('2d');context.fillStyle='white';context.fillRect(0,0,canvas.width,canvas.height);context.drawImage(bitmap,0,0,canvas.width,canvas.height);bitmap.close();
  for(const quality of [.9,.8,.65]){source=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',quality));if(source&&source.size<=3*1024*1024)break;}
  if(!source||source.size>3*1024*1024)throw Error('A foto ainda está grande. Envie uma imagem menor para a hospedagem.');
 }
 return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=()=>reject(Error('Não foi possível abrir a foto.'));reader.readAsDataURL(source);});
}
const expenseCategories=['Alimentação','Vestuário','Produtos de Limpeza','Energia','Água','Transporte','Saúde','Lazer','Outros'];
function categorySelect(value='Outros'){const select=document.createElement('select');for(const category of expenseCategories){const option=new Option(category,category,category===value,category===value);select.add(option);}return select;}
expensesView.innerHTML=`<section class="cards"><div class="card total"><div class="label">Despesas do mês</div><div class="amount" id="expenseTotal">—</div><div class="sub" id="expenseCount"></div></div></section>
<section class="panel"><div class="panelhead"><div><h2>Lançamentos de despesas</h2><p>Registre cada despesa conforme ela ocorrer.</p></div><div class="actions"><button id="expensePrint" class="secondary">Imprimir / PDF</button><button id="uploadBatch" type="button">Carregar notas em lote</button><button id="newExpense">+ Nova despesa</button></div></div>
<form id="expenseFilters" class="filters"><label>Mês das despesas<input id="expenseMonth" type="month" required></label><button>Filtrar despesas</button></form><p id="expenseError" class="error" role="alert"></p>
<div class="tablewrap"><table><thead><tr><th>Data</th><th>Descrição</th><th>Categoria</th><th>Valor</th><th>Ações</th></tr></thead><tbody id="expenseRows"></tbody></table></div></section>`;
main.querySelector('footer').before(expensesView);
document.querySelector('.sidebar .nav').insertAdjacentHTML('beforeend','<button class="tab-button" id="tabExpenses" aria-selected="false"><span>↘</span>Lançamentos de despesas</button>');
document.body.insertAdjacentHTML('beforeend',`<dialog id="expenseDialog"><h2>Registrar despesa</h2><p>Descrição livre: não é necessário cadastrar despesas fixas.</p><form id="expenseForm"><div class="formgrid"><label>Data<input id="expenseDate" type="date" required></label><label>Valor (R$)<input id="expenseValue" inputmode="decimal" pattern="[0-9]+([.,][0-9]{1,2})?" required placeholder="0,00"></label><label class="wide">Descrição da despesa<textarea id="expenseDescription" maxlength="500" rows="3" required placeholder="Ex.: Conta de energia"></textarea></label></div><p id="expenseFormError" class="error" role="alert"></p><div class="formactions"><button id="cancelExpense" type="button" class="secondary">Cancelar</button><button id="saveExpense">Salvar despesa</button></div></form></dialog>`);
$('expenseMonth').value=today().slice(0,7);
const categoryLabel=document.createElement('label');categoryLabel.textContent='Categoria';const categoryInput=categorySelect();categoryInput.id='expenseCategory';categoryLabel.append(categoryInput);document.querySelector('#expenseForm .formgrid').append(categoryLabel);
document.body.insertAdjacentHTML('beforeend',`<dialog id="editExpenseDialog"><h2>Editar despesa</h2><form id="editExpenseForm"><label>Descrição<textarea id="editExpenseDescription" required maxlength="500"></textarea></label><label id="editCategoryLabel">Categoria</label><p id="editExpenseError" class="error" role="alert"></p><div class="formactions"><button type="button" id="cancelExpenseEdit" class="secondary">Cancelar</button><button id="saveExpenseEdit">Salvar alterações</button></div></form></dialog>`);
const editCategory=categorySelect();$('editCategoryLabel').append(editCategory);let editingExpenseId;
function editExpense(row){editingExpenseId=row.id;$('editExpenseDescription').value=row.descricao;editCategory.value=row.categoria;$('editExpenseError').textContent='';$('editExpenseDialog').showModal();}
$('cancelExpenseEdit').onclick=()=>$('editExpenseDialog').close();
$('editExpenseForm').onsubmit=async e=>{e.preventDefault();$('saveExpenseEdit').disabled=true;try{await api('/api/despesas/editar',{id:editingExpenseId,descricao:$('editExpenseDescription').value,categoria:editCategory.value});$('editExpenseDialog').close();await loadExpenses();toast('Despesa atualizada.');}catch(error){$('editExpenseError').textContent=error.message;}finally{$('saveExpenseEdit').disabled=false;}};
document.querySelector('#expensesView .panel').insertAdjacentHTML('beforeend',`<section class="batch-section"><h2>Adicionar notas em lote</h2><p>Selecione fotos de várias notas. Confira a data, a descrição, a categoria e o total de cada uma antes de salvar. Valores não identificados ficam em branco.</p><label>Fotos das notas<input id="batchFiles" type="file" multiple accept="image/jpeg,image/png,image/webp"></label><p id="batchStatus" role="status"></p><div class="tablewrap"><table><thead><tr><th>Data</th><th>Descrição</th><th>Categoria</th><th>Valor (R$)</th><th>Conferência</th></tr></thead><tbody id="batchRows"></tbody></table></div></section>`);
const batchSection=document.querySelector('#expensesView .batch-section');
batchSection.id='batchSection';
document.querySelector('#expenseFilters').before(batchSection);
const batchHelp=document.createElement('p');batchHelp.textContent='Selecione todas as fotos de uma vez. A leitura continua enquanto você usa as outras abas do sistema. Mantenha esta página aberta e não a atualize até conferir e salvar as notas.';batchSection.querySelector('h2').after(batchHelp);
$('uploadBatch').onclick=()=>{batchSection.scrollIntoView({behavior:'smooth',block:'start'});if(!batchReading)$('batchFiles').click();};
const batchProgress=document.createElement('progress');batchProgress.id='batchProgress';batchProgress.hidden=true;batchProgress.setAttribute('aria-label','Notas processadas');$('batchStatus').before(batchProgress);
let batchReading=false;
$('batchFiles').onchange=async()=>{
 if(batchReading)return;batchReading=true;$('batchFiles').disabled=true;
 const files=[...$('batchFiles').files];let processed=0;batchProgress.hidden=false;batchProgress.max=Math.max(files.length,1);batchProgress.value=0;$('uploadBatch').textContent='Acompanhar leitura do lote';
 try{for(const file of files){
  $('batchStatus').textContent=`Lendo nota ${++processed} de ${files.length}. Aguarde…`;
  batchProgress.value=processed-1;
  const tr=document.createElement('tr'),dateInput=document.createElement('input'),description=document.createElement('textarea'),category=categorySelect(),value=document.createElement('input'),status=document.createElement('div'),save=document.createElement('button'),remove=document.createElement('button');
  dateInput.type='date';dateInput.required=true;description.maxLength=500;description.required=true;description.value=file.name;value.inputMode='decimal';value.placeholder='Confira o total';save.textContent='Salvar nota';save.disabled=true;remove.textContent='Retirar do lote';remove.className='secondary';remove.onclick=()=>tr.remove();
  for(const control of [dateInput,description,category,value]){const td=document.createElement('td');td.append(control);tr.append(td);}const actions=document.createElement('td');actions.append(status,save,remove);tr.append(actions);$('batchRows').append(tr);
  try{
   if(file.size>8*1024*1024)throw Error('Foto acima de 8 MB.');
   const arquivo=await encodeReceipt(file);
   const note=await api('/api/notas',{arquivo});description.value=note.descricao||'';category.value=note.categoria||'Outros';value.value=note.valor===null?'':(note.valor/100).toFixed(2).replace('.',',');status.textContent=(note.mensagem||'Confira os dados.')+' Informe a data da nota.';
   const link=document.createElement('a');link.href='/api/nota?id='+encodeURIComponent(note.id);link.target='_blank';link.rel='noopener';link.textContent='Ver nota';actions.prepend(link);save.disabled=false;
   save.onclick=async()=>{
    if(!dateInput.reportValidity()||!description.reportValidity())return;
    if(!/^\d+([.,]\d{1,2})?$/.test(value.value.trim())){status.textContent='Informe o total com até duas casas decimais.';return;}
    save.disabled=true;
    try{await api('/api/despesas',{nota_id:note.id,data:dateInput.value,descricao:description.value,categoria:category.value,valor:cents(value.value)});for(const control of [dateInput,description,category,value])control.disabled=true;save.remove();remove.remove();status.textContent='Salva';$('expenseMonth').value=dateInput.value.slice(0,7);await loadExpenses();}
    catch(error){status.textContent=error.message;save.disabled=false;}
   };
  }catch(error){status.textContent=error.message+' Retire esta linha e selecione a foto novamente para tentar outra vez.';}
 }}finally{batchProgress.value=files.length;$('uploadBatch').textContent='Carregar notas em lote';batchReading=false;$('batchFiles').disabled=false;$('batchFiles').value='';$('batchStatus').textContent='Leitura concluída. Confira e salve cada nota. As despesas anteriores permanecem na tabela do mês selecionado.';}
};
document.querySelector('#expenseDialog > p').insertAdjacentHTML('afterend','<p id="aiStatus" class="chart-subtitle" role="status" style="margin-top:10px"></p>');
document.querySelector('#expenseDialog > p').textContent='Anexe a nota e confira o total e a descrição sugeridos. Você pode complementar os campos antes de salvar.';
document.querySelector('#expenseForm .formgrid').insertAdjacentHTML('afterbegin', `<div class="wide"><label>Foto da nota (obrigatória)<input id="receiptFile" type="file" accept="image/jpeg,image/png,image/webp" required></label><p class="chart-subtitle">JPG, PNG ou WebP, até 8 MB. Fotografe a nota inteira, com boa iluminação. Na hospedagem, fotos grandes são compactadas antes do envio.</p><p id="receiptStatus" role="status" style="margin-top:10px"></p><img id="receiptPreview" alt="Nota anexada" hidden style="max-width:100%;max-height:220px;object-fit:contain;margin-top:12px"><details id="receiptDetails" hidden><summary>Texto identificado na nota</summary><pre id="receiptText" style="white-space:pre-wrap;max-height:180px;overflow:auto;font-size:12px"></pre></details></div>`);
let receiptId=null,receiptVersion=0,receiptLoading=false;
$('receiptStatus').insertAdjacentHTML('afterend','<button type="button" id="retryReceipt" class="secondary" hidden>Ler nota novamente</button>');
$('retryReceipt').onclick=()=>{if(!receiptLoading)$('receiptFile').onchange(true);};
function resetReceipt(){receiptVersion++;receiptId=null;receiptLoading=false;$('receiptStatus').textContent='';$('receiptPreview').hidden=true;$('receiptPreview').removeAttribute('src');$('receiptDetails').hidden=true;$('receiptText').textContent='';$('saveExpense').disabled=true;}
$('receiptFile').onchange=async(force=false)=>{
  resetReceipt();const version=receiptVersion,file=$('receiptFile').files[0];
  if(!file)return;
  $('retryReceipt').hidden=false;
  if(file.size>8*1024*1024){$('receiptStatus').textContent='A foto deve ter até 8 MB.';return;}
  receiptLoading=true;$('receiptStatus').textContent='Analisando a foto e conferindo os valores. Aguarde; a análise pode levar alguns minutos…';
  const oldValue=$('expenseValue').value,oldDescription=$('expenseDescription').value;
  try{
    const encoded=await encodeReceipt(file);
    if(version!==receiptVersion)return;
    const note=await api('/api/notas',{arquivo:encoded,reanalisar:force===true});if(version!==receiptVersion)return;
    receiptId=note.id;$('expenseCategory').value=note.categoria||'Outros';$('receiptPreview').src='/api/nota?id='+encodeURIComponent(receiptId);$('receiptPreview').hidden=false;
    $('receiptStatus').textContent=note.mensagem;
    if(!oldValue&&$('expenseValue').value===oldValue&&note.valor!==null)$('expenseValue').value=(note.valor/100).toFixed(2).replace('.',',');
    if((!oldDescription||oldDescription==='Despesa conforme nota fiscal')&&$('expenseDescription').value===oldDescription)$('expenseDescription').value=note.descricao;
    if(oldValue||oldDescription)$('receiptStatus').textContent+=' Os campos já preenchidos foram mantidos. Total sugerido: '+(note.valor===null?'não identificado':money(note.valor))+'. Descrição sugerida: '+note.descricao+'.';
    $('receiptText').textContent=note.texto;$('receiptDetails').hidden=!note.texto;
  }catch(e){if(version===receiptVersion)$('receiptStatus').textContent=e.message;}
  finally{if(version===receiptVersion){receiptLoading=false;$('saveExpense').disabled=!receiptId;}}
};
const previousSelectTab=selectTab;
selectTab=function(tab){
  document.querySelector('main > header .actions').hidden=tab!=='entries';
  expensesView.hidden=tab!=='expenses';$('tabExpenses').setAttribute('aria-selected',String(tab==='expenses'));
  if(tab!=='expenses'){previousSelectTab(tab);return;}
  activeTab=tab;dashboardView.hidden=entriesView.hidden=true;
  $('tabDashboard').setAttribute('aria-selected','false');$('tabEntries').setAttribute('aria-selected','false');
  main.querySelector('h1').textContent='Lançamentos de despesas';loadExpenses();
};
document.querySelector('main > header .actions').hidden=activeTab!=='entries';
$('tabExpenses').onclick=()=>selectTab('expenses');
let expenseRequest=0,loadedExpenseMonth='';
async function loadExpenses(){
  const request=++expenseRequest,mes=$('expenseMonth').value;
  $('expensePrint').disabled=true;$('expenseError').textContent='';
  $('expenseRows').replaceChildren();$('expenseTotal').textContent='—';$('expenseCount').textContent='';
  if(!mes)return;
  try{
    const data=await api('/api/despesas?mes='+encodeURIComponent(mes));if(request!==expenseRequest)return;
    loadedExpenseMonth=mes;$('expenseTotal').textContent=money(data.total);$('expenseCount').textContent=`${data.registros.length} despesas no mês`;
    for(const row of data.registros){const tr=document.createElement('tr');for(const [index,value] of [dateText(row.data),row.descricao,row.categoria,money(row.valor)].entries()){const td=document.createElement('td');td.textContent=value;if(index===1){td.style.whiteSpace='normal';td.style.minWidth='180px';const detail=document.createElement('div');if(row.nota_id){const link=document.createElement('a');link.href='/api/nota?id='+encodeURIComponent(row.nota_id);link.target='_blank';link.rel='noopener';link.textContent='Ver nota anexada';detail.append(link);}else{detail.textContent='Registro anterior sem anexo';detail.className='note';}td.append(detail);}if(index===0)td.style.textAlign='center';tr.append(td);}const edit=document.createElement('button');edit.textContent='Editar';edit.className='secondary';edit.onclick=()=>editExpense(row);const action=deleteCell('despesas',row.id,dateText(row.data)+' - '+row.descricao+' - '+money(row.valor),loadExpenses);action.prepend(edit);tr.append(action);$('expenseRows').append(tr);}
    if(!data.registros.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=5;td.className='empty';td.textContent='Nenhuma despesa neste mês.';tr.append(td);$('expenseRows').append(tr);}
    $('expensePrint').disabled=false;
  }catch(e){if(request===expenseRequest)$('expenseError').textContent=e.message;}
}
$('expenseMonth').onchange=loadExpenses;$('expenseFilters').onsubmit=e=>{e.preventDefault();loadExpenses();};
$('expensePrint').onclick=()=>location.assign('/relatorio-despesas?mes='+encodeURIComponent(loadedExpenseMonth));
$('newExpense').onclick=async()=>{$('expenseForm').reset();resetReceipt();$('retryReceipt').hidden=true;$('expenseDate').value=today();$('expenseFormError').textContent='';$('expenseDialog').showModal();try{const status=await api('/api/ia-status');$('aiStatus').textContent=status.mensagem;}catch(e){$('aiStatus').textContent=e.message;}};
$('cancelExpense').onclick=()=>$('expenseDialog').close();
$('expenseForm').onsubmit=async e=>{
  e.preventDefault();if(receiptLoading||!receiptId){$('expenseFormError').textContent='Anexe a nota e aguarde a leitura antes de salvar.';return;}$('saveExpense').disabled=true;$('receiptFile').disabled=true;$('expenseFormError').textContent='';
  try{await api('/api/despesas',{categoria:$('expenseCategory').value,nota_id:receiptId,data:$('expenseDate').value,descricao:$('expenseDescription').value,valor:cents($('expenseValue').value)});$('expenseMonth').value=$('expenseDate').value.slice(0,7);$('expenseDialog').close();toast('Despesa e nota salvas. Saldos atualizados automaticamente.');await loadExpenses();}
  catch(e){$('expenseFormError').textContent=e.message;}finally{$('receiptFile').disabled=false;$('saveExpense').disabled=!receiptId;}
};
