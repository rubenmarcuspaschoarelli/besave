//! CHK-05, MAN-01..08: `gerar` com `FakeFonte` + `PublicadorMemoria`.

mod comum;

use std::collections::BTreeMap;

use comum::{
    AGORA, compactar, descomprimir, fixture, linha, linhas_fixture, mapeamento, texto_aleatorio,
    validar_schema,
};
use worker::conversao::{LinhaOferta, Rejeicao};
use worker::fonte::FakeFonte;
use worker::geracao::{ErroGeracao, Relatorio, checar_orcamento, gerar};
use worker::modelo::{Area, Manifest};
use worker::publicador::{
    ErroPublicador, META_CHUNK, META_MANIFEST, Meta, Publicador, PublicadorMemoria,
};

fn rodar(linhas: Vec<LinhaOferta>, p: &mut dyn Publicador) -> Result<Relatorio, ErroGeracao> {
    gerar(
        &FakeFonte::new(linhas, vec![], AGORA),
        &mapeamento(),
        p,
        AGORA,
    )
}

fn manifest(p: &PublicadorMemoria) -> Manifest {
    serde_json::from_slice(&p.ler("manifest.json").unwrap().unwrap()).unwrap()
}

/// Fixture (chunk 5) + 1001 e 1500 (chunk 1) + 2 rejeitadas.
fn fonte_mista() -> Vec<LinhaOferta> {
    let mut v = linhas_fixture();
    v.push(linha(1500));
    v.push(linha(1001));
    v.push(LinhaOferta {
        preco_por: None,
        ..linha(1700)
    });
    v.push(LinhaOferta {
        id_produto: None,
        ..linha(1800)
    });
    v
}

#[test]
fn manifest_valida_contra_schema() {
    let mut p = PublicadorMemoria::new();
    rodar(fonte_mista(), &mut p).unwrap();
    validar_schema(
        "manifest.schema.json",
        &serde_json::from_slice(&p.ler("manifest.json").unwrap().unwrap()).unwrap(),
    );
}

#[test]
fn manifest_cabecalho() {
    let mut p = PublicadorMemoria::new();
    rodar(fonte_mista(), &mut p).unwrap();
    let m = manifest(&p);
    let pkg: serde_json::Value = serde_json::from_str(
        &std::fs::read_to_string(
            std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
                .join("../../packages/contract/package.json"),
        )
        .unwrap(),
    )
    .unwrap();
    assert_eq!(m.contrato, pkg["version"].as_str().unwrap());
    assert_eq!(m.versao, 20_260_924_124_000);
    assert_eq!(m.gerado_em, "2026-09-24T12:40:00Z");
    assert_eq!(m.busca, None);
}

#[test]
fn manifest_chunks_com_ids_reais_e_bytes_comprimidos() {
    let mut p = PublicadorMemoria::new();
    rodar(fonte_mista(), &mut p).unwrap();
    let m = manifest(&p);
    assert_eq!(m.chunks.iter().map(|c| c.n).collect::<Vec<_>>(), vec![1, 5]);
    assert_eq!(m.chunks[0].ids, [1001, 1500]);
    assert_eq!(m.chunks[0].qtd, 2);
    assert_eq!(m.chunks[1].ids, [5412, 5420]);
    assert_eq!(m.chunks[1].qtd, 3);
    for c in &m.chunks {
        let br = p.ler(&c.arquivo).unwrap().unwrap();
        assert_eq!(c.bytes, br.len() as u64, "{}", c.arquivo);
        let cards: Vec<serde_json::Value> = serde_json::from_slice(&descomprimir(&br)).unwrap();
        assert_eq!(c.qtd, cards.len() as u64);
    }
}

#[test]
fn fixture_vira_um_chunk_com_hash_deterministico() {
    let mut p = PublicadorMemoria::new();
    rodar(linhas_fixture(), &mut p).unwrap();
    let m = manifest(&p);
    assert_eq!(m.chunks.len(), 1);
    assert_eq!(
        m.chunks[0].arquivo,
        "data/chunks/5-89590e56ef6361dc.json.br"
    );
    let bruto = descomprimir(&p.ler(&m.chunks[0].arquivo).unwrap().unwrap());
    assert_eq!(
        String::from_utf8(bruto.clone()).unwrap(),
        compactar(&fixture("chunk-ok.json"))
    );
    validar_schema(
        "chunk.schema.json",
        &serde_json::from_slice(&bruto).unwrap(),
    );
}

#[test]
fn areas_contam_so_ativas_e_total_conta_todas() {
    let mut p = PublicadorMemoria::new();
    rodar(fonte_mista(), &mut p).unwrap();
    let m = manifest(&p);
    // 5420 (PETS) está expirada: fora de `areas`, mas dentro do chunk e do total.
    assert_eq!(m.areas, BTreeMap::from([(Area::Tech, 3), (Area::Elas, 1)]));
    assert_eq!(m.total_ofertas, 5);
}

#[test]
fn headers_e_manifest_por_ultimo() {
    let mut p = PublicadorMemoria::new();
    rodar(fonte_mista(), &mut p).unwrap();
    let m = manifest(&p);
    assert_eq!(p.gravacoes().last().unwrap(), "manifest.json");
    assert_eq!(p.meta("manifest.json"), Some(META_MANIFEST));
    for c in &m.chunks {
        let re = format!("data/chunks/{}-", c.n);
        assert!(c.arquivo.starts_with(&re) && c.arquivo.ends_with(".json.br"));
        assert_eq!(c.arquivo.len(), re.len() + 16 + ".json.br".len());
        assert_eq!(p.meta(&c.arquivo), Some(META_CHUNK));
    }
}

#[test]
fn chunk_acima_do_orcamento_falha_sem_gravar_nada() {
    let linhas: Vec<_> = (1..1000)
        .map(|id| LinhaOferta {
            titulo: Some(texto_aleatorio(id as u64, 200)),
            ..linha(id)
        })
        .collect();
    let mut p = PublicadorMemoria::new();
    let erro = rodar(linhas, &mut p).unwrap_err();
    assert!(
        matches!(erro, ErroGeracao::ChunkAcimaDoOrcamento { n: 0, bytes } if bytes > 61_440),
        "{erro:?}"
    );
    assert!(p.gravacoes().is_empty());
    assert!(!p.existe("manifest.json").unwrap());
}

#[test]
fn orcamento_aceita_61440_e_recusa_61441() {
    assert!(checar_orcamento(0, 61_440).is_ok());
    assert!(matches!(
        checar_orcamento(3, 61_441),
        Err(ErroGeracao::ChunkAcimaDoOrcamento {
            n: 3,
            bytes: 61_441
        })
    ));
}

/// Falha na 2ª gravação de chunk.
struct DiscoCheio {
    dentro: PublicadorMemoria,
    chunks: u32,
}

impl Publicador for DiscoCheio {
    fn existe(&self, chave: &str) -> worker::publicador::Result<bool> {
        self.dentro.existe(chave)
    }
    fn ler(&self, chave: &str) -> worker::publicador::Result<Option<Vec<u8>>> {
        self.dentro.ler(chave)
    }
    fn gravar(&mut self, chave: &str, bytes: &[u8], meta: &Meta) -> worker::publicador::Result<()> {
        if chave.starts_with("data/chunks/") {
            self.chunks += 1;
            if self.chunks == 2 {
                return Err(ErroPublicador::Io {
                    operacao: "gravando",
                    chave: chave.into(),
                    fonte: std::io::Error::other("disco cheio"),
                });
            }
        }
        self.dentro.gravar(chave, bytes, meta)
    }
    fn remover(&mut self, chave: &str) -> worker::publicador::Result<()> {
        self.dentro.remover(chave)
    }
    fn listar(&self, prefixo: &str) -> worker::publicador::Result<Vec<String>> {
        self.dentro.listar(prefixo)
    }
}

#[test]
fn falha_em_chunk_nao_grava_manifest() {
    let mut p = DiscoCheio {
        dentro: PublicadorMemoria::new(),
        chunks: 0,
    };
    let erro = rodar(fonte_mista(), &mut p).unwrap_err();
    assert!(matches!(erro, ErroGeracao::Publicador(_)), "{erro:?}");
    assert!(!p.dentro.existe("manifest.json").unwrap());
}

#[test]
fn relatorio_com_contagens() {
    let mut p = PublicadorMemoria::new();
    let rel = rodar(fonte_mista(), &mut p).unwrap();
    let m = manifest(&p);
    let maior = m.chunks.iter().max_by_key(|c| c.bytes).unwrap();
    assert_eq!(
        rel,
        Relatorio {
            lidas: 7,
            validas: 5,
            rejeitadas: BTreeMap::from([
                (Rejeicao::PrecoPorInvalido, 1),
                (Rejeicao::IdProdutoAusente, 1),
            ]),
            chunks_escritos: 2,
            chunks_reaproveitados: 0,
            chunks_removidos: 0,
            bytes_totais: m.chunks.iter().map(|c| c.bytes).sum(),
            maior_chunk: Some((maior.n, maior.bytes)),
            versao: 20_260_924_124_000,
        }
    );
}

#[test]
fn fonte_vazia_gera_manifest_vazio() {
    let mut p = PublicadorMemoria::new();
    rodar(vec![], &mut p).unwrap();
    let m = manifest(&p);
    assert!(m.chunks.is_empty());
    assert_eq!(m.total_ofertas, 0);
    assert!(m.areas.is_empty());
}

/// URL-03: card sem URL de afiliado não é publicado e conta como rejeição.
#[test]
fn sem_url_de_afiliado_nao_publica_o_card() {
    let mut p = PublicadorMemoria::new();
    let rel = rodar(
        vec![
            LinhaOferta {
                url_afiliado: " ".into(),
                ..linha(2000)
            },
            linha(2001),
        ],
        &mut p,
    )
    .unwrap();
    assert_eq!(
        rel.rejeitadas,
        BTreeMap::from([(Rejeicao::UrlAfiliadoAusente, 1)])
    );
    assert_eq!(rel.validas, 1);
    let m = manifest(&p);
    assert_eq!(m.total_ofertas, 1);
    assert_eq!(m.chunks[0].ids, [2001, 2001]);
}
