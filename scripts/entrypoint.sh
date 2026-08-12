#!/bin/bash
set -e

echo "=================================================="
echo " Party ${PARTY_ID} arrancando (${N_COLUMNS} columnas completas de ${N_STEPS} pasos, ${NUM_PARTIES} parties)"
echo "=================================================="

echo "-> Compilando sha256_full_column (n_steps=${N_STEPS}, n_parties=${NUM_PARTIES}, n_columns=${N_COLUMNS})"
./compile.py sha256_full_column "${N_STEPS}" "${NUM_PARTIES}" "${N_COLUMNS}"

mkdir -p Player-Data
{
  for ((c=0; c<N_COLUMNS; c++)); do
    for ((i=0; i<N_STEPS; i++)); do
      echo $(( (PARTY_ID + 1) * 1000000 + c * 1000 + i ))
    done
  done
} > "Player-Data/Input-P${PARTY_ID}-0"

echo "-> Lanzando semi-bin-party.x"
./semi-bin-party.x -N "${NUM_PARTIES}" -p "${PARTY_ID}" -h "${COORDINATOR_HOST}" \
  "sha256_full_column-${N_STEPS}-${NUM_PARTIES}-${N_COLUMNS}"
