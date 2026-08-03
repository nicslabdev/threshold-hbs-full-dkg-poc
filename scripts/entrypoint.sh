#!/bin/bash
set -e

# n_cols por defecto = 1 si no se define (reproduce el caso de una columna)
N_COLS="${N_COLS:-1}"
SYNC_DIR=/mpspdz/sync

echo "=================================================="
echo " Party ${PARTY_ID} arrancando (matriz de ${N_COLS} columnas x ${N_STEPS} pasos, ${NUM_PARTIES} parties)"
echo "=================================================="

# Cada party compila por su cuenta y el tiempo de compilacion varia entre
# contenedores (CPU compartida entre los N que compilan a la vez). Como
# semi-bin-party.x tiene un timeout fijo esperando a que se conecten el
# resto de parties, si una tarda mucho de mas las demas expiran antes de
# que arranque. Barrera por fichero compartido: nadie lanza
# semi-bin-party.x hasta que todas las parties han terminado de compilar.
mkdir -p "${SYNC_DIR}"
rm -f "${SYNC_DIR}/ready-${PARTY_ID}"

echo "-> Compilando sha256_full_column (n_steps=${N_STEPS}, n_parties=${NUM_PARTIES}, n_cols=${N_COLS})"
./compile.py sha256_full_column "${N_STEPS}" "${NUM_PARTIES}" "${N_COLS}"

mkdir -p Player-Data
# Orden columna-mayor (columna 0 completa, luego columna 1, ...) para
# coincidir con la lectura shares[p][c][i] del programa .mpc.
{
  for ((c=0; c<N_COLS; c++)); do
    for ((i=0; i<N_STEPS; i++)); do
      echo $(( (PARTY_ID + 1) * 1000000 + c * 1000 + i ))
    done
  done
} > "Player-Data/Input-P${PARTY_ID}-0"

touch "${SYNC_DIR}/ready-${PARTY_ID}"
echo "-> Compilacion lista, esperando al resto de parties..."
for ((p=0; p<NUM_PARTIES; p++)); do
  while [ ! -f "${SYNC_DIR}/ready-${p}" ]; do
    sleep 1
  done
done

echo "-> Lanzando semi-bin-party.x"
./semi-bin-party.x -N "${NUM_PARTIES}" -p "${PARTY_ID}" -h "${COORDINATOR_HOST}" \
  "sha256_full_column-${N_STEPS}-${NUM_PARTIES}-${N_COLS}"
