// Exibição: preço, tempo relativo e rótulos de área (CONTRATO §2.3, AD-032).
import type { Area, OfertaCard } from './dados.ts';

const BRL = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

/** Centavos → "R$ 1.299,90". */
export function reais(centavos: number): string {
	return BRL.format(centavos / 100);
}

const MIN = 60_000;
const HORA = 60 * MIN;
const DIA = 24 * HORA;
/** Brasília com offset fixo −03:00 (AD-032). */
const BRASILIA = -3 * HORA;

/** "há N min", "há N h", "há N d" ou "em DD/MM" (data de Brasília) a partir de `dp` (sem `dp`, `dt`). */
export function haQuanto(c: Pick<OfertaCard, 'dp' | 'dt'>, agora: number): string {
	const t = Date.parse(c.dp ?? c.dt);
	const passou = agora - t;
	if (passou < HORA) return `há ${Math.max(1, Math.floor(passou / MIN))} min`;
	if (passou < DIA) return `há ${Math.floor(passou / HORA)} h`;
	if (passou < 7 * DIA) return `há ${Math.floor(passou / DIA)} d`;
	const local = new Date(t + BRASILIA);
	const dd = String(local.getUTCDate()).padStart(2, '0');
	const mm = String(local.getUTCMonth() + 1).padStart(2, '0');
	return `em ${dd}/${mm}`;
}

export const ROTULO_AREA: Record<Area, string> = {
	TECH: 'Tech',
	PLAYERS: 'Players',
	MEU_LAR: 'Meu Lar',
	ELAS: 'Elas',
	ELES: 'Eles',
	CULTURA: 'Cultura',
	FAMILIA: 'Família & filhos',
	PETS: 'Pets',
	ESPORTE_VIDA: 'Esporte & vida',
	OUTROS: 'Outros'
};

export const SLUG_AREA: Record<Area, string> = {
	TECH: 'tech',
	PLAYERS: 'players',
	MEU_LAR: 'meu-lar',
	ELAS: 'elas',
	ELES: 'eles',
	CULTURA: 'cultura',
	FAMILIA: 'familia',
	PETS: 'pets',
	ESPORTE_VIDA: 'esporte-vida',
	OUTROS: 'outros'
};

/** Botões de área da home, na ordem do modelo A; `OUTROS` fica no menu "Mais". */
export const AREAS_MENU: { valor: Area; rotulo: string }[] = (
	[
		'ELAS',
		'MEU_LAR',
		'TECH',
		'ESPORTE_VIDA',
		'FAMILIA',
		'PETS',
		'PLAYERS',
		'CULTURA',
		'ELES'
	] as const
).map((valor) => ({ valor, rotulo: ROTULO_AREA[valor] }));
