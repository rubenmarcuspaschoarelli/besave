// Linha compacta do computador (BSV-37): as opções ficam numa faixa aberta pelo item do grupo.
import { expect } from '@playwright/test';
import type { Page } from '@playwright/test';

const GRUPOS: [string, string[]][] = [
	['Ordem', ['Recentes', 'Maior desconto', 'Menor preço']],
	['Público', ['Todos', 'Feminino', 'Masculino', 'Unissex', 'Infantil']],
	['Loja', ['Todas', 'Amazon', 'Mercado Livre', 'Shopee']],
	['Preço', ['Até R$ 50', 'R$ 50–100', 'R$ 100–200', 'Acima de R$ 200']]
];

/** Grupo da opção (`Feminino` → `Público`); `undefined` para "Só com cupom". */
export const grupoDe = (opcao: string) => GRUPOS.find(([, ops]) => ops.includes(opcao))?.[0];

/** Item do grupo na linha: `Público` ou `Público: Feminino`. */
export const item = (page: Page, grupo: string) =>
	page.locator('[data-compacta]').getByRole('button', { name: new RegExp(`^${grupo}(: .+)?$`) });

/**
 * No computador, abre a faixa do grupo da opção (se ainda não aberta) e devolve `true`;
 * no celular (sem linha compacta) não faz nada e devolve `false`.
 */
export async function abrirNaLinha(page: Page, opcao: string): Promise<boolean> {
	const grupo = grupoDe(opcao);
	if (!grupo || !(await page.locator('[data-compacta]').isVisible())) return false;
	const it = item(page, grupo);
	if ((await it.getAttribute('aria-expanded')) !== 'true') await it.click();
	await expect(page.getByRole('button', { name: opcao, exact: true })).toBeVisible();
	return true;
}
