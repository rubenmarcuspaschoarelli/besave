//! `FonteEnvio` sobre Oracle XE 11.2 (`sql/bsv-40.sql`). Colunas DATE em hora local
//! (`BESAVE_ORACLE_TZ`): o worker converte com o mesmo offset do ciclo. Toda escrita faz commit.

use std::collections::{HashMap, HashSet};

use oracle::Connection;
use oracle::sql_type::ToSql;

use crate::envio::fonte::{AvisoCanal, Expirada, FonteEnvio, UltimoEnvio};
use crate::envio::modelo::{Canal, LinhaCanal, OfertaCanal, Parametros};
use crate::fonte::Result;
use crate::oracle::{ConfigOracle, blocos_in, conectar, linha_aviso, linha_oferta};

/// Colunas de OFERTA para o canal: as 15 de `SQL_OFERTAS` (lidas por `linha_oferta`) + destaque,
/// recorrência e `DT_PUBLICACAO_SITE`. Datas em segundos Unix UTC (`:desloc` = offset local).
const COLUNAS_CANAL: &str = "o.ID_OFERTA, o.ID_PRODUTO, o.DS_LOJA, o.DS_TITULO, o.VL_PRECO_DE, \
     o.VL_PRECO_POR, o.DS_CUPOM, o.NR_NOTA_AVALIACAO, o.QT_AVALIACAO, \
     ROUND((o.DT_OFERTA - DATE '1970-01-01') * 86400) - :desloc, o.DS_COMUNIDADE, o.DS_PUBLICO, \
     CASE WHEN o.ST_ATIVO = 1 THEN 1 ELSE 0 END, \
     ROUND((o.DT_DESATIVACAO - DATE '1970-01-01') * 86400) - :desloc, o.DS_URL_AFILIADO, \
     o.DS_OFERTA_DESTAQUE, CASE WHEN o.ST_RECORRENCIA = 1 THEN 1 ELSE 0 END, \
     ROUND((o.DT_PUBLICACAO_SITE - DATE '1970-01-01') * 86400) - :desloc";

/// Segundos locais (`:n`) → DATE.
const DATA_LOCAL: &str = "DATE '1970-01-01' + :n / 86400";

pub fn sql_candidatas() -> String {
    format!(
        "SELECT {COLUNAS_CANAL} FROM OFERTA o \
         WHERE o.ST_ATIVO = 1 AND o.DT_PUBLICACAO_SITE IS NOT NULL \
         AND o.DT_OFERTA >= {} \
         AND NOT EXISTS (SELECT 1 FROM ENVIO_TELEGRAM e \
                         WHERE e.ID_CANAL = :canal AND e.ID_OFERTA = o.ID_OFERTA)",
        DATA_LOCAL.replace(":n", ":desde")
    )
}

/// Sem `ORDER BY`: `ROWNUM` direto (uma subconsulta com `SELECT *` exigiria alias em cada
/// expressão); a ordem das edições não importa.
pub fn sql_expiradas() -> String {
    format!(
        "SELECT {COLUNAS_CANAL}, e.ID_ENVIO, e.NR_MESSAGE_ID          FROM ENVIO_TELEGRAM e JOIN OFERTA o ON o.ID_OFERTA = e.ID_OFERTA          WHERE e.ID_CANAL = :canal AND e.NR_MESSAGE_ID IS NOT NULL AND e.DT_EDICAO IS NULL          AND o.ST_ATIVO = 0 AND ROWNUM <= :limite"
    )
}

/// `:1` canal, `:2..` ids.
pub fn sql_enviadas(n: usize) -> String {
    let binds: Vec<String> = (2..=n + 1).map(|i| format!(":{i}")).collect();
    format!(
        "SELECT ID_OFERTA FROM ENVIO_TELEGRAM WHERE ID_CANAL = :1 AND ID_OFERTA IN ({})",
        binds.join(", ")
    )
}

/// `:1` canal, `:2` desde (segundos locais), `:3..` ids de produto. Data em segundos locais.
pub fn sql_ultimos(n: usize) -> String {
    let binds: Vec<String> = (3..=n + 2).map(|i| format!(":{i}")).collect();
    format!(
        "SELECT ID_PRODUTO, VL_PRECO_POR, ROUND((DT_ENVIO - DATE '1970-01-01') * 86400) \
         FROM ENVIO_TELEGRAM WHERE ID_CANAL = :1 AND DT_ENVIO >= DATE '1970-01-01' + :2 / 86400 \
         AND ID_PRODUTO IN ({})",
        binds.join(", ")
    )
}

const SQL_CANAL: &str = "SELECT DS_CHAT_ID, ST_ATIVO FROM CANAL_ENVIO WHERE ID_CANAL = :1";
const SQL_PARAMETROS: &str = "SELECT QT_MAX_DIA, QT_POR_EXECUCAO, NR_HORA_INICIO, NR_HORA_FIM, \
     NR_HORA_SOM_INICIO, NR_HORA_SOM_FIM, PC_DESCONTO_MIN, NR_HORAS_OFERTA_MAX, NR_DIAS_REPETICAO, \
     PC_QUEDA_REPETICAO, PC_DESCONTO_DESTAQUE FROM PARAMETROS_ENVIO WHERE ID_CANAL = :1";
const SQL_ENVIADOS_DESDE: &str = "SELECT COUNT(*) FROM ENVIO_TELEGRAM \
     WHERE ID_CANAL = :1 AND DT_ENVIO >= DATE '1970-01-01' + :2 / 86400";
const SQL_SEQUENCIA: &str = "SELECT SQ_ENVIO_TELEGRAM.NEXTVAL FROM DUAL";
const SQL_RESERVAR: &str = "INSERT INTO ENVIO_TELEGRAM \
     (ID_ENVIO, ID_CANAL, ID_OFERTA, ID_PRODUTO, VL_PRECO_POR, DT_ENVIO) \
     VALUES (:1, :2, :3, :4, :5, DATE '1970-01-01' + :6 / 86400)";
const SQL_CONFIRMAR: &str = "UPDATE ENVIO_TELEGRAM SET NR_MESSAGE_ID = :1 WHERE ID_ENVIO = :2";
const SQL_CANCELAR: &str = "DELETE FROM ENVIO_TELEGRAM WHERE ID_ENVIO = :1";
const SQL_EDITADA: &str = "UPDATE ENVIO_TELEGRAM SET DT_EDICAO = DATE '1970-01-01' + :1 / 86400 \
     WHERE ID_ENVIO = :2";

/// Ligações ativas do canal com aviso ativo e no ar (BSV-41). As 9 primeiras colunas na ordem de
/// `oracle::SQL_AVISOS` (lidas por `linha_aviso`); depois intervalo, ligação ativa e último envio.
pub const SQL_AVISOS_CANAL: &str = "SELECT a.ID_AVISO, a.DS_TITULO, a.DS_TEXTO, a.DS_IMAGEM,      a.DS_LINK_INTERNO, CASE WHEN a.ST_ATIVO = 1 THEN 1 ELSE 0 END,      ROUND((a.DT_INICIO - DATE '1970-01-01') * 86400) - :desloc,      ROUND((a.DT_FIM - DATE '1970-01-01') * 86400) - :desloc,      ROUND((a.DT_PUBLICACAO_SITE - DATE '1970-01-01') * 86400) - :desloc,      ac.NR_INTERVALO_MIN, CASE WHEN ac.ST_ATIVO = 1 THEN 1 ELSE 0 END,      (SELECT ROUND((MAX(e.DT_ENVIO) - DATE '1970-01-01') * 86400) - :desloc FROM ENVIO_AVISO e       WHERE e.ID_AVISO = a.ID_AVISO AND e.ID_CANAL = ac.ID_CANAL)      FROM AVISO_CANAL ac JOIN AVISO a ON a.ID_AVISO = ac.ID_AVISO      WHERE ac.ID_CANAL = :canal AND ac.ST_ATIVO = 1 AND a.ST_ATIVO = 1      AND a.DT_PUBLICACAO_SITE IS NOT NULL";
const SQL_SEQUENCIA_AVISO: &str = "SELECT SQ_ENVIO_AVISO.NEXTVAL FROM DUAL";
const SQL_RESERVAR_AVISO: &str = "INSERT INTO ENVIO_AVISO (ID_ENVIO_AVISO, ID_AVISO, ID_CANAL, DT_ENVIO)      VALUES (:1, :2, :3, DATE '1970-01-01' + :4 / 86400)";
const SQL_CONFIRMAR_AVISO: &str =
    "UPDATE ENVIO_AVISO SET NR_MESSAGE_ID = :1 WHERE ID_ENVIO_AVISO = :2";
const SQL_CANCELAR_AVISO: &str = "DELETE FROM ENVIO_AVISO WHERE ID_ENVIO_AVISO = :1";

pub struct OracleEnvio {
    conn: Connection,
    fuso_segundos: i64,
}

impl OracleEnvio {
    pub fn conectar(cfg: &ConfigOracle) -> Result<Self> {
        Ok(Self {
            conn: conectar(cfg)?,
            fuso_segundos: cfg.fuso_segundos,
        })
    }

    /// Segundos Unix UTC → segundos "locais" (o que a coluna DATE guarda).
    fn local(&self, t: i64) -> i64 {
        t + self.fuso_segundos
    }

    fn linha_canal(r: &oracle::Row) -> Result<LinhaCanal> {
        Ok(LinhaCanal {
            oferta: linha_oferta(r)?,
            destaque: r.get(15)?,
            recorrencia: r.get::<_, i64>(16)? == 1,
            dt_publicacao_site: r.get(17)?,
        })
    }
}

impl FonteEnvio for OracleEnvio {
    fn canal(&self, id: i64) -> Result<Option<Canal>> {
        let mut linhas = self.conn.query(SQL_CANAL, &[&id])?;
        linhas
            .next()
            .transpose()?
            .map(|r| {
                Ok(Canal {
                    id,
                    chat_id: r.get(0)?,
                    ativo: r.get::<_, i64>(1)? == 1,
                })
            })
            .transpose()
    }

    fn parametros(&self, canal: i64) -> Result<Option<Parametros>> {
        let mut linhas = self.conn.query(SQL_PARAMETROS, &[&canal])?;
        linhas
            .next()
            .transpose()?
            .map(|r| {
                Ok(Parametros {
                    qt_max_dia: r.get(0)?,
                    qt_por_execucao: r.get(1)?,
                    hora_inicio: r.get(2)?,
                    hora_fim: r.get(3)?,
                    hora_som_inicio: r.get(4)?,
                    hora_som_fim: r.get(5)?,
                    pc_desconto_min: r.get(6)?,
                    horas_oferta_max: r.get(7)?,
                    dias_repeticao: r.get(8)?,
                    pc_queda_repeticao: r.get(9)?,
                    pc_desconto_destaque: r.get(10)?,
                })
            })
            .transpose()
    }

    fn candidatas(&self, canal: i64, desde: i64) -> Result<Vec<LinhaCanal>> {
        let linhas = self.conn.query_named(
            &sql_candidatas(),
            &[
                ("desloc", &self.fuso_segundos),
                ("desde", &self.local(desde)),
                ("canal", &canal),
            ],
        )?;
        linhas.map(|r| Self::linha_canal(&r?)).collect()
    }

    fn enviadas(&self, canal: i64, ids: &[i64]) -> Result<HashSet<i64>> {
        let mut out = HashSet::new();
        for bloco in blocos_in(ids) {
            let mut params: Vec<&dyn ToSql> = vec![&canal];
            params.extend(bloco.iter().map(|id| id as &dyn ToSql));
            for r in self.conn.query(&sql_enviadas(bloco.len()), &params)? {
                out.insert(r?.get(0)?);
            }
        }
        Ok(out)
    }

    fn ultimos_por_produto(
        &self,
        canal: i64,
        ids_produto: &[i64],
        desde: i64,
    ) -> Result<HashMap<i64, UltimoEnvio>> {
        let desde_local = self.local(desde);
        let mut out: HashMap<i64, UltimoEnvio> = HashMap::new();
        for bloco in blocos_in(ids_produto) {
            let mut params: Vec<&dyn ToSql> = vec![&canal, &desde_local];
            params.extend(bloco.iter().map(|id| id as &dyn ToSql));
            for r in self.conn.query(&sql_ultimos(bloco.len()), &params)? {
                let r = r?;
                let produto: i64 = r.get(0)?;
                let preco: Option<f64> = r.get(1)?;
                let local: i64 = r.get(2)?;
                let u = UltimoEnvio {
                    preco_por: preco.map_or(0, crate::conversao::centavos),
                    dt_envio: local - self.fuso_segundos,
                };
                let atual = out.entry(produto).or_insert(u);
                if u.dt_envio > atual.dt_envio {
                    *atual = u;
                }
            }
        }
        Ok(out)
    }

    fn enviados_desde(&self, canal: i64, desde: i64) -> Result<u64> {
        let n: i64 = self
            .conn
            .query_row_as(SQL_ENVIADOS_DESDE, &[&canal, &self.local(desde)])?;
        Ok(u64::try_from(n).unwrap_or(0))
    }

    fn reservar(&self, canal: i64, o: &OfertaCanal, agora: i64) -> Result<i64> {
        let id: i64 = self.conn.query_row_as(SQL_SEQUENCIA, &[])?;
        // Mesma unidade de OFERTA.VL_PRECO_POR (reais).
        let preco = o.preco_por as f64 / 100.0;
        self.conn.execute(
            SQL_RESERVAR,
            &[
                &id,
                &canal,
                &o.id,
                &o.id_produto,
                &preco,
                &self.local(agora),
            ],
        )?;
        self.conn.commit()?;
        Ok(id)
    }

    fn confirmar(&self, id_envio: i64, message_id: i64) -> Result<()> {
        self.conn
            .execute(SQL_CONFIRMAR, &[&message_id, &id_envio])?;
        Ok(self.conn.commit()?)
    }

    fn cancelar(&self, id_envio: i64) -> Result<()> {
        self.conn.execute(SQL_CANCELAR, &[&id_envio])?;
        Ok(self.conn.commit()?)
    }

    fn expiradas(&self, canal: i64, limite: usize) -> Result<Vec<Expirada>> {
        let limite = i64::try_from(limite).unwrap_or(i64::MAX);
        let linhas = self.conn.query_named(
            &sql_expiradas(),
            &[
                ("desloc", &self.fuso_segundos),
                ("canal", &canal),
                ("limite", &limite),
            ],
        )?;
        linhas
            .map(|r| {
                let r = r?;
                Ok(Expirada {
                    linha: Self::linha_canal(&r)?,
                    id_envio: r.get(18)?,
                    message_id: r.get(19)?,
                })
            })
            .collect()
    }

    fn marcar_editada(&self, id_envio: i64, agora: i64) -> Result<()> {
        self.conn
            .execute(SQL_EDITADA, &[&self.local(agora), &id_envio])?;
        Ok(self.conn.commit()?)
    }

    fn avisos_canal(&self, canal: i64) -> Result<Vec<AvisoCanal>> {
        let linhas = self.conn.query_named(
            SQL_AVISOS_CANAL,
            &[("desloc", &self.fuso_segundos), ("canal", &canal)],
        )?;
        linhas
            .map(|r| {
                let r = r?;
                Ok(AvisoCanal {
                    aviso: linha_aviso(&r)?,
                    intervalo_min: r.get(9)?,
                    ativo: r.get::<_, i64>(10)? == 1,
                    ultimo_envio: r.get(11)?,
                })
            })
            .collect()
    }

    fn reservar_aviso(&self, aviso: i64, canal: i64, agora: i64) -> Result<i64> {
        let id: i64 = self.conn.query_row_as(SQL_SEQUENCIA_AVISO, &[])?;
        self.conn.execute(
            SQL_RESERVAR_AVISO,
            &[&id, &aviso, &canal, &self.local(agora)],
        )?;
        self.conn.commit()?;
        Ok(id)
    }

    fn confirmar_aviso(&self, id_envio: i64, message_id: i64) -> Result<()> {
        self.conn
            .execute(SQL_CONFIRMAR_AVISO, &[&message_id, &id_envio])?;
        Ok(self.conn.commit()?)
    }

    fn cancelar_aviso(&self, id_envio: i64) -> Result<()> {
        self.conn.execute(SQL_CANCELAR_AVISO, &[&id_envio])?;
        Ok(self.conn.commit()?)
    }
}
