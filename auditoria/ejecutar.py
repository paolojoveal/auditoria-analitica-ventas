"""Ejecuta las pruebas de auditoría sobre el ciclo de ventas y genera el informe.

    1. Carga las tablas (CSV) en una base SQLite en memoria.
    2. Concilia la población: número de facturas e importe facturado, emitido y anulado.
    3. Corre las diez pruebas de `pruebas.sql` sobre el 100% de las transacciones.
    4. Aplica la ley de Benford al primer dígito de los importes.
    5. Busca usuarios que concentren excepciones más de lo que explica el azar.
    6. Compara las excepciones con las irregularidades sembradas en los datos sintéticos.
    7. Escribe el informe, los papeles de trabajo en Excel y las figuras en `resultados/`.

    python -m auditoria.ejecutar                # usa datos/ (los genera si no existen)
    python -m auditoria.ejecutar --semilla 7 --datos otra/datos --salida otra/resultados   # otra empresa sintética
"""
from __future__ import annotations

import argparse
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from . import concentracion, generar_datos

RAIZ = Path(__file__).resolve().parents[1]
RESULTADOS = RAIZ / "resultados"
SQL = Path(__file__).with_name("pruebas.sql")
TABLAS = ["clientes", "productos", "usuarios", "facturas", "factura_detalle", "notas_credito"]
CHI2_CRITICO_5, CHI2_CRITICO_1 = 15.51, 20.09            # chi-cuadrado con 8 grados de libertad


@dataclass
class Prueba:
    codigo: str
    titulo: str
    objetivo: str
    criterio: str
    riesgo: str
    seguimiento: str
    sql: str


def leer_pruebas(ruta: Path = SQL) -> list[Prueba]:
    """Lee `pruebas.sql`: cada bloque empieza con «-- @prueba:» y trae su ficha en comentarios."""
    pruebas = []
    for bloque in re.split(r"(?m)^-- @prueba:\s*", ruta.read_text(encoding="utf-8"))[1:]:
        lineas = bloque.splitlines()
        ficha = dict(m.groups() for m in (re.match(r"-- @(\w+):\s*(.*)", x) for x in lineas[1:]) if m)
        sql = "\n".join(x for x in lineas[1:] if not x.startswith("-- @")).strip().rstrip(";")
        pruebas.append(Prueba(lineas[0].strip(), ficha["titulo"], ficha["objetivo"], ficha["criterio"],
                              ficha["riesgo"], ficha["seguimiento"], sql))
    return pruebas


def cargar(tablas: dict[str, pd.DataFrame]) -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    for nombre in TABLAS:
        tablas[nombre].to_sql(nombre, con, index=False)
    con.executescript("""
        CREATE INDEX ix_detalle_factura ON factura_detalle (factura_id);
        CREATE INDEX ix_facturas_cliente ON facturas (cliente_id, fecha);
        CREATE INDEX ix_facturas_serie ON facturas (serie, numero);
    """)
    return con


def leer_tablas(carpeta: Path) -> dict[str, pd.DataFrame]:
    return {n: pd.read_csv(carpeta / f"{n}.csv") for n in [*TABLAS, "_verdad"] if (carpeta / f"{n}.csv").exists()}


def poblacion(con: sqlite3.Connection) -> dict:
    """Totales de control: lo primero que se concilia con contabilidad antes de probar nada."""
    fila = con.execute("""
        SELECT COUNT(*), MIN(fecha), MAX(fecha),
               SUM(estado = 'EMITIDA'), ROUND(SUM(CASE WHEN estado = 'EMITIDA' THEN total END), 2),
               SUM(estado = 'ANULADA'), ROUND(SUM(CASE WHEN estado = 'ANULADA' THEN total END), 2)
        FROM facturas""").fetchone()
    lineas, notas, importe_notas = con.execute(
        "SELECT (SELECT COUNT(*) FROM factura_detalle), COUNT(*), ROUND(SUM(importe), 2) FROM notas_credito").fetchone()
    return {"facturas": fila[0], "desde": fila[1], "hasta": fila[2], "emitidas": fila[3], "importe_emitido": fila[4],
            "anuladas": fila[5], "importe_anulado": fila[6], "lineas": lineas, "notas_credito": notas,
            "importe_notas": importe_notas}


def ejecutar(con: sqlite3.Connection, pruebas: list[Prueba]) -> dict[str, pd.DataFrame]:
    return {p.codigo: pd.read_sql_query(p.sql, con) for p in pruebas}


def resumir(pruebas: list[Prueba], excepciones: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return pd.DataFrame([{"prueba": p.codigo, "titulo": p.titulo, "excepciones": len(excepciones[p.codigo]),
                          "importe": round(float(excepciones[p.codigo]["importe"].sum()), 2)} for p in pruebas]
                        ).set_index("prueba")


def evaluar(excepciones: dict[str, pd.DataFrame], verdad: pd.DataFrame) -> pd.DataFrame:
    """Contrasta cada prueba con lo sembrado. Solo es posible porque los datos son sintéticos.

    sensibilidad = sembradas detectadas / sembradas
    precisión    = excepciones que eran sembradas / excepciones
    """
    filas = []
    for codigo, df in excepciones.items():
        sembradas, marcadas = set(verdad.loc[verdad["prueba"] == codigo, "clave"]), set(df["clave"])
        aciertos = len(sembradas & marcadas)
        filas.append({"prueba": codigo, "sembradas": len(sembradas), "detectadas": aciertos,
                      "no_sembradas": len(marcadas - sembradas),
                      "sensibilidad": aciertos / len(sembradas) if sembradas else np.nan,
                      "precision": aciertos / len(marcadas) if marcadas else np.nan})
    return pd.DataFrame(filas).set_index("prueba")


def benford(valores: pd.Series) -> tuple[pd.DataFrame, float, float]:
    """Primer dígito significativo frente a la ley de Benford: P(d) = log10(1 + 1/d).

    Devuelve la tabla por dígito, el estadístico chi-cuadrado (8 grados de libertad) y la
    desviación absoluta media (MAD), que no depende del tamaño de la muestra.
    """
    x = valores[valores >= 1].to_numpy(dtype=float)
    primer = np.floor(x / 10 ** np.floor(np.log10(x))).astype(int)
    digitos = np.arange(1, 10)
    observado = np.array([(primer == d).sum() for d in digitos])
    esperado = np.log10(1 + 1 / digitos)
    tabla = pd.DataFrame({"observado": observado, "proporcion": observado / len(x), "benford": esperado},
                         index=pd.Index(digitos, name="digito"))
    chi2 = float(((observado - esperado * len(x)) ** 2 / (esperado * len(x))).sum())
    return tabla, chi2, float(np.abs(tabla["proporcion"] - tabla["benford"]).mean())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--semilla", type=int, default=None, help="genera datos nuevos con esta semilla antes de auditar")
    ap.add_argument("--datos", type=Path, default=generar_datos.DATOS, help="carpeta con los CSV")
    ap.add_argument("--salida", type=Path, default=RESULTADOS, help="carpeta donde se escriben los resultados")
    args = ap.parse_args()
    if args.semilla is not None or not (args.datos / "facturas.csv").exists():
        generar_datos.escribir(generar_datos.generar(args.semilla if args.semilla is not None else 2025), args.datos)
    tablas = leer_tablas(args.datos)
    con = cargar(tablas)
    pruebas = leer_pruebas()
    pob = poblacion(con)
    excepciones = ejecutar(con, pruebas)
    con.close()
    resumen = resumir(pruebas, excepciones)
    emitidas = tablas["facturas"].loc[tablas["facturas"]["estado"] == "EMITIDA", "total"]
    tabla_benford, chi2, mad = benford(emitidas)
    evaluacion = evaluar(excepciones, tablas["_verdad"]) if "_verdad" in tablas else None
    por_usuario = concentracion.analizar(tablas, excepciones)

    pd.set_option("display.width", 200)
    print(f"Población: {pob['facturas']:,} facturas del {pob['desde']} al {pob['hasta']}; "
          f"{pob['emitidas']:,} vigentes por S/ {pob['importe_emitido']:,.0f} y {pob['anuladas']:,} anuladas.")
    print("\nExcepciones por prueba:")
    print(resumen.to_string(formatters={"importe": "{:,.0f}".format}))
    print(f"\nBenford (primer dígito de {len(emitidas):,} facturas): chi-cuadrado = {chi2:.1f} "
          f"(crítico al 5%: {CHI2_CRITICO_5}); MAD = {mad:.4f}")
    senales = concentracion.senales(por_usuario)
    print(f"\nConcentración por usuario: {len(por_usuario)} comparaciones; {int((por_usuario['p'] <= 0.05).sum())} con "
          f"p <= 0.05 sin corregir y {len(senales)} señales tras corregir por comparaciones múltiples.")
    if len(senales):
        print(senales[["prueba", "usuario", "operaciones", "excepciones", "esperadas", "razon", "p", "q"]].to_string(
            index=False, formatters={"esperadas": "{:.1f}".format, "razon": "{:.1f}".format,
                                     "p": concentracion.formato_p, "q": concentracion.formato_p}))
    if evaluacion is not None:
        print("\nContraste con las irregularidades sembradas:")
        print(evaluacion.to_string(formatters={"sensibilidad": "{:.0%}".format, "precision": "{:.0%}".format}))

    from . import informe
    informe.escribir_todo(args.salida, pruebas, pob, excepciones, resumen, evaluacion, tabla_benford, chi2, mad,
                          por_usuario)
    print(f"\nInforme, papeles de trabajo y figuras en {args.salida}/")


if __name__ == "__main__":
    main()
