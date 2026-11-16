import React from 'react';
import ReactDOM from 'react-dom/client';
import { HashRouter, Route, Routes, useParams } from 'react-router-dom';
import '@fontsource/manrope/latin-400.css';
import '@fontsource/manrope/latin-500.css';
import '@fontsource/manrope/latin-600.css';
import '@fontsource/manrope/latin-700.css';
import '@fontsource/manrope/latin-800.css';
import { ThemeProvider } from './app/ThemeProvider';
import { GeoPage } from './features/geo/GeoPage';
import './styles/geo.css';
function GeoRoute({ publicView = false }: { publicView?: boolean }) {
  const {id} = useParams();
  return <GeoPage key={`${publicView}:${id}`} publicView={publicView}/>;
}
ReactDOM.createRoot(document.getElementById('design-root')!).render(
  <React.StrictMode><ThemeProvider><HashRouter><Routes>
    <Route path="/order/:id" element={<GeoRoute/>}/><Route path="/tracking/:id" element={<GeoRoute publicView/>}/>
    <Route path="*" element={<main className="geo-main"><h1>Seguimiento de entregas</h1><p>Abre el mapa desde una entrega en <a href="http://127.0.0.1:8080/">la aplicación</a>.</p></main>}/>
  </Routes></HashRouter></ThemeProvider></React.StrictMode>,
);
