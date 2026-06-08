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

### 4. Added the initial `crypto_bias.py` test module

This program essentially contains multiple rejection sampling related tests including: valid input, rejection sampling, invalid hash length, invalid ticket count, grinding loop & recovery, and payload integrity test.

### 5. Made a unified `crypto/` testing module `test_crypto.py`

Instead of a separate test program for each and every module inside `core/crypto/`, I have decided to create a single unified program instead wherein each crypto module tests are divided into classes:

- `TestHashing(unittest.TestCase)` for `hashing.py`
- `TestCanonicalization(unittest.TestCase)` for `canonicalization.py`
- `TestRejectionSampling(unittest.TestCase)` for `rejection_sampling.py`

Each and every possible scenarios, inputs, and possibilities that I can think of has a test function. This theoretically and analytically ensures that the core cryptography modules of this program will remain stable and behave as expected in the future. See **[test_crypto.py](https://github.com/slcls/alea/blob/main/tests/test_crypto.py)**.

---

All the effort and time spent making these test proved to be worth it, run it for the first time, and I was hit by these errors lmao 🤣:

<details>
<summary>Click to expand test traceback</summary>

```text
(.venv) @slcls ➜ /workspaces/alea (main) $ python -m unittest tests.test_crypto
....EE...........
======================================================================
ERROR: test_integer_parsing (tests.test_crypto.TestCanonicalization.test_integer_parsing)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/workspaces/alea/tests/test_crypto.py", line 44, in test_integer_parsing
    payload_255 = build_payload(255)
                  ^^^^^^^^^^^^^^^^^^
  File "/workspaces/alea/core/crypto/canonicalization.py", line 37, in build_payload
    raw_bytes = _to_bytes(arg)
                ^^^^^^^^^^^^^^
  File "/workspaces/alea/core/crypto/canonicalization.py", line 25, in _to_bytes
    return value.to_bytes(byte_length, byteorder='big', signed=True) # Signedd just in case it goes negative.
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
OverflowError: int too big to convert

======================================================================
ERROR: test_multi_argument_payload (tests.test_crypto.TestCanonicalization.test_multi_argument_payload)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/workspaces/alea/tests/test_crypto.py", line 59, in test_multi_argument_payload
    payload = build_payload("0xaa", 255)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/workspaces/alea/core/crypto/canonicalization.py", line 37, in build_payload
    raw_bytes = _to_bytes(arg)
                ^^^^^^^^^^^^^^
  File "/workspaces/alea/core/crypto/canonicalization.py", line 25, in _to_bytes
    return value.to_bytes(byte_length, byteorder='big', signed=True) # Signedd just in case it goes negative.
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
OverflowError: int too big to convert

----------------------------------------------------------------------
Ran 17 tests in 0.003s

FAILED (errors=2)
```
</details>

I'm still not exactly sure why it overflowed but yeah, that's something for me to figure out sometime after my midterms 🙏.

## 06/03 to 06/05:

### 1. Fixed the overflow error on signed integers.

As it turns out, the error earlier `test_crypto.py` came from the fact that `canonicalization.py` integer block of `_to_bytes(value)` function serialized the integer `255` into `1 byte` using `signed=True`. It was a bit confusing but if my research serves me right, `signed=True` acts wherein the first bit on the left is used as a sign bit (0 for +, 1 for -), `255` translates to `11111111` to binary and if the integer is signed, `11111111` equates to `-1`. We kinda need 2 extra bytes to safely handle the data without overflow error so I just made this fix instead to detect overflow instead of doing some crazy ahh bit manipulation:

```python
elif isinstance(value, int):
        byte_length = (value.bit_length() + 7) // 8 or 1
        try:
            return value.to_bytes(byte_length, byteorder='big', signed=True)
        except OverflowError:
            # Plus 1 byte if it overflows :)
            return value.to_bytes(byte_length + 1, byteorder='big', signed=True)
```

Passed with flying colors 🙏

```text
(.venv) @slcls ➜ /workspaces/alea (main) $ python -m unittest tests.test_crypto
.................
----------------------------------------------------------------------
Ran 17 tests in 0.012s

OK
```

> Transitioning back to windows for phase 2 of this project, Helios and SPV integration. (this will probably be the hardest part)

---

## 06/06:

### 1. Environment Prep for Phase 2 (Helios & SPV)

- Installed `Windows Subsystem for Linux (WSL2)` on my Windows 10 computer since we aim for containerized microservice stack that runs seamlessly on Linux and ARM-based Raspberry Pis.
- Fully configured the environment including venv as well as the `python-bitcoinlib==0.12.2` & `websockets==16.0`.

By the way, as per the local Python environment (including WSL2), I opted to use **Python Version 3.11** for a major reason. Docker microservices uses `python:3.11-slim-bookworm` base image, and also, python 3.11 image has a very small footprint. Plus, it's relatively stable compared to version 3.14 that is still in pre-release / development phase.

### 2. Installed `Helios 0.11.1` Binary

- Added **[Helios](https://github.com/a16z/helios/) release 0.11.1** ***Linux amd64 binary*** and added it to WSL2 alea `/bin` directory with proper permission.

### 3. Drafted `btc_spv.py` & Cleard Up Ports

Added the initial configuration including the pathing to reach `/data/spv_state.db` and some initial sqlite setup with write-ahead logging. I also cleared up some WSL2 & Windows processes running on `port 8545` (where helios ETH will run) and `port 8546` (helios for BASE).

## 06/07:

### 1. Completed the `btc_spv.py` program

Aside from the basic features earlier, I also added dotenv support (though initially it was hard-coded), full consensus node startup, logging, and exit cleanup. I also made some fixes and revisions along the way:

- Added `/logs` on the root directory to store helios traceback instead of the original `DEVNULL` code, I certainly don't wanna be blind when errors like invalid API keys or firewall (port blocked) stuff happens.
- Added `try/except Exception` so it doesn't flood my terminal with lots of logs in case of missing .env file (print a concise `[FATAL]` log instead).
- Added `cl_rpc` validation for ETH helios booting (it's required, otherwise it will crash).
- Added `atexit` to run `_cleanup_zombies` automatically regardless if the program crashes.

### 2. Testing Helios & Networks

I already expected this to be the hardest part lol, compared to codes that I can logically debug, this part requires a lot of ports observation, firewall config, and lots of other OS related stuff (plus I'm not used to this WSL ubunto distro). 😭🙏

<details>
<summary>Click to expand WSL traceback</summary>

```text
(.venv) slcls@SLCLS:~/WORKSPACE/GITHUB/alea$ python core/engines/helios_manager.py
[ LOG ] helios_manager: Booting Ethereum Light Client on port 8545...
[ LOG ] helios_manager: Tailing logs to -> /home/slcls/WORKSPACE/GITHUB/alea/data/logs/helios_ethereum_8545.log
[ LOG ] helios_manager: Booting Base Light Client on port 8546...
[ LOG ] helios_manager: Tailing logs to -> /home/slcls/WORKSPACE/GITHUB/alea/data/logs/helios_base_8546.log
[ LOG ] helios_manager: Engines running. Press Ctrl+C to gracefully exit.

slcls@SLCLS:~/WORKSPACE/GITHUB/alea$  source /home/slcls/WORKSPACE/GITHUB/alea/.venv/bin/activate
(.venv) slcls@SLCLS:~/WORKSPACE/GITHUB/alea$ curl -X POST -H "Content-Type: application/json" \
--data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
http://127.0.0.1:8545
curl: (7) Failed to connect to 127.0.0.1 port 8545 after 0 ms: Could not connect to server
```
</details>

Gotta check the log files though, might just be a simple syntax error on my end. (it really is lmao, writing this live btw) Thankfully I added `helios_ethereum_8545.log` & `helios_base_8546.log` instead of the `DEVNULL`.

- So, as it turns out, the documentation that I was following earlier uses the old CLI syntax (`helios --network ethereum` should've been `helios ethereum --execution-rpc ...` & `helios opstack --network base --execution-rpc ...` for Base).

The program seems to be working now (well not totally but the telemetry pipeline works), next step would be finding a good `ETH_CONSENSUS_RPC` endpoint for light clients, updating the links and env.

### 3. Public Endpoints

Just made an account on Alchemy (gotta give them some credits, very generous on that free tier API limits), added those keys to `.env` and I also updated `/docs/.env.sample`. Just as a quick note, I used ETH chain key for `BASE_CONSENSUS_RPC` since base is an optimistic rollup, so it kinda borrows consensus data from ethereum for security.

- **NOTE to my SELF:** Consider adding infura as a backup in the future, also give some big thanks to Hackclub, Alchemy, and Infura on `README.md`.

Gonna test it out tomorrow, starting to feel a bit sleepy.

## 06/08:

Just got home from school, booted helios, and I'm `1780923672 seconds` (*56 years btw*) behind wth 😭🙏 and it seems like `lightclientdata.org` isn't as reliable as I once thought, got a `503 Service Temporarily Unavailable` error. This will definitely be a long night:

<details>
<summary>helios_ethereum_8545.log:</summary>

```text
[2m2026-06-08T13:00:08.131481Z[0m [31mERROR[0m [2mhelios::consensus[0m[2m:[0m sync failed [3merr[0m[2m=[0mcould not fetch bootstrap: rpc error on method: bootstrap, message: status: 503, raw response: b"<html>\r\n<head><title>503 Service Temporarily Unavailable</title></head>\r\n<body>\r\n<center><h1>503 Service Temporarily Unavailable</h1></center>\r\n</body>\r\n</html>\r\n"
```
</details>

<details>
<summary>helios_base_8546.log:</summary>

```text
[2m2026-06-08T13:00:07.623703Z[0m [31mERROR[0m [2mhelios::opstack[0m[2m:[0m failed to advance: error decoding response body
```
</details>

<details>
<summary>Bash Terminal log:</summary>

```text
slcls@SLCLS:~/WORKSPACE/GITHUB/alea$  source /home/slcls/WORKSPACE/GITHUB/alea/.venv/bin/activate
(.venv) slcls@SLCLS:~/WORKSPACE/GITHUB/alea$ curl -X POST -H "Content-Type: application/json" \
--data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
http://127.0.0.1:8545
{"jsonrpc":"2.0","error":{"code":1,"message":"out of sync: 1780923672 seconds behind"},"id":1}
```
</details>

Okay, I'm starting with ethereum first, the 503 error seems to be on `lightclientdata.org` end. Maybe it's congested or something, but this actually helped me identify a single point of failure that I haven't planned to work on during the initial design. To solve this, instead of relying solely on that RPC, I decided to add the following as well (of course, I needed to revise the .env as well as the helios manager to dynamically switch and query the next endpoint available upon failure):

- **`https://beaconstate.ethstaker.cc` (EthStaker)**: Very reputable endpoint with some pretty good DDoS protection, maintaineed by community engineers. (Added this first on the list.)
- **`https://lodestar-mainnet.chainsafe.io` (ChainSafe)**: If I'm not mistaken it's maintained by the same entity as the one who built **Lodestar** (one of the official production-grade Ethereum consensus clients), so I'm basically querying from the writer of the consensus software itself.

As per the *"error decoding response body"* error on Base, I appended `--consensus-rpc` at the end of the helios command for both eth and base, but base asks for `--l1-rpc`, it was a wrong argument.

In addition, although Alchemy is already as good as it gets, I'll probably add Infura as well tomorrow, just so everything is stable and there's no single point of failure.

Completed all of the necessary revisions for `helios_manager.py` today, gotta sleep now and do some testing tomorrow and add Infura. (+ update `.env.sample`, can't forget that)

## 06/09: