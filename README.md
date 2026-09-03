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
- **Diagnostics** - Service readiness, DNS health, TCP/UDP checks, traceroute, WHOIS, TLS certificate audits, HTTP headers, and local network state.
- **Batch operations** - Files or standard input, bounded concurrency, per-target results, and text, JSON, NDJSON, or CSV output.
- **MAC utilities** - Normalization, generation, address properties, and optional vendor lookup from a locally cached IEEE OUI registry.
- **Configuration** - Platform-aware VLAN and ACL generators for Cisco, Juniper, and Huawei.
- **Reference** - VLAN, ACL, firewall, routing, and NAT cheatsheets with optional provenance and explicitly separated legacy material.

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

## Usage

```text
SysAdminToolbox <command> <operation> [arguments] [options]
```

```bash
SysAdminToolbox convert ipclass 100.64.0.1
SysAdminToolbox subnet calc 192.168.1.42/24
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
| `vendor` (`v`) | `profiles`, `vlan`, `acl` |
| `cheat` (`cs`) | `vlan`, `acl`, `huawei`, `mikrotik`, `firewall`, `routing`, `nat` |

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

The standard-library test suite covers calculations, validation, batch formats and ordering, IPAM audits, OUI handling, platform profiles, CLI behavior, mocked external integrations, and loopback-only network checks.

```bash
python3 -m compileall -q src tests
python3 -W error -m unittest discover -s tests -v
```

CI installs the package and runs the suite on Python 3.9 through 3.14 on Linux, with additional Python 3.14 jobs on Windows and macOS.

## License

SysAdminToolbox is available under the [MIT License](LICENSE).

## Contact

Franck Ferman - [GitHub](https://github.com/franckferman) - [contact@franckferman.fr](mailto:contact@franckferman.fr)
