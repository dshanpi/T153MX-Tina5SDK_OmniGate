################################################################################
#
# thingsboard-gateway
#
################################################################################

THINGSBOARD_GATEWAY_VERSION = 3.8.3
THINGSBOARD_GATEWAY_SITE = $(call github,thingsboard,thingsboard-gateway,$(THINGSBOARD_GATEWAY_VERSION))
THINGSBOARD_GATEWAY_LICENSE = Apache-2.0
THINGSBOARD_GATEWAY_LICENSE_FILES = LICENSE
THINGSBOARD_GATEWAY_DEPENDENCIES = \
	host-python3 \
	python3 \
	python-can \
	python-cryptography \
	python-dateutil \
	python-jsonpath-rw \
	python-orjson \
	python-packaging \
	python-psutil \
	python-pysocks \
	python-pyyaml \
	python-regex \
	python-requests \
	python-serial \
	python-serial-asyncio \
	python-service-identity \
	python-simplejson

THINGSBOARD_GATEWAY_EXTRA_DOWNLOADS = \
	https://files.pythonhosted.org/packages/ab/c3/57f0601a2d4fe15de7a553c00adbc901425661bf048f2a22dfc500caf121/packaging-23.1-py3-none-any.whl \
	https://files.pythonhosted.org/packages/c8/19/4ec628951a74043532ca2cf5d97b7b14863931476d117c471e8e2b1eb39f/urllib3-2.3.0-py3-none-any.whl \
	https://files.pythonhosted.org/packages/f9/9b/335f9764261e915ed497fcdeb11df5dfd6f7bf257d4a6a2a686d80da4d54/requests-2.32.3-py3-none-any.whl \
	https://files.pythonhosted.org/packages/4c/7e/ae151f2750fb604247088774634fea321a178fb898cf8e961879825f9e41/pymodbus-3.9.2-py3-none-any.whl \
	https://files.pythonhosted.org/packages/65/b0/738cb3e6237aa224f3bf48cd1d24f5ddf42ef7d03e6226012f9bdf7f665d/pymmh3-0.0.5-py2.py3-none-any.whl \
	https://files.pythonhosted.org/packages/2c/fc/1d7b80d0eb7b714984ce40efc78859c022cd930e402f599d8ca9e39c78a4/cachetools-6.2.4-py3-none-any.whl \
	https://files.pythonhosted.org/packages/ab/bf/a84eb7d0584788b80b4d1c65ef63faec983219b0e21150e4fcfdf4a2e182/tb_paho_mqtt_client-2.1.2-py3-none-any.whl \
	https://files.pythonhosted.org/packages/22/68/994bd7ebd320e17c93d6f12da8169f6e8a4348ca8a219baa02a862b9c8ac/tb_mqtt_client-1.13.13-py3-none-any.whl

THINGSBOARD_GATEWAY_SITE_PACKAGES = $(TARGET_DIR)/usr/lib/python3.10/site-packages

define THINGSBOARD_GATEWAY_EXTRACT_WHEEL
	$(HOST_DIR)/bin/python3 -m zipfile -e \
		$(DL_DIR)/thingsboard-gateway/$(1) \
		$(THINGSBOARD_GATEWAY_SITE_PACKAGES)
endef

define THINGSBOARD_GATEWAY_INSTALL_TARGET_CMDS
	mkdir -p $(THINGSBOARD_GATEWAY_SITE_PACKAGES)
	cp -a $(@D)/thingsboard_gateway $(THINGSBOARD_GATEWAY_SITE_PACKAGES)/
	$(call THINGSBOARD_GATEWAY_EXTRACT_WHEEL,packaging-23.1-py3-none-any.whl)
	$(call THINGSBOARD_GATEWAY_EXTRACT_WHEEL,urllib3-2.3.0-py3-none-any.whl)
	$(call THINGSBOARD_GATEWAY_EXTRACT_WHEEL,requests-2.32.3-py3-none-any.whl)
	$(call THINGSBOARD_GATEWAY_EXTRACT_WHEEL,pymodbus-3.9.2-py3-none-any.whl)
	$(call THINGSBOARD_GATEWAY_EXTRACT_WHEEL,pymmh3-0.0.5-py2.py3-none-any.whl)
	$(call THINGSBOARD_GATEWAY_EXTRACT_WHEEL,cachetools-6.2.4-py3-none-any.whl)
	$(call THINGSBOARD_GATEWAY_EXTRACT_WHEEL,tb_paho_mqtt_client-2.1.2-py3-none-any.whl)
	$(call THINGSBOARD_GATEWAY_EXTRACT_WHEEL,tb_mqtt_client-1.13.13-py3-none-any.whl)
	$(INSTALL) -D -m 0755 $(THINGSBOARD_GATEWAY_PKGDIR)/thingsboard-gateway \
		$(TARGET_DIR)/usr/bin/thingsboard-gateway
	$(INSTALL) -D -m 0755 $(THINGSBOARD_GATEWAY_PKGDIR)/S70thingsboard-gateway \
		$(TARGET_DIR)/etc/init.d/S70thingsboard-gateway
	$(INSTALL) -D -m 0644 $(THINGSBOARD_GATEWAY_PKGDIR)/thingsboard-gateway.default \
		$(TARGET_DIR)/etc/default/thingsboard-gateway
endef

$(eval $(generic-package))
