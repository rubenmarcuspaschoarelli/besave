// Texto curto de cada área e das subpáginas com volume (BSV-33). Só as rotas de área importam
// este módulo: fica fora do bundle da home. Sem promessa de preço; o dono revisa no PR.
import type { Area, Publico } from '../dados.ts';

export const TEXTO_AREA: Record<Area, string> = {
	TECH: 'Ofertas de tecnologia: fones, carregadores, acessórios de celular, computadores, periféricos e eletrônicos para o dia a dia. Juntamos aqui as ofertas selecionadas, e a todo momento aparecem novidades.',
	PLAYERS:
		'Ofertas para quem joga: consoles, controles, headsets, jogos e acessórios para PC e videogame. Confira o preço e o cupom na loja antes de comprar, porque as condições mudam rápido.',
	MEU_LAR:
		'Ofertas para a casa: cozinha, organização, cama, mesa e banho, limpeza e decoração. As mais recentes aparecem primeiro, e os filtros ajudam a escolher loja, faixa de preço e cupom.',
	ELAS: 'Ofertas de beleza e cuidados pessoais: maquiagem, skincare, cabelo, perfumes, moda e acessórios. A lista junta as ofertas selecionadas a todo momento.',
	ELES: 'Ofertas para o público masculino: cuidados pessoais, barbear, perfumes, roupas e acessórios. Use os filtros para ver só uma loja, uma faixa de preço ou as ofertas com cupom.',
	CULTURA:
		'Ofertas de livros, filmes, séries, música e papelaria. O preço é o da loja no momento em que a oferta foi encontrada e pode mudar depois.',
	FAMILIA:
		'Ofertas para a família e para os filhos: brinquedos, roupas infantis, itens de bebê, material escolar e utilidades para a rotina com crianças. O filtro de público separa o que é infantil do que serve para todos.',
	PETS: 'Ofertas para cães, gatos e outros bichos: ração, petiscos, areia, brinquedos, camas e acessórios. As ofertas chegam do mercado on-line ao longo do dia.',
	ESPORTE_VIDA:
		'Ofertas de esporte e vida saudável: roupas e calçados esportivos, suplementos, equipamentos de treino e acessórios para atividades ao ar livre. Escolha o público para ver o que é feminino, masculino ou unissex.',
	OUTROS:
		'Ofertas que não se encaixam nas outras áreas: ferramentas, automotivo, presentes e achados variados. A variedade muda todos os dias, então vale passar por aqui de vez em quando.'
};

/** Uma frase por subpágina com volume (≥ 20 ativas e ≤ 90% da área, contagem de 08/10/2026). */
export const TEXTO_SUBPAGINA: Partial<Record<`${Area}/${Publico}`, string>> = {
	'ELAS/UNISSEX':
		'Aqui ficam os produtos de beleza e cuidados que servem para qualquer pessoa, como protetor solar, hidratantes e acessórios de cabelo.',
	'MEU_LAR/FEMININO':
		'Itens da casa pensados para o público feminino, como organizadores de maquiagem, acessórios de banheiro e decoração.',
	'ESPORTE_VIDA/UNISSEX':
		'Equipamentos e acessórios esportivos que servem para todos, como garrafas, tapetes de yoga, halteres e mochilas.',
	'ESPORTE_VIDA/FEMININO':
		'Roupas, calçados e acessórios esportivos femininos, como tops, leggings e tênis de corrida.',
	'ESPORTE_VIDA/MASCULINO':
		'Roupas, calçados e acessórios esportivos masculinos, como bermudas, camisetas de treino e tênis.',
	'FAMILIA/INFANTIL':
		'Brinquedos, roupas e itens para bebês e crianças, do enxoval à volta às aulas.',
	'FAMILIA/UNISSEX':
		'Itens para a família toda, como jogos, utilidades para passeios e produtos para a rotina com crianças.'
};

/** Parágrafos da página: a frase da subpágina (quando há) e o texto da área. */
export function textoDaPagina(area: Area, publico?: Publico): string[] {
	const sub = publico ? TEXTO_SUBPAGINA[`${area}/${publico}`] : undefined;
	return sub ? [sub, TEXTO_AREA[area]] : [TEXTO_AREA[area]];
}
