//! Fronteira do envio com o Oracle (`CANAL_ENVIO`, `PARAMETROS_ENVIO`, `ENVIO_TELEGRAM`, OFERTA).
//! Datas em segundos Unix UTC; preços em centavos.

use std::cell::{Cell, RefCell};
use std::collections::{HashMap, HashSet};

use crate::avisos::modelo::LinhaAviso;
use crate::envio::modelo::{Canal, LinhaCanal, OfertaCanal, Parametros};
use crate::fonte::{ErroFonte, Result};

/// Último envio de um produto ao canal.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct UltimoEnvio {
    pub preco_por: i64,
    pub dt_envio: i64,
}

/// Post confirmado de uma oferta que expirou e ainda não foi editado.
#[derive(Debug, Clone, PartialEq)]
pub struct Expirada {
    pub id_envio: i64,
    pub message_id: i64,
    pub linha: LinhaCanal,
}

/// Uma ligação `AVISO_CANAL` (BSV-41) com o aviso e o último envio dele ao canal.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AvisoCanal {
    pub aviso: LinhaAviso,
    pub intervalo_min: i64,
    /// `AVISO_CANAL.ST_ATIVO = 1`
    pub ativo: bool,
    /// `MAX(ENVIO_AVISO.DT_ENVIO)` do par (aviso, canal), confirmado ou só reservado.
    pub ultimo_envio: Option<i64>,
}

pub trait FonteEnvio {
    fn canal(&self, id: i64) -> Result<Option<Canal>>;
    /// `None`: canal sem linha em `PARAMETROS_ENVIO`.
    fn parametros(&self, canal: i64) -> Result<Option<Parametros>>;
    /// Pré-filtro (o Oracle aplica; o envio refaz todos os filtros): `ST_ATIVO = 1`,
    /// `DT_PUBLICACAO_SITE` preenchida, `DT_OFERTA ≥ desde`, não enviada ao canal.
    fn candidatas(&self, canal: i64, desde: i64) -> Result<Vec<LinhaCanal>>;
    /// Dos `ids`, os que já têm linha em `ENVIO_TELEGRAM` para o canal.
    fn enviadas(&self, canal: i64, ids: &[i64]) -> Result<HashSet<i64>>;
    /// Envio mais recente de cada produto com `DT_ENVIO ≥ desde`.
    fn ultimos_por_produto(
        &self,
        canal: i64,
        ids_produto: &[i64],
        desde: i64,
    ) -> Result<HashMap<i64, UltimoEnvio>>;
    /// Linhas do canal com `DT_ENVIO ≥ desde`.
    fn enviados_desde(&self, canal: i64, desde: i64) -> Result<u64>;
    /// Linha nova sem `NR_MESSAGE_ID` (antes do envio), com commit; devolve `ID_ENVIO`.
    fn reservar(&self, canal: i64, o: &OfertaCanal, agora: i64) -> Result<i64>;
    fn confirmar(&self, id_envio: i64, message_id: i64) -> Result<()>;
    /// Apaga a linha de um envio que falhou.
    fn cancelar(&self, id_envio: i64) -> Result<()>;
    /// Até `limite` posts confirmados de ofertas com `ST_ATIVO = 0` e `DT_EDICAO` nula.
    fn expiradas(&self, canal: i64, limite: usize) -> Result<Vec<Expirada>>;
    fn marcar_editada(&self, id_envio: i64, agora: i64) -> Result<()>;
    /// Pré-filtro (o envio refaz todos): ligação e aviso ativos, `DT_PUBLICACAO_SITE` preenchida.
    fn avisos_canal(&self, canal: i64) -> Result<Vec<AvisoCanal>>;
    /// Linha nova em `ENVIO_AVISO` sem `NR_MESSAGE_ID`, com commit; devolve `ID_ENVIO_AVISO`.
    fn reservar_aviso(&self, aviso: i64, canal: i64, agora: i64) -> Result<i64>;
    fn confirmar_aviso(&self, id_envio: i64, message_id: i64) -> Result<()>;
    /// Apaga a linha de um envio de aviso que falhou.
    fn cancelar_aviso(&self, id_envio: i64) -> Result<()>;
}

/// Uma linha de `AVISO_CANAL` no fake.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LigacaoAviso {
    pub canal: i64,
    pub aviso: LinhaAviso,
    pub intervalo_min: i64,
    pub ativo: bool,
}

/// Uma linha de `ENVIO_AVISO` no fake.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RegistroAviso {
    pub id_envio: i64,
    pub aviso: i64,
    pub canal: i64,
    pub message_id: Option<i64>,
    pub dt_envio: i64,
}

/// Uma linha de `ENVIO_TELEGRAM` no fake.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RegistroEnvio {
    pub id_envio: i64,
    pub canal: i64,
    pub id_oferta: i64,
    pub id_produto: Option<i64>,
    pub preco_por: i64,
    pub message_id: Option<i64>,
    pub dt_envio: i64,
    pub dt_edicao: Option<i64>,
}

/// Oracle em memória. `candidatas` devolve todas as linhas, sem o pré-filtro do SQL: a regra que
/// vale é a do envio.
#[derive(Debug, Default)]
pub struct FakeEnvio {
    canais: Vec<Canal>,
    parametros: HashMap<i64, Parametros>,
    linhas: RefCell<Vec<LinhaCanal>>,
    envios: RefCell<Vec<RegistroEnvio>>,
    seq: Cell<i64>,
    falhar_reserva: Cell<bool>,
    ligacoes: RefCell<Vec<LigacaoAviso>>,
    envios_aviso: RefCell<Vec<RegistroAviso>>,
    seq_aviso: Cell<i64>,
    falhar_avisos: Cell<bool>,
}

impl FakeEnvio {
    /// Canal 1 (`@besaveofertas`, ativo) com os parâmetros dados.
    pub fn new(p: Parametros, linhas: Vec<LinhaCanal>) -> Self {
        Self {
            canais: vec![Canal {
                id: 1,
                chat_id: "@besaveofertas".into(),
                ativo: true,
            }],
            parametros: HashMap::from([(1, p)]),
            linhas: RefCell::new(linhas),
            ..Default::default()
        }
    }

    pub fn com_canal(mut self, c: Canal) -> Self {
        self.canais.retain(|x| x.id != c.id);
        self.canais.push(c);
        self
    }

    pub fn adicionar(&self, l: LinhaCanal) {
        self.linhas.borrow_mut().push(l);
    }

    /// `ST_ATIVO = 0` (o robô desativou).
    pub fn expirar(&self, id: i64) {
        for l in self
            .linhas
            .borrow_mut()
            .iter_mut()
            .filter(|l| l.oferta.id == id)
        {
            l.oferta.ativo = false;
        }
    }

    /// Linha já existente em `ENVIO_TELEGRAM` (histórico).
    pub fn registrar(&self, r: RegistroEnvio) {
        self.seq.set(self.seq.get().max(r.id_envio));
        self.envios.borrow_mut().push(r);
    }

    pub fn falhar_reserva(&self, sim: bool) {
        self.falhar_reserva.set(sim);
    }

    pub fn envios(&self) -> Vec<RegistroEnvio> {
        self.envios.borrow().clone()
    }

    /// Linha de `AVISO_CANAL` (substitui a do mesmo par aviso/canal).
    pub fn ligar_aviso(&self, l: LigacaoAviso) {
        let mut v = self.ligacoes.borrow_mut();
        v.retain(|x| !(x.canal == l.canal && x.aviso.id == l.aviso.id));
        v.push(l);
    }

    /// Linha já existente em `ENVIO_AVISO` (histórico).
    pub fn registrar_aviso(&self, r: RegistroAviso) {
        self.seq_aviso.set(self.seq_aviso.get().max(r.id_envio));
        self.envios_aviso.borrow_mut().push(r);
    }

    pub fn envios_aviso(&self) -> Vec<RegistroAviso> {
        self.envios_aviso.borrow().clone()
    }

    /// `avisos_canal` passa a falhar (falha injetada).
    pub fn falhar_avisos(&self, sim: bool) {
        self.falhar_avisos.set(sim);
    }

    fn falha(motivo: &str) -> ErroFonte {
        ErroFonte::ConfigInvalida("ENVIO_TELEGRAM", motivo.to_owned())
    }

    fn alterar(&self, id_envio: i64, f: impl FnOnce(&mut RegistroEnvio)) -> Result<()> {
        let mut envios = self.envios.borrow_mut();
        let r = envios
            .iter_mut()
            .find(|r| r.id_envio == id_envio)
            .ok_or_else(|| Self::falha("id_envio inexistente"))?;
        f(r);
        Ok(())
    }
}

impl FonteEnvio for FakeEnvio {
    fn canal(&self, id: i64) -> Result<Option<Canal>> {
        Ok(self.canais.iter().find(|c| c.id == id).cloned())
    }

    fn parametros(&self, canal: i64) -> Result<Option<Parametros>> {
        Ok(self.parametros.get(&canal).copied())
    }

    fn candidatas(&self, _canal: i64, _desde: i64) -> Result<Vec<LinhaCanal>> {
        Ok(self.linhas.borrow().clone())
    }

    fn enviadas(&self, canal: i64, ids: &[i64]) -> Result<HashSet<i64>> {
        Ok(self
            .envios
            .borrow()
            .iter()
            .filter(|r| r.canal == canal && ids.contains(&r.id_oferta))
            .map(|r| r.id_oferta)
            .collect())
    }

    fn ultimos_por_produto(
        &self,
        canal: i64,
        ids_produto: &[i64],
        desde: i64,
    ) -> Result<HashMap<i64, UltimoEnvio>> {
        let mut out: HashMap<i64, UltimoEnvio> = HashMap::new();
        for r in self.envios.borrow().iter().filter(|r| {
            r.canal == canal
                && r.dt_envio >= desde
                && r.id_produto.is_some_and(|p| ids_produto.contains(&p))
        }) {
            let Some(p) = r.id_produto else { continue };
            let u = UltimoEnvio {
                preco_por: r.preco_por,
                dt_envio: r.dt_envio,
            };
            out.entry(p)
                .and_modify(|v| {
                    if u.dt_envio > v.dt_envio {
                        *v = u;
                    }
                })
                .or_insert(u);
        }
        Ok(out)
    }

    fn enviados_desde(&self, canal: i64, desde: i64) -> Result<u64> {
        Ok(self
            .envios
            .borrow()
            .iter()
            .filter(|r| r.canal == canal && r.dt_envio >= desde)
            .count() as u64)
    }

    fn reservar(&self, canal: i64, o: &OfertaCanal, agora: i64) -> Result<i64> {
        if self.falhar_reserva.get() {
            return Err(Self::falha("falha injetada"));
        }
        let mut envios = self.envios.borrow_mut();
        // UK_ENVIO_TELEGRAM (ID_CANAL, ID_OFERTA).
        if envios
            .iter()
            .any(|r| r.canal == canal && r.id_oferta == o.id)
        {
            return Err(Self::falha("UK_ENVIO_TELEGRAM"));
        }
        let id = self.seq.get() + 1;
        self.seq.set(id);
        envios.push(RegistroEnvio {
            id_envio: id,
            canal,
            id_oferta: o.id,
            id_produto: Some(o.id_produto),
            preco_por: o.preco_por,
            message_id: None,
            dt_envio: agora,
            dt_edicao: None,
        });
        Ok(id)
    }

    fn confirmar(&self, id_envio: i64, message_id: i64) -> Result<()> {
        self.alterar(id_envio, |r| r.message_id = Some(message_id))
    }

    fn cancelar(&self, id_envio: i64) -> Result<()> {
        self.envios.borrow_mut().retain(|r| r.id_envio != id_envio);
        Ok(())
    }

    fn expiradas(&self, canal: i64, limite: usize) -> Result<Vec<Expirada>> {
        let linhas = self.linhas.borrow();
        Ok(self
            .envios
            .borrow()
            .iter()
            .filter(|r| r.canal == canal && r.dt_edicao.is_none())
            .filter_map(|r| {
                let message_id = r.message_id?;
                let l = linhas
                    .iter()
                    .find(|l| l.oferta.id == r.id_oferta && !l.oferta.ativo)?;
                Some(Expirada {
                    id_envio: r.id_envio,
                    message_id,
                    linha: l.clone(),
                })
            })
            .take(limite)
            .collect())
    }

    fn marcar_editada(&self, id_envio: i64, agora: i64) -> Result<()> {
        self.alterar(id_envio, |r| r.dt_edicao = Some(agora))
    }

    /// Sem o pré-filtro do SQL: a regra que vale é a do envio.
    fn avisos_canal(&self, canal: i64) -> Result<Vec<AvisoCanal>> {
        if self.falhar_avisos.get() {
            return Err(Self::falha("falha injetada em AVISO_CANAL"));
        }
        let envios = self.envios_aviso.borrow();
        Ok(self
            .ligacoes
            .borrow()
            .iter()
            .filter(|l| l.canal == canal)
            .map(|l| AvisoCanal {
                aviso: l.aviso.clone(),
                intervalo_min: l.intervalo_min,
                ativo: l.ativo,
                ultimo_envio: envios
                    .iter()
                    .filter(|r| r.canal == canal && r.aviso == l.aviso.id)
                    .map(|r| r.dt_envio)
                    .max(),
            })
            .collect())
    }

    fn reservar_aviso(&self, aviso: i64, canal: i64, agora: i64) -> Result<i64> {
        let id = self.seq_aviso.get() + 1;
        self.seq_aviso.set(id);
        self.envios_aviso.borrow_mut().push(RegistroAviso {
            id_envio: id,
            aviso,
            canal,
            message_id: None,
            dt_envio: agora,
        });
        Ok(id)
    }

    fn confirmar_aviso(&self, id_envio: i64, message_id: i64) -> Result<()> {
        let mut v = self.envios_aviso.borrow_mut();
        let r = v
            .iter_mut()
            .find(|r| r.id_envio == id_envio)
            .ok_or_else(|| Self::falha("id_envio_aviso inexistente"))?;
        r.message_id = Some(message_id);
        Ok(())
    }

    fn cancelar_aviso(&self, id_envio: i64) -> Result<()> {
        self.envios_aviso
            .borrow_mut()
            .retain(|r| r.id_envio != id_envio);
        Ok(())
    }
}
