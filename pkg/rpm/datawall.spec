Name:           datawall
Version:        1.3.0
Release:        1%{?dist}
Summary:        Track daily network usage per program

License:        MIT
URL:            https://github.com/Erysnell/datawall
Source0:        %{url}/archive/v%{version}/%{name}-%{version}.tar.gz

BuildArch:      noarch
# %%check runs the test suite, which exercises the CLI and therefore needs the
# runtime dependencies present at build time.
BuildRequires:  make
# %%{_userunitdir} is not a base rpm macro; it comes from here. Without this
# the macro is undefined and %%files fails.
BuildRequires:  systemd-rpm-macros
BuildRequires:  python3
BuildRequires:  python3-psutil
BuildRequires:  python3-rich
BuildRequires:  iproute

Requires:       python3
Requires:       python3-psutil
Requires:       python3-rich
# Fedora and openSUSE ship the ss(8) command in iproute, not iproute2.
Requires:       iproute
# notify-send is optional: without it the daemon logs the fact once and
# stays quiet instead of failing.
Recommends:     libnotify

%description
datawall runs a lightweight background daemon that samples network traffic
and attributes it to the processes that caused it, using exact per-socket
byte counters read through ss(8). It provides a terminal UI showing a
per-program breakdown, total daily usage and current transfer speeds.

Features include a real-time bandwidth monitor, historical reports over a
range of days, a daily traffic limit with desktop notifications, a live TCP
connections viewer, and a diagnostic that measures where unattributable
traffic comes from.

%prep
%autosetup

%build
# Nothing to compile: datawall is a single Python script.

%install
%make_install PREFIX=%{_prefix}
# rpm installs the licence and docs itself through %%license and %%doc, so drop
# the copy `make install` placed in the docdir to avoid unpackaged files.
rm -rf %{buildroot}%{_datadir}/doc/%{name}

%check
make test

%files
%license LICENSE
%doc README.md CHANGELOG.md
%{_bindir}/datawall
%{_mandir}/man1/datawall.1*
%{_userunitdir}/datawall.service

%changelog
* Tue Nov 17 2026 Erysnell Gonzalez <noreply@github.com> - 1.3.0-1
- Packaging for RPM and Arch distributions, man page, LICENSE file
* Sat Oct 31 2026 Erysnell Gonzalez <noreply@github.com> - 1.2.0-1
- Limit notifications, daemon health in status, unittest suite
* Sat Oct 31 2026 Erysnell Gonzalez <noreply@github.com> - 1.1.0-1
- Fix reset reverting, interface selection by default route, add explain
* Mon Jul 20 2026 Erysnell Gonzalez <noreply@github.com> - 1.0.0-1
- First packaged release
