import hashlib

# Mantener en sincronia con docker-compose.yml (N_STEPS, NUM_PARTIES, N_COLS)
n_steps = 16
n_parties = 3
n_cols = 67


def val(p, c, i):
    """Mismos valores deterministas que genera scripts/entrypoint.sh:
    (party_id + 1) * 1000000 + c * 1000 + i (orden columna-mayor)."""
    return (p + 1) * 1000000 + c * 1000 + i


def S(c, i):
    """XOR de los valores de las n_parties trustees en la columna c,
    posicion i."""
    result = 0
    for p in range(n_parties):
        result ^= val(p, c, i)
    return result


def to_bytes32(value):
    return value.to_bytes(32, byteorder="big")


# Cada columna es una cadena de hash independiente. results[i][c] guarda
# CRV_{c,i} para poder imprimir en el mismo orden (paso-mayor) que el .mpc.
results = [[None] * n_cols for _ in range(n_steps)]

for c in range(n_cols):
    # Caso base: CRV_{c,0} = S_{c,0} (sin hash)
    S_prev = S(c, 0)
    crv_prev = S_prev
    results[0][c] = crv_prev

    # Resto de la columna: CRV_{c,i} = formula del README
    for i in range(1, n_steps):
        # El valor real al que se hace el hash es el XOR del CRV anterior y
        # el XOR de los valores de los trustees en la posicion anterior.
        T_prev = crv_prev ^ S_prev
        h = hashlib.sha256(to_bytes32(T_prev)).digest()
        H_value = int.from_bytes(h, byteorder="big")
        S_i = S(c, i)
        crv_i = H_value ^ S_i
        results[i][c] = crv_i
        crv_prev = crv_i
        S_prev = S_i

# Impresion en orden paso-mayor: para cada paso i, las n_cols columnas.
# Coincide linea a linea con la salida de party0 en la ejecucion MPC.
print(f"Matriz completa ({n_steps} pasos x {n_cols} columnas):\n")
for i in range(n_steps):
    for c in range(n_cols):
        print(f"CRV_{i}_col{c} = 0x{results[i][c]:064x}")
