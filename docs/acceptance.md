# Acceptance run

Open two terminals in the repository root. Start the simulator first:

```text
python -m dns_proxy.upstream_server
```

Start the proxy in the second terminal:

```text
python -m dns_proxy
```

Use the T1-T12 inputs from the assignment consecutively. The simulator prints one `Request #N` line only for domains that reach Upstream. T13 is a separate run after changing `sinkhole_ip=10.0.0.1` and `cache_enabled=false`.

Install the package once with `python -m pip install -e .`. The automated checks are:

```text
python -m unittest discover -s tests -v
```

The optional real DNS mode is enabled by setting `real_dns_enabled=true`, `upstream_ip=8.8.8.8` or `1.1.1.1`, and `upstream_port=53`. It uses a raw DNS A query and stores the returned IPv4 address and TTL.
