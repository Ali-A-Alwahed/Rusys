# Security Policy

## 🔒 Supported Versions

| Version | Supported |
|---------|-----------|
| 26.10.x | ✅ |
| 26.9.x  | ⚠️ Security fixes only |
| < 26.9  | ❌ |

> Releases ≤ 26.9.9 were published under the custom "LGPT v1.0" license and
> depended on the now-floored `requests` versions. Prefer 26.10.14 or later.

## 🚨 Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report security issues **privately** to the maintainer:

- **Email:** Open a GitHub security advisory at [github.com/Ali-A-Alwahed/Rusys/security/advisories/new](https://github.com/Ali-A-Alwahed/Rusys/security/advisories/new)
- Or contact the Pro Tool maintainer (Ali A Alwahed) directly

Please include:

- A description of the impact and attack scenario
- Steps to reproduce
- Any relevant logs (Rusys logs all operations to its log widget / stderr)
- Your operating system and Rusys version

### Response Timeline

- **Acknowledgment:** Within 48 hours
- **Initial Assessment:** Within 5 business days
- **Resolution:** Depends on severity; critical issues are prioritized

## 🛡️ Safety Notes

### Dependency Security Posture

Runtime dependency floors exist specifically to keep known vulnerabilities out
of the shipped binary:

| Package | Minimum | Advisories cleared |
|---|---|---|
| `requests` | `>=2.34.2` | CVE-2026-25645, CVE-2024-47081, CVE-2024-35195, CVE-2014-1829 |
| `PySide6` | `>=6.12,<6.13` | — |
| `setuptools` (build only) | `>=83.0.0` | PYSEC-2026-3447 |

Reproduce the audit with:

```bash
pip install pip-audit
pip-audit -r requirements.txt          # declared floors
pip-audit                               # your resolved environment
```

Both are expected to report **no known vulnerabilities**.

### Network and TLS
- All HTTP sessions are created with certificate verification **enabled**
  (`Session.verify = True`); TLS validation is never disabled.
- Downloads are streamed and size-capped, and pages that merely look like HTML
  are rejected rather than being written out as an ISO.

### Device Writing
- Rusys writes **directly to block devices**. It refuses to write to a mounted device and validates the target size before writing.
- On Linux, writing to a real USB device requires root privileges. Rusys uses `pkexec` for single-prompt privilege escalation.

### Download Verification
- Downloads are verified against an expected **SHA-256** when provided.
- ISO images are inspected before use.
- CDN cookie sessions are properly managed to prevent download failures.

### Custom Operations
- Custom file operations (#322) execute shell commands supplied by the user. Only enable them if you trust the configured commands.

### Secure Boot
- Rusys includes a **PCA2011 Secure Boot revocation advisory** (#2244) that warns before writing old media that may not boot on systems with updated Secure Boot keys.
- The Ventoy multiboot backend uses its own signed shim + MOK-enrolled GRUB for Secure Boot compatibility.

---

<div align="center">

**Security is taken seriously. If you find a vulnerability, please report it responsibly.**

</div>
