//! PLN-01..03: `publicar` sem `--sim` só planeja; com `--sim` escreve.

mod comum;

use std::collections::BTreeMap;

use comum::{AGORA, linha, mapeamento};
use worker::conversao::LinhaOferta;
use worker::fonte::FakeFonte;
use worker::geracao::gerar;
use worker::plano::{Operacao, Publicacao, publicar};
use worker::publicador::{Meta, Publicador, PublicadorMemoria};
use worker::redirects::{Redirects, RedirectsMemoria};

/// Destino que conta cada chamada de escrita.
#[derive(Default)]
struct PubEspiao {
    dentro: PublicadorMemoria,
    gravar: u32,
    remover: u32,
}

impl Publicador for PubEspiao {
    fn existe(&self, chave: &str) -> worker::publicador::Result<bool> {
        self.dentro.existe(chave)
    }
    fn ler(&self, chave: &str) -> worker::publicador::Result<Option<Vec<u8>>> {
        self.dentro.ler(chave)
    }
    fn gravar(&mut self, chave: &str, bytes: &[u8], meta: &Meta) -> worker::publicador::Result<()> {
        self.gravar += 1;
        self.dentro.gravar(chave, bytes, meta)
    }
    fn remover(&mut self, chave: &str) -> worker::publicador::Result<()> {
        self.remover += 1;
        self.dentro.remover(chave)
    }
    fn listar(&self, prefixo: &str) -> worker::publicador::Result<Vec<String>> {
        self.dentro.listar(prefixo)
    }
}

#[derive(Default)]
struct KvsEspiao {
    dentro: RedirectsMemoria,
    aplicar: u32,
}

impl Redirects for KvsEspiao {
    fn listar(&self) -> worker::redirects::Result<BTreeMap<i64, String>> {
        self.dentro.listar()
    }
    fn aplicar(&mut self, put: &[(i64, String)], del: &[i64]) -> worker::redirects::Result<()> {
        self.aplicar += 1;
        self.dentro.aplicar(put, del)
    }
}

fn url(id: i64) -> String {
    format!("https://loja.example/{id}")
}

fn titulo(id: i64, t: &str) -> LinhaOferta {
    LinhaOferta {
        titulo: Some(t.into()),
        ..linha(id)
    }
}

/// Destino com dois ciclos já publicados: o chunk 1 do 1º ciclo (`orfao`) só é órfão no 3º.
/// Devolve o destino e a chave desse chunk.
fn destino() -> (PubEspiao, KvsEspiao, String) {
    let m = mapeamento();
    let mut p = PublicadorMemoria::new();
    let mut kvs = RedirectsMemoria::new();
    let f1 = FakeFonte::new(vec![linha(1001), linha(5412), linha(5413)], vec![], AGORA);
    gerar(&f1, &m, &mut p, &mut kvs, AGORA).unwrap();
    let orfao = p.listar("data/chunks/1-").unwrap().remove(0);
    let f2 = FakeFonte::new(
        vec![titulo(1001, "Nova"), linha(5412), linha(5413)],
        vec![],
        AGORA,
    );
    gerar(&f2, &m, &mut p, &mut kvs, AGORA + 600).unwrap();
    (
        PubEspiao {
            dentro: p,
            ..Default::default()
        },
        KvsEspiao {
            dentro: kvs,
            ..Default::default()
        },
        orfao,
    )
}

/// 3º ciclo: entra 2001 (chunk 2 novo), sai 5413 (chunk 5 muda).
fn terceiro(p: &mut PubEspiao, kvs: &mut KvsEspiao, sim: bool) -> Publicacao {
    let f3 = FakeFonte::new(
        vec![titulo(1001, "Nova"), linha(2001), linha(5412)],
        vec![],
        AGORA,
    );
    publicar(&f3, &mapeamento(), p, kvs, AGORA + 1200, sim).unwrap()
}

#[test]
fn plano_nao_chama_escrita_no_destino() {
    let (mut p, mut kvs, _) = destino();
    let manifest = p.dentro.ler("manifest.json").unwrap();
    let chaves = p.dentro.listar("").unwrap();
    let estado_kvs = kvs.dentro.chaves();

    terceiro(&mut p, &mut kvs, false);

    assert_eq!((p.gravar, p.remover, kvs.aplicar), (0, 0, 0));
    assert_eq!(p.dentro.ler("manifest.json").unwrap(), manifest);
    assert_eq!(p.dentro.listar("").unwrap(), chaves);
    assert_eq!(kvs.dentro.chaves(), estado_kvs);
}

#[test]
fn plano_lista_gravacoes_remocoes_e_chaves() {
    let (mut p, mut kvs, orfao) = destino();
    let pb = terceiro(&mut p, &mut kvs, false);
    let ops = pb.plano.objetos;

    let gravadas: Vec<&Operacao> = ops
        .iter()
        .filter(|o| matches!(o, Operacao::Gravar { .. }))
        .collect();
    let chunk2 = gravadas
        .iter()
        .find_map(|o| match o {
            Operacao::Gravar {
                chave,
                bytes,
                cache_control,
            } if chave.starts_with("data/chunks/2-") => {
                Some((chave.clone(), *bytes, *cache_control))
            }
            _ => None,
        })
        .unwrap_or_else(|| panic!("{ops:?}"));
    assert!(chunk2.1 > 0);
    assert_eq!(chunk2.2, "public, max-age=31536000, immutable");
    assert!(gravadas.iter().any(|o| matches!(o,
        Operacao::Gravar { chave, cache_control, .. }
            if chave.starts_with("data/chunks/5-")
                && *cache_control == "public, max-age=31536000, immutable")));
    let ultimas: Vec<(&str, &str)> = gravadas[gravadas.len() - 2..]
        .iter()
        .map(|o| match o {
            Operacao::Gravar {
                chave,
                cache_control,
                ..
            } => (chave.as_str(), *cache_control),
            _ => unreachable!(),
        })
        .collect();
    let curto = "public, max-age=300, stale-while-revalidate=60";
    assert_eq!(
        ultimas,
        [("manifest.prev.json", curto), ("manifest.json", curto)]
    );
    assert!(
        ops.contains(&Operacao::Remover {
            chave: orfao.clone()
        }),
        "{ops:?}"
    );
    assert_eq!(
        ops.iter()
            .filter(|o| matches!(o, Operacao::Remover { .. }))
            .count(),
        1,
        "{ops:?}"
    );

    assert_eq!(
        pb.plano.redirects,
        [
            Operacao::PutKey {
                id: 2001,
                url: url(2001)
            },
            Operacao::DeleteKey { id: 5413 },
        ]
    );
    assert_eq!(pb.relatorio.redirects.puts, 1);
    assert_eq!(pb.relatorio.redirects.dels, 1);

    let texto: Vec<String> = pb.plano.redirects.iter().map(ToString::to_string).collect();
    assert_eq!(
        texto,
        [
            format!("putKey 2001 {}", url(2001)),
            "deleteKey 5413".into()
        ]
    );
    assert_eq!(
        Operacao::Remover {
            chave: orfao.clone()
        }
        .to_string(),
        format!("remover {orfao}")
    );
    assert_eq!(
        Operacao::Gravar {
            chave: chunk2.0.clone(),
            bytes: chunk2.1,
            cache_control: chunk2.2
        }
        .to_string(),
        format!(
            "gravar {} ({} B, public, max-age=31536000, immutable)",
            chunk2.0, chunk2.1
        )
    );
}

#[test]
fn sim_escreve_no_destino_e_plano_vem_vazio() {
    let (mut p, mut kvs, orfao) = destino();
    let pb = terceiro(&mut p, &mut kvs, true);

    assert!(pb.plano.objetos.is_empty());
    assert!(pb.plano.redirects.is_empty());
    assert!(p.gravar >= 4, "chunks 2 e 5 + manifests: {}", p.gravar);
    assert_eq!(p.remover, 1);
    assert_eq!(kvs.aplicar, 1);
    assert!(!p.dentro.existe(&orfao).unwrap());
    assert_eq!(
        kvs.dentro.listar().unwrap().into_keys().collect::<Vec<_>>(),
        [1001, 2001, 5412]
    );
    assert!(p.dentro.listar("data/chunks/2-").unwrap().len() == 1);
}

/// PLN-04: plano direto contra `PublicadorMemoria` + `RedirectsMemoria` (que registram
/// gravações, remoções e `aplicar`): nada muda, e o texto impresso lista o previsto.
#[test]
fn plano_contra_memoria_registra_zero_escritas_e_lista_previsto() {
    let (espiao, kvs_espiao, orfao) = destino();
    let (mut p, mut kvs) = (espiao.dentro, kvs_espiao.dentro);
    let (gravacoes, remocoes, aplicados) = (
        p.gravacoes().len(),
        p.remocoes().len(),
        kvs.aplicados().len(),
    );
    assert!(remocoes == 0 && aplicados > 0, "destino sem histórico");

    let f3 = FakeFonte::new(
        vec![titulo(1001, "Nova"), linha(2001), linha(5412)],
        vec![],
        AGORA,
    );
    let pb = publicar(&f3, &mapeamento(), &mut p, &mut kvs, AGORA + 1200, false).unwrap();

    assert_eq!(p.gravacoes().len(), gravacoes);
    assert_eq!(p.remocoes().len(), remocoes);
    assert_eq!(kvs.aplicados().len(), aplicados);

    let linhas = pb.plano.linhas();
    for l in &linhas {
        println!("{l}");
    }
    let s3 = linhas.iter().position(|l| l == "S3:").unwrap();
    let kvs_em = linhas.iter().position(|l| l.starts_with("KVS")).unwrap();
    assert!(s3 < kvs_em, "{linhas:?}");
    let objetos: Vec<&str> = linhas[s3 + 1..kvs_em].iter().map(|l| l.trim()).collect();
    let chaves: Vec<&str> = linhas[kvs_em + 1..].iter().map(|l| l.trim()).collect();
    let tem = |prefixo: &str| objetos.iter().any(|l| l.starts_with(prefixo));
    assert!(tem("gravar data/chunks/2-"), "{linhas:?}");
    assert!(tem("gravar data/chunks/5-"), "{linhas:?}");
    let n = objetos.len();
    assert!(
        objetos[n - 3].starts_with("gravar manifest.prev.json ("),
        "{linhas:?}"
    );
    assert!(
        objetos[n - 2].starts_with("gravar manifest.json ("),
        "{linhas:?}"
    );
    assert_eq!(objetos[n - 1], format!("remover {orfao}"));
    assert_eq!(
        chaves,
        [
            format!("putKey 2001 {}", url(2001)),
            "deleteKey 5413".to_owned()
        ]
    );
}
