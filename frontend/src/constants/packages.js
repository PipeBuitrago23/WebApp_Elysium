export const METODOS_PAGO = ['Efectivo', 'Transferencia', 'Tarjeta', 'Otro'];

export const CATEGORIAS = ['Pilates', 'Fisioterapia', 'Combos', 'Prendas de Vestir'];

// Pilates base plans — duplicated for Individual and x2 Personas
const PILATES_BASE = [
  { nombre: 'Plan Basic 4 Ses',     sesiones: 4,  precio: 152000 },
  { nombre: 'Plan Pro 8 Ses',       sesiones: 8,  precio: 262000 },
  { nombre: 'Plan Advanced 12 Ses', sesiones: 12, precio: 334000 },
  { nombre: 'Plan Elite 16 Ses',    sesiones: 16, precio: 419000 },
  { nombre: 'Plan Master 20 Ses',   sesiones: 20, precio: 475000 },
  { nombre: 'Plan Pro Max 24 Ses',  sesiones: 24, precio: 524000 },
];

export const PACKAGES = {
  Pilates: [
    ...PILATES_BASE.map((p) => ({
      nombre: `${p.nombre} – Individual`,
      sesiones: p.sesiones,
      precio: p.precio,
    })),
    ...PILATES_BASE.map((p) => ({
      nombre: `${p.nombre} – x2 Personas`,
      sesiones: p.sesiones,
      precio: p.precio * 2,
    })),
  ],
  Fisioterapia: [
    { nombre: 'Terapia Individual',    sesiones: 1,  precio: 83000  },
    { nombre: 'Paquete 5 Ses',         sesiones: 5,  precio: 381000 },
    { nombre: 'Paquete 10 Ses',        sesiones: 10, precio: 714000 },
    { nombre: 'Drenaje Linfático',     sesiones: 1,  precio: 119000 },
    { nombre: 'Terapia Suelo Pélvico', sesiones: 1,  precio: 119000 },
  ],
  Combos: [
    { nombre: 'Plan Basic Plus 4P+2F',     sesiones: 6,  precio: 318000 },
    { nombre: 'Plan Pro Plus 8P+2F',       sesiones: 10, precio: 428000 },
    { nombre: 'Plan Advanced Plus 12P+3F', sesiones: 15, precio: 583000 },
    { nombre: 'Plan Elite Plus 16P+4F',    sesiones: 20, precio: 751000 },
  ],
  'Prendas de Vestir': [],
};
