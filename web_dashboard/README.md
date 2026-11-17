# Relay DNS dashboard

Run the local dashboard from the repository root with Python 3.10 or later.

```cmd
py -3 web_dashboard\server.py
```

On macOS or Linux, use `python3 web_dashboard/server.py`. Open <http://127.0.0.1:8080> and keep the terminal running. Press Ctrl+C to shut it down. The dashboard uses the Python standard library and serves its assets locally.

With the default `config.txt`, the dashboard starts its own UDP simulator at `127.0.0.1:5354`. Use **Settings → Local simulator** to start or stop it for testing. If the CLI simulator already owns the port, the dashboard can send queries to that process. Stop it in its own terminal before starting the dashboard's simulator.

- **Resolver** looks up domains and shows the IPv4 address, TTL, elapsed time, and decision path. Press `/` to focus the lookup field. Counts are for the dashboard session.
- **DNS Cache** shows live TTL values and FIFO capacity. Repeat `normal.example.net` within its five-second TTL to see a cache hit.
- **Policy Lists** edits the two lists in `config.txt` and reloads them. Use `ads.example.com` and `service.example.org` to test the sample rules.
- **Activity** filters the last 60 entries from the shared `log.txt` by domain, source, or status. Select a domain from the log or cache to fill the resolver field.
- **Settings** updates `config.txt` for both modes. It retains the configured list paths, which can be changed directly in the file. Saving settings clears the dashboard's in-memory cache and keeps its session counts. Restart other running CLI sessions to load the new settings.
- **Real DNS** is selected in Settings. Choose **Use default address and port** to fill `1.1.1.1:53`, save, then look up a real domain such as `example.com`. This mode requires network access to the configured UDP DNS server.

The dashboard binds to the local loopback address. Its web runtime keeps an independent cache and counters from any separately running console instance.
