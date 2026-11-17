# Private Windows research server

This guide deploys the merged application into **a separate research checkout** on the
Windows PC's existing WSL2 Ubuntu installation. The repository implements these procedures;
cloud acceptance does not configure Windows, Tailscale, remote storage or the canonical
collector. See the [deployment acceptance packet](../data/deployment-review/20261117/README.md)
for executed checks and remaining physical gates. No command enables exchange submission.

The research service binds `127.0.0.1:43128`. Windows Tailscale Serve terminates private HTTPS
and supplies verified identity headers. The application additionally requires the exact
owner login, exact HTTPS audience, CSRF and an owner passphrase session for every private
API read, download and mutation. Cookies are Secure, HttpOnly and SameSite=Strict; sessions
expire after 30 minutes and disappear on restart. Direct loopback callers are trusted host
software: this is not isolation from a malicious Windows/WSL account administrator.

## Inspect the physical installation first

Run in PowerShell as the Windows user who owns the existing Ubuntu distribution:

```powershell
wsl.exe --version
wsl.exe --list --verbose
Get-Command tailscale.exe
& tailscale.exe status
& tailscale.exe serve status --json
wsl.exe -d Ubuntu -- /usr/bin/ps -p 1 -o comm=
wsl.exe -d Ubuntu -- /usr/bin/systemctl --version
```

Replace `Ubuntu` throughout with the **observed** distribution name. WSL must be version 2,
with systemd PID 1, systemd >=249 and working user mount namespaces. Existing collector
units/tasks stay untouched. If these prerequisites fail, plan a separate maintenance window;
do not upgrade WSL, rewrite `/etc/wsl.conf`, terminate the distro or run global
`wsl --shutdown` while its collector is running. Use the **Windows** Tailscale client only;
a second `tailscaled` inside WSL is refused by preflight. Tailscale HTTPS/MagicDNS must be
enabled for the tailnet. Do not enable Funnel or open a router/firewall port for 43128.

Record the existing collector checkout and scheduled task/unit status without changing them.
Expected exclusion: `~/Projects/EntropyTrade-collector`, canonical `data/cache/chain`.
Research cannot run inside that checkout, canonical chain paths or symlink aliases.

## Prepare the research checkout and private configuration

In an ordinary WSL terminal, choose a reviewed merged commit and an exact Python release.
The software was tested on Python 3.13.14; this example pins that release. Install `uv`,
GnuPG and Git through your reviewed installation procedure if absent. Preflight checks GPG
features (including bounded `--max-output`), rather than upgrading Ubuntu or assuming a
particular GPG version. Cloud crypto acceptance used GnuPG 2.4.7.

```bash
umask 077
mkdir -p "$HOME/Projects"
git clone https://github.com/GabeSternberg/EntropyTrade.git "$HOME/Projects/EntropyTrade-research"
cd "$HOME/Projects/EntropyTrade-research"
git checkout --detach REVIEWED_FULL_MERGED_COMMIT
uv sync --frozen --no-dev --python 3.13.14
mkdir -p data/cache/research data/backups data/recovery
mkdir -p "$HOME/.config/entropytrade-research"
chmod 700 "$HOME/.config/entropytrade-research"
.venv/bin/python -m entropytrade.api.owner init \
  --file "$HOME/.config/entropytrade-research/owner.json" --owner-id owner
```

Owner initialization prompts locally twice and refuses overwriting an existing verifier.
Use a unique passphrase; neither it nor exchange credentials belong in provider variables.
Store `provider.env` as a private 0600 file in that same directory. Empty is valid for
explicit offline templates. Supported unquoted `KEY=value` names are `GEMINI_API_KEY`,
`ENTROPYTRADE_RESEARCH_ANTHROPIC_API_KEY`, `ENTROPYTRADE_RESEARCH_OPENAI_API_KEY`,
`ENTROPYTRADE_RESEARCH_API_KEY`, `ENTROPYTRADE_LOCAL_LLM_URL` and
`ENTROPYTRADE_LOCAL_LLM_KEY`. Do not use `export`, shell expansion or quotes around values.
The launch environment discards ambient exchange/provider variables. Selected API providers
report missing credentials rather than falling back. Actual authenticated inference is a
separate physical acceptance check with a bounded research budget.

Generate the backup recipient on a **separate recovery machine**. Keep the encrypted secret
key and its passphrase off the server; retain two offline copies and record the complete
primary fingerprint independently. For example, in an isolated private GPG home:

```bash
umask 077
gpg --full-generate-key
gpg --with-colons --fingerprint RECOVERY_KEY_ID
gpg --armor --export FULL_PRIMARY_FINGERPRINT > recipient.asc
# A NEW path on offline media; never transfer this secret export to the server.
(set -o noclobber; gpg --armor --export-secret-keys FULL_PRIMARY_FINGERPRINT > /PRIVATE/OFFLINE-MEDIA/secret-UNIQUE.asc)
```

Choose an encryption-capable key (or encryption subkey), an expiry you will maintain and a
strong passphrase. Transfer only its public export into
`~/.config/entropytrade-research/recipient.asc`, verify its full primary fingerprint against
the independent record, and chmod it 0600. The tool rejects private packets, multiple primary
keys, mismatched pins and currently unusable/expired/revoked recipients. Keep encryption
subkey renewals backed up on the recovery machine before updating the server public key.

Create the deployment JSON below outside both checkouts. Substitute the actual absolute
paths, observed Tailscale DNS name and exact account login. `uv` is the absolute executable
returned by `command -v uv`; its path must not traverse symlinks. The Python interpreter leaf
may be uv's normal symlink, but `.venv` and its directories must belong to this checkout.

```bash
(set -o noclobber; : > "$HOME/.config/entropytrade-research/provider.env")
chmod 600 "$HOME/.config/entropytrade-research/"{provider.env,recipient.asc}
git rev-parse HEAD
sha256sum uv.lock
command -v uv
.venv/bin/python -c 'import platform; print(platform.python_version())'
```

```json
{
  "checkout": "/home/YOU/Projects/EntropyTrade-research",
  "collector_checkout": "/home/YOU/Projects/EntropyTrade-collector",
  "owner_file": "/home/YOU/.config/entropytrade-research/owner.json",
  "provider_env": "/home/YOU/.config/entropytrade-research/provider.env",
  "recipient_file": "/home/YOU/.config/entropytrade-research/recipient.asc",
  "recipient_fingerprint": "FULL_PRIMARY_FINGERPRINT",
  "private_origin": "https://WINDOWS-HOST.TAILNET.ts.net",
  "tailscale_owner": "YOUR_EXACT_TAILSCALE_LOGIN@example.com",
  "commit": "FULL_40_CHARACTER_COMMIT",
  "uv_lock_sha256": "64_CHARACTER_SHA256_WITHOUT_PREFIX",
  "uv": "/home/YOU/.local/bin/uv",
  "python_version": "3.13.14"
}
```

Use a lowercase FQDN without a trailing dot, port or slash in `private_origin`.
Save as `~/.config/entropytrade-research/deployment.json`, mode 0600. These four distinct
configuration files need a 0700, user-owned parent and cannot be symlinks. Pins verify HEAD,
tracked changes, untracked application source, lock hash, interpreter and installed frozen
production dependencies before service launch or maintenance. Updates require a stopped
research service, reviewed code/environment, updated pins and rerun preflight; the service
never pulls Git or installs dependencies automatically.

Enable linger for **this ordinary WSL research user only**, then preflight and render:

```bash
sudo loginctl enable-linger "$(id -un)"
.venv/bin/python -m entropytrade.operations.research_server doctor \
  --config "$HOME/.config/entropytrade-research/deployment.json"
.venv/bin/python -m entropytrade.operations.research_server render \
  --config "$HOME/.config/entropytrade-research/deployment.json" \
  --output "$HOME/.config/entropytrade-research/rendered-v1"
systemd-analyze --user verify "$HOME/.config/entropytrade-research/rendered-v1/"*.service \
  "$HOME/.config/entropytrade-research/rendered-v1/"*.timer
mkdir -p "$HOME/.config/systemd/user"
install -m 600 "$HOME/.config/entropytrade-research/rendered-v1/"* "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable --now entropytrade-research.service
systemctl --user status entropytrade-research.service
ss -ltnp 'sport = :43128'
```

Inspect the rendered units before installing. They have a read-only home/system, explicit
research-only writable paths, an inaccessible collector checkout, private namespaces,
no capabilities, bounded restarts and a 330-second SIGINT shutdown budget. A static unit
parse is tested; successful namespace/start/stop on the actual WSL version is still required.
Never remove hardening to force startup without diagnosing the failure. Logs:
`journalctl --user -u entropytrade-research.service -n 100 --no-pager`.

## Configure private HTTPS on Windows

Inspect `tailscale serve status --json` again. The following mapping is for an **unused**
443 slot on this Windows node; if another application owns it, stop and choose a separate
node/design. Do not reset all Serve configuration or overwrite an existing mapping.

```powershell
& tailscale.exe serve --bg --https=443 http://127.0.0.1:43128
& tailscale.exe serve status --json
curl.exe -i http://127.0.0.1:43128/api/owner
```

The direct unverified request must return 403. Confirm Windows localhost forwarding actually
reaches the WSL listener; no wildcard backend bind is permitted. If it does not, diagnose
WSL networking before proceeding. Do not rewrite external Host or invent forwarded login
headers. Serve strips incoming identity headers and injects its verified user login; the
backend ignores `X-Forwarded-*` as authority. Missing/tagged/Funnel identities and other
logins refuse even if a broad tailnet ACL accidentally admits them.

Configure the tailnet access policy so only your actual user can reach this node on 443.
The exact node/user selectors depend on your existing policy; edit and test that policy
without replacing unrelated rules. Validate both permitted and denied clients with the
Tailscale policy tester and an actual second identity. Device sharing is not owner identity.
From the Mac and phone on Tailscale, open the configured HTTPS origin, verify a trusted
certificate and log in through Operations. Research/history downloads should load only
after login. Test logout, expiry, restart invalidation, denied identity and cross-origin
requests; do not bypass TLS certificate errors to record a pass.

## Keep WSL alive across an unattended reboot

WSL systemd services alone do not keep its VM alive. Retain the collector's existing tasks.
Create a **new research-only** Windows startup task under the Windows account that owns the
WSL distribution, never SYSTEM or a different account. One reproducible example follows in
an elevated PowerShell terminal; it prompts through Windows for that account's password,
which Task Scheduler stores in Windows, not in a script/repository. Check the observed distro
and Linux user before registration. If your Windows sign-in has no usable task password,
configure the task through your organization's supported credential procedure; an interactive
logon-only task does not establish unattended reboot acceptance.

```powershell
$ResearchDistro = 'Ubuntu'
$ResearchLinuxUser = 'YOUR_WSL_USER'
$ResearchTaskName = 'EntropyTrade research WSL lifetime'
$ResearchWindowsUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
if (Get-ScheduledTask -TaskName $ResearchTaskName -ErrorAction SilentlyContinue) { throw 'Task already exists; inspect it first' }
$ResearchCredential = Get-Credential -UserName $ResearchWindowsUser -Message 'Account owning this WSL distribution'
$ResearchAction = New-ScheduledTaskAction -Execute "$env:WINDIR\System32\wsl.exe" -Argument "--distribution $ResearchDistro --user $ResearchLinuxUser --exec /usr/bin/sleep infinity"
$ResearchTrigger = New-ScheduledTaskTrigger -AtStartup
$ResearchSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $ResearchTaskName -Action $ResearchAction -Trigger $ResearchTrigger -Settings $ResearchSettings -User $ResearchCredential.UserName -Password $ResearchCredential.GetNetworkCredential().Password -RunLevel Limited
Remove-Variable ResearchCredential
Start-ScheduledTask -TaskName $ResearchTaskName
Get-ScheduledTaskInfo -TaskName $ResearchTaskName
```

The long-lived `wsl.exe` process retains WSL while the enabled lingering user manager starts
the research unit. Stop only this task if undoing the lifeline; this does not stop research
or collector systemd services. Check Windows power/sleep policy separately. Perform the
actual reboot only in a planned collector maintenance window, then verify task/user-unit
state and authenticated Mac/phone access **before signing into WSL interactively**. Confirm
the existing collector continues its normal chain without changed configuration or clocks.
These PowerShell commands are a physical procedure, not cloud-executed acceptance.

## Encrypted backup, offsite copy and restore drill

Start one backup after the service is healthy:

```bash
systemctl --user start entropytrade-research-backup.service
journalctl --user -u entropytrade-research-backup.service -n 100 --no-pager
systemctl --user is-active entropytrade-research.service
systemctl --user enable --now entropytrade-research-backup.timer
systemctl --user list-timers entropytrade-research-backup.timer
```

The coordinator stops **only** `entropytrade-research.service`, holds the workspace writer
lease through snapshot/encryption/publication and restarts it in `finally` if previously
active, including failure/interruption. An inactive service stays inactive. It refuses busy
or unknown states; it never stops or modifies the collector. The timer runs at 03:15
**America/New_York**, plus up to 15 minutes of jitter, with missed-run catch-up. Brief research
unavailability and lost RAM sessions are expected. Check failures in the journal. A forced
OS kill/power failure can leave private staging: while research is stopped, inspect
`data/recovery/.encrypted-*` and `data/backups/.encrypted-*` before removing identified
incomplete stages. Do not delete canonical evidence or completed backup files as cleanup.

New ciphertext and its receipt appear under `data/backups`. Originals, datasets, model bytes,
protected boundaries, SQL history, paper/readiness state and halt records are included;
owner/provider/private keys are deliberately configured separately after recovery. Snapshots
refuse unsupported/corrupt metadata or insufficient capacity instead of silently omitting it.
No model is loaded, training run, target scored or job resumed during verification/restore.
A backup must fit the bounded format (100,000 files, individual 256 MiB, distinct content
2 GiB, expanded content 4 GiB); large evidence needs a reviewed storage-format migration.

Local encrypted files are **not yet offsite backups**. Select an existing storage destination
and separately configure a copy tool such as rclone, with a private 0600 configuration outside
Git. No remote is assumed here. For each new backup, retain the expected ciphertext SHA-256
and recipient fingerprint in a separate trusted offline record; an adjacent receipt on the
same potentially compromised remote is not independent integrity evidence. An example using
an already configured remote and a newly selected file:

```bash
research_cipher="$HOME/Projects/EntropyTrade-research/data/backups/EXACT_NEW_FILE.gpg"
research_remote='YOUR_CONFIGURED_REMOTE:entropytrade/research'
rclone copyto --immutable "$research_cipher" "$research_remote/$(basename "$research_cipher")"
rclone copyto --immutable "$research_cipher.receipt.json" "$research_remote/$(basename "$research_cipher").receipt.json"
mkdir -m 700 "$HOME/entropytrade-offsite-drill-UNIQUE"
rclone copyto "$research_remote/$(basename "$research_cipher")" "$HOME/entropytrade-offsite-drill-UNIQUE/download.gpg"
sha256sum "$HOME/entropytrade-offsite-drill-UNIQUE/download.gpg"
```

Compare with the independently recorded hash, then transfer that downloaded ciphertext to
the offline recovery machine. Use the exact original application commit and `uv.lock`, with
Linux Python >=3.12 and `renameat2(RENAME_NOREPLACE)` support (for example recovery WSL or
Linux). Native macOS directory publication intentionally refuses; it is not claimed tested.
Provision the secret key into an explicit private 0700 GPG home there. For a passphrase key,
unlock its agent interactively after verifying the trusted ciphertext hash, without placing
the passphrase in argv/env/files. The bounded noninteractive tool can reuse that short-lived
agent cache. Retain old decryption subkeys after renewal; expiry blocks new encryption,
while historical authenticated ciphertext remains recoverable. No secret key is copied to
the research server.

```bash
mkdir -m 700 /PRIVATE/RECOVERY-HOME
gpg --homedir /PRIVATE/RECOVERY-HOME --import /PRIVATE/OFFLINE-MEDIA/secret-UNIQUE.asc
gpg --homedir /PRIVATE/RECOVERY-HOME --fingerprint FULL_PRIMARY_FINGERPRINT
export GPG_TTY="$(tty)"
gpg --homedir /PRIVATE/RECOVERY-HOME --max-output 3221225472 \
  --output /dev/null --decrypt /PATH/download.gpg
```

```bash
.venv/bin/python -m entropytrade.operations.backup workspace-restore \
  --repo /ABS/EntropyTrade-research \
  --ciphertext /PATH/download.gpg --expected-sha256 INDEPENDENTLY_RECORDED_SHA256 \
  --secret-homedir /PRIVATE/RECOVERY-HOME \
  --destination /ABS/EntropyTrade-research/data/cache/drill-UNIQUE
gpgconf --homedir /PRIVATE/RECOVERY-HOME --kill gpg-agent
```

The destination must be new; no-replace publication occurs only after complete validation.
Compare restored immutable hashes, logical SQL counts/history, retained unfinished work and
halt state against the backup receipt/original. Do not start workers during the offline
verification. To adopt after a real loss, stop the research unit, retain the old workspace
under a new recovery name, and move the verified restored directory to the configured
`data/cache/research` only if that path is absent. Reconfigure owner/provider files, rerun
preflight, start research, and inspect restart recovery before submitting new work. Restored
running jobs may become interrupted/resumable on normal startup; restore itself preserves
original statuses and timestamps. Existing live/order-submission refusal still applies.

Automate remote **copy**, not destructive sync, after successful local backup once the
remote is chosen. Retain at least 30 daily and 12 monthly generations and two offline key
copies; confirm capacity and do a download/restore drill monthly. This is a proposed policy,
not an installed retention/deletion job. Never delete the last verified restorable generation.
Report the physical/offsite gate pending until an actual upload, independent download/hash
check and offline-key application restore have completed.

## Back up collector history without operating the collector

The research service sandbox cannot read or write the collector checkout. The following is
an explicit **operator read-only export**, outside that service, during a naturally idle
collector interval. It opens the existing `.lock` read-only and obtains one nonblocking shared
lock through verification/copy. Busy/missing lock, stale work, lagging HEAD, bad hashes,
symlinks or capacity limits refuse without repair, initialization or deletion. Retry after
the normal collector cycle; do not stop its unit to force this export.

```bash
mkdir -m 700 "$HOME/entropytrade-encrypted-collector"
.venv/bin/python -m entropytrade.operations.backup chain-export \
  --source-repo "$HOME/Projects/EntropyTrade-collector" \
  --chain "$HOME/Projects/EntropyTrade-collector/data/cache/chain" \
  --output "$HOME/entropytrade-encrypted-collector/chain-UNIQUE.gpg" \
  --recipient-file "$HOME/.config/entropytrade-research/recipient.asc" \
  --recipient-fingerprint FULL_PRIMARY_FINGERPRINT
```

Copy ciphertext/receipt offsite and independently download/hash-check as above. Every complete
link, original archive, manifest, lineage, log and HEAD is preserved; `.lock` is not exported.
The separate default history budget is 64 GiB/100,000 files, never truncated to fit. Allow
space for an uncompressed history ZIP plus ciphertext and a downloaded restore copy. Original
workspace ZIPs are hash-verified opaque bytes; their historical application locks are not
replaced by today's code. No actual Windows chain export has been performed in cloud.

On the offline Linux recovery machine:

```bash
.venv/bin/python -m entropytrade.operations.backup chain-restore \
  --ciphertext /PATH/chain-UNIQUE.gpg --expected-sha256 INDEPENDENTLY_RECORDED_SHA256 \
  --secret-homedir /PRIVATE/RECOVERY-HOME --destination /ABS/offline-inspection-UNIQUE
```

This creates a new marked **inspection-only** directory outside every `data/cache`; it has
no lock or collector activation path. It must never replace, fork or reinitialize the
canonical chain. To consume evidence for research, select a workspace archive from the
verified history, use its recorded compatible commit/lock to verify/restore a separate
research copy, and use the existing [local-evidence consumer](research-modeling.md). That
consumer reads copied `runs/weather-datasets` snapshots inside the research workspace and
preserves receipt/protected clocks. Exporting history alone does not prove all old embedded
workspaces restore under today's code or make observations scientifically sufficient.

## Physical acceptance record

Keep a dated local receipt of observed software versions, selected pins, unit/Task Scheduler
states, available disk/RAM, exact Tailscale origin/login, allowed/denied policy tests, trusted
TLS/login/logout/expiry, Mac/phone access, clean stop/start, reboot without interactive WSL,
research backup failure/restart and an actual offsite research **and collector** restore drill.
Do not publish secrets, provider keys, private ciphertext or canonical data in GitHub.
Authentic point-in-time history, certified fees, live-provider verification and prospective
strategy eligibility remain distinct from infrastructure acceptance. No positive synthetic
fixture or owner readiness review permits live-money submission.

References: [Tailscale Serve](https://tailscale.com/docs/reference/tailscale-cli/serve),
[Serve identity headers](https://tailscale.com/docs/features/tailscale-serve#identity-headers),
[Windows/WSL](https://tailscale.com/docs/install/windows/wsl2#considerations),
[WSL networking](https://learn.microsoft.com/en-us/windows/wsl/networking),
[WSL systemd](https://learn.microsoft.com/en-us/windows/wsl/systemd),
[WSL service lifetime](https://devblogs.microsoft.com/commandline/systemd-support-is-now-available-in-wsl/),
[GnuPG options](https://www.gnupg.org/documentation/manuals/gnupg/OpenPGP-Options.html).
