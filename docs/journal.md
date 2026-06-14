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

## 06/13 to 06/14:

Had to take some break due to an emergency yesterday, but we're finally back on business and I've made some useful debugging:

- Definitely made some logic errors on the for loop, the logs says it is rotating the pool but the end-points query (including those on the logs) remains the same.
- Helios sessions are terminated each time that the pool rotates, and it seems like the header signature on the chainsafe query is getting flagged and block after a number of reboots.
- `Base endpoints exhausted. No backups remain.` probably due to repeated ethereum node termination (base relies on that for the consensus).