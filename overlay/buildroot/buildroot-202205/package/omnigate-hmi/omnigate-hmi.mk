################################################################################
# OmniGate Qt5 HMI
################################################################################

OMNIGATE_HMI_VERSION = 1.0
OMNIGATE_HMI_SITE = $(TOPDIR)/package/omnigate-hmi/src
OMNIGATE_HMI_SITE_METHOD = local
OMNIGATE_HMI_DEPENDENCIES = qt5base qt5charts omnigate-core
OMNIGATE_HMI_LICENSE = GPL-3.0-only
OMNIGATE_HMI_LICENSE_FILES = LICENSE

define OMNIGATE_HMI_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/omnigate-hmi $(TARGET_DIR)/usr/bin/omnigate-hmi
	$(INSTALL) -D -m 0755 $(TOPDIR)/package/omnigate-hmi/omnigate-hmi-launcher \
		$(TARGET_DIR)/usr/bin/omnigate-hmi-launcher
	$(INSTALL) -D -m 0755 $(TOPDIR)/package/omnigate-hmi/S75omnigate-hmi \
		$(TARGET_DIR)/etc/init.d/S75omnigate-hmi
	$(INSTALL) -D -m 0644 $(TOPDIR)/package/omnigate-hmi/omnigate-hmi.default \
		$(TARGET_DIR)/etc/default/omnigate-hmi
	$(INSTALL) -D -m 0600 $(TOPDIR)/package/omnigate-hmi/hmi-config.json \
		$(TARGET_DIR)/etc/omnigate-hmi/config.json
endef

$(eval $(qmake-package))
