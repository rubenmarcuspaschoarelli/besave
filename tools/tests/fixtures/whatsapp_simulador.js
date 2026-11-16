// Simulador de comportamento sobre a fixture REAL (whatsapp_canal_real.html), so para os testes (BSV-63).
// A fixture e dado: o recorte nao tem <script>. Os testes injetam este arquivo com page.add_script_tag e
// escolhem o cenario em window.__sim antes. Nada aqui fala com o WhatsApp de verdade.
//   status        aria-label do msg-meta do balao novo (padrao ' Enviada ', o real); null = sem aria-label
//   semChave      o balao novo nao traz o link besave.io/{id}
//   naoChega      o clique nao produz balao novo
//   mainFechado   #main oculto ate clicar na celula do canal
//   tituloAoClicar  titulo do cabecalho depois de clicar na celula (cabecalho divergente)
//   semInput      sem o input do footer; o clique em Anexar o cria
//   menuSemInput  sem input nenhum; Anexar mostra o item "Fotos e vídeos", que abre o seletor de arquivo
//   rejeitaTexto  a legenda da previa ignora colar e digitar
(() => {
  const opc = Object.assign({ status: ' Enviada ' }, window.__sim || {});
  window.__envios = [];
  window.__enters = 0;
  window.__cliquesCanais = 0;
  const $ = (s) => document.querySelector(s);
  const legenda = $('[data-testid="media-caption-input-container"]');
  const previa = legenda.parentElement;
  const mostrar = (el, sim) => { el.style.display = sim ? '' : 'none'; };
  mostrar(previa, false);
  legenda.style.minHeight = '1.5em';  // caixa vazia sem CSS teria altura 0 (invisivel)

  // --- navegacao
  const main = $('#main');
  const titulo = $('[data-testid="conversation-info-header-chat-title"]');
  if (opc.mainFechado) mostrar(main, false);
  $('button[aria-label="Canais"]').addEventListener('click', () => { window.__cliquesCanais++; });
  $('[data-testid="newsletter-tab-newsletter-cell"]').addEventListener('click', () => {
    mostrar(main, true);
    if (opc.tituloAoClicar !== undefined) titulo.textContent = opc.tituloAoClicar;
  });

  // --- anexo
  const footer = $('#main footer');
  const anexar = footer.querySelector('button[aria-label="Anexar"]');
  const abrirPrevia = (inp) => inp.addEventListener('change', () => {
    if (inp.files.length) { mostrar(previa, true); legenda.innerHTML = ''; }
  });
  let entrada = footer.querySelector('input[type="file"]');
  if (opc.semInput || opc.menuSemInput) entrada.remove(); else abrirPrevia(entrada);
  anexar.addEventListener('click', () => {
    anexar.setAttribute('aria-expanded', 'true');
    if (opc.semInput && !footer.querySelector('input[type="file"]')) {
      entrada = document.createElement('input');
      entrada.type = 'file'; entrada.accept = 'image/*'; entrada.style.display = 'none';
      footer.appendChild(entrada); abrirPrevia(entrada);
    }
    if (opc.menuSemInput) {
      const item = document.createElement('div');
      item.setAttribute('role', 'button'); item.textContent = 'Fotos e vídeos';
      document.body.appendChild(item);
      item.addEventListener('click', () => {
        const i = document.createElement('input'); i.type = 'file'; i.accept = 'image/*';
        abrirPrevia(i); i.click();
      });
    }
  });

  // --- legenda da previa (como o Lexical: colar vira um <p> por linha; Enter envia; Shift+Enter quebra)
  const textoEditor = (el) => {
    const txt = (n) => { let s = ''; n.childNodes.forEach(c => {
      if (c.nodeType === 3) s += c.data; else if (c.nodeName === 'BR') s += '\n'; else s += txt(c); }); return s; };
    const bloco = (n) => { const s = txt(n); return s.endsWith('\n') ? s.slice(0, -1) : s; };
    const ps = Array.from(el.children).filter(c => c.nodeName === 'P' || c.nodeName === 'DIV');
    return ps.length ? ps.map(bloco).join('\n') : bloco(el);
  };
  legenda.addEventListener('paste', (e) => {
    e.preventDefault();
    if (opc.rejeitaTexto) return;
    legenda.innerHTML = '';
    e.clipboardData.getData('text/plain').split('\n').forEach(l => {
      const p = document.createElement('p');
      if (l) p.textContent = l; else p.appendChild(document.createElement('br'));
      legenda.appendChild(p);
    });
  });
  legenda.addEventListener('beforeinput', (e) => { if (opc.rejeitaTexto) e.preventDefault(); });
  legenda.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); window.__enters++; enviar(); }
    else if (e.key === 'Enter' && e.shiftKey) { e.preventDefault(); document.execCommand('insertLineBreak'); }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { mostrar(previa, false); anexar.setAttribute('aria-expanded', 'false'); }
  });

  // --- envio: o balao novo e copia de um balao real com legenda (FAKEn), com o texto renderizado (sem * _ ~ `)
  let novos = 0;
  const modelo = Array.from(document.querySelectorAll('[data-testid^="conv-msg-"]'))
    .filter(b => b.querySelector('[data-testid~="image-caption"]')).pop();
  window.__novoBalao = (texto, status) => {
    const b = modelo.cloneNode(true);
    b.setAttribute('data-testid', 'conv-msg-NOVO' + (++novos));
    b.querySelector('[data-testid~="image-caption"]').textContent = texto;
    const meta = b.querySelector('[data-testid="msg-meta"] [aria-label]');
    if (status === null) meta.removeAttribute('aria-label'); else meta.setAttribute('aria-label', status);
    modelo.parentElement.appendChild(b);
    return b;
  };
  function enviar() {
    const texto = textoEditor(legenda);
    window.__envios.push(texto);
    mostrar(previa, false);
    legenda.innerHTML = '';
    if (opc.naoChega) return;
    let renderizado = texto.replace(/[*_~`]/g, '');
    if (opc.semChave) renderizado = renderizado.replace(/besave\.io\/\d+/g, 'besave.io/');
    window.__novoBalao(renderizado, opc.status);
  }
  $('div[role="button"][aria-label="Enviar 1 item selecionado"]').addEventListener('click', enviar);
})();
