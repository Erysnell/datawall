PACKAGE = datawall
VERSION = 1.0.0
BUILD_DIR = pkg/$(PACKAGE)
DEB = $(PACKAGE)_$(VERSION)_all.deb

.PHONY: all clean install deb lint

all: deb

$(BUILD_DIR)/usr/bin/datawall: datawall
	mkdir -p $(BUILD_DIR)/usr/bin
	cp datawall $(BUILD_DIR)/usr/bin/datawall
	chmod 755 $(BUILD_DIR)/usr/bin/datawall

$(BUILD_DIR)/usr/lib/systemd/user/datawall.service: datawall.service
	mkdir -p $(BUILD_DIR)/usr/lib/systemd/user
	cp datawall.service $(BUILD_DIR)/usr/lib/systemd/user/datawall.service

$(BUILD_DIR)/DEBIAN/control: pkg/debian/control pkg/debian/postinst pkg/debian/prerm
	mkdir -p $(BUILD_DIR)/DEBIAN
	cp pkg/debian/control $(BUILD_DIR)/DEBIAN/control
	cp pkg/debian/postinst $(BUILD_DIR)/DEBIAN/postinst
	cp pkg/debian/prerm $(BUILD_DIR)/DEBIAN/prerm
	chmod 755 $(BUILD_DIR)/DEBIAN/postinst $(BUILD_DIR)/DEBIAN/prerm

deb: $(BUILD_DIR)/usr/bin/datawall $(BUILD_DIR)/usr/lib/systemd/user/datawall.service $(BUILD_DIR)/DEBIAN/control
	dpkg-deb --build -Zxz $(BUILD_DIR) $(DEB)
	@echo ""
	@echo "Package built: $(DEB)"
	@echo "Install with: sudo dpkg -i $(DEB)"

install: datawall datawall.service
	install -Dm755 datawall /usr/bin/datawall
	install -Dm644 datawall.service /usr/lib/systemd/user/datawall.service
	@echo ""
	@echo "Installed. Enable the daemon with:"
	@echo "  systemctl --user enable --now datawall.service"

clean:
	rm -rf $(BUILD_DIR) *.deb

lint: $(BUILD_DIR)/usr/bin/datawall
	shellcheck $(BUILD_DIR)/DEBIAN/postinst $(BUILD_DIR)/DEBIAN/prerm 2>/dev/null || true
	pyflakes3 datawall 2>/dev/null || true
