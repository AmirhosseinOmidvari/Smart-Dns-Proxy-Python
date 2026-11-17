# Smart DNS Proxy

This repository implements the first phase of the Computer Networks course project in Python. It is a console DNS Proxy with a deterministic decision pipeline, a raw UDP text protocol for the simulated Upstream, a local TTL cache, and optional real DNS resolution.

## Requirements

Python 3.10 or newer is required. The mandatory path uses only the Python standard library. Install the package in editable mode once:

```text
python -m pip install -e .
```

## Run

The working directory must be the repository root because `config.txt` is loaded from the current directory.

Start the simulator in the first terminal:

```text
python -m dns_proxy.upstream_server
```

Start the proxy in the second terminal:

```text
python -m dns_proxy
```

The proxy prints `DNS Proxy ready.`, accepts one domain per line, and exits on `exit`. The commands `stats`, `reload`, and `cache` are implemented as optional controls.

## Decision order

Every domain is trimmed, validated, lowercased, and stripped of one final dot. Matching is exact or label-boundary subdomain matching. The order is:

1. Ad list to `sinkhole_ip`.
2. Sanction list to `proxy_ip`.
3. A valid unexpired cache entry.
4. One UDP request to Upstream.

A domain present in both lists is an `AD_BLOCK`. List decisions never contact Upstream. Only successful Upstream responses with a positive TTL are cached.

## Files

`config.txt` contains all addresses, ports, timeouts, TTL values, list paths, and feature switches. List files contain one domain per line; blank lines and lines beginning with `#` are ignored. Invalid list lines produce a warning and do not terminate the program.

The mandatory simulated protocol is `QUERY <domain>` followed by `OK <ip> <ttl>` or `NOT_FOUND`. A timeout, socket error, malformed response, or non-positive TTL produces `SERVER_ERROR` without retrying.

## Result format

Every domain input produces exactly this five-line block, followed by one blank line:

```text
Domain : <normalized name>
Source : AD_BLOCK | SANCTION | CACHE | UPSTREAM | NONE
Status : OK | NOT_FOUND | SERVER_ERROR | INVALID_INPUT
IP : <ip address> or -
TTL : <seconds> or -
```

## Optional features

`stats` prints total requests, decision counts, and errors. `reload` rereads both list files without restarting. `cache` prints valid entries as `domain | ip | remaining_seconds`, deleting expired entries. `log.txt` receives one pipe-delimited record for every domain request. `cache_max_entries` enables FIFO eviction. `real_dns_enabled=true` switches Upstream to a raw UDP DNS A-record query and preserves the real returned TTL.

## Verification

Run:

```text
python -m unittest discover -s tests -v
```

Then execute T1-T12 with the sample files and simulator, and execute T13 in a fresh run after changing the two configuration values specified by the assignment. Keep the final console transcript in `test_results.txt`.

## Team contribution

The repository owner implements the policy core, normalization, configuration, and TTL cache. Mahdis implements the UDP transports, simulator, and real DNS packet parser. Matin implements the console, optional controls, logging, automated tests, acceptance notes, and release verification. All members should be able to explain their modules and the end-to-end decision order during delivery.
