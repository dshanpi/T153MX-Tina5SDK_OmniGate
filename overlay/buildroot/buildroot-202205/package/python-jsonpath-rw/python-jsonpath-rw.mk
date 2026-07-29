################################################################################
#
# python-jsonpath-rw
#
################################################################################

PYTHON_JSONPATH_RW_VERSION = 1.4.0
PYTHON_JSONPATH_RW_SOURCE = jsonpath-rw-$(PYTHON_JSONPATH_RW_VERSION).tar.gz
PYTHON_JSONPATH_RW_SITE = https://files.pythonhosted.org/packages/71/7c/45001b1f19af8c4478489fbae4fc657b21c4c669d7a5a036a86882581d85
PYTHON_JSONPATH_RW_SETUP_TYPE = setuptools
PYTHON_JSONPATH_RW_LICENSE = Apache-2.0

$(eval $(python-package))
