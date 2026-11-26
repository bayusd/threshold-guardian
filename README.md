# Threshold Guardian

**Autonomous stop-loss / circuit-breaker for a vault, powered by Reactive Network.**

Built for the [Reactive Omni Buildathon](https://dorahacks.io/hackathon/reactive-omni-buildathon/detail)
(DoraHacks, 5 Nov – 5 Dec 2026), track **Set It and Forget It**.

Set a price threshold once — and forget it. When the price of the vault's asset
falls below the threshold, a reactive contract on Lasna notices the oracle event
and pauses the vault on Base Sepolia automatically. When the price recovers, it
unpauses it. No bots, no keepers, no manual intervention.

## How it works

```
MockPriceOracle (Base Sepolia)          Guardian (Lasna)              Vault (Base Sepolia)
  setPrice(40) ──PriceUpdated──▶  react() checks threshold
  price 40 < threshold 50            │ requestCallback(pause)
                                      └────────────▶ Vault.pause()
                                                     withdrawals blocked
  setPrice(60) ──PriceUpdated──▶  react() sees recovery
                                      └────────────▶ Vault.unpause()
                                                     withdrawals open again
```

Three contracts, one loop, zero off-chain automation:

| Contract | Chain | Address |
| --- | --- | --- |
| `MockPriceOracle` | Base Sepolia (84532) | `0xe0555a2e9567cae8B9bfdb64Df86aa29cF9D689f` |
| `Guardian` (reactive) | Lasna (5318007) | `0xAa3da8619c52134D652b501C02A61171AE8DBbAA` |
| `Vault` (callback) | Base Sepolia (84532) | `0xDf7D6eC96cB079A0F8Cd9cD640fAE92278081168` |

- **Oracle** emits `PriceUpdated(uint256 price, uint256 updatedAt)` on every price
  change. The Guardian subscribes to it via the Reactive system contract
  (`0x8888888888888888888888888888888888888888`).
- **Guardian** (`AbstractReactive`) implements `react(LogRecord)` with
  `onlySystem`. It decodes the price and applies hysteresis: one pause callback
  per crossing below threshold, one unpause callback per recovery. Repeated
  below-threshold events do not spam callbacks.
- **Vault** (`AbstractCallback`) only accepts `pause`/`unpause` through the
  Base Sepolia callback proxy (`0x476F44b11F5C942c58f4c8E3d0300E5710743585`)
  from the authorized Guardian — both guards, always (`onlyServiceProvider` +
  `onlyCallbackSender`).

## Measured loop latency

End-to-end latency = `PriceUpdated` block timestamp → callback block timestamp
(both on Base Sepolia, same clock). Measured live, 27 Nov 2026 — **17 crossings,
17/17 succeeded: 11× 1 s, 6× 2 s; p50 1 s, min 1 s, max 2 s.**

Full loop-test log (all 17 runs with event / `react()` / callback tx hashes):
[`scripts/loop-results.json`](scripts/loop-results.json).

<details>
<summary>All 17 loop runs (click to expand)</summary>

| Run | Action | Event → Callback |
| --- | --- | --- |
| 1 | breach → pause | 1 s |
| 2 | recover → unpause | 2 s |
| 3 | breach → pause | 1 s |
| 4 | recover → unpause | 1 s |
| 5 | breach → pause | 2 s |
| 6 | recover → unpause | 1 s |
| 7 | breach → pause | 1 s |
| 8 | recover → unpause | 2 s |
| 9 | breach → pause | 1 s |
| 10 | recover → unpause | 1 s |
| 11 | breach → pause | 1 s |
| 12 | recover → unpause | 1 s |
| 13 | breach → pause | 2 s |
| 14 | recover → unpause | 2 s |
| 15 | breach → pause | 1 s |
| 16 | recover → unpause | 2 s |
| 17 | breach → pause | 1 s |

</details>

Note: the `react()` tx lives on Lasna, whose block clock can run ~1 s ahead of
Base Sepolia's — a few runs show `react_ts` 1 s *before* `event_ts`. That is a
cross-chain clock skew, not a time machine. The headline metric above
(event → callback, both Base Sepolia) is unaffected.

## Deployment

Deployed 27 Nov 2026 from this repo (Foundry, solc 0.8.29):

| Step | Tx hash |
| --- | --- |
| Deploy `MockPriceOracle` (Base Sepolia) | `0xa98a32ed4994a4df163359288a1077fd9b8fd6f41ff2be54a4bf03f75e8655a2` |
| Faucet 0.001 ETH → 0.1 lREACT | `0xdc2179aeef184155e5e004641f86fa4850226658069298df80d1cb96038dd7fe` |
| Faucet 0.0032 ETH → 0.32 lREACT | `0x3c8ac33bcfb1478df8f84b65e569ce904bdfdd2bc00b8269058e006e2adec3fd` |
| Faucet 0.0004 ETH (Eth Sepolia) → 0.042 lREACT | `0x142dab25eaa169d88bbd4e2a2031d1289ccd92a79d0c28a837f5be0a13aebd07` |
| Deploy `Guardian` (Lasna) | `0x7232d915fe68927c815d0ee3f4fc920774c6a082b3fdaf30fb66289033ac034a` |
| Deploy `Vault` (Base Sepolia) | `0x227887ea1fea1e8df27b4dccb05417486cbfac2c922c87649708572d6f50a6c3` |
| `Guardian.setVault(Vault)` (Lasna) | see `broadcast/SetVault.s.sol/5318007/run-latest.json` |
| Fund Guardian reserves 0.3 lREACT (`depositTo`) | `0xb2838058783f9dcf8295feec3fdf7737ec1814cb90cafb8d8d5a56e4b54db7d5` |
| Fund Vault reserves 0.00005 ETH (`depositTo`) | `0xcddcc4a4ea9b82d2e4f7334150a515a14a113c47a2f47f89c52fe43dbd9289ca` |

A full loop (run 1): event
[`0xa9437e13cd80de341b38393c57c7ad9e08d6b586319fca08c01906c1b8551727`](https://sepolia.basescan.org/tx/0xa9437e13cd80de341b38393c57c7ad9e08d6b586319fca08c01906c1b8551727)
→ callback
[`0x91c46c0125576eb39d05105d1a0327b60bc4b008a4069f20c8cc2cf520a95a7c`](https://sepolia.basescan.org/tx/0x91c46c0125576eb39d05105d1a0327b60bc4b008a4069f20c8cc2cf520a95a7c).

## Economics (measured, not estimated)

Lasna gas price is a flat **100 gwei** — and the fee formula charges
`(gas_used + 100,000) × gas_price` per `react()`, so a testnet budget needs
real arithmetic (early estimates in the scope doc were 1000× too low; the
numbers below are what actually left the wallet):

| Item | Cost |
| --- | --- |
| Guardian deploy (Lasna) | ~0.075 lREACT |
| One `react()` (Guardian reserves) | ~0.015–0.020 lREACT |
| One callback (Vault reserves, Base Sepolia) | ~0.0000007 ETH |
| Guardian reserves for 17 crossings | 0.3 lREACT |

lREACT comes from the official faucet: send Sepolia ETH to
`0x2afaFD298b23b62760711756088F75B7409f5967` (Base Sepolia) or
`0x9b9BB25f1A81078C544C829c5EB7822d747Cf434` (Ethereum Sepolia) at
**1 ETH → 100 lREACT**.

## Reproduce

```bash
# Prereqs: Foundry (forge/cast). Libraries are vendored under lib/ (pinned):
#   reactive-lib-omni @ 3ade0dcf1d27e67e5783ef807e73a1b9e0c0cce8
#   forge-std        @ 15b2df92a05d4d2f76a06653872fefb287e0e01c
forge build
forge test            # 22 unit tests, all green

# Deploy (needs a funded testnet key in PRIVATE_KEY; see scripts/env.sh)
source scripts/env.sh
forge script script/DeployOracle.s.sol   --rpc-url $BASE_SEPOLIA_RPC --broadcast --private-key $PRIVATE_KEY
ORACLE_ADDRESS=<oracle> forge script script/DeployGuardian.s.sol --rpc-url $LASNA_RPC --broadcast --private-key $PRIVATE_KEY
GUARDIAN_ADDRESS=<guardian> forge script script/DeployVault.s.sol --rpc-url $BASE_SEPOLIA_RPC --broadcast --private-key $PRIVATE_KEY
GUARDIAN_ADDRESS=<guardian> VAULT_ADDRESS=<vault> forge script script/SetVault.s.sol --rpc-url $LASNA_RPC --broadcast --private-key $PRIVATE_KEY

# Fund reserves, then trigger a loop:
cast send $SYSTEM "depositTo(address)" <guardian> --value 0.3ether --rpc-url $LASNA_RPC --private-key $PRIVATE_KEY
cast send $CALLBACK_PROXY_BASE "depositTo(address)" <vault> --value 0.00005ether --rpc-url $BASE_SEPOLIA_RPC --private-key $PRIVATE_KEY
cast send <oracle> "setPrice(uint256)" 40ether --rpc-url $BASE_SEPOLIA_RPC --private-key $PRIVATE_KEY
# ...watch Vault.paused() flip to true within seconds.
```

Loop-test harness (alternating breach/recover, latency log):
```bash
source scripts/env.sh
python3 scripts/loop_test.py 10   # results -> scripts/loop-results.json
```

## Status page

[`docs/status.html`](docs/status.html) — a static page that reads the live
state (oracle price, Guardian, Vault, reserves) straight from the public RPCs,
no login. Serve it anywhere static.

## Security notes

- Testnet only. No mainnet funds, no real value.
- `Vault.pause`/`unpause` are double-guarded (proxy + Guardian address).
- `Guardian.react` is `onlySystem`; non-matching logs fall through without
  reverting (a reverting `react()` is still billed).
- The Guardian never holds user funds; the Vault's ledger is mock accounting
  for the demo.

## License

MIT — see [LICENSE](LICENSE).
