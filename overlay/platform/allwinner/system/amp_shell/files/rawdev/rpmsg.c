/*
* Copyright (c) 2019-2025 Allwinner Technology Co., Ltd. ALL rights reserved.
*
* Allwinner is a trademark of Allwinner Technology Co.,Ltd., registered in
* the the people's Republic of China and other countries.
* All Allwinner Technology Co.,Ltd. trademarks are used with permission.
*
* DISCLAIMER
* THIRD PARTY LICENCES MAY BE REQUIRED TO IMPLEMENT THE SOLUTION/PRODUCT.
* IF YOU NEED TO INTEGRATE THIRD PARTY’S TECHNOLOGY (SONY, DTS, DOLBY, AVS OR MPEGLA, ETC.)
* IN ALLWINNERS’SDK OR PRODUCTS, YOU SHALL BE SOLELY RESPONSIBLE TO OBTAIN
* ALL APPROPRIATELY REQUIRED THIRD PARTY LICENCES.
* ALLWINNER SHALL HAVE NO WARRANTY, INDEMNITY OR OTHER OBLIGATIONS WITH RESPECT TO MATTERS
* COVERED UNDER ANY REQUIRED THIRD PARTY LICENSE.
* YOU ARE SOLELY RESPONSIBLE FOR YOUR USAGE OF THIRD PARTY’S TECHNOLOGY.
*
*
* THIS SOFTWARE IS PROVIDED BY ALLWINNER"AS IS" AND TO THE MAXIMUM EXTENT
* PERMITTED BY LAW, ALLWINNER EXPRESSLY DISCLAIMS ALL WARRANTIES OF ANY KIND,
* WHETHER EXPRESS, IMPLIED OR STATUTORY, INCLUDING WITHOUT LIMITATION REGARDING
* THE TITLE, NON-INFRINGEMENT, ACCURACY, CONDITION, COMPLETENESS, PERFORMANCE
* OR MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
* IN NO EVENT SHALL ALLWINNER BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
* SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
* NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
* LOSS OF USE, DATA, OR PROFITS, OR BUSINESS INTERRUPTION)
* HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
* STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
* ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
* OF THE POSSIBILITY OF SUCH DAMAGE.
*/
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include <getopt.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <dirent.h>
#include <poll.h>
#include <errno.h>

#include "rpmsg.h"
#include "../amp_device.h"

/*
 * Whether the kernel rpmsg ctrl dev supports the Auto Free endpoint API
 * (RPMSG_CREATE_AF_EPT_IOCTL). Probed at runtime: try AF first and fall back
 * to RPMSG_CREATE_EPT_IOCTL so amp_shell works across kernel versions.
 */
static int use_auto_free_ept = 1;

#define RPMSG_DEV_NAME_MAX				128
#define RPMSG_CTRL_DEV "/dev/rpmsg_ctrl0"
#define RPMSG_BIND_NAME		"console"

static int fd_ctrl = -1;
static int fd_ept = -1;
static uint32_t ept_id;

static char dev_file_path[RPMSG_DEV_NAME_MAX] = RPMSG_CTRL_DEV;

int rpmsg_device_write(amp_device *device, char *data, int len)
{
	int fd = device->amp_fd;
	return write(fd, data, len);
}

int rpmsg_device_read(amp_device *device, char *data, int len)
{
	int ret = -1;
	int fd = device->amp_fd;

	struct pollfd poll_fds = {0};
	poll_fds.fd = fd;
	poll_fds.events = POLLIN;

	ret = poll(&poll_fds, 1, -1);
	if (ret < 0) {
		if (errno == EINTR) {
			printf("Signal occurred. Exit\n");
		} else {
			printf("Poll error (%s)\n", strerror(errno));
		}
	}
	return read(fd, data, len);
}

int rpmsg_device_connect(amp_device *device)
{
	return 0;
}

int rpmsg_getopt(int argc, char **argv)
{
	int opt;

	printf("rpmsg opt\n");
	opterr = 0;
	while ((opt = getopt(argc, argv, "d:")) != -1) {
		printf("opt = %c\r\n", opt);
		switch (opt) {
		case 'd':
			snprintf(dev_file_path, sizeof(dev_file_path), "%s", optarg);
			break;
		case '?':
			opterr = 0;
			break;
		default:
			break;
		}
	}

	return 0;
}

void rpmsg_opt_usage(void)
{
	printf("  -d: dev         : special dev\n");
}

int rpmsg_device_init(amp_device *device)
{
	int ret = -1;
	const char *ctrl_dev = dev_file_path;
	struct rpmsg_ept_info info;
	char ept_dev_name[RPMSG_DEV_NAME_MAX];
	int retry = 20;

	memset(&info, 0, sizeof(info));
	strcpy(info.name, RPMSG_BIND_NAME);
	info.id = 0xfffff;
	device->amp_fd = -1;
	use_auto_free_ept = 1;

	if (fd_ctrl < 0)
		fd_ctrl = open(ctrl_dev, O_RDWR);
	if (fd_ctrl < 0) {
		printf("Failed to open \"%s\" (ret: %d)\n", ctrl_dev, fd_ctrl);
		ret = -1;
		goto out;
	}

	printf("Creating Auto Free Endpoint...\r\n");
	ret = ioctl(fd_ctrl, RPMSG_CREATE_AF_EPT_IOCTL, &info);
	if (ret < 0) {
		printf("Auto free endpoint is unsupported (%s), "
		       "fallback to RPMSG_CREATE_EPT_IOCTL\r\n",
		       strerror(errno));
		printf("Creating Endpoint...\r\n");
		ret = ioctl(fd_ctrl, RPMSG_CREATE_EPT_IOCTL, &info);
		if (ret < 0) {
			printf("Failed to create endpoint (%s)\n", strerror(errno));
			ret = -1;
			goto close_fd_ctrl;
		}
		use_auto_free_ept = 0;
	}

	ept_id = info.id;
	printf("Success Create /dev/rpmsg%d\n", info.id);
	snprintf(ept_dev_name, sizeof(ept_dev_name), "/dev/rpmsg%d", info.id);

open_ept:
	fd_ept = open(ept_dev_name, O_RDWR);
	if (fd_ept < 0) {
		printf("Failed to open \"%s\" (ret: %d)\n", ept_dev_name, fd_ept);
		if (retry > 0) {
			retry--;
			printf("retry: %d\n", retry);
			usleep(100000);
			goto open_ept;
		}
		ret = -1;
		goto destroy_ept;
	}

	device->amp_fd = fd_ept;
	ret = 0;
	if (use_auto_free_ept)
		/* ept will be auto destroy when closing fd_ctrl */
		goto out;
	goto close_fd_ctrl;

destroy_ept:
	ioctl(fd_ctrl, RPMSG_DESTROY_EPT_IOCTL, &info);
close_fd_ctrl:
	close(fd_ctrl);
	fd_ctrl = -1;
out:
	return ret;
}

int rpmsg_device_deinit(amp_device *device)
{
	struct rpmsg_ept_info info;

	if (device->amp_fd >= 0) {
		close(device->amp_fd);
		device->amp_fd = -1;
	}

	info.id = ept_id;
	printf("destory rpmsg%d device\r\n", ept_id);

	if (use_auto_free_ept && fd_ctrl >= 0) {
		close(fd_ctrl);
		fd_ctrl = -1;
		return 0;
	}

	if (fd_ctrl < 0)
		fd_ctrl = open(dev_file_path, O_RDWR);

	if (fd_ctrl >= 0) {
		ioctl(fd_ctrl, RPMSG_DESTROY_EPT_IOCTL, &info);
		close(fd_ctrl);
		fd_ctrl = -1;
	}
	return 0;
}

raw_device_ops rpmsg_ops = {
	.write = rpmsg_device_write,
	.read = rpmsg_device_read,
	.init = rpmsg_device_init,
	.deinit = rpmsg_device_deinit,
	.connect = rpmsg_device_connect,
	.getopt = rpmsg_getopt,
	.usage = rpmsg_opt_usage,
};
