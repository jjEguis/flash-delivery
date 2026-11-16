// Compatibilidad de enlaces previos: toda la experiencia real vive ahora en el shell principal.
const [,kind,id] = location.hash.split('/');
const route = kind === 'tracking' ? 'mapa' : 'ubicacion';
location.replace(id ? `/#/${route}/${id}` : '/');
