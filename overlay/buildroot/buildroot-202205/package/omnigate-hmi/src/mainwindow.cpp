#include "mainwindow.h"

#include <QAbstractItemView>
#include <QBoxLayout>
#include <QCheckBox>
#include <QComboBox>
#include <QDateTime>
#include <QFormLayout>
#include <QFrame>
#include <QGroupBox>
#include <QHeaderView>
#include <QIcon>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonValue>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QNetworkReply>
#include <QPainter>
#include <QPushButton>
#include <QScrollArea>
#include <QSlider>
#include <QSpinBox>
#include <QStackedWidget>
#include <QTableWidget>
#include <QTabWidget>
#include <QtCharts/QChart>
#include <QtCharts/QChartView>
#include <QtCharts/QValueAxis>
#include <QtMath>

namespace {
const char *kBaseUrl = "http://127.0.0.1/api/hmi/v1";
const QColor kPanel("#22292f");
const QColor kGrid("#3b464e");
const QColor kText("#e6ecef");
const QColor kMuted("#a8b3ba");
const QColor kSuccess("#4fc38d");
const QColor kWarning("#e0a84b");
const QColor kDanger("#e06b6b");

QLabel *titleLabel(const QString &text)
{
    QLabel *label = new QLabel(text);
    label->setObjectName("sectionTitle");
    return label;
}

QLabel *captionLabel(const QString &text)
{
    QLabel *label = new QLabel(text);
    label->setObjectName("caption");
    return label;
}

QFrame *rule(Qt::Orientation orientation)
{
    QFrame *line = new QFrame;
    line->setObjectName("rule");
    line->setFrameShape(orientation == Qt::Horizontal ? QFrame::HLine : QFrame::VLine);
    if (orientation == Qt::Horizontal) line->setFixedHeight(1);
    else line->setFixedWidth(1);
    return line;
}

QTableWidgetItem *cell(const QString &text, const QColor &color = kText)
{
    QTableWidgetItem *item = new QTableWidgetItem(text);
    item->setForeground(color);
    item->setTextAlignment(Qt::AlignVCenter | Qt::AlignLeft);
    return item;
}

QLineEdit *edit(const QString &value, const QString &placeholder = QString())
{
    QLineEdit *e = new QLineEdit(value);
    e->setPlaceholderText(placeholder);
    e->setMinimumHeight(42);
    return e;
}

}

MainWindow::MainWindow(QWidget *parent) : QMainWindow(parent)
{
    resize(1024, 768);
    setWindowTitle("OmniGate 工业边缘网关");
    applyTheme();

    QWidget *root = new QWidget;
    QVBoxLayout *rootLayout = new QVBoxLayout(root);
    rootLayout->setContentsMargins(0, 0, 0, 0);
    rootLayout->setSpacing(0);

    QFrame *header = new QFrame;
    header->setObjectName("header");
    header->setFixedHeight(56);
    QHBoxLayout *headerLayout = new QHBoxLayout(header);
    headerLayout->setContentsMargins(18, 0, 18, 0);
    QLabel *mark = new QLabel("OG");
    mark->setObjectName("brandMark");
    mark->setFixedSize(34, 34);
    mark->setAlignment(Qt::AlignCenter);
    QLabel *brand = new QLabel("OMNIGATE   工业边缘网关");
    brand->setObjectName("brand");
    headerLayout->addWidget(mark);
    headerLayout->addSpacing(10);
    headerLayout->addWidget(brand);
    headerLayout->addSpacing(24);
    cpuValue = new QLabel("CPU --");
    memoryValue = new QLabel("内存 --");
    temperatureValue = new QLabel("温度 --");
    storageValue = new QLabel("存储 --");
    for (QLabel *label : {cpuValue, memoryValue, temperatureValue, storageValue}) {
        label->setObjectName("headerMetric");
        headerLayout->addWidget(label);
        headerLayout->addSpacing(14);
    }
    headerLayout->addStretch();
    demoBadge = new QLabel("演示");
    demoBadge->setObjectName("demoBadge");
    demoBadge->setVisible(false);
    alarmSummaryLabel = new QLabel("报警 --");
    alarmSummaryLabel->setObjectName("alarmSummary");
    connectionLabel = new QLabel("● 正在连接");
    connectionLabel->setObjectName("connection");
    clockLabel = new QLabel;
    clockLabel->setObjectName("clock");
    headerLayout->addWidget(demoBadge);
    headerLayout->addSpacing(14);
    headerLayout->addWidget(alarmSummaryLabel);
    headerLayout->addSpacing(18);
    headerLayout->addWidget(connectionLabel);
    headerLayout->addSpacing(18);
    headerLayout->addWidget(clockLabel);
    rootLayout->addWidget(header);

    QWidget *body = new QWidget;
    QHBoxLayout *bodyLayout = new QHBoxLayout(body);
    bodyLayout->setContentsMargins(0, 0, 0, 0);
    bodyLayout->setSpacing(0);
    QFrame *nav = new QFrame;
    nav->setObjectName("nav");
    nav->setFixedWidth(158);
    QVBoxLayout *navLayout = new QVBoxLayout(nav);
    navLayout->setContentsMargins(0, 14, 0, 12);
    navLayout->setSpacing(4);
    QLabel *navTitle = new QLabel("功能导航");
    navTitle->setObjectName("navTitle");
    navLayout->addWidget(navTitle);
    navLayout->addSpacing(6);
    const QStringList names = {"01  运行总览", "02  现场总线", "03  网络通信", "04  设备监控", "05  告警记录", "06  系统设置"};
    for (int i = 0; i < names.size(); ++i) {
        QPushButton *button = new QPushButton(names[i]);
        button->setObjectName("navButton");
        button->setCheckable(true);
        button->setMinimumHeight(54);
        connect(button, &QPushButton::clicked, this, [this, i]() { showPage(i); });
        navButtons << button;
        navLayout->addWidget(button);
    }
    navLayout->addStretch();
    QLabel *model = new QLabel("T153MX\nEDGE CONTROLLER");
    model->setObjectName("navModel");
    navLayout->addWidget(model);
    bodyLayout->addWidget(nav);

    pages = new QStackedWidget;
    pages->setObjectName("pages");
    pages->addWidget(buildOverview());
    pages->addWidget(buildFieldbus());
    pages->addWidget(buildNetwork());
    pages->addWidget(buildDevices());
    pages->addWidget(buildAlarms());
    pages->addWidget(buildSettings());
    bodyLayout->addWidget(pages, 1);
    rootLayout->addWidget(body, 1);

    setCentralWidget(root);

    connect(&networkManager, &QNetworkAccessManager::finished,
            this, &MainWindow::handleReply);
    connect(&refreshTimer, &QTimer::timeout, this, &MainWindow::requestSnapshot);
    connect(&pageTimer, &QTimer::timeout, this, [this]() {
        showPage((pages->currentIndex() + 1) % pages->count());
    });
    refreshTimer.start(1000);
    showPage(0);
    requestSnapshot();
}

void MainWindow::applyTheme()
{
    setStyleSheet(R"(
        * { font-family: "WenQuanYi Zen Hei"; font-size: 14px; color: #e6ecef; }
        QMainWindow, QWidget#pages, QStackedWidget { background: #171c20; }
        QFrame#header { background: #1b2126; border-bottom: 1px solid #3b464e; }
        QFrame#nav { background: #1b2126; border-right: 1px solid #3b464e; }
        QLabel#brandMark { color: #e6ecef; background: transparent; border: 1px solid #59656e; font-weight: 700; font-size: 15px; }
        QLabel#brand { font-size: 18px; font-weight: 700; color: #e6ecef; }
        QLabel#clock { font-size: 13px; color: #e6ecef; }
        QLabel#connection, QLabel#alarmSummary { color: #e6ecef; }
        QLabel#headerMetric { font-size: 12px; color: #e6ecef; }
        QLabel#demoBadge { color: #f2c879; background: #3a3020; border: 1px solid #806b3c; padding: 3px 7px; }
        QLabel#navTitle { color: #a8b3ba; font-size: 12px; padding-left: 20px; }
        QLabel#navModel { color: #a8b3ba; font-size: 11px; padding: 12px 20px; border-top: 1px solid #3b464e; }
        QLabel#sectionTitle { font-size: 17px; font-weight: 700; color: #e6ecef; }
        QLabel#caption { font-size: 12px; color: #a8b3ba; }
        QLabel#panelTitle { font-size: 13px; font-weight: 700; color: #e6ecef; }
        QLabel#statusName { font-size: 12px; color: #a8b3ba; }
        QLabel#statusValue { font-size: 16px; font-weight: 700; color: #e6ecef; }
        QLabel#nodeName { font-size: 15px; font-weight: 700; color: #e6ecef; }
        QLabel#nodeState { font-size: 12px; color: #a8b3ba; }
        QLabel#gatewayTitle { font-size: 18px; font-weight: 700; color: #e6ecef; }
        QLabel#gatewaySub { font-size: 12px; color: #a8b3ba; }
        QPushButton#navButton { border: none; border-radius: 0; text-align: left; padding-left: 24px;
                                color: #d6dde1; background: transparent; font-size: 14px; font-weight: 400; }
        QPushButton#navButton:checked { background: #2c353c; color: #ffffff; border-left: 5px solid #e0a84b; font-weight: 700; }
        QPushButton#navButton:pressed { background: #3b464e; color: #ffffff; }
        QPushButton { min-height: 38px; border-radius: 2px; padding: 0 14px; font-weight: 600;
                      color: #f2f4f5; background: #505c65; border: 1px solid #69757e; }
        QPushButton:pressed { background: #3b464e; }
        QPushButton[kind="danger"] { background: #493438; border-color: #e06b6b; }
        QPushButton[kind="secondary"] { color: #e6ecef; background: #30383e; border-color: #59656e; }
        QFrame#card, QFrame#panel, QGroupBox { background: #22292f; border: 1px solid #3b464e; border-radius: 1px; }
        QFrame#gateway { background: #1b2126; border: 2px solid #e0a84b; }
        QFrame#ioNode { background: #22292f; border: 1px solid #3b464e; border-left: 4px solid #e0a84b; }
        QFrame#ioNode[online="true"] { border-left: 4px solid #4fc38d; }
        QFrame#rule { color: #3b464e; background: #3b464e; border: none; }
        QGroupBox { margin-top: 14px; padding: 12px; font-weight: 700; font-size: 15px; }
        QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 7px; }
        QTableWidget { background: #22292f; alternate-background-color: #293138; border: 1px solid #3b464e;
                       border-radius: 0; gridline-color: #3b464e; selection-background-color: #46525b; }
        QHeaderView::section { background: #30383e; color: #e6ecef; border: none; border-right: 1px solid #3b464e;
                               border-bottom: 1px solid #3b464e; min-height: 36px; padding: 4px; font-weight: 700; }
        QTableWidget::item { padding: 5px; }
        QLineEdit, QComboBox, QSpinBox { background: #1b2126; border: 1px solid #59656e; border-radius: 2px;
                                        min-height: 38px; padding: 0 9px; }
        QComboBox QAbstractItemView { background: #22292f; selection-background-color: #46525b; }
        QTabWidget::pane { border: 1px solid #3b464e; background: #22292f; }
        QTabBar::tab { background: #293138; color: #a8b3ba; padding: 10px 22px; border-right: 1px solid #3b464e; }
        QTabBar::tab:selected { color: #ffffff; background: #46525b; }
        QCheckBox { spacing: 10px; }
        QSlider::groove:horizontal { height: 7px; background: #3b464e; border-radius: 1px; }
        QSlider::handle:horizontal { width: 20px; margin: -7px 0; background: #8c989f; border-radius: 2px; }
        QSlider::sub-page:horizontal { background: #e0a84b; border-radius: 1px; }
        QScrollArea { border: none; background: transparent; }
    )");
}

QWidget *MainWindow::metricCard(const QString &title, QLabel **value, const QString &color)
{
    Q_UNUSED(color);
    QFrame *card = new QFrame;
    card->setObjectName("card");
    card->setMinimumHeight(72);
    QVBoxLayout *layout = new QVBoxLayout(card);
    layout->setContentsMargins(14, 8, 14, 8);
    QLabel *name = new QLabel(title);
    name->setObjectName("cardTitle");
    *value = new QLabel("--");
    (*value)->setObjectName("cardValue");
    (*value)->setStyleSheet("color:#e6ecef;");
    layout->addWidget(name);
    layout->addWidget(*value);
    return card;
}

QTableWidget *MainWindow::makeTable(const QStringList &headers)
{
    QTableWidget *table = new QTableWidget(0, headers.size());
    table->setHorizontalHeaderLabels(headers);
    table->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);
    table->verticalHeader()->hide();
    table->setAlternatingRowColors(true);
    table->setEditTriggers(QAbstractItemView::NoEditTriggers);
    table->setSelectionBehavior(QAbstractItemView::SelectRows);
    table->setFocusPolicy(Qt::NoFocus);
    table->verticalHeader()->setDefaultSectionSize(38);
    return table;
}

QPushButton *MainWindow::actionButton(const QString &text, const QString &kind)
{
    QPushButton *button = new QPushButton(text);
    button->setProperty("kind", kind);
    return button;
}

static QChartView *createTrend(QList<QLineSeries *> &seriesOut, bool compact)
{
    QChart *chart = new QChart;
    chart->setBackgroundBrush(kPanel);
    chart->setPlotAreaBackgroundBrush(kPanel);
    chart->setPlotAreaBackgroundVisible(true);
    chart->legend()->setLabelColor(kText);
    chart->setMargins(QMargins(8, 4, 8, 4));
    const QStringList names = {"温度", "压力", "流量"};
    const QList<QColor> colors = {kWarning, kSuccess, kDanger};
    for (int i = 0; i < 3; ++i) {
        QLineSeries *series = new QLineSeries;
        series->setName(names[i]);
        QPen pen(colors[i]);
        pen.setWidth(2);
        if (i == 1) pen.setStyle(Qt::DashLine);
        if (i == 2) pen.setStyle(Qt::DotLine);
        series->setPen(pen);
        chart->addSeries(series);
        seriesOut << series;
    }
    QValueAxis *axisX = new QValueAxis;
    axisX->setRange(0, 59); axisX->setLabelFormat("%d"); axisX->setTickCount(7);
    QValueAxis *axisY = new QValueAxis;
    axisY->setRange(0, 100); axisY->setTickCount(5);
    for (QValueAxis *axis : {axisX, axisY}) {
        axis->setLabelsColor(kMuted);
        axis->setGridLineColor(kGrid);
        axis->setLinePenColor(kGrid);
    }
    chart->addAxis(axisX, Qt::AlignBottom);
    chart->addAxis(axisY, Qt::AlignLeft);
    for (QLineSeries *series : seriesOut) { series->attachAxis(axisX); series->attachAxis(axisY); }
    QChartView *view = new QChartView(chart);
    view->setFrameShape(QFrame::NoFrame);
    view->setBackgroundBrush(kPanel);
    view->viewport()->setStyleSheet("background:#22292f; border:none;");
    view->setRenderHint(QPainter::Antialiasing, false);
    view->setMinimumHeight(compact ? 190 : 280);
    return view;
}

QWidget *MainWindow::buildOverview()
{
    QWidget *page = new QWidget;
    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(16, 12, 16, 12);
    layout->setSpacing(9);

    QHBoxLayout *pageHead = new QHBoxLayout;
    pageHead->addWidget(titleLabel("运行总览"));
    pageHead->addSpacing(12);
    pageHead->addWidget(captionLabel("现场接口、网关和上行链路的实时运行关系"));
    pageHead->addStretch();
    pageHead->addWidget(captionLabel("数据刷新：1 秒"));
    layout->addLayout(pageHead);

    auto ioNode = [](const QString &name, const QString &detail, QLabel **state) {
        QFrame *node = new QFrame;
        node->setObjectName("ioNode");
        node->setMinimumHeight(55);
        QHBoxLayout *row = new QHBoxLayout(node);
        row->setContentsMargins(11, 6, 10, 6);
        QVBoxLayout *text = new QVBoxLayout;
        text->setSpacing(1);
        QLabel *nodeName = new QLabel(name); nodeName->setObjectName("nodeName");
        QLabel *nodeDetail = new QLabel(detail); nodeDetail->setObjectName("nodeState");
        text->addWidget(nodeName); text->addWidget(nodeDetail);
        *state = new QLabel("--");
        (*state)->setObjectName("nodeState");
        (*state)->setAlignment(Qt::AlignRight | Qt::AlignVCenter);
        row->addLayout(text, 1); row->addWidget(*state);
        return node;
    };

    QFrame *topology = new QFrame; topology->setObjectName("panel");
    QVBoxLayout *topologyLayout = new QVBoxLayout(topology);
    topologyLayout->setContentsMargins(12, 9, 12, 11);
    topologyLayout->setSpacing(7);
    QLabel *topologyTitle = new QLabel("通信拓扑"); topologyTitle->setObjectName("panelTitle");
    topologyLayout->addWidget(topologyTitle);
    QHBoxLayout *flow = new QHBoxLayout;
    flow->setSpacing(10);

    QVBoxLayout *inputs = new QVBoxLayout; inputs->setSpacing(6);
    const QStringList inputNames = {"CAN 0 / CAN 1", "RS485", "EtherCAT"};
    const QStringList inputDetails = {"CAN / CAN-FD / CANopen", "Modbus RTU", "CoE 实时总线"};
    for (int i = 0; i < inputNames.size(); ++i) {
        QLabel *state = nullptr;
        inputs->addWidget(ioNode(inputNames[i], inputDetails[i], &state));
        overviewBusStates << state;
    }
    flow->addLayout(inputs, 3);

    QLabel *leftArrow = new QLabel("▶"); leftArrow->setStyleSheet("color:#e0a84b;font-size:18px;");
    flow->addWidget(leftArrow, 0, Qt::AlignCenter);
    QFrame *gateway = new QFrame; gateway->setObjectName("gateway"); gateway->setMinimumWidth(220);
    QVBoxLayout *gatewayLayout = new QVBoxLayout(gateway);
    gatewayLayout->setContentsMargins(16, 14, 16, 12);
    QLabel *gatewayTitle = new QLabel("OmniGate T153MX"); gatewayTitle->setObjectName("gatewayTitle");
    QLabel *gatewaySub = new QLabel("工业协议转换与边缘计算"); gatewaySub->setObjectName("gatewaySub");
    gatewayLayout->addWidget(gatewayTitle); gatewayLayout->addWidget(gatewaySub); gatewayLayout->addStretch();
    QGridLayout *gatewayStatus = new QGridLayout; gatewayStatus->setHorizontalSpacing(12); gatewayStatus->setVerticalSpacing(5);
    const QStringList statusNames = {"系统", "设备", "告警", "运行"};
    QLabel **statusValues[] = {&systemValue, &devicesValue, &alarmsValue, &uptimeValue};
    for (int i = 0; i < 4; ++i) {
        QLabel *name = new QLabel(statusNames[i]); name->setObjectName("gatewaySub");
        *statusValues[i] = new QLabel("--"); (*statusValues[i])->setStyleSheet("color:#e6ecef;font-weight:700;");
        gatewayStatus->addWidget(name, i, 0); gatewayStatus->addWidget(*statusValues[i], i, 1, Qt::AlignRight);
    }
    gatewayLayout->addLayout(gatewayStatus);
    flow->addWidget(gateway, 3);
    QLabel *rightArrow = new QLabel("▶"); rightArrow->setStyleSheet("color:#e0a84b;font-size:18px;");
    flow->addWidget(rightArrow, 0, Qt::AlignCenter);

    QVBoxLayout *outputs = new QVBoxLayout; outputs->setSpacing(6);
    const QStringList outputNames = {"以太网", "4G / Wi-Fi", "ThingsBoard"};
    const QStringList outputDetails = {"ETH0 本地网络", "无线广域连接", "工业物联网平台"};
    for (int i = 0; i < outputNames.size(); ++i) {
        QLabel *state = nullptr;
        outputs->addWidget(ioNode(outputNames[i], outputDetails[i], &state));
        overviewNetworkStates << state;
    }
    flow->addLayout(outputs, 3);
    topologyLayout->addLayout(flow);
    layout->addWidget(topology, 3);

    QFrame *measurements = new QFrame; measurements->setObjectName("panel");
    QHBoxLayout *measurementLayout = new QHBoxLayout(measurements);
    measurementLayout->setContentsMargins(12, 7, 12, 7); measurementLayout->setSpacing(0);
    QLabel *measureTitle = new QLabel("关键测量"); measureTitle->setObjectName("panelTitle");
    measureTitle->setMinimumWidth(92); measurementLayout->addWidget(measureTitle);
    const QStringList sensorNames = {"温度", "压力", "流量"};
    for (int i = 0; i < sensorNames.size(); ++i) {
        measurementLayout->addWidget(rule(Qt::Vertical));
        QVBoxLayout *metric = new QVBoxLayout; metric->setContentsMargins(16, 0, 16, 0); metric->setSpacing(1);
        QLabel *name = new QLabel(sensorNames[i]); name->setObjectName("statusName");
        QLabel *value = new QLabel("--"); value->setObjectName("statusValue");
        metric->addWidget(name); metric->addWidget(value);
        measurementLayout->addLayout(metric, 1); overviewSensorValues << value;
    }
    layout->addWidget(measurements);

    QHBoxLayout *bottom = new QHBoxLayout; bottom->setSpacing(9);
    QFrame *chartPanel = new QFrame; chartPanel->setObjectName("panel");
    QVBoxLayout *chartLayout = new QVBoxLayout(chartPanel); chartLayout->setContentsMargins(10, 7, 10, 7);
    QLabel *chartTitle = new QLabel("实时趋势  /  最近 60 秒"); chartTitle->setObjectName("panelTitle");
    chartLayout->addWidget(chartTitle); chartLayout->addWidget(createTrend(overviewSeries, true));
    bottom->addWidget(chartPanel, 3);
    QFrame *alarmPanel = new QFrame; alarmPanel->setObjectName("panel");
    QVBoxLayout *alarmLayout = new QVBoxLayout(alarmPanel); alarmLayout->setContentsMargins(10, 7, 10, 8);
    QLabel *alarmTitle = new QLabel("活动告警"); alarmTitle->setObjectName("panelTitle"); alarmLayout->addWidget(alarmTitle);
    overviewAlarmTable = makeTable({"时间", "级别 / 内容"}); alarmLayout->addWidget(overviewAlarmTable);
    bottom->addWidget(alarmPanel, 2);
    layout->addLayout(bottom, 3);

    // Compatibility tables retain the existing snapshot update path but stay off-screen.
    overviewBusTable = makeTable({"接口", "状态"}); overviewBusTable->hide();
    overviewNetworkTable = makeTable({"接口", "状态"}); overviewNetworkTable->hide();
    return page;
}

QWidget *MainWindow::buildFieldbus()
{
    QWidget *page = new QWidget;
    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(18, 14, 18, 14);
    layout->addWidget(titleLabel("现场总线"));
    QTabWidget *tabs = new QTabWidget;

    QWidget *canPage = new QWidget; QVBoxLayout *canLayout = new QVBoxLayout(canPage);
    busTable = makeTable({"接口", "链路", "波特率", "数据来源"});
    canLayout->addWidget(busTable);
    QGroupBox *canCfg = new QGroupBox("CAN / CAN-FD 配置");
    QHBoxLayout *canCfgLayout = new QHBoxLayout(canCfg);
    QComboBox *canIf = new QComboBox; canIf->addItems({"can0", "can1"});
    QLineEdit *bitrate = edit("500000");
    QLineEdit *dbitrate = edit("2000000");
    QCheckBox *fd = new QCheckBox("CAN-FD");
    QPushButton *applyCan = actionButton("应用配置");
    canCfgLayout->addWidget(canIf); canCfgLayout->addWidget(bitrate); canCfgLayout->addWidget(dbitrate);
    canCfgLayout->addWidget(fd); canCfgLayout->addWidget(applyCan);
    connect(applyCan, &QPushButton::clicked, this, [=]() {
        QJsonObject p{{"interface", canIf->currentText()}, {"bitrate", bitrate->text().toInt()},
                      {"data_bitrate", dbitrate->text().toInt()}, {"fd", fd->isChecked()}, {"restart_ms", 100}};
        postAction("can_apply", p, "确认重新配置 " + canIf->currentText() + "？接口会短暂中断。");
    });
    canLayout->addWidget(canCfg);

    QGroupBox *co = new QGroupBox("CANopen 控制"); QGridLayout *coGrid = new QGridLayout(co);
    QComboBox *coIf = new QComboBox; coIf->addItems({"can0", "can1"});
    QSpinBox *node = new QSpinBox; node->setRange(0, 127); node->setValue(1);
    QComboBox *nmt = new QComboBox; nmt->addItems({"OPERATIONAL", "PRE-OPERATIONAL", "STOPPED", "RESET"});
    QPushButton *sendNmt = actionButton("发送 NMT", "danger");
    coGrid->addWidget(new QLabel("接口"), 0, 0); coGrid->addWidget(coIf, 0, 1);
    coGrid->addWidget(new QLabel("节点"), 0, 2); coGrid->addWidget(node, 0, 3);
    coGrid->addWidget(nmt, 0, 4); coGrid->addWidget(sendNmt, 0, 5);
    QLineEdit *coIndex = edit("0x2000"); QSpinBox *coSub = new QSpinBox; coSub->setRange(0, 255);
    QLineEdit *coValue = edit("0"); QPushButton *sdoWrite = actionButton("SDO 写入", "danger");
    coGrid->addWidget(new QLabel("索引"), 1, 0); coGrid->addWidget(coIndex, 1, 1);
    coGrid->addWidget(new QLabel("子索引"), 1, 2); coGrid->addWidget(coSub, 1, 3);
    coGrid->addWidget(coValue, 1, 4); coGrid->addWidget(sdoWrite, 1, 5);
    connect(sendNmt, &QPushButton::clicked, this, [=]() {
        postAction("canopen_nmt", {{"interface", coIf->currentText()}, {"node_id", node->value()},
                   {"state", nmt->currentText()}}, "确认向节点发送 NMT " + nmt->currentText() + "？");
    });
    connect(sdoWrite, &QPushButton::clicked, this, [=]() {
        bool ok = false; int index = coIndex->text().toInt(&ok, 0);
        if (!ok) { QMessageBox::warning(this, "参数错误", "对象索引格式错误"); return; }
        postAction("canopen_sdo_write", {{"interface", coIf->currentText()}, {"node_id", node->value()},
                   {"index", index}, {"subindex", coSub->value()}, {"value", coValue->text().toInt()}, {"size", 4}},
                   "确认写入 CANopen SDO？错误值可能改变设备行为。");
    });
    canLayout->addWidget(co);
    tabs->addTab(canPage, "CAN / CANopen");

    QWidget *rsPage = new QWidget; QVBoxLayout *rsLayout = new QVBoxLayout(rsPage);
    QGroupBox *rs = new QGroupBox("Modbus RTU 配置"); QFormLayout *rsForm = new QFormLayout(rs);
    QLineEdit *rsPort = edit("/dev/ttyAS5"); QLineEdit *rsBaud = edit("9600");
    QSpinBox *rsUnit = new QSpinBox; rsUnit->setRange(1, 247); rsUnit->setValue(1);
    QLineEdit *rsPoll = edit("1000"); QPushButton *saveRs = actionButton("保存并应用");
    rsForm->addRow("串口", rsPort); rsForm->addRow("波特率", rsBaud); rsForm->addRow("站号", rsUnit);
    rsForm->addRow("轮询周期(ms)", rsPoll); rsForm->addRow(saveRs);
    connect(saveRs, &QPushButton::clicked, this, [=]() {
        postAction("rs485_config", {{"port", rsPort->text()}, {"baudrate", rsBaud->text().toInt()},
                   {"unit_id", rsUnit->value()}, {"poll_ms", rsPoll->text().toInt()}}, "确认修改 Modbus RTU 参数？");
    });
    rsLayout->addWidget(rs); rsLayout->addStretch(); tabs->addTab(rsPage, "RS485 / Modbus");

    QWidget *ecPage = new QWidget; QVBoxLayout *ecLayout = new QVBoxLayout(ecPage);
    QGroupBox *ec = new QGroupBox("EtherCAT CoE 控制"); QFormLayout *ecForm = new QFormLayout(ec);
    QSpinBox *slave = new QSpinBox; slave->setRange(1, 65535); slave->setValue(1);
    QLineEdit *ecIndex = edit("0x6040"); QSpinBox *ecSub = new QSpinBox; ecSub->setRange(0, 255);
    QLineEdit *ecValue = edit("06 00"); QPushButton *ecWrite = actionButton("CoE SDO 写入", "danger");
    QPushButton *ecCycle = actionButton("执行 1000 次周期测试");
    ecForm->addRow("从站", slave); ecForm->addRow("索引", ecIndex); ecForm->addRow("子索引", ecSub);
    ecForm->addRow("十六进制数据", ecValue); ecForm->addRow(ecWrite); ecForm->addRow(ecCycle);
    connect(ecWrite, &QPushButton::clicked, this, [=]() {
        bool ok = false; int index = ecIndex->text().toInt(&ok, 0);
        if (!ok) { QMessageBox::warning(this, "参数错误", "对象索引格式错误"); return; }
        postAction("ethercat_sdo_write", {{"slave", slave->value()}, {"index", index},
                   {"subindex", ecSub->value()}, {"value", ecValue->text()}},
                   "确认写入 EtherCAT 从站？错误控制字可能导致设备动作。");
    });
    connect(ecCycle, &QPushButton::clicked, this, [=]() {
        postAction("ethercat_cycle", {{"count", 1000}, {"period_us", 1000}},
                   "确认执行 1 秒 EtherCAT 周期测试？");
    });
    ecLayout->addWidget(ec); ecLayout->addStretch(); tabs->addTab(ecPage, "EtherCAT");
    layout->addWidget(tabs, 1);
    return page;
}

QWidget *MainWindow::buildNetwork()
{
    QWidget *page = new QWidget; QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(18, 14, 18, 14); layout->addWidget(titleLabel("网络通信"));
    networkTable = makeTable({"接口", "链路", "IPv4 地址", "数据来源"});
    layout->addWidget(networkTable, 1);
    QHBoxLayout *controls = new QHBoxLayout;
    for (const QString &profile : {QString("ec20a"), QString("ec20b")}) {
        QGroupBox *box = new QGroupBox(profile.toUpper()); QHBoxLayout *row = new QHBoxLayout(box);
        QPushButton *connectButton = actionButton("拨号"); QPushButton *disconnectButton = actionButton("断开", "danger");
        row->addWidget(connectButton); row->addWidget(disconnectButton);
        connect(connectButton, &QPushButton::clicked, this, [=]() {
            postAction("ec20", {{"profile", profile}, {"operation", "connect"}}, "确认启动 " + profile + " 拨号？");
        });
        connect(disconnectButton, &QPushButton::clicked, this, [=]() {
            postAction("ec20", {{"profile", profile}, {"operation", "disconnect"}}, "确认断开 " + profile + "？");
        });
        controls->addWidget(box);
    }
    layout->addLayout(controls);
    return page;
}

QWidget *MainWindow::buildDevices()
{
    QWidget *page = new QWidget; QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(18, 14, 18, 14); layout->addWidget(titleLabel("设备监控"));
    deviceTable = makeTable({"指标", "实时值", "状态", "数据来源"});
    layout->addWidget(deviceTable, 1);
    QFrame *chartCard = new QFrame; chartCard->setObjectName("card"); QVBoxLayout *chartLayout = new QVBoxLayout(chartCard);
    chartLayout->addWidget(titleLabel("设备趋势（最近60秒）")); chartLayout->addWidget(createTrend(deviceSeries, false));
    layout->addWidget(chartCard, 2);
    return page;
}

QWidget *MainWindow::buildAlarms()
{
    QWidget *page = new QWidget; QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(18, 14, 18, 14);
    QHBoxLayout *top = new QHBoxLayout; top->addWidget(titleLabel("告警记录")); top->addStretch();
    QPushButton *ack = actionButton("确认选中告警"); top->addWidget(ack); layout->addLayout(top);
    alarmTable = makeTable({"ID", "时间", "级别", "来源", "内容", "状态"});
    layout->addWidget(alarmTable, 1);
    connect(ack, &QPushButton::clicked, this, [this]() {
        int row = alarmTable->currentRow();
        if (row < 0) { QMessageBox::information(this, "告警", "请先选择一条告警"); return; }
        int id = alarmTable->item(row, 0)->text().toInt();
        sendJson("POST", QString("/alarms/%1/ack").arg(id), {}, "ack");
    });
    return page;
}

QWidget *MainWindow::buildSettings()
{
    QWidget *page = new QWidget; QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(18, 14, 18, 14); layout->addWidget(titleLabel("系统设置"));
    QHBoxLayout *columns = new QHBoxLayout;
    QGroupBox *display = new QGroupBox("显示与数据"); QFormLayout *form = new QFormLayout(display);
    brightnessSlider = new QSlider(Qt::Horizontal); brightnessSlider->setRange(10, 255); brightnessSlider->setValue(220);
    demoCheck = new QCheckBox("启用工业数据演示（人工）"); demoCheck->setChecked(false);
    refreshCombo = new QComboBox; refreshCombo->addItem("0.5 秒", 500); refreshCombo->addItem("1 秒", 1000);
    refreshCombo->addItem("2 秒", 2000); refreshCombo->addItem("5 秒", 5000); refreshCombo->setCurrentIndex(1);
    form->addRow("背光亮度", brightnessSlider); form->addRow("演示数据", demoCheck); form->addRow("刷新周期", refreshCombo);
    QPushButton *save = actionButton("保存设置"); form->addRow(save);
    connect(save, &QPushButton::clicked, this, [this]() {
        QJsonObject body{{"brightness", brightnessSlider->value()}, {"demo_mode", demoCheck->isChecked()},
                         {"refresh_ms", refreshCombo->currentData().toInt()}, {"page_cycle_seconds", 0}};
        sendJson("PUT", "/settings", body, "settings");
        postAction("brightness", {{"value", brightnessSlider->value()}}, "确认应用新的背光亮度？");
    });
    columns->addWidget(display, 1);

    QGroupBox *services = new QGroupBox("服务与系统"); QVBoxLayout *serviceLayout = new QVBoxLayout(services);
    for (const QString &name : {QString("thingsboard"), QString("bluetooth"), QString("ntp")}) {
        QHBoxLayout *row = new QHBoxLayout; row->addWidget(new QLabel(name)); row->addStretch();
        QPushButton *start = actionButton("启动", "secondary"); QPushButton *restart = actionButton("重启", "secondary");
        QPushButton *stop = actionButton("停止", "danger"); row->addWidget(start); row->addWidget(restart); row->addWidget(stop);
        connect(start, &QPushButton::clicked, this, [=]() { postAction("service", {{"service", name}, {"operation", "start"}}, "确认启动 " + name + "？"); });
        connect(restart, &QPushButton::clicked, this, [=]() { postAction("service", {{"service", name}, {"operation", "restart"}}, "确认重启 " + name + "？"); });
        connect(stop, &QPushButton::clicked, this, [=]() { postAction("service", {{"service", name}, {"operation", "stop"}}, "确认停止 " + name + "？"); });
        serviceLayout->addLayout(row);
    }
    QPushButton *reboot = actionButton("重启整机", "danger");
    connect(reboot, &QPushButton::clicked, this, [this]() {
        postAction("system_reboot", {}, "确认重启 OmniGate？所有现场通信将暂时中断。");
    });
    serviceLayout->addStretch(); serviceLayout->addWidget(reboot);
    columns->addWidget(services, 1); layout->addLayout(columns);
    layout->addWidget(titleLabel("最近控制审计"));
    auditTable = makeTable({"时间", "动作", "目标", "结果"}); layout->addWidget(auditTable, 1);
    return page;
}

void MainWindow::showPage(int index)
{
    if (index < 0 || index >= pages->count()) return;
    pages->setCurrentIndex(index);
    for (int i = 0; i < navButtons.size(); ++i) navButtons[i]->setChecked(i == index);
    if (index == 4) sendJson("GET", "/alarms?limit=500", {}, "alarms");
    if (index == 5) sendJson("GET", "/audit", {}, "audit");
}

void MainWindow::requestSnapshot()
{
    if (requestActive) return;
    requestActive = true;
    QNetworkRequest req(QUrl(QString(kBaseUrl) + "/snapshot"));
    QNetworkReply *reply = networkManager.get(req);
    reply->setProperty("kind", "snapshot");
}

void MainWindow::sendJson(const QByteArray &method, const QString &path,
                          const QJsonObject &body, const QString &kind)
{
    QNetworkRequest req(QUrl(QString(kBaseUrl) + path));
    req.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");
    QNetworkReply *reply = networkManager.sendCustomRequest(req, method, QJsonDocument(body).toJson(QJsonDocument::Compact));
    reply->setProperty("kind", kind);
}

void MainWindow::postAction(const QString &action, const QJsonObject &params,
                            const QString &description)
{
    if (QMessageBox::warning(this, "操作确认", description,
                             QMessageBox::Yes | QMessageBox::No, QMessageBox::No) != QMessageBox::Yes) return;
    sendJson("POST", "/actions", {{"action", action}, {"params", params}, {"confirmed", true}}, "action");
}

void MainWindow::handleReply(QNetworkReply *reply)
{
    const QString kind = reply->property("kind").toString();
    if (kind == "snapshot") requestActive = false;
    const QByteArray raw = reply->readAll();
    const QJsonDocument doc = QJsonDocument::fromJson(raw);
    if (reply->error() != QNetworkReply::NoError || !doc.isObject()) {
        connectionLabel->setText("● 数据服务离线");
        connectionLabel->setStyleSheet(QString());
        if (kind != "snapshot") QMessageBox::critical(this, "操作失败", QString::fromUtf8(raw.isEmpty() ? reply->errorString().toUtf8() : raw));
        reply->deleteLater(); return;
    }
    const QJsonObject root = doc.object();
    if (!root.value("ok").toBool(true)) {
        QMessageBox::warning(this, "操作失败", root.value("error").toString("未知错误"));
    } else if (kind == "snapshot") {
        updateSnapshot(root);
    } else if (kind == "alarms") {
        const QJsonArray rows = root.value("alarms").toArray(); alarmTable->setRowCount(rows.size());
        for (int i = 0; i < rows.size(); ++i) {
            const QJsonObject x = rows[i].toObject();
            const QString timeText = QDateTime::fromSecsSinceEpoch(x.value("ts").toVariant().toLongLong()).toString("yyyy-MM-dd hh:mm:ss");
            alarmTable->setItem(i, 0, cell(QString::number(x.value("id").toInt())));
            alarmTable->setItem(i, 1, cell(timeText));
            alarmTable->setItem(i, 2, cell(x.value("severity").toString()));
            alarmTable->setItem(i, 3, cell(x.value("source").toString()));
            alarmTable->setItem(i, 4, cell(sourceText(x, x.value("message").toString())));
            alarmTable->setItem(i, 5, cell(x.value("state").toString()));
        }
    } else if (kind == "audit") {
        const QJsonArray rows = root.value("audit").toArray(); auditTable->setRowCount(rows.size());
        for (int i = 0; i < rows.size(); ++i) {
            QJsonObject x = rows[i].toObject();
            auditTable->setItem(i, 0, cell(QDateTime::fromSecsSinceEpoch(x.value("ts").toVariant().toLongLong()).toString("MM-dd hh:mm:ss")));
            auditTable->setItem(i, 1, cell(x.value("action").toString())); auditTable->setItem(i, 2, cell(x.value("target").toString()));
            auditTable->setItem(i, 3, cell(x.value("result").toString(), kMuted));
        }
    } else {
        QMessageBox::information(this, "操作完成", "操作已执行并写入审计记录");
        requestSnapshot();
        if (pages->currentIndex() == 5) sendJson("GET", "/audit", {}, "audit");
    }
    reply->deleteLater();
}

QString MainWindow::sourceText(const QJsonObject &item, const QString &text) const
{
    const QString source = item.value("source").toString("real");
    if (source == "demo") return text + "  [演示]";
    if (source == "unavailable") return text + "  [不可用]";
    return text;
}

QString MainWindow::uptimeText(qint64 seconds)
{
    qint64 days = seconds / 86400; seconds %= 86400;
    return QString("%1天 %2:%3").arg(days).arg(seconds / 3600, 2, 10, QChar('0')).arg((seconds / 60) % 60, 2, 10, QChar('0'));
}

void MainWindow::updateSnapshot(const QJsonObject &root)
{
    connectionLabel->setText("● 数据在线"); connectionLabel->setStyleSheet(QString());
    const qint64 timestamp = root.value("timestamp").toVariant().toLongLong();
    clockLabel->setText(QDateTime::fromSecsSinceEpoch(timestamp).toString("yyyy-MM-dd  hh:mm:ss"));
    const QJsonObject system = root.value("system").toObject();
    const QJsonObject summary = root.value("summary").toObject();
    systemValue->setText(summary.value("status").toString());
    devicesValue->setText(QString::number(summary.value("online_devices").toInt()));
    alarmsValue->setText(QString::number(summary.value("today_alarms").toInt()));
    alarmSummaryLabel->setText(QString("报警 %1").arg(summary.value("today_alarms").toInt()));
    uptimeValue->setText(uptimeText(system.value("uptime_seconds").toVariant().toLongLong()));
    cpuValue->setText(QString("CPU  %1%").arg(system.value("cpu").toDouble(), 0, 'f', 0));
    memoryValue->setText(QString("内存  %1%").arg(system.value("memory").toDouble(), 0, 'f', 0));
    temperatureValue->setText(QString("温度  %1°C").arg(system.value("temperature").toDouble(), 0, 'f', 1));
    storageValue->setText(QString("存储  %1%").arg(system.value("storage").toDouble(), 0, 'f', 0));

    const QJsonArray buses = root.value("buses").toArray();
    overviewBusTable->setRowCount(buses.size()); busTable->setRowCount(buses.size());
    for (int i = 0; i < buses.size(); ++i) {
        QJsonObject x = buses[i].toObject(); QString name = x.value("name").toString(); QString state = x.value("state").toString();
        const QColor color = kMuted;
        overviewBusTable->setItem(i, 0, cell(name)); overviewBusTable->setItem(i, 1, cell(sourceText(x, state), color));
        busTable->setItem(i, 0, cell(name)); busTable->setItem(i, 1, cell(state, color));
        busTable->setItem(i, 2, cell(x.value("bitrate").toInt() ? QString::number(x.value("bitrate").toInt()) : "--"));
        busTable->setItem(i, 3, cell(x.value("source").toString()));
        if (i < overviewBusStates.size()) {
            const bool online = x.value("online").toBool();
            overviewBusStates[i]->setText(online ? "正常" : sourceText(x, state));
            overviewBusStates[i]->setStyleSheet(QString("color:%1;font-weight:700;").arg(online ? kSuccess.name() : kWarning.name()));
        }
    }

    const QJsonArray networks = root.value("networks").toArray();
    networkTable->setRowCount(networks.size()); overviewNetworkTable->setRowCount(qMin(4, networks.size()));
    for (int i = 0; i < networks.size(); ++i) {
        QJsonObject x = networks[i].toObject(); QString name = x.value("name").toString();
        QString state = x.value("address").toString(); if (state.isEmpty()) state = x.value("state").toString();
        const QColor color = kMuted;
        networkTable->setItem(i, 0, cell(name)); networkTable->setItem(i, 1, cell(x.value("state").toString(), color));
        networkTable->setItem(i, 2, cell(x.value("address").toString("--"))); networkTable->setItem(i, 3, cell(x.value("source").toString()));
        if (i < 4) { overviewNetworkTable->setItem(i, 0, cell(name)); overviewNetworkTable->setItem(i, 1, cell(sourceText(x, state), color)); }
        if (i < overviewNetworkStates.size()) {
            const bool online = x.value("online").toBool();
            overviewNetworkStates[i]->setText(online ? "已连接" : sourceText(x, x.value("state").toString("离线")));
            overviewNetworkStates[i]->setStyleSheet(QString("color:%1;font-weight:700;").arg(online ? kSuccess.name() : kWarning.name()));
        }
    }

    const QJsonArray sensors = root.value("sensors").toArray();
    deviceTable->setRowCount(sensors.size());
    for (int i = 0; i < sensors.size(); ++i) {
        QJsonObject x = sensors[i].toObject();
        deviceTable->setItem(i, 0, cell(x.value("name").toString()));
        deviceTable->setItem(i, 1, cell(QString("%1 %2").arg(x.value("value").toDouble(), 0, 'f', 1).arg(x.value("unit").toString())));
        deviceTable->setItem(i, 2, cell(x.value("state").toString(), kMuted));
        deviceTable->setItem(i, 3, cell(x.value("source").toString() == "demo" ? "演示" : "真实", kMuted));
        if (i < overviewSensorValues.size()) {
            overviewSensorValues[i]->setText(QString("%1 %2").arg(x.value("value").toDouble(), 0, 'f', 1).arg(x.value("unit").toString()));
        }
    }
    updateSeries(sensors);

    const QJsonArray alarmRows = root.value("alarms").toObject().value("recent").toArray();
    overviewAlarmTable->setRowCount(alarmRows.size()); alarmTable->setRowCount(alarmRows.size());
    for (int i = 0; i < alarmRows.size(); ++i) {
        QJsonObject x = alarmRows[i].toObject();
        QString timeText = QDateTime::fromSecsSinceEpoch(x.value("ts").toVariant().toLongLong()).toString("MM-dd hh:mm");
        overviewAlarmTable->setItem(i, 0, cell(timeText)); overviewAlarmTable->setItem(i, 1, cell(sourceText(x, x.value("message").toString())));
        alarmTable->setItem(i, 0, cell(QString::number(x.value("id").toInt()))); alarmTable->setItem(i, 1, cell(timeText));
        alarmTable->setItem(i, 2, cell(x.value("severity").toString())); alarmTable->setItem(i, 3, cell(x.value("source").toString()));
        alarmTable->setItem(i, 4, cell(x.value("message").toString())); alarmTable->setItem(i, 5, cell(x.value("state").toString()));
    }

    const QJsonObject settings = root.value("settings").toObject();
    brightnessSlider->setValue(settings.value("brightness").toInt(220)); demoCheck->setChecked(settings.value("demo_mode").toBool(false));
    demoBadge->setVisible(settings.value("demo_mode").toBool(false));
    int refresh = settings.value("refresh_ms").toInt(1000); int combo = refreshCombo->findData(refresh);
    if (combo >= 0)
        refreshCombo->setCurrentIndex(combo);
    refreshTimer.setInterval(refresh);
    int cycle = settings.value("page_cycle_seconds").toInt();
    if (cycle > 0) pageTimer.start(cycle * 1000); else pageTimer.stop();
}

void MainWindow::updateSeries(const QJsonArray &sensors)
{
    if (sensors.size() < 3) return;
    ++sampleIndex;
    const QList<QList<QLineSeries *> *> sets = {&overviewSeries, &deviceSeries};
    for (QList<QLineSeries *> *set : sets) {
        for (int i = 0; i < 3; ++i) {
            QLineSeries *series = set->at(i);
            QVector<QPointF> points = series->pointsVector();
            for (QPointF &point : points) point.setX(point.x() - 1);
            while (!points.isEmpty() && points.first().x() < 0) points.removeFirst();
            points.append(QPointF(59, sensors[i].toObject().value("value").toDouble()));
            series->replace(points);
        }
    }
}
