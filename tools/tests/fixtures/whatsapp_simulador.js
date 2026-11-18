// Simulador de comportamento sobre a fixture REAL (whatsapp_canal_real.html), so para os testes (BSV-63).
// A fixture e dado: o recorte nao tem <script>. Os testes injetam este arquivo com page.add_script_tag e
// escolhem o cenario em window.__sim antes. Nada aqui fala com o WhatsApp de verdade.
//   status        aria-label do msg-meta do balao novo (padrao ' Enviada ', o real); null = sem aria-label
//   semChave      o balao novo nao traz o link besave.io/{id}
//   naoChega      o clique nao produz balao novo
//   mainFechado   #main oculto ate clicar na celula do canal
//   tituloAoClicar  titulo do cabecalho depois de clicar na celula (cabecalho divergente)
//   rejeitaTexto  a legenda da previa ignora colar e digitar
//   rejeitaColar  a legenda da previa ignora so o colar (digitar funciona)
//   atrasoPrevia  ms ate a previa abrir depois do arquivo escolhido (inst2 lenta)
//   Anexar sempre mostra o item "Fotos e vídeos" (que abre o seletor de arquivo), como no WhatsApp real. O input
//   oculto do footer (junto do microfone) continua no DOM e, se receber arquivo, so conta em __arquivosPorCaminho.input.
//   semItemMenu   Anexar nao mostra o item "Fotos e vídeos"
//   menuNaoAbre   o arquivo escolhido pelo menu nao abre a previa
//   camadaFixa    uma camada transparente cobre a pagina e intercepta cliques; Escape NAO a fecha
//   camadaDialogo uma camada [role="dialog"] cobre a pagina; Escape a fecha
//   semCaixa      a caixa do canal some (footer do canal nao volta)
//   atrasoMenu    ms ate o item "Fotos e vídeos" aparecer depois do clique no Anexar
//   dialogoNoAnexar  o clique no Anexar tambem abre uma camada [role="dialog"] (Escape fecha)
//   dialogoTeimoso   uma camada [role="dialog"] pequena, num canto, que Escape NAO fecha
//   reRender      depois do envio, a 1a leitura do data-testid de um balao antigo dispara o re-render da lista
//                 virtualizada (como na inst2 em 17/11): os 3 baloes antigos mais altos saem do DOM no meio da leitura
//   enviarCoberto quando a previa abre, uma camada cobre so o "Enviar 1 item selecionado" (clique interceptado)
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
  window.__arquivosPorCaminho = { input: 0, menu: 0 };
  const cobrirEnviar = () => {
    // camada que acompanha o botao (a legenda colada empurra o botao para baixo; o Playwright rola ate ele)
    if (document.querySelector('[data-sim="cobre-enviar"]')) return;
    const botao = $('div[role="button"][aria-label="Enviar 1 item selecionado"]');
    const c = document.createElement('div');
    c.setAttribute('data-sim', 'cobre-enviar');
    document.body.appendChild(c);
    const seguir = () => {
      const r = botao.getBoundingClientRect();
      c.style.cssText = `position:absolute;left:${r.left + scrollX - 2}px;top:${r.top + scrollY - 2}px;`
        + `width:${r.width + 4}px;height:${r.height + 4}px;z-index:9999;background:rgba(0,0,0,0.01)`;
      requestAnimationFrame(seguir);
    };
    seguir();
  };
  const abrirPrevia = (inp, caminho, naoAbre) => inp.addEventListener('change', () => {
    if (!inp.files.length) return;
    window.__arquivosPorCaminho[caminho]++;
    if (naoAbre) return;
    setTimeout(() => { mostrar(previa, true); legenda.innerHTML = ''; if (opc.enviarCoberto) cobrirEnviar(); },
               opc.atrasoPrevia || 0);
  });
  // input oculto do footer: o publicador NAO deve usa-lo; se usar, a previa abre (o mutante passaria sem a contagem)
  abrirPrevia(footer.querySelector('input[type="file"]'), 'input', false);
  anexar.addEventListener('click', () => {
    anexar.setAttribute('aria-expanded', 'true');
    window.__cliquesAnexar = (window.__cliquesAnexar || 0) + 1;
    if (opc.dialogoNoAnexar && !document.querySelector('[data-sim="camada-dialogo"]')) camada(true);
    if (opc.semItemMenu || document.querySelector('[data-sim="menu-fotos"]')) return;
    const item = document.createElement('div');
    item.setAttribute('role', 'button'); item.setAttribute('data-sim', 'menu-fotos'); item.textContent = 'Fotos e vídeos';
    item.style.display = 'none';
    setTimeout(() => { item.style.display = ''; }, opc.atrasoMenu || 0);
    document.body.appendChild(item);
    item.addEventListener('click', () => {
      const i = document.createElement('input'); i.type = 'file'; i.accept = 'image/*';
      abrirPrevia(i, 'menu', opc.menuNaoAbre); i.click();
    });
  });
  const camada = (dialogo) => {
    const c = document.createElement('div');
    c.setAttribute('data-sim', dialogo ? 'camada-dialogo' : 'camada-fixa');
    if (dialogo) c.setAttribute('role', 'dialog');
    c.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,0.01)';
    c.textContent = dialogo ? 'camada' : '';
    document.body.appendChild(c);
  };
  if (opc.camadaFixa) camada(false);
  if (opc.dialogoTeimoso) {
    const d = document.createElement('div');
    d.setAttribute('role', 'dialog'); d.setAttribute('data-sim', 'dialogo-teimoso'); d.textContent = 'teimoso';
    d.style.cssText = 'position:fixed;right:0;top:0;width:60px;height:20px;z-index:9999';
    document.body.appendChild(d);
  }
  if (opc.camadaDialogo) camada(true);
  if (opc.semCaixa) $('[data-testid="conversation-compose-box-input"]').remove();

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
    if (opc.rejeitaTexto || opc.rejeitaColar) return;
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
    if (e.key === 'Escape') {
      window.__escapes = (window.__escapes || 0) + 1;
      window.__escapesAntesDoMenu = window.__arquivosPorCaminho.menu === 0 ? window.__escapes : window.__escapesAntesDoMenu;
      mostrar(previa, false); anexar.setAttribute('aria-expanded', 'false');
      const m = document.querySelector('[data-sim="menu-fotos"]'); if (m) m.remove();
      const d = document.querySelector('[data-sim="camada-dialogo"]'); if (d) d.remove();
    }
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
    if (opc.reRender) armarReRender();
  }
  function armarReRender() {
    // a lista virtualizada do WhatsApp tira baloes do DOM quando o post novo entra; aqui isso acontece na
    // primeira leitura de um balao antigo, depois do clique: entre um count() e um nth(i), sempre
    const original = Element.prototype.getAttribute;
    let armado = true;
    Element.prototype.getAttribute = function (nome) {
      const valor = original.call(this, nome);
      if (armado && nome === 'data-testid' && /^conv-msg-FAKE/.test(valor || '')) {
        armado = false;
        Array.from(document.querySelectorAll('[data-testid^="conv-msg-FAKE"]')).slice(0, 3).forEach(b => b.remove());
        window.__reRenderizou = true;
      }
      return valor;
    };
  }
  $('div[role="button"][aria-label="Enviar 1 item selecionado"]').addEventListener('click', enviar);
})();
