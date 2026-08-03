#!/bin/bash
set -e

# n_cols por defecto = 1 si no se define (reproduce el caso de una columna)
N_COLS="${N_COLS:-1}"

echo "=================================================="
echo " Party ${PARTY_ID} arrancando (matriz de ${N_COLS} columnas x ${N_STEPS} pasos, ${NUM_PARTIES} parties)"
echo "=================================================="

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

echo "-> Lanzando semi-bin-party.x"
./semi-bin-party.x -N "${NUM_PARTIES}" -p "${PARTY_ID}" -h "${COORDINATOR_HOST}" \
  "sha256_full_column-${N_STEPS}-${NUM_PARTIES}-${N_COLS}"
