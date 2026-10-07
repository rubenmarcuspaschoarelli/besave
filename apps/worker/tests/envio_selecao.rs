//! BSV-40 FIL-01..02, REP-01..02, ORD-01: seleção das candidatas sobre o Oracle fake.

mod comum;

use comum::{AGORA, DIA, linha_canal, mapeamento};
use worker::envio::fonte::{FakeEnvio, RegistroEnvio};
use worker::envio::modelo::{LinhaCanal, Parametros};
use worker::envio::selecao::{Candidata, selecionar};

fn sel(f: &FakeEnvio, n: usize) -> Vec<Candidata> {
    selecionar(f, &mapeamento(), &Parametros::default(), 1, AGORA, n).unwrap()
}

fn ids(c: &[Candidata]) -> Vec<i64> {
    c.iter().map(|c| c.oferta.id).collect()
}

/// Envio anterior do produto `produto` a `preco` centavos, há `idade` segundos.
fn historico(f: &FakeEnvio, id_envio: i64, produto: i64, preco: i64, idade: i64) {
    f.registrar(RegistroEnvio {
        id_envio,
        canal: 1,
        id_oferta: 90_000 + id_envio,
        id_produto: Some(produto),
        preco_por: preco,
        message_id: Some(id_envio),
        dt_envio: AGORA - idade,
        dt_edicao: None,
    });
}

/// 50% de desconto, sem cupom.
fn boa(id: i64) -> LinhaCanal {
    linha_canal(id, Some(200.0), 100.0)
}

/// FIL-01: inativa, página fora do ar, `dt` de 25 h, rejeitada pelo §9 → fora.
#[test]
fn filtros_excluem() {
    let mut inativa = boa(1);
    inativa.oferta.ativo = false;
    let mut sem_pagina = boa(2);
    sem_pagina.dt_publicacao_site = None;
    let mut velha = boa(3);
    velha.oferta.dt_oferta = Some(AGORA - 25 * 3600);
    let mut sem_url = boa(4);
    sem_url.oferta.url_afiliado = String::new();
    let mut sem_produto = boa(5);
    sem_produto.oferta.id_produto = None;
    let ok = boa(6);
    let f = FakeEnvio::new(
        Parametros::default(),
        vec![inativa, sem_pagina, velha, sem_url, sem_produto, ok],
    );
    assert_eq!(ids(&sel(&f, 10)), vec![6]);
}

/// FIL-01: 24 h exatas ainda entram (`DT_OFERTA ≥ agora − 24 h`).
#[test]
fn idade_no_limite_entra() {
    let mut l = boa(1);
    l.oferta.dt_oferta = Some(AGORA - 24 * 3600);
    let f = FakeEnvio::new(Parametros::default(), vec![l]);
    assert_eq!(ids(&sel(&f, 10)), vec![1]);
}

/// FIL-01: já enviada a este canal → fora.
#[test]
fn ja_enviada_fica_fora() {
    let f = FakeEnvio::new(Parametros::default(), vec![boa(1), boa(2)]);
    f.registrar(RegistroEnvio {
        id_envio: 1,
        canal: 1,
        id_oferta: 1,
        id_produto: Some(1),
        preco_por: 10000,
        message_id: Some(7),
        dt_envio: AGORA - 10 * DIA,
        dt_edicao: None,
    });
    assert_eq!(ids(&sel(&f, 10)), vec![2]);
}

/// FIL-02: 29% fora, 30% dentro, `pd` nulo dentro.
#[test]
fn desconto_minimo() {
    let f = FakeEnvio::new(
        Parametros::default(),
        vec![
            linha_canal(1, Some(100.0), 71.0),
            linha_canal(2, Some(100.0), 70.0),
            linha_canal(3, None, 70.0),
        ],
    );
    let mut r = ids(&sel(&f, 10));
    r.sort_unstable();
    assert_eq!(r, vec![2, 3]);
}

/// REP-01: mesmo produto há 4 dias; queda de 9% → fora; 10% → dentro com a frase.
#[test]
fn repeticao_exige_queda() {
    let f = FakeEnvio::new(Parametros::default(), vec![boa(1)]);
    // Último envio do produto 1 a R$ 109,89: 100,00 é queda de 9,0%.
    historico(&f, 1, 1, 10989, 4 * DIA);
    assert!(sel(&f, 10).is_empty());

    let f = FakeEnvio::new(Parametros::default(), vec![boa(1)]);
    // R$ 111,12: 100,00 ≤ 111,12 × 0,9 = 100,008 → queda ≥ 10%.
    historico(&f, 1, 1, 11112, 4 * DIA);
    let c = sel(&f, 10);
    assert_eq!(ids(&c), vec![1]);
    assert!(c[0].caiu);

    // Exatamente 10%: 90,00 de 100,00 entra; 90,01 não.
    let f = FakeEnvio::new(Parametros::default(), vec![linha_canal(1, None, 90.0)]);
    historico(&f, 1, 1, 10000, 4 * DIA);
    assert!(sel(&f, 10)[0].caiu);
    let f = FakeEnvio::new(Parametros::default(), vec![linha_canal(1, None, 90.01)]);
    historico(&f, 1, 1, 10000, 4 * DIA);
    assert!(sel(&f, 10).is_empty());
}

/// REP-02: último envio há 5 dias → dentro, sem a frase.
#[test]
fn repeticao_depois_da_janela() {
    let f = FakeEnvio::new(Parametros::default(), vec![boa(1)]);
    historico(&f, 1, 1, 10000, 5 * DIA);
    let c = sel(&f, 10);
    assert_eq!(ids(&c), vec![1]);
    assert!(!c[0].caiu);
}

/// REP-01: vale o envio mais recente do produto.
#[test]
fn repeticao_compara_com_o_ultimo() {
    let f = FakeEnvio::new(Parametros::default(), vec![boa(1)]);
    historico(&f, 1, 1, 20000, 3 * DIA);
    historico(&f, 2, 1, 10500, DIA);
    assert!(sel(&f, 10).is_empty());
}

/// REP-01: duas ofertas do mesmo produto no mesmo lote: a segunda passa pela regra de queda.
#[test]
fn repeticao_dentro_do_lote() {
    let mut a = boa(1);
    let mut b = linha_canal(2, Some(200.0), 100.0);
    a.oferta.id_produto = Some(77);
    b.oferta.id_produto = Some(77);
    let f = FakeEnvio::new(Parametros::default(), vec![a, b]);
    assert_eq!(sel(&f, 2).len(), 1);
}

/// ORD-01: maior desconto primeiro; empate → com cupom; empate → `dt` mais recente; → id maior.
#[test]
fn ordem_de_envio() {
    let mut com_cupom = boa(1);
    com_cupom.oferta.cupom = Some("BESAVE".into());
    let sem_cupom = boa(2);
    let maior = linha_canal(3, Some(300.0), 100.0);
    let mut recente = boa(4);
    recente.oferta.dt_oferta = Some(AGORA - 60);
    let sem_pd = linha_canal(5, None, 100.0);
    let mut empate_a = boa(6);
    let mut empate_b = boa(7);
    empate_a.oferta.dt_oferta = Some(AGORA - 7200);
    empate_b.oferta.dt_oferta = Some(AGORA - 7200);
    let f = FakeEnvio::new(
        Parametros::default(),
        vec![
            sem_pd, sem_cupom, com_cupom, empate_a, maior, recente, empate_b,
        ],
    );
    assert_eq!(ids(&sel(&f, 10)), vec![3, 1, 4, 7, 6, 2, 5]);
}

/// Ordem: 50% sem cupom vs 50% com cupom → com cupom; empate total → mais recente.
#[test]
fn ordem_casos_da_spec() {
    let mut com = boa(1);
    com.oferta.cupom = Some("X1".into());
    let f = FakeEnvio::new(Parametros::default(), vec![boa(2), com]);
    assert_eq!(ids(&sel(&f, 1)), vec![1]);
    let mut nova = boa(1);
    nova.oferta.dt_oferta = Some(AGORA - 100);
    let f = FakeEnvio::new(Parametros::default(), vec![boa(2), nova]);
    assert_eq!(ids(&sel(&f, 1)), vec![1]);
}

/// Menos candidatas que o lote → as que houver.
#[test]
fn lote_maior_que_as_candidatas() {
    let f = FakeEnvio::new(Parametros::default(), vec![boa(1)]);
    assert_eq!(ids(&sel(&f, 2)), vec![1]);
}
