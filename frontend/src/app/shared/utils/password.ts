// Sin caracteres que se confunden al dictarlos o copiarlos a mano (0/O, 1/l/I).
const ALFABETO_PASSWORD = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789';

/** Contraseña temporal aleatoria para cuentas que crea un administrador. */
export function generarPassword(largo = 12): string {
  const valores = crypto.getRandomValues(new Uint32Array(largo));
  return Array.from(valores, (v) => ALFABETO_PASSWORD[v % ALFABETO_PASSWORD.length]).join('');
}

/** Copia texto al portapapeles; solo existe en contextos seguros (https o localhost). */
export function copiarAlPortapapeles(texto: string): Promise<boolean> {
  if (!navigator.clipboard) return Promise.resolve(false);
  return navigator.clipboard.writeText(texto).then(
    () => true,
    () => false,
  );
}
