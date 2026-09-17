#include <QApplication>
#include <QFont>
#include "mainwindow.h"

int main(int argc, char *argv[])
{
    QApplication app(argc, argv);
    app.setApplicationName("OmniGate HMI");
    app.setOverrideCursor(Qt::BlankCursor);
    QFont font("WenQuanYi Zen Hei", 12);
    font.setStyleStrategy(QFont::PreferAntialias);
    app.setFont(font);
    MainWindow window;
    window.showFullScreen();
    return app.exec();
}
