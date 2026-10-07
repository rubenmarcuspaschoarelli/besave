//! Fronteira do envio com o Telegram (bot do canal) e com o relógio, ambos com fake.

use std::cell::{Cell, RefCell};
use std::collections::VecDeque;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

/// Erros sem a URL do pedido (ela contém o token).
#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
pub enum ErroCanal {
    #[error("Telegram pediu espera de {0} s (HTTP 429)")]
    Limite(u64),
    #[error("Telegram recusou: HTTP {status}: {descricao}")]
    Recusada { status: u16, descricao: String },
    #[error("Telegram respondeu HTTP {0}")]
    Http(u16),
    #[error("Telegram sem resposta em {0} s")]
    Timeout(u64),
    #[error("Telegram: {0}")]
    Conexao(String),
}

/// Bot do canal (`TELEGRAM_CANAL_BOT_TOKEN`), `parse_mode=HTML`.
pub trait CanalTelegram {
    /// `sendPhoto` multipart; devolve o `message_id`.
    fn enviar_foto(
        &self,
        chat_id: &str,
        jpeg: &[u8],
        legenda: &str,
        silencioso: bool,
    ) -> Result<i64, ErroCanal>;
    fn editar_legenda(
        &self,
        chat_id: &str,
        message_id: i64,
        legenda: &str,
    ) -> Result<(), ErroCanal>;
    /// `sendMessage` com prévia do link (aviso sem foto, BSV-41); devolve o `message_id`.
    fn enviar_mensagem(
        &self,
        chat_id: &str,
        texto: &str,
        silencioso: bool,
    ) -> Result<i64, ErroCanal>;
}

pub trait Relogio {
    /// Milissegundos Unix.
    fn agora_ms(&self) -> i64;
    fn dormir(&self, d: Duration);
    /// Segundos Unix.
    fn agora(&self) -> i64 {
        self.agora_ms().div_euclid(1000)
    }
}

#[derive(Debug, Clone, Copy, Default)]
pub struct RelogioSistema;

impl Relogio for RelogioSistema {
    fn agora_ms(&self) -> i64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_or(0, |d| i64::try_from(d.as_millis()).unwrap_or(i64::MAX))
    }

    fn dormir(&self, d: Duration) {
        std::thread::sleep(d);
    }
}

/// Relógio de teste: `dormir` só avança o tempo.
#[derive(Debug, Default)]
pub struct RelogioFake {
    ms: Cell<i64>,
}

impl RelogioFake {
    pub fn em(segundos: i64) -> Self {
        Self {
            ms: Cell::new(segundos * 1000),
        }
    }

    pub fn definir(&self, segundos: i64) {
        self.ms.set(segundos * 1000);
    }
}

impl Relogio for RelogioFake {
    fn agora_ms(&self) -> i64 {
        self.ms.get()
    }

    fn dormir(&self, d: Duration) {
        let ms = i64::try_from(d.as_millis()).unwrap_or(i64::MAX);
        self.ms.set(self.ms.get().saturating_add(ms));
    }
}

/// Uma chamada ao fake do Telegram.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Chamada {
    /// `sendPhoto`, `sendMessage` ou `editMessageCaption`.
    pub metodo: &'static str,
    pub chat_id: String,
    pub legenda: String,
    pub silencioso: bool,
    pub message_id: i64,
    pub jpeg: Vec<u8>,
    /// Instante da chamada (relógio do teste), ms.
    pub ms: i64,
}

/// Telegram em memória. Respostas roteirizadas em `roteiro` (uma por chamada, na ordem); sem
/// roteiro, sucesso com `message_id` sequencial a partir de 1000.
pub struct FakeCanal<'a> {
    relogio: &'a dyn Relogio,
    chamadas: RefCell<Vec<Chamada>>,
    roteiro: RefCell<VecDeque<Result<(), ErroCanal>>>,
    proximo_id: Cell<i64>,
}

impl<'a> FakeCanal<'a> {
    pub fn new(relogio: &'a dyn Relogio) -> Self {
        Self {
            relogio,
            chamadas: RefCell::new(Vec::new()),
            roteiro: RefCell::new(VecDeque::new()),
            proximo_id: Cell::new(1000),
        }
    }

    /// Próximas respostas, na ordem das chamadas.
    pub fn roteirizar(&self, respostas: impl IntoIterator<Item = Result<(), ErroCanal>>) {
        self.roteiro.borrow_mut().extend(respostas);
    }

    pub fn chamadas(&self) -> Vec<Chamada> {
        self.chamadas.borrow().clone()
    }

    /// Chamadas a `metodo` (sem copiar as fotos).
    pub fn contar(&self, metodo: &str) -> usize {
        self.chamadas
            .borrow()
            .iter()
            .filter(|c| c.metodo == metodo)
            .count()
    }

    fn registrar(&self, mut c: Chamada) -> Result<i64, ErroCanal> {
        c.ms = self.relogio.agora_ms();
        let resposta = self.roteiro.borrow_mut().pop_front().unwrap_or(Ok(()));
        if c.metodo != "editMessageCaption" && resposta.is_ok() {
            c.message_id = self.proximo_id.get();
            self.proximo_id.set(c.message_id + 1);
        }
        let id = c.message_id;
        self.chamadas.borrow_mut().push(c);
        resposta.map(|()| id)
    }
}

impl CanalTelegram for FakeCanal<'_> {
    fn enviar_foto(
        &self,
        chat_id: &str,
        jpeg: &[u8],
        legenda: &str,
        silencioso: bool,
    ) -> Result<i64, ErroCanal> {
        self.registrar(Chamada {
            metodo: "sendPhoto",
            chat_id: chat_id.to_owned(),
            legenda: legenda.to_owned(),
            silencioso,
            message_id: 0,
            jpeg: jpeg.to_vec(),
            ms: 0,
        })
    }

    fn editar_legenda(
        &self,
        chat_id: &str,
        message_id: i64,
        legenda: &str,
    ) -> Result<(), ErroCanal> {
        self.registrar(Chamada {
            metodo: "editMessageCaption",
            chat_id: chat_id.to_owned(),
            legenda: legenda.to_owned(),
            silencioso: false,
            message_id,
            jpeg: Vec::new(),
            ms: 0,
        })
        .map(|_| ())
    }

    fn enviar_mensagem(
        &self,
        chat_id: &str,
        texto: &str,
        silencioso: bool,
    ) -> Result<i64, ErroCanal> {
        self.registrar(Chamada {
            metodo: "sendMessage",
            chat_id: chat_id.to_owned(),
            legenda: texto.to_owned(),
            silencioso,
            message_id: 0,
            jpeg: Vec::new(),
            ms: 0,
        })
    }
}
