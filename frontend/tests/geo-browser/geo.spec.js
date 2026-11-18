import {readFileSync} from 'node:fs';
import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
const sample={latitude:11.2408,longitude:-74.199,accuracyMeters:10,recordedAt:new Date().toISOString(),source:'SIMULATED'};
async function setup(page,{role='COURIER',location=null,freshness='UNAVAILABLE',status='ASSIGNED'}={}) {
  await page.addInitScript(role=>{
    localStorage.setItem('fd.session',JSON.stringify({token:'test-session',actor:{actorId:role==='STORE'?'store1':'courier1',role}}));
    window.__watchStarted=0;window.__watchCleared=0;
    navigator.geolocation.watchPosition=(success,error)=>{window.__watchStarted++;window.__gpsSuccess=success;window.__gpsError=error;return 42;};
    navigator.geolocation.clearWatch=()=>window.__watchCleared++;
  },role);
  await page.route('https://tile.openstreetmap.org/**', r=>r.fulfill({contentType:'image/png',body:readFileSync(new URL('../fixtures/map-tile.png',import.meta.url))}));
  const state={orderId:'o_1',status,updatedAt:new Date().toISOString(),location,freshness};
  const posts=[]; const deletes=[];
  await page.route('**/api/v1/**',async route=>{
    const request=route.request(); const url=request.url();
    if(url.endsWith('/route')) return route.fulfill({json:{orderId:'o_1',status:state.status,points:{pickup:{latitude:11.237,longitude:-74.201},dropoff:{latitude:11.235,longitude:-74.19}},route:state.location ? {geometry:{type:'LineString',coordinates:[[-74.211,11.244],[-74.209,11.242],[-74.207,11.240],[-74.201,11.237]]},distanceMeters:1500,durationSeconds:150,remainingMeters:1500,etaSeconds:150,progressMeters:0,phase:state.status,routeVersion:'r1',calculatedAt:new Date().toISOString(),stale:false,offRoute:false} : null}});
    if(request.method()==='POST'){
      const p=request.postDataJSON();posts.push(p);state.location=p;state.freshness='FRESH';
      return route.fulfill({status:202,json:{orderId:'o_1',recordedAt:p.recordedAt,accepted:true}});
    }
    if(request.method()==='DELETE'){deletes.push(url);state.location=null;state.freshness='UNAVAILABLE';return route.fulfill({status:204});}
    return route.fulfill({json:state});
  });
  return {state,posts,deletes};
}
for(const theme of ['light','dark'])for(const width of [360,390,768,1440]) {
  test(`mapa público ${theme} ${width}px con alternativa textual accesible`,async({page},info)=>{
    const external=[];
    page.on('request',r=>{if(!r.url().startsWith('http://127.0.0.1:5175')) external.push(r.url());});
    await setup(page,{location:{...sample,recordedAt:new Date().toISOString()},freshness:'FRESH'});
    await page.addInitScript(theme=>localStorage.setItem('flashdelivery:theme:v1',theme),theme);
    await page.setViewportSize({width,height:900});
    await page.goto('/geo.html#/tracking/o_1.secret');
    await expect(page.getByText('Modo simulación · Recorrido de demostración')).toBeVisible();
    await expect(page.getByText(/Latitud 11.24080/)).toBeVisible();
    await expect(page.getByText('Cargando mapa…')).toHaveCount(0);
    await expect(page.getByText(/No se pudo cargar el fondo/)).toHaveCount(0);
    await expect(page.locator('.maplibregl-canvas')).toBeVisible();
    await expect(page.getByRole('heading',{name:'Compartir mi ubicación'})).toHaveCount(0);
    await page.evaluate(()=>document.fonts.ready);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze()).violations).toEqual([]);
    expect(external.every(url=>url.startsWith('https://tile.openstreetmap.org/'))).toBe(true);
    await page.screenshot({path:info.outputPath(`map-${theme}-${width}.png`),fullPage:true});
  });
}
test('simulador exige consentimiento, publica, pausa, reanuda, reinicia y detiene',async({page})=>{
  const {posts,deletes}=await setup(page);
  await page.goto('/geo.html#/order/o_1');
  const start=page.getByRole('button',{name:'Iniciar simulación'});
  await expect(start).toBeDisabled();
  expect(await page.evaluate(()=>window.__watchStarted)).toBe(0);
  await page.getByRole('button',{name:'Usar inicio de demo en Santa Marta'}).click();
  await page.getByRole('checkbox').check();await start.click();
  await expect.poll(()=>posts.length,{timeout:7000}).toBe(1);
  expect(posts[0].source).toBe('SIMULATED');
  await expect(page.getByText('Modo simulación · Recorrido de demostración')).toBeVisible();
  await page.getByRole('button',{name:'Pausar',exact:true}).click();
  await expect(page.getByRole('button',{name:'Reanudar',exact:true})).toBeEnabled();
  await page.getByRole('button',{name:'Reanudar',exact:true}).click();
  await expect.poll(()=>posts.length,{timeout:7000}).toBe(2);
  expect(posts[1].latitude).not.toBe(posts[0].latitude);
  await page.getByRole('button',{name:'Reiniciar',exact:true}).click();
  await expect.poll(()=>posts.length,{timeout:7000}).toBe(3);
  expect(posts[2].latitude).toBe(posts[0].latitude);
  await page.getByRole('button',{name:'Detener y borrar ubicación'}).click();
  await expect.poll(()=>deletes.length).toBe(1);
  await expect(page.getByText('Sin posición disponible. No se muestran coordenadas de ejemplo.')).toBeVisible();
});
test('GPS no arranca sin consentimiento, denegación permite continuar por estados',async({page})=>{
  await setup(page);await page.goto('/geo.html#/order/o_1');
  await page.getByLabel('Fuente').selectOption('BROWSER_GPS');
  await expect(page.getByRole('button',{name:'Activar GPS'})).toBeDisabled();
  await page.getByRole('checkbox').check();await page.getByRole('button',{name:'Activar GPS'}).click();
  expect(await page.evaluate(()=>window.__watchStarted)).toBe(1);
  await page.evaluate(()=>window.__gpsError({code:1}));
  await expect(page.getByText(/No se pudo usar el GPS/)).toBeVisible();
  expect(await page.evaluate(()=>window.__watchCleared)).toBe(1);
  await expect(page.getByText('Asignada',{exact:true})).toBeVisible();
});
test('GPS publica coordenadas reales y detiene el watcher cuando cambia la sesión',async({page})=>{
  const {posts}=await setup(page);await page.goto('/geo.html#/order/o_1');
  await page.getByLabel('Fuente').selectOption('BROWSER_GPS');await page.getByRole('checkbox').check();
  await page.getByRole('button',{name:'Activar GPS'}).click();
  await page.evaluate(()=>window.__gpsSuccess({coords:{latitude:11.1,longitude:-74.2,accuracy:20},timestamp:Date.now()}));
  await expect.poll(()=>posts.length).toBe(1);expect(posts[0].source).toBe('BROWSER_GPS');
  await page.evaluate(()=>{localStorage.removeItem('fd.session');window.dispatchEvent(new StorageEvent('storage',{key:'fd.session'}));});
  await expect(page.getByText('La sesión cambió. Se detuvo el envío.')).toBeVisible();
  expect(await page.evaluate(()=>window.__watchCleared)).toBe(1);
});
test('datos obsoletos, mapa sin tiles y error de proveedor mantienen alternativa textual',async({page})=>{
  await setup(page,{role:'STORE',location:{...sample,recordedAt:new Date(Date.now()-45000).toISOString()},freshness:'STALE'});
  await page.route('https://tile.openstreetmap.org/**',r=>r.abort());
  await page.goto('/geo.html#/order/o_1');
  await expect(page.getByText(/Ubicación desactualizada/)).toBeVisible();
  await expect(page.getByText(/No se pudo cargar el fondo/)).toBeVisible();
  await expect(page.getByText(/Latitud 11.24080/)).toBeVisible();
  await expect(page.getByRole('link',{name:'OpenStreetMap',exact:true})).toBeVisible();
});
test('Redis caído mantiene el estado y permite reintentar sin coordenadas inventadas',async({page})=>{
  await setup(page);
  await page.route('**/api/v1/**/location',r=>r.fulfill({status:503,json:{error:{message:'Redis no disponible'}}}));
  await page.goto('/geo.html#/order/o_1');
  await expect(page.getByText('Asignada',{exact:true})).toBeVisible();
  await expect(page.getByText('Sin posición disponible. No se muestran coordenadas de ejemplo.')).toBeVisible();
  await expect(page.getByRole('button',{name:'Reintentar',exact:true})).toBeEnabled();
});
test('sin token válido no muestra ubicaciones ni controles de envío',async({page})=>{
  await setup(page);
  await page.route('**/api/v1/**',r=>r.fulfill({status:404,json:{error:{message:'No encontrado'}}}));
  await page.goto('/geo.html#/tracking/invalid');
  await expect(page.getByText('Este enlace o sesión no permite consultar la ubicación.')).toBeVisible();
  await expect(page.getByRole('button',{name:'Iniciar simulación'})).toHaveCount(0);
  await expect(page.getByRole('region',{name:'Mapa de la última ubicación'})).toHaveCount(0);
});
test('entrega terminada no ofrece compartir ubicación',async({page})=>{
  await setup(page,{status:'DELIVERED'});await page.goto('/geo.html#/order/o_1');
  await expect(page.getByText('Entregada',{exact:true})).toBeVisible();
  await expect(page.getByRole('checkbox')).toHaveCount(0);
});

test('el polling no se solapa y se detiene al cerrar la entrega',async({page})=>{
  const {state}=await setup(page,{role:'STORE'});
  let calls=0,inFlight=0,maximum=0;
  await page.route('**/api/v1/**/location',async route=>{
    calls++;inFlight++;maximum=Math.max(maximum,inFlight);
    await new Promise(resolve=>setTimeout(resolve,150));inFlight--;
    return route.fulfill({json:state});
  });
  await page.goto('/geo.html#/order/o_1');
  await expect(page.getByText('Asignada',{exact:true})).toBeVisible();
  state.status='DELIVERED';
  await expect(page.getByText('Entregada',{exact:true})).toBeVisible({timeout:10000});
  const stopped=calls;await page.waitForTimeout(6500);
  expect(calls).toBe(stopped);expect(maximum).toBe(1);
});
