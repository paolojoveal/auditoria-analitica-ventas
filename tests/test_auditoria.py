"""Las pruebas de auditoría, puestas a prueba: detectan lo sembrado y no marcan lo que está bien."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auditoria import concentracion, ejecutar, generar_datos  # noqa: E402

SIN_FALSAS_ALARMAS = ["P01", "P02", "P05", "P06", "P07", "P09"]      # pruebas que no admiten una explicación legítima


def auditar(tablas):
    con = ejecutar.cargar(tablas)
    try:
        return ejecutar.ejecutar(con, ejecutar.leer_pruebas())
    finally:
        con.close()


@pytest.fixture(scope="module")
def empresa():
    tablas = generar_datos.generar()
    return tablas, auditar(tablas)


def test_las_fichas_de_las_pruebas_estan_completas():
    pruebas = ejecutar.leer_pruebas()
    assert [p.codigo for p in pruebas] == [f"P{i:02d}" for i in range(1, 11)]
    for p in pruebas:
        assert all([p.titulo, p.objetivo, p.criterio, p.riesgo, p.seguimiento]), p.codigo
        assert p.sql.lstrip().upper().startswith(("SELECT", "WITH")), p.codigo


def test_el_generador_es_reproducible():
    a, b = generar_datos.generar(seed=3, n_facturas=1500), generar_datos.generar(seed=3, n_facturas=1500)
    for nombre in a:
        pd.testing.assert_frame_equal(a[nombre], b[nombre])
    otra = generar_datos.generar(seed=4, n_facturas=1500)
    assert not a["facturas"]["total"].equals(otra["facturas"]["total"])


def test_todas_las_pruebas_devuelven_clave_e_importe(empresa):
    _, excepciones = empresa
    for codigo, df in excepciones.items():
        assert {"clave", "importe"} <= set(df.columns), codigo
        assert df["clave"].is_unique, codigo
        assert (df["importe"] >= 0).all(), codigo


def test_detectan_todo_lo_sembrado(empresa):
    tablas, excepciones = empresa
    evaluacion = ejecutar.evaluar(excepciones, tablas["_verdad"])
    assert (evaluacion["sembradas"] > 0).all()
    assert (evaluacion["sensibilidad"] == 1.0).all(), evaluacion["sensibilidad"].to_dict()
    assert (evaluacion.loc[SIN_FALSAS_ALARMAS, "precision"] == 1.0).all()


@pytest.mark.parametrize("semilla", [7, 11])
def test_tambien_con_otras_empresas(semilla):
    tablas = generar_datos.generar(seed=semilla)
    evaluacion = ejecutar.evaluar(auditar(tablas), tablas["_verdad"])
    assert (evaluacion["sensibilidad"] >= 0.9).all(), evaluacion["sensibilidad"].to_dict()


def test_una_empresa_limpia_no_genera_excepciones():
    tablas = generar_datos.generar(sembrar=False)
    excepciones = auditar(tablas)
    assert tablas["_verdad"].empty
    for codigo in ["P01", "P02", "P04", "P05", "P06", "P07", "P08", "P09"]:
        assert excepciones[codigo].empty, codigo
    assert len(excepciones["P03"]) == 8        # los ocho pedidos repetidos legítimos a pocos días


def test_el_detalle_concilia_con_la_cabecera(empresa):
    tablas, excepciones = empresa
    detalle = tablas["factura_detalle"].groupby("factura_id")["importe"].sum()
    cabecera = tablas["facturas"].set_index("factura_id")["total"]
    diferencias = (cabecera - detalle).abs()
    assert set(diferencias[diferencias > 0.01].index) == set(excepciones["P01"]["clave"])
    assert set(tablas["factura_detalle"]["factura_id"]) == set(cabecera.index)     # no hay líneas huérfanas


def test_un_correlativo_eliminado_se_detecta():
    tablas = generar_datos.generar(seed=5, n_facturas=800, sembrar=False)
    f = tablas["facturas"]
    victima = f[(f["serie"] == "F001") & (f["numero"] == 100)]["factura_id"].iloc[0]
    tablas["facturas"] = f[f["factura_id"] != victima]
    tablas["factura_detalle"] = tablas["factura_detalle"][tablas["factura_detalle"]["factura_id"] != victima]
    assert auditar(tablas)["P02"]["clave"].tolist() == ["F001-000100"]


def test_poblacion():
    tablas = generar_datos.generar()
    con = ejecutar.cargar(tablas)
    pob = ejecutar.poblacion(con)
    con.close()
    f = tablas["facturas"]
    assert pob["facturas"] == len(f) and pob["emitidas"] + pob["anuladas"] == len(f)
    assert pob["importe_emitido"] == pytest.approx(f.loc[f["estado"] == "EMITIDA", "total"].sum(), abs=0.01)


def test_benford():
    rng = np.random.default_rng(0)
    conforme = pd.Series(10 ** rng.uniform(0, 5, 20_000))             # log-uniforme: cumple Benford
    tabla, chi2, mad = ejecutar.benford(conforme)
    assert tabla["benford"].sum() == pytest.approx(1) and tabla["observado"].sum() == 20_000
    assert mad < 0.006 and chi2 < ejecutar.CHI2_CRITICO_1
    uniforme = pd.Series(rng.uniform(100, 999, 20_000))               # primer dígito uniforme: no cumple
    assert ejecutar.benford(uniforme)[2] > 0.015


# ---------- concentración por usuario ----------
def test_benjamini_hochberg_con_respuesta_conocida():
    assert concentracion.benjamini_hochberg([0.01, 0.04, 0.03, 0.005]) == pytest.approx([0.02, 0.04, 0.04, 0.02])
    p = np.random.default_rng(1).uniform(size=50)
    q = concentracion.benjamini_hochberg(p)
    assert (q >= p).all() and (q <= 1).all()
    assert (np.diff(q[np.argsort(p)]) >= 0).all()                     # a menor p, menor q


def test_el_valor_p_es_la_cola_hipergeometrica():
    """Diez facturas, cuatro con excepción, las cuatro del mismo usuario: P(X >= 4) = 5/210."""
    facturas = pd.DataFrame({"factura_id": [f"F{i}" for i in range(10)], "usuario_registro": ["A"] * 5 + ["B"] * 5,
                             "estado": "EMITIDA", "usuario_anulacion": None})
    tablas = {"facturas": facturas, "factura_detalle": pd.DataFrame({"factura_id": facturas["factura_id"]}),
              "notas_credito": pd.DataFrame({"usuario_registro": []})}
    tabla = concentracion.analizar(tablas, {"P01": facturas.head(4)}).set_index("usuario")
    assert tabla.at["A", "p"] == pytest.approx(5 / 210)
    assert tabla.at["B", "p"] == pytest.approx(1.0)
    assert tabla["esperadas"].tolist() == [2.0, 2.0]


def test_la_concentracion_encuentra_lo_sembrado_y_nada_mas(empresa):
    """El generador concentra la facturación nocturna en FACT03 y FACT07 y reparte lo demás al azar."""
    tablas, excepciones = empresa
    tabla = concentracion.analizar(tablas, excepciones)
    senales = concentracion.senales(tabla)
    assert set(zip(senales["prueba"], senales["usuario"])) == {("P09", "FACT03"), ("P09", "FACT07")}
    assert (tabla["p"] <= 0.05).sum() > len(senales)                  # sin corregir habría señales falsas
    for _, grupo in tabla.groupby("prueba"):                          # las esperadas reparten todas las excepciones
        assert grupo["esperadas"].sum() == pytest.approx(grupo["excepciones"].sum())


def test_una_empresa_limpia_no_da_senales_de_concentracion():
    tablas = generar_datos.generar(sembrar=False)
    assert concentracion.senales(concentracion.analizar(tablas, auditar(tablas))).empty
