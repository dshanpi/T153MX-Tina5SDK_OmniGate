#include <linux/platform_device.h>
#include <linux/phy/phy.h>
#include "sunxi_can.h"

#include <linux/ptrace.h>

#define DRV_NAME "sunxi-can"
#define DRV_VER	 "V1.6"

#define CAN_CLK_FREQ 80000000

#if defined(CONFIG_ARCH_SUN8IW22)
static int can_dev_count;
static struct reset_control *can_sys_reset;
static DEFINE_MUTEX(sys_reset_mutex);
#endif

inline struct sunxi_can_priv *cdev_to_priv(struct sunxi_can_classdev *cdev)
{
	return container_of(cdev, struct sunxi_can_priv, cdev);
}

static u32 sunxi_iomap_read_reg(struct sunxi_can_classdev *cdev, int reg)
{
	struct sunxi_can_priv *priv = cdev_to_priv(cdev);

	return readl(priv->base + reg);
}

static int sunxi_iomap_write_reg(struct sunxi_can_classdev *cdev, int reg, int val)
{
	struct sunxi_can_priv *priv = cdev_to_priv(cdev);

	writel(val, priv->base + reg);

	return 0;
}

static u32 sunxi_iomap_top_read(struct sunxi_can_classdev *cdev, int reg)
{
	struct sunxi_can_priv *priv = cdev_to_priv(cdev);

	return readl(priv->top_base + reg);
}

static int sunxi_iomap_top_write(struct sunxi_can_classdev *cdev, int reg, int val)
{
	struct sunxi_can_priv *priv = cdev_to_priv(cdev);

	writel(val, priv->top_base + reg);

	return 0;
}

static int sunxi_iomap_read_fifo(struct sunxi_can_classdev *cdev, int offset,
									void *val, size_t val_count)
{
	struct sunxi_can_priv *priv = cdev_to_priv(cdev);
	void __iomem *src = priv->mram_base + offset;

	while (val_count--) {
		*(unsigned int *)val = ioread32(src);
		val += 4;
		src += 4;
	}

	return 0;
}

static int sunxi_iomap_write_fifo(struct sunxi_can_classdev *cdev, int offset,
									const void *val, size_t val_count)
{
	struct sunxi_can_priv *priv = cdev_to_priv(cdev);
	void __iomem *dst = priv->mram_base + offset;

	while (val_count--) {
		iowrite32(*(unsigned int *)val, dst);
		val += 4;
		dst += 4;
	}

	return 0;
}

static int sunxi_can_select_gpio_state(struct pinctrl *pctrl, char *name)
{
	int ret = 0;
	struct pinctrl_state *pctrl_state = NULL;

	pctrl_state = pinctrl_lookup_state(pctrl, name);
	if (IS_ERR(pctrl_state)) {
		pr_err("Failed to get pctrl_state\n");
		return -1;
	}

	ret = pinctrl_select_state(pctrl, pctrl_state);
	if (ret < 0)
		pr_err("pinctrl_select_state failed!\n");

	return ret;
}

static int sunxi_can_request_gpio(struct sunxi_can_classdev *sunxi_can_class)
{
	sunxi_can_class->pctrl = devm_pinctrl_get(sunxi_can_class->dev);

	if (IS_ERR_OR_NULL(sunxi_can_class->pctrl)) {
		pr_err("devm_pinctrl_get failed.\n");
		return -1;
	}

	return sunxi_can_select_gpio_state(sunxi_can_class->pctrl, PINCTRL_STATE_DEFAULT);
}

static void sunxi_can_release_gpio(struct sunxi_can_classdev *sunxi_can_class)
{
	devm_pinctrl_put(sunxi_can_class->pctrl);
	sunxi_can_class->pctrl = NULL;
}

static struct sunxi_can_ops sunxi_can_plat_ops = {
	.read_reg = sunxi_iomap_read_reg,
	.write_reg = sunxi_iomap_write_reg,
	.write_fifo = sunxi_iomap_write_fifo,
	.read_fifo = sunxi_iomap_read_fifo,
	.read_top = sunxi_iomap_top_read,
	.write_top = sunxi_iomap_top_write,
};

static const struct of_device_id sunxi_can_of_match[] = {
	{ .compatible = "allwinner,sun55i-t536-can", .data = NULL },
	{ .compatible = "allwinner,sun8i-t153-can", .data = NULL },
	{ /* sentinel */ },
};

MODULE_DEVICE_TABLE(of, sunxi_can_of_match);

#if defined(CONFIG_ARCH_SUN8IW22)
static int sunxi_can_deassert_sys_reset(struct device *dev)
{
	int ret = 0;
	mutex_lock(&sys_reset_mutex);
	can_dev_count++;

	printk("****** dev probe counts: %d\n", can_dev_count);
	if (IS_ERR_OR_NULL(can_sys_reset)) {
		can_sys_reset = devm_reset_control_get(dev, "can_sys_rst");
		if (IS_ERR(can_sys_reset)) {
			dev_err(dev, "Error: Get can sys rst failed\n");
			ret = -EINVAL;
		} else {
			ret = reset_control_deassert(can_sys_reset);
			if (ret)
				dev_err(dev, "Error: deassert can sys failed\n");
			else
				dev_err(dev, "can sys reset deasserted\n");
		}
	}

	mutex_unlock(&sys_reset_mutex);
	return ret;
}

static void sunxi_can_assert_sys_reset(struct device *dev)
{
	mutex_lock(&sys_reset_mutex);
	printk("****** dev probe counts: %d\n", can_dev_count);
	if (can_dev_count > 1) {
		can_dev_count--;
	} else {
		if (!IS_ERR_OR_NULL(can_sys_reset)) {
			reset_control_assert(can_sys_reset);
			dev_err(dev, "can sys reset asserted\n");
		}
	}
	mutex_unlock(&sys_reset_mutex);
}
#endif

static int sunxi_can_probe(struct platform_device *pdev)
{
	struct sunxi_can_classdev *sunxi_can_class;
	struct sunxi_can_priv *priv;
	struct resource *res;
	struct phy *transceiver = NULL;
	bool can_support_pm = true;

	void __iomem *addr;
	void __iomem *mram_addr;
	void __iomem *top_addr;
	void __iomem *dma_addr;

	//void __iomem *clk_base;

	int irq, top_irq, ret = 0;

	sunxi_can_class = sunxi_can_class_allocate_dev(&pdev->dev, sizeof(struct sunxi_can_priv));
	if (!sunxi_can_class)
		return -ENOMEM;

#if defined(CONFIG_ARCH_SUN8IW22)
	ret = sunxi_can_deassert_sys_reset(sunxi_can_class->dev);
	if (ret)
		goto probe_fail;
#endif

	priv = cdev_to_priv(sunxi_can_class);
	ret = sunxi_can_class_get_clocks(sunxi_can_class);
	if (ret)
		goto probe_fail;

	addr = devm_platform_ioremap_resource_byname(pdev, "can");
	irq = platform_get_irq_byname(pdev, "int0");
	top_irq = platform_get_irq_byname(pdev, "int_top");
	if (IS_ERR(addr) || irq < 0 || top_irq < 0) {
		ret = -EINVAL;
		goto probe_fail;
	}

	top_addr = devm_platform_ioremap_resource_byname(pdev, "can_top");
	dma_addr = devm_platform_ioremap_resource_byname(pdev, "can_dma");
	if (IS_ERR(top_addr) || IS_ERR(dma_addr)) {
		ret = -EINVAL;
		goto probe_fail;
	}

	res = platform_get_resource_byname(pdev, IORESOURCE_MEM, "message_ram");
	if (!res) {
		ret = -ENODEV;
		goto probe_fail;
	}

	sunxi_can_class->dma_mram_addr = res->start;

	mram_addr = devm_ioremap(&pdev->dev, res->start, resource_size(res));
	if (!mram_addr) {
		ret = -ENOMEM;
		goto probe_fail;
	}

	ret = sunxi_can_class_clk_init(sunxi_can_class);
	if (ret)
		goto probe_fail;

	ret = sunxi_can_request_gpio(sunxi_can_class);
	if (ret)
		goto probe_fail;

	priv->base = addr;
	priv->mram_base = mram_addr;
	priv->top_base = top_addr;

	sunxi_can_class->net->irq = irq;
	sunxi_can_class->pm_clock_support = can_support_pm ? 1 : 0;
	sunxi_can_class->can.clock.freq = clk_get_rate(sunxi_can_class->hclk);
	sunxi_can_class->dev = &pdev->dev;
	sunxi_can_class->transceiver = transceiver;
	sunxi_can_class->ops = &sunxi_can_plat_ops;
	sunxi_can_class->is_peripheral = false;
	pr_info("-----*clock freq is %d*----\n", sunxi_can_class->can.clock.freq);

	platform_set_drvdata(pdev, sunxi_can_class);

	ret = sunxi_can_init_ram(sunxi_can_class);
	if (ret)
		goto probe_fail;

	if (can_support_pm)
		pm_runtime_enable(sunxi_can_class->dev);

	ret = sunxi_can_class_register(sunxi_can_class);
	if (ret) {
		if (can_support_pm)
			goto out_runtime_disable;
		else
			goto probe_fail;
	}
	return ret;

out_runtime_disable:
	pm_runtime_disable(sunxi_can_class->dev);
probe_fail:
	sunxi_can_class_free_dev(sunxi_can_class->net);
	return ret;
}

static int sunxi_can_remove(struct platform_device *pdev)
{
	struct sunxi_can_priv *priv = platform_get_drvdata(pdev);
	struct sunxi_can_classdev *can_class = &priv->cdev;

	sunxi_can_release_gpio(can_class);
	unregister_candev(can_class->net);
	sunxi_can_class_free_dev(can_class->net);
	//free_irq(can_class->net->irq, can_class->net);
	sunxi_can_class_clk_deinit(can_class);

#if defined(CONFIG_ARCH_SUN8IW22)
	sunxi_can_assert_sys_reset(can_class->dev);
#endif

	return 0;
}

static __maybe_unused int sunxi_can_suspend(struct device *dev)
{
	return sunxi_can_class_suspend(dev);
}

static __maybe_unused int sunxi_can_resume(struct device *dev)
{
	return sunxi_can_class_resume(dev);
}

static int __maybe_unused sunxi_can_runtime_suspend(struct device *dev)
{
	struct sunxi_can_priv *priv = dev_get_drvdata(dev);
	struct sunxi_can_classdev *can_class = &priv->cdev;

	dev_dbg(dev, "PM runtime suspend.\n");

	sunxi_can_class_clk_deinit(can_class);
	return 0;
}

static int __maybe_unused sunxi_can_runtime_resume(struct device *dev)
{
	struct sunxi_can_priv *priv = dev_get_drvdata(dev);
	struct sunxi_can_classdev *can_class = &priv->cdev;

	dev_dbg(dev, "PM runtime resume.\n");
	return sunxi_can_class_clk_init(can_class);
}

static const struct dev_pm_ops sunxi_can_pmops = {
	SET_RUNTIME_PM_OPS(sunxi_can_runtime_suspend, sunxi_can_runtime_resume, NULL)
	SET_SYSTEM_SLEEP_PM_OPS(sunxi_can_suspend, sunxi_can_resume)
};


static struct platform_driver sunxi_can_driver = {
	.driver = {
		.name = DRV_NAME,
		.pm = &sunxi_can_pmops,
		.of_match_table = sunxi_can_of_match,
	},
	.probe = sunxi_can_probe,
	.remove = sunxi_can_remove,
};

module_platform_driver(sunxi_can_driver);

MODULE_AUTHOR("madonglin <madonglin@allwinnertech.com>");
MODULE_LICENSE("GPL v2");
MODULE_DESCRIPTION("CAN driver for Allwinner T536 SoCs");
