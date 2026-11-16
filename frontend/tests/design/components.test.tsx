import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import { Button, StatusBadge } from '../../src/components/ui';
import { sampleOrders } from '../../src/mocks/data';

it('cada estado tiene etiqueta legible e icono decorativo', () => {
  render(<>{(['PENDING', 'ASSIGNED', 'PICKED_UP', 'DELIVERED', 'CANCELLED', 'FAILED'] as const).map(status => <StatusBadge key={status} status={status} />)}</>);
  for (const label of ['Por asignar', 'Asignada', 'Recogida', 'Entregada', 'Cancelada', 'Fallida']) {
    const badge = screen.getByText(label);
    expect(badge.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
  }
});

it('las acciones pendientes de implementación no aparentan estar disponibles', () => {
  render(<Button disabled>Guardar cambios</Button>);
  expect(screen.getByRole('button', { name: 'Guardar cambios' })).toBeDisabled();
});

it('las métricas de la maqueta se pueden derivar de sus registros sin porcentajes inventados', () => {
  expect(sampleOrders).toHaveLength(8);
  expect(sampleOrders.filter(order => order.status === 'DELIVERED').reduce((sum, order) => sum + order.fee, 0)).toBe(19000);
  expect(sampleOrders.filter(order => ['ASSIGNED', 'PICKED_UP'].includes(order.status))).toHaveLength(3);
});
