#!/bin/bash
set -e

# MODE selects the execution mode of the .mpc program:
#   - "sequential": the N_COLS columns are generated one after another.
#   - "simd": the N_COLS columns are processed at once, packed as SIMD
#     lanes inside a single call to sha256() per step.
MODE="${MODE:-sequential}"
# N_COLS defaults to 1 if not set (reproduces the single-column case)
N_COLS="${N_COLS:-1}"
SYNC_DIR=/mpspdz/sync

if [[ "${MODE}" != "sequential" && "${MODE}" != "simd" ]]; then
  echo "MODE debe ser 'sequential' o 'simd' (recibido: '${MODE}')" >&2
  exit 1
fi

echo "=================================================="
echo " Party ${PARTY_ID} arrancando (modo=${MODE}, matriz de ${N_COLS} columnas x ${N_STEPS} pasos, ${NUM_PARTIES} parties)"
echo "=================================================="

# Each party compiles on its own and compile time varies between
# containers (CPU shared among the N that compile at the same time). Since
# semi-bin-party.x has a fixed timeout waiting for the other parties to
# connect, if one takes much longer the others time out before it starts.
# Shared-file barrier: no one launches semi-bin-party.x until all parties
# have finished compiling.
mkdir -p "${SYNC_DIR}"
rm -f "${SYNC_DIR}/ready-${PARTY_ID}"

echo "-> Compilando sha256_full_column (n_steps=${N_STEPS}, n_parties=${NUM_PARTIES}, n_cols=${N_COLS}, mode=${MODE})"
./compile.py sha256_full_column "${N_STEPS}" "${NUM_PARTIES}" "${N_COLS}" "${MODE}"

mkdir -p Player-Data
# Column-major order (column 0 in full, then column 1, ...) to match
# the shares[p][c][i] reading in the .mpc program. The order is the
# same for both modes.
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
  "sha256_full_column-${N_STEPS}-${NUM_PARTIES}-${N_COLS}-${MODE}"
