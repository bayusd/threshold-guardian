#!/usr/bin/env python3
"""Threshold Guardian loop test.

Alternates the oracle price below/above the Guardian threshold and measures
end-to-end latency: PriceUpdated event (Base Sepolia) -> react() (Lasna)
-> Vault pause/unpause callback (Base Sepolia).

Reads PRIVATE_KEY from the environment (source scripts/env.sh first).
Saves per-run results to scripts/loop-results.json.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

BASE_RPC = "https://sepolia.base.org"
LASNA_RPC = "https://lasna-rpc.rnk.dev/"
ORACLE = "0xe0555a2e9567cae8B9bfdb64Df86aa29cF9D689f"
VAULT = "0xDf7D6eC96cB079A0F8Cd9cD640fAE92278081168"
GUARDIAN = "0xAa3da8619c52134D652b501C02A61171AE8DBbAA"
SYSTEM = "0x8888888888888888888888888888888888888888"
WALLET = os.environ["WALLET"]

TOPIC_PRICE = "0x945c1c4e99aa89f648fbfe3df471b916f719e16d960fcec0737d4d56bd696838"
TOPIC_PAUSED = "0x5f2cfc49bb83f4aa2d271f5b3d4f060545ca449fe428d665d32b9dbe7bbfd76d"
TOPIC_UNPAUSED = "0x18355710024d8f7f134ebd5f4b33bb90dfbc3e70d37be0c5ddda35b2a7c71488"
TOPIC_BREACH = "0x31623823e9936905130436deb548a77f66041e0bfd18b4257f64d63f7d955e09"
TOPIC_RECOVER = "0xa1c19abd77a56b77b5ffe9a794e4aff113ca45604ef67573d2fb293a1fe71b05"

RESULTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "loop-results.json")


def rpc(url, method, params, tries=4):
    payload = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "cast/1.10.0"},
        method="POST",
    )
    last_err = None
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                out = json.load(r)
            if "error" in out:
                raise RuntimeError(f"{method} failed: {out['error']}")
            return out["result"]
        except Exception as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{method} failed after {tries} tries: {last_err}")


def cast(*args):
    p = subprocess.run(["cast", *args], capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        raise RuntimeError(
            f"cast {' '.join(args[:3])} failed: stderr={p.stderr.strip()[:200]} stdout={p.stdout.strip()[:200]}"
        )
    return p.stdout.strip()


def cast_call(addr, sig, rpc_url, *args):
    return cast("call", addr, sig, *args, "--rpc-url", rpc_url)


def paused():
    v = cast_call(VAULT, "paused()", BASE_RPC)
    return v.endswith("1")


def guardian_reserves():
    v = cast_call(SYSTEM, "reserves(address)", LASNA_RPC, GUARDIAN)
    return int(v, 16)


def wallet_lreact():
    v = cast("balance", WALLET, "--rpc-url", LASNA_RPC)
    return int(v)  # cast balance prints decimal wei


def top_up_reserves(amount_wei):
    print(f"  top-up reserves {amount_wei / 1e18:.3f} lREACT ...", flush=True)
    out = cast(
        "send", SYSTEM, "depositTo(address)", GUARDIAN,
        "--value", str(amount_wei), "--rpc-url", LASNA_RPC,
        "--private-key", os.environ["PRIVATE_KEY"],
    )
    assert "status" in out and "1 (success)" in out, out[:300]
    print("  top-up ok", flush=True)


def set_price(price_wei):
    out = cast(
        "send", ORACLE, "setPrice(uint256)", str(price_wei),
        "--rpc-url", BASE_RPC, "--private-key", os.environ["PRIVATE_KEY"], "--json",
    )
    tx = json.loads(out)
    assert tx.get("status") in ("0x1", 1), out[:300]
    bn = tx["blockNumber"]
    ev_block = int(bn, 16) if isinstance(bn, str) else bn
    return tx["transactionHash"], ev_block


def block_ts(rpc_url, block_number):
    # via cast (raw eth_getBlockByNumber is flaky through the egress proxy)
    out = cast("block", str(block_number), "--rpc-url", rpc_url)
    for line in out.splitlines():
        if line.startswith("timestamp "):
            return int(line.split()[1])
    raise RuntimeError(f"no timestamp in cast block output: {out[:200]}")


def block_number(rpc_url):
    try:
        return int(rpc(rpc_url, "eth_blockNumber", []), 16)
    except Exception:
        return int(cast("block-number", "--rpc-url", rpc_url))


def find_log(rpc_url, address, topic, from_block, to_block="latest"):
    try:
        return rpc(rpc_url, "eth_getLogs", [{
            "address": address,
            "fromBlock": hex(from_block),
            "toBlock": to_block,
            "topics": [topic],
        }])
    except Exception:
        # fallback: cast logs (same log dict shape)
        to_dec = int(to_block, 16) if isinstance(to_block, str) and to_block.startswith("0x") else to_block
        out = cast(
            "logs", "--from-block", str(from_block), "--to-block", str(to_dec),
            "--address", address, "--rpc-url", rpc_url, "--json",
        )
        return json.loads(out)


def wait_paused(expected, timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if paused() == expected:
            return time.time() - t0
        time.sleep(2)
    raise TimeoutError(f"vault did not reach paused={expected} within {timeout}s")


def run_crossing(i, breach):
    """One crossing. breach=True: price 40 (pause). breach=False: price 60 (unpause)."""
    price = 40 * 10**18 if breach else 60 * 10**18
    action = "BREACH->pause" if breach else "RECOVER->unpause"
    print(f"\n--- run {i}: {action} (price {price // 10**18}) ---", flush=True)
    # top up reserves if low (one react() costs ~0.02 lREACT)
    res = guardian_reserves()
    print(f"  guardian reserves: {res / 1e18:.4f} lREACT", flush=True)
    if res < 25 * 10**15:
        if wallet_lreact() > 60 * 10**15:
            top_up_reserves(50 * 10**15)
        else:
            print("  WARNING: reserves low and wallet cannot top up", flush=True)
    t_send = time.time()
    tx_hash, ev_block = set_price(price)
    ev_ts = block_ts(BASE_RPC, ev_block)
    print(f"  event tx {tx_hash} block {ev_block} ts {ev_ts}", flush=True)
    wait_s = wait_paused(breach)
    print(f"  vault paused={breach} after {wait_s:.1f}s of polling", flush=True)
    # callback event on Base Sepolia (public RPC caps eth_getLogs at 200 blocks).
    # Logs are permanent on-chain, so retry patiently instead of failing the run.
    topic = TOPIC_PAUSED if breach else TOPIC_UNPAUSED
    logs = []
    for attempt in range(6):
        try:
            logs = find_log(BASE_RPC, VAULT, topic, ev_block, hex(ev_block + 199))
            if logs:
                break
        except Exception as e:
            print(f"  callback-log fetch attempt {attempt + 1} failed: {str(e)[:120]}", flush=True)
        time.sleep(10)
    assert logs, "callback event not found after retries"
    cb = logs[0]
    cb_block = int(cb["blockNumber"], 16)
    cb_ts = block_ts(BASE_RPC, cb_block)
    cb_tx = cb["transactionHash"]
    # react() tx on Lasna (search back <=200 blocks; Lasna ~1s blocks). Best effort.
    lasna_now = block_number(LASNA_RPC)
    rtopic = TOPIC_BREACH if breach else TOPIC_RECOVER
    rlogs = []
    for attempt in range(3):
        try:
            rlogs = find_log(LASNA_RPC, GUARDIAN, rtopic, max(lasna_now - 199, 0), hex(lasna_now))
            if rlogs:
                break
        except Exception as e:
            print(f"  react-log fetch attempt {attempt + 1} failed: {str(e)[:120]}", flush=True)
        time.sleep(5)
    react_tx, react_ts = None, None
    if rlogs:
        r = rlogs[-1]
        react_tx = r["transactionHash"]
        react_ts = block_ts(LASNA_RPC, int(r["blockNumber"], 16))
    result = {
        "run": i,
        "action": action,
        "price": price // 10**18,
        "event_tx": tx_hash,
        "event_block": ev_block,
        "event_ts": ev_ts,
        "react_tx": react_tx,
        "react_ts": react_ts,
        "callback_tx": cb_tx,
        "callback_block": cb_block,
        "callback_ts": cb_ts,
        "latency_event_to_callback_s": cb_ts - ev_ts,
        "latency_event_to_react_s": (react_ts - ev_ts) if react_ts else None,
        "latency_react_to_callback_s": (cb_ts - react_ts) if react_ts else None,
        "poll_wait_s": round(wait_s, 1),
    }
    print(f"  react tx {react_tx} ts {react_ts}", flush=True)
    print(f"  callback tx {cb_tx} block {cb_block} ts {cb_ts}", flush=True)
    print(f"  LATENCY event->callback: {cb_ts - ev_ts}s", flush=True)
    return result


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    results = []
    if os.path.exists(RESULTS_PATH):
        results = json.load(open(RESULTS_PATH))
    start_run = len(results) + 1
    print(f"starting from paused={paused()}, {len(results)} prior runs recorded", flush=True)
    for k in range(n):
        i = start_run + k
        breach = not paused()  # if vault open -> breach; if paused -> recover
        try:
            r = run_crossing(i, breach)
        except Exception as e:
            print(f"  FAILED run {i}: {type(e).__name__}: {e}", flush=True)
            r = {"run": i, "action": "FAILED", "error": f"{type(e).__name__}: {e}"}
            results.append(r)
            json.dump(results, open(RESULTS_PATH, "w"), indent=2)
            break
        results.append(r)
        json.dump(results, open(RESULTS_PATH, "w"), indent=2)
    ok = [r for r in results if "latency_event_to_callback_s" in r]
    if ok:
        lats = sorted(r["latency_event_to_callback_s"] for r in ok)
        print(f"\n=== {len(ok)} successful crossings ===")
        print(f"latencies (s): {lats}")
        print(f"p50: {lats[len(lats) // 2]}s  min: {lats[0]}s  max: {lats[-1]}s")


if __name__ == "__main__":
    main()
