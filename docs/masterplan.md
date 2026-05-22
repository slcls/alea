# <h2><p align="center">**ALEA:**  ***A Crypto-Native Entropy***</p></h2>

### The Background: 
*Entropy* is one of the foundational resource of modern Cryptography in which all security architecture rests. By design, computers are deterministic, they excel at predictability but are incapable of generating true randomness on their own.

To bridge this gap, the industry evolved to aggregate environmental unpreditability as entropy source. From *Hardware True Random Number Generators (TRNGs)* to *Cloudflare's Lava Lamps*, analog noise has always been the industry standard when it comes to seeding entropy. Institutional frameworks like the *NIST Randomness Beacon*, *Drand*, and the *League of Entropy* scaled their services into a globally accessible networks.

But despite the mathematical quality of the entropy these services provide, from my vantage point, they suffer from two critical weaknesses:
1. **Trust Deficit:** These entropy providers requires absolute, unvetted trust. A user pulling a seed from an external beacon cannot easily verify if that data matches the raw physical source (e.g, light data obtained from lava lamps). The consumer must trust that a provider is not manipulating the calculation, front-running outputs, or serving a targeted stream to a specific user.

2. **API Hijacking Vulnerabilities:** Standard web API endpoints can be considered as an architectural weak link. Even if the entropy generation is trustworthy, the transport layer remains exposed to DNS spoofing, man-in-the-middle (MitM) attacks, and API endpoint hijacking. If the delivery pipeline is compromised, the cryptographic integrity of the application simply collapses.

**Alea** was conceptualized to solve this trust-and-delivery concerns entirely by leveraging public, decentralized blockchains as live, immutable entropy aggregates.

Instead of trusting a centralized corporation or a single entity, Alea treats the global consensus data of secure blockchains as continously updated, ungrindable source of raw entropy. By fetching the data directly through a local light node and executing cryptographic computation directly on the host machine, it introduces an entry point for entropy that is completely ***veriafiable***, inherently ***trussless***, and entirely ***API-less***.

# <h4><p align="center">This document serves as a compiled technical blueprint for **Alea**:<br>an *API-less*, *trustless*, purely *crypto-based* Veriable Randomness Program.</p></h2>

