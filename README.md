# sha256-full-column-test

Prueba conceptual: saca la columna COMPLETA de un CRV (n_steps
valores) en una unica ejecucion de MPC, reconstruyendo internamente
(sin revelarlo nunca) el valor real T_i que tendria el "virtual-dealer" en cada paso.

Formula usada:

$$
\mathrm{CRV}_i = H\left(\mathrm{CRV}_{i-1} \oplus \bigoplus_{j=1}^{k} \mathrm{SK}_j^{i-1}\right) \oplus \bigoplus_{j=1}^{k} \mathrm{SK}_j^i
$$

## Cómo ejecutarlo

```
docker compose up --build
```

`N_STEPS` (por defecto 16) y `NUM_PARTIES` (por defecto 3) se
configuran en `docker-compose.yml`.

## Qué esperar

En el log de `party0` (solo la party coordinadora imprime,
por diseño de MP-SPDZ) deberías ver N_STEPS líneas `Reg[0] = 0x...`
seguidas -- la columna completa, revelada de una sola pasada. Al
final, MP-SPDZ imprime el coste total (tiempo, datos enviados) de
TODA la columna de una vez.
