// Simulador de comportamento sobre as fixtures reais da tela de login (BSV-67), so para os testes.
// As fixtures sao dado (sem script). O teste monta a pagina com <div id="raiz"> (tela atual) e <template>
// t-qr, t-numero, t-codigo, e injeta este arquivo. Nada aqui fala com o WhatsApp de verdade.
//   window.__sim.inicio   template da tela inicial (padrao 't-qr')
//   window.__sim.codigo   data-link-code da tela do codigo (padrao o da fixture)
//   window.__sim.mascara  'whatsapp' (padrao: formata +55 11 98765-0000, como medido em 27/11)
//                         'duplica'  (o campo limpo volta com '+55 ': digitar '+55...' duplica o DDI)
(() => {
  const ligar = () => {
    const opc = Object.assign({ inicio: 't-qr', mascara: 'whatsapp' }, window.__sim || {});
    const raiz = document.getElementById('raiz');
    window.__avancos = 0;
    window.__valorAvancado = null;
    const trocar = (id) => {
      raiz.innerHTML = document.getElementById(id).innerHTML;
      const celulas = raiz.querySelector('[data-testid="link-with-phone-number-code-cells"]');
      if (celulas && opc.codigo) celulas.setAttribute('data-link-code', opc.codigo);
      const campo = raiz.querySelector('input[data-testid="phone-number-input"]');
      if (campo) campo.addEventListener('input', () => formatar(campo));
    };
    const formatar = (campo) => {
      const d = campo.value.replace(/\D/g, '');
      if (opc.mascara === 'duplica') {
        if (!campo.value.startsWith('+55 ')) campo.value = '+55 ' + campo.value;
        return;
      }
      if (!d) return;
      let v = '+' + d.slice(0, 2);
      if (d.length > 2) v += ' ' + d.slice(2, 4);
      if (d.length > 4) v += ' ' + d.slice(4, 9);
      if (d.length > 9) v += '-' + d.slice(9);
      campo.value = v;
    };
    document.addEventListener('click', (ev) => {
      if (ev.target.closest('[data-testid="link_device_qr_phone_number_link"]')) {
        trocar('t-numero');
        return;
      }
      const tela = ev.target.closest('[data-testid="link-device-phone-number-entry-screen"]');
      const botao = ev.target.closest('button');
      if (tela && botao && /^(Avançar|Next)$/.test(botao.innerText.trim())) {
        window.__avancos += 1;
        window.__valorAvancado = raiz.querySelector('input[data-testid="phone-number-input"]').value;
        trocar('t-codigo');
      }
    }, true);
    trocar(opc.inicio);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ligar);
  else ligar();
})();
