(function(){
  const $ = id => document.getElementById(id);
  const fields = ['data','pedido','cliente','representante','referencia','codigoLaser',
    'tamanho','diametro','espessura','material','acabamento','cor','corSufixo',
    'chapaMedia','chapaGrande','textoLaser','descCor','obs'];

  function todayBR(){
    const d = new Date();
    const pad = n => String(n).padStart(2,'0');
    return pad(d.getDate())+'/'+pad(d.getMonth()+1)+'/'+d.getFullYear();
  }
  $('data').value = todayBR();

  let diametroTouched = false;
  $('diametro').addEventListener('input', ()=>{ diametroTouched = true; });
  $('tamanho').addEventListener('input', ()=>{
    if(diametroTouched) return;
    const l = parseFloat($('tamanho').value);
    if(!isNaN(l)){
      $('diametro').value = (l*0.635).toFixed(2).replace('.', ',') + ' mm';
    } else {
      $('diametro').value = '';
    }
  });

  function val(id){ return $(id).value.trim(); }
  function dash(v){ return v ? v : '—'; }

  function render(){
    $('outData').textContent = dash(val('data'));
    $('outCliente').textContent = dash(val('cliente'));
    $('outRepresentante').textContent = dash(val('representante'));
    $('outPedido').textContent = dash(val('pedido'));
    $('outReferencia').textContent = dash(val('referencia'));
    $('outCodigoLaser').textContent = dash(val('codigoLaser'));
    $('outTamanho').textContent = val('tamanho') ? val('tamanho')+'”' : '—';
    $('outDiametro').textContent = dash(val('diametro'));
    $('outEspessura').textContent = val('espessura') ? val('espessura')+' mm' : '—';
    $('outMaterial').textContent = dash(val('material'));
    const cor = val('cor');
    const sufixo = val('corSufixo');
    $('outCor').textContent = cor ? (cor + (sufixo ? ' + '+sufixo : '')) : '—';
    $('outAcabamento').textContent = dash($('acabamento').value);
    $('outChapaMedia').textContent = val('chapaMedia') ? val('chapaMedia')+' grs.' : '—';
    $('outChapaGrande').textContent = val('chapaGrande') ? val('chapaGrande')+' grs.' : '—';

    const list = $('outPersonal');
    list.innerHTML = '';
    const texto = val('textoLaser');
    const li1 = document.createElement('li');
    li1.innerHTML = '<b>Texto:</b> ' + (texto ? '<span class="val">"'+texto+'"</span>' : '<span class="empty">apenas logo</span>');
    list.appendChild(li1);

    const procs = [];
    if($('pTingir').checked) procs.push('Tingir');
    if($('pEstonar').checked) procs.push('Estonar');
    if(procs.length){
      const li3 = document.createElement('li');
      li3.textContent = procs.join(' e ') + '.';
      list.appendChild(li3);
    }

    const descCor = val('descCor');
    if(descCor){
      const li2 = document.createElement('li');
      li2.innerHTML = '<b>Descrição da cor:</b> <span class="val">' + descCor + '</span>';
      list.appendChild(li2);
    }

    const obs = val('obs');
    if(obs){
      const li4 = document.createElement('li');
      li4.innerHTML = '<b>Obs.:</b> ' + obs;
      list.appendChild(li4);
    }
  }

  document.getElementById('form').addEventListener('input', render);
  $('acabamento').addEventListener('change', render);
  render();

  $('printBtn').addEventListener('click', ()=> window.print());
  $('clearBtn').addEventListener('click', ()=>{
    fields.forEach(id=>{ if($(id)) $(id).value=''; });
    $('material').value = 'Poliéster';
    $('data').value = todayBR();
    $('pTingir').checked = false;
    $('pEstonar').checked = false;
    diametroTouched = false;
    render();
  });
})();
