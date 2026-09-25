//! `FonteOfertas` sobre Oracle XE 11.2 (crate `oracle`, OCI via Instant Client ≥ 19).

use oracle::{Connection, Row};

use crate::conversao::{LinhaOferta, LinhaProduto};
use crate::fonte::{ErroFonte, FonteOfertas, Result};

/// Fuso das colunas DATE (os robôs gravam hora local). Offset fixo: o arquivo de fuso do
/// XE 11.2 ainda aplica horário de verão em America/Sao_Paulo.
const FUSO_PADRAO: &str = "-03:00";

/// Credenciais só por env; nunca em arquivo versionado. Sem `Debug` para não vazar a senha.
pub struct ConfigOracle {
    pub dsn: String,
    pub usuario: String,
    senha: String,
    /// `BESAVE_ORACLE_TZ`, opcional.
    pub fuso: String,
}

impl ConfigOracle {
    pub fn do_env() -> Result<Self> {
        Self::de(|k| std::env::var(k).ok())
    }

    pub fn de(env: impl Fn(&str) -> Option<String>) -> Result<Self> {
        let obrig = |k: &'static str| {
            env(k)
                .filter(|v| !v.is_empty())
                .ok_or(ErroFonte::ConfigAusente(k))
        };
        Ok(Self {
            dsn: obrig("BESAVE_ORACLE_DSN")?,
            usuario: obrig("BESAVE_ORACLE_USER")?,
            senha: obrig("BESAVE_ORACLE_PASS")?,
            fuso: env("BESAVE_ORACLE_TZ")
                .filter(|v| !v.is_empty())
                .unwrap_or_else(|| FUSO_PADRAO.to_owned()),
        })
    }
}

pub struct OracleFonte {
    conn: Connection,
    fuso: String,
}

impl OracleFonte {
    pub fn conectar(cfg: &ConfigOracle) -> Result<Self> {
        let conn = Connection::connect(&cfg.usuario, &cfg.senha, &cfg.dsn)?;
        Ok(Self {
            conn,
            fuso: cfg.fuso.clone(),
        })
    }
}

/// DATE local → segundos Unix UTC.
macro_rules! epoch_utc {
    ($col:literal) => {
        concat!(
            "ROUND((CAST(SYS_EXTRACT_UTC(FROM_TZ(CAST(",
            $col,
            " AS TIMESTAMP), :tz)) AS DATE) - DATE '1970-01-01') * 86400)"
        )
    };
}

/// Query de publicação (CONTRATO §7). `DT_ULT_ATUALIZACAO` não é lida.
const SQL_OFERTAS: &str = concat!(
    "SELECT ID_OFERTA, ID_PRODUTO, DS_LOJA, DS_TITULO, VL_PRECO_DE, VL_PRECO_POR, DS_CUPOM, ",
    "NR_NOTA_AVALIACAO, QT_AVALIACAO, ",
    epoch_utc!("DT_OFERTA"),
    ", DS_COMUNIDADE, DS_PUBLICO, CASE WHEN ST_ATIVO = 1 THEN 1 ELSE 0 END, ",
    epoch_utc!("DT_DESATIVACAO"),
    " FROM OFERTA WHERE ST_ATIVO = 1 OR DT_DESATIVACAO >= SYSDATE - 7 ORDER BY ID_OFERTA"
);

const SQL_PRODUTO: &str = "SELECT ID_PRODUTO, DS_DESCRICAO_PRODUTO, DS_MARCA, DS_FABRICANTE, \
     DS_MODELO, DS_PAIS_ORIGEM, DS_GENERO, DS_FAIXA_ETARIA, VR_PRECO_MINIMO, VR_PRECO_MAXIMO \
     FROM PRODUTO WHERE ID_PRODUTO = :id";

impl FonteOfertas for OracleFonte {
    fn ofertas(&self) -> Result<Vec<LinhaOferta>> {
        let linhas = self.conn.query_named(SQL_OFERTAS, &[("tz", &self.fuso)])?;
        linhas.map(|r| linha_oferta(&r?)).collect()
    }

    fn produto(&self, id_produto: i64) -> Result<Option<LinhaProduto>> {
        let mut linhas = self.conn.query_named(SQL_PRODUTO, &[("id", &id_produto)])?;
        linhas
            .next()
            .transpose()?
            .map(|r| linha_produto(&r))
            .transpose()
    }
}

fn linha_oferta(r: &Row) -> Result<LinhaOferta> {
    Ok(LinhaOferta {
        id: r.get(0)?,
        id_produto: r.get(1)?,
        loja: r.get(2)?,
        titulo: r.get(3)?,
        preco_de: r.get(4)?,
        preco_por: r.get(5)?,
        cupom: r.get(6)?,
        nota: r.get(7)?,
        qt_avaliacoes: r.get(8)?,
        dt_oferta: r.get(9)?,
        area: r.get(10)?,
        publico: r.get(11)?,
        ativo: r.get::<_, i64>(12)? == 1,
        dt_desativacao: r.get(13)?,
    })
}

fn linha_produto(r: &Row) -> Result<LinhaProduto> {
    Ok(LinhaProduto {
        id_produto: r.get(0)?,
        descricao: r.get(1)?,
        marca: r.get(2)?,
        fabricante: r.get(3)?,
        modelo: r.get(4)?,
        pais_origem: r.get(5)?,
        genero: r.get(6)?,
        faixa_etaria: r.get(7)?,
        preco_min: r.get(8)?,
        preco_max: r.get(9)?,
    })
}
