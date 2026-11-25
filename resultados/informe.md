# Informe de auditoría: ciclo de ventas

**Distribuidora Altiplano S.A.C. (empresa ficticia)** · Periodo 2025-01-02 a 2025-12-30

> Informe generado por `python -m auditoria.ejecutar` a partir de datos sintéticos. Las causas y recomendaciones de una auditoría real salen del seguimiento de cada excepción, no de la consulta.

## Resumen

- **Población:** 9,095 facturas (18,477 líneas) y 265 notas de crédito. Facturación vigente de S/ 18,179,165; 260 facturas anuladas por S/ 482,772.
- **Alcance:** diez pruebas sobre el 100% de las transacciones, sin muestreo, más un análisis de Benford.
- **Resultado:** 345 excepciones en total. Los mayores importes expuestos son: fraccionamiento bajo el umbral de aprobación (S/ 680,043), facturación fuera de horario (S/ 119,227), posibles facturas duplicadas (S/ 73,994).
- **Una excepción no es un hallazgo.** Es un registro que no cumple el criterio y que hay que explicar. Parte de ellas tendrá sustento válido.

| Prueba | Título | Excepciones | Importe expuesto |
|---|---|---|---|
| P01 | Integridad de totales | 10 | S/ 4,465 |
| P02 | Correlativos faltantes | 18 | S/ 0 |
| P03 | Posibles facturas duplicadas | 33 | S/ 73,994 |
| P04 | Ventas por debajo del costo | 41 | S/ 4,877 |
| P05 | Descuentos fuera de política | 80 | S/ 6,721 |
| P06 | Segregación de funciones | 35 | S/ 47,523 |
| P07 | Anulaciones tardías | 20 | S/ 46,247 |
| P08 | Notas de crédito sin sustento | 16 | S/ 37,302 |
| P09 | Facturación fuera de horario | 45 | S/ 119,227 |
| P10 | Fraccionamiento bajo el umbral de aprobación | 47 | S/ 680,043 |

## Detalle por prueba

### P01 · Integridad de totales

- **Objetivo:** Verificar que el total de cada factura coincide con la suma de sus líneas.
- **Criterio:** El total de la cabecera debe ser igual a la suma del detalle (tolerancia de S/ 0.01).
- **Riesgo:** Ventas registradas por un importe distinto del facturado; errores o manipulación del total.
- **Resultado:** 10 excepciones por S/ 4,465.
- **Seguimiento:** Recalcular la factura con el documento físico y revisar quién modificó la cabecera.

Las cinco primeras excepciones:

| clave | fecha | usuario_registro | total_cabecera | total_detalle | diferencia | importe |
|---|---|---|---|---|---|---|
| F001-000279 | 2025-01-20 | FACT02 | 2970.34 | 2112.19 | 858.15 | 858.15 |
| F001-000380 | 2025-01-27 | FACT02 | 3364.0099999999998 | 2662.83 | 701.18 | 701.18 |
| F001-005436 | 2025-12-03 | FACT03 | 2631.33 | 3251.69 | -620.36 | 620.36 |
| F002-002438 | 2025-10-27 | FACT07 | 3574.71 | 3013.85 | 560.86 | 560.86 |
| F002-002042 | 2025-09-10 | FACT06 | 2275.2300000000005 | 2789.01 | -513.78 | 513.78 |

### P02 · Correlativos faltantes

- **Objetivo:** Identificar números de factura que no existen dentro del rango emitido por cada serie.
- **Criterio:** La numeración de cada serie es correlativa y sin saltos.
- **Riesgo:** Facturas eliminadas del sistema o ventas no registradas.
- **Resultado:** 18 excepciones por S/ 0.
- **Seguimiento:** Pedir el sustento de cada número faltante (anulación física, error de impresión) y cruzar con SUNAT.

Las cinco primeras excepciones:

| clave | serie | numero_faltante | fecha_de_la_anterior | importe |
|---|---|---|---|---|
| F001-000025 | F001 | 25 | 2025-01-03 | 0.00 |
| F001-000051 | F001 | 51 | 2025-01-04 | 0.00 |
| F001-000076 | F001 | 76 | 2025-01-06 | 0.00 |
| F001-000108 | F001 | 108 | 2025-01-08 | 0.00 |
| F001-000125 | F001 | 125 | 2025-01-09 | 0.00 |

### P03 · Posibles facturas duplicadas

- **Objetivo:** Detectar ventas registradas dos veces.
- **Criterio:** No deben existir dos facturas vigentes del mismo cliente por el mismo importe en un lapso de tres días.
- **Riesgo:** Ingresos sobrestimados y cuentas por cobrar inexistentes.
- **Resultado:** 33 excepciones por S/ 73,994.
- **Seguimiento:** Confirmar con el cliente y con la guía de despacho si hubo dos entregas. Un pedido repetido es legítimo.

Las cinco primeras excepciones:

| clave | factura_anterior | cliente_id | fecha_anterior | fecha | dias_entre_ambas | usuario_registro | importe |
|---|---|---|---|---|---|---|---|
| F002-001087 | F002-001079 | C0346 | 2025-05-21 | 2025-05-22 | 1 | FACT07 | 16,277.67 |
| F001-004967 | F001-004932 | C0093 | 2025-10-31 | 2025-11-03 | 3 | FACT01 | 8,604.90 |
| F002-001867 | F002-001852 | C0155 | 2025-08-16 | 2025-08-18 | 2 | FACT08 | 4,909.54 |
| F002-001922 | F002-001911 | C0370 | 2025-08-23 | 2025-08-25 | 2 | FACT03 | 4,775.63 |
| F001-005173 | F001-005139 | C0133 | 2025-11-13 | 2025-11-14 | 1 | FACT06 | 4,174.61 |

### P04 · Ventas por debajo del costo

- **Objetivo:** Identificar líneas vendidas a un precio neto menor que el costo unitario del producto.
- **Criterio:** El precio neto de descuento no puede ser inferior al costo unitario.
- **Riesgo:** Pérdida directa de margen; precios mal cargados o ventas de favor.
- **Resultado:** 41 excepciones por S/ 4,877.
- **Seguimiento:** Validar el costo vigente a la fecha de venta y la autorización del precio. El importe es la pérdida frente al costo.

**Concentración.** FACT04 y FACT05 acumulan 21 de las 41 excepciones (51%).

Las cinco primeras excepciones:

| clave | fecha | cliente_id | usuario_registro | sku | cantidad | precio_unitario | descuento_pct | precio_neto | costo_unitario | importe |
|---|---|---|---|---|---|---|---|---|---|---|
| F001-003996/1 | 2025-09-03 | C0169 | FACT05 | P029 | 118 | 19.49 | 0.0 | 19.49 | 26.43 | 818.92 |
| F001-004454/1 | 2025-10-01 | C0244 | FACT03 | P118 | 105 | 13.07 | 0.0 | 13.07 | 16.73 | 384.30 |
| F001-000810/1 | 2025-02-22 | C0305 | FACT05 | P013 | 42 | 17.66 | 0.0 | 17.66 | 24.59 | 291.06 |
| F001-004754/1 | 2025-10-20 | C0029 | FACT04 | P112 | 148 | 4.33 | 0.0 | 4.33 | 6.04 | 253.08 |
| F002-000632/1 | 2025-03-25 | C0364 | FACT05 | P106 | 100 | 13.32 | 0.0 | 13.32 | 15.66 | 234.00 |

### P05 · Descuentos fuera de política

- **Objetivo:** Verificar que los descuentos respetan los límites y las aprobaciones de la política comercial.
- **Criterio:** Hasta 10% sin aprobación; de 10% a 20% con aprobación de un supervisor; más de 20% no está permitido.
- **Riesgo:** Descuentos no autorizados que reducen el margen; colusión entre vendedor y cliente.
- **Resultado:** 80 excepciones por S/ 6,721.
- **Seguimiento:** Revisar el sustento de cada descuento. El importe es el descuento otorgado por encima del 10% libre.
- **Por tipo:** Sin aprobación: 35; Supera el máximo de 20%: 25; Aprobado por quien no es supervisor: 20.

Las cinco primeras excepciones:

| clave | fecha | cliente_id | vendedor_id | usuario_registro | descuento_pct | usuario_aprueba | rol_de_quien_aprueba | motivo | importe |
|---|---|---|---|---|---|---|---|---|---|
| F001-001603/1 | 2025-04-15 | C0377 | V04 | FACT02 | 27.7 | SUP02 | SUPERVISOR | Supera el máximo de 20% | 1,609.20 |
| F001-005003/1 | 2025-11-05 | C0360 | V12 | FACT03 | 18.9 | FACT03 | FACTURADOR | Aprobado por quien no es supervisor | 425.93 |
| F001-001937/1 | 2025-05-05 | C0281 | V07 | FACT02 | 26.8 | SUP03 | SUPERVISOR | Supera el máximo de 20% | 376.02 |
| F002-002145/1 | 2025-09-22 | C0328 | V11 | FACT02 | 27.7 | SUP02 | SUPERVISOR | Supera el máximo de 20% | 306.62 |
| F002-000035/1 | 2025-01-07 | C0228 | V08 | FACT06 | 28.0 | SUP02 | SUPERVISOR | Supera el máximo de 20% | 299.70 |

### P06 · Segregación de funciones

- **Objetivo:** Detectar operaciones en que la misma persona ejecuta y autoriza.
- **Criterio:** Quien registra una factura no puede aprobar su descuento ni anularla.
- **Riesgo:** Una sola persona puede otorgar beneficios u ocultar una venta sin que nadie más intervenga.
- **Resultado:** 35 excepciones por S/ 47,523.
- **Seguimiento:** Revisar los perfiles de acceso al sistema y el sustento de cada operación.
- **Por tipo:** Registra la factura y aprueba su descuento: 20; Registra la factura y la anula: 15.

Las cinco primeras excepciones:

| clave | conflicto | usuario | fecha | importe |
|---|---|---|---|---|
| F001-003539 | Registra la factura y la anula | FACT02 | 2025-08-06 | 15,496.69 |
| F001-005700 | Registra la factura y la anula | FACT02 | 2025-12-15 | 6,582.72 |
| F001-002433 | Registra la factura y la anula | FACT05 | 2025-06-04 | 5,238.49 |
| F001-003130 | Registra la factura y la anula | FACT04 | 2025-07-12 | 4,654.58 |
| F002-001387 | Registra la factura y la anula | FACT02 | 2025-06-25 | 3,000.08 |

### P07 · Anulaciones tardías

- **Objetivo:** Identificar facturas anuladas después del cierre del mes en que se emitieron.
- **Criterio:** Una factura solo se anula dentro del mes de emisión; después corresponde una nota de crédito.
- **Riesgo:** Reversión de ventas ya reportadas; ventas ficticias para alcanzar metas que luego se anulan.
- **Resultado:** 20 excepciones por S/ 46,247.
- **Seguimiento:** Verificar si la venta contó para comisiones o metas del mes de emisión y quién pidió la anulación.

**Concentración.** SUP03 y SUP01 acumulan 14 de las 20 excepciones (70%).

Las cinco primeras excepciones:

| clave | fecha | fecha_anulacion | dias_hasta_la_anulacion | vendedor_id | usuario_anulacion | importe |
|---|---|---|---|---|---|---|
| F002-000532 | 2025-03-13 | 2025-06-11 | 90 | V07 | SUP03 | 2,162.28 |
| F001-000160 | 2025-01-11 | 2025-04-09 | 88 | V04 | SUP03 | 114.52 |
| F001-003100 | 2025-07-11 | 2025-10-02 | 83 | V01 | SUP02 | 387.99 |
| F001-001722 | 2025-04-22 | 2025-07-08 | 77 | V10 | SUP01 | 4,987.15 |
| F002-001504 | 2025-07-07 | 2025-09-18 | 73 | V09 | SUP02 | 157.61 |

### P08 · Notas de crédito sin sustento

- **Objetivo:** Verificar que cada nota de crédito corresponde a una factura vigente y no excede su importe.
- **Criterio:** La nota de crédito referencia una factura existente y vigente, y el acumulado no supera el total facturado.
- **Riesgo:** Notas de crédito ficticias para reducir cuentas por cobrar o encubrir apropiación de cobranzas.
- **Resultado:** 16 excepciones por S/ 37,302.
- **Seguimiento:** Pedir el sustento (devolución física, reclamo) y confirmar el saldo con el cliente.
- **Por tipo:** La factura no existe: 6; Las notas de crédito superan el total de la factura: 5; La factura está anulada: 5.

**Concentración.** FACT04 y FACT03 acumulan 8 de las 16 excepciones (50%).

Las cinco primeras excepciones:

| clave | fecha | factura_id | usuario_registro | total_factura | total_notas | motivo | importe |
|---|---|---|---|---|---|---|---|
| NC01-00096 | 2025-05-30 | F001-003721 | FACT04 | 8007.92 | 13894.9 | Las notas de crédito superan el total de la factura | 13,894.90 |
| NC01-00013 | 2025-02-03 | F001-000724 | FACT01 | 3580.48 | 5341.29 | Las notas de crédito superan el total de la factura | 5,341.29 |
| NC01-00235 | 2025-12-10 | F001-001608 | FACT04 | 2869.24 | 4491.13 | Las notas de crédito superan el total de la factura | 4,491.13 |
| NC01-00247 | 2025-12-17 | F002-001355 | FACT02 | 1217.54 | 2044.82 | Las notas de crédito superan el total de la factura | 2,044.82 |
| NC01-00249 | 2025-12-19 | F001-969475 | FACT03 |  | 1964.19 | La factura no existe | 1,964.19 |

### P09 · Facturación fuera de horario

- **Objetivo:** Identificar facturas registradas en domingo o fuera del horario de operación.
- **Criterio:** La facturación se realiza de lunes a sábado, de 08:00 a 20:00.
- **Riesgo:** Operaciones registradas sin supervisión; uso indebido de usuarios.
- **Resultado:** 45 excepciones por S/ 119,227.
- **Seguimiento:** Revisar la concentración por usuario y contrastar con el registro de accesos al sistema.
- **Por tipo:** Fuera de 08:00 a 20:00: 30; Domingo: 15.

**Concentración.** FACT07 y FACT03 acumulan 34 de las 45 excepciones (76%).

Las cinco primeras excepciones:

| clave | fecha | hora_registro | usuario_registro | motivo | importe |
|---|---|---|---|---|---|
| F001-000040 | 2025-01-04 | 03:02 | FACT03 | Fuera de 08:00 a 20:00 | 401.41 |
| F001-000095 | 2025-01-08 | 04:00 | FACT03 | Fuera de 08:00 a 20:00 | 463.16 |
| F001-000178 | 2025-01-12 | 18:36 | FACT05 | Domingo | 5,304.24 |
| F001-000261 | 2025-01-19 | 09:59 | FACT07 | Domingo | 6,402.00 |
| F002-000139 | 2025-01-20 | 22:23 | FACT07 | Fuera de 08:00 a 20:00 | 2,167.41 |

### P10 · Fraccionamiento bajo el umbral de aprobación

- **Objetivo:** Detectar ventas divididas en varias facturas para evitar la aprobación de gerencia.
- **Criterio:** Las ventas desde S/ 10 000 requieren aprobación de gerencia; no se fraccionan para eludirla.
- **Riesgo:** Ventas grandes sin la evaluación de crédito que exige la política.
- **Resultado:** 47 excepciones por S/ 680,043.
- **Seguimiento:** Revisar si las facturas corresponden a un mismo pedido u orden de compra. Dos pedidos distintos el mismo día son legítimos.

Las cinco primeras excepciones:

| clave | cliente_id | fecha | facturas_del_dia | factura_mayor | documentos | usuarios | importe |
|---|---|---|---|---|---|---|---|
| C0181|2025-10-27 | C0181 | 2025-10-27 | 4 | 8750.05 | F001-004839, F001-004840, F001-004848, F001-004859 | FACT02,FACT08,FACT05 | 23,697.29 |
| C0157|2025-11-18 | C0157 | 2025-11-18 | 3 | 9580.42 | F001-005207, F001-005212, F001-005214 | FACT05,FACT01 | 22,838.91 |
| C0190|2025-11-07 | C0190 | 2025-11-07 | 3 | 9359.91 | F001-005034, F001-005038, F001-005040 | FACT01,FACT07 | 19,634.55 |
| C0034|2025-06-05 | C0034 | 2025-06-05 | 3 | 9576.9 | F001-002454, F001-002465, F001-002467 | FACT05,FACT03 | 19,246.16 |
| C0048|2025-12-01 | C0048 | 2025-12-01 | 3 | 8545.9 | F001-005389, F001-005390, F001-005393 | FACT02,FACT04 | 18,740.40 |

## Análisis de Benford

En importes que abarcan varios órdenes de magnitud, el primer dígito sigue la ley de Benford. Una desviación marcada puede indicar importes fabricados o fraccionados cerca de un umbral.

| Dígito | Facturas | Proporción | Benford |
|---|---|---|---|
| 1 | 2,496 | 28.3% | 30.1% |
| 2 | 1,548 | 17.5% | 17.6% |
| 3 | 1,119 | 12.7% | 12.5% |
| 4 | 914 | 10.3% | 9.7% |
| 5 | 756 | 8.6% | 7.9% |
| 6 | 586 | 6.6% | 6.7% |
| 7 | 517 | 5.9% | 5.8% |
| 8 | 479 | 5.4% | 5.1% |
| 9 | 420 | 4.8% | 4.6% |

Chi-cuadrado = 21.1 (valor crítico al 5% con 8 grados de libertad: 15.5). Desviación absoluta media = 0.0044: **conformidad cercana** según los umbrales de Nigrini (2012). El chi-cuadrado rechaza con facilidad en muestras grandes; por eso se lee junto con la desviación absoluta media.

## Contraste con las irregularidades sembradas

Los datos son sintéticos y el generador anota qué irregularidades sembró. Eso permite medir algo que en una auditoría real no se observa: cuánto detecta cada prueba y cuántas excepciones son falsas alarmas.

| Prueba | Sembradas | Detectadas | Excepciones no sembradas | Sensibilidad | Precisión |
|---|---|---|---|---|---|
| P01 | 10 | 10 | 0 | 100% | 100% |
| P02 | 18 | 18 | 0 | 100% | 100% |
| P03 | 25 | 25 | 8 | 100% | 76% |
| P04 | 40 | 40 | 1 | 100% | 98% |
| P05 | 80 | 80 | 0 | 100% | 100% |
| P06 | 35 | 35 | 0 | 100% | 100% |
| P07 | 20 | 20 | 0 | 100% | 100% |
| P08 | 15 | 15 | 1 | 100% | 94% |
| P09 | 45 | 45 | 0 | 100% | 100% |
| P10 | 30 | 30 | 17 | 100% | 64% |

## Alcance y limitaciones

- Las pruebas verifican atributos de los registros; no reemplazan la confirmación con clientes, la revisión documentaria ni el recorrido del proceso.
- Un correlativo faltante al final de una serie no es detectable: no hay un número posterior que lo delate.
- Los umbrales (tres días para duplicados, S/ 10 000 para fraccionamiento) son parámetros de la prueba. Cambiarlos mueve el balance entre excepciones omitidas y falsas alarmas.