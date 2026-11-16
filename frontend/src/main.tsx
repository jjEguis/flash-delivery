import React from 'react';
import ReactDOM from 'react-dom/client';
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import '@fontsource/manrope/latin-400.css';
import '@fontsource/manrope/latin-500.css';
import '@fontsource/manrope/latin-600.css';
import '@fontsource/manrope/latin-700.css';
import '@fontsource/manrope/latin-800.css';
import { ThemeProvider } from './app/ThemeProvider';
import { DemoProvider } from './app/DemoProvider';
import { AppShell } from './app/AppShell';
import { StorePreview } from './features/store/StorePreview';
import { CourierPreview } from './features/courier/CourierPreview';
import { AdminPreview, NotFoundPreview, TrackingPreview } from './features/other/SecondaryPreview';

ReactDOM.createRoot(document.getElementById('design-root')!).render(
  <React.StrictMode><ThemeProvider><DemoProvider><HashRouter><Routes><Route element={<AppShell />}>
    <Route index element={<Navigate to="/app/store" replace />} />
    <Route path="/app/store" element={<StorePreview />} /><Route path="/app/store/orders" element={<StorePreview />} />
    <Route path="/app/courier" element={<CourierPreview />} /><Route path="/app/courier/available" element={<CourierPreview />} />
    <Route path="/app/courier/history" element={<CourierPreview />} /><Route path="/track/demo" element={<TrackingPreview />} />
    <Route path="/app/admin" element={<AdminPreview />} /><Route path="*" element={<NotFoundPreview />} />
  </Route></Routes></HashRouter></DemoProvider></ThemeProvider></React.StrictMode>,
);
