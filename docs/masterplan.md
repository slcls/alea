# <h2><p align="center">**ALEA:**  ***A Crypto-Native Entropy***</p></h2>

### The Background: 
*Entropy* is one of the foundational resource of modern Cryptography in which all security architecture rests. By design, computers are deterministic, they excel at predictability but are incapable of generating true randomness on their own.

To bridge this gap, the industry evolved to aggregate environmental unpreditability as entropy source. From *Hardware True Random Number Generators (TRNGs)* to *Cloudflare's Lava Lamps*, analog noise has always been the industry standard when it comes to seeding entropy. Institutional frameworks like the *NIST Randomness Beacon*, *Drand*, and the *League of Entropy* scaled their services into a globally accessible networks.

But despite the mathematical quality of the entropy these services provide, from my vantage point, they suffer from two critical weaknesses:
1. **Trust Deficit:** These entropy providers requires absolute, unvetted trust. A user pulling a seed from an external beacon cannot easily verify if that data matches the raw physical source (e.g, light data obtained from lava lamps). The consumer must trust that a provider is not manipulating the calculation, front-running outputs, or serving a targeted stream to a specific user.

2. **API Hijacking Vulnerabilities:** Standard web API endpoints can be considered as an architectural weak link. Even if the entropy generation is trustworthy, the transport layer remains exposed to DNS spoofing, man-in-the-middle (MitM) attacks, and API endpoint hijacking. If the delivery pipeline is compromised, the cryptographic integrity of the application simply collapses.

**Alea** was conceptualized to solve this trust-and-delivery concerns entirely by leveraging public, decentralized blockchains as live, immutable entropy aggregates.

Instead of trusting a centralized intermediaries (e.g., *Infura*, *Alchemy*) or a single entity (e.g., *Drand*, *NIST*), Alea treats the global consensus data of secure blockchains as continously updated, ungrindable source of raw entropy. By fetching the data directly through a local light node and executing cryptographic computation directly on the host machine, it introduces an entry point for entropy that is completely ***veriafiable***, inherently ***trussless***, and entirely ***API-less***.

# <h4><p align="center">This document serves as a compiled technical blueprint for **Alea**:<br>an *API-less*, *trustless*, purely *crypto-based* Veriable Randomness Program.</p></h4>

---

As a quick background, **BASE** and **Ethereum** was chosen to be an aggregate since *Helios Light Client* is relatively stable, light, and easy to integrate. The same goes with **BTC** via a local *Simplified Payment Verification (SPV) client* connecting directly to the P2P network.

The program was originally planned to be a single sub-second entropy generator, but a vulnerability concept in cryptography called the "Last Actor Problem" made me rethink of my approach. This, from my vantage point, is a limitation of solely taking blockchain aggregates for entrophy generation.

## 1. The 3 Entropy Mode
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