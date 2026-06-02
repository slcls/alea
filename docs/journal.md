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

Not only have I drafted the initial `canonicalization.py` including features like prefix (0x, 0000...) checking, overflow guards (on negative signed integers), and null/empty payload checking, BUT, ***I discovered a flaw, and through it, I discovered a better feature as well...*** on my previous plan on having `|` or `b'\x76'` as a delimiter when joining two aggregates/input. Let me write down the details in here:

- The original plan was to use `|` as a delimiter, but think about it, say on the planned sub-second or domain seperation mode, an attacker intentionally added `|` to the payload, then my `build_payload(*args)` function would let it pass through, allowing an attacker to manipulate the output. Example:

    - **Normal Payload:**
    > `input("shan","111","ph")` -> `shan|111|ph`
    - **Malicious Payload:**
    > `input("shan|69","111","ph")` -> `shan|69|111|ph`

- Of course, I could've simply filtered the input to not allow `|`, but I took inspiration on **[Ethereum's RLP serialization](https://ethereum.org/developers/docs/data-structures-and-encoding/rlp)** wherein before appending a data, we append first exactly how many bytes the data contains (a.k.a length prefixing). In my case, it also makes it impossible to spoof boundaries using special characters. Example
    - **Normal Payload:**
    > `input("shan","100")` -> `[00 00 00 04]shan[00 00 00 03]100`
    - **Malicious Payload:**
    > `input("shan|69","100")` -> `[00 00 00 07]shan|69[00 00 00 03]100`

## 05/30 to 06/02:

### 1. Added the initial `rejection_sampling.py`

This is one of the most important part of the program wherein instead of using the simple `hash % total_tickets`, I took into account **Modulo Bias**. To further understand this concept, say that our hash is tiny (outputs numbers from 0 to 10 only, which equates to a total of 11 possible outcome) and we run a lottery with 3 tickets... by using the simple formula, we can visualize the biased outputs that we need to place into our rejection zone. (say that the formula is `hash % 3`)

| HASHES        | WINNING TICKET  | Winning Chances    | 
|:--------------|:----------------|:-------------------|
| `0, 3, 6, 9`  | Ticket 0        | 4 Times            |
| `1, 4, 7, 10` | Ticket 1        | 4 Times            |
| `2, 5, 8`     | Ticket 2        | 3 Times            |

We can see from this table that ticket 0 and 1 has unfair advantage, which we can fix by calculating the uneven remainder at the top of the range (hashes 9 and 10) and declaring them a Rejection Zone.

### 2. Updated `rejection_sampling.py`

I have updated this string-based error checking part:
```python
except ValueError as e:
            if "[REJECT]" in str(e):
                nonce += 1
                continue
```

by using custom exception class `class ModuloBiasRejection(Exception)` to esseentially make the program stable in case of string changes.

### 3. Added the initial `hashing.py`

The hashing wrapper was actually already integrated on `rejection_sampling.py`, I have decided to separate it though according to the initial architectural plan for better security auditing and reusability.