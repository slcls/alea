import asyncio
import json
import logging
import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger("Alea.WSSubscriber")
logging.basicConfig(
    level=logging.INFO,
    format="[ %(levelname)s ] %(asctime)s | %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)

async def subscribe_new_heads(network: str, ws_url: str):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_subscribe",
        "params": ["newHeads"]
    }

    while True:
        try:
            logger.info(f"[{network.upper()}] Attempting WS connection to {ws_url}...")

            async with websockets.connect(
                ws_url,
                ping_interval=20,
                ping_timeout=20,
                max_size=10_485_760
                ) as ws:

                await ws.send(json.dumps(payload))

                sub_response_raw = await ws.recv()
                sub_response = json.loads(sub_response_raw)

                if "result" in sub_response:
                    logger.info(f"[{network.upper()}] Successfully subscribed to newHeads! Sub ID: {sub_response['result']}")
                else:
                    logger.error(f"[{network.upper()}] Subscription failed: {sub_response}")
                    continue

                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)

                    if "method" in data and data["method"] == "eth_subscription":
                        header = data["params"]["result"]
                        block_number = int(header.get("number", "0x0"), 16)
                        block_hash = header.get("hash")

                        logger.info(f"[{network.upper()}] NEW BLOCK: {block_number} | HASH: {block_hash}")

        except (ConnectionRefusedError, ConnectionClosed) as e:
            logger.warning(f"[{network.upper()}] WS Connection lost or refused ({e}). Helios might be syncing or dead. Retrying in 5s...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"[{network.upper()}] Unexpected WS error: {e}. Retrying in 5s...")
            await asyncio.sleep(5)

async def main():
    eth_task = asyncio.create_task(subscribe_new_heads("ethereum", "ws://127.0.0.1:43210"))
    base_task = asyncio.create_task(subscribe_new_heads("base", "ws://127.0.0.1:43211"))

    logger.info("[ SYSTEM ] Global WebSocket Subscriber Active.")
    await asyncio.gather(eth_task, base_task)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n[ SYSTEM ] WS Subscriber cleanly terminated.")