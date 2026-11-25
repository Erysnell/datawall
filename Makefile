PACKAGE = datawall
# Single source of truth: the VERSION constant inside the script itself.
VERSION = $(shell sed -n "s/^VERSION = '\(.*\)'/\1/p" datawall)

# Staging root and install prefixes. Distro packagers override DESTDIR to
# stage a build; everything below derives from PREFIX so /usr/local works too.
DESTDIR ?=
PREFIX ?= /usr
BINDIR ?= $(PREFIX)/bin
DATADIR ?= $(PREFIX)/share
MANDIR ?= $(DATADIR)/man
DOCDIR ?= $(DATADIR)/doc/$(PACKAGE)
UNITDIR ?= $(PREFIX)/lib/systemd/user

BUILD_DIR = pkg/$(PACKAGE)
DEB = $(PACKAGE)_$(VERSION)_all.deb

.PHONY: all clean install uninstall stage deb dist spec rpm lint version test test-all

all: deb

version:
	@test -n "$(VERSION)" || { echo "ERROR: could not read VERSION from datawall"; exit 1; }
	@echo "$(PACKAGE) $(VERSION)"

# The one definition of what this package consists of. Every packaging
# target below stages through it, so a new file cannot be forgotten in one
# format and not another.
install: datawall datawall.service datawall.1
	install -Dm755 datawall $(DESTDIR)$(BINDIR)/datawall
	install -Dm644 datawall.service $(DESTDIR)$(UNITDIR)/datawall.service
	install -Dm644 datawall.1 $(DESTDIR)$(MANDIR)/man1/datawall.1
	install -Dm644 LICENSE $(DESTDIR)$(DOCDIR)/LICENSE
	@echo ""
	@echo "Installed to $(DESTDIR)$(PREFIX). Enable the daemon with:"
	@echo "  systemctl --user enable --now datawall.service"

uninstall:
	rm -f $(DESTDIR)$(BINDIR)/datawall
	rm -f $(DESTDIR)$(UNITDIR)/datawall.service
	rm -f $(DESTDIR)$(MANDIR)/man1/datawall.1 $(DESTDIR)$(MANDIR)/man1/datawall.1.gz
	rm -rf $(DESTDIR)$(DOCDIR)
	@echo "Removed. Per-user data in ~/.datawall was left alone."

# Stage a filesystem tree for packaging.
stage:
	rm -rf $(BUILD_DIR)
	$(MAKE) install DESTDIR=$(BUILD_DIR) PREFIX=/usr >/dev/null

deb: version stage
	mkdir -p $(BUILD_DIR)/DEBIAN
	sed 's/^Version:.*/Version: $(VERSION)/' pkg/debian/control > $(BUILD_DIR)/DEBIAN/control
	install -m755 pkg/debian/postinst $(BUILD_DIR)/DEBIAN/postinst
	install -m755 pkg/debian/prerm $(BUILD_DIR)/DEBIAN/prerm
	# Debian policy requires compressed man pages
	gzip -9n $(BUILD_DIR)/usr/share/man/man1/datawall.1
	dpkg-deb --build -Zxz $(BUILD_DIR) $(DEB)
	@echo ""
	@echo "Package built: $(DEB)"
	@echo "Install with: sudo apt install ./$(DEB)"

# Source tarball consumed by the RPM spec and the Arch PKGBUILD.
DIST_NAME = $(PACKAGE)-$(VERSION)
DIST = $(DIST_NAME).tar.gz
DIST_FILES = datawall datawall.service datawall.1 LICENSE Makefile \
             README.md README.es.md CHANGELOG.md CHANGELOG.es.md pkg tests

dist: version
	rm -rf $(DIST_NAME) $(DIST)
	mkdir -p $(DIST_NAME)
	cp -r $(DIST_FILES) $(DIST_NAME)/
	find $(DIST_NAME) -name '__pycache__' -type d -prune -exec rm -rf {} +
	rm -rf $(DIST_NAME)/pkg/$(PACKAGE)
	tar czf $(DIST) $(DIST_NAME)
	rm -rf $(DIST_NAME)
	@echo ""
	@echo "Source tarball: $(DIST)"

# Keep the RPM spec's version in step with the script.
spec: version
	sed -i 's/^Version:.*/Version:        $(VERSION)/' pkg/rpm/$(PACKAGE).spec
	sed -i 's/^pkgver=.*/pkgver=$(VERSION)/' pkg/arch/PKGBUILD
	@echo "pkg/rpm/$(PACKAGE).spec and pkg/arch/PKGBUILD set to $(VERSION)"

# Build the RPM from the source tarball. Needs rpm-build.
rpm: dist spec
	mkdir -p $(HOME)/rpmbuild/SOURCES
	cp $(DIST) $(HOME)/rpmbuild/SOURCES/
	rpmbuild -bb pkg/rpm/$(PACKAGE).spec
	@echo ""
	@echo "RPM built under $(HOME)/rpmbuild/RPMS/noarch/"

test:
	./tests/run.sh

test-all:
	./tests/run.sh --all

clean:
	rm -rf $(BUILD_DIR) *.deb *.tar.gz $(PACKAGE)-*/

lint: datawall.1
	groff -man -ww -z datawall.1
	shellcheck pkg/debian/postinst pkg/debian/prerm 2>/dev/null || true
	pyflakes3 datawall 2>/dev/null || true
