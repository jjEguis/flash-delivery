import {readFileSync} from 'node:fs';
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


test('tiles reciben solo el origen y la API no recibe Referer ni token de navegación',async({page,baseURL})=>{
  const tileHeaders=[],apiHeaders=[];
  const secret='o1.secret-referrer-regression';
  await page.route('https://tile.openstreetmap.org/**',async route=>{
    tileHeaders.push(await route.request().allHeaders());
    return route.fulfill({contentType:'image/png',body:readFileSync(new URL('../fixtures/map-tile.png',import.meta.url))});
  });
  await page.route('**/api/v1/**',async route=>{
    apiHeaders.push(await route.request().allHeaders());
    const path=new URL(route.request().url()).pathname;
    const body=path.endsWith('/route')?{orderId:'o1',status:'ASSIGNED',points:null,route:null}:
      {orderId:'o1',status:'ASSIGNED',updatedAt:new Date().toISOString(),location:{latitude:11.244,longitude:-74.211,recordedAt:new Date().toISOString(),source:'SIMULATED'},freshness:'FRESH'};
    return route.fulfill({json:body});
  });
  const response=await page.goto('/#/mapa/'+secret);
  expect(response.headers()['referrer-policy']).toBe('strict-origin');
  await expect.poll(()=>tileHeaders.length).toBeGreaterThan(0);
  expect(tileHeaders.every(headers=>headers.referer===baseURL+'/')).toBe(true);
  expect(tileHeaders.every(headers=>!JSON.stringify(headers).includes(secret))).toBe(true);
  expect(apiHeaders.length).toBeGreaterThan(0);
  expect(apiHeaders.every(headers=>!headers.referer)).toBe(true);
  await expect(page.getByText('Cargando mapa…')).toHaveCount(0);
  await expect(page.getByText(/No se pudo cargar el fondo/)).toHaveCount(0);
});
