import hashlib

n_steps = 16
n_parties = 3

# Mismos valores deterministas que genera scripts/entrypoint.sh:
# (party_id + 1) * 1000 + i
values = [[(p + 1) * 1000 + i for i in range(n_steps)] for p in range(n_parties)]


def S(i):
    """XOR de los valores de las n_parties trustees en la posicion i."""
    result = 0
    for p in range(n_parties):
        result ^= values[p][i]
    return result


def to_bytes32(value):
    return value.to_bytes(32, byteorder="big")


results = []

# Caso base: CRV_0 = S_0 (sin hash)
S_prev = S(0)
crv_prev = S_prev
results.append(crv_prev)

# Resto de la columna: CRV_i = formula del README
for i in range(1, n_steps):
    T_prev = crv_prev ^ S_prev # El valor real al que se le hace el hash es el XOR del CRV anterior y el XOR de los valores de los trustees en la posicion anterior
    h = hashlib.sha256(to_bytes32(T_prev)).digest()
    H_value = int.from_bytes(h, byteorder="big")
    S_i = S(i) # Guardamos el valor del XOR de los valores de los trustees en la posicion i para la proxima iteracion
    crv_i = H_value ^ S_i # El valor del CRV en la posicion i es el XOR del hash que obtendría el "virtual-dealer" y el XOR de los valores de los trustees en la posicion i
    results.append(crv_i)
    crv_prev = crv_i
    S_prev = S_i

print(f"Columna completa ({n_steps} valores):\n")
for i, r in enumerate(results):
    print(f"CRV_{i} = 0x{r:064x}")
