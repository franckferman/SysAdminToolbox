<div align="center">

<a href="https://github.com/franckferman/SysAdminToolbox">
  <img src="https://raw.githubusercontent.com/franckferman/SysAdminToolbox/stable/docs/github/graphical_resources/Logo-Without_background-SysAdminToolbox.png" alt="SysAdminToolbox logo" width="320">
</a>

*Network administration suite - calculations, diagnostics, and configuration helpers.*

Zero runtime Python dependencies. Standard library only.

</div>

## About

SysAdminToolbox provides network calculations, operational checks, and configuration generation through a single-file Python command-line interface.

- **Conversions** - Binary, decimal, hexadecimal, IPv4, masks, CIDR, wildcards, and IANA address classification.
- **Address planning** - IPv4/IPv6 subnetting, VLSM, ranges, containment, exclusion, indexed addresses, overlap checks, supernets, and inventory audits.
- **Diagnostics** - Read-only host, filesystem, inode, service, Nginx, firewall, listener, DNS, TCP/UDP, TLS, HTTP, and local network checks.
- **Batch operations** - Files or standard input, bounded concurrency, per-target results, and text, JSON, NDJSON, or CSV output.
- **MAC utilities** - Normalization, generation, address properties, and optional vendor lookup from a locally cached IEEE OUI registry.
- **Configuration** - Platform-aware VLAN and ACL generators for Cisco, Juniper, and Huawei.
- **Reference** - VLAN, ACL, firewall, routing, and NAT cheatsheets with optional provenance and explicitly separated legacy material.
- **AI assistant (optional)** - Ask questions, explain output, or suggest a command through a local Ollama or a cloud provider (Anthropic, OpenAI, DeepSeek, Kimi). Standard library only, opt-in.
- **Web UI (optional)** - Serve the safe command groups and cheatsheets in a local browser.

## Installation

Requires Python 3.9 or newer.

### Direct download

```bash
curl -fsSLO https://raw.githubusercontent.com/franckferman/SysAdminToolbox/stable/src/SysAdminToolbox/SysAdminToolbox.py
python3 SysAdminToolbox.py --version
```

### pip

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install https://github.com/franckferman/SysAdminToolbox/archive/refs/heads/stable.zip
SysAdminToolbox --version
```

### Source

```bash
git clone https://github.com/franckferman/SysAdminToolbox.git
cd SysAdminToolbox
python3 src/SysAdminToolbox/SysAdminToolbox.py --version
```

The calculations use only Python. Some diagnostics use operating-system commands when available:

| Function | Command |
| --- | --- |
| Ping and ping sweep | `ping` |
| Traceroute and ASN enrichment | `traceroute`, `tracert`, and `dig` |
| WHOIS | `whois` |
| Advanced DNS, DNSSEC, and delegation checks | `dig`, with a limited `nslookup` fallback |
| Local network snapshot | `ip`, `ifconfig`, `route`, or `ipconfig` |
| System and service diagnostics | `systemctl`, `journalctl`, `rc-service`, `service`, `launchctl`, `sc`, `timedatectl`, `chronyc`, `ntpq`, or `w32tm` |
| Listener and disk analysis | `ss` or `netstat`, plus optional `du` |
| Nginx diagnostics | `nginx`, plus optional `getenforce` and security-context output from `ls` |
| Host-firewall diagnostics | `ufw`, `firewall-cmd`, `nft`, `iptables`, `ip6tables`, Windows PowerShell, or `pfctl` when available |

## Usage

```text
SysAdminToolbox <command> <operation> [arguments] [options]
```

```bash
SysAdminToolbox convert ipclass 100.64.0.1
SysAdminToolbox subnet calc 192.168.1.42/24
SysAdminToolbox doctor system
SysAdminToolbox doctor nginx --url http://127.0.0.1 --host-header example.com
SysAdminToolbox doctor firewall 80,443
SysAdminToolbox net doctor https://example.com
SysAdminToolbox net wait database.internal 5432 --timeout 60
SysAdminToolbox vendor profiles
SysAdminToolbox cheat vlan trunk --show-sources
```

Run `SysAdminToolbox --help` or `SysAdminToolbox <command> --help` for the complete built-in reference. Run `SysAdminToolbox -i` for the interactive REPL.

### Command families

| Command | Operations |
| --- | --- |
| `convert` (`c`) | Base and address conversions, `ipinfo`, `ipclass` |
| `subnet` (`s`) | `calc`, `adv`, `vlsm`, `range`, `contains`, `exclude`, `nth`, `overlap`, `supernet`, `audit` |
| `ipv6` (`v6`) | `expand`, `compress`, `tobin`, `type`, `subnet`, `ula` |
| `mac` (`m`) | `info`, `format`, `normalize`, `vendor`, `generate`, `oui-update` |
| `net` (`n`) | `doctor`, `wait`, `cert-audit`, `dns-health`, `local`, plus focused network checks |
| `doctor` (`diag`, `diagnose`) | `system`, `nginx`, `service`, `disk`, `network`, `firewall` |
| `vendor` (`v`) | `profiles`, `vlan`, `acl` |
| `cheat` (`cs`) | `vlan`, `acl`, `huawei`, `mikrotik`, `firewall`, `routing`, `nat` |
| `ai` | `ask`, `explain`, `suggest`, `run`, `diagnose`, `agent` - opt-in, local Ollama or a cloud provider |
| `web` | Local browser UI for the safe command groups and cheatsheets |

## Address planning and IPAM checks

```bash
# Address details and stable IANA special-purpose classification
SysAdminToolbox convert ipinfo 192.168.1.42/24
SysAdminToolbox convert ipclass 192.0.2.10
SysAdminToolbox convert ipclass 2001:db8::10 --json

# Subnet calculations
SysAdminToolbox subnet adv 192.168.1.0/24 26
SysAdminToolbox subnet adv 2001:db8::/32 48 --limit 32
SysAdminToolbox subnet vlsm 192.168.1.0/24 50 30 10
SysAdminToolbox subnet range 192.168.1.10 192.168.1.35
SysAdminToolbox subnet contains 10.0.0.0/8 10.20.30.40
SysAdminToolbox subnet exclude 10.0.0.0/24 10.0.0.64/26
SysAdminToolbox subnet nth 2001:db8::/64 1000
SysAdminToolbox subnet overlap 10.0.0.0/24 10.0.0.128/25
SysAdminToolbox subnet supernet 10.0.0.0/25 10.0.0.128/25
```

`subnet adv` calculates the exact subnet count without materializing every IPv6 network. It displays at most 256 detail rows by default; use `--limit` to change that bound.

`subnet audit` accepts JSON, CSV, or one-CIDR-per-line text. It detects invalid and duplicate allocations, overlaps, allocations outside a parent, insufficient host capacity, and free space.

```json
{
  "parent": "10.20.0.0/16",
  "allocations": [
    {"name": "users", "network": "10.20.0.0/23", "requested_hosts": 400},
    {"name": "servers", "network": "10.20.2.0/24", "requested_hosts": 120}
  ]
}
```

```bash
SysAdminToolbox subnet audit inventory.json --json
SysAdminToolbox subnet audit allocations.csv 10.20.0.0/16
```

The audit exits with status 1 when it finds an issue, which makes it suitable for validation jobs.

## Operational diagnostics

### Host and application diagnostics

The top-level `doctor` command follows an explicit diagnostic path without changing the host. Every result contains the ordered methodology, the status of each step, skipped checks and their dependencies, observations, findings, and ranked cause candidates. A candidate remains a hypothesis until the evidence proves it. The command never starts or reloads a service, edits configuration, changes ownership or permissions, deletes data, or remounts a filesystem.

The workflow follows the evidence and hypothesis cycle described in Google's [Effective Troubleshooting](https://sre.google/sre-book/effective-troubleshooting/). Network checks use Cisco's documented [bottom-up OSI method](https://www.cisco.com/cisco/web/docs/iam/unified/ipt611/System_Troubleshooting_Methodology.html), while application doctors replace a rigid OSI walk with the dependency order of the application being inspected.

Provide the observation and recent change when they are known. This keeps the snapshot tied to the reported problem instead of treating every unusual metric as causal:

```bash
SysAdminToolbox doctor system \
  --symptom "API latency increased at 14:20 UTC" \
  --expected "health endpoint below 200 ms" \
  --recent-change "application release at 14:10 UTC"
```

```bash
# Overall host state: CPU/load, memory, pressure stalls, disk capacity,
# inodes, mounts, failed services, routing, DNS, and listeners
SysAdminToolbox doctor system

# Add a bounded top-level disk-usage scan
SysAdminToolbox doctor system /var --du

# Capacity, inode exhaustion, read-only mounts, and largest entries
SysAdminToolbox doctor disk /var --du

# Generic service state and exit information, optionally correlated with its port
SysAdminToolbox doctor service postgresql --port 5432

# Bottom-up interface, addressing, route, DNS, TCP, and optional HTTP/TLS path
SysAdminToolbox doctor network database.internal --port 5432
SysAdminToolbox doctor network https://app.example.com/health

# Host firewall discovery and cautious inbound TCP-port correlation
SysAdminToolbox doctor firewall 80,443
```

`doctor network` proceeds bottom-up: interface/link evidence, local addressing and routing prerequisites, name resolution, route selection for the resolved address, transport, then TLS/HTTP when the target is a URL. A failed DNS step explicitly skips target-route and transport checks instead of producing misleading secondary failures.

`doctor firewall` discovers the host controls available on the current platform and correlates only the requested inbound TCP ports. On Linux it understands UFW application profiles, active firewalld zones and services, nftables input-hook chains, and IPv4/IPv6 iptables INPUT rules. It also supports Windows Firewall profiles and rules through PowerShell and PF on macOS and BSD. The result distinguishes an observed allow, an observed deny, a default-deny policy without a direct allow, an inactive firewall, insufficient privileges, and an indeterminate ruleset. It never invokes `sudo` or changes policy.

Some platforms restrict ruleset inspection to root or an account with equivalent capabilities. SysAdminToolbox uses the privileges of the current process: run it normally from an existing root session, or let the operator explicitly elevate only the diagnostic that needs it. For example:

```bash
sudo SysAdminToolbox doctor firewall 80,443
sudo python3 ./SysAdminToolbox.py doctor firewall 80,443

# When installed in a user-owned virtual environment, use its absolute path
sudo /absolute/path/to/.venv/bin/SysAdminToolbox doctor firewall 80,443
```

`sudo -E` is unnecessary. Without sufficient access, the command returns `firewall_inspection_limited` and keeps the port verdict `indeterminate`. Even UID 0 may remain restricted inside a container without the required network capability or when the relevant rules belong to another network namespace. Log contents remain opt-in when an Nginx or service diagnostic is elevated.

These are local-host observations, not a proof of end-to-end reachability. Cloud security groups, provider firewalls, routers, load balancers, container or network namespaces, source restrictions, interface selection, rule order, jumps, sets, and state tracking can change the effective result. The tool therefore reports cautious evidence such as `potentially_blocked` instead of claiming that a port is certainly open or closed. UFW is treated as a frontend and may appear beside its nftables or iptables backend. See the official [Ubuntu UFW guide](https://documentation.ubuntu.com/server/how-to/security/firewalls/index.html), [firewalld documentation](https://firewalld.org/documentation/man-pages/firewall-cmd.html), [nftables ruleset operations](https://wiki.nftables.org/wiki-nftables/index.php/Operations_at_ruleset_level), and [iptables manual](https://man7.org/linux/man-pages/man8/iptables.8.html).

`doctor nginx` follows an application-specific dependency path: host capacity, service manager plus running-process correlation, bounded service logs, binary discovery, `nginx -t`, expanded active configuration from `nginx -T`, configured logs, IP and Unix listeners, host-firewall correlation for configured TCP ports, a direct virtual-host probe, and the relevant content/security-policy path. It branches its recommendations for TLS failures, connection failures, redirects, 401, 403, 404, and upstream-oriented 502/503/504 responses.

```bash
SysAdminToolbox doctor nginx
SysAdminToolbox doctor nginx --config /etc/nginx/nginx.conf
SysAdminToolbox doctor nginx \
  --url http://127.0.0.1/health \
  --host-header app.example.com

# Connect locally while selecting and validating the HTTPS virtual host by SNI
SysAdminToolbox doctor nginx \
  --url https://127.0.0.1/health \
  --host-header app.example.com \
  --sni app.example.com
```

When `--sni` is omitted for HTTPS, the SNI name follows `--host-header`, then the URL hostname. The socket always connects directly to the URL address: environment proxies are ignored. Redirects are recorded but not followed unless `--follow-redirects` is explicit. `--insecure` disables certificate verification only for that probe and makes the overall result a warning.

Its findings distinguish common failure classes such as invalid includes, missing roots or certificates, 403 policy and path traversal errors, 404 virtual-host or deployment mismatches, unavailable upstreams, bind collisions, timeouts, full filesystems, inode exhaustion, file-descriptor exhaustion, and TLS file-loading errors. The expanded configuration is parsed in memory and is not printed, because it may contain credentials. Nginx officially defines `-t` as syntax and referenced-file validation and `-T` as the same validation plus a configuration dump; see the [command-line reference](https://nginx.org/en/docs/switches.html). This also discovers distribution-specific includes such as `/etc/nginx/sites-enabled/*` when they are part of the active configuration; the tool does not hard-code that Debian-specific layout.

`.htaccess` is an [Apache HTTP Server per-directory mechanism](https://httpd.apache.org/docs/current/en/howto/htaccess.html) and is intentionally not inspected by `doctor nginx`.

Log contents are never read by default. Select them explicitly and keep the sample narrow:

```bash
# Service journal only
SysAdminToolbox doctor service nginx --logs service --lines 50 --since "30 minutes ago"

# Nginx error and access logs plus the service journal
SysAdminToolbox doctor nginx --logs all --lines 100
```

Selected logs are capped at 500 lines per source and redact authorization headers, cookies, common secret parameters, and JWT-shaped values. Automatic service-journal collection uses `journalctl`; other service managers report that the application-specific log path must be selected manually. `--raw-logs` disables redaction and should be used only when the output remains in an approved location. Some checks need elevated read access, but the tool does not require or invoke `sudo` itself. Nginx validation opens referenced files, and an optional HTTP probe normally creates a regular access-log entry.

Log selectors are scope-specific: `doctor system` accepts `system`, `doctor service` accepts `service`, and `doctor nginx` accepts `service`, `error`, `access`, or `all`. Log content remains opt-in because a general diagnostic should not expose application data by default.

### Doctor and batch input

`net doctor` combines name resolution, TCP connectivity, TLS verification, certificate lifetime, the HTTP response, and security headers.

```bash
SysAdminToolbox net doctor https://example.com --timeout 5
SysAdminToolbox net doctor app.internal:8080 --json
```

For multiple endpoints, provide one target per line. Empty lines and lines beginning with `#` are ignored; duplicates are removed while preserving order.

```text
https://example.com
app.internal:8080
[2001:db8::10]:443
```

```bash
SysAdminToolbox net doctor --input targets.txt --workers 20 --format ndjson
printf '%s\n' example.com example.net | SysAdminToolbox net doctor --input - --format csv
```

Batch operations preserve input order, report errors per target, accept 1 to 256 workers, and cap input at 10,000 unique targets.

### Service readiness

```bash
SysAdminToolbox net wait database.internal 5432 --timeout 90 --interval 2
```

The command exits 0 when the TCP endpoint becomes ready and 1 when the deadline expires.

### Certificate audit

```bash
SysAdminToolbox net cert-audit example.com --warn-days 30
SysAdminToolbox net cert-audit --input tls-targets.txt --workers 20 --format csv
```

Each result includes verification state, validity dates, remaining days, SANs, TLS version, cipher, ALPN, and the SHA-256 certificate fingerprint. Expired, not-yet-valid, untrusted, and soon-expiring certificates produce a nonzero exit status.

### DNS health

```bash
SysAdminToolbox net dns-health example.com
SysAdminToolbox net dns-health example.com --dkim-selector mail --json
SysAdminToolbox net dns-health --input domains.txt --workers 10 --format ndjson
```

The check covers A, AAAA, CNAME, NS, SOA, MX, CAA, and TXT records, recursive and authoritative NS consistency, DNSSEC signals, SPF, DMARC, and an optional DKIM selector. Install `dig` for complete DNSSEC and authoritative checks.

### Local network snapshot and focused checks

```bash
SysAdminToolbox net local --json
SysAdminToolbox net ping 192.168.1.1
SysAdminToolbox net portscan 192.168.1.1 22 80 443
SysAdminToolbox net portscan-udp 192.168.1.1 53 161
SysAdminToolbox net traceroute-asn example.com
SysAdminToolbox net dns-type example.com MX
SysAdminToolbox net dns-compare example.com 1.1.1.1 8.8.8.8
SysAdminToolbox net certcheck example.com
SysAdminToolbox net headers https://example.com
```

Network-wide operations are capped at 4,096 hosts to prevent accidental memory or traffic spikes. Run active checks only against systems you administer or are authorized to test.

## MAC vendor lookup

No vendor data is embedded, so the single source file never ships a stale snapshot. Updating the database is explicit and stores the official IEEE MA-L CSV in the user cache.

```bash
SysAdminToolbox mac oui-update
SysAdminToolbox mac vendor 00:11:22:33:44:55

# Use a controlled database path instead of the default cache
SysAdminToolbox mac oui-update --db ./oui.csv
SysAdminToolbox mac vendor 00:11:22:33:44:55 --db ./oui.csv --json
```

Locally administered MAC addresses are identified before lookup because their first 24 bits are not a globally assigned vendor OUI.

## Platform-aware configuration and references

Current platform profiles are the default. Legacy profiles must be selected by name and explicitly enabled.

```bash
SysAdminToolbox vendor profiles
SysAdminToolbox vendor profiles --legacy

# Current Cisco IOS XE access and trunk examples
SysAdminToolbox vendor vlan cisco 100 Users Gi1/0/1 Gi1/0/2
SysAdminToolbox vendor vlan cisco 100 Users Gi1/0/48 \
  --mode trunk --allowed-vlans 100,200-210 --native-vlan 999

# A maintained older Cisco IOS environment
SysAdminToolbox vendor vlan cisco 100 Users Gi0/1 \
  --platform cisco-ios --software-version 15.2 --mode trunk --legacy

SysAdminToolbox vendor acl juniper BLOCK_WEB deny tcp 10.0.0.0/8 any 0 443
```

Generated configuration is a reviewed starting point, not an automatic deployment. Confirm interface names, platform syntax, policy order, software release, and change-control requirements before applying it.

Reference output uses current guidance by default:

```bash
SysAdminToolbox cheat vlan trunk
SysAdminToolbox cheat vlan trunk --show-sources
SysAdminToolbox cheat vlan --platform cisco-iosxe --show-sources
```

Use `--legacy` only when maintaining or migrating older environments:

```bash
SysAdminToolbox cheat vlan legacy_trunking --legacy --show-sources
SysAdminToolbox cheat vlan legacy_vtp --legacy --show-sources
```

Legacy entries are labeled with their status, target platform, replacement, and source. Current generators never emit ISL; the old protocol remains available only as a clearly marked compatibility reference.

## AI assistant (optional)

The `ai` command is opt-in and adds no dependencies - it uses the standard library and only reaches the network when you run it. It prefers a local Ollama (private) and otherwise falls back to the first configured cloud provider.

```bash
SysAdminToolbox ai ask "what is a /29 useful for"
SysAdminToolbox ai suggest "split 10.0.0.0/24 into 4 subnets"
SysAdminToolbox net cert-audit example.com --json | SysAdminToolbox ai explain
```

Beyond question-answering, the AI can drive the tool itself:

- `ai run "<request>"` turns a natural-language request into a single SysAdminToolbox command and runs it (after a confirmation).
- `ai diagnose <target>` runs a fixed battery of read-only checks (DNS, ping, TLS, HTTP headers, traceroute) and narrates a root-cause assessment.
- `ai agent "<goal>"` is an autonomous loop: the model calls read-only SysAdminToolbox commands, reads their JSON, and iterates until it can conclude. It runs read-only commands only, prints each one before running it, is bounded by `--max-steps` (default 8), and `--dry-run` prints the plan without executing. Add `--json` for a machine-readable report of the goal, each step's command and output, and the final conclusion.

```bash
SysAdminToolbox ai run "check the TLS certificate of example.com"
SysAdminToolbox ai diagnose example.com --symptom "site is slow"
SysAdminToolbox ai agent "why can I not reach example.com on 443"
SysAdminToolbox ai agent "plan a VLSM scheme for 50, 30 and 10 hosts" --dry-run
SysAdminToolbox ai agent "how many usable hosts in 172.16.0.0/22" --json | jq .conclusion
```

Choose a provider with `--provider` (`auto` by default): `ollama`, `anthropic`, `openai`, `deepseek`, or `kimi`, optionally `provider:model`. API keys are read from the environment only and are never stored - `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `MOONSHOT_API_KEY`; local Ollama uses `OLLAMA_HOST`, and `LLM_TIMEOUT` sets the per-request timeout in seconds (raise it for slow local models). Before any cloud call the tool prints the provider, model, and a prompt digest and asks for confirmation; pass `--yes` to skip it, or keep everything private with a local Ollama.

## Web UI (optional)

The `web` command serves a small local interface for the safe command groups and cheatsheets. It binds `127.0.0.1` by default, runs each request through the same commands in an isolated subprocess behind a fixed whitelist, and never exposes the network diagnostics, `doctor`, or the `ai` command.

```bash
SysAdminToolbox web
SysAdminToolbox web --host 127.0.0.1 --port 8787
```

## Output and exit status

`--json` works before or after a command. Batch diagnostics additionally support `--format text`, `json`, `ndjson`, or `csv`. Colors disable automatically when output is redirected; `--no-color` and the `NO_COLOR` environment variable disable them explicitly.

```bash
SysAdminToolbox --json subnet calc 10.0.0.0/8
SysAdminToolbox subnet calc 10.0.0.0/8 --json | jq '.first_host'
SysAdminToolbox --no-color ipv6 type fd00::1
```

Exit status conventions:

- `0` - The command completed and no monitored issue was found.
- `1` - Validation failed, an operational check failed, or an audit reported an issue.
- `2` - Command-line syntax is invalid.
- `130` - The command was interrupted.

## Tests

The standard-library test suite covers calculations, validation, batch formats and ordering, IPAM audits, OUI handling, platform profiles, CLI behavior, diagnostic correlation and redaction, mocked external integrations, and loopback-only network checks.

```bash
python3 -m compileall -q src tests
python3 -W error -m unittest discover -s tests -v
```

CI installs the package and runs the suite on Python 3.9 through 3.14 on Linux, with additional Python 3.14 jobs on Windows and macOS. Two further workflows run on every source change: a flake8 correctness lint that flags unused imports, undefined names, and syntax errors, and a Bandit security scan.

## License

This project is licensed under the GNU Affero General Public License, Version 3.0. For more details, please refer to the LICENSE file in the repository: [Read the license on GitHub](https://github.com/franckferman/SysAdminToolbox/blob/stable/LICENSE).

## Contact

Franck Ferman - [GitHub](https://github.com/franckferman) - [contact@franckferman.fr](mailto:contact@franckferman.fr)
