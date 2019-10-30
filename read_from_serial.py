'''
 * Copyright 2018-2019. All rights reserved.
 * Этот файл содержит информацию, являющуюся
 * собственностью коллектива исполнителей по проекту
 * РФФИ № 18-38-20188.
 *
 * Любая часть этого файла не может быть скопирована,
 * исправлена, переведена на другие языки,
 * локализована или модифицирована любым способом,
 * откомпилирована, передана по сети с или на
 * любую компьютерную систему без предварительного
 * соглашения с коллективом проекта РФФИ № 18-38-20188
 * (в лице руководителя Шайхутдинова Д.В.).
'''

# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import matplotlib
# Make sure that we are using QT5
matplotlib.use('Qt5Agg')
import serial
import os
import syslog
import time
import sys
import simple_list
from PyQt5 import QtWidgets, QtCore
from PyQt5 import QtGui
from PyQt5.QtCore import QCoreApplication
import warnings
import serial.tools.list_ports
import csv
from datetime import datetime
import datetime as dt
import shutil
import sending_email
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
#from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib as mpl
from pathlib import Path
import subprocess
import boto3
from clickhouse_driver import Client

global ard_tp_
ard_tp_ = 15

global i_a, i_b, i_c, i_n, u_a, u_b, u_c
global mag_i_a, mag_i_b, mag_i_c, mag_i_n, mag_u_a, mag_u_b, mag_u_c
# Entrance to Object Storage (boto3)
global region_name_
global aws_access_key_id_
global aws_secret_access_key_
global backet_
region_name_='ru-central1'
aws_access_key_id_='XRvmi6FXPjmNL1VuCiwZ'
aws_secret_access_key_='PISQFA71JyIqqTVk48Hn6FBqquez9gAvyQUD7bfC'
bucket_ = 'bucketdataset'
# Entrance to ClickHouse (db1)
global host_
global pass_
global user_
global db_
global ca_certs_
host_='rc1c-hpbo72qg2rsq2gkl.mdb.yandexcloud.net'
pass_='8635255240'
user_='user1'
db_  = 'db1'
ca_certs_ = '/usr/local/share/ca-certificates/Yandex/YandexInternalRootCA.crt'



autostart = False
del_sent_files = False

Gain = 1000

time_to_sleep = 15

port_name = '/dev/ttyACM0'
port_speed = 9600
port_timeout = 10

addr_to   = "d.v.shaykhutdinov@gmail.com"
theme = "Отчет за день"
email_msg = "Уважаемые коллеги!\
            \n\nСм. приложенный файл.\
            \n\nС уважением,\nВаша Raspberry Pi."

ProtocolTypes = ['V1. Основные данные и гармоники рассчитываются на МП. Разделитель %',
                 'V2. МП передает полный набор осциллограмм. Разделители | и %',
                 'V3. Тестовый протокол. Разделитель %',
                 'V4. Прием данных (7 сигналов по 50 гармоник) из облака']
speeds = ['1200','2400', '4800', '9600', '19200', '38400', '57600', '115200']
ports = [p.device for p in serial.tools.list_ports.comports()]

class MeinDynamicMplCanvas(FigureCanvas):
    """A canvas that updates itself every second with a new plot."""

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = plt.figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        mpl.rcParams.update({'font.size':8})
        

        self.compute_initial_figure()

        FigureCanvas.__init__(self, fig)
        self.setParent(parent)

        FigureCanvas.setSizePolicy(self,
                                   QtWidgets.QSizePolicy.Expanding,
                                   QtWidgets.QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)
        timer = QtCore.QTimer(self)
        #self.data = data
        #timer.timeout.connect(self.update_figure)
        #timer.start(1000)

    def compute_initial_figure(self):
        pass

    def update_figure(self, data=[], title = ""):
        self.axes.cla()
        ind = [i/5 for i in range(len(data))]
        self.axes.plot(ind, data, 'r')
        self.axes.yaxis.grid(True)
        self.axes.xaxis.grid(True)
        self.axes.title.set_text("Осциллограмма,"+ title + "vs время(мс)")
        self.draw()

    def update_figure_g(self, data=[], title = ""):
        self.axes.cla()
        ind = [i+0.5 for i in range(len(data))]
        self.axes.bar(ind, data)
        self.axes.yaxis.grid(True)
        self.axes.xaxis.grid(True)
        self.axes.title.set_text('Гар-ки(1-49) % DFT(1)')
        self.draw()


class SimpleListApp(QtWidgets.QMainWindow, simple_list.Ui_MainWindow, QCoreApplication):
    def __init__(self):
        # This is need to access to variables and methods
        # in simple_list file
        super().__init__()
        self.setupUi(self) # This is need to initialise our design
        self.readButton.clicked.connect(self.read_start_button)
        # self.stopButton.clicked.connect(self.instance().quit)
        self.connectButton.clicked.connect(self.connect_button)
        self.disconnectButton.clicked.connect(self.disconnect_button)
        self.readCyclicButtonStart.clicked.connect(self.read_cyclic_start)
        self.readCyclicButtonStop.clicked.connect(self.read_cyclic_stop)
        self.pushButtonWriteTunning.clicked.connect(self.writeTunning)
        self.TunningCheckBox.clicked.connect(self.TunningShow)
        self.pushButtonTune.clicked.connect(self.TuneCoeffPoints)
        self.msg_tabData = []
        self.lists_clear()
        self.processEvents()
        
        self.Port.addItems(ports)
        self.Port.setCurrentIndex(len(ports)-1)
        self.Speed.addItems(speeds)
        self.Speed.setCurrentIndex(6)
        self.Protocol.addItems(ProtocolTypes)
        self.Protocol.setCurrentIndex(1)
        self.tabWidget.setCurrentIndex(0)
        self.processEvents()       
        self.labelReadDone.setVisible(0)
        '''try:
            session = boto3.session.Session()
            s3 = session.client(service_name='s3', endpoint_url='https://storage.yandexcloud.net',
                                region_name=region_name_,
                                aws_access_key_id=aws_access_key_id_,
                                aws_secret_access_key=aws_secret_access_key_)
            get_object_response = s3.get_object(Bucket=bucket_,Key='data/actual_data.csv')
            msg3 = get_object_response['Body'].read().decode().split(';')
        except Exception as e:
            self.InternetCheckBox.setChecked(0)'''
            


        #Раздел посвящен меню юстировки
        self.coeffpoints = [1, 1, 1, 1, 1, 1, 1, 5, 6, 5, 0.3535, -0.7255, 0.5175, 0.8697, -0.0153, -0.1801, 0.3741, -0.2569, 1.0564, 0.0067, 0.4643, -1.0404, 0.8257, 0.7535, -0.0033]
        self.TunningVisible(0)
        self.tunning_f = 'Tunning_coeff.csv'
        if os.path.exists(self.tunning_f):
            with open(self.tunning_f, "r", newline = '') as f:
                reader = csv.reader(f, delimiter=";")
                self.coeffpoints1 = [cp for cp in reader]
                self.coeffpoints1 = [float(cp) for cp in self.coeffpoints1[0]]
            if len(self.coeffpoints1) == 25:
                self.coeffpoints = self.coeffpoints1
        else:
            with open(self.tunning_f, "w", newline = '') as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(self.coeffpoints)
        
        if self.GraphicsCheckBox.isChecked():
            self.GraphicsCheckBox.setChecked(0)

        '''self.file_menu = QtWidgets.QMenu('&File', self)
        self.menuBar().addMenu(self.file_menu)
        self.help_menu = QtWidgets.QMenu('&Help', self)
        self.menuBar().addSeparator()
        self.menuBar().addMenu(self.help_menu)
        self.help_menu.addAction('&About', self.about)'''

        self.IagGrView_ = self.IagGrView
        IagGrView__ = QtWidgets.QVBoxLayout(self.IagGrView_)
        self.IagGrView___ = MeinDynamicMplCanvas(self.IagGrView_, width=5,
                                                 height=4, dpi=100)
        IagGrView__.addWidget(self.IagGrView___)
        
        self.IamGrView_ = self.IamGrView
        IamGrView__ = QtWidgets.QVBoxLayout(self.IamGrView_)
        self.IamGrView___ = MeinDynamicMplCanvas(self.IamGrView_, width=5,
                                                 height=4, dpi=100)
        IamGrView__.addWidget(self.IamGrView___)
        
        self.IbgGrView_ = self.IbgGrView
        IbgGrView__ = QtWidgets.QVBoxLayout(self.IbgGrView_)
        self.IbgGrView___ = MeinDynamicMplCanvas(self.IbgGrView_, width=5,
                                                 height=4, dpi=100)
        IbgGrView__.addWidget(self.IbgGrView___)
        
        self.IbmGrView_ = self.IbmGrView
        IbmGrView__ = QtWidgets.QVBoxLayout(self.IbmGrView_)
        self.IbmGrView___ = MeinDynamicMplCanvas(self.IbmGrView_, width=5,
                                                 height=4, dpi=100)
        IbmGrView__.addWidget(self.IbmGrView___)
        
        self.IcgGrView_ = self.IcgGrView
        IcgGrView__ = QtWidgets.QVBoxLayout(self.IcgGrView_)
        self.IcgGrView___ = MeinDynamicMplCanvas(self.IcgGrView_, width=5,
                                                 height=4, dpi=100)
        IcgGrView__.addWidget(self.IcgGrView___)
        
        self.IcmGrView_ = self.IcmGrView
        IcmGrView__ = QtWidgets.QVBoxLayout(self.IcmGrView_)
        self.IcmGrView___ = MeinDynamicMplCanvas(self.IcmGrView_, width=5,
                                                 height=4, dpi=100)
        IcmGrView__.addWidget(self.IcmGrView___)
        
        self.IngGrView_ = self.IngGrView
        IngGrView__ = QtWidgets.QVBoxLayout(self.IngGrView_)
        self.IngGrView___ = MeinDynamicMplCanvas(self.IngGrView_, width=5,
                                                 height=4, dpi=100)
        IngGrView__.addWidget(self.IngGrView___)
        
        self.InmGrView_ = self.InmGrView
        InmGrView__ = QtWidgets.QVBoxLayout(self.InmGrView_)
        self.InmGrView___ = MeinDynamicMplCanvas(self.InmGrView_, width=5,
                                                 height=4, dpi=100)
        InmGrView__.addWidget(self.InmGrView___)
        
        self.UagGrView_ = self.UagGrView
        UagGrView__ = QtWidgets.QVBoxLayout(self.UagGrView_)
        self.UagGrView___ = MeinDynamicMplCanvas(self.UagGrView_, width=5,
                                                 height=4, dpi=100)
        UagGrView__.addWidget(self.UagGrView___)
        
        self.UamGrView_ = self.UamGrView
        UamGrView__ = QtWidgets.QVBoxLayout(self.UamGrView_)
        self.UamGrView___ = MeinDynamicMplCanvas(self.UamGrView_, width=5,
                                                 height=4, dpi=100)
        UamGrView__.addWidget(self.UamGrView___)
        
        self.UbgGrView_ = self.UbgGrView
        UbgGrView__ = QtWidgets.QVBoxLayout(self.UbgGrView_)
        self.UbgGrView___ = MeinDynamicMplCanvas(self.UbgGrView_, width=5,
                                                 height=4, dpi=100)
        UbgGrView__.addWidget(self.UbgGrView___)
        
        self.UbmGrView_ = self.UbmGrView
        UbmGrView__ = QtWidgets.QVBoxLayout(self.UbmGrView_)
        self.UbmGrView___ = MeinDynamicMplCanvas(self.UbmGrView_, width=5,
                                                 height=4, dpi=100)
        UbmGrView__.addWidget(self.UbmGrView___)
        
        self.UcgGrView_ = self.UcgGrView
        UcgGrView__ = QtWidgets.QVBoxLayout(self.UcgGrView_)
        self.UcgGrView___ = MeinDynamicMplCanvas(self.UcgGrView_, width=5,
                                                 height=4, dpi=100)
        UcgGrView__.addWidget(self.UcgGrView___)
        
        self.UcmGrView_ = self.UcmGrView
        UcmGrView__ = QtWidgets.QVBoxLayout(self.UcmGrView_)
        self.UcmGrView___ = MeinDynamicMplCanvas(self.UcmGrView_, width=5,
                                                 height=4, dpi=100)
        UcmGrView__.addWidget(self.UcmGrView___)

        
        self.show()
        
        #self.file_to_write=datetime.today().strftime("%Y-%m-%d_%H-%M-%S")+'.csv'
        self.file_to_write=datetime.today().strftime("%-d_%-m_%Y")+'.csv'
        if not os.path.exists(self.file_to_write):
            shutil.copy2(r'test_data0.csv', self.file_to_write)
        with open(self.file_to_write, "a", newline='') as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow("")
        with open("log_"+self.file_to_write, "a", newline='') as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow([datetime.today().strftime("%H-%M-%S")]+["Программа запущена"])

        
        if autostart:
            if self.connect_button():
                self.processEvents()
                self.read_cyclic_start()
            
        else:
            self.labelCyclicRead.setVisible(0)
            self.labelConnect.setVisible(0)
            self.disconnectButton.setEnabled(0)
            self.readButton.setEnabled(0)
            self.readCyclicButtonStop.setEnabled(0)
            self.processEvents()
            self.readCyclicButtonStart.setEnabled(0)

    def TuneCoeffPoints(self):
        try:
            self.coeffpoints[0] = self.dSBTunningiam.value()
            self.coeffpoints[1] = self.dSBTunningibm.value()
            self.coeffpoints[2] = self.dSBTunningicm.value()
            self.coeffpoints[3] = self.dSBTunninginm.value()
            self.coeffpoints[4] = self.dSBTunninguam.value()
            self.coeffpoints[5] = self.dSBTunningubm.value()
            self.coeffpoints[6] = self.dSBTunningucm.value()
        
            self.coeffpoints[7] = self.spinBoxTunningua.value()
            self.coeffpoints[8] = self.spinBoxTunningub.value()
            self.coeffpoints[9] = self.spinBoxTunninguc.value()

            self.coeffpoints[10] = self.dSBTunningcosa4.value()
            self.coeffpoints[11] = self.dSBTunningcosa3.value()
            self.coeffpoints[12] = self.dSBTunningcosa2.value()
            self.coeffpoints[13] = self.dSBTunningcosa1.value()
            self.coeffpoints[14] = self.dSBTunningcosa0.value()
            self.coeffpoints[15] = self.dSBTunningcosb4.value()
            self.coeffpoints[16] = self.dSBTunningcosb3.value()
            self.coeffpoints[17] = self.dSBTunningcosb2.value()
            self.coeffpoints[18] = self.dSBTunningcosb1.value()
            self.coeffpoints[19] = self.dSBTunningcosb0.value()
            self.coeffpoints[20] = self.dSBTunningcosc4.value()
            self.coeffpoints[21] = self.dSBTunningcosc3.value()
            self.coeffpoints[22] = self.dSBTunningcosc2.value()
            self.coeffpoints[23] = self.dSBTunningcosc1.value()
            self.coeffpoints[24] = self.dSBTunningcosc0.value()
        except Exception as e:
            print(e)
        pass
    
    def writeTunning(self):
        # Запись в файл
        # self.TunningVisible(0)
        # self.TunningCheckBox.setChecked(0)
        self.tunning_f = 'Tunning_coeff.csv'
        self.coeffpoints[0] = self.dSBTunningiam.value()
        self.coeffpoints[1] = self.dSBTunningibm.value()
        self.coeffpoints[2] = self.dSBTunningicm.value()
        self.coeffpoints[3] = self.dSBTunninginm.value()
        self.coeffpoints[4] = self.dSBTunninguam.value()
        self.coeffpoints[5] = self.dSBTunningubm.value()
        self.coeffpoints[6] = self.dSBTunningucm.value()
        
        self.coeffpoints[7] = self.spinBoxTunningua.value()
        self.coeffpoints[8] = self.spinBoxTunningub.value()
        self.coeffpoints[9] = self.spinBoxTunninguc.value()

        self.coeffpoints[10] = self.dSBTunningcosa4.value()
        self.coeffpoints[11] = self.dSBTunningcosa3.value()
        self.coeffpoints[12] = self.dSBTunningcosa2.value()
        self.coeffpoints[13] = self.dSBTunningcosa1.value()
        self.coeffpoints[14] = self.dSBTunningcosa0.value()
        self.coeffpoints[15] = self.dSBTunningcosb4.value()
        self.coeffpoints[16] = self.dSBTunningcosb3.value()
        self.coeffpoints[17] = self.dSBTunningcosb2.value()
        self.coeffpoints[18] = self.dSBTunningcosb1.value()
        self.coeffpoints[19] = self.dSBTunningcosb0.value()
        self.coeffpoints[20] = self.dSBTunningcosc4.value()
        self.coeffpoints[21] = self.dSBTunningcosc3.value()
        self.coeffpoints[22] = self.dSBTunningcosc2.value()
        self.coeffpoints[23] = self.dSBTunningcosc1.value()
        self.coeffpoints[24] = self.dSBTunningcosc0.value()
            
        with open(self.tunning_f, "w", newline = '') as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(self.coeffpoints)
        pass

    def TunningShow(self):
        # Чтение из файла в переменные
        self.tunning_f = 'Tunning_coeff.csv'
        try:
            if os.path.exists(self.tunning_f):
                with open(self.tunning_f, "r", newline = '') as f:
                    reader = csv.reader(f, delimiter=";")
                    self.coeffpoints1 = [cp for cp in reader]
                    self.coeffpoints1 = [float(cp) for cp in self.coeffpoints1[0]]
            if ((len(self.coeffpoints1)) == 25):
                self.coeffpoints = self.coeffpoints1
            self.TunningVisible(self.TunningCheckBox.isChecked())
        except Exception as e:
            print(e, len(self.coeffpoints))
        
        pass

    def TunningVisible(self, TF=0):
        self.label_22.setVisible(TF)
        self.label_23.setVisible(TF)
        self.label_24.setVisible(TF)
        self.label_25.setVisible(TF)
        self.label_26.setVisible(TF)
        self.label_27.setVisible(TF)
        self.label_28.setVisible(TF)
        self.label_29.setVisible(TF)
        self.label_30.setVisible(TF)
        self.label_31.setVisible(TF)
        self.label_32.setVisible(TF)
        self.label_33.setVisible(TF)
        self.label_34.setVisible(TF)
        self.label_35.setVisible(TF)
        self.label_36.setVisible(TF)
        self.label_37.setVisible(TF)
        self.label_38.setVisible(TF)
        self.label_39.setVisible(TF)
        self.label_40.setVisible(TF)
        self.label_41.setVisible(TF)
        self.label_42.setVisible(TF)
        self.label_43.setVisible(TF)
        self.label_44.setVisible(TF)
        self.label_45.setVisible(TF)
        self.label_46.setVisible(TF)
        
        self.dSBTunningiam.setVisible(TF)
        self.dSBTunningiam.setValue(self.coeffpoints[0])
        self.dSBTunningibm.setVisible(TF)
        self.dSBTunningibm.setValue(self.coeffpoints[1])
        self.dSBTunningicm.setVisible(TF)
        self.dSBTunningicm.setValue(self.coeffpoints[2])
        self.dSBTunninginm.setVisible(TF)
        self.dSBTunninginm.setValue(self.coeffpoints[3])
        self.dSBTunninguam.setVisible(TF)
        self.dSBTunninguam.setValue(self.coeffpoints[4])
        self.dSBTunningubm.setVisible(TF)
        self.dSBTunningubm.setValue(self.coeffpoints[5])
        self.dSBTunningucm.setVisible(TF)
        self.dSBTunningucm.setValue(self.coeffpoints[6])
        
        self.spinBoxTunningua.setVisible(TF)
        self.spinBoxTunningua.setValue(round(self.coeffpoints[7],0))
        self.spinBoxTunningub.setVisible(TF)
        self.spinBoxTunningub.setValue(round(self.coeffpoints[8],0))
        self.spinBoxTunninguc.setVisible(TF)
        self.spinBoxTunninguc.setValue(round(self.coeffpoints[9],0))

        self.dSBTunningcosa4.setVisible(TF)
        self.dSBTunningcosa4.setValue(self.coeffpoints[10])
        self.dSBTunningcosa3.setVisible(TF)
        self.dSBTunningcosa3.setValue(self.coeffpoints[11])
        self.dSBTunningcosa2.setVisible(TF)
        self.dSBTunningcosa2.setValue(self.coeffpoints[12])
        self.dSBTunningcosa1.setVisible(TF)
        self.dSBTunningcosa1.setValue(self.coeffpoints[13])
        self.dSBTunningcosa0.setVisible(TF)
        self.dSBTunningcosa0.setValue(self.coeffpoints[14])
        self.dSBTunningcosb4.setVisible(TF)
        self.dSBTunningcosb4.setValue(self.coeffpoints[15])
        self.dSBTunningcosb3.setVisible(TF)
        self.dSBTunningcosb3.setValue(self.coeffpoints[16])
        self.dSBTunningcosb2.setVisible(TF)
        self.dSBTunningcosb2.setValue(self.coeffpoints[17])
        self.dSBTunningcosb1.setVisible(TF)
        self.dSBTunningcosb1.setValue(self.coeffpoints[18])
        self.dSBTunningcosb0.setVisible(TF)
        self.dSBTunningcosb0.setValue(self.coeffpoints[19])
        self.dSBTunningcosc4.setVisible(TF)
        self.dSBTunningcosc4.setValue(self.coeffpoints[20])
        self.dSBTunningcosc3.setVisible(TF)
        self.dSBTunningcosc3.setValue(self.coeffpoints[21])
        self.dSBTunningcosc2.setVisible(TF)
        self.dSBTunningcosc2.setValue(self.coeffpoints[22])
        self.dSBTunningcosc1.setVisible(TF)
        self.dSBTunningcosc1.setValue(self.coeffpoints[23])
        self.dSBTunningcosc0.setVisible(TF)
        self.dSBTunningcosc0.setValue(self.coeffpoints[24])

        self.pushButtonWriteTunning.setVisible(TF)
        self.pushButtonTune.setVisible(TF)

    def about(self):
        QtWidgets.QMessageBox.about(self, "About",
                                    """Copyright 2019 Danil Shaykhutdinov, Sergey Kostinskiy, Nuri Narakidze

Данная программа обеспечивает съем данных с serial-порта, обработку и передачу на следующий уровень."""
                                )

    def read_cyclic_start(self):
        self.readyToCyclicRead = True
        self.labelCyclicRead.setVisible(1)
        self.readCyclicButtonStart.setEnabled(0)
        self.readCyclicButtonStop.setEnabled(1)
        self.readButton.setEnabled(0)
        self.disconnectButton.setEnabled(0)
        self.processEvents()
        self.spinBoxRate.setEnabled(0)

        if (self.Protocol.currentIndex()==0):
            self.read_cyclic_start_v1()
        elif (self.Protocol.currentIndex()==1):
            self.read_cyclic_start_v2()
        elif (self.Protocol.currentIndex()==2):
            self.read_cyclic_start_v3()
        elif (self.Protocol.currentIndex()==3):
            self.read_cyclic_start_v4()
        

    def read_serial(self):
        msg_str_= "_"
        msg_str = " "
        while ((not ((len(msg_str_)==0) & (msg_str[len(msg_str)-1] == '%'))) & self.readyToCyclicRead):
            try:
                msg_bin = self.ard.read(self.ard.inWaiting())
                msg_bin += self.ard.read(self.ard.inWaiting())
                msg_bin += self.ard.read(self.ard.inWaiting())
                msg_bin += self.ard.read(self.ard.inWaiting())
                msg_str_ = msg_bin.decode()
            except Exception as e:
                self.readyToCyclicRead = False
                self.disconnect_button()
                with open("log_"+self.file_to_write, "a", newline='') as f:
                    writer = csv.writer(f, delimiter=";")
                    writer.writerow([datetime.today().strftime("%H-%M-%S")]+["Need to Change Port & Reboot"])
                #Reboot for Orange PI#################################
                #subprocess.check_call('reboot')

                self.tabWidget.setCurrentIndex(0)
            msg_str += msg_str_
            self.processEvents()
            time.sleep(0.2)

        self.lists_clear()
        self.tables_clear()
        msg_last = msg_str.split('%')
        msg_last = msg_last[len(msg_last)-2]
        return msg_last

    def fft_fft1000(self, osc = [], Gain = 1000):
        magnitude__ = np.fft.fft(osc)/1000/np.sqrt(2)/Gain
        #print(magnitude__[480:520])
        magnitude_ = 2*np.abs(magnitude__)
        #print(np.fft.ifft(magnitude__))
        phase_ = np.angle(magnitude__, deg = True)
        magnitude = [[magnitude_[i], phase_[i], magnitude__[i]] for i in range(10,500,10)]
        return magnitude

    def ifft_fft1000(self, magnitude = [], Gain = 1000):
        magnitude__ = [0 for i in range(501)]
        for i in range(10,491,10):
            magnitude__[i] = magnitude[(i-10)//10]
        '''for i in range(510,991,10):
            magnitude__[i] = magnitude[-((i-500)//10)]'''    
        #print(magnitude__)
        osc = np.fft.irfft(magnitude__)*1000*np.sqrt(2)*Gain
        return osc

    def sqrsumm (self, osc_0 = [], osc_1 = []):
        summ = 0
        if len(osc_0) == len(osc_1):
            for i in range(len(osc_0)):
                summ = summ + osc_0[i]*osc_1[i]*0.0002
        return summ

    def read_cyclic_start_v4(self):
        self.indexRate = 1
        while self.readyToCyclicRead:
            time.sleep(0.5)
            msg2=[]
            msg3=['' for i in range(369)]
            i_a = [0 for i in range(1000)]
            i_b = i_a
            i_c = i_a
            i_n = i_a
            u_a = i_a
            u_b = i_a
            u_c = i_a
            if (self.spinBoxRate.value() <= (self.indexRate//2)) & self.InternetCheckBox.isChecked():
                self.indexRate = 1
                self.lists_clear()
                self.tables_clear()
                session = boto3.session.Session()
                s3 = session.client(service_name='s3', endpoint_url='https://storage.yandexcloud.net',
                                    region_name=region_name_,
                                    aws_access_key_id=aws_access_key_id_,
                                    aws_secret_access_key=aws_secret_access_key_)
                get_object_response = s3.get_object(Bucket=bucket_,Key='data/actual_data.csv')
                msg3 = get_object_response['Body'].read().decode().split(';')
                with open('actual_data.csv', "w", newline='') as f:
                    writer = csv.writer(f, delimiter=";")
                    writer.writerow(msg3)
                self.processEvents()
                mag_ = [complex(msg3[i]) for i in range(19,68)]
                i_a = self.ifft_fft1000(mag_, Gain=1)
                mag_ = [complex(msg3[i]) for i in range(69,118)]
                i_b = self.ifft_fft1000(mag_, Gain=1)
                mag_ = [complex(msg3[i]) for i in range(119,168)]
                i_c = self.ifft_fft1000(mag_, Gain=1)
                mag_ = [complex(msg3[i]) for i in range(169,218)]
                i_n = self.ifft_fft1000(mag_, Gain=1)
                mag_ = [complex(msg3[i]) for i in range(219,268)]
                u_a = self.ifft_fft1000(mag_, Gain=1)
                mag_ = [complex(msg3[i]) for i in range(269,318)]
                u_b = self.ifft_fft1000(mag_, Gain=1)
                mag_ = [complex(msg3[i]) for i in range(319,368)]
                u_c = self.ifft_fft1000(mag_, Gain=1)
                try:
                    mag_i_a = self.fft_fft1000(i_a, Gain=1)
        
                    mag_i_b = self.fft_fft1000(i_b, Gain=1)
                    
                    mag_i_c = self.fft_fft1000(i_c, Gain=1)
                    
                    mag_i_n = self.fft_fft1000(i_n, Gain=1)
                    
                    mag_u_a = self.fft_fft1000(u_a, Gain=1)
                   
                    mag_u_b = self.fft_fft1000(u_b, Gain=1)
                    
                    mag_u_c = self.fft_fft1000(u_c, Gain=1)
                    
                except Exception as e:
                    with open("log_"+self.file_to_write, "a", newline='') as f:
                        writer = csv.writer(f, delimiter=";")
                        writer.writerow([datetime.today().strftime("%H-%M-%S")]+[str(e)])
                self.processEvents()
                try:   
                    msg2[:3] = msg3[:3]
                    msg2.append(str(round(np.sqrt(self.sqrsumm(u_a, u_a)/0.2),2)))
                    msg2.append(str(round(np.sqrt(self.sqrsumm(u_b, u_b)/0.2),2)))
                    msg2.append(str(round(np.sqrt(self.sqrsumm(u_c, u_c)/0.2),2)))
                    msg2.append(str(round(np.sqrt(self.sqrsumm(i_a, i_a)/0.2),2)))
                    msg2.append(str(round(np.sqrt(self.sqrsumm(i_b, i_b)/0.2),2)))
                    msg2.append(str(round(np.sqrt(self.sqrsumm(i_c, i_c)/0.2),2)))
                    msg2.append(str(round(np.sqrt(self.sqrsumm(i_n, i_n)/0.2),2)))

                    self.p_a = self.sqrsumm(i_a, u_a)/0.2 /Gain
                    self.p_b = self.sqrsumm(i_b, u_b)/0.2 /Gain
                    self.p_c = self.sqrsumm(i_c, u_c)/0.2 /Gain

                    self.s_a = np.sqrt(self.sqrsumm(i_a, i_a)/0.2) * np.sqrt(self.sqrsumm(u_a, u_a)/0.2) /Gain
                    self.s_b = np.sqrt(self.sqrsumm(i_b, i_b)/0.2) * np.sqrt(self.sqrsumm(u_b, u_b)/0.2) /Gain
                    self.s_c = np.sqrt(self.sqrsumm(i_c, i_c)/0.2) * np.sqrt(self.sqrsumm(u_c, u_c)/0.2) /Gain

                    self.cos_a = self.p_a / self.s_a
                    self.cos_b = self.p_b / self.s_b
                    self.cos_c = self.p_c / self.s_c

                    self.cos_a = self.coeffpoints[10]*(self.cos_a**4)+self.coeffpoints[11]*(self.cos_a**3)+self.coeffpoints[12]*(self.cos_a**2)+self.coeffpoints[13]*self.cos_a+self.coeffpoints[14]
                    self.cos_b = self.coeffpoints[15]*(self.cos_b**4)+self.coeffpoints[16]*(self.cos_b**3)+self.coeffpoints[17]*(self.cos_b**2)+self.coeffpoints[18]*self.cos_b+self.coeffpoints[19]
                    self.cos_c = self.coeffpoints[20]*(self.cos_c**4)+self.coeffpoints[21]*(self.cos_c**3)+self.coeffpoints[22]*(self.cos_c**2)+self.coeffpoints[23]*self.cos_c+self.coeffpoints[24]

                    self.p_a = self.s_a*self.cos_a
                    self.p_b = self.s_b*self.cos_b
                    self.p_c = self.s_c*self.cos_c
                   

                    msg2.append(str(round(self.p_a,2)))
                    msg2.append(str(round(self.p_b,2)))
                    msg2.append(str(round(self.p_c,2)))

                    msg2.append(str(round(self.s_a,2)))
                    msg2.append(str(round(self.s_b,2)))
                    msg2.append(str(round(self.s_c,2)))

                    msg2.append(str(round(self.cos_a,3)))
                    msg2.append(str(round(self.cos_b,3)))
                    msg2.append(str(round(self.cos_c,3)))

                #msg2[10:19] = ['-' for i in range(9)]
                    if self.PhaseCheckBox.isChecked():
                        msg2[19:68] = [str(round(mag_i_a[i][0],2))+'/'+str(round(mag_i_a[i][1],3)) for i in range(49)]
                        msg2.append('-')
                        msg2[69:118] = [str(round(mag_i_b[i][0],2))+'/'+str(round(mag_i_b[i][1],3)) for i in range(49)]
                        msg2.append('-')
                        msg2[119:168] = [str(round(mag_i_c[i][0],2))+'/'+str(round(mag_i_c[i][1],3)) for i in range(49)]
                        msg2.append('-')
                        msg2[169:218] = [str(round(mag_i_n[i][0],2))+'/'+str(round(mag_i_n[i][1],3)) for i in range(49)]
                        msg2.append('-')
                        msg2[219:268] = [str(round(mag_u_a[i][0],2))+'/'+str(round(mag_u_a[i][1],3)) for i in range(49)]
                        msg2.append('-')
                        msg2[269:318] = [str(round(mag_u_b[i][0],2))+'/'+str(round(mag_u_b[i][1],3)) for i in range(49)]
                        msg2.append('-')
                        msg2[319:368] = [str(round(mag_u_c[i][0],2))+'/'+str(round(mag_u_c[0][1],3)) for i in range(49)]
                        msg2.append('-')
                    else:
                        msg2[19:68] = [str(round(mag_i_a[i][0],2)) for i in range(49)]
                        msg2.append('-')
                        msg2[69:118] = [str(round(mag_i_b[i][0],2)) for i in range(49)]
                        msg2.append('-')
                        msg2[119:168] = [str(round(mag_i_c[i][0],2)) for i in range(49)]
                        msg2.append('-')
                        msg2[169:218] = [str(round(mag_i_n[i][0],2)) for i in range(49)]
                        msg2.append('-')
                        msg2[219:268] = [str(round(mag_u_a[i][0],2)) for i in range(49)]
                        msg2.append('-')
                        msg2[269:318] = [str(round(mag_u_b[i][0],2)) for i in range(49)]
                        msg2.append('-')
                        msg2[319:368] = [str(round(mag_u_c[i][0],2)) for i in range(49)]
                        msg2.append('-')
                    if (self.spinBoxRate.value() <= (self.indexRate//2)):
                        with open(self.file_to_write, "a", newline='') as f:
                            writer = csv.writer(f, delimiter=";")
                            writer.writerow(msg2)
                    
                except Exception as e:
                    with open("log_"+self.file_to_write, "a", newline='') as f:
                        writer = csv.writer(f, delimiter=";")
                        writer.writerow([datetime.today().strftime("%H-%M-%S")]+[str(e)])

                try: # Разделение данных на 8 групп
                    self.msg_tabData = msg2[:19]
                    self.msg_tableIag = msg2[19:69]
                    self.msg_tableIbg = msg2[69:119]
                    self.msg_tableIcg = msg2[119:169]
                    self.msg_tableIng = msg2[169:219]
                    self.msg_tableUag = msg2[219:269]
                    self.msg_tableUbg = msg2[269:319]
                    self.msg_tableUcg = msg2[319:]
                except Exception as e:
                    with open("log_"+self.file_to_write, "a", newline='') as f:
                        writer = csv.writer(f, delimiter=";")
                        writer.writerow([datetime.today().strftime("%H-%M-%S")]+[str(e)])
                try:
                    self.write_tabData()
                    if self.GraphicsCheckBox.isChecked():
                        self.write_tableGarm()
                        mag_proc = [mag_i_a[i][0]/mag_i_a[0][0]*100 for i in range(len(mag_i_a))]
                        self.IagGrView___.update_figure_g(mag_proc)
                        self.IamGrView___.update_figure(data=i_a, title=" I_a (мА) ")
                        mag_proc = [mag_i_b[i][0]/mag_i_b[0][0]*100 for i in range(len(mag_i_b))]
                        self.IbgGrView___.update_figure_g(mag_proc)
                        self.IbmGrView___.update_figure(data=i_b, title=" I_b (мА) ")
                        mag_proc = [mag_i_c[i][0]/mag_i_c[0][0]*100 for i in range(len(mag_i_c))]
                        self.IcgGrView___.update_figure_g(mag_proc)
                        self.IcmGrView___.update_figure(data=i_c, title=" I_c (мА) ")
                        mag_proc = [mag_i_n[i][0]/mag_i_n[0][0]*100 for i in range(len(mag_i_n))]
                        self.IngGrView___.update_figure_g(mag_proc)
                        self.InmGrView___.update_figure(data=i_n, title=" I_n (мА) ")
                        mag_proc = [mag_u_a[i][0]/mag_u_a[0][0]*100 for i in range(len(mag_u_a))]
                        self.UagGrView___.update_figure_g(mag_proc)
                        self.UamGrView___.update_figure(data=u_a, title=" U_a (В) ")
                        mag_proc = [mag_u_b[i][0]/mag_u_b[0][0]*100 for i in range(len(mag_u_b))]
                        self.UbgGrView___.update_figure_g(mag_proc)
                        self.UbmGrView___.update_figure(data=u_b, title=" U_b (В) ")
                        mag_proc = [mag_u_c[i][0]/mag_u_c[0][0]*100 for i in range(len(mag_u_c))]
                        self.UcgGrView___.update_figure_g(mag_proc)
                        self.UcmGrView___.update_figure(data=u_c, title=" U_c (В) ")
                except Exception as e:
                    with open("log_"+self.file_to_write, "a", newline='') as f:
                        writer = csv.writer(f, delimiter=";")
                        writer.writerow([datetime.today().strftime("%H-%M-%S")]+[str(e)])
            elif self.InternetCheckBox.isChecked():
                self.indexRate += 1
                self.processEvents()
            elif not self.InternetCheckBox.isChecked():
                reply = QtWidgets.QMessageBox.question(self, 'Message',
                                               "Без интернета данный протокол не работает.\n",
                                               QtWidgets.QMessageBox.Yes,
                                               QtWidgets.QMessageBox.Yes)
                self.readyToCyclicRead = False
                self.read_cyclic_stop()
                
        pass

    def read_cyclic_start_v2(self):
        self.indexRate = 1
        while self.readyToCyclicRead:
            msg2=[]
            msg3=[]
            msg_last = self.read_serial()
            len_data = False
            try:
                c = msg_last.split('|')
                c = c[:len(c)-1]
                
                c = [d.split(';') for d in c]
                gpt_date_time_text = c[0][:len(c[0])-1]
                i_a_text = c[1][:len(c[1])-1]
                i_a = [float(d)*self.coeffpoints[0] for d in i_a_text]
                ind_iu = range(len(i_a))
                i_a = [i_a[d-int(self.coeffpoints[7])] for d in ind_iu]
                i_b_text = c[2][:len(c[2])-1]
                i_b = [float(d)*self.coeffpoints[1] for d in i_b_text]
                i_b = [i_b[d-int(self.coeffpoints[8])] for d in ind_iu]
                i_c_text = c[3][:len(c[3])-1]
                i_c = [float(d)*self.coeffpoints[2] for d in i_c_text]
                i_c = [i_c[d-int(self.coeffpoints[9])] for d in ind_iu]
                i_n_text = c[4][:len(c[4])-1]
                i_n = [float(d)*self.coeffpoints[3] for d in i_n_text]
                i_n = [i_n[d] for d in ind_iu]
                u_a_text = c[5][:len(c[5])-1]
                u_a = [float(d)*self.coeffpoints[4] for d in u_a_text]
                u_a = [u_a[d] for d in ind_iu]
                u_b_text = c[6][:len(c[6])-1]
                u_b = [float(d)*self.coeffpoints[5] for d in u_b_text]
                u_b = [u_b[d] for d in ind_iu]
                u_c_text = c[7][:len(c[7])-1]
                u_c = [float(d)*self.coeffpoints[6] for d in u_c_text]
                u_c = [u_c[d] for d in ind_iu]
                len_data = True

            except Exception as e:
                len_data = False
                with open("log_"+self.file_to_write, "a", newline='') as f:
                    writer = csv.writer(f, delimiter=";")
                    writer.writerow([datetime.today().strftime("%H-%M-%S")]+[str(e)])
                pass

            self.processEvents()
            if len_data:
                try:
                    mag_i_a = self.fft_fft1000(i_a, Gain=1)
                    
                    mag_i_b = self.fft_fft1000(i_b, Gain=1)
                    
                    mag_i_c = self.fft_fft1000(i_c, Gain=1)
                    
                    mag_i_n = self.fft_fft1000(i_n, Gain=1)
                    
                    mag_u_a = self.fft_fft1000(u_a, Gain=1)
                   
                    mag_u_b = self.fft_fft1000(u_b, Gain=1)
                    
                    mag_u_c = self.fft_fft1000(u_c, Gain=1)

                    
                    
                except Exception as e:
                    with open("log_"+self.file_to_write, "a", newline='') as f:
                        writer = csv.writer(f, delimiter=";")
                        writer.writerow([datetime.today().strftime("%H-%M-%S")]+[str(e)])
                self.processEvents()
                try:   
                    msg2[:3] = [gpt_date_time_text[i] for i in range(3)]
                    msg3[:3] = [gpt_date_time_text[i] for i in range(3)]
                    msg2.append(str(round(np.sqrt(self.sqrsumm(u_a, u_a)/0.2),2)))
                    msg3.append(str(round(np.sqrt(self.sqrsumm(u_a, u_a)/0.2),2)))
                    msg2.append(str(round(np.sqrt(self.sqrsumm(u_b, u_b)/0.2),2)))
                    msg3.append(str(round(np.sqrt(self.sqrsumm(u_b, u_b)/0.2),2)))
                    msg2.append(str(round(np.sqrt(self.sqrsumm(u_c, u_c)/0.2),2)))
                    msg3.append(str(round(np.sqrt(self.sqrsumm(u_c, u_c)/0.2),2)))
                    msg2.append(str(round(np.sqrt(self.sqrsumm(i_a, i_a)/0.2),2)))
                    msg3.append(str(round(np.sqrt(self.sqrsumm(i_a, i_a)/0.2),2)))
                    msg2.append(str(round(np.sqrt(self.sqrsumm(i_b, i_b)/0.2),2)))
                    msg3.append(str(round(np.sqrt(self.sqrsumm(i_b, i_b)/0.2),2)))
                    msg2.append(str(round(np.sqrt(self.sqrsumm(i_c, i_c)/0.2),2)))
                    msg3.append(str(round(np.sqrt(self.sqrsumm(i_c, i_c)/0.2),2)))
                    msg2.append(str(round(np.sqrt(self.sqrsumm(i_n, i_n)/0.2),2)))
                    msg3.append(str(round(np.sqrt(self.sqrsumm(i_n, i_n)/0.2),2)))

                    self.p_a = self.sqrsumm(i_a, u_a)/0.2 /Gain
                    self.p_b = self.sqrsumm(i_b, u_b)/0.2 /Gain
                    self.p_c = self.sqrsumm(i_c, u_c)/0.2 /Gain

                    self.s_a = np.sqrt(self.sqrsumm(i_a, i_a)/0.2) * np.sqrt(self.sqrsumm(u_a, u_a)/0.2) /Gain
                    self.s_b = np.sqrt(self.sqrsumm(i_b, i_b)/0.2) * np.sqrt(self.sqrsumm(u_b, u_b)/0.2) /Gain
                    self.s_c = np.sqrt(self.sqrsumm(i_c, i_c)/0.2) * np.sqrt(self.sqrsumm(u_c, u_c)/0.2) /Gain

                    self.cos_a = self.p_a / self.s_a
                    self.cos_b = self.p_b / self.s_b
                    self.cos_c = self.p_c / self.s_c

                    self.cos_a = self.coeffpoints[10]*(self.cos_a**4)+self.coeffpoints[11]*(self.cos_a**3)+self.coeffpoints[12]*(self.cos_a**2)+self.coeffpoints[13]*self.cos_a+self.coeffpoints[14]
                    self.cos_b = self.coeffpoints[15]*(self.cos_b**4)+self.coeffpoints[16]*(self.cos_b**3)+self.coeffpoints[17]*(self.cos_b**2)+self.coeffpoints[18]*self.cos_b+self.coeffpoints[19]
                    self.cos_c = self.coeffpoints[20]*(self.cos_c**4)+self.coeffpoints[21]*(self.cos_c**3)+self.coeffpoints[22]*(self.cos_c**2)+self.coeffpoints[23]*self.cos_c+self.coeffpoints[24]

                    self.p_a = self.s_a*self.cos_a
                    self.p_b = self.s_b*self.cos_b
                    self.p_c = self.s_c*self.cos_c
                   

                    msg2.append(str(round(self.p_a,2)))
                    msg3.append(str(round(self.p_a,2)))
                    msg2.append(str(round(self.p_b,2)))
                    msg3.append(str(round(self.p_b,2)))
                    msg2.append(str(round(self.p_c,2)))
                    msg3.append(str(round(self.p_c,2)))

                    msg2.append(str(round(self.s_a,2)))
                    msg3.append(str(round(self.s_a,2)))
                    msg2.append(str(round(self.s_b,2)))
                    msg3.append(str(round(self.s_b,2)))
                    msg2.append(str(round(self.s_c,2)))
                    msg3.append(str(round(self.s_c,2)))

                    msg2.append(str(round(self.cos_a,3)))
                    msg3.append(str(round(self.cos_a,3)))
                    msg2.append(str(round(self.cos_b,3)))
                    msg3.append(str(round(self.cos_b,3)))
                    msg2.append(str(round(self.cos_c,3)))
                    msg3.append(str(round(self.cos_c,3)))

                    #IA######################################################################
                    msg2.append(str(round(mag_i_a[0][0],2))) #19,1
                    if mag_i_a[1][0] <= 3900: #20,2
                        msg2.append(str(round(np.maximum(0.9675*mag_i_a[1][0] + 11.898, 0),2)))
                    else:
                        msg2.append(str(round(np.maximum(1.0826*mag_i_a[1][0] - 402.5, np.random.random()),2)))
                    if mag_i_a[2][0] <= 1000: #21,3
                        msg2.append(str(round(np.maximum(0.9758*mag_i_a[2][0]-8.3622, np.random.random()),2)))
                    else:
                        msg2.append(str(round(np.maximum(0.976*mag_i_a[2][0]-17.841, np.random.random()),2)))
                    if mag_i_a[3][0] <= 2000: #22,4
                        msg2.append(str(round(np.maximum(0.9699*mag_i_a[3][0]+1.4302, 0),2)))
                    else:
                        msg2.append(str(round(np.maximum(9E-05*mag_i_a[3][0]**2+0.5079*mag_i_a[3][0]+583.07, 0),2)))
                    if mag_i_a[4][0] <= 2450: #23,5
                        msg2.append(str(round(np.maximum(0.9745*mag_i_a[4][0]+3.1688, 0),2)))
                    else:
                        msg2.append(str(round(np.maximum(6E-05*mag_i_a[4][0]**2+0.7503*mag_i_a[4][0]+183.54, 0),2)))
                    if mag_i_a[5][0] <= 2750: #24,6
                        msg2.append(str(round(np.maximum(0.9801*mag_i_a[5][0] + 0.4198, 0),2)))
                    else:
                        msg2.append(str(round(np.maximum(4E-05*mag_i_a[5][0]**2+0.8308*mag_i_a[5][0]+97.32, 0),2)))
                    if mag_i_a[6][0] <= 2400: #25,7
                        msg2.append(str(round(np.maximum(0.9955*mag_i_a[6][0]+0.8009, 0),2)))
                    else:
                        msg2.append(str(round(np.maximum(9E-05*mag_i_a[6][0]**2+0.5443*mag_i_a[6][0]+571.75, 0),2)))
                    if mag_i_a[7][0] <= 2600: #26,8
                        msg2.append(str(round(np.maximum(0.9961*mag_i_a[7][0]+0.3284, 0),2)))
                    else:
                        msg2.append(str(round(np.maximum(1E-04*mag_i_a[7][0]**2+0.4854*mag_i_a[7][0]+663.56, 0),2)))
                    if mag_i_a[8][0] <= 2700: #27,9
                        msg2.append(str(round(np.maximum(1.0057*mag_i_a[8][0]+0.6316, 0),2)))
                    else:
                        msg2.append(str(round(np.maximum(1.0715*mag_i_a[8][0]-167.65, np.random.random()),2)))
                    msg2.append(str(round(np.maximum(1.0215*mag_i_a[9][0]-4.2914, np.random.random()),2))) #28,10
                    msg2.append(str(round(np.maximum(1.0332*mag_i_a[10][0]-3.0744, np.random.random()),2))) #29,11
                    msg2.append(str(round(np.maximum(1.048*mag_i_a[11][0]-4.5148, np.random.random()),2))) #30,12
                    msg2.append(str(round(np.maximum(1.064*mag_i_a[12][0]-4.2321, np.random.random()),2))) #31,13
                    msg2.append(str(round(np.maximum(1.0811*mag_i_a[13][0]-3.8762, np.random.random()),2))) #32,14
                    msg2.append(str(round(np.maximum(1.101*mag_i_a[14][0]-4.5711, np.random.random()),2))) #33,15
                    msg2.append(str(round(np.maximum(1.1202*mag_i_a[15][0]-3.6401, np.random.random()),2))) #34,16
                    msg2.append(str(round(np.maximum(1.1438*mag_i_a[16][0]-4.4185, np.random.random()),2))) #35,17
                    msg2.append(str(round(np.maximum(1.1678*mag_i_a[17][0]-3.6506, np.random.random()),2))) #36,18
                    msg2.append(str(round(np.maximum(1.195*mag_i_a[18][0]-3.2788, np.random.random()),2))) #37,19
                    msg2.append(str(round(np.maximum(1.2257*mag_i_a[19][0]-4.004, np.random.random()),2))) #38,20
                    msg2.append(str(round(np.maximum(1.2524*mag_i_a[20][0]-0.4877, np.random.random()),2))) #39,21
                    msg2.append(str(round(np.maximum(1.2862*mag_i_a[21][0]+0.749, 0),2))) #40,22
                    msg2.append(str(round(np.maximum(1.326*mag_i_a[22][0]+0.1472, 0),2))) #41,23
                    msg2.append(str(round(np.maximum(1.366*mag_i_a[23][0]-0.0238, np.random.random()),2))) #42,24
                    msg2.append(str(round(np.maximum(1.4137*mag_i_a[24][0]-0.5992, np.random.random()),2))) #43,25
                    msg2.append(str(round(np.maximum(1.4619*mag_i_a[25][0]+0.086, 0),2))) #44,26
                    msg2.append(str(round(np.maximum(1.5158*mag_i_a[26][0]+0.0356, 0),2))) #45,27
                    msg2.append(str(round(np.maximum(1.5781*mag_i_a[27][0]-0.3575, np.random.random()),2))) #46,28
                    msg2.append(str(round(np.maximum(1.6419*mag_i_a[28][0]+0.0616, 0),2))) #47,29
                    msg2.append(str(round(np.maximum(1.7134*mag_i_a[29][0]+0.4808, 0),2))) #48,30
                    msg2.append(str(round(np.maximum(1.7956*mag_i_a[30][0]+0.0094, 0),2))) #49,31
                    msg2.append(str(round(np.maximum(1.8825*mag_i_a[31][0] + 0.321, 0),2))) #50,32
                    msg2.append(str(round(np.maximum(1.9826*mag_i_a[32][0] - 0.4332, np.random.random()),2))) #51,33
                    msg2.append(str(round(np.maximum(2.0934*mag_i_a[33][0] + 0.056, 0),2))) #52,34
                    msg2.append(str(round(np.maximum(2.2243*mag_i_a[34][0] + 0.0857, 0),2))) #53,35
                    msg2.append(str(round(np.maximum(2.3482*mag_i_a[35][0] + 0.4823, 0),2))) #54,36
                    msg2.append(str(round(np.maximum(2.5112*mag_i_a[36][0] - 0.8924, np.random.random()),2))) #55,37
                    msg2.append(str(round(np.maximum(2.6845*mag_i_a[37][0] + 0.7146, 0),2))) #56,38
                    msg2.append(str(round(np.maximum(2.8882*mag_i_a[38][0] - 0.0195, np.random.random()),2))) #57,39
                    msg2.append(str(round(np.maximum(3.1279*mag_i_a[39][0] + 0.4239, 0),2))) #58,40
                    msg2.append(str(round(np.maximum(3.4197*mag_i_a[40][0] + 1.0125, 0),2))) #59,41
                    msg2.append(str(round(np.maximum(3.7263*mag_i_a[41][0] + 2.2576, 0),2))) #60,42
                    msg2.append(str(round(np.maximum(4.1295*mag_i_a[42][0] - 0.0465, np.random.random()),2))) #61,43
                    msg2.append(str(round(np.maximum(4.615*mag_i_a[43][0] - 1.3082, np.random.random()),2))) #62,44
                    msg2.append(str(round(np.maximum(5.2592*mag_i_a[44][0] - 1.8408, np.random.random()),2))) #63,45
                    msg2.append(str(round(np.maximum(5.976*mag_i_a[45][0] - 0.3867, np.random.random()),2))) #64,46
                    msg2.append(str(round(np.maximum(6.8963*mag_i_a[46][0] + 4.3749, 0),2))) #65,47
                    msg2.append(str(round(np.maximum(8.3321*mag_i_a[47][0] - 4.9167, np.random.random()),2))) #66,48
                    msg2.append(str(round(np.maximum(10.056*mag_i_a[48][0] + 8.1225, 0),2))) #67,49
                    msg2.append('-') #68,50

                    #IB######################################################################
                    msg2.append(str(round(mag_i_b[0][0],2))) #69,1
                    if mag_i_b[1][0] <= 3900: #70,2
                        msg2.append(str(round(np.maximum(0.9783*mag_i_b[1][0] - 4.68, np.random.random()),2)))
                    else:
                        msg2.append(str(round(np.maximum(1.0914*mag_i_b[1][0] - 420.33, np.random.random()),2)))
                    if mag_i_b[2][0] <= 1000: #71,3
                        msg2.append(str(round(np.maximum(0.9657*mag_i_b[2][0]+0.2748, 0),2)))
                    else:
                        msg2.append(str(round(np.maximum(0.9691*mag_i_b[2][0]+8.0737, 0),2)))
                    if mag_i_b[3][0] <= 2000: #72,4
                        msg2.append(str(round(np.maximum(0.9736*mag_i_b[3][0]+2.1805, 0),2)))
                    else:
                        msg2.append(str(round(np.maximum(9E-05*mag_i_b[3][0]**2+0.5242*mag_i_b[3][0]+560.98, 0),2)))
                    if mag_i_b[4][0] <= 2450: #73,5
                        msg2.append(str(round(np.maximum(0.9787*mag_i_b[4][0]+2.7614, 0),2)))
                    else:
                        msg2.append(str(round(np.maximum(6E-05*mag_i_b[4][0]**2+0.756*mag_i_b[4][0]+180.49, 0),2)))
                    if mag_i_b[5][0] <= 2750: #74,6
                        msg2.append(str(round(np.maximum(0.9884*mag_i_b[5][0] - 0.0927, np.random.random()),2)))
                    else:
                        msg2.append(str(round(np.maximum(4E-05*mag_i_b[5][0]**2+0.859*mag_i_b[5][0]+58.375, 0),2)))
                    if mag_i_b[6][0] <= 2400: #75,7
                        msg2.append(str(round(np.maximum(1.0009*mag_i_b[6][0]-0.7693, np.random.random()),2)))
                    else:
                        msg2.append(str(round(np.maximum(8E-05*mag_i_b[6][0]**2+0.593*mag_i_b[6][0]+502.54, 0),2)))
                    if mag_i_b[7][0] <= 2600: #76,8
                        msg2.append(str(round(np.maximum(1.0006*mag_i_b[7][0]+0.0185, 0),2)))
                    else:
                        msg2.append(str(round(np.maximum(9E-05*mag_i_b[7][0]**2+0.5295*mag_i_b[7][0]+609.65, 0),2)))
                    if mag_i_b[8][0] <= 2700: #77,9
                        msg2.append(str(round(np.maximum(1.0143*mag_i_b[8][0]+0.9146, 0),2)))
                    else:
                        msg2.append(str(round(np.maximum(1.0756*mag_i_b[8][0]-153.01, np.random.random()),2)))
                    msg2.append(str(round(np.maximum(1.0253*mag_i_b[9][0]-3.3614, np.random.random()),2))) #78,10
                    msg2.append(str(round(np.maximum(1.038*mag_i_b[10][0]-3.3204, np.random.random()),2))) #79,11
                    msg2.append(str(round(np.maximum(1.0572*mag_i_b[11][0]-4.6505, np.random.random()),2))) #80,12
                    msg2.append(str(round(np.maximum(1.068*mag_i_b[12][0]-4.1126, np.random.random()),2))) #81,13
                    msg2.append(str(round(np.maximum(1.0854*mag_i_b[13][0]-3.7589, np.random.random()),2))) #82,14
                    msg2.append(str(round(np.maximum(1.1113*mag_i_b[14][0]-5.897, np.random.random()),2))) #83,15
                    msg2.append(str(round(np.maximum(1.1269*mag_i_b[15][0]-5.0999, np.random.random()),2))) #84,16
                    msg2.append(str(round(np.maximum(1.1497*mag_i_b[16][0]-4.9778, np.random.random()),2))) #85,17
                    msg2.append(str(round(np.maximum(1.1789*mag_i_b[17][0]-4.8426, np.random.random()),2))) #86,18
                    msg2.append(str(round(np.maximum(1.2019*mag_i_b[18][0]-5.5988, np.random.random()),2))) #87,19
                    msg2.append(str(round(np.maximum(1.2306*mag_i_b[19][0]-3.8238, np.random.random()),2))) #88,20
                    msg2.append(str(round(np.maximum(1.2646*mag_i_b[20][0]-0.5778, np.random.random()),2))) #89,21
                    msg2.append(str(round(np.maximum(1.2944*mag_i_b[21][0]-0.4408, np.random.random()),2))) #90,22
                    msg2.append(str(round(np.maximum(1.3333*mag_i_b[22][0]-0.5446, np.random.random()),2))) #91,23
                    msg2.append(str(round(np.maximum(1.379*mag_i_b[23][0]+0.0113, 0),2))) #92,24
                    msg2.append(str(round(np.maximum(1.4199*mag_i_b[24][0]-0.5906, np.random.random()),2))) #93,25
                    msg2.append(str(round(np.maximum(1.4702*mag_i_b[25][0]-0.2378, np.random.random()),2))) #94,26
                    msg2.append(str(round(np.maximum(1.5299*mag_i_b[26][0]+0.2498, 0),2))) #95,27
                    msg2.append(str(round(np.maximum(1.5823*mag_i_b[27][0]+0.9645, 0),2))) #96,28
                    msg2.append(str(round(np.maximum(1.6519*mag_i_b[28][0]+0.0969, 0),2))) #97,29
                    msg2.append(str(round(np.maximum(1.7302*mag_i_b[29][0]-0.2925, np.random.random()),2))) #98,30
                    msg2.append(str(round(np.maximum(1.8048*mag_i_b[30][0]-0.3866, np.random.random()),2))) #99,31
                    msg2.append(str(round(np.maximum(1.8921*mag_i_b[31][0] + 0.1066, 0),2))) #100,32
                    msg2.append(str(round(np.maximum(1.9976*mag_i_b[32][0] - 0.4147, np.random.random()),2))) #101,33
                    msg2.append(str(round(np.maximum(2.1039*mag_i_b[33][0] - 0.6783, np.random.random()),2))) #102,34
                    msg2.append(str(round(np.maximum(2.2067*mag_i_b[34][0] - 0.1675, np.random.random()),2))) #103,35
                    msg2.append(str(round(np.maximum(2.3713*mag_i_b[35][0] + 0.788, 0),2))) #104,36
                    msg2.append(str(round(np.maximum(2.5209*mag_i_b[36][0] + 0.0039, 0),2))) #105,37
                    msg2.append(str(round(np.maximum(2.7083*mag_i_b[37][0] - 1.73, np.random.random()),2))) #106,38
                    msg2.append(str(round(np.maximum(2.9057*mag_i_b[38][0] + 1.5964, 0),2))) #107,39
                    msg2.append(str(round(np.maximum(3.1564*mag_i_b[39][0] - 1.7874, np.random.random()),2))) #108,40
                    msg2.append(str(round(np.maximum(3.3917*mag_i_b[40][0] + 0.5713, 0),2))) #109,41
                    msg2.append(str(round(np.maximum(3.7705*mag_i_b[41][0] - 0.187, np.random.random()),2))) #110,42
                    msg2.append(str(round(np.maximum(4.1652*mag_i_b[42][0] - 0.9919, np.random.random()),2))) #111,43
                    msg2.append(str(round(np.maximum(4.6466*mag_i_b[43][0] + 0.1385, 0),2))) #112,44
                    msg2.append(str(round(np.maximum(5.2161*mag_i_b[44][0] - 2.3062, np.random.random()),2))) #113,45
                    msg2.append(str(round(np.maximum(5.8938*mag_i_b[45][0] + 6.5574, 0),2))) #114,46
                    msg2.append(str(round(np.maximum(6.9717*mag_i_b[46][0] - 0.2564, np.random.random()),2))) #115,47
                    msg2.append(str(round(np.maximum(8.3759*mag_i_b[47][0] - 2.9425, np.random.random()),2))) #116,48
                    msg2.append(str(round(np.maximum(10.471*mag_i_b[48][0] - 8.1662, np.random.random()),2))) #117,49
                    msg2.append('-') #118,50

                    #IC######################################################################
                    msg2.append(str(round(mag_i_c[0][0],2))) #119,1
                    if mag_i_c[1][0] <= 3900: #120,2
                        msg2.append(str(round(np.maximum(0.9769*mag_i_c[1][0] + 1.6441, 0),2)))
                    else:
                        msg2.append(str(round(np.maximum(1.1128*mag_i_c[1][0] - 500.86, np.random.random()),2)))
                    if mag_i_c[2][0] <= 1000: #121,3
                        msg2.append(str(round(np.maximum(0.992*mag_i_c[2][0]-8.8633, np.random.random()),2)))
                    else:
                        msg2.append(str(round(np.maximum(0.9731*mag_i_c[2][0]+6.2499, 0),2)))
                    if mag_i_c[3][0] <= 2000: #122,4
                        msg2.append(str(round(np.maximum(0.9774*mag_i_c[3][0]-0.6451, np.random.random()),2)))
                    else:
                        msg2.append(str(round(np.maximum(9E-05*mag_i_c[3][0]**2+0.528*mag_i_c[3][0]+555.51, 0),2)))
                    if mag_i_c[4][0] <= 2450: #123,5
                        msg2.append(str(round(np.maximum(0.9806*mag_i_c[4][0]+2.2102, 0),2)))
                    else:
                        msg2.append(str(round(np.maximum(6E-05*mag_i_c[4][0]**2+0.7402*mag_i_c[4][0]+212.47, 0),2)))
                    if mag_i_c[5][0] <= 2750: #124,6
                        msg2.append(str(round(np.maximum(0.9921*mag_i_c[5][0] - 0.512, np.random.random()),2)))
                    else:
                        msg2.append(str(round(np.maximum(5E-05*mag_i_c[5][0]**2+0.7826*mag_i_c[5][0]+199.39, 0),2)))
                    if mag_i_c[6][0] <= 2400: #125,7
                        msg2.append(str(round(np.maximum(1.0029*mag_i_c[6][0]-0.323, np.random.random()),2)))
                    else:
                        msg2.append(str(round(np.maximum(9E-05*mag_i_c[6][0]**2+0.5401*mag_i_c[6][0]+585.58, 0),2)))
                    if mag_i_c[7][0] <= 2600: #126,8
                        msg2.append(str(round(np.maximum(1.0035*mag_i_c[7][0]-1.1118, np.random.random()),2)))
                    else:
                        msg2.append(str(round(np.maximum(1E-04*mag_i_c[7][0]**2+0.497*mag_i_c[7][0]+661.01, 0),2)))
                    if mag_i_c[8][0] <= 2700: #127,9
                        msg2.append(str(round(np.maximum(1.0185*mag_i_c[8][0]-0.595, np.random.random()),2)))
                    else:
                        msg2.append(str(round(np.maximum(1.0829*mag_i_c[8][0]-162.97, np.random.random()),2)))
                    msg2.append(str(round(np.maximum(1.0281*mag_i_c[9][0]-5.2206, np.random.random()),2))) #128,10
                    msg2.append(str(round(np.maximum(1.0409*mag_i_c[10][0]-4.8242, np.random.random()),2))) #129,11
                    msg2.append(str(round(np.maximum(1.0607*mag_i_c[11][0]-5.093, np.random.random()),2))) #130,12
                    msg2.append(str(round(np.maximum(1.0705*mag_i_c[12][0]-4.9561, np.random.random()),2))) #131,13
                    msg2.append(str(round(np.maximum(1.0876*mag_i_c[13][0]-4.113, np.random.random()),2))) #132,14
                    msg2.append(str(round(np.maximum(1.1144*mag_i_c[14][0]-5.9206, np.random.random()),2))) #133,15
                    msg2.append(str(round(np.maximum(1.1274*mag_i_c[15][0]-4.1793, np.random.random()),2))) #134,16
                    msg2.append(str(round(np.maximum(1.1493*mag_i_c[16][0]-3.0777, np.random.random()),2))) #135,17
                    msg2.append(str(round(np.maximum(1.1824*mag_i_c[17][0]-4.6092, np.random.random()),2))) #136,18
                    msg2.append(str(round(np.maximum(1.2042*mag_i_c[18][0]-5.4638, np.random.random()),2))) #137,19
                    msg2.append(str(round(np.maximum(1.2336*mag_i_c[19][0]-5.1226, np.random.random()),2))) #138,20
                    msg2.append(str(round(np.maximum(1.2667*mag_i_c[20][0]-0.0778, np.random.random()),2))) #139,21
                    msg2.append(str(round(np.maximum(1.2936*mag_i_c[21][0]+1.3494, 0),2))) #140,22
                    msg2.append(str(round(np.maximum(1.3765*mag_i_c[22][0]+1.4331, 0),2))) #141,23
                    msg2.append(str(round(np.maximum(1.3834*mag_i_c[23][0]-0.6117, np.random.random()),2))) #142,24
                    msg2.append(str(round(np.maximum(1.4209*mag_i_c[24][0]-0.023, np.random.random()),2))) #143,25
                    msg2.append(str(round(np.maximum(1.4765*mag_i_c[25][0]-1.5728, np.random.random()),2))) #144,26
                    msg2.append(str(round(np.maximum(1.5327*mag_i_c[26][0]+0.6102, 0),2))) #145,27
                    msg2.append(str(round(np.maximum(1.5855*mag_i_c[27][0]-0.004, np.random.random()),2))) #146,28
                    msg2.append(str(round(np.maximum(1.6514*mag_i_c[28][0]+0.1835, 0),2))) #147,29
                    msg2.append(str(round(np.maximum(1.7381*mag_i_c[29][0]-0.9568, np.random.random()),2))) #148,30
                    msg2.append(str(round(np.maximum(1.807*mag_i_c[30][0]-0.8226, np.random.random()),2))) #149,31
                    msg2.append(str(round(np.maximum(1.8962*mag_i_c[31][0] - 0.6746, np.random.random()),2))) #150,32
                    msg2.append(str(round(np.maximum(2.003*mag_i_c[32][0] - 0.004, np.random.random()),2))) #151,33
                    msg2.append(str(round(np.maximum(2.1063*mag_i_c[33][0] - 0.6717, np.random.random()),2))) #152,34
                    msg2.append(str(round(np.maximum(2.2117*mag_i_c[34][0] + 1.4143, 0),2))) #153,35
                    msg2.append(str(round(np.maximum(2.372*mag_i_c[35][0] + 1.9446, 0),2))) #154,36
                    msg2.append(str(round(np.maximum(2.5232*mag_i_c[36][0] - 0.4249, np.random.random()),2))) #155,37
                    msg2.append(str(round(np.maximum(2.7025*mag_i_c[37][0] + 0.3112, 0),2))) #156,38
                    msg2.append(str(round(np.maximum(2.9222*mag_i_c[38][0] + 0.0544, 0),2))) #157,39
                    msg2.append(str(round(np.maximum(3.1346*mag_i_c[39][0] + 1.5134, 0),2))) #158,40
                    msg2.append(str(round(np.maximum(3.417*mag_i_c[40][0] - 1.4205, np.random.random()),2))) #159,41
                    msg2.append(str(round(np.maximum(3.7794*mag_i_c[41][0] - 0.2731, np.random.random()),2))) #160,42
                    msg2.append(str(round(np.maximum(4.146*mag_i_c[42][0] - 1.342, np.random.random()),2))) #161,43
                    msg2.append(str(round(np.maximum(4.6403*mag_i_c[43][0] - 1.4393, np.random.random()),2))) #162,44
                    msg2.append(str(round(np.maximum(5.225*mag_i_c[44][0] + 0.5021, 0),2))) #163,45
                    msg2.append(str(round(np.maximum(5.9739*mag_i_c[45][0] + 2.9319, 0),2))) #164,46
                    msg2.append(str(round(np.maximum(6.9253*mag_i_c[46][0] + 0.898, 0),2))) #165,47
                    msg2.append(str(round(np.maximum(8.3666*mag_i_c[47][0] - 2.1514, np.random.random()),2))) #166,48
                    msg2.append(str(round(np.maximum(9.9222*mag_i_c[48][0] + 6.8161, 0),2))) #167,49
                    msg2.append('-') #168,50

                    #IN######################################################################
                    msg2.append(str(round(mag_i_n[0][0],2))) #169,1
                    if mag_i_n[1][0] <= 3900: #170,2
                        msg2.append(str(round(np.maximum(1.0021*mag_i_n[1][0] - 1.1277, np.random.random()),2)))
                    else:
                        msg2.append(str(round(np.maximum(1.1395*mag_i_n[1][0] - 496.91, np.random.random()),2)))
                    if mag_i_n[2][0] <= 1000: #171,3
                        msg2.append(str(round(np.maximum(1.0229*mag_i_n[2][0]-7.014, np.random.random()),2)))
                    else:
                        msg2.append(str(round(np.maximum(0.9996*mag_i_n[2][0]+12.964, 0),2)))
                    if mag_i_n[3][0] <= 2000: #172,4
                        msg2.append(str(round(np.maximum(1.0082*mag_i_n[3][0]+0.8499, 0),2)))
                    else:
                        msg2.append(str(round(np.maximum(1E-04*mag_i_n[3][0]**2+0.5418*mag_i_n[3][0]+560.96, 0),2)))
                    if mag_i_n[4][0] <= 2450: #173,5
                        msg2.append(str(round(np.maximum(1.0132*mag_i_n[4][0]+0.3477, 0),2)))
                    else:
                        msg2.append(str(round(np.maximum(6E-05*mag_i_n[4][0]**2+0.8002*mag_i_n[4][0]+155.62, 0),2)))
                    if mag_i_n[5][0] <= 2750: #174,6
                        msg2.append(str(round(np.maximum(1.0244*mag_i_n[5][0] - 0.3628, np.random.random()),2)))
                    else:
                        msg2.append(str(round(np.maximum(5E-05*mag_i_n[5][0]**2+0.8439*mag_i_n[5][0]+144.22, 0),2)))
                    if mag_i_n[6][0] <= 2400: #175,7
                        msg2.append(str(round(np.maximum(1.0369*mag_i_n[6][0]-0.2, np.random.random()),2)))
                    else:
                        msg2.append(str(round(np.maximum(0.0001*mag_i_n[6][0]**2+0.5289*mag_i_n[6][0]+636.41, 0),2)))
                    if mag_i_n[7][0] <= 2600: #176,8
                        msg2.append(str(round(np.maximum(1.0378*mag_i_n[7][0]-1.3557, np.random.random()),2)))
                    else:
                        msg2.append(str(round(np.maximum(1E-04*mag_i_n[7][0]**2+0.5472*mag_i_n[7][0]+607.94, 0),2)))
                    if mag_i_n[8][0] <= 2700: #177,9
                        msg2.append(str(round(np.maximum(1.0523*mag_i_n[8][0]-1.8365, np.random.random()),2)))
                    else:
                        msg2.append(str(round(np.maximum(1.1117*mag_i_n[8][0]-145.61, np.random.random()),2)))
                    msg2.append(str(round(np.maximum(1.0634*mag_i_n[9][0]-5.663, np.random.random()),2))) #178,10
                    msg2.append(str(round(np.maximum(1.0769*mag_i_n[10][0]-5.2521, np.random.random()),2))) #179,11
                    msg2.append(str(round(np.maximum(1.0961*mag_i_n[11][0]-5.1561, np.random.random()),2))) #180,12
                    msg2.append(str(round(np.maximum(1.1067*mag_i_n[12][0]-4.1236, np.random.random()),2))) #181,13
                    msg2.append(str(round(np.maximum(1.1247*mag_i_n[13][0]-3.3627, np.random.random()),2))) #182,14
                    msg2.append(str(round(np.maximum(1.1516*mag_i_n[14][0]-6.1885, np.random.random()),2))) #183,15
                    msg2.append(str(round(np.maximum(1.166*mag_i_n[15][0]-4.212, np.random.random()),2))) #184,16
                    msg2.append(str(round(np.maximum(1.1893*mag_i_n[16][0]-3.6679, np.random.random()),2))) #185,17
                    msg2.append(str(round(np.maximum(1.2211*mag_i_n[17][0]-3.3137, np.random.random()),2))) #186,18
                    msg2.append(str(round(np.maximum(1.2457*mag_i_n[18][0]-5.5519, np.random.random()),2))) #187,19
                    msg2.append(str(round(np.maximum(1.2757*mag_i_n[19][0]-4.4037, np.random.random()),2))) #188,20
                    msg2.append(str(round(np.maximum(1.3097*mag_i_n[20][0]-0.6851, np.random.random()),2))) #189,21
                    msg2.append(str(round(np.maximum(1.3376*mag_i_n[21][0]+1.8634, 0),2))) #190,22
                    msg2.append(str(round(np.maximum(1.3097*mag_i_n[22][0]+0.6851, 0),2))) #191,23
                    msg2.append(str(round(np.maximum(1.4298*mag_i_n[23][0]-0.7491, np.random.random()),2))) #192,24
                    msg2.append(str(round(np.maximum(1.4698*mag_i_n[24][0]-0.312, np.random.random()),2))) #193,25
                    msg2.append(str(round(np.maximum(1.5269*mag_i_n[25][0]-1.2608, np.random.random()),2))) #194,26
                    msg2.append(str(round(np.maximum(1.583*mag_i_n[26][0]+0.747, 0),2))) #195,27
                    msg2.append(str(round(np.maximum(1.6411*mag_i_n[27][0]-0.7343, np.random.random()),2))) #196,28
                    msg2.append(str(round(np.maximum(1.7093*mag_i_n[28][0]+0.2143, 0),2))) #197,29
                    msg2.append(str(round(np.maximum(1.7973*mag_i_n[29][0]-1.3673, np.random.random()),2))) #198,30
                    msg2.append(str(round(np.maximum(1.8736*mag_i_n[30][0]-2.4655, np.random.random()),2))) #199,31
                    msg2.append(str(round(np.maximum(1.9612*mag_i_n[31][0] - 0.5294, np.random.random()),2))) #200,32
                    msg2.append(str(round(np.maximum(2.0674*mag_i_n[32][0] + 1.5709, 0),2))) #201,33
                    msg2.append(str(round(np.maximum(2.1787*mag_i_n[33][0] - 0.3668, np.random.random()),2))) #202,34
                    msg2.append(str(round(np.maximum(2.2913*mag_i_n[34][0] - 0.1033, np.random.random()),2))) #203,35
                    msg2.append(str(round(np.maximum(2.4507*mag_i_n[35][0] + 2.3031, 0),2))) #204,36
                    msg2.append(str(round(np.maximum(2.6092*mag_i_n[36][0] - 0.3808, np.random.random()),2))) #205,37
                    msg2.append(str(round(np.maximum(2.7981*mag_i_n[37][0] + 0.2383, 0),2))) #206,38
                    msg2.append(str(round(np.maximum(3.008*mag_i_n[38][0] + 1.7002, 0),2))) #207,39
                    msg2.append(str(round(np.maximum(3.2435*mag_i_n[39][0] + 1.1826, 0),2))) #208,40
                    msg2.append(str(round(np.maximum(3.5347*mag_i_n[40][0] + 0.0126, 0),2))) #209,41
                    msg2.append(str(round(np.maximum(3.9036*mag_i_n[41][0] + 0.6088, 0),2))) #210,42
                    msg2.append(str(round(np.maximum(4.2869*mag_i_n[42][0] - 2.5891, np.random.random()),2))) #211,43
                    msg2.append(str(round(np.maximum(4.8034*mag_i_n[43][0] - 3.3474, np.random.random()),2))) #212,44
                    msg2.append(str(round(np.maximum(5.4015*mag_i_n[44][0] + 0.48, 0),2))) #213,45
                    msg2.append(str(round(np.maximum(6.2148*mag_i_n[45][0] + 1.2054, 0),2))) #214,46
                    msg2.append(str(round(np.maximum(7.1974*mag_i_n[46][0] - 0.9641, np.random.random()),2))) #215,47
                    msg2.append(str(round(np.maximum(8.6977*mag_i_n[47][0] - 5.6079, np.random.random()),2))) #216,48
                    msg2.append(str(round(np.maximum(10.318*mag_i_n[48][0] + 2.0608, 0),2))) #217,49
                    msg2.append('-') #218,50

                    #UA######################################################################
                    msg2.append(str(round(mag_u_a[0][0],2))) #219,1
                    msg2.append(str(round(np.maximum(0.9927*mag_u_a[1][0] + 0.18, 0),2))) #220,2
                    msg2.append(str(round(np.maximum(1.0005*mag_u_a[2][0] - 0.0246, np.random.random()),2))) #221,3
                    msg2.append(str(round(np.maximum(1.0054*mag_u_a[3][0] - 0.0083, np.random.random()),2))) #222,4
                    msg2.append(str(round(np.maximum(1.0144*mag_u_a[4][0] - 0.0482, np.random.random()),2))) #223,5
                    msg2.append(str(round(np.maximum(1.0138*mag_u_a[5][0] + 0.0097, 0),2))) #224,6
                    msg2.append(str(round(np.maximum(1.0253*mag_u_a[6][0] - 0.0143, np.random.random()),2))) #225,7
                    msg2.append(str(round(np.maximum(1.0317*mag_u_a[7][0] + 0.0087, 0),2))) #226,8
                    msg2.append(str(round(np.maximum(1.0348*mag_u_a[8][0] + 0.0668, 0),2))) #227,9
                    msg2.append(str(round(np.maximum(1.0503*mag_u_a[9][0] + 0.0087, 0),2))) #228,10
                    msg2.append(str(round(np.maximum(1.0654*mag_u_a[10][0] + 0.0212, 0),2))) #229,11
                    msg2.append(str(round(np.maximum(1.0804*mag_u_a[11][0] - 0.0222, np.random.random()),2))) #230,12
                    msg2.append(str(round(np.maximum(1.0971*mag_u_a[12][0] - 0.02, np.random.random()),2))) #231,13
                    msg2.append(str(round(np.maximum(1.1136*mag_u_a[13][0] + 0.0235, 0),2))) #232,14
                    msg2.append(str(round(np.maximum(1.1353*mag_u_a[14][0] - 0.0058, np.random.random()),2))) #233,15
                    msg2.append(str(round(np.maximum(1.1569*mag_u_a[15][0] - 0.0114, np.random.random()),2))) #234,16
                    msg2.append(str(round(np.maximum(1.1895*mag_u_a[16][0] - 0.048, np.random.random()),2))) #235,17
                    msg2.append(str(round(np.maximum(1.203*mag_u_a[17][0] + 0.0088, 0),2))) #236,18
                    msg2.append(str(round(np.maximum(1.2255*mag_u_a[18][0] + 0.0435, 0),2))) #237,19
                    msg2.append(str(round(np.maximum(1.2709*mag_u_a[19][0] - 0.051, np.random.random()),2))) #238,20
                    msg2.append(str(round(np.maximum(1.3227*mag_u_a[20][0] - 0.0371, np.random.random()),2))) #239,21
                    msg2.append(str(round(np.maximum(1.3562*mag_u_a[21][0] - 0.0349, np.random.random()),2))) #240,22
                    msg2.append(str(round(np.maximum(1.3694*mag_u_a[22][0] + 0.0392, 0),2))) #241,23
                    msg2.append(str(round(np.maximum(1.412*mag_u_a[23][0] + 0.0328, 0),2))) #242,24
                    msg2.append(str(round(np.maximum(1.4685*mag_u_a[24][0] - 0.0179, np.random.random()),2))) #243,25
                    msg2.append(str(round(np.maximum(1.5163*mag_u_a[25][0] + 0.0292, 0),2))) #244,26
                    msg2.append(str(round(np.maximum(1.582*mag_u_a[26][0] - 0.0302, np.random.random()),2))) #245,27
                    msg2.append(str(round(np.maximum(1.6448*mag_u_a[27][0] - 0.0488, np.random.random()),2))) #246,28
                    msg2.append(str(round(np.maximum(1.6693*mag_u_a[28][0] + 0.0527, 0),2))) #247,29
                    msg2.append(str(round(np.maximum(1.7413*mag_u_a[29][0] + 0.0487, 0),2))) #248,30
                    msg2.append(str(round(np.maximum(1.8622*mag_u_a[30][0] + 0.0969, 0),2))) #249,31
                    msg2.append(str(round(np.maximum(2.0292*mag_u_a[31][0] - 0.1256, np.random.random()),2))) #250,32
                    msg2.append(str(round(np.maximum(2.0621*mag_u_a[32][0] - 0.0353, np.random.random()),2))) #251,33
                    msg2.append(str(round(np.maximum(2.1217*mag_u_a[33][0] + 0.0652, 0),2))) #252,34
                    msg2.append(str(round(np.maximum(2.2601*mag_u_a[34][0] + 0.0835, 0),2))) #253,35
                    msg2.append(str(round(np.maximum(2.4473*mag_u_a[35][0] - 0.0647, np.random.random()),2))) #254,36
                    msg2.append(str(round(np.maximum(2.5947*mag_u_a[36][0] - 0.0165, np.random.random()),2))) #255,37
                    msg2.append(str(round(np.maximum(2.7434*mag_u_a[37][0] + 0.0586, 0),2))) #256,38
                    msg2.append(str(round(np.maximum(2.8632*mag_u_a[38][0] + 0.1482, 0),2))) #257,39
                    msg2.append(str(round(np.maximum(3.239*mag_u_a[39][0] - 0.137, np.random.random()),2))) #258,40
                    msg2.append(str(round(np.maximum(3.5942*mag_u_a[40][0] - 0.3128, np.random.random()),2))) #259,41
                    msg2.append(str(round(np.maximum(3.9072*mag_u_a[41][0] - 0.0683, np.random.random()),2))) #260,42
                    msg2.append(str(round(np.maximum(4.1933*mag_u_a[42][0] + 0.1283, 0),2))) #261,43
                    msg2.append(str(round(np.maximum(4.5722*mag_u_a[43][0] + 0.2904, 0),2))) #262,44
                    msg2.append(str(round(np.maximum(5.2549*mag_u_a[44][0] + 0.154, 0),2))) #263,45
                    msg2.append(str(round(np.maximum(5.9701*mag_u_a[45][0] + 0.1789, 0),2))) #264,46
                    msg2.append(str(round(np.maximum(7.0181*mag_u_a[46][0] + 0.1043, 0),2))) #265,47
                    msg2.append(str(round(np.maximum(7.9881*mag_u_a[47][0] + 0.3604, 0),2))) #266,48
                    msg2.append(str(round(np.maximum(9.2287*mag_u_a[48][0] + 0.6321, np.random.random()),2))) #267,49
                    msg2.append('-') #268,50

                    #UB######################################################################
                    msg2.append(str(round(mag_u_b[0][0],2))) #269,1
                    msg2.append(str(round(np.maximum(1.012*mag_u_b[1][0] - 0.2287, np.random.random()),2))) #270,2
                    msg2.append(str(round(np.maximum(1.0016*mag_u_b[2][0] + 0.0732, 0),2))) #271,3
                    msg2.append(str(round(np.maximum(1.0069*mag_u_b[3][0] - 0.0638, np.random.random()),2))) #272,4
                    msg2.append(str(round(np.maximum(1.0009*mag_u_b[4][0] + 0.1126, 0),2))) #273,5
                    msg2.append(str(round(np.maximum(1.0195*mag_u_b[5][0] - 0.0955, np.random.random()),2))) #274,6
                    msg2.append(str(round(np.maximum(1.0262*mag_u_b[6][0] - 0.0401, np.random.random()),2))) #275,7
                    msg2.append(str(round(np.maximum(1.0369*mag_u_b[7][0] - 0.0216, np.random.random()),2))) #276,8
                    msg2.append(str(round(np.maximum(1.0449*mag_u_b[8][0] - 0.0241, np.random.random()),2))) #277,9
                    msg2.append(str(round(np.maximum(1.0535*mag_u_b[9][0] - 0.0193, np.random.random()),2))) #278,10
                    msg2.append(str(round(np.maximum(1.0686*mag_u_b[10][0] + 0.012, 0),2))) #279,11
                    msg2.append(str(round(np.maximum(1.0808*mag_u_b[11][0] + 0.0371, 0),2))) #280,12
                    msg2.append(str(round(np.maximum(1.0973*mag_u_b[12][0] - 0.037, np.random.random()),2))) #281,13
                    msg2.append(str(round(np.maximum(1.1178*mag_u_b[13][0] + 0.0547, 0),2))) #282,14
                    msg2.append(str(round(np.maximum(1.136*mag_u_b[14][0] - 0.0074, np.random.random()),2))) #283,15
                    msg2.append(str(round(np.maximum(1.1595*mag_u_b[15][0] - 0.05, np.random.random()),2))) #284,16
                    msg2.append(str(round(np.maximum(1.1799*mag_u_b[16][0] + 0.0278, 0),2))) #285,17
                    msg2.append(str(round(np.maximum(1.2096*mag_u_b[17][0] + 0.0025, 0),2))) #286,18
                    msg2.append(str(round(np.maximum(1.2331*mag_u_b[18][0] + 0.0085, 0),2))) #287,19
                    msg2.append(str(round(np.maximum(1.2655*mag_u_b[19][0] + 0.029, 0),2))) #288,20
                    msg2.append(str(round(np.maximum(1.2831*mag_u_b[20][0] + 0.116, 0),2))) #289,21
                    msg2.append(str(round(np.maximum(1.3337*mag_u_b[21][0] + 0.0246, 0),2))) #290,22
                    msg2.append(str(round(np.maximum(1.4043*mag_u_b[22][0] - 0.0531, np.random.random()),2))) #291,23
                    msg2.append(str(round(np.maximum(1.4346*mag_u_b[23][0] - 0.0726, np.random.random()),2))) #292,24
                    msg2.append(str(round(np.maximum(1.4542*mag_u_b[24][0] + 0.0334, 0),2))) #293,25
                    msg2.append(str(round(np.maximum(1.5185*mag_u_b[25][0] + 0.0266, 0),2))) #294,26
                    msg2.append(str(round(np.maximum(1.5466*mag_u_b[26][0] + 0.1164, 0),2))) #295,27
                    msg2.append(str(round(np.maximum(1.6048*mag_u_b[27][0] + 0.0399, 0),2))) #296,28
                    msg2.append(str(round(np.maximum(1.7123*mag_u_b[28][0] - 0.0227, np.random.random()),2))) #297,29
                    msg2.append(str(round(np.maximum(1.8122*mag_u_b[29][0] - 0.1031, np.random.random()),2))) #298,30
                    msg2.append(str(round(np.maximum(1.8308*mag_u_b[30][0] + 0.1758, 0),2))) #299,31
                    msg2.append(str(round(np.maximum(2*mag_u_b[31][0] - 0.0643, np.random.random()),2))) #300,32
                    msg2.append(str(round(np.maximum(2.0873*mag_u_b[32][0] - 0.0375, np.random.random()),2))) #301,33
                    msg2.append(str(round(np.maximum(2.1705*mag_u_b[33][0] - 0.0346, np.random.random()),2))) #302,34
                    msg2.append(str(round(np.maximum(2.2991*mag_u_b[34][0] + 0.0015, 0),2))) #303,35
                    msg2.append(str(round(np.maximum(2.397*mag_u_b[35][0] + 0.0855, 0),2))) #304,36
                    msg2.append(str(round(np.maximum(2.5467*mag_u_b[36][0] - 0.0017, np.random.random()),2))) #305,37
                    msg2.append(str(round(np.maximum(2.7476*mag_u_b[37][0] + 0.0637, 0),2))) #306,38
                    msg2.append(str(round(np.maximum(2.9658*mag_u_b[38][0] - 0.0204, np.random.random()),2))) #307,39
                    msg2.append(str(round(np.maximum(3.264*mag_u_b[39][0] - 0.1637, np.random.random()),2))) #308,40
                    msg2.append(str(round(np.maximum(3.7353*mag_u_b[40][0] - 0.0738, np.random.random()),2))) #309,41
                    msg2.append(str(round(np.maximum(3.7809*mag_u_b[41][0] + 0.164, 0),2))) #310,42
                    msg2.append(str(round(np.maximum(4.2291*mag_u_b[42][0] - 0.0961, np.random.random()),2))) #311,43
                    msg2.append(str(round(np.maximum(4.6541*mag_u_b[43][0] + 0.0791, 0),2))) #312,44
                    msg2.append(str(round(np.maximum(5.4327*mag_u_b[44][0] - 0.0762, np.random.random()),2))) #313,45
                    msg2.append(str(round(np.maximum(6.0263*mag_u_b[45][0] + 0.0246, 0),2))) #314,46
                    msg2.append(str(round(np.maximum(7.1007*mag_u_b[46][0] - 0.0037, np.random.random()),2))) #315,47
                    msg2.append(str(round(np.maximum(8.137*mag_u_b[47][0] + 0.0813, 0),2))) #316,48
                    msg2.append(str(round(np.maximum(10.115*mag_u_b[48][0] - 0.0537, np.random.random()),2))) #317,49
                    msg2.append('-') #318,50

                    #UC######################################################################
                    msg2.append(str(round(mag_u_c[0][0],2))) #319,1
                    msg2.append(str(round(np.maximum(0.9937*mag_u_c[1][0] - 0.0925, np.random.random()),2))) #320,2
                    msg2.append(str(round(np.maximum(0.9993*mag_u_c[2][0] - 0.0473, np.random.random()),2))) #321,3
                    msg2.append(str(round(np.maximum(1.0061*mag_u_c[3][0] + 0.012, 0),2))) #322,4
                    msg2.append(str(round(np.maximum(1.0034*mag_u_c[4][0] + 0.1108, 0),2))) #323,5
                    msg2.append(str(round(np.maximum(1.0108*mag_u_c[5][0] + 0.1102, 0),2))) #324,6
                    msg2.append(str(round(np.maximum(1.0275*mag_u_c[6][0] - 0.0061, np.random.random()),2))) #325,7
                    msg2.append(str(round(np.maximum(1.0331*mag_u_c[7][0] - 0.017, np.random.random()),2))) #326,8
                    msg2.append(str(round(np.maximum(1.0475*mag_u_c[8][0] - 0.0317, np.random.random()),2))) #327,9
                    msg2.append(str(round(np.maximum(1.0561*mag_u_c[9][0] - 0.0263, np.random.random()),2))) #328,10
                    msg2.append(str(round(np.maximum(1.0702*mag_u_c[10][0] - 0.0161, np.random.random()),2))) #329,11
                    msg2.append(str(round(np.maximum(1.084*mag_u_c[11][0] - 0.0111, np.random.random()),2))) #330,12
                    msg2.append(str(round(np.maximum(1.1*mag_u_c[12][0] - 0.0142, np.random.random()),2))) #331,13
                    msg2.append(str(round(np.maximum(1.1171*mag_u_c[13][0] + 0.0025, 0),2))) #332,14
                    msg2.append(str(round(np.maximum(1.1335*mag_u_c[14][0] + 0.0161, 0),2))) #333,15
                    msg2.append(str(round(np.maximum(1.1574*mag_u_c[15][0] + 0.0126, 0),2))) #334,16
                    msg2.append(str(round(np.maximum(1.1787*mag_u_c[16][0] + 0.0205, 0),2))) #335,17
                    msg2.append(str(round(np.maximum(1.2057*mag_u_c[17][0] - 0.0138, np.random.random()),2))) #336,18
                    msg2.append(str(round(np.maximum(1.2363*mag_u_c[18][0] - 0.0278, np.random.random()),2))) #337,19
                    msg2.append(str(round(np.maximum(1.2612*mag_u_c[19][0] + 0.0196, 0),2))) #338,20
                    msg2.append(str(round(np.maximum(1.2813*mag_u_c[20][0] + 0.1081, 0),2))) #339,21
                    msg2.append(str(round(np.maximum(1.3276*mag_u_c[21][0] + 0.0122, 0),2))) #340,22
                    msg2.append(str(round(np.maximum(1.3592*mag_u_c[22][0] + 0.1138, 0),2))) #341,23
                    msg2.append(str(round(np.maximum(1.4389*mag_u_c[23][0] - 0.0779, np.random.random()),2))) #342,24
                    msg2.append(str(round(np.maximum(1.4586*mag_u_c[24][0] + 0.0604, 0),2))) #343,25
                    msg2.append(str(round(np.maximum(1.5533*mag_u_c[25][0] - 0.1379, np.random.random()),2))) #344,26
                    msg2.append(str(round(np.maximum(1.5833*mag_u_c[26][0] - 0.0111, np.random.random()),2))) #345,27
                    msg2.append(str(round(np.maximum(1.6737*mag_u_c[27][0] - 0.1523, np.random.random()),2))) #346,28
                    msg2.append(str(round(np.maximum(1.742*mag_u_c[28][0] - 0.0466, np.random.random()),2))) #347,29
                    msg2.append(str(round(np.maximum(1.7645*mag_u_c[29][0] + 0.0911, 0),2))) #348,30
                    msg2.append(str(round(np.maximum(1.8951*mag_u_c[30][0] - 0.2688, np.random.random()),2))) #349,31
                    msg2.append(str(round(np.maximum(1.8861*mag_u_c[31][0] + 0.0865, 0),2))) #350,32
                    msg2.append(str(round(np.maximum(2.0632*mag_u_c[32][0] - 0.0687, np.random.random()),2))) #351,33
                    msg2.append(str(round(np.maximum(2.1061*mag_u_c[33][0] + 0.0991, 0),2))) #352,34
                    msg2.append(str(round(np.maximum(2.3058*mag_u_c[34][0] - 0.0483, np.random.random()),2))) #353,35
                    msg2.append(str(round(np.maximum(2.4134*mag_u_c[35][0] + 0.0571, 0),2))) #354,36
                    msg2.append(str(round(np.maximum(2.6423*mag_u_c[36][0] - 0.0351, np.random.random()),2))) #355,37
                    msg2.append(str(round(np.maximum(2.734*mag_u_c[37][0] + 0.1448, 0),2))) #356,38
                    msg2.append(str(round(np.maximum(2.966*mag_u_c[38][0] + 0.2133, 0),2))) #357,39
                    msg2.append(str(round(np.maximum(2.9737*mag_u_c[39][0] + 0.7219, 0),2))) #358,40
                    msg2.append(str(round(np.maximum(3.4064*mag_u_c[40][0] + 0.302, 0),2))) #359,41
                    msg2.append(str(round(np.maximum(3.9977*mag_u_c[41][0] - 0.1739, np.random.random()),2))) #360,42
                    msg2.append(str(round(np.maximum(4.4255*mag_u_c[42][0] - 0.2005, np.random.random()),2))) #361,43
                    msg2.append(str(round(np.maximum(4.7537*mag_u_c[43][0] + 0.0029, 0),2))) #362,44
                    msg2.append(str(round(np.maximum(5.254*mag_u_c[44][0] + 0.0033, 0),2))) #363,45
                    msg2.append(str(round(np.maximum(5.7985*mag_u_c[45][0] + 0.1894, 0),2))) #364,46
                    msg2.append(str(round(np.maximum(6.821*mag_u_c[46][0] + 0.0518, 0),2))) #365,47
                    msg2.append(str(round(np.maximum(8.2312*mag_u_c[47][0] + 0.1065, 0),2))) #366,48
                    msg2.append(str(round(np.maximum(10.675*mag_u_c[48][0] - 0.2321, np.random.random()),2))) #367,49
                    msg2.append('-') #368,50

                    #msg2[10:19] = ['-' for i in range(9)]
                    if self.PhaseCheckBox.isChecked():
                        msg2[19:68] = [msg2[i+19]+'/'+str(round(mag_i_a[i][1],3)) for i in range(49)]
                        msg2.append('-')
                        msg2[69:118] = [msg2[i+69]+'/'+str(round(mag_i_b[i][1],3)) for i in range(49)]
                        msg2.append('-')
                        msg2[119:168] = [msg2[i+119]+'/'+str(round(mag_i_c[i][1],3)) for i in range(49)]
                        msg2.append('-')
                        msg2[169:218] = [msg2[i+169]+'/'+str(round(mag_i_n[i][1],3)) for i in range(49)]
                        msg2.append('-')
                        msg2[219:268] = [msg2[i+219]+'/'+str(round(mag_u_a[i][1],3)) for i in range(49)]
                        msg2.append('-')
                        msg2[269:318] = [msg2[i+269]+'/'+str(round(mag_u_b[i][1],3)) for i in range(49)]
                        msg2.append('-')
                        msg2[319:368] = [msg2[i+319]+'/'+str(round(mag_u_c[0][1],3)) for i in range(49)]
                        msg2.append('-')
                    '''else:
                        msg2[19:68] = [str(round(mag_i_a[i][0],2)) for i in range(49)]
                        msg2.append('-')
                        msg2[69:118] = [str(round(mag_i_b[i][0],2)) for i in range(49)]
                        msg2.append('-')
                        msg2[119:168] = [str(round(mag_i_c[i][0],2)) for i in range(49)]
                        msg2.append('-')
                        msg2[169:218] = [str(round(mag_i_n[i][0],2)) for i in range(49)]
                        msg2.append('-')
                        msg2[219:268] = [str(round(mag_u_a[i][0],2)) for i in range(49)]
                        msg2.append('-')
                        msg2[269:318] = [str(round(mag_u_b[i][0],2)) for i in range(49)]
                        msg2.append('-')
                        msg2[319:368] = [str(round(mag_u_c[i][0],2)) for i in range(49)]
                        msg2.append('-')'''
                        
                    msg3[19:68] = [str(round((mag_i_a[i][2]*float(msg2[i+19].split('/')[0])/mag_i_a[i][0]),2)) for i in range(49)]
                    msg3.append('-')
                    msg3[69:118] = [str(round((mag_i_b[i][2]*float(msg2[i+69].split('/')[0])/mag_i_b[i][0]),2)) for i in range(49)]
                    msg3.append('-')
                    msg3[119:168] = [str(round((mag_i_c[i][2]*float(msg2[i+119].split('/')[0])/mag_i_c[i][0]),2)) for i in range(49)]
                    msg3.append('-')
                    msg3[169:218] = [str(round((mag_i_n[i][2]*float(msg2[i+169].split('/')[0])/mag_i_n[i][0]),2)) for i in range(49)]
                    msg3.append('-')
                    msg3[219:268] = [str(round((mag_u_a[i][2]*float(msg2[i+219].split('/')[0])/mag_u_a[i][0]),2)) for i in range(49)]
                    msg3.append('-')
                    msg3[269:318] = [str(round((mag_u_b[i][2]*float(msg2[i+269].split('/')[0])/mag_u_b[i][0]),2)) for i in range(49)]
                    msg3.append('-')
                    msg3[319:368] = [str(round((mag_u_c[i][2]*float(msg2[i+319].split('/')[0])/mag_u_c[i][0]),2)) for i in range(49)]
                    msg3.append('-')
                    list_files = [f for f in os.listdir() if ((os.path.isfile(os.path.join(f))) & (Path(f).suffix == '.csv'))]
                    list_files.remove('test_data0.csv')
                    list_files.remove('Tunning_coeff.csv')
                    list_files.remove('actual_data.csv')
                    if self.InternetCheckBox.isChecked():
                        a, b = sending_email.read_email(theme, email_msg, list_files, region_name_, aws_access_key_id_, aws_secret_access_key_, bucket_)
                        if (a==1):
                            with open("log_"+self.file_to_write, "a", newline='') as f:
                                    writer = csv.writer(f, delimiter=";")
                                    writer.writerow([datetime.today().strftime("%H-%M-%S")]+["Данные отправлены по запросу "+b])
                        elif (a==2):
                            with open("log_"+self.file_to_write, "a", newline='') as f:
                                    writer = csv.writer(f, delimiter=";")
                                    writer.writerow([datetime.today().strftime("%H-%M-%S")]+["Программа обновлена"])
                            self.read_cyclic_stop()
                            self.disconnect_button()
                            subprocess.check_call('reboot')
                    if (self.file_to_write != (msg2[1]+'.csv')):
                        if self.InternetCheckBox.isChecked():
                            sending_email.send_email(addr_to, theme, email_msg, list_files, region_name_, aws_access_key_id_, aws_secret_access_key_, bucket_)
                            with open("log_"+self.file_to_write, "a", newline='') as f:
                                writer = csv.writer(f, delimiter=";")
                                writer.writerow([datetime.today().strftime("%H-%M-%S")]+["Данные отправлены на email: "+addr_to])
                            if del_sent_files:
                                for i in list_files:
                                    os.remove(i)
                        self.file_to_write = msg2[1]+'.csv'
                        if not os.path.exists(self.file_to_write):
                            shutil.copy2(r'test_data0.csv', self.file_to_write)
                            with open(self.file_to_write, "a", newline='') as f:
                                writer = csv.writer(f, delimiter=";")
                                writer.writerow("")
                            with open("log_"+self.file_to_write, "a", newline='') as f:
                                writer = csv.writer(f, delimiter=";")
                                writer.writerow([datetime.today().strftime("%H-%M-%S")]+["Начало новых суток. Без проишествий"])
                    if ((self.spinBoxRate.value() / ard_tp_) <= self.indexRate):
                        with open(self.file_to_write, "a", newline='') as f:
                            writer = csv.writer(f, delimiter=";")
                            writer.writerow(msg2)
                        self.indexRate = 1
                        if self.InternetCheckBox.isChecked():
                            # Data to the Object Storage
                            session = boto3.session.Session()
                            s3 = session.client(service_name='s3', endpoint_url='https://storage.yandexcloud.net',
                                                region_name=region_name_,
                                                aws_access_key_id=aws_access_key_id_,
                                                aws_secret_access_key=aws_secret_access_key_)
                            with open('actual_data.csv', "w", newline='') as f:
                                writer = csv.writer(f, delimiter=";")
                                writer.writerow(msg3)
                            s3.upload_file('actual_data.csv', bucket_, 'data/actual_data.csv')

                            # Data to the db1 in ClickHouse
                            client = Client(host_, #compression = 'lz4',
                                            connect_timeout=1,
                                            send_receive_timeout=5, sync_request_timeout=1,
                                            secure=True, port = 9440,
                                            user = user_, password = pass_, database=db_,
                                            ca_certs=ca_certs_)
                            d_ = [int(i) for i in msg3[1].split('_')]
                            t_ = [int(i) for i in msg3[2].split('_')]
                            date_ = dt.date(year=d_[2], month=d_[1], day=d_[0])
                            time_ = datetime(year=d_[2], month=d_[1], day=d_[0],
                                            hour=t_[0], minute=t_[1], second=t_[2])
                            temp_dict = {'gps_lat_long': msg3[0], 'date': date_, 'time': time_,
                                          'Ua_V': float(msg3[3]), 'Ub_V': float(msg3[4]), 'Uc_V': float(msg3[5]),
                                          'Ia_mA': float(msg3[6]), 'Ib_mA': float(msg3[7]), 'Ic_mA': float(msg3[8]),
                                          'In_mA': float(msg3[9]),
                                          'Pa_W': float(msg3[10]), 'Pb_W': float(msg3[11]), 'Pc_W': float(msg3[12]),
                                          'Sa_VA': float(msg3[13]), 'Sb_VA': float(msg3[14]), 'Sc_VA': float(msg3[15]),
                                          'cosa': float(msg3[16]), 'cosb': float(msg3[17]), 'cosc': float(msg3[18])}
                            temp = client.execute('INSERT INTO base_data \
                                                  (gps_lat_long, date, time, Ua_V, Ub_V, Uc_V, \
                                                    Ia_mA, Ib_mA, Ic_mA, In_mA, Pa_W, Pb_W, Pc_W, \
                                                    Sa_VA, Sb_VA, Sc_VA, cosa, cosb, cosc) VALUES', [temp_dict])
                            temp_list = ['a', 'b', 'c', 'n']
                            for ind in temp_list:
                                temp = ['i_' + ind +'_'+str(i+1) for i in range(49)]
                                temp_str = '(time, '
                                temp_dict['time'] = time_
                                for i in range(49):
                                    if ind == 'a':
                                        temp_dict[temp[i]] = float(msg2[i+19].split('/')[0])
                                    elif ind == 'b':
                                        temp_dict[temp[i]] = float(msg2[i+69].split('/')[0])
                                    elif ind == 'c':
                                        temp_dict[temp[i]] = float(msg2[i+119].split('/')[0])
                                    elif ind == 'n':
                                        temp_dict[temp[i]] = float(msg2[i+169].split('/')[0])
                                    temp_str = temp_str + temp[i]+', '
                                temp_dict['i_'+ind+'_50'] = 0
                                temp_str = temp_str + 'i_'+ind+'_50) '
                                temp = client.execute('INSERT INTO i_'+ind+'_mag_data '+ temp_str + 'VALUES', [temp_dict])
                            temp_list = ['a', 'b', 'c', 'n']
                            for ind in temp_list:
                                temp = ['i_' + ind +'_'+str(i+1) for i in range(49)]
                                temp_str = '(time, '
                                temp_dict['time'] = time_
                                for i in range(49):
                                    if ind == 'a':
                                        temp_dict[temp[i]] = msg3[i+19]
                                    elif ind == 'b':
                                        temp_dict[temp[i]] = msg3[i+69]
                                    elif ind == 'c':
                                        temp_dict[temp[i]] = msg3[i+119]
                                    elif ind == 'n':
                                        temp_dict[temp[i]] = msg3[i+169]
                                    temp_str = temp_str + temp[i]+', '
                                temp_dict['i_'+ind+'_50'] = '0'
                                temp_str = temp_str + 'i_'+ind+'_50) '
                                temp = client.execute('INSERT INTO i_'+ind+'_garm_data '+ temp_str + 'VALUES', [temp_dict])
                            temp_list = ['a', 'b', 'c']
                            for ind in temp_list:
                                temp = ['u_' + ind +'_'+str(i+1) for i in range(49)]
                                temp_str = '(time, '
                                temp_dict['time'] = time_
                                for i in range(49):
                                    if ind == 'a':
                                        temp_dict[temp[i]] = float(msg2[i+219].split('/')[0])
                                    elif ind == 'b':
                                        temp_dict[temp[i]] = float(msg2[i+269].split('/')[0])
                                    elif ind == 'c':
                                        temp_dict[temp[i]] = float(msg2[i+319].split('/')[0])
                                    temp_str = temp_str + temp[i]+', '
                                temp_dict['u_'+ind+'_50'] = 0
                                temp_str = temp_str + 'u_'+ind+'_50) '
                                temp = client.execute('INSERT INTO u_'+ind+'_mag_data '+ temp_str + 'VALUES', [temp_dict])
                            temp_list = ['a', 'b', 'c']
                            for ind in temp_list:
                                temp = ['u_' + ind +'_'+str(i+1) for i in range(49)]
                                temp_str = '(time, '
                                temp_dict['time'] = time_
                                for i in range(49):
                                    if ind == 'a':
                                        temp_dict[temp[i]] = msg3[i+219]
                                    elif ind == 'b':
                                        temp_dict[temp[i]] = msg3[i+269]
                                    elif ind == 'c':
                                        temp_dict[temp[i]] = msg3[i+319]
                                    temp_str = temp_str + temp[i]+', '
                                temp_dict['u_'+ind+'_50'] = '0'
                                temp_str = temp_str + 'u_'+ind+'_50) '
                                temp = client.execute('INSERT INTO u_'+ind+'_garm_data '+ temp_str + 'VALUES', [temp_dict])
                            temp = client.disconnect()
                    else:
                        self.indexRate += 1
                    
                except Exception as e:
                    with open("log_"+self.file_to_write, "a", newline='') as f:
                        writer = csv.writer(f, delimiter=";")
                        writer.writerow([datetime.today().strftime("%H-%M-%S")]+[str(e)])

                try: # Разделение данных на 8 групп
                    self.msg_tabData = msg2[:19]
                    self.msg_tableIag = msg2[19:69]
                    self.msg_tableIbg = msg2[69:119]
                    self.msg_tableIcg = msg2[119:169]
                    self.msg_tableIng = msg2[169:219]
                    self.msg_tableUag = msg2[219:269]
                    self.msg_tableUbg = msg2[269:319]
                    self.msg_tableUcg = msg2[319:]
                except Exception as e:
                    with open("log_"+self.file_to_write, "a", newline='') as f:
                        writer = csv.writer(f, delimiter=";")
                        writer.writerow([datetime.today().strftime("%H-%M-%S")]+[str(e)])
                try:
                    self.write_tabData()
                    if self.GraphicsCheckBox.isChecked():
                        self.write_tableGarm()
                        mag_proc = [float(msg2[i].split('/')[0])/mag_i_a[0][0]*100 for i in range(19, 19+len(mag_i_a))]
                        self.IagGrView___.update_figure_g(mag_proc)
                        self.IamGrView___.update_figure(data=i_a, title=" I_a (мА) ")
                        mag_proc = [float(msg2[i].split('/')[0])/mag_i_b[0][0]*100 for i in range(69, 69+len(mag_i_b))]
                        self.IbgGrView___.update_figure_g(mag_proc)
                        self.IbmGrView___.update_figure(data=i_b, title=" I_b (мА) ")
                        mag_proc = [float(msg2[i].split('/')[0])/mag_i_c[0][0]*100 for i in range(119, 119+len(mag_i_c))]
                        self.IcgGrView___.update_figure_g(mag_proc)
                        self.IcmGrView___.update_figure(data=i_c, title=" I_c (мА) ")
                        mag_proc = [float(msg2[i].split('/')[0])/mag_i_n[0][0]*100 for i in range(169, 169+len(mag_i_n))]
                        self.IngGrView___.update_figure_g(mag_proc)
                        self.InmGrView___.update_figure(data=i_n, title=" I_n (мА) ")
                        mag_proc = [float(msg2[i].split('/')[0])/mag_u_a[0][0]*100 for i in range(219, 219+len(mag_u_a))]
                        self.UagGrView___.update_figure_g(mag_proc)
                        self.UamGrView___.update_figure(data=u_a, title=" U_a (В) ")
                        mag_proc = [float(msg2[i].split('/')[0])/mag_u_b[0][0]*100 for i in range(269, 269+len(mag_u_b))]
                        self.UbgGrView___.update_figure_g(mag_proc)
                        self.UbmGrView___.update_figure(data=u_b, title=" U_b (В) ")
                        mag_proc = [float(msg2[i].split('/')[0])/mag_u_c[0][0]*100 for i in range(319, 319+len(mag_u_c))]
                        self.UcgGrView___.update_figure_g(mag_proc)
                        self.UcmGrView___.update_figure(data=u_c, title=" U_c (В) ")
                except Exception as e:
                    with open("log_"+self.file_to_write, "a", newline='') as f:
                        writer = csv.writer(f, delimiter=";")
                        writer.writerow([datetime.today().strftime("%H-%M-%S")]+[str(e)])
        pass

    def write_Graphs(self):
        self.IagGrView___.update_figure(mag_i_a)

    def read_cyclic_start_v3(self):
        self.indexRate = 1
        while self.readyToCyclicRead:
            msg_last = self.read_serial()
            msg = msg_last.split(';')
            self.processEvents()
            try:
                msg1 = msg[:len(msg)-1]
                if len(msg) > 10:
                    #if (self.file_to_write != (datetime.today().strftime("%Y-%m-%d")+'.csv')):
                        #self.file_to_write = datetime.today().strftime("%Y-%m-%d")+'.csv'
                    list_files = [f for f in os.listdir() if ((os.path.isfile(os.path.join(f))) & (Path(f).suffix == '.csv'))]
                    list_files.remove('test_data0.csv')
                    list_files.remove('Tunning_coeff.csv')
                    list_files.remove('actual_data.csv')
                    if self.InternetCheckBox.isChecked():
                        a,b = sending_email.read_email(theme, email_msg, list_files)
                        if (a==1):
                            with open("log_"+self.file_to_write, "a", newline='') as f:
                                writer = csv.writer(f, delimiter=";")
                                writer.writerow([datetime.today().strftime("%H-%M-%S")]+["Данные отправлены по запросу "+b])
                        elif (a==2):
                            with open("log_"+self.file_to_write, "a", newline='') as f:
                                writer = csv.writer(f, delimiter=";")
                                writer.writerow([datetime.today().strftime("%H-%M-%S")]+["Программа обновлена"])
                            self.read_cyclic_stop()
                            self.disconnect_button()
                            subprocess.check_call('reboot')
                    if (self.file_to_write != (msg1[1]+'.csv')):
                        if self.InternetCheckBox.isChecked():
                            sending_email.send_email(addr_to, theme, email_msg, list_files, region_name_, aws_access_key_id_, aws_secret_access_key_, bucket_)
                            with open("log_"+self.file_to_write, "a", newline='') as f:
                                writer = csv.writer(f, delimiter=";")
                                writer.writerow([datetime.today().strftime("%H-%M-%S")]+["Данные отправлены на email: "+addr_to])
                            if del_sent_files:
                                for i in list_files:
                                    os.remove(i)
                        self.file_to_write = msg1[1]+'.csv'
                        if not os.path.exists(self.file_to_write):
                            shutil.copy2(r'test_data0.csv', self.file_to_write)
                            with open(self.file_to_write, "a", newline='') as f:
                                writer = csv.writer(f, delimiter=";")
                                writer.writerow("")
                            with open("log_"+self.file_to_write, "a", newline='') as f:
                                    writer = csv.writer(f, delimiter=";")
                                    writer.writerow([datetime.today().strftime("%H-%M-%S")]+["Начало новых суток. Без проишествий"])
                    if ((self.spinBoxRate.value() / ard_tp_) <= self.indexRate):
                        with open(self.file_to_write, "a", newline='') as f:
                            writer = csv.writer(f, delimiter=";")
                            writer.writerow(msg1)
                        self.indexRate = 1
                    else:
                        self.indexRate += 1
            except Exception as e:
                with open("log_"+self.file_to_write, "a", newline='') as f:
                        writer = csv.writer(f, delimiter=";")
                        writer.writerow([datetime.today().strftime("%H-%M-%S")]+[str(e)])
            
            try: # Разделение данных на 8 групп
                self.msg_tabData = msg[:19]
            except Exception as e:
                with open("log_"+self.file_to_write, "a", newline='') as f:
                        writer = csv.writer(f, delimiter=";")
                        writer.writerow([datetime.today().strftime("%H-%M-%S")]+[str(e)])
            try:
                self.write_tabData()
                #self.write_tableGarm()
            except Exception as e:
                with open("log_"+self.file_to_write, "a", newline='') as f:
                        writer = csv.writer(f, delimiter=";")
                        writer.writerow([datetime.today().strftime("%H-%M-%S")]+[str(e)])
    

    def read_cyclic_start_v1(self):
        self.indexRate = 1
        while self.readyToCyclicRead:
            msg_last = self.read_serial()
            msg = msg_last.split(';')
            self.processEvents()
            try:
                msg1 = msg[:len(msg)-1]
                if len(msg) > 10:
                    #if (self.file_to_write != (datetime.today().strftime("%Y-%m-%d")+'.csv')):
                        #self.file_to_write = datetime.today().strftime("%Y-%m-%d")+'.csv'
                    list_files = [f for f in os.listdir() if ((os.path.isfile(os.path.join(f))) & (Path(f).suffix == '.csv'))]
                    list_files.remove('test_data0.csv')
                    list_files.remove('Tunning_coeff.csv')
                    list_files.remove('actual_data.csv')
                    if self.InternetCheckBox.isChecked():
                        a = sending_email.read_email(theme, email_msg, list_files)
                        if (a==1):
                            with open("log_"+self.file_to_write, "a", newline='') as f:
                                writer = csv.writer(f, delimiter=";")
                                writer.writerow([datetime.today().strftime("%H-%M-%S")]+["Данные отправлены по запросу "+b])
                        elif (a==2):
                            with open("log_"+self.file_to_write, "a", newline='') as f:
                                writer = csv.writer(f, delimiter=";")
                                writer.writerow([datetime.today().strftime("%H-%M-%S")]+["Программа обновлена"])
                            self.read_cyclic_stop()
                            self.disconnect_button()
                            subprocess.check_call('reboot')
                    if (self.file_to_write != (msg1[1]+'.csv')):
                        if self.InternetCheckBox.isChecked():
                            sending_email.send_email(addr_to, theme, email_msg, list_files, region_name_, aws_access_key_id_, aws_secret_access_key_, bucket_)
                            with open("log_"+self.file_to_write, "a", newline='') as f:
                                writer = csv.writer(f, delimiter=";")
                                writer.writerow([datetime.today().strftime("%H-%M-%S")]+["Данные отправлены на email: "+addr_to])
                            if del_sent_files:
                                for i in list_files:
                                    os.remove(i)
                        self.file_to_write = msg1[1]+'.csv'
                        if not os.path.exists(self.file_to_write):
                            shutil.copy2(r'test_data0.csv', self.file_to_write)
                            with open(self.file_to_write, "a", newline='') as f:
                                writer = csv.writer(f, delimiter=";")
                                writer.writerow("")
                            with open("log_"+self.file_to_write, "a", newline='') as f:
                                    writer = csv.writer(f, delimiter=";")
                                    writer.writerow([datetime.today().strftime("%H-%M-%S")]+["Начало новых суток. Без проишествий"])
                    if ((self.spinBoxRate.value() / ard_tp_) <= self.indexRate):
                        with open(self.file_to_write, "a", newline='') as f:
                            writer = csv.writer(f, delimiter=";")
                            writer.writerow(msg1)
                        self.indexRate = 1
                    else:
                        self.indexRate += 1
            except Exception as e:
                with open("log_"+self.file_to_write, "a", newline='') as f:
                        writer = csv.writer(f, delimiter=";")
                        writer.writerow([datetime.today().strftime("%H-%M-%S")]+[str(e)])
            
            try: # Разделение данных на 8 групп
                self.msg_tabData = msg[:19]
                self.msg_tableIag = msg[19:69]
                self.msg_tableIbg = msg[69:119]
                self.msg_tableIcg = msg[119:169]
                self.msg_tableIng = msg[169:219]
                self.msg_tableUag = msg[219:269]
                self.msg_tableUbg = msg[269:319]
                self.msg_tableUcg = msg[319:]
            except Exception as e:
                with open("log_"+self.file_to_write, "a", newline='') as f:
                        writer = csv.writer(f, delimiter=";")
                        writer.writerow([datetime.today().strftime("%H-%M-%S")]+[str(e)])
            try:
                self.write_tabData()
                self.write_tableGarm()
            except Exception as e:
                with open("log_"+self.file_to_write, "a", newline='') as f:
                        writer = csv.writer(f, delimiter=";")
                        writer.writerow([datetime.today().strftime("%H-%M-%S")]+[str(e)])
    
    def read_cyclic_stop(self):
        self.labelCyclicRead.setVisible(0)
        self.readCyclicButtonStart.setEnabled(1)
        self.readCyclicButtonStop.setEnabled(0)
        self.readButton.setEnabled(1)
        self.disconnectButton.setEnabled(1)
        self.spinBoxRate.setEnabled(1)
        self.labelReadDone.setVisible(0)
        self.readyToCyclicRead = False
        pass
    

    def lists_clear(self):
        self.listGPS.clear()
        self.listDate.clear()
        self.listTime.clear()
        self.listUa.clear()
        self.listUb.clear()
        self.listUc.clear()
        self.listIa.clear()
        self.listIb.clear()
        self.listIc.clear()
        self.listIn.clear()
        self.listPa.clear()
        self.listPb.clear()
        self.listPc.clear()
        self.listSa.clear()
        self.listSb.clear()
        self.listSc.clear()
        self.listCosa.clear()
        self.listCosb.clear()
        self.listCosc.clear()
        self.listWidgetTime.clear()

    def write_tabData(self):
        self.listGPS.addItem(self.msg_tabData[0])
        self.listDate.addItem(self.msg_tabData[1])
        self.listTime.addItem(self.msg_tabData[2])
        self.listUa.addItem(self.msg_tabData[3])
        self.listUb.addItem(self.msg_tabData[4])
        self.listUc.addItem(self.msg_tabData[5])
        self.listIa.addItem(self.msg_tabData[6])
        self.listIb.addItem(self.msg_tabData[7])
        self.listIc.addItem(self.msg_tabData[8])
        self.listIn.addItem(self.msg_tabData[9])
        self.listPa.addItem(self.msg_tabData[10])
        self.listPb.addItem(self.msg_tabData[11])
        self.listPc.addItem(self.msg_tabData[12])
        self.listSa.addItem(self.msg_tabData[13])
        self.listSb.addItem(self.msg_tabData[14])
        self.listSc.addItem(self.msg_tabData[15])
        self.listCosa.addItem(self.msg_tabData[16])
        self.listCosb.addItem(self.msg_tabData[17])
        self.listCosc.addItem(self.msg_tabData[18])
        self.listWidgetTime.addItem(str(datetime.today()))

    def write_tableGarm(self):
        for _ in range(20):
            self.tableIag.setItem(_, 1, QtWidgets.QTableWidgetItem(self.msg_tableIag[_]))
            self.tableIag.setItem(_, 3, QtWidgets.QTableWidgetItem(self.msg_tableIag[_+20]))

            self.tableIbg.setItem(_, 1, QtWidgets.QTableWidgetItem(self.msg_tableIbg[_]))
            self.tableIbg.setItem(_, 3, QtWidgets.QTableWidgetItem(self.msg_tableIbg[_+20]))

            self.tableIcg.setItem(_, 1, QtWidgets.QTableWidgetItem(self.msg_tableIcg[_]))
            self.tableIcg.setItem(_, 3, QtWidgets.QTableWidgetItem(self.msg_tableIcg[_+20]))

            self.tableIng.setItem(_, 1, QtWidgets.QTableWidgetItem(self.msg_tableIng[_]))
            self.tableIng.setItem(_, 3, QtWidgets.QTableWidgetItem(self.msg_tableIng[_+20]))

            self.tableUag.setItem(_, 1, QtWidgets.QTableWidgetItem(self.msg_tableUag[_]))
            self.tableUag.setItem(_, 3, QtWidgets.QTableWidgetItem(self.msg_tableUag[_+20]))

            self.tableUbg.setItem(_, 1, QtWidgets.QTableWidgetItem(self.msg_tableUbg[_]))
            self.tableUbg.setItem(_, 3, QtWidgets.QTableWidgetItem(self.msg_tableUbg[_+20]))

            self.tableUcg.setItem(_, 1, QtWidgets.QTableWidgetItem(self.msg_tableUcg[_]))
            self.tableUcg.setItem(_, 3, QtWidgets.QTableWidgetItem(self.msg_tableUcg[_+20]))

        for _ in range(10):
            self.tableIag.setItem(_, 5, QtWidgets.QTableWidgetItem(self.msg_tableIag[_+40]))
            self.tableIbg.setItem(_, 5, QtWidgets.QTableWidgetItem(self.msg_tableIbg[_+40]))
            self.tableIcg.setItem(_, 5, QtWidgets.QTableWidgetItem(self.msg_tableIcg[_+40]))
            self.tableIng.setItem(_, 5, QtWidgets.QTableWidgetItem(self.msg_tableIng[_+40]))
            self.tableUag.setItem(_, 5, QtWidgets.QTableWidgetItem(self.msg_tableUag[_+40]))
            self.tableUbg.setItem(_, 5, QtWidgets.QTableWidgetItem(self.msg_tableUbg[_+40]))
            self.tableUcg.setItem(_, 5, QtWidgets.QTableWidgetItem(self.msg_tableUcg[_+40]))

    def tables_clear(self):
        for _ in range(20):
            self.tableIag.setItem(_, 1, QtWidgets.QTableWidgetItem(''))
            self.tableIag.setItem(_, 3, QtWidgets.QTableWidgetItem(''))

            self.tableIbg.setItem(_, 1, QtWidgets.QTableWidgetItem(''))
            self.tableIbg.setItem(_, 3, QtWidgets.QTableWidgetItem(''))

            self.tableIcg.setItem(_, 1, QtWidgets.QTableWidgetItem(''))
            self.tableIcg.setItem(_, 3, QtWidgets.QTableWidgetItem(''))

            self.tableIng.setItem(_, 1, QtWidgets.QTableWidgetItem(''))
            self.tableIng.setItem(_, 3, QtWidgets.QTableWidgetItem(''))

            self.tableUag.setItem(_, 1, QtWidgets.QTableWidgetItem(''))
            self.tableUag.setItem(_, 3, QtWidgets.QTableWidgetItem(''))

            self.tableUbg.setItem(_, 1, QtWidgets.QTableWidgetItem(''))
            self.tableUbg.setItem(_, 3, QtWidgets.QTableWidgetItem(''))

            self.tableUcg.setItem(_, 1, QtWidgets.QTableWidgetItem(''))
            self.tableUcg.setItem(_, 3, QtWidgets.QTableWidgetItem(''))

        for _ in range(10):
            self.tableIag.setItem(_, 5, QtWidgets.QTableWidgetItem(''))
            self.tableIbg.setItem(_, 5, QtWidgets.QTableWidgetItem(''))
            self.tableIcg.setItem(_, 5, QtWidgets.QTableWidgetItem(''))
            self.tableIng.setItem(_, 5, QtWidgets.QTableWidgetItem(''))
            self.tableUag.setItem(_, 5, QtWidgets.QTableWidgetItem(''))
            self.tableUbg.setItem(_, 5, QtWidgets.QTableWidgetItem(''))
            self.tableUcg.setItem(_, 5, QtWidgets.QTableWidgetItem(''))


    def read_start_button(self):
        self.somethingWrong = False
        self.readCyclicButtonStart.setEnabled(0)
        self.readCyclicButtonStop.setEnabled(0)
        self.connectButton.setEnabled(0)
        self.disconnectButton.setEnabled(0)
        self.labelReadDone.setVisible(0)
        self.lists_clear()
        self.tables_clear()
        self.processEvents()
        _ = 0
        msg_str_= "_"
        msg_str = " "
        
        while ((not ((len(msg_str_)==0) & (msg_str[len(msg_str)-1] == '%'))) & (_<(time_to_sleep*10))):
            try:
                msg_bin = self.ard.read(self.ard.inWaiting())
                msg_str_ = msg_bin.decode()
            except Exception as e:
                _ = time_to_sleep*10
                self.disconnect_button()
                with open("log_"+self.file_to_write, "a", newline='') as f:
                        writer = csv.writer(f, delimiter=";")
                        writer.writerow([datetime.today().strftime("%H-%M-%S")]+[str(e)]+["--User mistake"])
                reply = QtWidgets.QMessageBox.question(self, 'Message',
                                               "Need to Change Port!",
                                               QtWidgets.QMessageBox.Yes,
                                               QtWidgets.QMessageBox.Yes)
                self.tabWidget.setCurrentIndex(0)
                self.somethingWrong = True
            msg_str += msg_str_
            _ += 1
            self.processEvents()
            time.sleep(.1)
        if (_ == (time_to_sleep*10)):
            if (len(msg_str) == 1):
                with open("log_"+self.file_to_write, "a", newline='') as f:
                        writer = csv.writer(f, delimiter=";")
                        writer.writerow([datetime.today().strftime("%H-%M-%S")]+["Буфер пуст"]+["--User mistake"])
                reply = QtWidgets.QMessageBox.question(self, 'Message',
                                               "Считать данные не удалось.\n"+
                                                " Видимо буфер данных пуст.\n"+
                                                   "Попробуйте перезапустить устройство.",
                                               QtWidgets.QMessageBox.Yes,
                                               QtWidgets.QMessageBox.Yes)
            else:
                with open("log_"+self.file_to_write, "a", newline='') as f:
                        writer = csv.writer(f, delimiter=";")
                        writer.writerow([datetime.today().strftime("%H-%M-%S")]+["Буфер переполнен"]+["--User mistake"])
                reply = QtWidgets.QMessageBox.question(self, 'Message',
                                               "Считать все данные не удалось.\n"+
                                                " Видимо буфер данных переполнен.\n"+
                                                   "Попробуйте еще раз."+str(len(msg_str)),
                                               QtWidgets.QMessageBox.Yes,
                                               QtWidgets.QMessageBox.Yes)

        if (_ != (time_to_sleep*10)) and not self.somethingWrong:
            self.lists_clear()
            self.tables_clear()
            #msg_str = msg_str.strip()
            msg_last = msg_str.split('%')
            msg_last = msg_last[len(msg_last)-2]
            msg = msg_last.split(';')
            msg = msg[:len(msg)-1]
            if (self.file_to_write != (datetime.today().strftime("%Y-%m-%d")+'.csv')):
                        self.file_to_write = datetime.today().strftime("%Y-%m-%d")+'.csv'
                        if not os.path.exists(self.file_to_write):
                            shutil.copy2(r'test_data0.csv', self.file_to_write)
                            with open(self.file_to_write, "a", newline='') as f:
                                writer = csv.writer(f, delimiter=";")
                                writer.writerow("")
            with open(self.file_to_write, "a", newline='') as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(msg)
            try: # Разделение данных на 8 групп
                self.msg_tabData = msg[:19]
                self.msg_tableIag = msg[19:69]
                self.msg_tableIbg = msg[69:119]
                self.msg_tableIcg = msg[119:169]
                self.msg_tableIng = msg[169:219]
                self.msg_tableUag = msg[219:269]
                self.msg_tableUbg = msg[269:319]
                self.msg_tableUcg = msg[319:]
            except Exception as e:
                with open("log_"+self.file_to_write, "a", newline='') as f:
                        writer = csv.writer(f, delimiter=";")
                        writer.writerow([datetime.today().strftime("%H-%M-%S")]+[str(e)]+["--User mistake"])
                reply = QtWidgets.QMessageBox.question(self, 'Message',
                                               "Количество данных в истонике\n"+
                                                "и приемных ячейках не совпадает:\n"+
                                                   str(e),
                                               QtWidgets.QMessageBox.Yes,
                                               QtWidgets.QMessageBox.Yes)
            try:
                self.write_tabData()
                self.write_tableGarm()
                self.labelReadDone.setVisible(1)
            except Exception as e:
                with open("log_"+self.file_to_write, "a", newline='') as f:
                        writer = csv.writer(f, delimiter=";")
                        writer.writerow([datetime.today().strftime("%H-%M-%S")]+[str(e)]+["--User mistake"])
                reply = QtWidgets.QMessageBox.question(self, 'Message',
                                               "Перенести данные не удалось.\n"+
                                                "Проверьте:\n"+
                                                   str(e),
                                               QtWidgets.QMessageBox.Yes,
                                               QtWidgets.QMessageBox.Yes)
        # QCoreApplication.processEvents()
        if not self.somethingWrong:
            self.readCyclicButtonStart.setEnabled(1)
            self.readCyclicButtonStop.setEnabled(0)
            self.connectButton.setEnabled(0)
            self.disconnectButton.setEnabled(1)

    def connect_button(self):
        autostart = True
        if (self.Port.currentText() != ""):
            port_name = self.Port.currentText()
        if (self.Speed.currentText() != ""):
            port_speed = int(self.Speed.currentText())
        try:
            self.ard = serial.Serial(port_name, port_speed, timeout = port_timeout)
            time.sleep(1)
            self.ard.flushInput()
            #self.сonnectButton.setStyleSheet("background-color: green")
            #self.сonnectButton.setText('')
            self.labelConnect.setVisible(1)
            self.connectButton.setEnabled(0)
            self.disconnectButton.setEnabled(1)
            self.readButton.setEnabled(1)
        except Exception as e:
            autostart = False
            with open("log_"+self.file_to_write, "a", newline='') as f:
                        writer = csv.writer(f, delimiter=";")
                        writer.writerow([datetime.today().strftime("%H-%M-%S")]+["Подключиться не удалось: "+str(e)])
            reply = QtWidgets.QMessageBox.question(self, 'Message',
                                               "Подключиться не удалось.\n"+
                                                " Проверьте:\n"+
                                                   str(e),
                                               QtWidgets.QMessageBox.Yes,
                                               QtWidgets.QMessageBox.Yes)
        self.readButton.setEnabled(1)
        self.readCyclicButtonStart.setEnabled(1)
        self.processEvents()
        self.Port.setEnabled(0)
        self.Speed.setEnabled(0)
        self.Protocol.setEnabled(0)
        return autostart
        
    def disconnect_button(self):
        try:
            #self.ard.flushInput()
            #time.sleep(1)
            self.ard.close()
            time.sleep(1)
            #self.ard.close()
            #time.sleep(1)
        except Exception as e:
            with open("log_"+self.file_to_write, "a", newline='') as f:
                        writer = csv.writer(f, delimiter=";")
                        writer.writerow([datetime.today().strftime("%H-%M-%S")]+["Отключиться не удалось: "+str(e)])
            reply = QtWidgets.QMessageBox.question(self, 'Message',
                                               "Отключиться не удалось.\n"+
                                                " Проверьте:\n"+
                                                   str(e),
                                               QtWidgets.QMessageBox.Yes,
                                               QtWidgets.QMessageBox.Yes)
            pass
        self.connectButton.setEnabled(1)
        self.disconnectButton.setEnabled(0)
        self.labelConnect.setVisible(0)
        self.readButton.setEnabled(0)
        self.readCyclicButtonStart.setEnabled(0)
        self.readCyclicButtonStop.setEnabled(0)
        self.labelCyclicRead.setVisible(0)
        self.Port.setEnabled(1)
        self.Speed.setEnabled(1)
        self.Protocol.setEnabled(1)
        

    def closeEvent(self, event):
        with open("log_"+self.file_to_write, "a", newline='') as f:
                        writer = csv.writer(f, delimiter=";")
                        writer.writerow([datetime.today().strftime("%H-%M-%S")]+["Программа завершена"])
        reply = QtWidgets.QMessageBox.question(self, 'Message',
                                               "Вы отключили устройство?",
                                               QtWidgets.QMessageBox.Yes |
                                               QtWidgets.QMessageBox.No,
                                               QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            #self.disconnect_button()
            event.accept()
        else:
            event.ignore()

def main():
    app = QtWidgets.QApplication(sys.argv) # New instance of QApplication
    window = SimpleListApp() # Create object of SimpleListApp class
    window.show() # Show the window
    sys.exit(app.exec_()) # Starting the application

    print("The End")
    
if __name__ == '__main__': # If we run file directly
    main() # then running main() fuction
    
