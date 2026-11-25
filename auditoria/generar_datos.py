"""Genera los datos sintéticos del ciclo de ventas de una distribuidora ficticia.

Produce las tablas que un auditor pediría al área de sistemas (clientes, productos, usuarios,
facturas, detalle y notas de crédito) y siembra en ellas irregularidades de diez tipos. Lo que
se sembró queda anotado en `_verdad.csv`, un archivo que en una auditoría real no existe y que
aquí sirve para medir cuánto detecta cada prueba y cuántas de sus excepciones son falsas alarmas.

    python -m auditoria.generar_datos            # escribe los CSV en datos/
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "datos"
ANIO = 2025

# Políticas de la empresa (los criterios contra los que se audita)
DESCUENTO_LIBRE = 10.0          # % máximo sin aprobación
DESCUENTO_MAXIMO = 20.0         # % máximo con aprobación de un supervisor
UMBRAL_GERENCIA = 10_000.0      # facturas desde este importe requieren aprobación de gerencia
HORA_INICIO, HORA_FIN = "08:00", "20:00"   # facturación de lunes a sábado

SEMBRADAS = {"P01": 10, "P02": 18, "P03": 25, "P04": 40, "P05": 60, "P06": 35, "P07": 20, "P08": 15,
             "P09": 45, "P10": 30}


def _maestros(rng: np.random.Generator):
    n_prod, n_cli = 120, 400
    categorias = ["Abarrotes", "Bebidas", "Limpieza", "Cuidado personal", "Snacks", "Lácteos"]
    costo = np.round(rng.lognormal(np.log(18), 0.6, n_prod), 2)
    productos = pd.DataFrame({
        "sku": [f"P{i:03d}" for i in range(1, n_prod + 1)],
        "categoria": rng.choice(categorias, n_prod),
        "costo_unitario": costo,
        "precio_lista": np.round(costo * (1 + rng.uniform(0.30, 0.60, n_prod)), 2),
    })
    segmento = rng.choice(["Bodega", "Minimarket", "Mayorista"], n_cli, p=[0.55, 0.30, 0.15])
    clientes = pd.DataFrame({
        "cliente_id": [f"C{i:04d}" for i in range(1, n_cli + 1)],
        "segmento": segmento,
        "zona": rng.choice(["Lima", "Provincias"], n_cli, p=[0.65, 0.35]),
        "vendedor_id": rng.choice([f"V{i:02d}" for i in range(1, 13)], n_cli),
    })
    usuarios = pd.DataFrame({
        "usuario_id": [f"FACT{i:02d}" for i in range(1, 9)] + [f"SUP{i:02d}" for i in range(1, 4)] + ["GER01"],
        "rol": ["FACTURADOR"] * 8 + ["SUPERVISOR"] * 3 + ["GERENCIA"],
    })
    return productos, clientes, usuarios


def _dias_habiles() -> pd.DatetimeIndex:
    dias = pd.date_range(f"{ANIO}-01-02", f"{ANIO}-12-30", freq="D")
    return dias[dias.day_of_week < 6]                    # lunes a sábado


def _hora(rng: np.random.Generator, n: int, fuera: bool = False) -> list[str]:
    horas = rng.choice([21, 22, 23, 0, 1, 2, 3, 4, 5], n) if fuera else rng.integers(8, 20, n)
    return [f"{h:02d}:{m:02d}" for h, m in zip(horas, rng.integers(0, 60, n))]


def generar(seed: int = 2025, n_facturas: int = 9000, sembrar: bool = True) -> dict[str, pd.DataFrame]:
    """Devuelve las tablas y la tabla `_verdad` con las irregularidades sembradas.

    Con `sembrar=False` la empresa sale limpia: sirve para comprobar que las pruebas no marcan
    excepciones donde no las hay.
    """
    rng = np.random.default_rng(seed)
    n = SEMBRADAS if sembrar else dict.fromkeys(SEMBRADAS, 0)
    parte = lambda k: k if sembrar else 0             # para las pruebas que se siembran en dos tandas
    productos, clientes, usuarios = _maestros(rng)
    dias = _dias_habiles()
    facturadores = usuarios.loc[usuarios["rol"] == "FACTURADOR", "usuario_id"].to_numpy()
    supervisores = usuarios.loc[usuarios["rol"] == "SUPERVISOR", "usuario_id"].to_numpy()
    precio = productos.set_index("sku")["precio_lista"]
    costo = productos.set_index("sku")["costo_unitario"]
    tamano = {"Bodega": 8, "Minimarket": 25, "Mayorista": 60}         # unidades típicas por línea

    # ---------- facturas limpias ----------
    peso_dia = 1 + 0.35 * (dias.month == 12) + 0.15 * (dias.month == 7)
    peso_cli = clientes["segmento"].map({"Bodega": 1.0, "Minimarket": 1.6, "Mayorista": 2.4}).to_numpy()
    cab = pd.DataFrame({
        "tmp": np.arange(n_facturas),
        "fecha": rng.choice(dias, n_facturas, p=peso_dia / peso_dia.sum()),
        "cliente_id": rng.choice(clientes["cliente_id"], n_facturas, p=peso_cli / peso_cli.sum()),
        "usuario_registro": rng.choice(facturadores, n_facturas),
    })
    cab["hora_registro"] = _hora(rng, n_facturas)
    cab = cab.merge(clientes[["cliente_id", "segmento", "zona", "vendedor_id"]], on="cliente_id")
    cab["serie"] = cab["zona"].map({"Lima": "F001", "Provincias": "F002"})
    cab["estado"], cab["fecha_anulacion"], cab["usuario_anulacion"] = "EMITIDA", pd.NaT, None

    n_lineas = rng.choice([1, 2, 3, 4], n_facturas, p=[0.35, 0.35, 0.20, 0.10])
    det = pd.DataFrame({"tmp": np.repeat(cab["tmp"].to_numpy(), n_lineas)})
    det["linea"] = det.groupby("tmp").cumcount() + 1
    det["sku"] = rng.choice(productos["sku"], len(det))
    seg = cab.set_index("tmp")["segmento"].reindex(det["tmp"]).map(tamano).to_numpy()
    det["cantidad"] = np.maximum(1, np.round(rng.lognormal(np.log(seg), 0.55))).astype(int)
    det["precio_unitario"] = det["sku"].map(precio).to_numpy()
    tipo = rng.choice(["sin", "libre", "aprobado"], len(det), p=[0.70, 0.25, 0.05])
    det["descuento_pct"] = np.select([tipo == "libre", tipo == "aprobado"],
                                     [np.round(rng.uniform(1, DESCUENTO_LIBRE, len(det)), 1),
                                      np.round(rng.uniform(DESCUENTO_LIBRE + 0.5, DESCUENTO_MAXIMO, len(det)), 1)], 0.0)
    det["usuario_aprueba"] = np.where(tipo == "aprobado", rng.choice(supervisores, len(det)), None)

    verdad: list[tuple[str, object]] = []                 # (prueba, identificador provisional)
    libres = set(cab["tmp"])                              # facturas aún sin irregularidad sembrada

    def tomar(n: int, candidatas=None) -> np.ndarray:
        base = np.array(sorted(libres if candidatas is None else libres & set(candidatas)))
        elegidas = rng.choice(base, n, replace=False)
        libres.difference_update(elegidas)
        return elegidas

    # anulaciones legítimas: un supervisor, dentro del mismo mes
    for t in tomar(int(n_facturas * 0.025)):
        f = cab.loc[cab["tmp"] == t, "fecha"].iloc[0]
        fin_mes = f + pd.offsets.MonthEnd(0)
        cab.loc[cab["tmp"] == t, ["estado", "fecha_anulacion", "usuario_anulacion"]] = [
            "ANULADA", min(f + pd.Timedelta(days=int(rng.integers(0, 4))), fin_mes), rng.choice(supervisores)]

    # ---------- irregularidades sembradas ----------
    # P04 ventas bajo el costo: precio neto por debajo del costo, sin descuento
    for t in tomar(n["P04"]):
        i = det.index[det["tmp"] == t][0]
        det.loc[i, ["precio_unitario", "descuento_pct", "usuario_aprueba"]] = [
            round(float(costo[det.at[i, "sku"]]) * rng.uniform(0.70, 0.96), 2), 0.0, None]
        verdad.append(("P04", (t, det.at[i, "linea"])))

    # P05 descuentos fuera de política: sobre el límite libre sin aprobación, o sobre el máximo
    for k, t in enumerate(tomar(n["P05"])):
        i = det.index[det["tmp"] == t][0]
        if k < 35:
            det.loc[i, ["descuento_pct", "usuario_aprueba"]] = [round(rng.uniform(11, DESCUENTO_MAXIMO), 1), None]
        else:
            det.loc[i, ["descuento_pct", "usuario_aprueba"]] = [round(rng.uniform(21, 28), 1), rng.choice(supervisores)]
        verdad.append(("P05", (t, det.at[i, "linea"])))

    # P06 segregación de funciones: quien registra aprueba su propio descuento (20) o anula su factura (15)
    for t in tomar(parte(20)):
        i = det.index[det["tmp"] == t][0]
        quien = cab.loc[cab["tmp"] == t, "usuario_registro"].iloc[0]
        det.loc[i, ["descuento_pct", "usuario_aprueba"]] = [round(rng.uniform(11, DESCUENTO_MAXIMO), 1), quien]
        verdad += [("P06", (t, det.at[i, "linea"])), ("P05", (t, det.at[i, "linea"]))]   # también incumple P05
    for t in tomar(parte(15)):
        f = cab.loc[cab["tmp"] == t, "fecha"].iloc[0]
        cab.loc[cab["tmp"] == t, ["estado", "fecha_anulacion", "usuario_anulacion"]] = [
            "ANULADA", min(f + pd.Timedelta(days=int(rng.integers(0, 3))), f + pd.offsets.MonthEnd(0)),
            cab.loc[cab["tmp"] == t, "usuario_registro"].iloc[0]]
        verdad.append(("P06", t))

    # P07 anulaciones tardías: en un mes posterior al de emisión
    antes_de_octubre = cab.loc[cab["fecha"] < f"{ANIO}-10-01", "tmp"]
    for t in tomar(n["P07"], antes_de_octubre):
        f = cab.loc[cab["tmp"] == t, "fecha"].iloc[0]
        cab.loc[cab["tmp"] == t, ["estado", "fecha_anulacion", "usuario_anulacion"]] = [
            "ANULADA", f + pd.offsets.MonthEnd(0) + pd.Timedelta(days=int(rng.integers(5, 75))), rng.choice(supervisores)]
        verdad.append(("P07", t))

    # P09 facturación fuera de horario: de noche (30) o en domingo (15)
    nocturnas = tomar(parte(30))
    cab.loc[cab["tmp"].isin(nocturnas), "hora_registro"] = _hora(rng, len(nocturnas), fuera=True)
    cab.loc[cab["tmp"].isin(nocturnas), "usuario_registro"] = rng.choice(["FACT03", "FACT07"], len(nocturnas))   # dos usuarios concentran el patrón
    for t in tomar(parte(15)):
        f = cab.loc[cab["tmp"] == t, "fecha"].iloc[0]
        cab.loc[cab["tmp"] == t, "fecha"] = f + pd.Timedelta(days=6 - f.day_of_week)    # el domingo de esa semana
        nocturnas = np.append(nocturnas, t)
    verdad += [("P09", t) for t in nocturnas]

    # P10 fraccionamiento: dos facturas del mismo cliente y día, cada una bajo el umbral de gerencia
    siguiente = int(cab["tmp"].max()) + 1
    nuevas_cab, nuevas_det = [], []
    mayoristas = clientes.loc[clientes["segmento"] == "Mayorista", "cliente_id"].to_numpy()
    for _ in range(n["P10"]):
        cli, dia, quien = rng.choice(mayoristas), rng.choice(dias), rng.choice(facturadores)
        zona = clientes.loc[clientes["cliente_id"] == cli].iloc[0]
        for objetivo in (rng.uniform(8200, 9900), rng.uniform(3500, 7500)):
            sku = rng.choice(productos["sku"])
            nuevas_cab.append({"tmp": siguiente, "fecha": pd.Timestamp(dia), "cliente_id": cli, "usuario_registro": quien,
                               "hora_registro": _hora(rng, 1)[0], "segmento": "Mayorista", "zona": zona["zona"],
                               "vendedor_id": zona["vendedor_id"], "serie": {"Lima": "F001", "Provincias": "F002"}[zona["zona"]],
                               "estado": "EMITIDA", "fecha_anulacion": pd.NaT, "usuario_anulacion": None})
            nuevas_det.append({"tmp": siguiente, "linea": 1, "sku": sku, "cantidad": max(1, int(objetivo / precio[sku])),
                               "precio_unitario": float(precio[sku]), "descuento_pct": 0.0, "usuario_aprueba": None})
            siguiente += 1
        verdad.append(("P10", (cli, pd.Timestamp(dia))))
    if nuevas_cab:
        cab = pd.concat([cab, pd.DataFrame(nuevas_cab)], ignore_index=True)
        det = pd.concat([det, pd.DataFrame(nuevas_det)], ignore_index=True)

    # P03 duplicados: la misma factura registrada otra vez, el mismo día o hasta tres días después.
    # También se generan pedidos repetidos legítimos: 20 a una o dos semanas (la prueba no debe
    # marcarlos) y 8 a pocos días (la prueba los marca y el seguimiento debe descartarlos).
    def copiar(t: int, dias_despues: int) -> None:
        nonlocal cab, det, siguiente
        copia = cab.loc[cab["tmp"] == t].iloc[0].copy()
        copia["tmp"] = siguiente
        copia["fecha"] = copia["fecha"] + pd.Timedelta(days=dias_despues)
        if copia["fecha"].day_of_week == 6:
            copia["fecha"] += pd.Timedelta(days=1)
        if dias_despues == 0:                              # el mismo día, unos minutos después
            h, m = map(int, copia["hora_registro"].split(":"))
            minutos = min(h * 60 + m + int(rng.integers(5, 90)), 19 * 60 + 59)
            copia["hora_registro"] = f"{minutos // 60:02d}:{minutos % 60:02d}"
        else:
            copia["hora_registro"] = _hora(rng, 1)[0]
        cab = pd.concat([cab, copia.to_frame().T], ignore_index=True)
        det = pd.concat([det, det[det["tmp"] == t].assign(tmp=siguiente)], ignore_index=True)
        siguiente += 1

    hasta_noviembre = cab.loc[pd.to_datetime(cab["fecha"]) < f"{ANIO}-12-01", "tmp"]
    for t in tomar(n["P03"], hasta_noviembre):
        verdad.append(("P03", siguiente))
        copiar(t, int(rng.integers(0, 3)))
    for k, t in enumerate(tomar(28, hasta_noviembre)):
        copiar(t, int(rng.integers(7, 15)) if k < 20 else int(rng.integers(1, 3)))

    # ---------- importes, aprobación de gerencia y numeración ----------
    cab["fecha"] = pd.to_datetime(cab["fecha"])
    det["importe"] = np.round(det["cantidad"] * det["precio_unitario"] * (1 - det["descuento_pct"] / 100), 2)
    cab["total"] = cab["tmp"].map(det.groupby("tmp")["importe"].sum().round(2))
    cab["aprobacion_gerencia"] = np.where(cab["total"] >= UMBRAL_GERENCIA, "GER01", None)
    cab = cab.sort_values(["serie", "fecha", "hora_registro", "tmp"]).reset_index(drop=True)
    cab["numero"] = cab.groupby("serie").cumcount() + 1
    cab["factura_id"] = cab["serie"] + "-" + cab["numero"].map("{:06d}".format)
    ident = cab.set_index("tmp")["factura_id"]

    # P01 integridad: el total de la cabecera no coincide con el detalle
    for t in tomar(n["P01"], cab.loc[cab["total"] > 2000, "tmp"]):
        cab.loc[cab["tmp"] == t, "total"] += round(float(rng.choice([-1, 1]) * rng.uniform(50, 900)), 2)
        verdad.append(("P01", t))

    # P08 notas de crédito: 250 legítimas y 15 irregulares
    vigentes = cab[(cab["estado"] == "EMITIDA") & cab["tmp"].isin(libres)]
    base = vigentes.sample(250, random_state=seed)
    notas = pd.DataFrame({"factura_id": base["factura_id"].to_numpy(),
                          "fecha": base["fecha"].to_numpy() + pd.to_timedelta(rng.integers(1, 20, 250), unit="D"),
                          "importe": np.round(base["total"].to_numpy() * rng.uniform(0.02, 0.40, 250), 2),
                          "motivo": rng.choice(["Devolución", "Diferencia de precio", "Producto dañado"], 250)})
    irregulares = []
    for k in range(n["P08"]):
        if k < 5:                                         # la factura no existe
            fila = {"factura_id": f"F001-{int(rng.integers(900000, 999999)):06d}", "importe": round(float(rng.uniform(200, 3000)), 2)}
        elif k < 10:                                      # la factura está anulada
            anulada = cab[cab["estado"] == "ANULADA"].sample(1, random_state=seed + k).iloc[0]
            fila = {"factura_id": anulada["factura_id"], "importe": round(float(anulada["total"]) * 0.5, 2)}
        else:                                             # la nota supera el total de la factura
            f = vigentes[~vigentes["factura_id"].isin(notas["factura_id"])].sample(1, random_state=seed + k).iloc[0]
            fila = {"factura_id": f["factura_id"], "importe": round(float(f["total"]) * rng.uniform(1.15, 1.80), 2)}
        fila.update(fecha=pd.Timestamp(rng.choice(dias)), motivo="Devolución", irregular=True)
        irregulares.append(fila)
    notas = pd.concat([notas.assign(irregular=False), *([pd.DataFrame(irregulares)] if irregulares else [])], ignore_index=True)
    notas = notas.sort_values("fecha").reset_index(drop=True)
    notas["nota_id"] = [f"NC01-{i:05d}" for i in range(1, len(notas) + 1)]
    notas["usuario_registro"] = rng.choice(facturadores, len(notas))
    verdad += [("P08", n) for n in notas.loc[notas["irregular"], "nota_id"]]

    # P02 correlativos faltantes: se eliminan facturas ya numeradas
    eliminar = tomar(n["P02"], cab.loc[cab["numero"] > 1, "tmp"])
    verdad += [("P02", ident[t]) for t in eliminar]
    cab = cab[~cab["tmp"].isin(eliminar)]
    det = det[~det["tmp"].isin(eliminar)]

    # ---------- tablas finales ----------
    def clave(prueba: str, x) -> str:
        if prueba in ("P04", "P05") or (prueba == "P06" and isinstance(x, tuple)):
            return f"{ident[x[0]]}/{x[1]}"
        if prueba == "P10":
            return f"{x[0]}|{x[1]:%Y-%m-%d}"
        return ident[x] if prueba in ("P01", "P03", "P06", "P07", "P09") else str(x)

    verdad_df = pd.DataFrame([(p, clave(p, x)) for p, x in verdad], columns=["prueba", "clave"])
    det["factura_id"] = det["tmp"].map(ident)
    cab["fecha_anulacion"] = pd.to_datetime(cab["fecha_anulacion"]).dt.strftime("%Y-%m-%d")
    facturas = cab[["factura_id", "serie", "numero", "fecha", "hora_registro", "cliente_id", "vendedor_id",
                    "usuario_registro", "total", "aprobacion_gerencia", "estado", "fecha_anulacion",
                    "usuario_anulacion"]].assign(fecha=cab["fecha"].dt.strftime("%Y-%m-%d"))
    detalle = det[["factura_id", "linea", "sku", "cantidad", "precio_unitario", "descuento_pct", "usuario_aprueba",
                   "importe"]].sort_values(["factura_id", "linea"])
    notas_credito = notas[["nota_id", "fecha", "factura_id", "importe", "motivo", "usuario_registro"]].assign(
        fecha=notas["fecha"].dt.strftime("%Y-%m-%d"))
    return {"clientes": clientes, "productos": productos, "usuarios": usuarios,
            "facturas": facturas.sort_values("factura_id").reset_index(drop=True),
            "factura_detalle": detalle.reset_index(drop=True), "notas_credito": notas_credito,
            "_verdad": verdad_df.sort_values(["prueba", "clave"]).reset_index(drop=True)}


def escribir(tablas: dict[str, pd.DataFrame], carpeta: Path = DATOS) -> None:
    carpeta.mkdir(exist_ok=True)
    for nombre, tabla in tablas.items():
        tabla.to_csv(carpeta / f"{nombre}.csv", index=False)


if __name__ == "__main__":
    tablas = generar()
    escribir(tablas)
    for nombre, tabla in tablas.items():
        print(f"{nombre:16s} {len(tabla):6,d} filas")
