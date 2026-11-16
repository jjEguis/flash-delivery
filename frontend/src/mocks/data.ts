export type OrderStatus = 'PENDING' | 'ASSIGNED' | 'PICKED_UP' | 'DELIVERED' | 'CANCELLED' | 'FAILED';
export type DemoOrder = {
  id: string; pickupAddress: string; dropoffAddress: string; zone: string;
  fee: number; status: OrderStatus; time: string; courier?: string;
};

export const sampleOrders: DemoOrder[] = [
  { id: 'FD-2048', pickupAddress: 'Calle 17 # 3-42', dropoffAddress: 'Calle 18 # 5-24', zone: 'Centro', fee: 8500, status: 'PENDING', time: '10:42' },
  { id: 'FD-2047', pickupAddress: 'Calle 17 # 3-42', dropoffAddress: 'Carrera 4 # 12-31', zone: 'Centro', fee: 9500, status: 'ASSIGNED', time: '10:30', courier: 'Andrés Pérez' },
  { id: 'FD-2046', pickupAddress: 'Calle 17 # 3-42', dropoffAddress: 'Calle 22 # 8-10', zone: 'Centro', fee: 7500, status: 'PICKED_UP', time: '10:14', courier: 'Laura Gómez' },
  { id: 'FD-2045', pickupAddress: 'Calle 17 # 3-42', dropoffAddress: 'Carrera 12 # 26-09', zone: 'Centro', fee: 11000, status: 'DELIVERED', time: '09:58', courier: 'Andrés Pérez' },
  { id: 'FD-2044', pickupAddress: 'Calle 17 # 3-42', dropoffAddress: 'Calle 16 # 7-16', zone: 'Centro', fee: 8000, status: 'DELIVERED', time: '09:45', courier: 'Laura Gómez' },
  { id: 'FD-2043', pickupAddress: 'Calle 17 # 3-42', dropoffAddress: 'Carrera 5 # 20-18', zone: 'Centro', fee: 6500, status: 'PENDING', time: '09:36' },
  { id: 'FD-2042', pickupAddress: 'Calle 17 # 3-42', dropoffAddress: 'Calle 21 # 4-22', zone: 'Centro', fee: 7500, status: 'ASSIGNED', time: '09:20', courier: 'Camilo Díaz' },
  { id: 'FD-2041', pickupAddress: 'Calle 17 # 3-42', dropoffAddress: 'Carrera 6 # 18-30', zone: 'Centro', fee: 6000, status: 'CANCELLED', time: '09:05' },
];

export const offers: DemoOrder[] = [
  { id: 'FD-2051', pickupAddress: 'Calle 19 # 4-18', dropoffAddress: 'Carrera 5 # 22-16', zone: 'Centro', fee: 9000, status: 'PENDING', time: '10:45' },
  { id: 'FD-2050', pickupAddress: 'Carrera 3 # 18-06', dropoffAddress: 'Calle 23 # 6-21', zone: 'Centro', fee: 7500, status: 'PENDING', time: '10:41' },
];

export const money = (value: number) => new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }).format(value);
