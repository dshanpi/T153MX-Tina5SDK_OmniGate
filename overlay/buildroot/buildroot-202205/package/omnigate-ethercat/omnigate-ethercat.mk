################################################################################
#
# omnigate-ethercat
#
################################################################################

OMNIGATE_ETHERCAT_VERSION = 1.0
OMNIGATE_ETHERCAT_SITE = $(TOPDIR)/package/omnigate-ethercat
OMNIGATE_ETHERCAT_SITE_METHOD = local
OMNIGATE_ETHERCAT_DEPENDENCIES = soem
OMNIGATE_ETHERCAT_LICENSE = GPL-3.0-only
OMNIGATE_ETHERCAT_LICENSE_FILES = LICENSE

define OMNIGATE_ETHERCAT_BUILD_CMDS
	$(TARGET_CC) $(TARGET_CFLAGS) $(TARGET_LDFLAGS) \
		-I$(STAGING_DIR)/usr/include \
		-o $(@D)/omnigate-ethercat $(@D)/omnigate-ethercat.c \
		-L$(STAGING_DIR)/usr/lib -lsoem -lpthread -lrt
endef

define OMNIGATE_ETHERCAT_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 $(@D)/omnigate-ethercat \
		$(TARGET_DIR)/usr/bin/omnigate-ethercat
endef

$(eval $(generic-package))
