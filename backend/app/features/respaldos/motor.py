"""Copia de seguridad y restauración de toda la base de datos de EGRESA.

Formato: un .zip con manifest.json y un archivo por tabla en el formato COPY de PostgreSQL
(texto). Conserva los tipos exactos (uuid, jsonb, vector, fechas con zona) sin depender de
pg_dump, que no está en la imagen del backend. La copia se toma dentro de una sola
transacción REPEATABLE READ de solo lectura, así todas las tablas son de la misma foto.

La restauración también es una sola transacción: vacía las tablas de la copia, las recarga
en orden de dependencias y, si algo falla, no cambia nada. La bitácora nunca pierde
entradas: las posteriores a la copia se vuelven a insertar (es de solo agregado).
"""

import hashlib
import json
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from graphlib import TopologicalSorter
from pathlib import Path

from psycopg import errors as pg_errors
from psycopg import sql
from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.core.database import engine

FORMATO = "egresa-respaldo"
VERSION_FORMATO = 1
# El catálogo de copias no se respalda ni se restaura: tiene que sobrevivir para poder volver atrás.
TABLAS_EXCLUIDAS = frozenset({"system_backup", "scheduled_task_run"})
TABLA_BITACORA = "audit_log"
_BLOQUE = 64 * 1024


@dataclass
class ResumenCopia:
    tablas: int
    filas: int
    tamanio: int
    sha256: str


@dataclass
class ResultadoRestauracion:
    tablas: int
    filas: int
    bitacora_conservada: int
    # Tablas que no estaban en la copia pero dependían de ella y quedaron vacías.
    vaciadas_extra: list[str] = field(default_factory=list)


def sha256_de(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as archivo:
        while bloque := archivo.read(_BLOQUE):
            h.update(bloque)
    return h.hexdigest()


# ─── Copia ───────────────────────────────────────────────────────────────────


def generar(destino: Path, autor: str) -> ResumenCopia:
    """Escribe en `destino` la copia completa de la base."""
    with engine.connect().execution_options(isolation_level="REPEATABLE READ", postgresql_readonly=True) as conn:
        with conn.begin():
            columnas = _columnas_por_tabla(conn)
            orden = _orden_por_dependencias(conn, set(columnas))
            crudo = conn.connection.driver_connection
            manifiesto_tablas = []
            with zipfile.ZipFile(destino, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for tabla in orden:
                    filas = _copiar_tabla_a_zip(crudo, tabla, columnas[tabla], zf)
                    manifiesto_tablas.append({"nombre": tabla, "columnas": columnas[tabla], "filas": filas})
                version = conn.execute(text("SHOW server_version")).scalar()
                zf.writestr(
                    "manifest.json",
                    json.dumps(
                        {
                            "formato": FORMATO,
                            "version": VERSION_FORMATO,
                            "creado_en": datetime.now(timezone.utc).isoformat(),
                            "creado_por": autor,
                            "postgres": version,
                            "tablas": manifiesto_tablas,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                )
    return ResumenCopia(
        tablas=len(manifiesto_tablas),
        filas=sum(t["filas"] for t in manifiesto_tablas),
        tamanio=destino.stat().st_size,
        sha256=sha256_de(destino),
    )


def _copiar_tabla_a_zip(crudo, tabla: str, columnas: list[str], zf: zipfile.ZipFile) -> int:
    consulta = sql.SQL("COPY {} ({}) TO STDOUT").format(
        sql.Identifier(tabla), sql.SQL(", ").join(map(sql.Identifier, columnas))
    )
    filas = 0
    with crudo.cursor() as cur, cur.copy(consulta) as copia, zf.open(f"datos/{tabla}.copy", "w") as archivo:
        for bloque in copia:
            datos = bytes(bloque)
            archivo.write(datos)
            # En el formato texto de COPY cada fila es exactamente una línea.
            filas += datos.count(b"\n")
    return filas


# ─── Lectura y validación de un .zip ─────────────────────────────────────────


def leer_manifiesto(ruta: Path) -> dict:
    """Valida que el archivo sea una copia de EGRESA y devuelve su manifiesto."""
    try:
        with zipfile.ZipFile(ruta) as zf:
            manifiesto = json.loads(zf.read("manifest.json"))
            nombres = set(zf.namelist())
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BusinessException("El archivo no es una copia de seguridad de EGRESA.") from exc
    if manifiesto.get("formato") != FORMATO:
        raise BusinessException("El archivo no es una copia de seguridad de EGRESA.")
    if manifiesto.get("version") != VERSION_FORMATO:
        raise BusinessException("La copia es de un formato que esta versión de EGRESA no reconoce.")
    tablas = manifiesto.get("tablas")
    if not isinstance(tablas, list) or not tablas:
        raise BusinessException("La copia no contiene tablas.")
    for tabla in tablas:
        if f"datos/{tabla.get('nombre')}.copy" not in nombres:
            raise BusinessException(f"La copia está incompleta: falta la tabla {tabla.get('nombre')}.")
    return manifiesto


# ─── Restauración ────────────────────────────────────────────────────────────


def restaurar(
    db: Session, ruta: Path, *, simulacro: bool, registrar_en_bitacora: Callable[[], None]
) -> ResultadoRestauracion:
    """Reemplaza los datos de la base por los de la copia, todo o nada.

    Con `simulacro` hace exactamente lo mismo y al final deshace todo: sirve para comprobar
    que la copia se puede restaurar sin tocar los datos.
    """
    manifiesto = leer_manifiesto(ruta)
    conn = db.connection()
    actuales = _columnas_por_tabla(conn)
    tablas = {t["nombre"]: t["columnas"] for t in manifiesto["tablas"] if t["nombre"] not in TABLAS_EXCLUIDAS}
    _validar_compatibilidad(tablas, actuales)

    try:
        db.execute(text("SET LOCAL lock_timeout = '15s'"))
        conserva_bitacora = TABLA_BITACORA in tablas
        if conserva_bitacora:
            db.execute(text(f"CREATE TEMP TABLE _bitacora_previa ON COMMIT DROP AS SELECT * FROM {TABLA_BITACORA}"))

        vaciadas_extra = sorted(_tablas_que_referencian(conn, set(tablas)) - set(tablas) - TABLAS_EXCLUIDAS)
        lista = sql.SQL(", ").join(map(sql.Identifier, sorted(tablas)))
        crudo = conn.connection.driver_connection
        with crudo.cursor() as cur:
            cur.execute(sql.SQL("TRUNCATE {} CASCADE").format(lista))

        filas = 0
        with zipfile.ZipFile(ruta) as zf:
            for tabla in _orden_por_dependencias(conn, set(tablas)):
                filas += _cargar_tabla_desde_zip(crudo, tabla, tablas[tabla], zf)

        conservadas = _reinsertar_bitacora(db, actuales[TABLA_BITACORA]) if conserva_bitacora else 0
        registrar_en_bitacora()
        db.flush()
    except (pg_errors.Error, DBAPIError) as exc:
        db.rollback()
        original = getattr(exc, "orig", None) or exc
        if isinstance(original, pg_errors.LockNotAvailable):
            raise BusinessException(
                "La base está ocupada en este momento. Probá de nuevo en un minuto; no se cambió nada."
            ) from exc
        primera_linea = str(original).splitlines()[0] if str(original) else original.__class__.__name__
        raise BusinessException(f"La copia no se pudo restaurar ({primera_linea}). No se cambió nada.") from exc

    if simulacro:
        db.rollback()
    else:
        db.commit()
    return ResultadoRestauracion(
        tablas=len(tablas), filas=filas, bitacora_conservada=conservadas, vaciadas_extra=vaciadas_extra
    )


def _validar_compatibilidad(copia: dict[str, list[str]], actuales: dict[str, list[str]]) -> None:
    faltan_tablas = sorted(set(copia) - set(actuales))
    if faltan_tablas:
        raise BusinessException(
            f"La copia tiene tablas que esta versión ya no usa ({', '.join(faltan_tablas)}). No se puede restaurar."
        )
    for tabla, columnas in copia.items():
        sobran = sorted(set(columnas) - set(actuales[tabla]))
        if sobran:
            raise BusinessException(
                f"La tabla {tabla} de la copia tiene columnas que ya no existen ({', '.join(sobran)})."
            )


def _cargar_tabla_desde_zip(crudo, tabla: str, columnas: list[str], zf: zipfile.ZipFile) -> int:
    consulta = sql.SQL("COPY {} ({}) FROM STDIN").format(
        sql.Identifier(tabla), sql.SQL(", ").join(map(sql.Identifier, columnas))
    )
    filas = 0
    with crudo.cursor() as cur, cur.copy(consulta) as copia, zf.open(f"datos/{tabla}.copy") as archivo:
        while bloque := archivo.read(_BLOQUE):
            copia.write(bloque)
            filas += bloque.count(b"\n")
    return filas


def _reinsertar_bitacora(db: Session, columnas: list[str]) -> int:
    """Vuelve a agregar las entradas de bitácora que no estaban en la copia.

    Si el usuario de una entrada ya no existe tras restaurar, la entrada se conserva sin
    usuario en vez de perderse.
    """
    destino = sql.SQL(", ").join(map(sql.Identifier, columnas))
    origen = sql.SQL(", ").join(
        sql.SQL("CASE WHEN EXISTS (SELECT 1 FROM app_user u WHERE u.id = p.user_id) THEN p.user_id END")
        if col == "user_id"
        else sql.SQL("p.{}").format(sql.Identifier(col))
        for col in columnas
    )
    consulta = sql.SQL(
        "INSERT INTO {tabla} ({destino}) SELECT {origen} FROM _bitacora_previa p "
        "WHERE NOT EXISTS (SELECT 1 FROM {tabla} a WHERE a.id = p.id)"
    ).format(tabla=sql.Identifier(TABLA_BITACORA), destino=destino, origen=origen)
    crudo = db.connection().connection.driver_connection
    with crudo.cursor() as cur:
        cur.execute(consulta)
        return cur.rowcount


# ─── Esquema ─────────────────────────────────────────────────────────────────


def _columnas_por_tabla(conn: Connection) -> dict[str, list[str]]:
    filas = conn.execute(
        text(
            """SELECT c.table_name, array_agg(c.column_name::text ORDER BY c.ordinal_position)
               FROM information_schema.columns c
               JOIN information_schema.tables t
                 ON t.table_schema = c.table_schema AND t.table_name = c.table_name
               WHERE c.table_schema = 'public' AND t.table_type = 'BASE TABLE'
               GROUP BY c.table_name"""
        )
    )
    return {tabla: list(columnas) for tabla, columnas in filas if tabla not in TABLAS_EXCLUIDAS}


def _dependencias(conn: Connection) -> list[tuple[str, str]]:
    """Pares (tabla hija, tabla padre) de las claves foráneas del esquema public."""
    filas = conn.execute(
        text(
            """SELECT hija.relname, padre.relname
               FROM pg_constraint fk
               JOIN pg_class hija ON hija.oid = fk.conrelid
               JOIN pg_class padre ON padre.oid = fk.confrelid
               WHERE fk.contype = 'f' AND fk.connamespace = 'public'::regnamespace"""
        )
    )
    return [(hija, padre) for hija, padre in filas]


def _orden_por_dependencias(conn: Connection, tablas: set[str]) -> list[str]:
    """Tablas ordenadas para que cada una se cargue después de las que referencia."""
    grafo: dict[str, set[str]] = {tabla: set() for tabla in sorted(tablas)}
    for hija, padre in _dependencias(conn):
        if hija in tablas and padre in tablas and hija != padre:
            grafo[hija].add(padre)
    return list(TopologicalSorter(grafo).static_order())


def _tablas_que_referencian(conn: Connection, tablas: set[str]) -> set[str]:
    """Todas las tablas que TRUNCATE ... CASCADE vaciaría además de `tablas`."""
    hijas_de: dict[str, set[str]] = {}
    for hija, padre in _dependencias(conn):
        hijas_de.setdefault(padre, set()).add(hija)
    alcanzadas = set(tablas)
    pendientes = list(tablas)
    while pendientes:
        for hija in hijas_de.get(pendientes.pop(), ()):
            if hija not in alcanzadas:
                alcanzadas.add(hija)
                pendientes.append(hija)
    return alcanzadas
