"""Reportes personalizados (requisito general 5).

El usuario elige la fuente, las columnas y su orden, los filtros y el orden de las filas;
ve una vista previa paginada y lo exporta a Excel, PDF o HTML, o lo manda por correo.
Todo se valida contra el catálogo (catalogo.py): una columna o filtro que no está en la
lista no llega nunca a la consulta.
"""

import uuid
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import Select, and_, func, select
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException, ResourceNotFoundException
from app.features.bitacora.service import BitacoraService
from app.features.reportes.catalogo import FUENTES, Columna, Contexto, Filtro, Fuente
from app.features.reportes.schema import (
    ColumnaCatalogo,
    ConsultaReporte,
    EnviarReporte,
    ExportarReporte,
    FiltroCatalogo,
    FuenteCatalogo,
    OpcionFiltro,
    OrdenReporte,
    VistaPreviaReporte,
)
from app.shared.email_service import EmailService
from app.shared.exportacion import ZONA_BOLIVIA, Tabla, a_excel, a_html, a_pdf, texto_celda

MAX_FILAS_EXPORTACION = 5000
_FORMATOS = {
    "excel": ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", a_excel),
    "pdf": ("pdf", "application/pdf", a_pdf),
    "html": ("html", "text/html; charset=utf-8", a_html),
}
_NOMBRE_FORMATO = {"excel": "Excel", "pdf": "PDF", "html": "HTML"}


class Archivo:
    def __init__(self, contenido: bytes, nombre: str, tipo: str, total: int, exportadas: int) -> None:
        self.contenido = contenido
        self.nombre = nombre
        self.tipo = tipo
        self.total = total
        self.exportadas = exportadas


class ReporteService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ─── Catálogo ────────────────────────────────────────────────────────────

    def catalogo(self, ctx: Contexto) -> list[FuenteCatalogo]:
        return [self._fuente_catalogo(f, ctx) for f in FUENTES.values() if ctx.rol in f.roles]

    def _fuente_catalogo(self, fuente: Fuente, ctx: Contexto) -> FuenteCatalogo:
        return FuenteCatalogo(
            clave=fuente.clave,
            nombre=fuente.nombre,
            descripcion=fuente.descripcion,
            columnas=[self._columna_catalogo(c) for c in fuente.columnas if c.visible(ctx)],
            filtros=[
                FiltroCatalogo(
                    clave=f.clave,
                    etiqueta=f.etiqueta,
                    tipo=f.tipo,
                    opciones=[OpcionFiltro(valor=v, etiqueta=e) for v, e in self._opciones(f).items()],
                )
                for f in fuente.filtros
                if f.visible(ctx)
            ],
            orden=[OrdenReporte(columna=c, direccion=d) for c, d in fuente.orden],
        )

    @staticmethod
    def _columna_catalogo(c: Columna) -> ColumnaCatalogo:
        return ColumnaCatalogo(clave=c.clave, etiqueta=c.etiqueta, tipo=c.tipo, por_defecto=c.por_defecto)

    def _opciones(self, filtro: Filtro) -> dict[str, str]:
        if filtro.opciones_de is not None:
            return filtro.opciones_de(self.db)
        # Dos valores con el mismo texto se muestran una sola vez.
        vistos: dict[str, str] = {}
        for valor, etiqueta in filtro.opciones.items():
            if etiqueta not in vistos.values():
                vistos[valor] = etiqueta
        return vistos

    # ─── Consulta ────────────────────────────────────────────────────────────

    def _armar(self, ctx: Contexto, consulta: ConsultaReporte) -> tuple[Fuente, list[Columna], Select, list[str]]:
        fuente = FUENTES.get(consulta.fuente)
        if fuente is None or ctx.rol not in fuente.roles:
            raise ResourceNotFoundException("Ese reporte no existe o no está disponible para tu cuenta.")
        visibles = {c.clave: c for c in fuente.columnas if c.visible(ctx)}
        elegidas: list[Columna] = []
        for clave in consulta.columnas:
            if clave not in visibles:
                raise BusinessException(f"La columna «{clave}» no está disponible en este reporte.")
            if visibles[clave] not in elegidas:
                elegidas.append(visibles[clave])

        stmt = fuente.base(ctx).with_only_columns(*(c.expr(ctx).label(c.clave) for c in elegidas))
        filtros = {f.clave: f for f in fuente.filtros if f.visible(ctx)}
        textos_filtros = []
        for clave, valor in consulta.filtros.items():
            filtro = filtros.get(clave)
            if filtro is None:
                raise BusinessException(f"El filtro «{clave}» no está disponible en este reporte.")
            condicion, texto = self._condicion(filtro, valor, ctx)
            if condicion is not None:
                stmt = stmt.where(condicion)
                textos_filtros.append(f"{filtro.etiqueta}: {texto}")

        textos_orden = []
        for orden in consulta.orden or [OrdenReporte(columna=c, direccion=d) for c, d in fuente.orden]:
            columna = visibles.get(orden.columna)
            if columna is None:
                raise BusinessException(f"No se puede ordenar por «{orden.columna}».")
            expr = columna.expr(ctx)
            stmt = stmt.order_by(expr.desc().nulls_last() if orden.direccion == "desc" else expr.asc().nulls_last())
            textos_orden.append(f"{columna.etiqueta} ({'mayor a menor' if orden.direccion == 'desc' else 'menor a mayor'})")

        descripcion = [
            "Filtros: " + ("; ".join(textos_filtros) if textos_filtros else "ninguno (todos los registros)"),
            "Orden: " + ", ".join(textos_orden),
        ]
        return fuente, elegidas, stmt, descripcion

    def _condicion(self, filtro: Filtro, valor: Any, ctx: Contexto) -> tuple[Any, str]:
        expr = filtro.expr(ctx)
        if filtro.tipo == "texto":
            texto = str(valor or "").strip()[:120]
            if not texto:
                return None, ""
            patron = texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            return expr.ilike(f"%{patron}%", escape="\\"), f"contiene «{texto}»"

        if filtro.tipo == "opciones":
            if not isinstance(valor, list):
                raise BusinessException(f"El filtro «{filtro.etiqueta}» espera una lista de opciones.")
            opciones = filtro.opciones_de(self.db) if filtro.opciones_de else filtro.opciones
            elegidas = [str(v) for v in valor if str(v) in opciones]
            if not elegidas:
                return None, ""
            # Un texto puede abarcar varios valores (p. ej. dos estados que se muestran igual).
            etiquetas = {opciones[v] for v in elegidas}
            valores = [v for v, e in opciones.items() if e in etiquetas]
            return expr.in_(valores), ", ".join(sorted(etiquetas))

        if filtro.tipo == "fechas":
            if not isinstance(valor, dict):
                raise BusinessException(f"El filtro «{filtro.etiqueta}» espera un rango de fechas.")
            desde, hasta = self._fecha(valor.get("desde"), filtro), self._fecha(valor.get("hasta"), filtro)
            condiciones, textos = [], []
            if desde:
                condiciones.append(expr >= datetime.combine(desde, datetime.min.time(), ZONA_BOLIVIA))
                textos.append(f"desde {desde:%d/%m/%Y}")
            if hasta:
                condiciones.append(expr < datetime.combine(hasta + timedelta(days=1), datetime.min.time(), ZONA_BOLIVIA))
                textos.append(f"hasta {hasta:%d/%m/%Y}")
            if desde and hasta and desde > hasta:
                raise BusinessException(f"En «{filtro.etiqueta}» la fecha inicial es posterior a la final.")
            return (and_(*condiciones), " ".join(textos)) if condiciones else (None, "")

        if filtro.tipo == "numeros":
            if not isinstance(valor, dict):
                raise BusinessException(f"El filtro «{filtro.etiqueta}» espera un rango de números.")
            minimo, maximo = self._numero(valor.get("min"), filtro), self._numero(valor.get("max"), filtro)
            condiciones, textos = [], []
            if minimo is not None:
                condiciones.append(expr >= minimo)
                textos.append(f"desde {minimo:g}")
            if maximo is not None:
                condiciones.append(expr <= maximo)
                textos.append(f"hasta {maximo:g}")
            return (and_(*condiciones), " ".join(textos)) if condiciones else (None, "")

        raise BusinessException(f"Tipo de filtro desconocido: {filtro.tipo}")

    @staticmethod
    def _fecha(valor: Any, filtro: Filtro) -> date | None:
        if valor in (None, ""):
            return None
        try:
            return date.fromisoformat(str(valor)[:10])
        except ValueError:
            raise BusinessException(f"«{valor}» no es una fecha válida en «{filtro.etiqueta}».") from None

    @staticmethod
    def _numero(valor: Any, filtro: Filtro) -> float | None:
        if valor in (None, ""):
            return None
        try:
            return float(valor)
        except (TypeError, ValueError):
            raise BusinessException(f"«{valor}» no es un número válido en «{filtro.etiqueta}».") from None

    @staticmethod
    def _valor(columna: Columna, valor: Any) -> Any:
        if columna.tipo == "estado" and valor is not None:
            return columna.opciones.get(valor, valor)
        if isinstance(valor, uuid.UUID):
            return str(valor)
        return valor

    def _total(self, stmt: Select) -> int:
        return self.db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0

    # ─── Vista previa y archivos ─────────────────────────────────────────────

    def vista_previa(self, ctx: Contexto, consulta: ConsultaReporte, pagina: int, tamanio: int) -> VistaPreviaReporte:
        _, columnas, stmt, descripcion = self._armar(ctx, consulta)
        filas = self.db.execute(stmt.limit(tamanio).offset((pagina - 1) * tamanio)).all()
        return VistaPreviaReporte(
            columnas=[self._columna_catalogo(c) for c in columnas],
            filas=[[self._valor(c, v) for c, v in zip(columnas, fila)] for fila in filas],
            total=self._total(stmt),
            pagina=pagina,
            tamanio=tamanio,
            descripcion=descripcion,
        )

    def generar(self, ctx: Contexto, consulta: ExportarReporte, autor: str | None) -> Archivo:
        fuente, columnas, stmt, descripcion = self._armar(ctx, consulta)
        total = self._total(stmt)
        filas = self.db.execute(stmt.limit(MAX_FILAS_EXPORTACION)).all()
        ahora = datetime.now(ZONA_BOLIVIA)
        cantidad = f"{total} registros."
        if total > len(filas):
            cantidad = f"{total} registros; se incluyen los primeros {len(filas)}."
        tabla = Tabla(
            titulo=(consulta.titulo or "").strip() or f"Reporte de {fuente.nombre.lower()}",
            encabezados=[c.etiqueta for c in columnas],
            filas=[[self._valor(c, v) for c, v in zip(columnas, fila)] for fila in filas],
            descripcion=[f"Generado el {texto_celda(ahora)} por {autor or 'EGRESA'}.", *descripcion, cantidad],
            tipos=["numero" if c.tipo == "numero" else "texto" for c in columnas],
        )
        extension, tipo, convertir = _FORMATOS[consulta.formato]
        nombre = f"reporte-{fuente.clave}-{ahora:%Y%m%d-%H%M}.{extension}"
        return Archivo(convertir(tabla), nombre, tipo, total, len(filas))

    def exportar(
        self, ctx: Contexto, consulta: ExportarReporte, autor: str | None, usuario_id: uuid.UUID, ip: str | None
    ) -> Archivo:
        archivo = self.generar(ctx, consulta, autor)
        BitacoraService(self.db).registrar(
            modulo="reportes",
            accion="exportar_reporte",
            usuario_id=usuario_id,
            ip=ip,
            detalles=f"fuente={consulta.fuente} formato={consulta.formato} filas={archivo.exportadas}",
        )
        self.db.commit()
        return archivo

    def enviar(
        self, ctx: Contexto, consulta: EnviarReporte, autor: str | None, usuario_id: uuid.UUID, ip: str | None
    ) -> list[str]:
        correo = EmailService()
        correo.exigir_configuracion()
        archivo = self.generar(ctx, consulta, autor)
        titulo = (consulta.titulo or "").strip() or f"Reporte de {FUENTES[consulta.fuente].nombre.lower()}"
        destinatarios = list(dict.fromkeys(str(d).lower() for d in consulta.destinatarios))
        cuerpo = (
            f"{autor or 'Un usuario de EGRESA'} te envió el reporte «{titulo}» "
            f"({archivo.exportadas} registros, formato {_NOMBRE_FORMATO[consulta.formato]}).\n"
        )
        if consulta.mensaje and consulta.mensaje.strip():
            cuerpo += f"\nMensaje:\n{consulta.mensaje.strip()}\n"
        cuerpo += "\nEl archivo va adjunto a este correo.\n\n— EGRESA, bolsa de trabajo universitaria"
        correo.enviar_con_adjuntos(destinatarios, f"EGRESA · {titulo}", cuerpo, [(archivo.nombre, archivo.contenido, archivo.tipo)])
        BitacoraService(self.db).registrar(
            modulo="reportes",
            accion="enviar_reporte",
            usuario_id=usuario_id,
            ip=ip,
            detalles=(
                f"fuente={consulta.fuente} formato={consulta.formato} filas={archivo.exportadas} "
                f"destinatarios={len(destinatarios)}"
            ),
        )
        self.db.commit()
        return destinatarios
