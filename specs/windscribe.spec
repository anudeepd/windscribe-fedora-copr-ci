# Prebuilt foreign binary: no build-id or debuginfo can be produced, so the
# debug package is disabled. The binaries ship as-is from the upstream release
# RPM.
%global debug_package %{nil}

# NOTE (verified by local rpmbuild of 2.24.13): %%global debug_package %%{nil}
# is what makes the default ELF-rewriting brp hooks run, not what skips them —
# Fedora's %%__os_install_post gates brp-strip / brp-strip-comment-note on
# %%__debug_package being *undefined*. With them in place the payload's ELF
# files get rewritten (they are built with .symtab/.comment intact), so the
# packaged payload stops matching the upstream RPM. brp-strip-lto and
# brp-strip-static-archive are not gated at all. Empty all four so every
# payload file stays byte-identical to upstream. Set them to %%{nil} rather
# than %%undefine'ing them: with rpm 6.0.2 %%undefine does not mask brp-strip /
# brp-strip-comment-note (verified — the hooks still ran, while %%undefine on
# the lto one did take effect).
%global __brp_strip %{nil}
%global __brp_strip_comment_note %{nil}
%global __brp_strip_lto %{nil}
%global __brp_strip_static_archive %{nil}

# add-determinism's brp hook (add-det) would regenerate /usr/lib/.build-id
# links from the payload's ELF build-id notes and otherwise normalize the
# payload. The payload must ship as upstream built it, so unset the hook.
%undefine __brp_add_determinism

# check-rpaths rejects /opt/windscribe/lib (ERROR 0002: its whitelist is
# /lib, /usr/lib, /usr/libexec and $ORIGIN). That RUNPATH is load-bearing and
# cannot be dropped: the bundle carries its own libwsnet.so, libcrypto.so.4 and
# libssl.so.4, and Fedora has no provider for the .so.4 OpenSSL SONAMEs at all,
# so the loader finds them through this RUNPATH alone. Unset the hook rather
# than rewriting the binaries we promise to ship untouched.
#
# Fedora moved that invocation between redhat-rpm-config revisions: older ones
# run check-rpaths from %%__os_install_post through %%__brp_check_rpaths, newer
# ones from the arch-level hook through the QA_CHECK_RPATHS shell variable.
# Neutralize both, keeping the other half of the arch hook (check-buildroot) in
# place.
%global __brp_check_rpaths %{nil}
%global __arch_install_post %{_rpmconfigdir}/check-buildroot

Name:           windscribe
Version:        2.24.13
Release:        %autorelease
Summary:        VPN client with a desktop GUI
License:        GPL-2.0-only
URL:            https://windscribe.com
ExclusiveArch:  x86_64

Source0:        https://github.com/Windscribe/Desktop-App/releases/download/v%{version}/windscribe_%{version}_amd64_fedora.rpm
# Upstream ships no GPL text outside open_source_licenses.txt (which only covers
# the bundled third-party components, and is kept in /opt as upstream ships it).
# spectool fetches LICENSE for the exact version being packaged from the release
# tag; a failed fetch fails the build, so the packaged license always matches
# the packaged version.
Source1:        https://raw.githubusercontent.com/Windscribe/Desktop-App/v%{version}/LICENSE
# Upstream ships no AppStream metadata at all; this repo ships a curated file.
# CI patches the <release> version/date on each new upstream release.
Source2:        com.windscribe.desktop.metainfo.xml
# Service account for the privileged helper. Upstream creates it in %post with
# groupadd/useradd; rpm creates it from this sysusers entry instead, before the
# payload is installed (so %attr below can resolve the group).
Source3:        windscribe.sysusers.conf
# Repo README shipped as %%doc.
Source4:        README.md

BuildRequires:  desktop-file-utils
BuildRequires:  appstream
BuildRequires:  cpio
BuildRequires:  systemd-rpm-macros

# The package ships a system unit and drives systemd from its scriptlets and
# from the helper's scripts (systemctl, resolvectl, busctl).
Requires:       systemd
Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd

# Upstream ships two mutually exclusive RPMs with overlapping payloads (both
# own /opt/windscribe): windscribe (this GUI build) and windscribe-cli (the
# headless build). Declare the conflict so dnf reports it instead of failing
# with a wall of file-conflict errors. Not declared upstream.
Conflicts:      windscribe-cli

# Runtime tools and interpreters the payload shells out to. Everything that is
# linked (glib2, libX11, libxcb*, libxkbcommon*, libglvnd*, fontconfig,
# freetype, libacl, libstdc++, dbus-libs, systemd-libs, ...) is auto-detected
# from DT_NEEDED and deliberately not duplicated here:
# - bash: every script under /opt/windscribe/scripts runs under bash (they use
#   [[ ]], arrays and ${10}).
# - coreutils, util-linux: cut/sed/mkdir/touch/realpath/getent, and
#   mount/logger/runuser from the cgroup, DNS and self-update scripts.
# - kmod: cgroups-up runs modprobe cls_cgroup (the helper does too).
# - iproute, iputils, iw, nftables: the routing/mark rules, latency probes, wifi
#   scanning and firewall rules the helper and its scripts run.
# - e2fsprogs: update-network-manager flips /etc/resolv.conf immutable with
#   chattr while the tunnel is up.
# - polkit: install-update (GUI build) re-executes itself as root with pkexec.
# - gnupg2: the helper verifies update packages with gpgv before staging them.
# - procps-ng, psmisc: procps-ng for pgrep/pkill/ps in the self-update script,
#   psmisc for the killall in %postun.
# Upstream also declares sudo for this build; the GUI build never calls it (the
# self-update script uses pkexec instead), so it is not carried over.
Requires:       bash
Requires:       coreutils
Requires:       e2fsprogs
Requires:       gnupg2
Requires:       iproute
Requires:       iputils
Requires:       iw
Requires:       kmod
Requires:       nftables
Requires:       polkit
Requires:       procps-ng
Requires:       psmisc
Requires:       util-linux

%description
Windscribe is a VPN service client with a desktop GUI: it manages WireGuard,
OpenVPN and AmneziaWG tunnels, DNS handling and firewall rules through a
privileged helper service. This package rewraps the upstream prebuilt Fedora
RPM for Fedora (COPR only).

%prep
rpm2cpio %{SOURCE0} | cpio -idmu
cp %{SOURCE1} LICENSE
# %%doc is copied from the build directory, not the buildroot.
cp %{SOURCE4} README.md

%build
# Nothing to compile: the prebuilt upstream binary is unpacked in %%prep.
# The section exists so rpm's build hooks (e.g. macro-injected steps) run.

%install
cp -a etc opt usr %{buildroot}/
install -Dm0644 %{SOURCE2} %{buildroot}%{_metainfodir}/com.windscribe.desktop.metainfo.xml
install -Dm0644 %{SOURCE3} %{buildroot}%{_sysusersdir}/windscribe.conf
# Upstream's %post writes this per-architecture marker (linux_rpm_x64 on x86_64,
# linux_rpm_arm64 on aarch64) that its self-update script reads back. Ship the
# same content as a file instead of generating it in a scriptlet.
printf 'linux_rpm_x64\n' > %{buildroot}/etc/windscribe/platform
chmod 0644 %{buildroot}/etc/windscribe/platform
# Upstream's %post creates this symlink; own it in %%files instead so rpm
# tracks what the package puts on PATH.
install -d %{buildroot}%{_bindir}
ln -s /opt/windscribe/windscribe-cli %{buildroot}%{_bindir}/windscribe-cli

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/windscribe.desktop
appstreamcli validate --no-net %{buildroot}%{_metainfodir}/com.windscribe.desktop.metainfo.xml

%files
%license LICENSE
%doc README.md
%{_bindir}/windscribe-cli
# Upstream chgrps this binary to the windscribe group and chmods it 2755 in
# %post so any user running the GUI picks up group access to the helper. Same
# result as %attr, but recorded in the package instead of applied by a script.
# Listed file by file rather than as /opt/windscribe/, so the %attr below is not
# re-listed by a directory glob (rpm warns about that, and the effective mode
# becomes ambiguous).
%attr(2755,root,windscribe) /opt/windscribe/Windscribe
/opt/windscribe/helper
/opt/windscribe/lib/
/opt/windscribe/open_source_licenses.txt
/opt/windscribe/scripts/
/opt/windscribe/windscribe-cli
/opt/windscribe/windscribeamneziawg
/opt/windscribe/windscribectrld
/opt/windscribe/windscribeopenvpn
/opt/windscribe/windscribewstunnel
# Upstream's RPM carries /usr/lib/.build-id links to the bundle's ELF files.
# The add-determinism hook is unset above, so they ship exactly as upstream
# built them (no regenerated links, no dropped ones).
/usr/lib/.build-id/
# Upstream marks this autostart entry as a config file.
%config(noreplace) /etc/windscribe/autostart/windscribe.desktop
/etc/windscribe/platform
%{_sysusersdir}/windscribe.conf
%{_unitdir}/windscribe-helper.service
%{_presetdir}/69-windscribe-helper.preset
%{_datadir}/applications/windscribe.desktop
%{_datadir}/icons/hicolor/*/apps/Windscribe.png
%{_metainfodir}/com.windscribe.desktop.metainfo.xml
# Release is %%autorelease. COPR builds this repo from an uploaded SRPM, where
# rpm's plain %%autorelease fallback applies: the release is a literal 1 plus
# the chroot's dist tag, NOT the changelog entry count. A %%changelog entry
# therefore documents a spec change but does not on its own give an
# already-built upstream version a new NVR — publish it with the force_build
# workflow input, which rewrites Release to %%{autorelease}.f<run_id> (a
# unique, higher release).

%post
%systemd_post windscribe-helper.service
# Upstream's posttrans restarts the helper on every install/upgrade; the preset
# applied above only covers the next boot, so bring it up now as well.
systemctl restart windscribe-helper.service || :

%preun
if [ $1 -eq 0 ]; then
    # Upstream's preuninstall, kept as is: undo the MAC addresses the helper
    # rewrote, while the helper binary is still on disk.
    if [ -x /opt/windscribe/helper ]; then
        /opt/windscribe/helper --reset-mac-addresses || :
    fi
fi
%systemd_preun windscribe-helper.service

%postun
if [ $1 -eq 0 ]; then
    killall -q Windscribe || :
    # The packaged files are gone by now; these are runtime state the helper
    # creates (and the /opt tree rpm leaves behind once empty), so remove them
    # here as upstream's postuninstall does.
    rm -rf /etc/windscribe /opt/windscribe /var/log/windscribe /var/lib/windscribe
    # The windscribe account is deliberately left behind: Fedora's guidelines
    # say packages must not delete users/groups on uninstall (upstream runs
    # userdel/groupdel here).
else
    # Upstream drops the generated VPN config on upgrade so the new helper
    # rebuilds it; same here.
    rm -rf /etc/windscribe/stunnel.conf /etc/windscribe/config.ovpn \
        /etc/windscribe/windscribe_servers
fi
%systemd_postun_with_restart windscribe-helper.service

%changelog
* Sun Sep 27 2026 Anudeep D <anudeepd2@gmail.com> - 2.24.13-1
- Initial Fedora repackaging of the upstream prebuilt Fedora RPM (GUI build)
- Replace upstream's scriptlets with rpm-owned payload: sysusers entry for the
  windscribe account, %%attr for the setgid GUI binary, /usr/bin/windscribe-cli
  owned by %%files, /etc/windscribe/platform shipped as a file
- Ship curated AppStream metadata (upstream ships none)
- Keep every payload file byte-identical to upstream (brp strip hooks and
  check-rpaths unset)
