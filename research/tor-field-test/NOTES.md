# Tor field test — 17 Nov 2026

These are the measurements behind blueprint §3.3. Only well-known legitimate onion services were contacted.

| File | Contents |
|---|---|
| `tor_field_test.py` | E1 fetch latency, E2 circuit isolation, E3 descriptor probes (HSFETCH) |
| `desc_decrypt.py` | Decrypts cached descriptors (needs `stem` and `cryptography`) to read intro points, `pow-params` and flags |
| `fetch_and_isolation_results.json` | E1 and E2 results. Its E3 block is invalid: the event listener crashed on that run. |
| `descriptor_probe_results.json` | Valid E3 results from the rerun |

Descriptor decryption results (printed by `desc_decrypt.py`, PoW seeds omitted):

| Site | Intro points | pow-params | Flags |
|---|---|---|---|
| torproject | 8 | none | create2-formats 2 |
| duckduckgo | 10 | none | single-onion-service, flow-control 1-2 31 |
| bbc | 3 | none | single-onion-service, flow-control 1-2 31 |
| securedrop | 3 | v1, effort 0 | flow-control 1-2 31 |
| ahmia | 10 | none | flow-control 1-2 31 |

## Re-running

1. Start your own tor with a private torrc: `SocksPort 127.0.0.1:19050`, `ControlPort 127.0.0.1:19051`, `CookieAuthentication 1`, and a `DataDirectory` of `tordata` next to these scripts.
2. Run `python tor_field_test.py`.
3. To run only the descriptor probes, set `LIB_ONLY_DESC=1`.
4. If tor runs somewhere else, set `LIB_SOCKS`, `LIB_CTRL` and `LIB_COOKIE` to point at it.
