# Decentralized LoRa Mesh — Blockchain + TinyML + Federated Learning

A research-grade simulation and firmware implementation of a decentralized peer-to-peer mesh network for first-responder health monitoring. The system combines blockchain integrity, Proof-of-Authority consensus, Byzantine fault tolerance, differentially private federated learning, and (in later phases) real LoRa radio on ESP32 hardware.

---

## Milestone Map

| # | Milestone | Runs On | Status |
|---|---|---|---|
| M1 | Python blockchain core | PC | Done |
| M2 | PoA consensus — 2 virtual nodes | PC | Done |
| M3 | Byzantine fault tolerance | PC | Done |
| M4 | Federated learning simulation | PC | Done |
| M5 | N-node scaling + research metrics | PC | Done |
| M6 | Blockchain firmware on ESP32 | 1x ESP32 | Pending |
| M7 | LoRa P2P block transmission | 2x ESP32 | Pending |
| M8 | Sensor integration (MPU6050 + MAX30102) | 3x ESP32 | Pending |
| M9 | TinyML on-device inference | 3x ESP32 | Pending |
| M10 | Hybrid physical + virtual mesh | 3x ESP32 + PC | Pending |
| M11 | Full demo | All hardware | Pending |

---

## Novel Research Contributions

| Contribution | Module | Research Claim |
|---|---|---|
| Reputation-Weighted PoA | `src/consensus/reputation.py` | Sybil resistance; Byzantine exclusion in <= 3 blocks |
| Simulated LoRa PHY | `src/network/lora_sim.py` | Log-distance path-loss PDR model; results match empirical LoRa range data |
| (epsilon, delta)-DP Federated Learning | `src/federated/dp_noise.py` | Provable privacy on weight broadcasts; no raw sensor data shared |
| Hierarchical FedAvg | `src/federated/hierarchical.py` | O(sqrt(N)) global communication vs O(N) flat FedAvg |

---

## Project Structure

```
c:\IDP\
|-- .venv\                         Python 3.10 virtual environment
|-- src\
|   |-- blockchain\
|   |   |-- block.py               Block dataclass, SHA-256, ECDSA sign/verify
|   |   |-- chain.py               Chain: append, validate, Merkle sync
|   |   |-- crypto.py              ECDSA P-256 keygen, sign, verify
|   |   `-- merkle.py              Merkle tree for O(log K) chain sync
|   |-- consensus\
|   |   |-- validator.py           5-check validation pipeline
|   |   |-- poa.py                 PoA round coordinator (propose->vote->commit)
|   |   `-- reputation.py          Reputation engine [NOVEL]
|   |-- network\
|   |   |-- node.py                VirtualNode class
|   |   |-- mesh.py                Partial-mesh topology builder
|   |   |-- gossip.py              Gossip with seen-set deduplication
|   |   `-- lora_sim.py            LoRa PHY: path loss, RSSI, PDR [NOVEL]
|   |-- federated\
|   |   |-- local_model.py         Float-array model + simulated gradient step
|   |   |-- fedavg.py              Standard FedAvg
|   |   |-- dp_noise.py            (epsilon,delta)-DP Gaussian mechanism [NOVEL]
|   |   `-- hierarchical.py        Two-tier clustered FedAvg [NOVEL]
|   |-- byzantine\
|   |   `-- attacker.py            6 tamper scenarios
|   `-- metrics\
|       |-- collector.py           MetricsCollector dataclass
|       `-- visualize.py           Matplotlib plots + CSV export
|-- bridge\
|   |-- mqtt_bridge.py             MQTT <-> simulation bridge (used from M10)
|   `-- influx_writer.py           Writes all events to InfluxDB
|-- firmware\                      ESP32 C++ source (PlatformIO, used from M6)
|   |-- platformio.ini
|   |-- include\
|   |   |-- Block.h
|   |   |-- Chain.h
|   |   |-- Crypto.h
|   |   |-- PoA.h
|   |   |-- LoRaMesh.h
|   |   |-- SensorReader.h
|   |   `-- TinyMLInfer.h
|   `-- src\
|       `-- main.cpp
|-- simulations\
|   |-- m1_blockchain_core.py      [DONE]
|   |-- m2_poa_2nodes.py           [DONE]
|   |-- m3_byzantine_faults.py           [DONE]
|   |-- m4_federated_learning.py           [DONE]
|   `-- m5_scaling.py              [DONE]
|-- tests\
|   |-- test_blockchain.py
|   |-- test_consensus.py
|   |-- test_byzantine.py
|   `-- test_federated.py
|-- grafana\                       Grafana + InfluxDB + Mosquitto dashboard stack
|   |-- docker-compose.yml
|   `-- provisioning\
|-- results\                       CSV outputs + PNG plots
`-- requirements.txt
```

---

## Quick Start

```bash
# 1. Activate environment
.venv\Scripts\activate

# 2. Run simulations in order
python simulations/m1_blockchain_core.py
python simulations/m2_poa_2nodes.py
python simulations/m3_byzantine_faults.py
python simulations/m4_federated_learning.py
python simulations/m5_scaling.py

# 3. Run tests
pytest tests/ -v

# 4. Launch dashboard (requires Docker)
cd grafana && docker compose up -d
# open http://localhost:3000
```

---

## Milestone Details

### M1 — Python Blockchain Core (PC)

Single virtual node creates blocks, hashes them with SHA-256, signs with ECDSA P-256, stores in memory, and validates the full chain. Merkle tree computed over all block hashes.

**Prove it works:**
- 10 blocks created and chain validates
- Tamper any field in any block -> chain reports INVALID at that index
- Restore -> chain reports VALID again

**Run:** `python simulations/m1_blockchain_core.py`

---

### M2 — PoA Consensus — 2 Virtual Nodes (PC)

Two virtual nodes propose blocks to each other and vote. A block only enters both chains when both nodes approve. Reputation engine weights votes.

**Validator 5-check pipeline (in order):**
1. ECDSA signature verification
2. Hash integrity check
3. Previous hash linkage
4. Frame counter replay check
5. Anomaly score threshold (> 0.7 rejected)

**Prove it works:**
- Valid block from Node 1 enters both chains
- Block with wrong prev_hash rejected before entering any chain
- Both chain tips identical after every committed block

**Run:** `python simulations/m2_poa_2nodes.py`

---

### M3 — Byzantine Fault Tolerance (PC)

A compromised node attempts 6 different attacks. All are rejected by the honest mesh. Byzantine node is automatically flagged after 3 consecutive failures.

**Attack scenarios:**

| Scenario | What is mutated | Rejected by check |
|---|---|---|
| Invalid signature | Wrong private key | Check 1 |
| Tampered payload | Mutate after signing | Checks 1+2 |
| Impossible values | HR=999, SpO2=150 | Check 5 |
| GPS teleport | Jump 50 km | Check 5 |
| Replay attack | Rebroadcast old block | Check 4 |
| Counter manipulation | Decrement frame counter | Check 4 |

**Run:** `python simulations/m3_byzantine_faults.py`

---

### M4 — Federated Learning Simulation (PC)

Nodes share model weight updates over the mesh. Weight sharing is verified by SHA-256 hash before averaging. Each FL round is logged as a blockchain block through full PoA consensus. Differential privacy noise added before broadcast.

**Privacy guarantee:** Gaussian mechanism, epsilon=1.0, delta=1e-5.

**Prove it works:**
- Two nodes start with different weights; converge after 5 FL rounds
- Tampered weights rejected by hash verification
- Each FL round appears as a verified block in both chains

**Run:** `python simulations/m4_federated_learning.py`

---

### M5 — N-Node Scaling (PC)

Scale to 10, 20, 50 virtual nodes with realistic LoRa PHY packet delivery. Gossip protocol propagates blocks. Metrics exported as CSV for research paper.

**LoRa PHY model (log-distance path loss):**
```
PL(d) = 40 + 10 * 2.7 * log10(d) + shadow_fading
RSSI  = 14 - PL(d)   [dBm]
PDR   = sigmoid((RSSI - (-131)) / 4)
```

**Simulation scenarios:**
- 10 nodes, 1 Byzantine
- 20 nodes, 3 Byzantine
- 50 nodes, 5 simultaneous failures
- 20 nodes, network partition -> heal -> chain sync
- 20 nodes, hierarchical FL vs flat FL convergence comparison

**Outputs:** `results/metrics_N{n}_B{b}.csv` + 5 PNG plots

**Run:** `python simulations/m5_scaling.py`

---

### M6–M11 — ESP32 Hardware Phases (requires boards)

| Milestone | Hardware | Key capability added |
|---|---|---|
| M6 | 1x ESP32 | Blockchain in C++, SPIFFS storage, ECDSA via mbedTLS |
| M7 | 2x ESP32 | LoRa P2P with AES-128 encryption + FHSS |
| M8 | 3x ESP32 + MPU6050 + MAX30102 | Real sensors: fall detection, HR, SpO2, GPS distress |
| M9 | Same + Edge Impulse | TinyML inference < 10ms; anomaly score feeds PoA gate |
| M10 | 3x ESP32 + PC | Hybrid mesh: ESP32 + Python via MQTT; Grafana dashboard live |
| M11 | All | Full 5-minute reproducible demo |

**Firmware toolchain:** PlatformIO + Arduino framework + mbedTLS + LoRa (Sandeep Mistry)

---

### Dashboard — Grafana + InfluxDB + MQTT (PC, used from M10)

```
ESP32 Node 1 -+
ESP32 Node 2 -+-- WiFi --> Mosquitto MQTT Broker
ESP32 Node 3 -+                    |
                                   +-- mqtt_bridge.py --> InfluxDB --> Grafana
Python VirtualNodes (N) -----------+
```

**MQTT topics:**
```
mesh/blocks/propose    any node proposes a block
mesh/blocks/vote       any node casts a vote
mesh/blocks/commit     committed block broadcast
mesh/heartbeat         node presence + position
mesh/fl/weights        FL weight broadcast with hash
mesh/alert             FALL / DISTRESS / BYZANTINE events
mesh/sensor/{node_id}  raw sensor telemetry (ESP32 only)
```

**Grafana panels:** Live mesh topology, per-node chain explorer, consensus latency, sensor telemetry, alert feed, reputation scores, FL convergence, Byzantine rejection log.

---

## Research Paper Metrics

| Metric | Source | Target |
|---|---|---|
| Consensus latency vs N | m5_scaling.py | < 5s at N=20 |
| Block delivery rate | m5_scaling.py gossip | > 95% at N=20 |
| Byzantine rejection rate | m3_byzantine_faults.py | 100% for sig/hash attacks |
| FL convergence rounds | m4_federated_learning.py | < 10 rounds |
| Reputation flagging speed | m3 + reputation.py | <= 3 invalid blocks |
| DP privacy budget | dp_noise.py | epsilon=1.0, delta=1e-5 |
| Hierarchical vs flat FL | m5 scenario E | O(sqrt(N)) reduction confirmed |
| LoRa PDR at 50m / 200m | lora_sim.py | ~98% / ~72% |
| Chain sync (10 missed blocks) | m5 partition scenario | < 30s |
| ESP32 inference latency | Serial monitor (M9) | < 10ms |

---

## Python to ESP32 Migration Guide

Every Python module has a direct C++ equivalent in `firmware/include/`. The logic is identical — only the language, crypto library, and storage API change.

### Toolchain Setup

```bash
# Install PlatformIO CLI
pip install platformio

# Or use the PlatformIO VSCode extension (recommended)
# Create project
pio project init --board esp32dev --ide vscode
```

### Module-by-Module Mapping

| Python module | C++ equivalent | Migration notes |
|---|---|---|
| `src/blockchain/crypto.py` | `Crypto.h` | Replace `cryptography` lib with `mbedtls_pk`, `mbedtls_ecdsa`, `mbedtls_sha256`. Same P-256 curve. Keypair stored in SPIFFS on first boot. |
| `src/blockchain/block.py` | `Block.h` | Port `Block` dataclass to C++ struct. `compute_hash()` uses `mbedtls_sha256`. JSON serialization via ArduinoJson v7. |
| `src/blockchain/chain.py` | `Chain.h` | `validate()` logic is identical. Storage: each block written as `/chain/blk_{index}.json` in SPIFFS. `tip_hash()` and `last_frame_counter()` are direct ports. |
| `src/blockchain/merkle.py` | `Merkle.h` | Pure SHA-256 tree — direct port. No external library needed. Used for chain sync over LoRa. |
| `src/consensus/validator.py` | `PoA.h` (validate section) | All 5 checks port 1-to-1. `anomaly_score` comes from TinyML inference output instead of a Python float. |
| `src/consensus/reputation.py` | `PoA.h` (reputation section) | Scores stored as `float scores[MAX_NODES]`. `reward()`, `penalize()`, `is_flagged()` are identical logic. |
| `src/consensus/poa.py` | `PoA.h` (coordinator section) | `propose()` sends block over LoRa instead of calling peers directly. Collect votes within `VOTE_TIMEOUT_MS`. Weighted threshold identical. |
| `src/network/node.py` | `main.cpp` | Node identity (ID + keypair) set at flash time. `create_block()` and `receive_proposal()` map directly to C++ functions. |
| `src/network/gossip.py` | `LoRaMesh.h` | `seen_set` becomes a circular buffer of last 32 block hashes. Fanout over LoRa instead of function calls. |
| `src/federated/local_model.py` | `TinyMLInfer.h` | Float array replaced by Edge Impulse exported model weights. Gradient step replaced by on-device inference output. |
| `src/federated/fedavg.py` | `TinyMLInfer.h` | `np.mean()` replaced by element-wise float averaging. Same FedAvg formula. |

### Key Library Replacements

| Python | C++ / PlatformIO |
|---|---|
| `cryptography` (ECDSA, SHA-256) | `mbedTLS` (bundled with ESP-IDF, available in Arduino framework) |
| `json.dumps()` | `ArduinoJson` v7 — `serializeJson(doc, buffer)` |
| File I/O (`open`, `write`) | `SPIFFS.open()`, `file.write()` |
| `time.time()` | `millis()` / `esp_timer_get_time()` |
| `numpy` arrays | Plain `float[]` arrays |
| `paho-mqtt` | `PubSubClient` library |
| `hashlib.sha256` | `mbedtls_sha256()` |

### What Does NOT Change

- Block field names and structure
- SHA-256 hash computation logic (same input, same output)
- The 5-check validator order and rejection reasons
- PoA weighted threshold formula (0.51)
- FedAvg averaging formula
- Reputation reward/penalty values
- MQTT topic schema (bridge connects both sides)

### Firmware platformio.ini

```ini
[env:esp32dev]
platform = espressif32
board = esp32dev
framework = arduino
monitor_speed = 115200
lib_deps =
  sandeepmistry/LoRa@^0.8.0
  adafruit/Adafruit MPU6050@^2.2.6
  sparkfun/SparkFun MAX3010x Pulse and Proximity@^1.1.2
  bblanchon/ArduinoJson@^7.0.4
  knolleary/PubSubClient@^2.8
```

### Migration Order (M6 onwards)

```
Step 1  Crypto.h   — keygen + sign + verify (test on Serial monitor)
Step 2  Block.h    — struct + compute_hash + sign_block
Step 3  Chain.h    — append + validate + SPIFFS persistence
Step 4  Merkle.h   — Merkle tree (copy from Python logic)
Step 5  PoA.h      — validator + reputation + coordinator
Step 6  LoRaMesh.h — AES-128 encrypt + FHSS + send/receive
Step 7  main.cpp   — wire everything together, hardcoded sensor values
Step 8  SensorReader.h  — MPU6050 + MAX30102 (M8)
Step 9  TinyMLInfer.h   — Edge Impulse library (M9)
Step 10 WiFi + PubSubClient MQTT — bridge to Python mesh (M10)
```

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| cryptography | >= 42.0 | ECDSA P-256, SHA-256 |
| numpy | >= 1.26 | Weight arrays, DP noise |
| matplotlib | >= 3.8 | Research plots |
| networkx | >= 3.2 | Mesh topology visualization |
| pandas | >= 2.1 | Metrics CSV export |
| scipy | >= 1.12 | Statistical utilities |
| paho-mqtt | >= 2.0 | Bridge to ESP32 nodes |
| influxdb-client | >= 1.40 | Time-series storage for dashboard |
| pytest | >= 8.0 | Unit testing |
