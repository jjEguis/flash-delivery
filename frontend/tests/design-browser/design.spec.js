import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.beforeEach(async ({ page }) => {
  // El prototipo nunca debe llamar a APIs ni depender de recursos externos.
  await page.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin !== 'http://127.0.0.1:5174' || url.pathname.startsWith('/api/')) throw new Error('Llamada externa/API no permitida: ' + url.href);
    return route.continue();
  });
});

for (const width of [360, 390, 768, 1024, 1440]) {
  for (const theme of ['light', 'dark']) {
    for (const role of ['store', 'courier']) {
      test(`${role}: ${width}px, ${theme}, sin desbordes y con contraste`, async ({ page }, testInfo) => {
        await page.setViewportSize({ width, height: 960 });
        await page.addInitScript(theme => localStorage.setItem('flashdelivery:theme:v1', theme), theme);
        const errors = []; page.on('pageerror', error => errors.push(error.message));
        await page.goto(`/preview.html#/app/${role}`);
        await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
        await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
        await page.evaluate(() => document.fonts.ready);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        const accessibility = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze();
        expect(accessibility.violations).toEqual([]);
        await page.screenshot({ path: testInfo.outputPath(`${role}-${width}-${theme}.png`), fullPage: true });
        expect(errors).toEqual([]);
      });
    }
  }
}

test('apariencia persiste, sigue el sistema y no altera la sesión ni el rol', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  await page.addInitScript(() => localStorage.setItem('fd.session', 'keep-this-session'));
  await page.goto('/preview.html#/app/store');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.getByRole('combobox', { name: 'Apariencia' })).toHaveValue('system');
  await page.getByRole('combobox', { name: 'Apariencia' }).selectOption('light');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await page.emulateMedia({ colorScheme: 'dark' });
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await page.getByRole('combobox', { name: 'Apariencia' }).selectOption('system');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.emulateMedia({ colorScheme: 'light' });
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  expect(await page.evaluate(() => localStorage.getItem('fd.session'))).toBe('keep-this-session');
  await expect(page).toHaveURL(/app\/store$/);
});

test('selector operativo con almacenamiento bloqueado, público y administración', async ({ page }) => {
  await page.addInitScript(() => {
    Storage.prototype.getItem = () => { throw new Error('blocked'); };
    Storage.prototype.setItem = () => { throw new Error('blocked'); };
  });
  await page.goto('/preview.html#/app/store');
  await page.getByRole('combobox', { name: 'Apariencia' }).selectOption('dark');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.getByLabel('Vista de demostración').selectOption('tracking');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Tu entrega va avanzando.');
  await expect(page.locator('.desktop-sidebar')).toHaveCount(0);
  await expect(page.locator('#design-main')).not.toContainText('Carrera 4 # 12-31');
  await page.getByRole('combobox', { name: 'Apariencia' }).selectOption('light');
  await page.getByLabel('Vista de demostración').selectOption('admin');
  await expect(page.getByRole('button', { name: 'Habilitar perfiles' })).toBeDisabled();
  await page.getByRole('combobox', { name: 'Apariencia' }).selectOption('dark');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
});

test('menú móvil con teclado, Escape y foco restaurado', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/preview.html#/app/store');
  const menu = page.getByRole('button', { name: 'Abrir menú' });
  await menu.focus(); await page.keyboard.press('Enter');
  await expect(page.getByRole('dialog', { name: 'Menú de navegación' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog', { name: 'Menú de navegación' })).not.toBeVisible();
  await expect(menu).toBeFocused();
  await menu.click();
  await page.getByRole('dialog').getByRole('link', { name: 'Mis entregas', exact: true }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Mis entregas');
  await expect(page.getByRole('dialog')).not.toBeVisible();
});

test('formulario de ejemplo valida, confirma y actualiza las métricas simuladas', async ({ page }) => {
  await page.goto('/preview.html#/app/store');
  await page.getByRole('button', { name: 'Nueva entrega', exact: true }).click();
  await page.getByRole('button', { name: 'Revisar entrega' }).click();
  await expect(page.getByRole('alert')).toContainText('Indica la dirección de entrega.');
  await page.getByLabel('Dirección de entrega', { exact: true }).fill('Calle de ejemplo 25');
  await page.getByRole('button', { name: 'Revisar entrega' }).click();
  await page.getByRole('button', { name: 'Confirmar entrega de ejemplo' }).click();
  await expect(page.getByRole('dialog')).not.toBeVisible();
  await expect(page.getByRole('status')).toContainText('No se envió a la API');
  await expect(page.locator('.order-table')).toContainText('FD-DEMO-9');
});

test('disponibilidad, recogida y confirmación de entrega cambian solo la demo', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/preview.html#/app/courier');
  const action = await page.getByRole('button', { name: 'Marcar como recogido' }).boundingBox();
  const bottomNav = await page.getByRole('navigation', { name: 'Navegación móvil' }).boundingBox();
  expect(action.y + action.height).toBeLessThanOrEqual(bottomNav.y);
  await page.getByRole('switch').uncheck();
  await expect(page.getByRole('button', { name: 'Aceptar entrega FD-2051' })).toBeDisabled();
  await page.getByRole('button', { name: 'Marcar como recogido' }).click();
  await page.getByRole('button', { name: 'Finalizar entrega', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('button', { name: 'Confirmar entrega finalizada' }).click();
  await expect(page.getByRole('heading', { name: 'No tienes una entrega activa' })).toBeVisible();
  await page.getByRole('switch').check();
  await expect(page.getByRole('button', { name: 'Aceptar entrega FD-2051' })).toBeEnabled();
  await page.getByRole('button', { name: 'Aceptar entrega FD-2051' }).click();
  await expect(page.locator('.active-title')).toContainText('FD-2051');
});

test('carga, vacío, error y conflicto legibles con movimiento reducido', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce', colorScheme: 'dark' });
  await page.goto('/preview.html#/app/store');
  await page.getByLabel('Estado de ejemplo').selectOption('loading');
  await expect(page.getByRole('status', { name: 'Cargando entregas de demostración' })).toBeVisible();
  expect(await page.locator('.skeleton-row i').first().evaluate(el => getComputedStyle(el).animationName)).toBe('none');
  await page.getByLabel('Estado de ejemplo').selectOption('empty');
  await expect(page.getByRole('heading', { name: 'Todo por empezar' })).toBeVisible();
  await page.getByLabel('Estado de ejemplo').selectOption('error');
  await expect(page.getByText('No pudimos cargar las entregas.', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: 'Volver a intentar' }).click();
  await expect(page.locator('.order-table')).toBeVisible();
  await page.getByLabel('Estado de ejemplo').selectOption('conflict');
  await expect(page.getByText('Esta entrega ya fue aceptada.', { exact: false })).toBeVisible();
});

test('el atributo de tema se aplica antes de arrancar React', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('flashdelivery:theme:v1', 'dark'));
  await page.route('**/src/main.tsx', route => route.abort());
  await page.goto('/preview.html');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.locator('#design-root')).toBeEmpty();
});

for (const theme of ['light', 'dark']) {
  test(`opciones nativas legibles en todos los selectores: ${theme}`, async ({ page }) => {
    await page.addInitScript(theme => localStorage.setItem('flashdelivery:theme:v1', theme), theme);
    await page.goto('/preview.html#/app/store');
    await expect(page.getByRole('combobox', { name: 'Apariencia' })).toBeVisible();
    const options = await page.locator('select option').evaluateAll(elements => elements.map(element => {
      const style = getComputedStyle(element);
      const rgb = value => value.match(/[\d.]+/g).slice(0, 3).map(Number);
      const luminance = color => rgb(color).map(value => {
        const channel = value / 255;
        return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
      }).reduce((total, value, index) => total + value * [0.2126, 0.7152, 0.0722][index], 0);
      const foreground = luminance(style.color);
      const background = luminance(style.backgroundColor);
      return { text: element.textContent, background: style.backgroundColor, contrast: (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05) };
    }));
    expect(options.length).toBeGreaterThan(3);
    for (const option of options) {
      expect(option.background, option.text).not.toBe('rgba(0, 0, 0, 0)');
      expect(option.contrast, option.text).toBeGreaterThanOrEqual(4.5);
    }
    const appearance = page.getByRole('combobox', { name: 'Apariencia' });
    await appearance.focus();
    await appearance.press('Home');
    await appearance.press('ArrowDown');
    await appearance.press('Enter');
    await expect(appearance).toHaveValue('light');
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  });
}
