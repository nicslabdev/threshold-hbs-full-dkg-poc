import hashlib
import os
import sys

# Se pueden pasar por linea de comandos o por entorno, para no tener que
# tocar el script cada vez que se cambia la configuracion del compose:
#   python3 verify_full_column.py [n_columns] [n_steps] [n_parties]
def _arg(pos, env, default):
    if len(sys.argv) > pos:
        return int(sys.argv[pos])
    return int(os.environ.get(env, default))

n_columns = _arg(1, "N_COLUMNS", 4)
n_steps = _arg(2, "N_STEPS", 16)
n_parties = _arg(3, "NUM_PARTIES", 3)

# Mismos valores deterministas que genera scripts/entrypoint.sh:
# (party_id + 1) * 1000000 + columna * 1000 + paso
values = [[[(p + 1) * 1000000 + c * 1000 + i for i in range(n_steps)]
           for c in range(n_columns)]
          for p in range(n_parties)]


def S(c, i):
    """XOR de los valores de las n_parties trustees en la posicion i de la columna c."""
    result = 0
    for p in range(n_parties):
        result ^= values[p][c][i]
    return result


def to_bytes32(value):
    return value.to_bytes(32, byteorder="big")


def column(c):
    """Recalcula la columna c completa (independiente del resto)."""
    results = []

    # Caso base: CRV_0 = S_0 (sin hash)
    S_prev = S(c, 0)
    crv_prev = S_prev
    results.append(crv_prev)

    # Resto de la columna: CRV_i = formula del README
    for i in range(1, n_steps):
        T_prev = crv_prev ^ S_prev # El valor real al que se le hace el hash es el XOR del CRV anterior y el XOR de los valores de los trustees en la posicion anterior
        h = hashlib.sha256(to_bytes32(T_prev)).digest()
        H_value = int.from_bytes(h, byteorder="big")
        S_i = S(c, i) # Guardamos el valor del XOR de los valores de los trustees en la posicion i para la proxima iteracion
        crv_i = H_value ^ S_i # El valor del CRV en la posicion i es el XOR del hash que obtendría el "virtual-dealer" y el XOR de los valores de los trustees en la posicion i
        results.append(crv_i)
        crv_prev = crv_i
        S_prev = S_i

    return results


print(f"{n_columns} columnas de {n_steps} valores cada una:\n")
for c in range(n_columns):
    print(f"--- Columna {c} ---")
    for i, r in enumerate(column(c)):
        print(f"CRV_{i} = 0x{r:064x}")
    print()
