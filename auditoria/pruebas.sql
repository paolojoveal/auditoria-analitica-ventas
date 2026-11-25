-- Pruebas de auditoría sobre el ciclo de ventas (SQLite).
--
-- Cada prueba corre sobre el 100% de las transacciones y devuelve una fila por excepción, con:
--   clave    identificador del registro observado (para el seguimiento y los papeles de trabajo)
--   importe  monto expuesto en soles, según la prueba
-- Las líneas «-- @campo: valor» son la ficha de la prueba; ejecutar.py las lee para armar el informe.

-- @prueba: P01
-- @titulo: Integridad de totales
-- @objetivo: Verificar que el total de cada factura coincide con la suma de sus líneas.
-- @criterio: El total de la cabecera debe ser igual a la suma del detalle (tolerancia de S/ 0.01).
-- @riesgo: Ventas registradas por un importe distinto del facturado; errores o manipulación del total.
-- @seguimiento: Recalcular la factura con el documento físico y revisar quién modificó la cabecera.
SELECT f.factura_id AS clave,
       f.fecha,
       f.usuario_registro,
       f.total                                   AS total_cabecera,
       ROUND(SUM(d.importe), 2)                  AS total_detalle,
       ROUND(f.total - SUM(d.importe), 2)        AS diferencia,
       ABS(ROUND(f.total - SUM(d.importe), 2))   AS importe
FROM facturas f
JOIN factura_detalle d USING (factura_id)
GROUP BY f.factura_id
HAVING ABS(f.total - SUM(d.importe)) > 0.01
ORDER BY importe DESC;

-- @prueba: P02
-- @titulo: Correlativos faltantes
-- @objetivo: Identificar números de factura que no existen dentro del rango emitido por cada serie.
-- @criterio: La numeración de cada serie es correlativa y sin saltos.
-- @riesgo: Facturas eliminadas del sistema o ventas no registradas.
-- @seguimiento: Pedir el sustento de cada número faltante (anulación física, error de impresión) y cruzar con SUNAT.
WITH RECURSIVE
limites AS (
    SELECT serie, MIN(numero) AS primero, MAX(numero) AS ultimo FROM facturas GROUP BY serie
),
esperados(serie, numero, ultimo) AS (
    SELECT serie, primero, ultimo FROM limites
    UNION ALL
    SELECT serie, numero + 1, ultimo FROM esperados WHERE numero < ultimo
)
SELECT e.serie || '-' || printf('%06d', e.numero) AS clave,
       e.serie,
       e.numero AS numero_faltante,
       (SELECT MAX(fecha) FROM facturas x WHERE x.serie = e.serie AND x.numero < e.numero) AS fecha_de_la_anterior,
       0.0 AS importe
FROM esperados e
LEFT JOIN facturas f ON f.serie = e.serie AND f.numero = e.numero
WHERE f.numero IS NULL
ORDER BY e.serie, e.numero;

-- @prueba: P03
-- @titulo: Posibles facturas duplicadas
-- @objetivo: Detectar ventas registradas dos veces.
-- @criterio: No deben existir dos facturas vigentes del mismo cliente por el mismo importe en un lapso de tres días.
-- @riesgo: Ingresos sobrestimados y cuentas por cobrar inexistentes.
-- @seguimiento: Confirmar con el cliente y con la guía de despacho si hubo dos entregas. Un pedido repetido es legítimo.
SELECT b.factura_id AS clave,
       a.factura_id AS factura_anterior,
       b.cliente_id,
       a.fecha      AS fecha_anterior,
       b.fecha,
       CAST(julianday(b.fecha) - julianday(a.fecha) AS INTEGER) AS dias_entre_ambas,
       b.usuario_registro,
       b.total      AS importe
FROM facturas a
JOIN facturas b
  ON  b.cliente_id = a.cliente_id
  AND b.total = a.total
  AND b.factura_id > a.factura_id
  AND julianday(b.fecha) - julianday(a.fecha) BETWEEN 0 AND 3
WHERE a.estado = 'EMITIDA' AND b.estado = 'EMITIDA'
ORDER BY importe DESC;

-- @prueba: P04
-- @titulo: Ventas por debajo del costo
-- @objetivo: Identificar líneas vendidas a un precio neto menor que el costo unitario del producto.
-- @criterio: El precio neto de descuento no puede ser inferior al costo unitario.
-- @riesgo: Pérdida directa de margen; precios mal cargados o ventas de favor.
-- @seguimiento: Validar el costo vigente a la fecha de venta y la autorización del precio. El importe es la pérdida frente al costo.
SELECT d.factura_id || '/' || d.linea AS clave,
       f.fecha,
       f.cliente_id,
       f.usuario_registro,
       d.sku,
       d.cantidad,
       d.precio_unitario,
       d.descuento_pct,
       ROUND(d.precio_unitario * (1 - d.descuento_pct / 100.0), 2) AS precio_neto,
       p.costo_unitario,
       ROUND((p.costo_unitario - d.precio_unitario * (1 - d.descuento_pct / 100.0)) * d.cantidad, 2) AS importe
FROM factura_detalle d
JOIN facturas f  USING (factura_id)
JOIN productos p USING (sku)
WHERE f.estado = 'EMITIDA'
  AND d.precio_unitario * (1 - d.descuento_pct / 100.0) < p.costo_unitario
ORDER BY importe DESC;

-- @prueba: P05
-- @titulo: Descuentos fuera de política
-- @objetivo: Verificar que los descuentos respetan los límites y las aprobaciones de la política comercial.
-- @criterio: Hasta 10% sin aprobación; de 10% a 20% con aprobación de un supervisor; más de 20% no está permitido.
-- @riesgo: Descuentos no autorizados que reducen el margen; colusión entre vendedor y cliente.
-- @seguimiento: Revisar el sustento de cada descuento. El importe es el descuento otorgado por encima del 10% libre.
SELECT d.factura_id || '/' || d.linea AS clave,
       f.fecha,
       f.cliente_id,
       f.vendedor_id,
       f.usuario_registro,
       d.descuento_pct,
       d.usuario_aprueba,
       u.rol AS rol_de_quien_aprueba,
       CASE WHEN d.descuento_pct > 20      THEN 'Supera el máximo de 20%'
            WHEN d.usuario_aprueba IS NULL THEN 'Sin aprobación'
            ELSE 'Aprobado por quien no es supervisor' END AS motivo,
       ROUND(d.cantidad * d.precio_unitario * (d.descuento_pct - 10) / 100.0, 2) AS importe
FROM factura_detalle d
JOIN facturas f USING (factura_id)
LEFT JOIN usuarios u ON u.usuario_id = d.usuario_aprueba
WHERE f.estado = 'EMITIDA'
  AND (d.descuento_pct > 20
       OR (d.descuento_pct > 10 AND (d.usuario_aprueba IS NULL OR u.rol <> 'SUPERVISOR')))
ORDER BY importe DESC;

-- @prueba: P06
-- @titulo: Segregación de funciones
-- @objetivo: Detectar operaciones en que la misma persona ejecuta y autoriza.
-- @criterio: Quien registra una factura no puede aprobar su descuento ni anularla.
-- @riesgo: Una sola persona puede otorgar beneficios u ocultar una venta sin que nadie más intervenga.
-- @seguimiento: Revisar los perfiles de acceso al sistema y el sustento de cada operación.
SELECT d.factura_id || '/' || d.linea AS clave,
       'Registra la factura y aprueba su descuento' AS conflicto,
       f.usuario_registro AS usuario,
       f.fecha,
       ROUND(d.cantidad * d.precio_unitario * d.descuento_pct / 100.0, 2) AS importe
FROM factura_detalle d
JOIN facturas f USING (factura_id)
WHERE d.usuario_aprueba = f.usuario_registro
UNION ALL
SELECT f.factura_id,
       'Registra la factura y la anula',
       f.usuario_registro,
       f.fecha,
       f.total
FROM facturas f
WHERE f.estado = 'ANULADA' AND f.usuario_anulacion = f.usuario_registro
ORDER BY importe DESC;

-- @prueba: P07
-- @titulo: Anulaciones tardías
-- @objetivo: Identificar facturas anuladas después del cierre del mes en que se emitieron.
-- @criterio: Una factura solo se anula dentro del mes de emisión; después corresponde una nota de crédito.
-- @riesgo: Reversión de ventas ya reportadas; ventas ficticias para alcanzar metas que luego se anulan.
-- @seguimiento: Verificar si la venta contó para comisiones o metas del mes de emisión y quién pidió la anulación.
SELECT factura_id AS clave,
       fecha,
       fecha_anulacion,
       CAST(julianday(fecha_anulacion) - julianday(fecha) AS INTEGER) AS dias_hasta_la_anulacion,
       vendedor_id,
       usuario_anulacion,
       total AS importe
FROM facturas
WHERE estado = 'ANULADA'
  AND strftime('%Y-%m', fecha_anulacion) > strftime('%Y-%m', fecha)
ORDER BY dias_hasta_la_anulacion DESC;

-- @prueba: P08
-- @titulo: Notas de crédito sin sustento
-- @objetivo: Verificar que cada nota de crédito corresponde a una factura vigente y no excede su importe.
-- @criterio: La nota de crédito referencia una factura existente y vigente, y el acumulado no supera el total facturado.
-- @riesgo: Notas de crédito ficticias para reducir cuentas por cobrar o encubrir apropiación de cobranzas.
-- @seguimiento: Pedir el sustento (devolución física, reclamo) y confirmar el saldo con el cliente.
WITH acumulado AS (
    SELECT factura_id, SUM(importe) AS total_notas FROM notas_credito GROUP BY factura_id
)
SELECT n.nota_id AS clave,
       n.fecha,
       n.factura_id,
       n.usuario_registro,
       f.total  AS total_factura,
       a.total_notas,
       CASE WHEN f.factura_id IS NULL  THEN 'La factura no existe'
            WHEN f.estado = 'ANULADA'  THEN 'La factura está anulada'
            ELSE 'Las notas de crédito superan el total de la factura' END AS motivo,
       n.importe
FROM notas_credito n
LEFT JOIN facturas f  USING (factura_id)
LEFT JOIN acumulado a USING (factura_id)
WHERE f.factura_id IS NULL
   OR f.estado = 'ANULADA'
   OR a.total_notas > f.total + 0.01
ORDER BY n.importe DESC;

-- @prueba: P09
-- @titulo: Facturación fuera de horario
-- @objetivo: Identificar facturas registradas en domingo o fuera del horario de operación.
-- @criterio: La facturación se realiza de lunes a sábado, de 08:00 a 20:00.
-- @riesgo: Operaciones registradas sin supervisión; uso indebido de usuarios.
-- @seguimiento: Revisar la concentración por usuario y contrastar con el registro de accesos al sistema.
SELECT factura_id AS clave,
       fecha,
       hora_registro,
       usuario_registro,
       CASE WHEN strftime('%w', fecha) = '0' THEN 'Domingo' ELSE 'Fuera de 08:00 a 20:00' END AS motivo,
       total AS importe
FROM facturas
WHERE strftime('%w', fecha) = '0'
   OR hora_registro < '08:00'
   OR hora_registro >= '20:00'
ORDER BY fecha, hora_registro;

-- @prueba: P10
-- @titulo: Fraccionamiento bajo el umbral de aprobación
-- @objetivo: Detectar ventas divididas en varias facturas para evitar la aprobación de gerencia.
-- @criterio: Las ventas desde S/ 10 000 requieren aprobación de gerencia; no se fraccionan para eludirla.
-- @riesgo: Ventas grandes sin la evaluación de crédito que exige la política.
-- @seguimiento: Revisar si las facturas corresponden a un mismo pedido u orden de compra. Dos pedidos distintos el mismo día son legítimos.
SELECT cliente_id || '|' || fecha AS clave,
       cliente_id,
       fecha,
       COUNT(*)                        AS facturas_del_dia,
       ROUND(MAX(total), 2)            AS factura_mayor,
       GROUP_CONCAT(factura_id, ', ')  AS documentos,
       GROUP_CONCAT(DISTINCT usuario_registro) AS usuarios,
       ROUND(SUM(total), 2)            AS importe
FROM facturas
WHERE estado = 'EMITIDA'
GROUP BY cliente_id, fecha
HAVING COUNT(*) >= 2
   AND MAX(total) < 10000
   AND SUM(total) >= 10000
ORDER BY importe DESC;
