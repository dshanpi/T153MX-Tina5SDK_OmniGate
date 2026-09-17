#ifndef OMNIGATE_MAINWINDOW_H
#define OMNIGATE_MAINWINDOW_H

#include <QJsonObject>
#include <QMainWindow>
#include <QNetworkAccessManager>
#include <QPointer>
#include <QTimer>
#include <QtCharts/QLineSeries>

QT_BEGIN_NAMESPACE
class QCheckBox;
class QComboBox;
class QLabel;
class QNetworkReply;
class QPushButton;
class QSlider;
class QStackedWidget;
class QTableWidget;
class QTabWidget;
QT_END_NAMESPACE

QT_CHARTS_USE_NAMESPACE

class MainWindow : public QMainWindow
{
    Q_OBJECT
public:
    explicit MainWindow(QWidget *parent = nullptr);

private slots:
    void requestSnapshot();
    void handleReply(QNetworkReply *reply);
    void showPage(int index);

private:
    QWidget *buildOverview();
    QWidget *buildFieldbus();
    QWidget *buildNetwork();
    QWidget *buildDevices();
    QWidget *buildAlarms();
    QWidget *buildSettings();
    QWidget *metricCard(const QString &title, QLabel **value, const QString &color);
    QTableWidget *makeTable(const QStringList &headers);
    QPushButton *actionButton(const QString &text, const QString &kind = "primary");
    void applyTheme();
    void updateSnapshot(const QJsonObject &root);
    void updateSeries(const QJsonArray &sensors);
    void sendJson(const QByteArray &method, const QString &path,
                  const QJsonObject &body, const QString &kind);
    void postAction(const QString &action, const QJsonObject &params,
                    const QString &description);
    QString sourceText(const QJsonObject &item, const QString &text) const;
    static QString uptimeText(qint64 seconds);

    QNetworkAccessManager networkManager;
    QTimer refreshTimer;
    QTimer pageTimer;
    QStackedWidget *pages = nullptr;
    QList<QPushButton *> navButtons;
    QLabel *clockLabel = nullptr;
    QLabel *connectionLabel = nullptr;
    QLabel *alarmSummaryLabel = nullptr;
    QLabel *demoBadge = nullptr;
    QLabel *systemValue = nullptr;
    QLabel *devicesValue = nullptr;
    QLabel *alarmsValue = nullptr;
    QLabel *uptimeValue = nullptr;
    QLabel *cpuValue = nullptr;
    QLabel *memoryValue = nullptr;
    QLabel *temperatureValue = nullptr;
    QLabel *storageValue = nullptr;
    QList<QLabel *> overviewSensorValues;
    QList<QLabel *> overviewBusStates;
    QList<QLabel *> overviewNetworkStates;
    QTableWidget *overviewBusTable = nullptr;
    QTableWidget *overviewNetworkTable = nullptr;
    QTableWidget *overviewAlarmTable = nullptr;
    QTableWidget *busTable = nullptr;
    QTableWidget *networkTable = nullptr;
    QTableWidget *deviceTable = nullptr;
    QTableWidget *alarmTable = nullptr;
    QTableWidget *auditTable = nullptr;
    QSlider *brightnessSlider = nullptr;
    QCheckBox *demoCheck = nullptr;
    QComboBox *refreshCombo = nullptr;
    QList<QLineSeries *> overviewSeries;
    QList<QLineSeries *> deviceSeries;
    int sampleIndex = 0;
    bool requestActive = false;
};

#endif
