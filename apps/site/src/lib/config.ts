// Links e funções futuras do site (AD-077): ícone ou botão só aparece com link ou flag ligada.
export type Rede = 'x' | 'facebook' | 'instagram' | 'youtube' | 'discord';
export type App = 'android' | 'ios';
export type BotaoTopo = 'postar' | 'notificacoes' | 'entrar';
/** `social`: likes e comentários no card (fase com login). */
export type Flag = BotaoTopo | 'social';

export interface Config {
	canal: string;
	redes: Record<Rede, string | null>;
	apps: Record<App, string | null>;
	flags: Record<Flag, boolean>;
}

export const CONFIG: Config = {
	canal: 'https://t.me/besaveofertas',
	redes: { x: null, facebook: null, instagram: null, youtube: null, discord: null },
	apps: { android: null, ios: null },
	flags: { postar: false, notificacoes: false, entrar: false, social: false }
};

/** Só as entradas com link, na ordem do objeto. */
export function comLink<K extends string>(
	links: Record<K, string | null>
): { chave: K; url: string }[] {
	return (Object.entries(links) as [K, string | null][])
		.filter((e): e is [K, string] => typeof e[1] === 'string' && e[1].trim() !== '')
		.map(([chave, url]) => ({ chave, url }));
}

/** Botões do topo com flag ligada, na ordem de exibição. */
export function botoesLigados(flags: Record<Flag, boolean>): BotaoTopo[] {
	return (['postar', 'notificacoes', 'entrar'] as const).filter((f) => flags[f]);
}
