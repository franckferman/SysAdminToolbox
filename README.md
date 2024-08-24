<div id="top" align="center">

[![Contributors][contributors-shield]](https://github.com/franckferman/SysAdminToolbox/graphs/contributors)
[![Forks][forks-shield]](https://github.com/franckferman/SysAdminToolbox/network/members)
[![Stargazers][stars-shield]](https://github.com/franckferman/SysAdminToolbox/stargazers)
[![Issues][issues-shield]](https://github.com/franckferman/SysAdminToolbox/issues)
[![License][license-shield]](https://github.com/franckferman/SysAdminToolbox/blob/stable/LICENSE)

<a href="https://github.com/franckferman/SysAdminToolbox">
  <img src="https://raw.githubusercontent.com/franckferman/SysAdminToolbox/stable/docs/github/graphical_resources/Logo-Without_background-SysAdminToolbox.png" alt="SysAdminToolbox Logo" width="auto" height="auto">
</a>

<h3 align="center">SysAdminToolbox</h3>
<p align="center">
    <em>Network administration suite - calculations, diagnostics, and configuration helpers.</em>
    <br>
    Zero external dependencies. Python 3 stdlib only.
</p>

</div>

## Table of Contents

<details open>
  <summary><strong>Click to collapse/expand</strong></summary>
  <ol>
    <li><a href="#about">About</a></li>
    <li><a href="#installation">Installation</a></li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#commands">Commands</a></li>
    <li><a href="#troubleshooting">Troubleshooting</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
  </ol>
</details>

## About

SysAdminToolbox is a self-contained CLI tool for network administrators. It consolidates subnet calculations, base conversions, IPv6 utilities, network diagnostics, MAC address analysis, vendor configuration helpers, and cheatsheets into a single script with zero pip dependencies.

### Features

**Conversions** - Decimal, binary, hexadecimal, IP, mask, CIDR, wildcard conversions in all directions.

**Subnet calculations** - Subnet calculator, advanced subnetting (IPv4 + IPv6), VLSM, supernet aggregation, overlap detection.

**IPv6** - Expand, compress, binary conversion, type identification, subnet calculator.

**Network diagnostics** - Ping, TCP port scan (single ports or ranges), traceroute, WHOIS, DNS/reverse DNS lookups.

**MAC address** - Normalize, format (colon/dash/cisco/bare), OUI extraction, unicast/multicast/LAA detection.

**Vendor helpers** - VLAN and ACL configuration generators for Cisco, Juniper, Huawei.

**Cheatsheets** - Cisco VLAN, Cisco ACL, Huawei VLAN, MikroTik VLAN, Firewall (Palo Alto, Fortinet, iptables, nftables), Routing (static, OSPF, BGP), NAT.

**Output** - ANSI colored terminal output (auto-detects TTY), JSON mode (`--json`), interactive REPL (`-i`).

## Installation

**Requirements:** Python >= 3.9

```bash
git clone https://github.com/franckferman/SysAdminToolbox.git
cd SysAdminToolbox
python3 src/SysAdminToolbox/SysAdminToolbox.py --version
```

Or install as a package:

```bash
pip install .
SysAdminToolbox --version
```

## Usage

The tool uses **subcommands** organized by category:

```
SysAdminToolbox <command> <operation> [arguments] [--json] [--no-color]
```

Run without arguments to see the banner and help. Use `-i` for interactive mode:

```bash
python3 src/SysAdminToolbox/SysAdminToolbox.py -i
```

```
 +-----------------------------------------+
 |  SysAdminToolbox  v3.0.0                |
 |  Network Administration Suite           |
 +-----------------------------------------+

sat > subnet calc 192.168.1.0/24
sat > net ping 8.8.8.8
sat > convert d2b 42
sat > help
sat > exit
```

## Commands

### `convert` (alias: `c`)

Base and format conversions.

| Operation | Example |
|---|---|
| `d2b` | `convert d2b 42` |
| `b2d` | `convert b2d 10101010` |
| `d2h` | `convert d2h 255` |
| `h2d` | `convert h2d ff` |
| `b2h` | `convert b2h 11111111` |
| `h2b` | `convert h2b ff` |
| `iptobin` | `convert iptobin 192.168.1.1` |
| `bintoip` | `convert bintoip 11000000.10101000.00000001.00000001` |
| `m2c` | `convert m2c 255.255.255.0` |
| `c2m` | `convert c2m 24` |
| `m2w` | `convert m2w 255.255.255.0` |
| `w2m` | `convert w2m 0.0.0.255` |
| `c2w` | `convert c2w 24` |
| `w2c` | `convert w2c 0.0.0.255` |

### `subnet` (alias: `s`)

Subnet calculations.

```bash
# Basic subnet calculator
subnet calc 192.168.1.0/24
subnet calc 10.0.0.1 255.255.0.0

# Advanced subnetting (IPv4 and IPv6)
subnet adv 192.168.1.0/24 26
subnet adv 2001:db8::/32 48

# VLSM
subnet vlsm 192.168.1.0/24 50 30 10

# Check overlap
subnet overlap 192.168.1.0/24 192.168.1.128/25

# Find smallest supernet
subnet supernet 192.168.1.0/26 192.168.1.64/26 192.168.1.128/25
```

### `ipv6` (alias: `v6`)

IPv6 utilities.

```bash
ipv6 expand ::1
ipv6 compress 2001:0db8:0000:0000:0000:0000:0000:0001
ipv6 tobin fe80::1
ipv6 type fe80::1          # -> link-local
ipv6 subnet 2001:db8::/32
```

### `net` (alias: `n`)

Network diagnostics, scanning, and reconnaissance.

```bash
# Ping
net ping 8.8.8.8
net pingsweep 192.168.1.0/24

# Port scanning
net portscan 192.168.1.1 22 80 443
net portscan 192.168.1.1 20-25
net portscan-adv 192.168.1.1 top20
net portscan-adv 192.168.1.1 22 80 443 banner
net portscan-udp 192.168.1.1 53 161
net portscan-net 192.168.1.0/24 22
net banner 192.168.1.1 80

# Traceroute
net traceroute google.com
net traceroute-asn google.com          # with ASN/country per hop

# DNS
net dns example.com
net dns-type google.com MX
net dns-type google.com TXT 8.8.8.8    # query specific server
net dns-compare google.com 8.8.8.8 1.1.1.1
net dns-axfr example.com
net rdns 8.8.8.8
net rdns-sweep 192.168.1.0/24

# TLS / HTTP
net certcheck google.com
net certcheck google.com 8443          # custom port
net headers https://google.com

# Local network
net arp
net whois google.com
```

### `mac` (alias: `m`)

MAC address utilities.

```bash
mac info AA:BB:CC:DD:EE:FF
mac format aa:bb:cc:dd:ee:ff cisco    # -> aabb.ccdd.eeff
mac format AA-BB-CC-DD-EE-FF bare     # -> aabbccddeeff
mac normalize aabb.ccdd.eeff          # -> aa:bb:cc:dd:ee:ff
mac vendor AA:BB:CC:DD:EE:FF
```

### `vendor` (alias: `v`)

Generate vendor-specific configuration commands.

```bash
vendor vlan cisco 10 Engineering Gi0/1-15
vendor vlan juniper 10 Engineering
vendor vlan huawei 100 MGMT GE0/0/1 GE0/0/2
vendor acl cisco BLOCK deny tcp 192.168.1.0/24 any 0 80
```

### `cheat` (alias: `cs`)

Configuration cheatsheets.

```bash
cheat vlan              # all Cisco VLAN sections
cheat vlan trunk        # specific section
cheat acl
cheat huawei
cheat mikrotik
cheat firewall          # Palo Alto, Fortinet, iptables, nftables
cheat firewall iptables # specific vendor
cheat routing           # static, OSPF, BGP
cheat routing ospf
cheat nat
cheat nat cisco_pat
```

### Global flags

| Flag | Description |
|---|---|
| `--json` | Output in JSON format (works with any command) |
| `--no-color` | Disable ANSI colors |
| `--version` | Show version |
| `-i` | Interactive REPL mode |

```bash
# JSON output
subnet calc 10.0.0.0/8 --json
net ping 8.8.8.8 --json

# Pipe-friendly
subnet calc 10.0.0.0/8 --json | jq '.first_host'
```

## Troubleshooting

Encountering issues? [Submit an issue on GitHub](https://github.com/franckferman/SysAdminToolbox/issues).

Some commands require system tools:
- `net traceroute` requires `traceroute` (`apt install traceroute`)
- `net whois` requires `whois` (`apt install whois`)
- `net ping` requires `ping` (usually pre-installed)

<p align="right">(<a href="#top">Back to top</a>)</p>

## Contributing

Contributions, feedback, and suggestions are welcome. Feel free to open an issue or submit a pull request.

<p align="right">(<a href="#top">Back to top</a>)</p>

## License

This project is licensed under the GNU Affero General Public License, Version 3.0. See the [LICENSE](https://github.com/franckferman/SysAdminToolbox/blob/stable/LICENSE) file.

<p align="right">(<a href="#top">Back to top</a>)</p>

## Contact

[![ProtonMail][protonmail-shield]](mailto:contact@franckferman.fr)
[![LinkedIn][linkedin-shield]](https://www.linkedin.com/in/franckferman)
[![Twitter][twitter-shield]](https://www.twitter.com/franckferman)

<p align="right">(<a href="#top">Back to top</a>)</p>

[contributors-shield]: https://img.shields.io/github/contributors/franckferman/SysAdminToolbox.svg?style=for-the-badge
[forks-shield]: https://img.shields.io/github/forks/franckferman/SysAdminToolbox.svg?style=for-the-badge
[stars-shield]: https://img.shields.io/github/stars/franckferman/SysAdminToolbox.svg?style=for-the-badge
[issues-shield]: https://img.shields.io/github/issues/franckferman/SysAdminToolbox.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/franckferman/SysAdminToolbox.svg?style=for-the-badge
[protonmail-shield]: https://img.shields.io/badge/ProtonMail-8B89CC?style=for-the-badge&logo=protonmail&logoColor=blueviolet
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=for-the-badge&logo=linkedin&colorB=blue
[twitter-shield]: https://img.shields.io/badge/-Twitter-black.svg?style=for-the-badge&logo=twitter&colorB=blue
