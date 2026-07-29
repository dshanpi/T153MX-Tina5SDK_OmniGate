################################################################################
#
# soem
#
################################################################################

SOEM_VERSION = 2.0.0
SOEM_SITE = $(call github,OpenEtherCATsociety,SOEM,v$(SOEM_VERSION))
SOEM_LICENSE = GPL-3.0 or commercial
SOEM_LICENSE_FILES = LICENSE.md
SOEM_INSTALL_STAGING = YES
SOEM_CONF_OPTS = \
	-DBUILD_SHARED_LIBS=ON \
	-DSOEM_BUILD_SAMPLES=ON \
	-DCMAKE_BUILD_TYPE=Release

$(eval $(cmake-package))
