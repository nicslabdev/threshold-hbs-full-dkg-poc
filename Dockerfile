FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

RUN apt-get update && apt-get install -y \
    automake build-essential clang cmake git \
    libboost-dev libboost-filesystem-dev libboost-iostreams-dev libboost-thread-dev \
    libgmp-dev libntl-dev \
    libsodium-dev libssl-dev libtool \
    python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /mpspdz

RUN git clone --depth 1 https://github.com/data61/MP-SPDZ.git .

RUN make setup

RUN make -j"$(nproc)" semi-bin-party.x

# Fetch the circuits submodule at build time: otherwise compile.py
# clones it over the network in every container at startup, which adds
# variable network latency right before the parties connect to each
# other and can cause connection timeouts between them.
RUN git submodule update --init Programs/Circuits || git clone --depth 1 https://github.com/mkskeller/bristol-fashion Programs/Circuits

COPY programs/sha256_full_column.mpc ./Programs/Source/sha256_full_column.mpc
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
