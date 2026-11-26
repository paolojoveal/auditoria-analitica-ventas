"""¿Las excepciones se reparten como el trabajo, o algunos usuarios concentran un patrón?

    Para cada prueba y cada usuario se compara el número de excepciones con el que le tocaría
    si las excepciones cayeran al azar entre las operaciones de todos (prueba hipergeométrica
    de una cola). Como se hacen decenas de comparaciones a la vez, los valores p se corrigen con
    el procedimiento de Benjamini-Hochberg: sin esa corrección, varias celdas saldrían
    «significativas» por puro azar y el auditor perseguiría patrones que no existen.

    Quedan fuera tres pruebas: P02 (un correlativo faltante no tiene usuario), P06 (por
    definición señala a un mismo usuario en dos funciones) y P10 (cada caso reúne facturas de
    varios usuarios).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

NIVEL = 0.05          # proporción de falsos descubrimientos que se tolera entre las señales

# prueba -> (operación que se cuenta, columna de la excepción con el usuario responsable)
RESPONSABLE = {
    "P01": ("facturas", "usuario_registro"),
    "P03": ("facturas", "usuario_registro"),
    "P04": ("líneas", "usuario_registro"),
    "P05": ("líneas", "usuario_registro"),
    "P07": ("anulaciones", "usuario_anulacion"),
    "P08": ("notas de crédito", "usuario_registro"),
    "P09": ("facturas", "usuario_registro"),
}


def actividad(tablas: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
    """Operaciones de cada usuario: el denominador contra el que se comparan sus excepciones."""
    facturas, detalle = tablas["facturas"], tablas["factura_detalle"]
    registrador = detalle["factura_id"].map(facturas.set_index("factura_id")["usuario_registro"])
    return {
        "facturas": facturas["usuario_registro"].value_counts(),
        "líneas": registrador.value_counts(),
        "anulaciones": facturas.loc[facturas["estado"] == "ANULADA", "usuario_anulacion"].value_counts(),
        "notas de crédito": tablas["notas_credito"]["usuario_registro"].value_counts(),
    }


def benjamini_hochberg(p) -> np.ndarray:
    """Valores q: el menor nivel de falsos descubrimientos con el que cada comparación es una señal."""
    p = np.asarray(p, dtype=float)
    orden = np.argsort(p)
    q = p[orden] * p.size / np.arange(1, p.size + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    salida = np.empty(p.size)
    salida[orden] = np.minimum(q, 1.0)
    return salida


def analizar(tablas: dict[str, pd.DataFrame], excepciones: dict[str, pd.DataFrame], nivel: float = NIVEL) -> pd.DataFrame:
    """Una fila por prueba y usuario: excepciones observadas, esperadas, valor p y valor q."""
    operaciones = actividad(tablas)
    filas = []
    for prueba, (unidad, columna) in RESPONSABLE.items():
        if prueba not in excepciones:
            continue
        por_usuario = operaciones[unidad]
        observadas = excepciones[prueba][columna].value_counts()
        total, con_excepcion = int(por_usuario.sum()), int(observadas.reindex(por_usuario.index).fillna(0).sum())
        for usuario, n in por_usuario.sort_index().items():
            x = int(observadas.get(usuario, 0))
            esperadas = con_excepcion * n / total
            filas.append({"prueba": prueba, "usuario": usuario, "unidad": unidad, "operaciones": int(n),
                          "excepciones": x, "esperadas": esperadas,
                          "razon": x / esperadas if esperadas > 0 else np.nan,
                          # P(X >= x) si las excepciones se repartieran al azar entre las operaciones
                          "p": float(stats.hypergeom.sf(x - 1, total, con_excepcion, int(n)))})
    tabla = pd.DataFrame(filas)
    tabla["q"] = benjamini_hochberg(tabla["p"])
    tabla["senal"] = tabla["q"] <= nivel
    return tabla


def senales(tabla: pd.DataFrame) -> pd.DataFrame:
    return tabla[tabla["senal"]].sort_values("q")


def formato_p(valor: float) -> str:
    """Un valor p o q legible: nunca «0.0000»."""
    return "< 0.0001" if valor < 0.0001 else f"{valor:.4f}"
