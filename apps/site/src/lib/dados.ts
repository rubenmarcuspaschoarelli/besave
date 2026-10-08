// Camada de dados do site (BSV-35): única porta de entrada; componentes não fazem fetch.
export { AREAS, LOJAS, PUBLICOS, ROTULO_LOJA } from './dados/tipos.ts';
export type {
	Area,
	ChunkRef,
	Filtro,
	Loja,
	Manifest,
	OfertaCard,
	Ordem,
	Publico
} from './dados/tipos.ts';
export { Catalogo, descontoPct, maioresDescontos, normalizar } from './dados/catalogo.ts';
export { buscar } from './dados/busca.ts';
export type { ResultadoBusca } from './dados/busca.ts';
export { INTERVALO_MS, criarSincronizador, diferenca } from './dados/sincronizador.ts';
export type { Deps, Evento, Resposta, Sincronizador } from './dados/sincronizador.ts';
