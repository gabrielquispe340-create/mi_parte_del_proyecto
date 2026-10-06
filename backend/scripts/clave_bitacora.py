"""Clave de desarrollador de la bitácora confidencial.

    python -m scripts.clave_bitacora              genera una clave nueva y su clave pública
    python -m scripts.clave_bitacora "<clave>"    calcula la clave pública de una clave existente

La clave de desarrollador NO se guarda en ningún lado del sistema ni en el repositorio:
quien la tenga es el único que puede leer la bitácora. En el servidor solo va la clave
pública, en la variable BITACORA_CLAVE_PUBLICA. Si la clave se pierde, las entradas
cifradas con ella no se pueden recuperar.
"""

import sys

from app.security.cifrado_bitacora import clave_publica_de, generar_clave_desarrollador


def main() -> None:
    nueva = len(sys.argv) < 2
    clave = generar_clave_desarrollador() if nueva else sys.argv[1]
    publica = clave_publica_de(clave)
    if nueva:
        print("Clave de desarrollador (guardala en un lugar seguro, no se vuelve a mostrar):")
        print(f"  {clave}\n")
    print("Variable para el servidor (Railway / .env):")
    print(f"  BITACORA_CLAVE_PUBLICA={publica}")


if __name__ == "__main__":
    main()
