# windscribe-fedora-copr-ci

[Windscribe](https://windscribe.com) is a VPN service client. This repo packages
it for Fedora by rewrapping the upstream prebuilt Linux RPMs with Fedora specs:

- `windscribe` — the desktop GUI build, from
  `windscribe_<version>_amd64_fedora.rpm`
- `windscribe-cli` — the headless command line build, from
  `windscribe-cli_<version>_amd64_fedora.rpm`

The two are separate upstream builds (their `Windscribe`/`helper`/`windscribe-cli`
binaries and their `install-update` script all differ; only the CLI build ships
the per-user unit), and both own `/opt/windscribe`, so they are mutually
exclusive — this repo declares `Conflicts:` between them so dnf says so plainly
instead of drowning the user in file-conflict errors.

Currently x86_64 only. Upstream also publishes aarch64 RPMs
(`windscribe_<version>_arm64_fedora.rpm`, `windscribe-cli_<version>_arm64_fedora.rpm`);
this repo does not cover them yet.

A GitHub Actions workflow runs daily at 12AM UTC to check the latest release
from https://github.com/Windscribe/Desktop-App and rebuilds COPR only when a new
version is published. Each downloaded RPM is verified against a recorded SHA256
checksum before submission.

The COPR project repository is available from:
https://copr.fedorainfracloud.org/coprs/anudeepd/windscribe

## Packaging compliance

Both packages are distributed via COPR only. They rewrap upstream prebuilt
binary RPMs, so they are **not eligible for the official Fedora repositories**:
the Fedora Packaging Guidelines require all binaries to be built from source in
the Fedora build system, and this repo intentionally ships the upstream blobs
as-is (see `specs/*.spec`).

Everything else follows the guidelines:

- `ExclusiveArch: x86_64` — matches upstream's prebuilt artifacts.
- `%build` present (empty — nothing to compile) so rpm's build hooks run.
- `%check` runs `desktop-file-validate` (on the packaged upstream desktop file)
  and `appstreamcli validate` (on the packaged AppStream metadata) inside the
  GUI build. The CLI build has neither file, so it has no `%check`.
- `rpmlint` runs in CI on the built RPMs and passes clean: `rpmlintrc`
  documents every inherent finding of a prebuilt-blob rewrap — the `/opt`
  layout, the bundle's `RUNPATH`, the unstripped and statically linked prebuilt
  binaries, upstream's 2755/`windscribe` mode on the client binary, the private
  bundled `libwsnet.so` and its unversioned SONAME, the bundle's own TLS
  defaults and `gethostbyname` calls, the missing man page, the runtime-state
  file under `/etc`, the `%postun` cleanup of unowned runtime directories, the
  old FSF address in upstream's GPL text, and two dictionary misses in
  `%description`. A finding that is not in that list fails the step.
- `%doc README.md` ships this file with each package.
- License provenance: `LICENSE` (the GPL-2.0 text upstream mirrors from the
  client's public sources) is fetched from the upstream release tag by
  `spectool`; a fetch failure fails the build, so the packaged license always
  matches the packaged version. `License: GPL-2.0-only` (SPDX) matches what the
  upstream RPM declares (`GPLv2`). The bundled third-party notices ship inside
  the payload as `open_source_licenses.txt`, exactly as upstream packages them.
- `%{_bindir}`, `%{_unitdir}`, `%{_userunitdir}`, `%{_presetdir}`,
  `%{_sysusersdir}`, `%{_datadir}`, `%{_metainfodir}` macros used in `%files`.
- `%global debug_package %{nil}` with an explicit rationale: the prebuilt
  foreign binaries cannot produce debuginfo, so the debug package is
  meaningless for a rewrap. Note that this is what *enables* Fedora's
  ELF-rewriting brp hooks rather than skipping them: `%__os_install_post` gates
  `brp-strip` and `brp-strip-comment-note` on `%__debug_package` being
  undefined, and with them active the payload's ELF files get rewritten. All
  four strip hooks plus `add-det` are emptied in the specs, and `check-rpaths`
  is unset too (the bundle's `RUNPATH=/opt/windscribe/lib` is load-bearing: it
  is the only way the loader finds the bundled `libwsnet.so`, `libcrypto.so.4`
  and `libssl.so.4`). The RPM build test workflow then verifies that every
  payload file present in both the upstream and the rebuilt RPM is
  byte-identical.
- Runtime deps declared explicitly for the tools the payload shells out to
  (`bash`, `coreutils`, `util-linux`, `kmod`, `iproute`, `iputils`, `iw`,
  `nftables`, `e2fsprogs`, `gnupg2`, `procps-ng`, `psmisc`, `systemd`);
  library deps auto-detected from `DT_NEEDED` and not duplicated. `polkit` is
  declared for the GUI build only (its self-update path uses `pkexec`) and
  `sudo` for the CLI build only (its self-update path uses `sudo -k`);
  upstream declares both for both, plus `ethtool`, which nothing in the payload
  calls. No network access inside the buildroot.
- The downloaded RPM is verified against a recorded SHA256 checksum before
  submission to COPR.

### Deltas from the upstream RPMs

Upstream runs its payload setup from RPM scriptlets (`%post` creates the
`windscribe` account, symlinks `/usr/bin/windscribe-cli`, chgrps the client
binary and writes `/etc/windscribe/platform`). Because this repo re-packs the
payload with `rpm2cpio`, those scriptlets cannot be carried over verbatim, so
their effects are expressed declaratively instead:

- `sources/windscribe.sysusers.conf` creates the `windscribe` group/account;
  rpm creates it before the payload is installed, so
  `%attr(2755,root,windscribe) /opt/windscribe/Windscribe` resolves (upstream's
  `chgrp` + `chmod 2755` did the same from `%post`).
- `/usr/bin/windscribe-cli` and `/etc/windscribe/platform`
  (`linux_rpm_x64` for the GUI build, `linux_rpm_x64_cli` for the CLI build) are
  owned by `%files` instead of being created by a scriptlet.
- The account is **not** deleted on uninstall, unlike upstream's `userdel`/
  `groupdel`: Fedora's guidelines forbid deleting accounts from package
  scriptlets.
- GUI build only: curated AppStream metadata (`com.windscribe.desktop`),
  since upstream ships none. The upstream desktop file and icons ship untouched.

Everything the scriptlets did at runtime is kept, via Fedora's systemd macros
and the parts no declarative equivalent exists for: the helper service is
preset on install and restarted on install/upgrade, `%preun` still runs
`helper --reset-mac-addresses` before the files go away, and `%postun` still
cleans up `/var/log/windscribe`, `/var/lib/windscribe` and the generated VPN
config on upgrade (the CLI build also kills a running client first, as upstream
does).

# Instructions

Enable the COPR repository then install one of the two packages.

<pre>
sudo dnf copr enable anudeepd/windscribe
sudo dnf install windscribe
</pre>

or

<pre>
sudo dnf copr enable anudeepd/windscribe
sudo dnf install windscribe-cli
</pre>

## Credits

Pattern and workflow structure adapted from
[DeltaCopy/waterfox-fedora-copr-ci](https://github.com/DeltaCopy/waterfox-fedora-copr-ci)
— thanks for the clean reference implementation.

<h3> COPR build status </h3>

[![Copr build status](https://copr.fedorainfracloud.org/coprs/anudeepd/windscribe/package/windscribe/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/anudeepd/windscribe/package/windscribe/)

[![Copr build status](https://copr.fedorainfracloud.org/coprs/anudeepd/windscribe/package/windscribe-cli/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/anudeepd/windscribe/package/windscribe-cli/)

<h3> GitHub action workflow status </h3>

[![windscribe Fedora COPR CI](https://github.com/anudeepd/windscribe-fedora-copr-ci/actions/workflows/windscribe-ci.yml/badge.svg)](https://github.com/anudeepd/windscribe-fedora-copr-ci/actions/workflows/windscribe-ci.yml)

## Latest version
<a href="https://github.com/Windscribe/Desktop-App/releases">
  <img src="https://img.shields.io/github/v/release/Windscribe/Desktop-App" alt="Windscribe latest release">
</a>
