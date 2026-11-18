import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
async function fixture(page,{theme='light',active=false,conflict=false}={}) {
  await page.addInitScript(theme=>{localStorage.setItem('flashdelivery:theme:v1',theme);localStorage.setItem('fd.session',JSON.stringify({token:'test',actor:{role:'ADMIN',actorId:'admin'}}));},theme);
  let profile={storeId:'store_1',name:'Panadería del Parque',zoneId:'centro',enabled:false,approvalStatus:'PENDING',version:1};let events=[];const changes=[];let failed=conflict;
  await page.route('**/api/v1/**',async route=>{
    const req=route.request(),url=new URL(req.url()),path=url.pathname.slice(7);let body;
    if(path==='/zones')body={items:[{zoneId:'centro',name:'Centro'}]};
    else if(path==='/admin/stores')body={items:url.searchParams.get('status')===profile.approvalStatus?[profile]:[],nextCursor:null};
    else if(path==='/admin/couriers')body={items:active?[{courierId:'courier_1',name:'Ana Repartidora',zoneId:'centro',enabled:true,approvalStatus:'ENABLED',version:2}]:[],nextCursor:null};
    else if(path==='/admin/couriers/courier_1')body={courierId:'courier_1',name:'Ana Repartidora',zoneId:'centro',enabled:true,approvalStatus:'ENABLED',version:2,activeOrderId:'order_1'};
    else if(path.endsWith('/events'))body={items:events,nextCursor:null};
    else if(path==='/admin/stores/store_1'&&req.method()==='PATCH'){
      changes.push(req.postDataJSON());if(failed){failed=false;profile={...profile,version:2};return route.fulfill({status:409,json:{error:{message:'El perfil cambió; actualiza antes de confirmar'}}});}
      const input=req.postDataJSON();events=[{eventId:'a_'+profile.version,actorId:'admin',occurredAt:'2026-11-18T12:00:00Z',fromStatus:profile.approvalStatus,toStatus:input.enabled?'ENABLED':'SUSPENDED',profileVersion:profile.version+1,reason:input.reason},...events];
      profile={...profile,version:profile.version+1,enabled:input.enabled,approvalStatus:input.enabled?'ENABLED':'SUSPENDED'};body=profile;
    }else if(path==='/admin/stores/store_1')body=profile;
    else throw Error('Sin fixture: '+path);
    await route.fulfill({json:body});
  });return changes;
}
for(const theme of ['light','dark'])for(const width of [390,1440])test(`aprobación auditada ${theme} ${width}`,async({page},info)=>{
  const changes=await fixture(page,{theme});await page.setViewportSize({width,height:1000});await page.goto('/#/admin');
  const review=page.getByRole('button',{name:'Revisar perfil de Panadería del Parque'});await review.click();
  const dialog=page.getByRole('dialog',{name:'Revisar perfil'});await expect(dialog.getByRole('heading',{name:'Panadería del Parque'})).toBeVisible();
  await expect(dialog.getByRole('button',{name:'Habilitar perfil'})).toBeDisabled();
  await dialog.getByLabel('Motivo de la decisión').fill('Documentación verificada');await dialog.getByRole('button',{name:'Habilitar perfil'}).click();
  await expect(dialog.getByRole('button',{name:'Cancelar',exact:true})).toBeFocused();await dialog.getByRole('button',{name:'Cancelar',exact:true}).click();expect(changes).toEqual([]);
  await dialog.getByRole('button',{name:'Habilitar perfil'}).click();await dialog.getByRole('button',{name:'Confirmar decisión'}).click();
  await expect(dialog.getByRole('status')).toHaveText('Estado confirmado.');await expect(dialog.getByText('Documentación verificada',{exact:true})).toBeVisible();
  expect(changes).toEqual([{enabled:true,expectedVersion:1,reason:'Documentación verificada'}]);
  expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze()).violations).toEqual([]);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.screenshot({path:info.outputPath(`approval-${theme}-${width}.png`),fullPage:true});
  await page.keyboard.press('Escape');await expect(dialog).toHaveCount(0);
  await page.getByLabel('Estado de comercios').selectOption('ENABLED');await review.click();await expect(dialog.getByText('Habilitado',{exact:true}).first()).toBeVisible();
  await dialog.getByLabel('Motivo de la decisión').fill('Pausa solicitada');await dialog.getByRole('button',{name:'Suspender perfil'}).click();await dialog.getByRole('button',{name:'Confirmar decisión'}).click();
  await expect(dialog.getByText('Suspendido',{exact:true}).first()).toBeVisible();await expect(dialog.getByText('Pausa solicitada',{exact:true})).toBeVisible();
  await dialog.getByLabel('Motivo de la decisión').fill('Regreso a operación');await dialog.getByRole('button',{name:'Habilitar perfil'}).click();await dialog.getByRole('button',{name:'Confirmar decisión'}).click();
  await expect(dialog.getByText('Regreso a operación',{exact:true})).toBeVisible();expect(changes.map(change=>change.expectedVersion)).toEqual([1,2,3]);
});
test('conflicto de versión actualiza el perfil y exige una nueva confirmación',async({page})=>{
  const changes=await fixture(page,{conflict:true});await page.goto('/#/admin');await page.getByRole('button',{name:'Revisar perfil de Panadería del Parque'}).click();
  const dialog=page.getByRole('dialog',{name:'Revisar perfil'});await dialog.getByLabel('Motivo de la decisión').fill('Verificado');await dialog.getByRole('button',{name:'Habilitar perfil'}).click();await dialog.getByRole('button',{name:'Confirmar decisión'}).click();
  await expect(dialog.getByRole('alert')).toContainText('El perfil cambió');await expect(dialog.locator('dd').last()).toHaveText('2');
  await expect(dialog.getByLabel('Motivo de la decisión')).toHaveValue('Verificado');await dialog.getByRole('button',{name:'Habilitar perfil'}).click();await dialog.getByRole('button',{name:'Confirmar decisión'}).click();
  await expect(dialog.getByRole('status')).toBeVisible();expect(changes.map(c=>c.expectedVersion)).toEqual([1,2]);
});
test('repartidor con entrega activa muestra el bloqueo de suspensión',async({page})=>{
  await fixture(page,{active:true});await page.goto('/#/admin');await page.getByLabel('Estado de repartidores').selectOption('ENABLED');await page.getByRole('button',{name:'Revisar perfil de Ana Repartidora'}).click();
  const dialog=page.getByRole('dialog',{name:'Revisar perfil'});await expect(dialog.getByText(/Entrega activa: order_1/)).toBeVisible();await dialog.getByLabel('Motivo de la decisión').fill('Revisión');await expect(dialog.getByRole('button',{name:'Suspender perfil'})).toBeDisabled();
});
test('error recuperable y paginación de perfiles',async({page})=>{
  await fixture(page);let count=0,failedPage=false;
  await page.route('**/api/v1/admin/stores?**',async route=>{
    count++;if(count===1)return route.fulfill({status:503,json:{error:{message:'Consulta temporalmente no disponible'}}});
    const next=new URL(route.request().url()).searchParams.has('cursor');
    if(next&&!failedPage){failedPage=true;return route.fulfill({status:503,json:{error:{message:'Página no disponible'}}});}
    await route.fulfill({json:{items:[{storeId:next?'s2':'s1',name:next?'Segundo perfil':'Primer perfil',zoneId:'centro',approvalStatus:'PENDING',version:1}],nextCursor:next?null:'opaque'}});
  });
  await page.goto('/#/admin');await expect(page.getByRole('alert')).toContainText('Consulta temporalmente no disponible');await page.getByRole('button',{name:'Reintentar',exact:true}).click();
  await expect(page.getByText('Primer perfil',{exact:true})).toBeVisible();await page.getByRole('button',{name:'Cargar más comercios'}).click();
  await expect(page.getByRole('alert')).toContainText('Página no disponible');await page.getByRole('button',{name:'Cargar más comercios'}).click();
  await expect(page.getByText('Segundo perfil',{exact:true})).toBeVisible();await expect(page.getByText('Primer perfil',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'Cargar más comercios'})).toHaveCount(0);
});
