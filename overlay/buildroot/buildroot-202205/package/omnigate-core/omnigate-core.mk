################################################################################
#
# omnigate-core
#
################################################################################

OMNIGATE_CORE_VERSION = 0.1.0
OMNIGATE_CORE_SITE = $(TOPDIR)/package/omnigate-core/src
OMNIGATE_CORE_SITE_METHOD = local
OMNIGATE_CORE_LICENSE = GPL-3.0-only
OMNIGATE_CORE_LICENSE_FILES = LICENSE

define OMNIGATE_CORE_INSTALL_TARGET_CMDS
	mkdir -p $(TARGET_DIR)/usr/lib/omnigate-core/omnigate_core
	$(INSTALL) -D -m 0644 $(@D)/omnigate_core/__init__.py \
		$(TARGET_DIR)/usr/lib/omnigate-core/omnigate_core/__init__.py
	$(INSTALL) -D -m 0644 $(@D)/omnigate_core/platform.py \
		$(TARGET_DIR)/usr/lib/omnigate-core/omnigate_core/platform.py
	$(INSTALL) -D -m 0644 $(@D)/omnigate_core/store.py \
		$(TARGET_DIR)/usr/lib/omnigate-core/omnigate_core/store.py
	$(INSTALL) -D -m 0644 $(@D)/omnigate_core/api.py \
		$(TARGET_DIR)/usr/lib/omnigate-core/omnigate_core/api.py
	$(INSTALL) -D -m 0644 $(@D)/schemas/platform-manifest.schema.json \
		$(TARGET_DIR)/usr/share/omnigate/schemas/platform-manifest.schema.json
	$(INSTALL) -D -m 0644 $(@D)/schemas/device-template.schema.json \
		$(TARGET_DIR)/usr/share/omnigate/schemas/device-template.schema.json
endef

$(eval $(generic-package))
