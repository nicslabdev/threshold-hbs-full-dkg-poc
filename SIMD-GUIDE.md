---
This guide describes the `simd` execution mode of `sha256_full_column.mpc`
(`MODE=simd` in `docker-compose.yml` / `entrypoint.sh`). See the main
[`README.md`](README.md) for the `sequential` mode and how to select
between the two.

0. The mental model first (what "SIMD" means here)

Forget MPC for a second. Think of the SHA-256 circuit as a physical machine made of wires and logic gates (AND, XOR, NOT). Normally each wire carries one bit. To hash one 256-bit message you feed 256 bits in, the gates fire, and 256 output bits come out.

The SIMD trick — called bit-slicing or packing — is this: instead of each wire carrying one bit, make each wire carry a stack of N_COLS bits, one per column. When an AND gate fires, it ANDs the two entire stacks together elementwise. So a single pass through the circuit computes N_COLS independent hashes at once, because every gate does the work for all columns simultaneously.

Normal:                          SIMD-packed (N_COLS=4):
  wire 0 ── [1]                    wire 0 ── [1,0,1,1]   ← col0,col1,col2,col3
  wire 1 ── [0]                    wire 1 ── [0,0,1,0]
  ...                              ...
  wire 255 ── [1]                  wire 255 ── [1,1,0,1]

The number of stacked values is called the SIMD width (or numbcolumn c. The whole point of the design is: the columns of theCRV matrix are independent hash chains, so they're perfect candidates to become lanes.

Now let's see how the code actually sets this up, end to end.


1. Input generation — scripts/entrypoint.sh

Each party must supply one secret share per matrix cell. For N_COLS=4, N_STEPS=16 that's 4 × 16 = 64 secret values per party.

The file is written in column-major order (all of column 0's steps, then all of column 1's, …):

# scripts/entrypoint.sh:27-33
{
  for ((c=0; c<N_COLS; c++)); do
    for ((i=0; i<N_STEPS; i++)); do
      echo $(( (PARTY_ID + 1) * 1000000 + c * 1000 + i ))
    done
  done
} > "Player-Data/Input-P${PARTY_ID}-0"

For party 0 the file data/party0/Input-P0-0 looks like:

1000000   ← col 0, step 0   (1*1_000_000 + 0*1000 + 0)
← col 1, step 1
...
1003015   ← col 3, step 15   (64 lines total)

The encoding (party+1)*1e6 + col*1e3 + step is just a deterministic, human-readable test value so the Python verifier can reproduce it. Party 1's file starts at 2000000, party 2's at 3000000. These are the SK_j^{c,i} secret shares.

Why column-major matters: the .mpc program reads the file sequentially, and it reads it in the same nesting order (column outer, step inner). If the two orders disagreed, every value would land in the wrong matrix cell. Keep this in mind for the next step.

---
2. Reading the inputs inside MPC — sha256_full_column.mpc

# programs/sha256_full_column.mpc:41
T = sbits.get_type(n_bytes * 8)   # T = a 256-bit secret type

# lines 68-69
shares = [[[T.get_input_from(p) for _ in range(n_steps)]
           for _ in range(n_cols)] for p in range(n_parties)]

T = sbits.get_type(256) defines the type "a secret-shared 256-bit value." T.get_input_from(p) reads one value from party p's input file and returns it as
a secret. Crucially, get_input_from consumes the file sequentixt line.er).

---
3. Combining shares — the S function

# lines 71-77
def S(c, i):
    result = shares[0][c][i]
    for p in range(1, n_parties):
        result = result ^ shares[p][c][i]
    return result

S(c, i) = XOR of all parties' shares at cell (c, i). This is the joint secret S_{c,i} from the README formula. XOR of secret-shared bits is a local operation in MPC — no communication between parties. S(c,i) is still a single 256-bit secret, width 1.

---
-85
S_prev = [S(c, 0) for c in range(n_cols)]      # 4 secret values (one per column)
crv_prev = sbitvec(S_prev).reveal()            # ONE open reveals all 4 columns
for cv in crv_prev:
    cv.print_reg()

CRV_{c,0} = S_{c,0} (base case, no hash). The interesting line is sbitvec(S_prev).reveal().

S_prev is a Python list of 4 secret values. Passing that list to sbitvec(...) stacks them into 4 SIMD lanes (this is the same packing operation we'll use for the hash — I'll dissect it in §6). .reveal() then opens all 4 lanes in a single communication round, returning a Python list of 4 public values. So all 4 columns of row 0 are revealed with one network exchange, not four.

This is the recurring theme: columns are handled together per step, never one at a time.

---
5. Converting a value into SHA-256's message bits — to_message

Before packing, understand what the SHA circuit wants as input. This function handles the byte-endianness the Bristol SHA-256 circuit expects:

# lines 43-53
def to_message_bits(value):
    all_bits = value.bit_decompose(n_bytes * 8)   # 256 individual secret bits
    message_bits = []
    for i in range(n_bytes):                        # for each of 32 bytes
        chunk_index = n_bytes - 1 - i               # reverse byte order
        chunk = all_bits[8 * chunk_index : 8 * chunk_index + 8]
        message_bits += list(reversed(chunk))       # reverse
    return sbitvec.from_vec(message_bits)

Key point for our purposes: value.bit_decompose(256) turns onelist of 256 single-bit secret registers. The rest just reorders those 256 bits for endianness. sbitvec.from_vec(message_bits) wraps them back into an sbitvec.

So to_message_bits(v) returns an sbitvec whose internal bit list .v has length 256, and each of those 256 entries is a width-1 register (one lane). Think of it as a column vector of 256 bits for one input.

---
6. The packing — to_message_bits_batched (the heart of it)

# lines 56-61
def to_message_bits_batched(values):
    return sbitvec([to_message_bits(v) for v in values])

values is the list of 4 secret column-values [T_0, T_1, T_2, T_3]. The inner comprehension produces 4 sbitvecs, each a 256-bit message (width 1). Then —
this is the crucial line — we pass that list of 4 sbitvecs to
and sbitvec a list of sbitvec rows, it transposes them into the SIMD dimension. The result is a single sbitvec where:

- .v still has length 256 (still logically a 256-bit message), but
- each of those 256 entries is now a width-4 register: entry k, lane c holds column c's k-th message bit.

Picture it as a 256 × 4 grid:

              lane0   lane1   lane2   lane3
              (col0)  (col1)  (col2)  (col3)
  bit 0    [   b0,0    b0,1    b0,2    b0,3  ]   ← one width-4 register
  bit 1    [   b1,0    b1,1    b1,2    b1,3  ]
  ...
  bit 255  [ b255,0  b255,1  b255,2  b255,3 ]

Each row of this grid is one wire of the circuit, now carrying a 4-bit stack. This is precisely the "stack per wire" picture from §0. The SIMD width is N_COLS = the number of rows you passed in. Nothing about the circuit changed — we just widened every wire.

D call to SHA-256

# line 94
H = sha256(to_message_bits_batched(T_prev)).elements()

sha256(...) evaluates the SHA-256 Bristol circuit exactly once. But because every input wire is 4 lanes wide, every AND/XOR gate operates on 4-lane registers, and the circuit emits 4 hashes in one pass. This is the whole payoff:

- Bytecode is emitted once per step, not once per column. Adding columns widens registers; it does not add more circuit instances or more communication rounds.
- .elements() unpacks the width-4 SIMD result back into a Python list of 4 separate values: H[0]…H[3], where H[c] is column c's hash. These are back to
width-1 individual values.

Concrete evidence from your own run log: the compiler reported

16384 bit inputs from player 0

That's exactly 4 cols × 16 steps × 256 bits = 16384. The inputs scale with the number of columns (more data), but the round count (24122 virtual machine rounds) is driven by the 16 sequential steps, not by 4 × 16 — because within each step all columns collapse into that single sha256() call.

---
8. Blinding and the batched reveal per step

# lines 88-103                                                                                                                                            for i in range(1, n_steps):
    # local ops only (no communication):
    T_prev = [T.conv(crv_prev[c]) ^ S_prev[c] for c in range(n_cols)]   # reconstruct secret T_{c,i-1}

    H = sha256(to_message_bits_batched(T_prev)).elements()             # ONE SIMD hash                                                                    

1. T_prev — reconstruct the real chain value T_{c,i-1} = CRV_{c,i-1} ⊕ S_{c,i-1}. crv_prev[c] is the public CRV from the previous step; T.conv(...) lifts it back into the secret domain; XOR-ing with the secret S_prev[c] yields a secret T. This is where the "no dealer" property lives: T is the value a trusted dealer would have hashed, but here it only ever exists as a secret share — never revealed. All local ops, zero communication.
2. sha256(...) — the single packed hash from §7, giving H[c] for each column.
3. Blind + reveal — XOR each hash with the fresh secret S_{c,i}, re-stack the 4 results into 4 lanes with sbitvec([...]), and .reveal() opens all 4 columns in one round. The blinding is what makes it safe to reveal: H(T) ⊕ S_i looks uniformly random, so the reveal leaks nothing about T or the shares.

So per step we pay one SIMD hash + one batched open, regardless of how many columns. The sequential dependency is only along the 16 steps (each needs the previous CRV). That's why wall-clock ≈ a single column, whileff line-by-line against the MPC output.

---
The one-paragraph summary

Each party writes N_COLS × N_STEPS secret shares in column-major order (entrypoint.sh); the program reads them into shares[p][c][i] in the matching order (.mpc:68). The columns are independent hash chains, so they become SIMD lanes: to_message_bits_batched (.mpc:56) stacks the N_COLS per-column 256-bit messages into an sbitvec where every one of the 256 message-bit positions is a register N_COLS lanes wide. A single sha256() call then evaluates the circuit once but hashes all columns simultaneously (.mpc:94), and a single batched .reveal() opens all columns per step (.mpc:98). The only sequential axis is the N_STEPS chain steps — adding columns just widens tn rounds and wall-clock stay ≈ a single column while throughput scales with N_COLS.
