#![allow(dead_code)]

use std::path::PathBuf;

pub fn fixture(nome: &str) -> String {
    let p = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../packages/contract/fixtures")
        .join(nome);
    std::fs::read_to_string(&p).unwrap_or_else(|e| panic!("{}: {e}", p.display()))
}

pub fn caminho_mapeamento() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../packages/contract/mapeamento.json")
}

/// Remove espaços fora de strings: forma compacta da fixture, mesma ordem de chaves.
pub fn compactar(json: &str) -> String {
    let mut out = String::with_capacity(json.len());
    let (mut em_string, mut escape) = (false, false);
    for ch in json.chars() {
        if em_string {
            out.push(ch);
            if escape {
                escape = false;
            } else if ch == '\\' {
                escape = true;
            } else if ch == '"' {
                em_string = false;
            }
        } else if ch == '"' {
            em_string = true;
            out.push(ch);
        } else if !ch.is_whitespace() {
            out.push(ch);
        }
    }
    out
}

/// Descomprime Brotli.
pub fn descomprimir(br: &[u8]) -> Vec<u8> {
    let mut out = Vec::new();
    brotli::BrotliDecompress(&mut &br[..], &mut out).unwrap();
    out
}

/// Valida `instancia` contra `packages/contract/schema/<nome>`, com os demais schemas
/// registrados pelo `$id` (resolve `$ref` relativos) e `format` checado.
pub fn validar_schema(nome: &str, instancia: &serde_json::Value) {
    let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../packages/contract/schema");
    let mut schemas = Vec::new();
    for e in std::fs::read_dir(&dir).unwrap() {
        let p = e.unwrap().path();
        let v: serde_json::Value =
            serde_json::from_str(&std::fs::read_to_string(&p).unwrap()).unwrap();
        schemas.push((p.file_name().unwrap().to_string_lossy().into_owned(), v));
    }
    let registro = jsonschema::Registry::new()
        .extend(
            schemas
                .iter()
                .map(|(_, v)| (v["$id"].as_str().unwrap().to_owned(), v.clone())),
        )
        .unwrap()
        .prepare()
        .unwrap();
    let (_, alvo) = schemas.iter().find(|(n, _)| n == nome).unwrap();
    let v = jsonschema::options()
        .with_registry(&registro)
        .should_validate_formats(true)
        .build(alvo)
        .unwrap();
    let erros: Vec<String> = v.iter_errors(instancia).map(|e| e.to_string()).collect();
    assert!(erros.is_empty(), "{nome}: {erros:?}");
}

/// 2026-09-24T12:40:00Z
pub const AGORA: i64 = 1_790_253_600;
pub const DIA: i64 = 86_400;

pub fn mapeamento() -> worker::mapeamento::Mapeamento {
    worker::mapeamento::Mapeamento::carregar(caminho_mapeamento()).unwrap()
}

/// Linha válida e ativa em TECH, faixa `id / 1000`.
pub fn linha(id: i64) -> worker::conversao::LinhaOferta {
    worker::conversao::LinhaOferta {
        id,
        id_produto: Some(id),
        loja: Some("Amazon".into()),
        titulo: Some(format!("Oferta {id}")),
        preco_por: Some(10.0),
        dt_oferta: Some(AGORA - 3600),
        area: Some("Tech".into()),
        publico: Some("U".into()),
        ativo: true,
        url_afiliado: format!("https://loja.example/{id}"),
        ..Default::default()
    }
}

/// Linhas equivalentes aos 3 registros de `chunk-ok.json` (5420 expirada).
pub fn linhas_fixture() -> Vec<worker::conversao::LinhaOferta> {
    use worker::conversao::LinhaOferta;
    vec![
        LinhaOferta {
            id: 5412,
            id_produto: Some(910),
            loja: Some("Amazon".into()),
            titulo: Some("Fone Bluetooth XYZ com ANC".into()),
            preco_de: Some(299.90),
            preco_por: Some(199.90),
            cupom: Some("besave10".into()),
            dt_oferta: Some(1_790_253_600),
            area: Some("Tecnologia".into()),
            publico: Some("Unissex".into()),
            ativo: true,
            url_afiliado: "https://loja.example/5412".into(),
            ..Default::default()
        },
        LinhaOferta {
            id: 5413,
            id_produto: Some(911),
            loja: Some("Shopee".into()),
            titulo: Some("Kit Skincare Vitamina C 3 passos".into()),
            preco_por: Some(89.90),
            dt_oferta: Some(1_790_253_660),
            area: Some("Elas".into()),
            publico: Some("Mulher".into()),
            ativo: true,
            url_afiliado: "https://loja.example/5413".into(),
            ..Default::default()
        },
        LinhaOferta {
            id: 5420,
            id_produto: Some(912),
            loja: Some("MercadoLivre".into()),
            titulo: Some("Ração Premium Cães Adultos 15kg".into()),
            preco_de: Some(249.00),
            preco_por: Some(199.00),
            dt_oferta: Some(1_790_150_400),
            area: Some("Pet".into()),
            publico: Some("U".into()),
            ativo: false,
            dt_desativacao: Some(AGORA - DIA),
            url_afiliado: "https://loja.example/5420".into(),
            ..Default::default()
        },
    ]
}

/// Texto pseudoaleatório (letras e espaços) de `n` caracteres: comprime mal.
pub fn texto_aleatorio(semente: u64, n: usize) -> String {
    let mut x = semente
        .wrapping_mul(6_364_136_223_846_793_005)
        .wrapping_add(1);
    (0..n)
        .map(|i| {
            x = x
                .wrapping_mul(6_364_136_223_846_793_005)
                .wrapping_add(1_442_695_040_888_963_407);
            let k = (x >> 33) % 27;
            if k == 26 || i == 0 || i + 1 == n {
                if i == 0 || i + 1 == n { 'x' } else { ' ' }
            } else {
                char::from(b'a' + k as u8)
            }
        })
        .collect()
}
