import {test,expect} from '@playwright/test';
test('compilación normal ofrece GPS con consentimiento y excluye simulación',async({page})=>{
  await page.addInitScript(()=>localStorage.setItem('fd.session',JSON.stringify({token:'test',actor:{actorId:'c1',role:'COURIER'}})));
  await page.route('**/api/v1/**',route=>route.fulfill({json:{orderId:'o1',status:'ASSIGNED',updatedAt:new Date().toISOString(),location:null,freshness:'UNAVAILABLE'}}));
  await page.goto('/design-dist/geo.html#/order/o1');
  await expect(page.getByRole('heading',{name:'Compartir mi ubicación'})).toBeVisible();
  await expect(page.getByLabel('Fuente')).toHaveValue('BROWSER_GPS');
  await expect(page.getByLabel('Fuente').locator('option')).toHaveCount(1);
  await expect(page.getByRole('button',{name:'Iniciar simulación'})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Reiniciar',exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Activar GPS'})).toBeDisabled();
});
