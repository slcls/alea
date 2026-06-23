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

### 1. Draft of `btc_spv.py` program

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

### 1. Added backup endpoints

Okay, I'm starting with ethereum first, the 503 error seems to be on `lightclientdata.org` end. Maybe it's congested or something, but this actually helped me identify a single point of failure that I haven't planned to work on during the initial design. To solve this, instead of relying solely on that RPC, I decided to add the following as well (of course, I needed to revise the .env as well as the helios manager to dynamically switch and query the next endpoint available upon failure):

- **`https://beaconstate.ethstaker.cc` (EthStaker)**: Very reputable endpoint with some pretty good DDoS protection, maintaineed by community engineers. (Added this first on the list.)
- **`https://lodestar-mainnet.chainsafe.io` (ChainSafe)**: If I'm not mistaken it's maintained by the same entity as the one who built **Lodestar** (one of the official production-grade Ethereum consensus clients), so I'm basically querying from the writer of the consensus software itself.

### 2. Fix Flag argument error

As per the *"error decoding response body"* error on Base, I appended `--consensus-rpc` at the end of the helios command for both eth and base, but base asks for `--l1-rpc`, it was a wrong argument.

In addition, although Alchemy is already as good as it gets, I'll probably add Infura as well tomorrow, just so everything is stable and there's no single point of failure.

Completed all of the necessary revisions for `helios_manager.py` today, gotta sleep now and do some testing tomorrow and add Infura. (+ update `.env.sample`, can't forget that)

## 06/09:

### 1. Fixed wrong network endpoint + `.env.sample` Update

I just noticed it when I was adding Infura as a backup RPC, seems like I added optimism instead of Base network for the Alchemy endpoint. Fixed it now though and I've also updated the sample env.

### 2. Fixed Flag & Re-ordered RPC

Thankfully the log was very specific and it seems like the `--l1-rpc` isn't needed anymore on the latest update, did some minor revision on `helios_manager.py`.
> `Usage: helios opstack --network <NETWORK> --execution-rpc <EXECUTION_RPC> --rpc-port <RPC_PORT>`

Also, yesterday I made `beaconstate.ethstaker.cc` as the primary ETH RPC but upon testing today, I was weirded out why I didn't trigger the failover on the program upon failure. So I tested it out on insomnia and it seems that it actually connected by returned `404 Not Found`, not really sure but it seems like it's on their end. Added `lodestar-mainnet.chainsafe.io` as the primary endpoint now. (will definitely work on this further, later after the test of course)

---

Also, the base node is finally working!!!

```text
[2m2026-06-09T03:16:33.205860Z[0m [32m INFO[0m [2mhelios::client[0m[2m:[0m latest block     number=47092822 age=2s
[2m2026-06-09T03:16:34.659792Z[0m [32m INFO[0m [2mhelios::client[0m[2m:[0m latest block     number=47092823 age=1s
```

Unfortunately, the ethereum node seems to be getting rate limited on both Alchemy as well as chainsafe:

```text
[2m2026-06-09T03:31:28.144903Z[0m [32m INFO[0m [2mhelios::consensus[0m[2m:[0m saved checkpoint to DB: 0x00275e1d7b9d5d048c67e0e71e8155a13de8a18b8dbfddc55e4f4e34a270cc30
[2m2026-06-09T03:31:40.989073Z[0m [33m WARN[0m [2mhelios::consensus[0m[2m:[0m send error: rpc error on method: blocks, message: status: 429, raw response: b"<html>\r\n<head><title>429 Too Many Requests</title></head>\r\n<body>\r\n<center><h1>429 Too Many Requests</h1></center>\r\n<hr><center>nginx/1.29.8</center>\r\n</body>\r\n</html>\r\n"
```

### 3. Dangling processes Fix

Okay, so first and foremost, it seems like the ETH node is trying to catch up with the latest header (`WARN helios::consensus: checkpoint too old`), and it behaved in a way that triggered rate-limiting for those platforms. It works on the first attempt though and upon checking my network history, it seems like the helios process doesn't stop querying after getting 249 error. It does so every ~10-12 seconds. In a way, the termination upon error logic that I've added to `helios_manager.py` doesn't work since helios isn't crashing, it's simply querying again and again. Refactored part of the `start_helios_node()` and added active telemetry and failover routing.

Still getting rate-limited though so I had to implement the following changes (+ a pretty massive `helios_manager.py` refactoring) as well:

- Added `--fallback` flag to the ethereum node helios CLI since the checkpoint it's trying to catch up from is literally months behind, it basically pings a community beacon (`beaconcha.in`) in this case to grab a starting point that isn't too far from the current header.
- Added active tail logging for every node (always running) to ensure proper endpoints failover, pretty sure this process isn't very heavy but i'll try to optimize compute heavy task soon.

---

And oh boy, I really can't figure it out lmao.

<details>
<summary>WSL2 Terminal log:</summary>

```text
(.venv) slcls@SLCLS:~/WORKSPACE/GITHUB/alea$ /home/slcls/WORKSPACE/GITHUB/alea/.venv/bin/python /home/slcls/WORKSPACE/GITHUB/alea/core/engines/helios_manager.py
[ LOG ] helios_manager: Booting Ethereum Light Client on port 8545
[ LOG ] helios_manager: Target EL -> https://eth-mainnet.g.alchemy.com/v2/cu--6MYw...
[ LOG ] helios_manager: Target CL/L1 -> https://lodestar-mainnet.chainsafe.io...
[ LOG ] helios_manager: Booting Base Light Client on port 8546
[ LOG ] helios_manager: Target EL -> https://base-mainnet.g.alchemy.com/v2/A-k7Nx4...
[ LOG ] helios_manager: Target CL/L1 -> https://eth-mainnet.g.alchemy.com/v2/cu--6MYw...
[ SYSTEM ] helios_manager: Continuous Supervisor Active. Press Ctrl+C to exit.
[ WARN ] helios_manager: Ethereum hit a Rate Limit (429/404). Assassinating zombie process...
[ LOG ] helios_manager: Ethereum Consensus endpoint throttled. Rotating CL backup pool...
[ LOG ] helios_manager: Booting Ethereum Light Client on port 8545
[ LOG ] helios_manager: Target EL -> https://eth-mainnet.g.alchemy.com/v2/cu--6MYw...
[ LOG ] helios_manager: Target CL/L1 -> https://beaconstate.ethstaker.cc...
[ WARN ] helios_manager: Ethereum hit a Rate Limit (429/404). Assassinating zombie process...
[ LOG ] helios_manager: Ethereum Consensus endpoint throttled. Rotating CL backup pool...
[ LOG ] helios_manager: Booting Ethereum Light Client on port 8545
[ LOG ] helios_manager: Target EL -> https://eth-mainnet.g.alchemy.com/v2/cu--6MYw...
[ LOG ] helios_manager: Target CL/L1 -> https://www.lightclientdata.org...
[ WARN ] helios_manager: Base hit a Rate Limit (429/404). Assassinating zombie process...
[ LOG ] helios_manager: Base Execution endpoint throttled. Rotating EL backup pool...
[ LOG ] helios_manager: Booting Base Light Client on port 8546
[ LOG ] helios_manager: Target EL -> https://base-mainnet.infura.io/v3/a01c56869da...
[ LOG ] helios_manager: Target CL/L1 -> https://eth-mainnet.g.alchemy.com/v2/cu--6MYw...
[ WARN ] helios_manager: Base hit a Rate Limit (429/404). Assassinating zombie process...
[FATAL] helios_manager: Base endpoints exhausted. No backups remain.
```
</details>

There's just literally no way that I am hitting rate limits on each and every endpoints there is.

### 4. Major refactoring on the failover logic

`--checkpoint` added so it won't rely on the single endpoint (`beaconcha.in`) anymore when trying to keep up with the latest header. Updated the log-tailing logic with a `last_read_pos` tracker that counts to 3 before swapping the RPC. Added `time.sleep(10)` before booting processes as to not to congest the network. And a whole lot more of changes.

## 06/10:

Gonna focus on debugging what exactly is happening to `helios_manager.py` as well as the RPC endpoints today.

<details>
<summary>WSL2 Terminal log:</summary>

```text
(.venv) slcls@SLCLS:~/WORKSPACE/GITHUB/alea$ /home/slcls/WORKSPACE/GITHUB/alea/.venv/bin/python /home/slcls/WORKSPACE/GITHUB/alea/core/engines/helios_manager.py
[ LOG ] helios_manager: Booting Ethereum Light Client on port 8545
[ LOG ] helios_manager: Target EL -> https://eth-mainnet.g.alchemy.com/v2/cu--6MYw...
[ LOG ] helios_manager: Target CL/L1 -> https://lodestar-mainnet.chainsafe.io...
[ LOG ] helios_manager: Booting Base Light Client on port 8546
[ LOG ] helios_manager: Target EL -> https://base-mainnet.g.alchemy.com/v2/A-k7Nx4...
[ LOG ] helios_manager: Target CL/L1 -> https://eth-mainnet.g.alchemy.com/v2/cu--6MYw...
[ SYSTEM ] helios_manager: Continuous Supervisor Active. Press Ctrl+C to exit.
[ WARN ] helios_manager: Ethereum hit a Rate Limit (429/404). Assassinating zombie process...
[ LOG ] helios_manager: Ethereum Consensus endpoint throttled. Rotating CL backup pool...
[ LOG ] helios_manager: Booting Ethereum Light Client on port 8545
[ LOG ] helios_manager: Target EL -> https://eth-mainnet.g.alchemy.com/v2/cu--6MYw...
[ LOG ] helios_manager: Target CL/L1 -> https://beaconstate.ethstaker.cc...
[ WARN ] helios_manager: Ethereum hit a Rate Limit (429/404). Assassinating zombie process...
[ LOG ] helios_manager: Ethereum Consensus endpoint throttled. Rotating CL backup pool...
[ LOG ] helios_manager: Booting Ethereum Light Client on port 8545
[ LOG ] helios_manager: Target EL -> https://eth-mainnet.g.alchemy.com/v2/cu--6MYw...
[ LOG ] helios_manager: Target CL/L1 -> https://www.lightclientdata.org...
[ WARN ] helios_manager: Base hit a Rate Limit (429/404). Assassinating zombie process...
[ LOG ] helios_manager: Base Execution endpoint throttled. Rotating EL backup pool...
[ LOG ] helios_manager: Booting Base Light Client on port 8546
[ LOG ] helios_manager: Target EL -> https://base-mainnet.infura.io/v3/a01c56869da...
[ LOG ] helios_manager: Target CL/L1 -> https://eth-mainnet.g.alchemy.com/v2/cu--6MYw...
[ WARN ] helios_manager: Base hit a Rate Limit (429/404). Assassinating zombie process...
[FATAL] helios_manager: Base endpoints exhausted. No backups remain.
[ LOG ] helios_manager: All active Helios nodes successfully terminated and logs saved.
(.venv) slcls@SLCLS:~/WORKSPACE/GITHUB/alea$ /home/slcls/WORKSPACE/GITHUB/alea/.venv/bin/python /home/slcls/WORKSPACE/GITHUB/alea/core/engines/helios_manager.py
[ LOG ] helios_manager: Acquired dynamic L1 checkpoint 0xee9c29cd... from https://lodestar-mainnet.chainsafe.io
[ LOG ] helios_manager: Booting Ethereum Light Client on port 8545
[ LOG ] helios_manager: Target EL -> https://eth-mainnet.g.alchemy.com/v2/cu--6MYw...
[ LOG ] helios_manager: Target CL/L1 -> https://lodestar-mainnet.chainsafe.io...
[ LOG ] helios_manager: Allowing L1 peer handshake to settle (10s delay)...
[ LOG ] helios_manager: Booting Base Light Client on port 8546
[ LOG ] helios_manager: Target EL -> https://base-mainnet.g.alchemy.com/v2/A-k7Nx4...
[ LOG ] helios_manager: Target CL/L1 -> https://eth-mainnet.g.alchemy.com/v2/cu--6MYw...
[ SYSTEM ] helios_manager: Continuous Supervisor Active. Press Ctrl+C to exit.
[ ALERT ] helios_manager: Ethereum detected a transient rate limit (Strike 1/3). Backing off...
[ ALERT ] helios_manager: Ethereum detected a transient rate limit (Strike 2/3). Backing off...
[ WARN ] helios_manager: Ethereum hit max Rate Limit strikes. Assassinating zombie process...
[ LOG ] helios_manager: Ethereum Consensus endpoint throttled. Rotating CL backup pool...
[ LOG ] helios_manager: Acquired dynamic L1 checkpoint 0xee9c29cd... from https://lodestar-mainnet.chainsafe.io
[ LOG ] helios_manager: Booting Ethereum Light Client on port 8545
[ LOG ] helios_manager: Target EL -> https://eth-mainnet.g.alchemy.com/v2/cu--6MYw...
[ LOG ] helios_manager: Target CL/L1 -> https://beaconstate.ethstaker.cc...
[ ALERT ] helios_manager: Ethereum detected a transient rate limit (Strike 1/3). Backing off...
[ ALERT ] helios_manager: Base detected a transient rate limit (Strike 1/3). Backing off...
[ LOG ] helios_manager: Base successfully recovered. Resetting rate limit strikes.
[ ALERT ] helios_manager: Base detected a transient rate limit (Strike 1/3). Backing off...
[ LOG ] helios_manager: Base successfully recovered. Resetting rate limit strikes.
[ ALERT ] helios_manager: Base detected a transient rate limit (Strike 1/3). Backing off...
[ LOG ] helios_manager: Base successfully recovered. Resetting rate limit strikes.
[ ALERT ] helios_manager: Base detected a transient rate limit (Strike 1/3). Backing off...
[ LOG ] helios_manager: Base successfully recovered. Resetting rate limit strikes.
[ ALERT ] helios_manager: Base detected a transient rate limit (Strike 1/3). Backing off...
[ LOG ] helios_manager: Base successfully recovered. Resetting rate limit strikes.
[ ALERT ] helios_manager: Base detected a transient rate limit (Strike 1/3). Backing off...
[ LOG ] helios_manager: Base successfully recovered. Resetting rate limit strikes.
[ LOG ] helios_manager: All active Helios nodes successfully terminated and logs saved.
```
</details>

What's good though is I succesfully eliminated the possible `beaconcha.in` single point of failure and the logs show that it was actually able to acquire a checkpoint (`0xee9c29cd`) from Chainsafe.

### 1. Improved Filters & Grace time

Added checks for `execution`, `consensus` before deciding which pool to rotate. + `status: 429`, `status: 404`, or `rate limit` instead of just `404`. + Closed processes only after continously returning error state for more than 15 seconds.

## 06/11:

Okay, a bit of improvement, I am actually being able to connect to the ethereum `eth-mainnetbeacon.g.alchemy.com` RTC now, though I still need to check the official documentation because it's throwing this error in my logs:

```
status: 400, raw response: b"{\"error\": \"Unsupported method: /eth/v1/beacon/light_client/bootstrap/... on ETH_MAINNETBEACON\"}"
```

It seems like it returned a `400 Bad Request` error after helios asked for `light_client/bootstrap` payload, a good friend of mine told me that Alchemy's beacon node doesn't actually support Altair's light client sub-protocols. These are some very good diagnostic info though and I'm looking for ways to have it fixed now.

### 1. Bumped ChainSafe `elapsed_errors`

The last grace window for querying dynamic checkpoint from chainsafe was 15 seconds, and upon testing, I figured out that I was still rate-limited at some point. It seems like continous requests gets throttled at a rate that doubles each time (e.g., 2s, 4s, 8s, 16s...), so I bumped it up to 45 seconds.

### 2. Logging Changes on `helios_manager.py`

Added `SESSION_ID` timestamp on logs, reverted back to append mode instead of write so I can better analyze the errors and stuff. Added `last_read_pos` as well.

## 06/13:

Had to take some break due to an emergency yesterday, but we're finally back on business and I've made some useful debugging:

- Definitely made some logic errors on the for loop, the logs says it is rotating the pool but the end-points query (including those on the logs) remains the same.
- Helios sessions are terminated each time that the pool rotates, and it seems like the header signature on the chainsafe query is getting flagged and block after a number of reboots.
- `Base endpoints exhausted. No backups remain.` probably due to repeated ethereum node termination (base relies on that for the consensus).

## 06/14:

After some tedious debugging with no clear progress, I have decided to completely scratch out the current `helios_manager.py` and change my approach into a more verbose, modular, and development friendly alternative:

- The earlier `helios_manager.py` has some very messy `while True` loops that juggle process states that makes it super hard for me to debug which failing is who. I plan on refactoring this completely, still unified though but I want to integrate something like `eth_node.check_health()` and `base_node.check_health()` to encapsulate the processes.
- Gonna add a dedicated `test_helios_eth.py` with python's `test_helios_eth.py` mock as well along side the main program so I can easily see the bottlenecks. Definitely going to use the `logging` library as well as the `asyncio` framework to capture logs in real time.
- Originally, I was planning to build the docker microservices near the end of project, but working with different machines and different environments (my main PC, codespaces, MAC Lab PC, etc.) as well as the networking errors that I have to debug each and everytime made me decide that this phase is also the perfect time to learn docker and implement it.
- Gonna add a pre-flight checks as well that pings `/eth/v1/node/version` / `/eth/v1/beacon/headers` RPC endpoints before starting the main program.
- The logs earlier really gives me a massive migraine, I have decided to have `BOOTING`, `SYNCING`, `HEALTHY`, `THROTTLED`, or `DEAD` states rather than some messy logging syntax.

---

### 1. Newly refactored `helios_manager.py`

- Calls `/eth/v1/beacon/headers/finalized` during `validate_upstream_rpcs()` to confirm if the node actually supports Altair light client protocol as well as to grab the dynamic checkpoint needed to boot helios (bypassing `fetch_dynamic_checkpoint`).
- It now parse in real time wherein the `consume_stream()` and `readline()` functions accepts the output byte by byte, and triggers `NodeState.THROTTLED` instantly without waiting for the logging.
- Refactored the disk/file stored tailing with `asyncio.create_subprocess_exec` wherein it is now stored in memory to remove I/O bottlenecks (+ storage degragation).
- Implemented the `NodeState(Enum)` dictionary mentioned earlier to classify the actions that we will use for each node.
- `stdout=asyncio.subprocess.PIPE` that captures the output to python memory as to not degrate the host flash memory.
- Added `@property` decorator so we can avoid `IndexOutOfBounds` errors.
- Better RPC rotations, failover, and lots of other stuff that I hope works.

### 2. Bug fixes

- Base node fails the pre-flight check (`400 Bad Request`), rotates to EL Pool, then fails again. I was able to find the issue wherein the .env file still has the alchemy and infura L1 endpoints on `BASE_CONSENSUS_RPC` , as per the earlier logs, base does not require a consensus (`--l1-rpc` argument). `validate_upstream_rpcs()` is pinging those list entries for a beacon header `/eth/v1/beacon/...`.
- Ethereum boots okay with chainsafe, it syncs for about ~15 seconds then it is suddenly rate limited (`status: 429`), rotates to `ethstaker.cc` (`404 Not Found` respond), rotates to `lightclientdata.org` (`503 Service Temporarily Unavailable` response) and it goes all over again 😭🙏. I have checked my alchemy logs and some of the request didn't even make it there, suggesting that it was definitely blocked (probably due to simultaneous compute request limits). The other two RPC doesn't seem to be helping.

To fix those, I have made some changes to `validate_upstream_rpcs` so that it only validate the consensus layer if the network is == ethereum (issue #1). I also added a 15 seconds sleep in the `main_supervisor` if a node is marked as `THROLLED`, and I have pruned the other two non-functioning RPC (temporarily, I just want it to work flawlessly with ChainSafe for now).

---

### 3. Major Refactoring & Updates

Lots of errors, debugging, research, and some other stuff happened during this period of time and I probably won't be able to document all of it. But basically, I chose to scrap out the entire helios module in favor these changes:

- To solve the rate limiting issue, I have decided to add the following public RPC Roster:
  1. `https://cloudflare-eth.com`
  2. `https://eth.llamarpc.com`
  3. `https://ethereum-rpc.publicnode.com`
  4. `https://rpc.ankr.com/eth`
  5. `https://1rpc.io/eth`

- This alone technically wouldn't solve the rate limit issue if the program is simply bombarding one endpoint then rotating to the next once it encounters an error, so I opted to create a load balancer program (with a primary endpoint while keeping a record of the current state and an active failover that instantly caches the pending request and send it to the next provider on the list).

### 4. Development of `rpc_proxy.py`

This program serves as the load balancer that also host the endpoint that provides the input data for `helios_manager.py` in a way wherein helios manager now only focuses on the hosting and helios logic while the `rpc_proxy.py` manages all of the consensus and networking stuff. As per the network, it runs on the following port (for now, planning to migrate it later to some "surely" unoccupied ports; `127.0.0.1:xxxx`):
  - `9000:` Ethereum Execution (EL)
  - `9001:` Ethereum Consensus (CL)
  - `9002:` Base Execution (EL)

It also utilizes `aiohttp` instead of the standard `urllib` to avoid concurrent proxy request bottlenecks.

## 06/16:

### 1. Complete `rpc_proxy.py` & Refactored `helios_manager.py`

This is a continuation of the progress last time, tested it as well and it is really looking promising and more easier to debug and maintain compared to the unified helios manager. The proxy perfectly swept the endpoint, correctly identified dead and active nodes, staggered distributed checks (didn't mentioned this earlier but I basically programmed it in a way wherein dead nodes are pinged every 60 seconds, if it returns a valid response, it is moved to active nodes... The pings are distributed as to not create a network spike), `helios_manager.py` succesfully got the beacon root from chainsafe, base network run for 15+ minutes without any error, none of the program crashed. Very nice progress!!!

Still though, there is a single issue to be resolved:

- I only have one working CL endpoint as of the moment (ChainSafe), the thing is, it runs flawlessly for sometime then it gets rate-limited, moved to dead pool, waits for 60 seconds to move back to active pool... And since it has no replacement, it's dead for that entire 60 seconds period of time.

### 2. Fixes & Refactoring

To solve the rate limit bottleneck, I decided to add an additional two public keyless RPC endpoint as well as a private one (with free tier):

  1. `https://eth-beacon-chain.drpc.org`
  2. `https://ethereum-beacon-rpc.publicnode.com`
  3. `https://nodereal.io` (private, free tier)

Not only that but I also added a local rate limit to throttle down the initial sync queries of helios to only every ~100ms. This of course, increased the initialization phase by about ~15-20 seconds but it should be able to effortlessly sustain all of the operation loads once the node finally complete the sync.

In addition, the earlier ports (9000s and 8545, 8546) are fairly common and used by other webservices/crypto applications. To avoid networking conflicts, I have explicitly moved everything to `43200` range:

  - `43200` -> ETH Proxy (Execution)
  - `43201` -> ETH Proxy (Consensus)
  - `43202` -> BASE Proxy (Execution)
  - `43210` -> Helios ETH Verified Output
  - `43211` -> Helios BASE Verified Output

---

And oh boy, you do not know how happy am I right now. It finally works! The endpoints sweep is beautifully done! **4:3 (Active : Dead Ratio)** on `ETH_EL` and **2:4 (Active : Dead Ratio)** on `ETH_CL` and **4:1 (Active : Dead Ratio)** on `BASE_EL`, helios booted very well and was handed off a good beacon root, beautiful fallback and recovery on ChainSafe without stopping operation. This is as good as it can get, I am really happy about it (considering the fact that this was the hardest part so far).

<details>
<summary>helios_manager.py logs:</summary>

```text
(.venv) slcls@SLCLS:~/WORKSPACE/GITHUB/alea$ python3 core/engines/helios_manager.py
[ INFO ] 21:09:20 | Alea.Supervisor: [ETHEREUM] Requesting dynamic checkpoint from local proxy...
[ INFO ] 21:09:20 | Alea.Supervisor: [ETHEREUM] Checkpoint acquired: 0x2f0b91a8...
[ INFO ] 21:09:20 | Alea.Supervisor: [ETHEREUM] Booting Light Client on port 43210...
[ INFO ] 21:09:22 | Alea.Supervisor: [BASE] Booting Light Client on port 43211...
[ INFO ] 21:09:23 | Alea.Supervisor: [ETHEREUM] Node successfully synced and healthy.
[ INFO ] 21:09:24 | Alea.Supervisor: [BASE] Node successfully synced and healthy.
[ INFO ] 21:09:24 | Alea.Supervisor: [ SYSTEM ] Async Supervisor Active. Press Ctrl+C to exit.
^C
[ INFO ] 21:13:42 | Alea.Supervisor: [ SYSTEM ] Shutdown signal received. Terminating nodes...
```
</details>

<details>
<summary>rpc_proxy.py partial logs:</summary>

```text
(.venv) slcls@SLCLS:~/WORKSPACE/GITHUB/alea$ /home/slcls/WORKSPACE/GITHUB/alea/.venv/bin/python /home/slcls/WORKSPACE/GITHUB/alea/core/engines/rpc_proxy.py
[ INFO ] 21:09:11 | Alea.Proxy: [BASE_EL] Boot Sweep Complete. Active: 4 | Dead: 1
[ INFO ] 21:09:11 | Alea.Proxy: [ETH_EL] Boot Sweep Complete. Active: 4 | Dead: 3
[ INFO ] 21:09:13 | Alea.Proxy: [ETH_CL] Boot Sweep Complete. Active: 2 | Dead: 4
[ INFO ] 21:09:13 | Alea.Proxy: [ SYSTEM ] Web3 Proxy Multiplexer Active. Awaiting Helios traffic...
[ INFO ] 21:09:21 | aiohttp.access: 127.0.0.1 [16/Jun/2026:21:09:20 +0800] "GET /eth/v1/beacon/light_client/bootstrap/0x2f0b91a8c3eb7bf3c8b812363b6d0ebaa95457cdd19017f1b61ceb9fcab9bf82 HTTP/1.1" 200 54548 "-" "-"
[ WARNING ] 21:09:23 | Alea.Proxy: [ETH_CL] Endpoint https://lodestar-mainnet.chainsafe.... threw 429. Banish to Dead Pool.
[ WARNING ] 21:09:23 | Alea.Proxy: [ETH_CL] https://lodestar-mainnet.chainsafe.... assigned to Dead Pool. Recovery check in 60s.
[ INFO ] 21:10:03 | aiohttp.access: 127.0.0.1 [16/Jun/2026:21:10:03 +0800] "GET /eth/v2/beacon/blocks/14565947 HTTP/1.1" 200 461766 "-" "-"
[ INFO ] 21:10:24 | Alea.Proxy: [ETH_CL] https://lodestar-mainnet.chainsafe.... RECOVERED. Graduated to Active Pool.
```
</details>

## 06/17:

### 1. Added `ws_subscriber.py`

Earlier, Helios is running on ports `43210` and `43211` by itself. This new websocker subscriber program localted at `/core/server/` basically taps into those ports using the `websockets` library. Instead of constantly polling the node that waste CPU cycles, it uses a json RPC method with the `newHeads` parameter that forces helios to actively push block header to alea the exact time that the block is verified.

### 2. Added `test_helios_manager.py`

Same concept with `test_crypto.py` but it uses `unittest.IsolatedAsyncioTestCase` and extensive `AsyncMock` objects to deal with asynchronous event loops. It basically feeds simulated data in an isolated environment to ensure that `helios_manager.py` works properly on almost all anticipated cases. Also added some test cases for possible OS program interuption (say, if it encounters an out of memory error on a raspberry pi) as well as possible native processes crash.

### 3. Testing & Fixes

The `ws_subscriber.py` logs contains this line -> `sent 1009 (message too big) frame with 1064612 bytes exceeds limit of 1048576 bytes` which stems from the 1MB limit of `websockets` library, seems like the BASE node pushed a block `1.06 MB` in size that caused that error. Changed the `max_size` to 10MB.

The `test_helios.py` on the other hand returned this error:

```text
AssertionError: <NodeState.BOOTING: 'BOOTING'> != <NodeState.HEALTHY: 'HEALTHY'>
RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
```

This was an issue with `self.eth_node.process.stdout` since it was mocked as `AsyncMock()` and every method inside of it becomes asynchronous mocked, `at_eof()` method was supposed to be a normal synchronous method.

## 06/18:

### 1. Research and Planning

Working on designing the program specifications and architecture for the BTC SPV module. I plan on relying primarily on trusted public RPC endpoints while locally verifying Merkle roots and Proof of Work difficulty. Of course, I also considered having a direct P2P connection but I opted to have a separate module that users can download to optionally support this in the future, this is because compared to the fast and quick json queries and lightweight nature of public RPC option, using direct P2P connections means much more resource footprint (both on RAM and CPU) due to its bandwidth heavy nature as well as the need to host our own table of block headers (plus some other issues like network splits, multiplexing of endpoints, etc.). I plan on having the similar active/dead pool and failover logic as the one I did in helios. As per the data I have gathered, here are the current pool of endpoints that I am planning to add as of the moment:

  1. `electrum.blockstream.info:50002`
  2. `bitcoin.lu.ke:50002`
  3. `alvey.pissedoff.net:50002`
  4. `electrum.emzy.de:50002`
  5. `electrum.jochen-hoenicke.de:50006`
  6. `fortress.qtornado.com:443`
  7. `https://bitcoin-mainnet.gateway.tatum.io` (private, free tier)

I also looked on some private providers that provides a free tier, there's definitely a few compared to ETH/BASE but I manage to find `https://tatum.io/`, setting up the account and stuff as of the moment. Going to start the real development tomorrow.

NOTE TO MYSELF:
- Keep transport protocols in mind (Stratum protocol).
- Add Tatum ETH and Base endpoints (lesss gooo, greater pool population).

## 06/19

### 1. Minor RPC endpoint entry fix

Tested out all of the RPC endpoints for helios by manually sending a query via insomia and I found that `https://eth2-beacon-mainnet.nodereal.io` on `ETH_CONSENSUS_RPC` is almost always alive but for some reason it is always placed at the dead pool, checked the program, didn't find any issue. And when I checked the .env, I saw this entry `https://eth2-beacon-mainnet.nodereal.io/v1/SAMPLE_KEY/eth/v1` lmao 😭🙏, I forgot to remove the `/eth/v1` part at the end, the program automatically appends that. Fixed that already, seems to be working well now.

### 2. Added `gateway.tatum.io` to Pool

This was originally planned to be used for BTC SPV, but since it also supports ETH/BASE JSON RPC and ETH BEACON API, I also added it as a backup next to infura, alchemy, and nodereal.

### 3. HTTP Header support

The official documentation for Tatum requires (probably the right word, since passing the API key as a url parameter isn't shown) passing the API key in the HTTP header as `x-api-key: {YOUR_API_KEY}`. Made some changes to `rpc_proxy.py` to accomodate this change dynamically.

Great addition to be honest, tested it out once again and due to the .env fix plus this new endpoint, it's now `5:3` on `ETH_EL`, `5:1` on `BASE_EL`, and `4:3` on `ETH_CL`:

```text
[ INFO ] 12:09:20 | Alea.Proxy: [ETH_EL] Boot Sweep Complete. Active: 5 | Dead: 3
[ INFO ] 12:09:20 | Alea.Proxy: [BASE_EL] Boot Sweep Complete. Active: 5 | Dead: 1
[ INFO ] 12:09:22 | Alea.Proxy: [ETH_CL] Boot Sweep Complete. Active: 4 | Dead: 3
```

### 4. Added initial `btc_spv.py`

Core module for BTC SPV, mode C (Proof). Shares some of the architecture implemented on the earlier helios such as the endpoints sweep, active/dead pool setup, failover, etc. In addition, it also:

- Has support for both the standard HTTP JSON-RPC endpoints (especially for the tatum endpoint), as well as the raw TCP socket connections via electrum protocol (no worries, I'll add an optional stratum protocol support for direct P2P connections later on down the line, probably after the MVP).
- Has local Proof of Work validation by performing double SHA-256 hash on the 80-byte block headers to verify that they match the expected hash.
- Uses a local SQLite database with Write-ahead-logging (WAL) -> `spv_state.db` (might not be seen on the github repository since /data/logs is added to .gitignore 😳)

### 5. Preparation & Minor Adjustments

Renamed `rpc_proxy.py` to `helios_proxy.py` to pave way for the similar rpc proxy program for BTC SPV (endpoint load balancer with some other cool features). Also moved both `helios_manager.py` & `helios_rpc.py` to `/core/engines/helios/` for better organization. Also made lots of research and architectural design (that will involve lots of changes), I'm starting to feel a bit of migraine so I'll just document it all tomorrow.

## 06/20:

Earlier, before the current stable helios module that the program has today, I needed to go through several revisions, refactoring, and on occasions... A full start from scratch due to errors and architectural mistakes. Unfortunately with the recent `btc_spv.py`, I feel like I'm doing the same mistaken by not researching well enough all of the possible edge cases when it comes to the cryptography and BTC blockchain mechanics, and more importantly, the load balancing and failover architecture that I should design (since it also relies on RPCs like helios, though I am planning to add support for direcr P2P and full node in the future). In addition, I feel like it's not modular enough to be maintainable and easy to develop, thus, I have rethinked my approach and decided to start it once again (better and more proper this time). Here are the strict requirements that I am abiding with:

1. **Automatic Block Detection:** The program will be designed to implement the stratum protocol (`blockchain.headers.subscribe`) via persistent TPC sockets to receive input instantly once a block is mined, eliminating the HTTP polling latency.

2. **RPC Multiplexing:** Basically, instead of chosing a primary endpoint and querying it every once in a while, I now plan to to be wherein all of electrum endpoints on the active pool are used. The first valid header to be received will be used while the subsequent delayed headers of the same height will be dropped.

3. **Pool SafeGuard:** Earlier (`btc_spv.py`), when an endpoint provides an invalid header, the program just rotates to the next endpoint without removing that potentially malicious RPC to another pool. This time, if an endpoint pushes an invalid header, it is banished into the dead pool.

4. **True PoW Verification + Target Checking:** Basically parses the `bits` field from the raw 80 bytes header to calculate the exact target threshold $SHA256(SHA256(header))$.

5. **2016 Block Rule (Difficulty Retargeting):** This was actually the mainflaw that a collegue of me pointed out on the original design of the BTC SPV module, I was too naive to realize that the program was actually relying or putting its trust on the RPC. I plan on implemeting the "epoch math" to locally calculate the network's supposed difficulty adjustments (requires 2016 block boundary) -> $NewTarget = OldTarget \times \frac{ActualTime}{2016 \times 10 \text{ minutes}}$

6. **Database Pruning:** I only plan on keeping 3000 blocks to ensure that we abide by the 2016 block rule and allow flexibility for possibly historical window retargeting.

7. **Catch Up Sync Feature:** On boot, the program should evaluate the tip of the SQLite database and execute a bulk fetch of the historical headers to bridge the gap of the current tip and the latest network block.

8. **Network Split Cases:** This is actually one of the main QoL of the plan, basically, from time to time, it happens wherein two miners find a block at the exact same time... The network splits in this case (temporarily), an endpoint may push, for example, block A, then a few moments later, the network agrees on block B. The program should be flexible enough to handle this instances by continously verifying that `previous_block_hash` matches the tip, and if a split thus happens, it should also be able to delete the invalid block and reconstruct the chain from the fork.

9. **Modularity:** Exactly why I restructured the `/engines` directory earlier, I am planning to create a separate folder alongside `/helios` to host both `spv_core.py` (handles cryptographic math and SQLite) as well as `btc_proxy.py` (handles the TCP multiplexing, load balancing, failovers, and other stuff.)

10. **Unified WebSocket Integration:** Gonna refactor ws_subscriber.py so SPV can stream alongside ETH and Base.

---

### 1. Added the refactored `spv_core.py` (partial)

In summary, this initial commit contains mostly the cryptography and math functions to parse raw hexadecimal headers into dictionaries, verify PoW (proof of work) against the parsed `bits` target, and to of course calculate the 2016 block difficulty retarget epoch limits.

### 2. Added `test_spv.py` (for `engines/spv`)

Though it would be the perfect time to add the preliminary math testing module for the SPV programs. Added multiple tests divided into classes (`TestSPVMathCryptography(unittest.TestCase)`, `TestDifficultyTargets(unittest.TestCase)`, and `TestRetargetingEpochs(unittest.TestCase)`). Found this error upon running the program:

<details>
<summary>test_spv.py logs:</summary>

```text
(.venv) slcls@SLCLS:~/WORKSPACE/GITHUB/alea$ python -m unittest tests.test_spv
.....F...
======================================================================
FAIL: test_calculate_next_work_required_max_bound (tests.test_spv.TestRetargetingEpochs.test_calculate_next_work_required_max_bound)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/slcls/WORKSPACE/GITHUB/alea/tests/test_spv.py", line 84, in test_calculate_next_work_required_max_bound
    self.assertEqual(new_target, self.base_target * 4)
AssertionError: 26959946667150639794667015087019630673637144422540572481103610249215 != 107838141164045237972625905378895965344043594954296656344551092387840

----------------------------------------------------------------------
Ran 9 tests in 0.007s

FAILED (failures=1)
```
</details>

### 3. Fixes on `spv_core.py`

Took me a bit to understand what is happening in here, so basically, we used `GENESIS_BITS` to run the test, it operates at difficulty = 1 (mathematically the highest possible target / easiest difficulty allowed). The program correctly applied the x4 bound constraint but by multiplyinhg the genesis target by 4, it pushes the integer out of bounds (which btw exceeds the max limit of bitcoin protocol). Added these fixes:

  - Changed `MAX_TARGET` value from `0x00000000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF` to `0x00000000FFFF0000000000000000000000000000000000000000000000000000`.
  - Replaced the `test_calculate_next_work_required_max_bound(self)` function on `test_spv.py` with `test_calculate_next_work_required_absolute_ceiling(self)` and `test_calculate_next_work_required_relative_x4_limit(self)`.

## 06/21:

### 1. Added the State Management to `spv_core.py`

After finally passing the test for the math module, I added the `SPVState` class which wraps the math functions added earlier around an SQLite database. As a summary of its major features, it has `process_new_header` that checks if every raw string pushed by the network has a valid PoW, chronologically mapped to the previous hash, and respects the epoch math. Also added the pruning mechanisim planned earlier (see `prune_ancient_blocks`) baed on the defined `retention_limit` set to 3000 blocks. Plus lots of other features like self-healing forks (`_handle_reorg`) and the 2016 rule execution, see it for yourself!

## 06/22:

### 1. Added State Management tests to `test_spv.py`

Kindly check out the 3 new added classes to the program -> `TestSPVStateManagement(unittest.TestCase)`, `TestSPVStateReorganizations(unittest.TestCase)`, and `TestSPVStateRetargetingAndPruning(unittest.TestCase)`. To summarize most of it's coverage, it contains `test_genesis_block_insertion` that validates the bootstrapping logic when the node boots from the genesis block. `test_invalid_pow_rejection` to check if malicious input are properly rejected. `test_sequential_chaining_and_stale_rejection` that covers the core telemetry. `test_chain_split_rollback` as the name suggest. `test_automated_pruning_execution` that generates an artificial chain of 100 blocks, triggers the prune flag, and execute raw SQLite row count, and some more, just check it out 🙏.

### 2. Fixed Sibling Block blindspot

Upon running `test_spv.py`, I got this error:

<details>
<summary>test_spv.py logs:</summary>

```text
(.venv) slcls@SLCLS:~/WORKSPACE/GITHUB/alea$ python -m unittest tests.test_spv
...........[SPV] SECURITY ALERT: Invalid PoW for header at expected height 1!
.[SPV] Gap detected. Tip is 1, received 3. Requires Catch-Up Sync.
.F..
======================================================================
FAIL: test_chain_split_rollback (tests.test_spv.TestSPVStateReorganizations.test_chain_split_rollback)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/usr/lib/python3.11/unittest/mock.py", line 1378, in patched
    return func(*newargs, **newkeywargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/slcls/WORKSPACE/GITHUB/alea/tests/test_spv.py", line 165, in test_chain_split_rollback
    self.assertTrue(success)
AssertionError: False is not true

----------------------------------------------------------------------
Ran 16 tests in 0.068s

FAILED (failures=1)
```
</details>

The test simulates a BTC network split at **Height 11**, the database already accepted the first one (`orphan_11`), making the current `tip['height']` equal to 11. It took me a while to understand what's happening but this is the traceback analogy:

- `if expected_height == tip['height'] + 1:` wherein 11 == 12 is evaluated as **false**.
- `if expected_height <= tip['height']:` wherein 11 <= 11 is evaluated as **true**.
- The program categorizes the valid tip as an old/stale block and returns **false**.

I'm actually very happy about this catch, it would be worse if this was encountered during production.

Added a fix to `spv_core.py` that breaks apart the `<` and `=` operators in the stale block check so that the engine can route same height conflicts to `_handle_reorg` function.

## 06/23:

### 1. Error fix on the recent test

Applied the fix yesterday, booted the test suite, and encountered this error:

<details>
<summary>test_spv.py logs:</summary>

```text
(.venv) slcls@SLCLS:~/WORKSPACE/GITHUB/alea$ python -m unittest tests.test_spv
...........[SPV] SECURITY ALERT: Invalid PoW for header at expected height 1!
.[SPV] CHAIN SPLIT DETECTED at height 1. Initiating localized rollback...
F[SPV] CHAIN SPLIT DETECTED at height 11. Initiating localized rollback...
======================================================================
FAIL: test_sequential_chaining_and_stale_rejection (tests.test_spv.TestSPVStateManagement.test_sequential_chaining_and_stale_rejection)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/usr/lib/python3.11/unittest/mock.py", line 1378, in patched
    return func(*newargs, **newkeywargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/slcls/WORKSPACE/GITHUB/alea/tests/test_spv.py", line 138, in test_sequential_chaining_and_stale_rejection
    self.assertFalse(success_stale)
AssertionError: True is not false

----------------------------------------------------------------------
Ran 16 tests in 0.010s

FAILED (failures=1) 
```
</details>

It seems like it was a logic error that I overlooked earlier. `test_sequential_chaining_and_stale_rejection` pushes a block at the same height as the tip but with a different hash and expected it to be `False`. `test_chain_split_rollback` on the other hand pushes block at the same heigh as well, with a different hash, but expected it to overwrite the tip as a "chain split". The changes earlier violated `test_sequential_chaining_and_stale_rejection`, and I've made some changes to `spv_core.py` and `test_spv.py` to fix this:

- Stale Block is mathematically older than the tip (`expected_height < tip['height']`). Gonna update the test to push a block that is genuinely older, rather than a same-height sibling.
- Lateral Reorg (Sibling Block) occurs at the exact same height (`expected_height == tip['height']`). Gonna accept this and overwrite the tip.
- Deep Reorg (Heavier Chain) occurs when the incoming block is `tip['height'] + 1`, but the `prev_hash` does not match the tip. If our tip is proven to be an orphan, we'll delete it and return False so the program initiates a Catch-Up Sync.

### 2. Added initial `btc_proxy.py`

This program, as mentioned earlier, shall serve as a multiplexer that handles the RPC management, load balancing, and failovers. It fully abides by the requirements planned earlier including the:

```
2. **RPC Multiplexing:** Basically, instead of chosing a primary endpoint and querying it every once in a while, I now plan to to be wherein all of electrum endpoints on the active pool are used. The first valid header to be received will be used while the subsequent delayed headers of the same height will be dropped.
```

As well as the Catch-Up Reserve (HTTP) wherein wndpoints starting with http will be filtered out of the live pool and safely stored in a separate pool. Implemented to use lightning-fast bulk fetches to sync the SQLite database before we open the live Stratum sockets.

### 3. Network Management for SPV

Here's the current ports planned to be occupied by the project:

  - `43200` -> ETH Proxy (Execution)
  - `43201` -> ETH Proxy (Consensus)
  - `43202` -> BASE Proxy (Execution)
  - `43203` -> BTC Proxy (HTTP Reserve)
  - `43210` -> Helios ETH Verified Output
  - `43211` -> Helios BASE Verified Output
  - `43212` -> BTC Verified Output