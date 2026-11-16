import {test,expect} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import {readFileSync,mkdtempSync,rmdirSync,mkdirSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';

test('simulador completo → API Gateway → Lambda → Redis → comercio y destinatario',async({browser,request})=>{
  const directory=mkdtempSync(join(tmpdir(),'flashdelivery-geo-'));
  const fixture=join(directory,'fixture.json');
  const python=process.env.GEO_PYTHON || resolve('../.venv/bin/python');
  const run=(operation)=>execFileSync(python,['-m','scripts.geo_fixture',operation,fixture],{cwd:resolve('../app'),stdio:'pipe'});
  run('create');
  const data=JSON.parse(readFileSync(fixture,'utf8'));
  const contexts=[];
  try {
    const courier=await browser.newContext();contexts.push(courier);
    await courier.addInitScript(session=>localStorage.setItem('fd.session',JSON.stringify(session)),data.sessions.COURIER);
    const page=await courier.newPage();
    await page.goto(`/design-dist/geo.html#/order/${data.order.orderId}`);
    await page.getByRole('checkbox').check();
    await page.getByRole('button',{name:'Iniciar simulación'}).click();
    const publicContext=await browser.newContext();contexts.push(publicContext);
    const recipient=await publicContext.newPage();
    await recipient.goto(`/design-dist/geo.html#/tracking/${encodeURIComponent(data.order.trackingToken)}`);
    await expect(recipient.getByText('Modo simulación · Recorrido ficticio')).toBeVisible({timeout:12000});
    const store=await browser.newContext();contexts.push(store);
    await store.addInitScript(session=>localStorage.setItem('fd.session',JSON.stringify(session)),data.sessions.STORE);
    const storePage=await store.newPage();
    await storePage.goto(`/design-dist/geo.html#/order/${data.order.orderId}`);
    await expect(storePage.getByRole('region',{name:'Mapa de la última ubicación'})).toBeVisible();
    await expect(page.getByText('Recorrido finalizado. Esto no marca el pedido como entregado.')).toBeVisible({timeout:45000});
    await expect(recipient.getByText(/Latitud 11.24320/)).toBeVisible({timeout:10000});
    if(process.env.GEO_EVIDENCE_DIR) {
      const directory=process.env.GEO_EVIDENCE_DIR;mkdirSync(directory,{recursive:true});
      await storePage.setViewportSize({width:1440,height:1000});
      await storePage.getByRole('combobox',{name:'Apariencia'}).selectOption('light');
      await expect(storePage.getByText(/Latitud 11.24320/)).toBeVisible({timeout:10000});
      await storePage.evaluate(()=>document.fonts.ready);
      await storePage.screenshot({path:join(directory,'comercio-claro-1440.png'),fullPage:true});
      await recipient.setViewportSize({width:390,height:844});
      await recipient.getByRole('combobox',{name:'Apariencia'}).selectOption('dark');
      await recipient.evaluate(()=>document.fonts.ready);
      await recipient.screenshot({path:join(directory,'destinatario-oscuro-390.png'),fullPage:true});
    }
    const endpoint=`/api/v1/orders/${data.order.orderId}`;
    for(const action of ['pickup','deliver']) {
      const response=await request.post(endpoint+'/'+action,{headers:{Authorization:'Bearer '+data.sessions.COURIER.token,'Idempotency-Key':'geo_ui_'+action}});
      expect(response.status()).toBe(200);
      data.created.requests.push([data.sessions.COURIER.actor.actorId,`dispatch.${action}.v1`,'geo_ui_'+action]);
      // El helper de limpieza necesita también las intenciones que se crearon desde el navegador.
    }
    const {writeFileSync}=await import('node:fs');writeFileSync(fixture,JSON.stringify(data),{mode:0o600});
    await expect(page.getByText('Entregada',{exact:true})).toBeVisible({timeout:10000});
    await expect(recipient.getByText('Aún no hay ubicación compartida')).toBeVisible({timeout:10000});
    await expect(storePage.getByText('Aún no hay ubicación compartida')).toBeVisible({timeout:10000});
  } finally {
    for(const context of contexts) await context.close();
    run('cleanup');rmdirSync(directory);
  }
});
