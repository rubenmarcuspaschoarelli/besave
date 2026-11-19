//! BSV-62 SQL-01: o DDL da fila do WhatsApp, lido como texto (o dono roda no Oracle).

const SQL: &str = include_str!("../sql/bsv-62.sql");

/// Sem comentários (`-- …`) e com espaços normalizados, em maiúsculas.
fn comandos() -> String {
    SQL.lines()
        .map(|l| l.split("--").next().unwrap_or(""))
        .collect::<Vec<_>>()
        .join(" ")
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .to_uppercase()
}

fn tabela() -> String {
    let c = comandos();
    let ini = c
        .find("CREATE TABLE ENVIO_WHATSAPP (")
        .expect("CREATE TABLE");
    let fim = ini + c[ini..].find(");").expect("fim do CREATE TABLE");
    c[ini..fim].to_owned()
}

#[test]
fn canal_2_e_parametros() {
    let c = comandos();
    assert!(
        c.contains(
            "INSERT INTO CANAL_ENVIO (ID_CANAL, DS_NOME, DS_CHAT_ID) VALUES (2, 'WHATSAPP', 'BESAVE - PREÇOS BAIXOS E OFERTAS INCRÍVEIS');"
        ),
        "{c}"
    );
    assert!(
        c.contains(
            "INSERT INTO PARAMETROS_ENVIO (ID_CANAL, QT_MAX_DIA, NR_HORA_INICIO, NR_HORA_FIM) VALUES (2, 40, 8, 22);"
        ),
        "{c}"
    );
}

#[test]
fn colunas_da_fila() {
    let t = tabela();
    for col in [
        "ID_ENVIO_WA NUMBER(12) NOT NULL",
        "ID_CANAL NUMBER(10) NOT NULL",
        "ID_OFERTA NUMBER NOT NULL",
        "ID_ENVIO_TELEGRAM NUMBER(12),",
        "DS_LEGENDA VARCHAR2(4000 BYTE) NOT NULL",
        "DS_AREA_SLUG VARCHAR2(20) NOT NULL",
        "ST_ENVIO CHAR(1) DEFAULT 'P' NOT NULL",
        "DS_MOTIVO VARCHAR2(60),",
        "DT_FILA DATE DEFAULT SYSDATE NOT NULL",
        "DT_ENVIO DATE,",
    ] {
        assert!(t.contains(col), "falta {col}: {t}");
    }
}

#[test]
fn unico_indice_e_chaves() {
    let c = comandos();
    let t = tabela();
    assert!(c.contains("CREATE SEQUENCE SQ_ENVIO_WHATSAPP"), "{c}");
    assert!(t.contains("PRIMARY KEY (ID_ENVIO_WA)"), "{t}");
    assert!(t.contains("UNIQUE (ID_CANAL, ID_OFERTA)"), "{t}");
    assert!(
        t.contains("FOREIGN KEY (ID_CANAL) REFERENCES CANAL_ENVIO (ID_CANAL)"),
        "{t}"
    );
    assert!(
        t.contains("CHECK (ST_ENVIO IN ('P', 'E', 'D', 'X'))"),
        "{t}"
    );
    // Sem FK para OFERTA, igual a ENVIO_TELEGRAM.
    assert_eq!(t.matches("REFERENCES").count(), 1, "{t}");
    assert!(!t.contains("REFERENCES OFERTA"), "{t}");
    assert!(
        c.contains(
            "CREATE INDEX IX_ENVIO_WHATSAPP_FILA ON ENVIO_WHATSAPP (ID_CANAL, ST_ENVIO, DT_FILA);"
        ),
        "{c}"
    );
}

#[test]
fn checagem_zero_antes_do_ddl() {
    let c = comandos();
    let checagem = c.find("NLS_CHARACTERSET").expect("checagem do charset");
    let canal = c
        .find("FROM CANAL_ENVIO WHERE ID_CANAL = 2")
        .expect("checagem do canal 2");
    let primeiro_insert = c.find("INSERT INTO").expect("insert");
    assert!(checagem < primeiro_insert && canal < primeiro_insert);
}

#[test]
fn grants_comentados_e_sem_segredo() {
    // Nenhum GRANT ativo; os comentados existem.
    assert!(!comandos().contains("GRANT "));
    assert!(SQL.contains("-- GRANT SELECT, INSERT, UPDATE ON ENVIO_WHATSAPP TO <USUARIO>;"));
    let baixo = SQL.to_lowercase();
    for proibido in ["chat.whatsapp.com", "http://", "https://", "+55", "token"] {
        assert!(!baixo.contains(proibido), "{proibido}");
    }
    // Nenhuma sequência de 8+ dígitos (telefone) nem IP.
    let digitos = SQL
        .split(|c: char| !c.is_ascii_digit())
        .map(str::len)
        .max()
        .unwrap_or(0);
    assert!(digitos < 8, "sequência longa de dígitos");
    assert!(
        !SQL.split(|c: char| !(c.is_ascii_digit() || c == '.'))
            .any(|s| s.split('.').filter(|p| !p.is_empty()).count() == 4),
        "parece um IP"
    );
}
