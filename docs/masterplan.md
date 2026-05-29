# <h2><p align="center">**ALEA:**  ***A Crypto-Native Entropy***</p></h2>

### The Background: 
*Entropy* is one of the foundational resources of modern Cryptography in which all security architecture rests. By design, computers are deterministic, they excel at predictability but are incapable of generating true randomness on their own.

To bridge this gap, the industry evolved to aggregate environmental unpredictability as entropy source. From *Hardware True Random Number Generators (TRNGs)* to *Cloudflare's Lava Lamps*, analog noise has always been the industry standard when it comes to seeding entropy. Institutional frameworks like the *NIST Randomness Beacon*, *Drand*, and the *League of Entropy* scaled their services into a globally accessible networks.

But despite the mathematical quality of the entropy these services provide, from my vantage point, they suffer from two critical weaknesses:
1. **Trust Deficit:** These entropy providers require absolute, unvetted trust. A user pulling a seed from an external beacon cannot easily verify if that data matches the raw physical source (e.g, light data obtained from lava lamps). The consumer must trust that a provider is not manipulating the calculation, front-running outputs, or serving a targeted stream to a specific user.

2. **API Hijacking Vulnerabilities:** Standard web API endpoints can be considered as an architectural weak link. Even if the entropy generation is trustworthy, the transport layer remains exposed to DNS spoofing, man-in-the-middle (MitM) attacks, and API endpoint hijacking. If the delivery pipeline is compromised, the cryptographic integrity of the application simply collapses.

**Alea** was conceptualized to solve this trust-and-delivery concerns entirely by leveraging public, decentralized blockchains as live, immutable entropy aggregates.

Instead of trusting a centralized intermediaries (e.g., *Infura*, *Alchemy*) or a single entity (e.g., *Drand*, *NIST*), Alea treats the global consensus data of secure blockchains as continuously updated, ungrindable source of raw entropy. By fetching the data directly through a local light node and executing cryptographic computation directly on the host machine, it introduces an entry point for entropy that is completely ***verifiable***, inherently ***trustless***, and entirely ***API-less***.

# <h4><p align="center">This document serves as a compiled technical blueprint for **Alea**:<br>an *API-less*, *trustless*, purely *crypto-based* Verifiable Randomness Program.</p></h4>

---

As a quick background, **BASE** and **Ethereum** was chosen to be an aggregate because *Helios Light Client* is relatively stable, light, and easy to integrate. The same goes with **BTC** via a local *Simplified Payment Verification (SPV) client* connecting directly to the P2P network.

The program was originally planned to be a single sub-second entropy generator, but a vulnerability concept in cryptography called the *"Last Actor Problem"* made me rethink of my approach. This, from my vantage point, is a limitation of solely taking blockchain aggregates for entropy generation.

## 1. The 3 Entropy Modes
Blockchains face a strict trilemma between speed and security (The Last Actor Problem). Alea solves this by abstracting blockchain parameters into three runtime modes matching the host risk tolerance and generation frequency requirements.

|                  | OPTIMISTIC                            | ATTESTED           | PROOF                        |
|:-----------------|:--------------------------------------|:-------------------|:-----------------------------|
| Consensus Source | Base Network (Optimism Stack Layer 2) | Ethereum Mainnet   | Bitcoin Mainnet Block Header |
| Latency          | 2 Seconds (fixed)                     | 12 Seconds (fixed) | ~10 Minutes average          |

### MODE A: Optimistic
- **Consensus Source:**
    > Base Network (Optimism Stack Layer 2)
- **Fixed Latency:**
    > 2 Seconds
- **Mechanism:**
    > Fetched via the local Helios Light Client
- **Optional Sub-Second Temporal Salting:**
    > For applications requiring sub-second pulses between the 2-second blocks, users can optionally salt the block hash with the local host’s exact millisecond timestamp.

    - Security Tradeoff: Introducing the local clock opens a Grinding Attack Vector. A malicious host could iterate hashes within a 2-second window to pick a favorable outcome, downgrading the crypto-native guarantee to a "Provably Honest Server" model.

### MODE B: Attested
- **Consensus Source:**
    > Ethereum Mainnet

- **Fixed Latency:**
    > 12 Seconds (Aligned with Ethereum Slot consensus cycle)

- **Mechanism:**
    > Uses the mixHash from the RANDAO beacon, fetched via Helios.

- **Threat Model Mitigation:**
    > Protected by the Ethereum PoS. A rogue validator must drop their block, forfeiting thousands of dollars in block rewards and MEV, to manipulate the feed.

### MODE C: Proof
- Consensus Source:
    > Bitcoin Mainnet Block Header.

- Latency Profile:
    > ~10 Minutes average (Poisson Distribution)

- Mechanism & Mitigation:
    > Fetched via a local Simplified Payment Verification (SPV) client connecting directly to the BTC P2P network. To negate human coordination and "Spoiler Problems," selection runs completely independent of UTC time. Registrations close at a designated Block $X$. The winning seed is bound explicitly to the header of a future target block ($X + N$), forcing a malicious miner to forfeit ~$200,000+ in rewards to alter the draw.

## 2. Configuration Options
To support multi-instance deployment and low latency use-cases, Alea provides advanced runtime configurations. Both options utilize Alea's strict canonicalization format (`0x7C` delimiter) to prevent boundary collision attacks.

### A. Domain Separation
By default, if two distinct applications (e.g., a roulette wheel and an RPG loot drop) request entropy from Alea at the exact same moment for the same Mode, they will receive the exact same blockchain hash. This breaks randomness isolation, as the outcome of Application A perfectly predicts the outcome of Application B.

To solve this, Alea can optionally be configured with  Domain Separation.

- **Mechanism:** The client must pass a unique identifier in their WebSocket payload (e.g., `{"nonce": "shanti.coke_69"}`). This identifier is absorbed into the *SHA3-256* sponge, strictly separated by the `0x7C` (ASCII `|`) delimiter.
- **Formula:**
    $$\text{Input} = \text{BlockHash} \parallel \text{0x7C} \parallel \text{Nonce}$$
- **Result:** The canonicalized input ensures that the same block generates a completely unique, uncorrelated cryptographic seed for every individual event.

### B. Sub-Second Temporal Salting
It relies on the Optimism L2 sequencer, which produces a block exactly every 2 seconds. For extreme high-frequency environments (like a bullet-hell game) where waiting up to 2 seconds is unfeasible, Alea can optionally synthesize sub-second pulses.
- **Mechanism:** When a request is received between blocks, Alea freezes the local server's exact Unix Millisecond timestamp and appends it to the most recent block hash.
- **Formula:**

  ```math
  \text{Input} = \text{BlockHash} \parallel \text{0x7C} \parallel \text{Unix\_Milliseconds}
  ```

  **Why SHA-3?** Unlike `SHA-2`, it is safe against length-extension attacks, which allows us to have inputs of different length without complicated padding schemes.

---

**IMPORTANT DISCLOSURE:**
- Opting for Temporal Salting  downgrades Alea's profile from Purely Trustless to a Provably Honest Server model.

- Because a millisecond updates 1,000 times a second, introducing the local machine's clock opens a Grinding Attack Vector. A malicious host operator could iterate the SHA3-256 algorithm thousands of times within a 2-second window to identify the exact millisecond that yields their desired Rejection Sampling integer, artificially broadcasting that specific timestamp to the client.

- While the client's Edge Verification will confirm the math is perfectly accurate (the equation resolves correctly), the client has no mathematical way to prove the host did not manipulate the timestamp. This mode should only be enabled when sub-second UX takes absolute precedence over strict cryptographic trustlessness.

## 3. Cryptographic Methods
Alea uses **SHA3-256** as its main hashing algorithm. Natively supported via Python’s `hashlib`, *SHA-3* belongs to the *Keccak family* and relies on a "Sponge Construction" (absorbing input data at a specific bitrate and squeezing out a fixed-length digest).

- **Input:**
  > Raw data fetched by the local *Light Client/SPV node* (e.g., ***Ethereum mixHash*** or ***Bitcoin block header***).

- **Output:**
  > A fixed 256-bit (32-byte) representation, generating a random integer within a space of $2^{256}$.

**Formula:**

```math
\text{Entropy\_Seed} = \text{SHA3\_256}(\text{Consensus\_Data})
```

**Why SHA-3?** Unlike `SHA-2`, it is safe against length-extension attacks, which allows us to have inputs of different length without complicated padding schemes.

---

Alea's *"trustless"* design is not software reliant, it is enforced by the use of `SHA3-256` that guarantees three mathematical properties:

- **Strict Determinism:** Same input pushed through the algorithm will produce the exact same 256-bit output 100% of the time.
- **High Variation:** If a single bit in the blockchain header changes, the resulting `256-bit SHA-3` digest is completely & unpredictably altered.
- **One-Way Function:** If an attacker knows the final random number, they cannot mathematically deduce what the original block hash was, preventing downstream state manipulation.

## 4. Client-Side Verifiability
Because blockchains are public and SHA3-256 is deterministic, the host loses all ability to lie to the client. Verifiability is achieved through a closed mathematical loop on the client's local machine:
- Broadcast:
    > The Alea daemon broadcasts the raw Block Hash and the final random Seed to the client application.
- Independent Fetch:
    > The client application (e.g., a web UI or game engine) can independently query a public blockchain explorer to confirm that the broadcasted Block Hash is genuine.
- Client-Side Execution:
    > The client runs the identical SHA3-256 formula locally using the public Block Hash as the input.
- Proof:
    > If the client's locally generated 256-bit digest perfectly matches the seed broadcasted by Alea, the randomness is mathematically proven to be unaltered, unbiased, and completely authentic. No trust in the Alea host is required.

## 5. Anti-Bias Math Design
This layer ensures that aggregated raw blockchain data are processed into verifiable outcomes without the risk of structural biases.

### A. Canonicalization
This applies to both `sub-second` and `Domain Separation` configuration.

To protect the combined inputs against canonicalization attacks *(e.g., scenarios wherein the output of `12+345` == `123+25`)*, all inputs absorbed into the *SHA3-256* (Keccak) sponge are separated by a byte delimiter (`0x7C` / the ASCII `|` character):

> ```math
> \text{Input} = \text{Source\_Data} \parallel \text{0x7C} \parallel \text{Salt}
> ```

### B. Modulo Bias & Rejection Sampling
Standard integer division ($Winner = \text{Hash}\pmod{T}$) introduces Modulo Bias (`Pigeonhole Problem`) whenever the total ticket pool ($T$) is not a perfect power of two.

Alea leverages Python's native arbitrary-precision integers to execute a deterministic Rejection Sampling loop, reducing bias to zero.

1. Extract the first *128 bits (16 bytes)* from the *256-bit SHA-3* output.
2. Cast directly into an integer ($\text{Int128}$).
3. Calculate the upper mathematical boundary for an unbiased distribution:
$$Max = 2^{128} - (2^{128} \pmod{T})$$
4. Evaluate:
    - If $\text{Int128} < Max$: Accept the integer and compute the final output index:
    $$Winner = \text{Int128} \pmod{T}$$
    - If $\text{Int128} \ge Max$: Reject the integer. Re-hash the current output to generate a fresh candidate, repeating the loop until the condition is satisfied.


## 6. Binary Architecture
The program is deployed as a containerized microservice stack. This utilizes **Docker Compose Profiles**, allowing the operator to selectively boot only the modules they require.

| SERVICE           | IMAGE                        | FUNCTION                                                           | NETWORKING                                            |
|:------------------|:-----------------------------|:-------------------------------------------------------------------|:------------------------------------------------------|
| **Alea Router**   | python:3.11-slim-bookworm    | Core engine, Rejection Sampling, WSS server, and BTC SPV worker.   | Internal routing; utilizes named volume for SPV data. |
| **Helios (ETH)**  | Custom (Binary DL)           | Mode B consensus client. (Profile: attested)                          | Binds to 0.0.0.0:8545. Internal only.                 |
| **Helios (Base)** | Custom (Binary DL)           | Mode A consensus client. (Profile: optimistic)                          | Binds to 0.0.0.0:8546. Internal only.                 |
| **Reverse Proxy** | NGINX / Traefik              | TLS Termination (wss:// support).                                  | Exposes port 443 to the host network.                 |

### **Networking Specification:**
- **Localhost Resolution:** Because containers do not communicate over standard `127.0.0.1` interface, Helios instances are explicitly configured to bind their JSON-RPC endpoints to `0.0.0.0` inside a shared Docker bridge network.
- **Dual-Network Collision:** Using separate containers for Ethereum (helios-eth) and Base (helios-base) ensures the Light Clients can track disparate chain states simultaneously without cross-network pollution.
- **Insecure WebSockets:** Modern web browsers block mixed content (ws:// on an https:// site). The reverse proxy sits in front of the Python daemon to handle SSL/TLS termination, exposing a clean, secure wss:// feed to end users.

## 7. Footprint & System Requirements
A common constraint when running blockchain nodes is the massive hardware overhead required for execution and storage. Alea bypasses this by utilizing stateless Light Clients (Helios) and Simplified Payment Verification (Bitcoin SPV) nodes.

Because Alea only verifies mathematical proofs and block headers rather than downloading terabytes of blockchain data, the program is exceptionally lightweight. This makes Alea viable for **Edge Deployments, Single-Board Computers (SBCs) like the Raspberry Pi, Small Form Factor (SFF) Proxmox hypervisors, and entry-level ($4/month) Cloud VPS instances.**

### A. Hardware Footprint
In theory, even when operating all services concurrently, the system demands a microscopic fraction of compute resources:

- **RAM Capacity:** ***< 250 MB Total*** across the entire microservice stack.
    - Helios (ETH): ~50 MB
    - Helios (Base): ~50 MB
    - Alea Core & SPV Worker: ~50–100 MB

- **Storage / Disk I/O:** ***< 200 MB Total***.
    - Helios operates entirely in RAM and writes zero state to disk.
    - The Bitcoin SPV database maxes out at ~70 MB (80-byte headers for ~850,000+ blocks).

- **CPU Utilization:** ***< 5%*** of a standard single core (e.g., ARM Cortex-A72 or basic x86 virtual CPU).

### B. ARM Architecture (Raspberry Pi Viability)
Alea will be explicitly engineered to run on ARM-based hardware without emulation layers.
- **Native ARM64 Compilation:** I have planned to compile Docker images for both `linux/amd64` (PCs/servers) and `linux/arm64` (Raspberry Pi). When `docker compose up -d` is executed on a Pi, the Docker daemon automatically pulls the native ARM architecture.

- **WARNING:** Standard Raspberry Pi setups utilize microSD cards, which are highly susceptible to burnout from continuous write cycles. When deploying Alea on an SBC, IT is advised to boot the OS from an external USB Solid State Drive (SSD) or utilize a High-Endurance MicroSD.

## 8. Stability Designs
#### **Persistence:**
Alea Router mounts a persistent named Docker volume (`bitcoin_spv_data:/app/data`) to the SPV data directory. The SPV state survives container rebuilds, enabling the service to synchronize to the chain tip within seconds of booting.

#### **SQLite Write-Ahead Logging:**
On boot, the Alea daemon forces the SPV database connection into WAL mode. This allows parallel, non-blocking read/write execution.

```SQL
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
```

#### **Upstream Execution RPC Protection**:
The Program exclusively subscribes to the local Helios instance via the `newHeads` WebSocket subscription. Block proofs are pushed efficiently, minimizing outbound RPC calls and bandwidth consumption.

#### **OS Architecture:**
Alea’s core image strictly utilizes `python:3.11-slim-bookworm` (Debian-based). This ensures small image footprint while maintaining native `glibc` optimization for cryptographic speed.

#### **Auto-Recovery & Healthchecks:**
The topology includes automated health checks. If a client fails to respond to local RPC pings for three consecutive intervals, Docker automatically terminates and respawns the node without requiring intervention.

```YAML
healthcheck:
  test: ["CMD", "curl", "-f", "http://127.0.0.1:8545/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

## 9. Edge Verification
To completely neutralize host manipulation (as the server owner fundamentally controls the metal running the daemon), Alea pushes mathematical execution to the edge.

1. **Init:** The daemon boots, generating an ephemeral asymmetric private key.

2. **Subscribe:** A client application (e.g., Unity game) connects to the WebSocket and sends a request payload: {"mode": "attested"}.

3. **Execution & Signature:** When the respective target block arrives, the Python router does not send the final integer. It extracts the raw block hash, signs it with its private key, and broadcasts this cryptographic receipt.

4. **Edge Math Verification:** The client application receives the payload and executes the SHA3-256 hashing and Rejection Sampling logic locally. The client verifies the math without needing to trust the host execution environment.

***Note on Temporal Salting:*** Edge Verification mathematically proves the integrity of the hashing algorithm. However, if a client opts into Sub-Second Temporal Salting, the client can only verify the equation. It is not possible to prove the host did not manipulate the injected local timestamp to cherry-pick a favorable outcome.

## 10. CI/CD & Deployment Pipelines
Alea utilizes *GitHub Actions* to manage two distinct release pipelines, targeting both backend environments and desktop operation.

### Pipeline A: The Docker Hub Stack
- **Target:**
    > Multi-architecture Linux images (linux/amd64, linux/arm64).
- **Build Logic:**
    > Rust compilation is explicitly bypassed in CI to avoid 30+ minute QEMU emulation timeouts. The Dockerfile natively fetches pre-compiled Helios Linux binaries directly from a16z's official GitHub releases.
- **Distribution:**
    > Automated push to the GitHub Container Registry (GHCR), enabling one-command server deployment.

### Pipeline B: Nuitka Windows Executable
- **Target:**
    > A standalone .exe compiled for native Windows environments.
- **Build Logic:**
    > Uses Nuitka to translate Python source blocks into optimized C code and compiles via MSVC.
- **Asset Bundling:**
    > Uses the --include-data-files flag to embed the pre-compiled Windows Helios binary within the final executable.
- **Runtime Path Resolution:**
    > Implements a dynamic Python sys._MEIPASS helper to ensure subprocess.Popen accurately locates the embedded Helios binary when it is extracted into the temporary Windows AppData directory during execution.