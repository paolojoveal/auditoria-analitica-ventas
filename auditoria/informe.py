"""Salidas de la auditoría: figuras, papeles de trabajo en Excel e informe en Markdown."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from . import concentracion, estilo

EMPRESA = "Distribuidora Altiplano S.A.C. (empresa ficticia)"
PIE = "Datos sintéticos generados por auditoria/generar_datos.py. Elaboración propia."
NOMBRE_CORTO = {"P01": "Totales", "P03": "Duplicados", "P04": "Bajo el costo", "P05": "Descuentos",
                "P07": "Anulación tardía", "P08": "Notas de crédito", "P09": "Fuera de horario"}
MAD_BENFORD = [(0.006, "conformidad cercana"), (0.012, "conformidad aceptable"),
               (0.015, "conformidad marginal"), (np.inf, "no conforme")]      # umbrales de Nigrini (2012), primer dígito


def soles(x: float) -> str:
    return f"S/ {x:,.0f}"


def lectura_benford(mad: float) -> str:
    return next(texto for limite, texto in MAD_BENFORD if mad <= limite)


# ---------- figuras ----------
def figura_excepciones(resumen: pd.DataFrame, ruta: Path) -> None:
    fig, (a, b) = plt.subplots(1, 2, figsize=(11.5, 4.8), sharey=True)
    y = np.arange(len(resumen))
    etiquetas = [f"{c} · {t}" for c, t in zip(resumen.index, resumen["titulo"])]
    for ax, columna, formato, titulo, sub in [
            (a, "excepciones", "{:,.0f}", "Excepciones por prueba", "Registros que no cumplen el criterio"),
            (b, "importe", "S/ {:,.0f}", "Importe expuesto", "Soles; la medida depende de la prueba")]:
        ax.barh(y, resumen[columna], height=0.46, color=estilo.AZUL)
        for i, v in enumerate(resumen[columna]):
            estilo.etiqueta(ax, v, i, formato.format(v))
        ax.set_xlim(0, resumen[columna].max() * 1.32)
        ax.grid(axis="y", visible=False)
        ax.grid(axis="x", visible=True)
        ax.xaxis.set_major_locator(plt.MaxNLocator(5))
        ax.xaxis.set_major_formatter(plt.FuncFormatter(
            (lambda v, _: f"{v / 1000:,.0f} mil" if v else "0") if columna == "importe" else (lambda v, _: f"{v:,.0f}")))
        estilo.titulo(ax, titulo, sub)
    a.set_yticks(y, etiquetas)
    a.set_ylim(len(resumen) - 0.5, -0.6)
    estilo.guardar(fig, ruta, PIE)


def figura_benford(tabla: pd.DataFrame, mad: float, ruta: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    ax.bar(tabla.index, tabla["proporcion"] * 100, width=0.46, color=estilo.AZUL, label="Facturas de la empresa")
    ax.plot(tabla.index, tabla["benford"] * 100, "o", ms=9, color=estilo.SUPERFICIE, mec=estilo.TINTA, mew=1.6,
            label="Ley de Benford", zorder=4)
    ax.set_xticks(tabla.index)
    ax.set_xlabel("Primer dígito del importe de la factura")
    estilo.formato_pct(ax)
    estilo.titulo(ax, "Primer dígito de los importes frente a la ley de Benford",
                  f"Desviación absoluta media = {mad:.4f}: {lectura_benford(mad)}")
    ax.legend(loc="upper right")
    estilo.guardar(fig, ruta, PIE)


def titulo_concentracion(tabla: pd.DataFrame) -> str:
    """Una frase con el resultado: quién concentra qué, o que nadie lo hace."""
    senales = concentracion.senales(tabla)
    if senales.empty:
        return "Ningún usuario concentra más excepciones de las que explica el azar"
    if senales["prueba"].nunique() == 1:
        usuarios = list(senales["usuario"])
        quienes = usuarios[0] if len(usuarios) == 1 else ", ".join(usuarios[:-1]) + " y " + usuarios[-1]
        verbo = "concentra" if len(usuarios) == 1 else "concentran"
        return f"{quienes} {verbo} las excepciones de {senales['prueba'].iloc[0]}"
    return f"{len(senales)} combinaciones de usuario y prueba superan lo que explica el azar"


def figura_concentracion(tabla: pd.DataFrame, ruta: Path) -> None:
    """Mapa de usuarios por pruebas.

    El color es el residuo estandarizado, (observadas - esperadas) / raíz(esperadas): mide cuánta
    evidencia hay, no solo cuánto se aleja la razón. Con pocas excepciones esperadas, una razón
    de cero o de tres no significa nada, y el color queda neutro.
    """
    usuarios = sorted(tabla["usuario"].unique())
    pruebas = [p for p in concentracion.RESPONSABLE if p in set(tabla["prueba"])]
    fig, ax = plt.subplots(figsize=(10.0, 5.4))
    escala = plt.Normalize(-4, 4)
    for fila in tabla.itertuples():
        x, y = pruebas.index(fila.prueba), usuarios.index(fila.usuario)
        nivel = float(np.clip((fila.excepciones - fila.esperadas) / np.sqrt(fila.esperadas), -4, 4)) if fila.esperadas > 0 else 0.0
        ax.add_patch(plt.Rectangle((x - 0.5, y - 0.5), 1, 1, facecolor=estilo.MAPA_DIVERGENTE(escala(nivel)),
                                   edgecolor=estilo.SUPERFICIE, linewidth=2.5, zorder=2))
        ax.text(x, y, f"{fila.excepciones} / {fila.esperadas:.1f}", ha="center", va="center", fontsize=9, zorder=4,
                color="#ffffff" if abs(nivel) > 2.7 else estilo.TINTA, fontweight="bold" if fila.senal else "normal")
        if fila.senal:
            ax.add_patch(plt.Rectangle((x - 0.46, y - 0.46), 0.92, 0.92, fill=False, edgecolor=estilo.TINTA,
                                       linewidth=2.2, zorder=5))
    ax.set_xlim(-0.5, len(pruebas) - 0.5)
    ax.set_ylim(len(usuarios) - 0.5, -0.5)
    ax.set_xticks(range(len(pruebas)), [f"{p}\n{NOMBRE_CORTO.get(p, '')}" for p in pruebas])
    ax.set_yticks(range(len(usuarios)), usuarios)
    ax.tick_params(length=0)
    ax.grid(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_visible(False)
    barra = fig.colorbar(plt.cm.ScalarMappable(norm=escala, cmap=estilo.MAPA_DIVERGENTE), ax=ax, fraction=0.035, pad=0.03,
                         ticks=[-4, -2, 0, 2, 4])
    barra.ax.set_yticklabels(["\u22124", "\u22122", "0", "+2", "+4"])
    barra.set_label("Desviación frente a lo esperado, en desviaciones estándar", fontsize=8.5, color=estilo.TINTA_2)
    barra.outline.set_visible(False)
    barra.ax.tick_params(length=0, labelsize=8.5)
    estilo.titulo(ax, titulo_concentracion(tabla),
                  "En cada celda: excepciones observadas / esperadas si se repartieran como el trabajo. "
                  "Con borde: señales tras la corrección")
    estilo.guardar(fig, ruta, PIE)


# ---------- papeles de trabajo ----------
def _encabezar(hoja, fila: int, columnas: list[str]) -> None:
    for j, nombre in enumerate(columnas, start=1):
        c = hoja.cell(fila, j, nombre)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="184F95")
        c.alignment = Alignment(vertical="center", wrap_text=True)


def _anchos(hoja, minimo: int = 10, maximo: int = 46) -> None:
    for j, columna in enumerate(hoja.iter_cols(min_row=1, max_row=min(hoja.max_row, 200)), start=1):
        largo = max((len(str(c.value)) for c in columna if c.value is not None and c.row > 8), default=minimo)
        hoja.column_dimensions[get_column_letter(j)].width = max(minimo, min(maximo, largo + 2))


def papeles_de_trabajo(ruta: Path, pruebas, pob: dict, excepciones: dict[str, pd.DataFrame], resumen: pd.DataFrame) -> None:
    libro = Workbook()
    indice = libro.active
    indice.title = "Índice"
    indice["A1"], indice["A2"] = "Auditoría del ciclo de ventas", EMPRESA
    indice["A1"].font = Font(bold=True, size=14)
    indice["A3"] = f"Periodo: {pob['desde']} a {pob['hasta']}. Procedimientos sobre el 100% de la población. Datos sintéticos."
    datos_poblacion = [("Facturas en la población", pob["facturas"]), ("Facturas vigentes", pob["emitidas"]),
                       ("Importe vigente (S/)", pob["importe_emitido"]), ("Facturas anuladas", pob["anuladas"]),
                       ("Importe anulado (S/)", pob["importe_anulado"]), ("Líneas de detalle", pob["lineas"]),
                       ("Notas de crédito", pob["notas_credito"]), ("Importe de notas de crédito (S/)", pob["importe_notas"])]
    indice["A5"] = "Población"
    indice["A5"].font = Font(bold=True)
    for i, (nombre, valor) in enumerate(datos_poblacion, start=6):
        indice.cell(i, 1, nombre)
        indice.cell(i, 2, valor).number_format = "#,##0.00" if isinstance(valor, float) else "#,##0"
    inicio = 6 + len(datos_poblacion) + 1
    _encabezar(indice, inicio, ["Ref.", "Prueba", "Objetivo", "Criterio", "Excepciones", "Importe (S/)"])
    for i, p in enumerate(pruebas, start=inicio + 1):
        ref = indice.cell(i, 1, p.codigo)
        ref.hyperlink, ref.font = f"#'{p.codigo}'!A1", Font(color="1C5CAB", underline="single")
        for j, valor in enumerate([p.titulo, p.objetivo, p.criterio, int(resumen.at[p.codigo, "excepciones"]),
                                   float(resumen.at[p.codigo, "importe"])], start=2):
            c = indice.cell(i, j, valor)
            c.alignment = Alignment(vertical="top", wrap_text=True)
            if j == 6:
                c.number_format = "#,##0.00"
    for letra, ancho in zip("ABCDEF", [32, 30, 58, 62, 13, 16]):
        indice.column_dimensions[letra].width = ancho

    for p in pruebas:
        df = excepciones[p.codigo]
        hoja = libro.create_sheet(p.codigo)
        ficha = [("Prueba", f"{p.codigo} · {p.titulo}"), ("Objetivo", p.objetivo), ("Criterio", p.criterio),
                 ("Riesgo", p.riesgo),
                 ("Procedimiento", f"Consulta {p.codigo} de auditoria/pruebas.sql sobre el 100% de la población."),
                 ("Resultado", f"{len(df):,} excepciones por {soles(df['importe'].sum())}."),
                 ("Seguimiento", p.seguimiento)]
        for i, (nombre, valor) in enumerate(ficha, start=1):
            hoja.cell(i, 1, nombre).font = Font(bold=True)
            hoja.cell(i, 2, valor)
        _encabezar(hoja, 9, list(df.columns))
        for i, fila in enumerate(df.itertuples(index=False), start=10):
            for j, valor in enumerate(fila, start=1):
                hoja.cell(i, j, None if pd.isna(valor) else (valor.item() if isinstance(valor, np.generic) else valor))
        hoja.freeze_panes = "A10"
        if len(df):
            hoja.auto_filter.ref = f"A9:{get_column_letter(len(df.columns))}{9 + len(df)}"
        _anchos(hoja)
        hoja.column_dimensions["A"].width = 24
    libro.save(ruta)


# ---------- informe ----------
def _tabla_md(df: pd.DataFrame, formatos: dict | None = None) -> str:
    formatos = formatos or {}
    celda = lambda col, v: "" if pd.isna(v) else (formatos[col].format(v) if col in formatos else str(v))
    lineas = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    lineas += ["| " + " | ".join(celda(c, v) for c, v in zip(df.columns, fila)) + " |" for fila in df.itertuples(index=False)]
    return "\n".join(lineas)


def _concentracion(codigo: str, por_usuario: pd.DataFrame | None) -> str:
    """Usuarios de esta prueba cuyas excepciones superan lo que explica el azar."""
    if por_usuario is None:
        return ""
    senales = concentracion.senales(por_usuario)
    senales = senales[senales["prueba"] == codigo]
    if senales.empty:
        return ""
    detalle = "; ".join(f"{f.usuario}, {f.excepciones} excepciones cuando se esperaban {f.esperadas:.1f}"
                        for f in senales.itertuples())
    return f"\n**Concentración.** {detalle}. La diferencia supera lo que explica el azar.\n"


def informe_md(ruta: Path, pruebas, pob: dict, excepciones, resumen: pd.DataFrame, evaluacion, tabla_benford,
               chi2: float, mad: float, por_usuario: pd.DataFrame | None = None) -> None:
    orden = resumen.sort_values("importe", ascending=False)
    mayores = ", ".join(f"{f.titulo.lower()} ({soles(f.importe)})" for f in orden.head(3).itertuples())
    t = [f"# Informe de auditoría: ciclo de ventas\n\n**{EMPRESA}** · Periodo {pob['desde']} a {pob['hasta']}\n",
         "> Informe generado por `python -m auditoria.ejecutar` a partir de datos sintéticos. Las causas y "
         "recomendaciones de una auditoría real salen del seguimiento de cada excepción, no de la consulta.\n",
         "## Resumen\n",
         f"- **Población:** {pob['facturas']:,} facturas ({pob['lineas']:,} líneas) y {pob['notas_credito']:,} notas de crédito. "
         f"Facturación vigente de {soles(pob['importe_emitido'])}; {pob['anuladas']:,} facturas anuladas por {soles(pob['importe_anulado'])}.",
         "- **Alcance:** diez pruebas sobre el 100% de las transacciones, sin muestreo, más un análisis de Benford.",
         f"- **Resultado:** {int(resumen['excepciones'].sum()):,} excepciones en total. Los mayores importes expuestos son: {mayores}.",
         "- **Una excepción no es un hallazgo.** Es un registro que no cumple el criterio y que hay que explicar. "
         "Parte de ellas tendrá sustento válido.\n",
         "| Prueba | Título | Excepciones | Importe expuesto |", "|---|---|---|---|"]
    t += [f"| {c} | {f.titulo} | {f.excepciones:,} | {soles(f.importe)} |" for c, f in zip(resumen.index, resumen.itertuples())]
    t.append("\n## Detalle por prueba\n")
    for p in pruebas:
        df = excepciones[p.codigo]
        t += [f"### {p.codigo} · {p.titulo}\n",
              f"- **Objetivo:** {p.objetivo}", f"- **Criterio:** {p.criterio}", f"- **Riesgo:** {p.riesgo}",
              f"- **Resultado:** {len(df):,} excepciones por {soles(df['importe'].sum())}.",
              f"- **Seguimiento:** {p.seguimiento}"]
        if "motivo" in df.columns or "conflicto" in df.columns:
            col = "motivo" if "motivo" in df.columns else "conflicto"
            t.append("- **Por tipo:** " + "; ".join(f"{k}: {v}" for k, v in df[col].value_counts().items()) + ".")
        t.append(_concentracion(p.codigo, por_usuario))
        if len(df):
            t += ["Las cinco primeras excepciones:\n", _tabla_md(df.head(5), {"importe": "{:,.2f}"}), ""]
    if por_usuario is not None:
        senales = concentracion.senales(por_usuario)
        t += ["## Concentración por usuario\n",
              "Para cada prueba y cada usuario se compara el número de excepciones con el que le tocaría si las "
              "excepciones se repartieran como el trabajo (prueba hipergeométrica de una cola). Los valores p se "
              "corrigen con el procedimiento de Benjamini-Hochberg, porque se hacen muchas comparaciones a la vez.\n",
              f"- **Comparaciones:** {len(por_usuario)}.",
              f"- **Con p ≤ 0.05 sin corregir:** {int((por_usuario['p'] <= 0.05).sum())}.",
              f"- **Señales tras la corrección:** {len(senales)}.\n"]
        if len(senales):
            cuadro = senales[["prueba", "usuario", "unidad", "operaciones", "excepciones", "esperadas", "razon", "p", "q"]]
            t += [_tabla_md(cuadro.rename(columns={
                "prueba": "Prueba", "usuario": "Usuario", "unidad": "Operación", "operaciones": "Operaciones",
                "excepciones": "Excepciones", "esperadas": "Esperadas", "razon": "Observadas / esperadas",
                "p": "Valor p", "q": "Valor q"}).assign(**{"Valor p": cuadro["p"].map(concentracion.formato_p),
                                                         "Valor q": cuadro["q"].map(concentracion.formato_p)}),
                {"Operaciones": "{:,}", "Esperadas": "{:.1f}", "Observadas / esperadas": "{:.1f}"}), ""]
        t.append("Una señal indica a quién preguntar primero. No prueba una irregularidad: puede haber una razón "
                 "operativa, como un turno o una zona asignada.\n")
    t += ["## Análisis de Benford\n",
          "En importes que abarcan varios órdenes de magnitud, el primer dígito sigue la ley de Benford. Una desviación "
          "marcada puede indicar importes fabricados o fraccionados cerca de un umbral.\n",
          _tabla_md(tabla_benford.reset_index().rename(columns={"digito": "Dígito", "observado": "Facturas",
                                                                 "proporcion": "Proporción", "benford": "Benford"}),
                    {"Facturas": "{:,}", "Proporción": "{:.1%}", "Benford": "{:.1%}"}),
          f"\nChi-cuadrado = {chi2:.1f} (valor crítico al 5% con 8 grados de libertad: 15.5). Desviación absoluta media = "
          f"{mad:.4f}: **{lectura_benford(mad)}** según los umbrales de Nigrini (2012). El chi-cuadrado rechaza con "
          "facilidad en muestras grandes; por eso se lee junto con la desviación absoluta media.\n"]
    if evaluacion is not None:
        ev = evaluacion.reset_index().rename(columns={"prueba": "Prueba", "sembradas": "Sembradas", "detectadas": "Detectadas",
                                                      "no_sembradas": "Excepciones no sembradas",
                                                      "sensibilidad": "Sensibilidad", "precision": "Precisión"})
        t += ["## Contraste con las irregularidades sembradas\n",
              "Los datos son sintéticos y el generador anota qué irregularidades sembró. Eso permite medir algo que en "
              "una auditoría real no se observa: cuánto detecta cada prueba y cuántas excepciones son falsas alarmas.\n",
              _tabla_md(ev, {"Sensibilidad": "{:.0%}", "Precisión": "{:.0%}"}), ""]
    t += ["## Alcance y limitaciones\n",
          "- Las pruebas verifican atributos de los registros; no reemplazan la confirmación con clientes, la revisión "
          "documentaria ni el recorrido del proceso.",
          "- Un correlativo faltante al final de una serie no es detectable: no hay un número posterior que lo delate.",
          "- Los umbrales (tres días para duplicados, S/ 10 000 para fraccionamiento) son parámetros de la prueba. "
          "Cambiarlos mueve el balance entre excepciones omitidas y falsas alarmas."]
    ruta.write_text("\n".join(x for x in t if x is not None), encoding="utf-8")


def escribir_todo(carpeta: Path, pruebas, pob, excepciones, resumen, evaluacion, tabla_benford, chi2, mad,
                  por_usuario: pd.DataFrame | None = None) -> None:
    carpeta.mkdir(exist_ok=True)
    (carpeta / "excepciones").mkdir(exist_ok=True)
    estilo.aplicar()
    figura_excepciones(resumen, carpeta / "excepciones.png")
    figura_benford(tabla_benford, mad, carpeta / "benford.png")
    resumen.to_csv(carpeta / "resumen.csv")
    tabla_benford.round(4).to_csv(carpeta / "benford.csv")
    if evaluacion is not None:
        evaluacion.round(3).to_csv(carpeta / "contraste_con_lo_sembrado.csv")
    for codigo, df in excepciones.items():
        df.to_csv(carpeta / "excepciones" / f"{codigo}.csv", index=False)
    papeles_de_trabajo(carpeta / "papeles_de_trabajo.xlsx", pruebas, pob, excepciones, resumen)
    if por_usuario is not None:
        figura_concentracion(por_usuario, carpeta / "concentracion.png")
        por_usuario.round({"esperadas": 2, "razon": 3, "p": 6, "q": 6}).to_csv(carpeta / "concentracion.csv", index=False)
    informe_md(carpeta / "informe.md", pruebas, pob, excepciones, resumen, evaluacion, tabla_benford, chi2, mad,
               por_usuario)
