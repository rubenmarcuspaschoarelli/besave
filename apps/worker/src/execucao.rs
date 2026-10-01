//! Ciclo agendado (BSV-14): o mesmo `gerar()` do `--publicar --sim`, com a falha classificada
//! (fase + variante), o relatório em uma linha `chave=valor` e o código de saída do Agendador.

use std::fmt;
use std::path::Path;

use tracing::{error, info};

use crate::alerta::Alertas;
use crate::fonte::FonteOfertas;
use crate::geracao::{ErroGeracao, Relatorio};
use crate::mapeamento::Mapeamento;
use crate::plano::publicar;
use crate::publicador::Publicador;
use crate::redirects::Redirects;
use crate::site::ConfigSite;

/// Código de saída lido pelo Agendador de Tarefas.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Codigo {
    /// Sucesso ou ciclo pulado pela trava.
    Ok,
    /// Falha de execução do ciclo.
    Falha,
    /// Configuração ausente ou inválida (env, `.env`).
    Config,
}

impl Codigo {
    pub fn valor(self) -> u8 {
        match self {
            Self::Ok => 0,
            Self::Falha => 1,
            Self::Config => 2,
        }
    }
}

/// Por que o ciclo parou. `erro` (texto completo) só vai para o log; o alerta usa `variante`.
#[derive(Debug)]
pub struct Falha {
    pub codigo: Codigo,
    pub fase: &'static str,
    pub variante: String,
    pub erro: String,
}

impl Falha {
    pub fn config(fase: &'static str, erro: &(impl fmt::Debug + fmt::Display)) -> Self {
        Self::nova(Codigo::Config, fase, erro)
    }

    pub fn execucao(fase: &'static str, erro: &(impl fmt::Debug + fmt::Display)) -> Self {
        Self::nova(Codigo::Falha, fase, erro)
    }

    fn nova(codigo: Codigo, fase: &'static str, erro: &(impl fmt::Debug + fmt::Display)) -> Self {
        Self {
            codigo,
            fase,
            variante: variante_de(erro),
            erro: erro.to_string(),
        }
    }

    /// A variante de topo de `ErroGeracao` diz o módulo de `gerar()` onde o ciclo parou.
    pub fn de_geracao(e: &ErroGeracao) -> Self {
        let fase = match e {
            ErroGeracao::Fonte(_) => "leitura_fonte",
            ErroGeracao::Imagens(_) => "imagens",
            ErroGeracao::Chunk(_) | ErroGeracao::ChunkAcimaDoOrcamento { .. } => "chunks",
            ErroGeracao::Site(_) => "paginas",
            ErroGeracao::Redirects(_) => "redirects",
            ErroGeracao::ManifestAnteriorInvalido(_)
            | ErroGeracao::Manifest(_)
            | ErroGeracao::VersaoContrato => "manifest",
            ErroGeracao::Publicador(_) => "s3",
        };
        Self::execucao(fase, e)
    }
}

/// Até 2 identificadores do `Debug` (`Redirects(Kvs { … })` → `Redirects::Kvs`). Nunca carrega
/// dado do erro (URL, caminho, token): só `[A-Za-z0-9_]`.
pub fn variante_de(e: &dyn fmt::Debug) -> String {
    let d = format!("{e:?}");
    let mut partes = Vec::new();
    let mut resto = d.as_str();
    while partes.len() < 2 {
        let fim = resto
            .find(|c: char| !(c.is_ascii_alphanumeric() || c == '_'))
            .unwrap_or(resto.len());
        if fim == 0 {
            break;
        }
        partes.push(&resto[..fim]);
        match resto[fim..].strip_prefix('(') {
            Some(r) => resto = r,
            None => break,
        }
    }
    if partes.is_empty() {
        "Desconhecido".to_owned()
    } else {
        partes.join("::")
    }
}

/// `--publicar --sim`: escreve no destino.
pub fn rodar(
    fonte: &dyn FonteOfertas,
    m: &Mapeamento,
    pub_: &mut dyn Publicador,
    kvs: &mut dyn Redirects,
    dir_imagens: &Path,
    site: &ConfigSite,
    agora: i64,
) -> Result<Relatorio, Falha> {
    publicar(fonte, m, pub_, kvs, dir_imagens, site, agora, true)
        .map(|p| p.relatorio)
        .map_err(|e| Falha::de_geracao(&e))
}

/// Relatório do ciclo em pares `chave=valor` separados por espaço.
pub fn linha_relatorio(rel: &Relatorio, tempo_ms: u64) -> String {
    let t = &rel.tempos;
    let pag = &rel.site.paginas;
    let pares: [(&str, String); 26] = [
        ("lidas", rel.lidas.to_string()),
        ("validas", rel.validas.to_string()),
        (
            "rejeitadas",
            rel.rejeitadas.values().sum::<u64>().to_string(),
        ),
        ("chunks_escritos", rel.chunks_escritos.to_string()),
        (
            "chunks_reaproveitados",
            rel.chunks_reaproveitados.to_string(),
        ),
        ("chunks_removidos", rel.chunks_removidos.to_string()),
        ("bytes_totais", rel.bytes_totais.to_string()),
        ("versao", rel.versao.to_string()),
        ("redirects_modo", rel.redirects.modo.to_string()),
        ("redirects_put", rel.redirects.puts.to_string()),
        ("redirects_del", rel.redirects.dels.to_string()),
        ("redirects_total", rel.redirects.total.to_string()),
        ("imagens_publicadas", rel.imagens.publicadas.to_string()),
        ("imagens_falhas", rel.imagens.falhas.len().to_string()),
        ("paginas_publicadas", pag.publicadas.to_string()),
        ("paginas_removidas", pag.removidas.to_string()),
        ("paginas_falhas", pag.falhas.len().to_string()),
        ("t_leitura_fonte", t.leitura_fonte.to_string()),
        ("t_imagens", t.imagens.to_string()),
        ("t_chunks", t.chunks.to_string()),
        ("t_paginas", t.paginas.to_string()),
        ("t_redirects", t.redirects.to_string()),
        ("t_redirects_listagem", t.redirects_listagem.to_string()),
        ("t_manifest", t.manifest.to_string()),
        ("t_orfaos", t.orfaos.to_string()),
        ("tempo_ms", tempo_ms.to_string()),
    ];
    pares
        .iter()
        .map(|(k, v)| format!("{k}={v}"))
        .collect::<Vec<_>>()
        .join(" ")
}

/// Loga o resultado, avisa o Telegram (se ligado) e devolve o código de saída. O alerta nunca
/// muda o código.
pub fn concluir(
    resultado: Result<(Relatorio, u64), Falha>,
    alertas: Option<&Alertas>,
    agora: i64,
) -> Codigo {
    match resultado {
        Ok((rel, tempo_ms)) => {
            info!("relatorio {}", linha_relatorio(&rel, tempo_ms));
            if let Some(a) = alertas {
                a.sucesso(agora);
            }
            Codigo::Ok
        }
        Err(f) => {
            error!(
                fase = %f.fase,
                variante = %f.variante,
                erro = %f.erro,
                "falha no ciclo"
            );
            if let Some(a) = alertas {
                a.falha(&f.variante, f.fase, agora);
            }
            f.codigo
        }
    }
}
