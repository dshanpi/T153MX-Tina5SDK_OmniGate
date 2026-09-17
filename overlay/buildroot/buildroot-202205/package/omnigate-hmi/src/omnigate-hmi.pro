QT += core gui widgets network charts
CONFIG += c++11 release
TARGET = omnigate-hmi
TEMPLATE = app
SOURCES += main.cpp mainwindow.cpp
HEADERS += mainwindow.h
target.path = /usr/bin
INSTALLS += target
