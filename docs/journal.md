## 05/19 to 05/28:

**FUN FACT:**
The name **"Alea"** came from the quote ***"Alea iacta est"*** (*translates to "The die is cast"*) by **Julius Ceasar**.

### 1. Wrote the concept and technical masterplan for Alea.

Prior to this time period, I have already envisioned something like this. A self-hosted, verifiable, trustless entropy generator. As a matter of fact, I have added a project named "truly-random" back then during the Flavortown event but due to some technical hurdles and concept breaking issues like the "last actor problem", I was stopped on my tracks.

These past few months, I came to reevaluate the weakness on my previous ideas, gaps in the current entropy generators, and I was able to came up with what it is today.

This time period as well as the past months prior was taken to conceptualize Alea and document the technical design, accessible on [masterplan.md](https://github.com/slcls/alea/blob/main/docs/masterplan.md).

## 05/29:

### 1. Added my planned file structure.

`core/crypto` - Contains the math logic including the canonicalization, hashing, rejection sampling, etc.
`core/engines` - Contains the modules for helios and spv.
`core/server` - Websockets stuff probably.

### 2. Added the initial `canonicalization.py`
