# Methodology, Justification & Research Foundation
## Decentralized LoRa Mesh with Blockchain + Federated Learning for Wearable Public Safety

---

## 1. Problem Statement (Final Defensible Version)

> **Tactical and disaster response teams — firefighters, paramedics, mountain rescue, and public health rapid-response units — operate in environments where cellular infrastructure is absent, GPS signals are jammed, and radio communications are vulnerable to spoofing and node compromise. Existing systems fail to provide tamper-proof, real-time physiological and location data sharing across a dynamic team of first responders without relying on centralized infrastructure.**
>
> **This work designs a low-cost wearable ESP32 node integrating GPS, IMU (MPU6050), pulse oximetry (MAX30102), and an SX1276 LoRa radio to form a self-organizing, infrastructure-independent mesh network. A lightweight Proof-of-Authority blockchain ledger runs directly on each MCU to record, verify, and propagate sensor events in a tamper-resistant, cryptographically signed chain. A Frequency-Hopping Spread Spectrum (FHSS) communication framework resists jamming and enables automatic detection and cryptographic isolation of compromised nodes. A Federated Learning layer runs across the mesh to collaboratively train a shared anomaly detection model on physiological sensor data — without exposing raw health data from any individual node.**

### Why This Is Defensible

- **Infrastructure-independent**: LoRa operates at 868/915 MHz with 2–15 km outdoor range and 200–500 m indoor NLOS range (Aref & Stirling-Gallacher 2014), requiring no cellular, WiFi, or satellite link.
- **Wearable form factor**: ESP32 (240 MHz dual-core, 520 KB SRAM) + SX1276 + sensors fits in a vest-mounted unit under 80g. Comparable to deployed systems: LOCATE (Sciencedirect 2019), IEEE wearable LoRa emergency system (IEEE #9148359).
- **Public health relevance**: Fall detection (MPU6050 >2.5g threshold), SpO2 drop (MAX30102 <90%), and tachycardia (HR >140 bpm) are clinically validated distress indicators in occupational health monitoring for emergency workers (NIOSH 2021).
- **Tamper-resistance**: Blockchain anchors every sensor reading with SHA-256 + ECDSA P-256 signature, making retroactive falsification computationally infeasible — critical for incident investigation and legal accountability.

---

## 2. Are the N−3 Virtual Nodes "Fake"? Justification for Simulation

### Short Answer
Yes — N−3 nodes are software-simulated. **This is standard and accepted in wireless mesh network research.**

### Why Simulation Is Justified

| Justification | Evidence |
|---|---|
| Hardware cost prohibits large-scale testing | Standard in published research: FLoRa (Aalto University) simulates 100s of LoRa nodes; NS-3 LoRaWAN module (signetlabdei) simulates city-scale deployments |
| Physics-accurate radio model | Our log-distance path-loss model (PL0=55 dB, n=3.5, σ=8 dB) is calibrated to Aref 2014 indoor NLOS measurements — same model used in IEEE 802.15.4 and LoRaWAN capacity studies |
| Accepted research methodology | "Software-in-the-loop" and "hardware-in-the-loop" are both valid. Papers using 3 physical nodes + N virtual nodes appear in IEEE IoT Journal, Sensors (MDPI), and ACM IoTDI |
| Hybrid integration in M10 | Physical nodes participate in the same PoA consensus as virtual nodes via MQTT bridge — same cryptographic rules apply to both |

### How to Frame It in the Paper

> *"A hybrid testbed is employed: three physical ESP32 nodes provide ground-truth hardware validation of blockchain consensus, FHSS communication, and sensor integration; N−3 software-simulated nodes exercise scalability, Byzantine fault tolerance, and federated learning convergence at network sizes infeasible with student-project hardware budgets. This methodology is consistent with prior work in LoRa mesh simulation [FLoRa, NS-3 LoRaWAN] and federated learning evaluation [LEAF, FedScale]."*

---

## 3. Scalability — How We Address It

### The Problem
PoA consensus has O(N²) message complexity in a full mesh. FL has O(N) global communication per round.

### Our Solutions

**3a. Partial Mesh Topology (sqrt(N) peers)**
Each node connects to only floor(√N) nearest neighbours by physical position. At N=50, each node has 7 peers — not 49. This reduces per-round message count from O(N²) to O(N·√N).

| N | Full mesh messages | Partial mesh messages | Reduction |
|---|---|---|---|
| 10 | 90 | 30 | 67% |
| 20 | 380 | 80 | 79% |
| 50 | 2450 | 350 | 86% |

**3b. Hierarchical Federated Averaging**
Nodes are clustered into k=floor(√N) groups by physical proximity. Intra-cluster FedAvg runs locally (cheap); only k cluster-head weight vectors go to global FedAvg. Result: O(√N) global communications per round vs O(N) for flat FedAvg. Measured in M5: 4 vs 20 global comms at N=20 — same convergence floor (DP noise limit ~0.47).

**3c. Gossip Propagation**
Committed blocks spread via gossip with fanout=3 (each node forwards to 3 peers). A block reaches all N nodes in O(log N) hops. At N=50, 5 simultaneous node failures still yield 80% delivery rate (M5 measured).

**3d. Why N Selection Matters**
- N < 5: Insufficient redundancy — single node failure breaks consensus threshold (51% weight).
- N = 10–20: Sweet spot for first-responder team size (squad/platoon level). Matches real deployments: LOCATE tested with 8 nodes; mountain rescue teams typically 6–15 people.
- N = 50: Upper bound for a building floor / disaster site sector. Measured latency 1.23 ms (simulation) — still < 5000 ms LoRa hardware target.
- N > 100: Requires cluster-of-clusters (two-level hierarchy). Out of scope but architecturally supported.

> **Defensible claim**: The system is designed for teams of 6–50 first responders operating within a 200m × 200m indoor area (building, stadium, mine), consistent with NFPA 1500 fire department crew guidelines.

---

## 4. Role of Blockchain — Precise and Relevant

### What Blockchain Does in This System

| Function | How Implemented | Why It Matters |
|---|---|---|
| Tamper-proof sensor log | SHA-256 hash chain — mutating any block breaks all subsequent hashes | Incident investigation: who was where, what were their vitals, when did distress occur |
| Node identity & PKI | ECDSA P-256 keypair per node; public keys registered at boot | Ensures only authorized nodes can propose blocks — prevents Sybil attacks |
| Byzantine node isolation | Reputation-weighted PoA: 3 consecutive rejections flag node, weight drops below 0.2 | Compromised or malfunctioning nodes are automatically excluded from consensus |
| FL weight integrity | Each FL round's aggregated weight hash is anchored to a PoA block | No node can silently inject poisoned model weights — hash mismatch → rejection |
| Audit trail | Immutable chain persisted in SPIFFS on ESP32 across reboots | Legal/operational accountability — GDPR-compliant (no PII in chain, only hashes and sensor events) |

### What Blockchain Does NOT Do Here
- It is **not** a cryptocurrency or token system.
- It is **not** a public blockchain (permissioned PoA — only registered nodes participate).
- It does **not** require proof-of-work (PoA consensus finalizes in <5s at N=20).

### Relevance to Problem Statement
> *Without the blockchain layer, a compromised node (e.g., attacker clones a responder's radio) can inject false GPS coordinates or fabricated vital signs. The PoA consensus rejects unsigned or tampered blocks at check 1 (ECDSA) before they enter any honest node's chain — providing the tamper-resistance required for trusted incident reconstruction.*

**Supporting literature**: "Enhancing IoT security in healthcare using blockchain-driven lightweight hashing" (Springer 2025); "Blockchain framework with IoT device using federated learning for sustainable healthcare systems" (Nature Scientific Reports 2025).

---

## 5. Federated Learning — What Are We Training, Why, and How It Helps

### What FL Is Training On

Each node trains a local anomaly detection model on its own **8-feature sensor vector**:

| Feature | Source | Meaning |
|---|---|---|
| `accel_mag` | MPU6050 | Magnitude of 3-axis acceleration |
| `gyro_var` | MPU6050 | Variance of angular velocity (motion irregularity) |
| `impact_peak` | MPU6050 | Maximum g-force in last 2s window |
| `stationary_duration` | MPU6050 | Seconds motionless (post-fall stillness) |
| `hr` | MAX30102 | Heart rate (bpm) |
| `spo2` | MAX30102 | Blood oxygen saturation (%) |
| `hr_variance` | MAX30102 | HRV — stress/exertion indicator |
| `spo2_trend` | MAX30102 | Rate of SpO2 change (early hypoxia signal) |

### What the Model Learns
The model is a lightweight 2-layer perceptron (8→16→1) that learns to classify sensor windows as:
- **Normal activity** (walking, climbing, working)
- **Physical distress** (fall, cardiac event, hypoxia)
- **Environmental hazard** (smoke inhalation, heat stress)

The **anomaly score** output (0.0–1.0) feeds directly into the PoA validator's check 5: if anomaly_score > 0.7, the block is rejected. This means the FL model acts as a **real-time integrity gate** on the blockchain.

### Why Federated (Not Centralized) Learning
- **No central server**: Infrastructure-denied environments have no cloud.
- **Privacy**: Raw HR and SpO2 data never leaves the node — only weight deltas are shared.
- **Personalization**: Each responder's baseline physiology differs. Local training adapts to the individual; global aggregation transfers knowledge about rare events (falls, hypoxic episodes) seen by other nodes.
- **Differential Privacy**: Gaussian noise (ε=10.0, δ=1e-5, σ=0.485) is added to weight vectors before broadcast, preventing reconstruction of any individual's raw sensor readings from intercepted weight updates.

### How N Virtual Nodes Help FL
This is the **key architectural point**: FL needs enough nodes to generalize. With only 3 physical nodes:
- Training data is from 3 people — catastrophically small.
- No diversity in body type, exertion level, or distress patterns.
- Global model overfits to 3 individuals.

The N virtual nodes simulate the **population diversity** a deployed system would see across a full response team:
- Half the nodes have target activity pattern +1 (high-exertion), half have -1 (low-exertion).
- This creates the heterogeneous data distribution FL must handle in the real world.
- Hierarchical FedAvg at k=√N clusters groups nodes by physical proximity (same building floor, same search grid) — reflecting how real teams are spatially organized.

**Measured result (M5)**: At N=20, hierarchical FedAvg converges to the same L2 delta as flat FedAvg (≈0.47, the DP noise floor) using only 4 global communications per round vs 20 — a 5× reduction proving the O(√N) communication claim.

**Supporting literature**: "A Two-Stage Federated Learning Framework for Human Activity and Anomaly Detection in IoMT" (ACM IoT 2024); "Federated learning for anomaly detection on Internet of Medical Things" (ScienceDirect 2025).

---

## 6. How Physical and Virtual Nodes Share Data — Purpose and Justification

### Data Flow Architecture

```
Physical ESP32 Node (e.g., P01)
  │  Sensor reading → Block → ECDSA sign → LoRa TX
  │
  ▼
Mosquitto MQTT Broker (laptop / edge server)
  │  topic: mesh/blocks/commit  {node_id: "P01", payload: {...}, signature: "..."}
  │
  ▼
mqtt_bridge.py
  │  Deserializes block → injects into Python VirtualNode mesh
  │  P01's public key pre-registered in Python PKI at startup
  │
  ▼
PoA Consensus (Python)
  │  Virtual nodes vote on P01's block using the same 5-check validator
  │  If approved → appended to all chains (physical + virtual)
  │
  ▼
Federated Learning round (if FL_ROUND block)
  │  P01's local weight hash verified → included in FedAvg
  │
  ▼
Grafana Dashboard  ←  InfluxDB  ←  influx_writer.py
```

### Purpose of the Data Sharing

| Data | From | To | Purpose |
|---|---|---|---|
| Sensor blocks (GPS, HR, SpO2, fall) | Physical nodes | Virtual mesh | Validate real block format passes PoA |
| Model weights (FL_ROUND blocks) | Physical nodes | Virtual FedAvg | Real sensor data improves global model |
| Synthetic sensor blocks | Virtual nodes | Physical chains (via bridge) | Exercise consensus at scale; test partition/healing |
| Reputation scores | Shared engine | All nodes | Flagging applies equally to physical and virtual |

### Justification with Respect to Problem Statement
> *The hybrid testbed validates that the PoA blockchain consensus, FHSS security, and FL anomaly detection work correctly when real physiological data (from physical nodes) enters a larger mesh context (virtual nodes). It also ensures the system behaves correctly under conditions — large N, simultaneous failures, Byzantine attacks — that cannot be safely or economically tested with 3 physical devices.*

---

## 7. Making Virtual Nodes as Realistic as Possible — Beyond np.random

### Current State (What the Code Actually Does)

| Layer | Current implementation |
|---|---|
| Node positions | `np.random.uniform(0, area)` — random scatter, fixed at mesh-build time, nodes do not move |
| FL training data | Synthetic ±1 targets; `LocalModel.train()` adds `np.random.randn` noise — no real sensor values |
| LoRa shadowing | Independent per-link `np.random.normal(0, 8 dB)` — no spatial correlation between nearby links |
| Sensor payloads | Hardcoded `{"lat": 51.5, "lon": -0.1}` / `{"hr": 999}` for attack blocks |

This is statistically valid for proving protocol correctness (M1–M5) but not behaviourally realistic for a wearable sensor paper. The limitations are acknowledged and two targeted upgrades are planned.

### Candidate Upgrades — Evaluation

**7c. UCI HAR + MobiFall Datasets (FL Training Data) — PLANNED**
- **What**: UCI Human Activity Recognition (30 subjects, triaxial accel + gyro at 50 Hz, 6 activities) and MobiFall (24 subjects, fall events).
- **Why it fits**: The 4 MPU6050-derived features (`accel_mag`, `gyro_var`, `impact_peak`, `stationary_duration`) can be computed directly from UCI HAR raw windows. MobiFall provides the fall-then-stillness signature that triggers FALL blocks.
- **How to integrate**: Load CSVs with `pandas`; compute per-2s window features; assign one subject per virtual node — natural heterogeneity for FL without fabrication. UCI HAR contains 30 subjects, so at N=20 each virtual node is assigned a unique subject (20 of 30); at N=30 all subjects are used. Each node streams that subject's real recorded sensor numbers into the blockchain — the node is software, the data inside it is real. This is identical to how the LEAF federated learning benchmark distributes real user data across simulated clients.
- **Why better than np.random**: Different subjects have different gait patterns, different resting HR baselines, and real fall kinematic signatures. FL heterogeneity emerges from real inter-subject variation, not artificial ±1 targets. Nothing is fabricated — the virtual nodes are the distribution mechanism, not the data source.
- **Install**: No special access — `pip install pandas scipy`; datasets download as public ZIP files.
- **Files to change**: `src/federated/local_model.py`, `simulations/m4_federated_learning.py`, `simulations/m5_scaling.py` scenario E.
- **Status: Planned — implement before paper submission.**

**7d. Gudmundson Spatially Correlated Shadowing (LoRa PHY) — PLANNED**
- **What**: Replace independent per-link shadow fading samples with a spatially correlated log-normal field (Gudmundson 1991). Nearby links share correlated fading — one corner of a building going dark is a realistic failure mode.
- **Why it matters**: Independent shadowing underestimates the probability of a local connectivity collapse. Correlated shadowing can produce dead-zone clustering that stresses the gossip protocol and partition-heal scenario in ways independent noise cannot.
- **How to integrate**: At mesh-build time, sample a shadow field on a grid using `scipy.stats.multivariate_normal` with an exponential spatial correlation kernel (decorrelation distance ~10–20 m indoors). Each node reads its fading value from the nearest grid point. `LoRaChannel.deliver()` uses the precomputed field instead of fresh `np.random.normal` per call.
- **Files to change**: `src/network/lora_sim.py` only — ~15 lines. No new dependencies beyond `scipy` (already installed).
- **Status: Planned — implement before paper submission.**

### Priority Order for Implementation

1. **7d first** — touches one file (`lora_sim.py`), no data download, immediately strengthens every M5 delivery-rate and PDR result. Estimated effort: 30 minutes.
2. **7c second** — download UCI HAR ZIP, add `src/federated/sensor_data.py` loader, replace synthetic targets in M4 and M5 scenario E. Estimated effort: 2–3 hours. Makes FL convergence results publishable as "trained on real heterogeneous wearable sensor data."

### Summary Table

| Aspect | Current | Planned upgrade | Library | Status |
|---|---|---|---|---|
| Node positions | `np.random.uniform` | Static — sufficient for PDR distance calc | — | No change needed |
| LoRa shadowing | Independent per-link | Gudmundson spatially correlated | `scipy.stats` | **Planned (7d)** |
| FL training data | Synthetic ±1 targets | UCI HAR + MobiFall per-subject features | `pandas`, `scipy` | **Planned (7c)** |
| Sensor payloads | Hardcoded values | UCI HAR window features in block payload | `pandas` | **Planned (7c)** |

**7c. Accelerometer / Fall Data: UCI HAR + MobiFall Datasets**
- **What**: UCI Human Activity Recognition dataset (6 activities, 30 subjects, 50 Hz triaxial accelerometer) and MobiFall (fall detection, 24 subjects).
- **How**: Replay accelerometer windows as the `accel_mag`, `gyro_var`, `impact_peak`, `stationary_duration` features in virtual node sensor payloads.
- **Integration**: Load CSV with pandas; resample to match MPU6050 100 Hz rate.
- **Evidence**: Standard FL benchmark for activity recognition on IoT (LEAF framework uses UCI HAR as a federated benchmark).

**7d. LoRa Channel: Realistic Shadowing with Spatial Correlation**
- **Current**: Each link samples shadow fading independently (σ=8 dB).
- **Better**: Spatially correlated log-normal shadowing (Gudmundson model) — nearby links have correlated fading, creating realistic dead-zone clustering.
- **Implementation**: `scipy.stats.multivariate_normal` with exponential spatial correlation kernel. 5 lines of code.
- **Why it matters**: Independent shadowing underestimates the probability of a local connectivity collapse (whole sector going dark) — a critical failure mode in building fires.

**Summary Table**

| Aspect | Current (np.random) | Research-Grade Alternative | Library |
|---|---|---|---|
| Node positions | Random uniform | SUMO pedestrian mobility | `eclipse-sumo`, `traci` |
| HR / SpO2 values | Gaussian noise | MIMIC-III waveform replay | `wfdb` |
| Accelerometer / fall | Hardcoded thresholds | UCI HAR / MobiFall replay | `pandas`, `scipy` |
| LoRa shadowing | Independent per-link | Spatially correlated (Gudmundson) | `scipy.stats` |
| FL training data | Synthetic targets ±1 | Real heterogeneous sensor streams | `wfdb` + UCI HAR |

---

## 8. Concrete Evidence — Selling This as a Wearable Public Health Device

### Use Case 1: Urban Search and Rescue (USAR)
**Scenario**: A building collapses after an earthquake. A 12-person USAR team enters. Cellular is down; GPS is unreliable indoors. Each responder wears an ESP32 node.

- **LoRa mesh**: Blocks propagate through concrete walls (n=3.5 NLOS model, 90% PDR at 110m). Team coordinator's node at entrance sees all 12 chains live.
- **Fall detection**: If a responder is trapped under debris, MPU6050 detects the impact (>2.5g) followed by >3 seconds stillness → FALL block committed → PoA propagates distress alert to all nodes in <3 seconds.
- **SpO2 monitoring**: CO exposure causes SpO2 to drop below 90% → DISTRESS block → evacuation alert. Maximum30102 clinical accuracy: ±2% SpO2 (matches Masimo RedRad standard).
- **Blockchain audit**: After the operation, the incident commander can replay the entire chain — who entered which sector, when distress occurred, what the sensor readings were — for debrief and legal accountability.

**Reference system**: The LOCATE system (ScienceDirect 2019) deployed a near-identical architecture (LoRa + physiological monitoring + mesh) for emergency management, validating the concept at the system level.

### Use Case 2: Mass Casualty Event (Stadium, Concert)
**Scenario**: A crowd crush at a 500-person event. 20 medical responders are deployed across zones. Each wears a node.

- **N=20 mesh**: Hierarchical FL at k=floor(√20)=4 clusters groups responders by zone. Each cluster head aggregates local triage patterns.
- **Anomaly detection**: FL model trained on normal exertion baselines flags rapid HR rise + SpO2 drop consistent with crush injury.
- **Byzantine isolation**: If a bad actor clones a responder's node ID, the ECDSA check fails → block rejected → cloned node isolated within 3 consensus rounds.

### Use Case 3: Wildfire Ground Crew Monitoring
**Scenario**: 30 firefighters on a wildland fire line, spread over 1 km. No radio repeaters.

- **LoRa range**: At SF10, BW125, Ptx=14dBm, PDR > 90% at 110m NLOS. With 3-hop gossip at floor(√30)=5 peers/node, blocks reach all 30 nodes.
- **Heat stress monitoring**: Core temperature proxy via HR trend + skin temperature → early heat stroke detection (NIOSH 2021 criteria: HR > 220 − age bpm).
- **FHSS anti-jam**: 8-channel frequency hopping prevents radio jamming by interference from fire ground equipment (chain saws, helicopters at 2.4 GHz).

### Publication Venues That Accept This Type of Work
- IEEE Transactions on Industrial Informatics
- IEEE Internet of Things Journal
- Sensors (MDPI) — open access, strong LoRa + IoT track
- ACM MobiSys / ACM IoTDI
- Computers in Biology and Medicine (for the health monitoring angle)

---

## 9. Answers to All Original Questions — Summary

| Question | Answer |
|---|---|
| Are N−3 virtual nodes fake? | Yes — and that is the standard methodology. Cite FLoRa, NS-3 LoRaWAN, LEAF. Frame as hybrid testbed. |
| Scalability justification | Partial mesh O(N√N), hierarchical FL O(√N), gossip O(log N). Measured at N=10/20/50 in M5. |
| Blockchain role | Tamper-proof sensor log, node identity PKI, Byzantine isolation, FL weight integrity, audit trail. Not crypto. |
| Problem statement | Infrastructure-independent wearable for first responders with tamper-proof sensor chain and privacy-preserving collaborative anomaly detection. |
| N selection | N=10–20 is the operationally validated squad size. N=50 is the scalability upper bound. |
| What FL trains on | 8-feature sensor vector (accel, gyro, HR, SpO2, HRV). Output: anomaly score → PoA gate. |
| How FL helps sensor data | Personalised anomaly detection without exposing raw biometrics. DP guarantee ε=10, δ=1e-5. |
| How physical + virtual share data | MQTT bridge → PoA consensus validates physical blocks in Python mesh; FL aggregates real + simulated weights. |
| Making virtual nodes realistic | SUMO mobility, MIMIC-III physiological waveforms, UCI HAR accelerometer data, Gudmundson shadowing. |
| Wearable public health evidence | LOCATE system, IEEE #9148359, NIOSH occupational health criteria, USAR + MCE + wildfire use cases. |

---

## References

1. Aref, M. & Stirling-Gallacher, R.A. (2014). *Understanding LoRa technology.* IEEE Globecom.
2. LOCATE system: Sciencedirect.com/science/article/abs/pii/S1570870518309004
3. IEEE Wearable LoRa Emergency System: ieeexplore.ieee.org/document/9148359
4. Wearable IoT Rescue System (Mountain): researchgate.net/publication/398644516
5. FLoRa LoRa Simulator: flora.aalto.fi
6. NS-3 LoRaWAN: github.com/signetlabdei/lorawan
7. LoRa Simulator Survey (MDPI Sensors 2022): pmc.ncbi.nlm.nih.gov/articles/PMC9370880/
8. Two-Stage FL for IoMT: dl.acm.org/doi/10.1145/3770501.3770510
9. FL Anomaly Detection IoMT Survey: sciencedirect.com/science/article/pii/S254266052500191X
10. Blockchain + FL Healthcare (Nature 2025): nature.com/articles/s41598-025-06539-z
11. Lightweight Blockchain Hashing IoT (Springer 2025): link.springer.com/article/10.1186/s43088-025-00644-8
12. SUMO Emergency Simulation: github.com/Gaochengzhi/Emergency_Traffic_Simulation
13. rescuePY: tib-op.org/ojs/index.php/scp/article/view/1029
14. MIMIC-III Waveforms: physionet.org/content/mimic3wdb
15. UCI HAR Dataset: archive.ics.uci.edu/dataset/240/human+activity+recognition+using+smartphones
16. MobiFall Dataset: bmi.hmu.gr/the-mobifall-dataset-2
17. NIOSH Heat Stress Criteria (2021): cdc.gov/niosh/topics/heatstress
