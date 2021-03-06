#!/usr/bin/env python
# -*- coding: utf-8 -*-
#############################################################################
#
# VoiceID, Copyright (C) 2011, Sardegna Ricerche.
# Email: labcontdigit@sardegnaricerche.it, michela.fancello@crs4.it,
#        mauro.mereu@crs4.it
# Web: http://code.google.com/p/voiceid
# Authors: Michela Fancello, Mauro Mereu
#
# This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#############################################################################
#
# VoiceID is a speaker recognition/identification system written in Python,
# based on the LIUM Speaker Diarization framework.
#
# VoiceID can process video or audio files to identify in which slices of
# time there is a person speaking (diarization); then it examines all those
# segments to identify who is speaking. To do so you must have a voice models
# database. To create the database you have to do a "train phase", in
# interactive mode, by assigning a label to the unknown speakers.
# You can also build yourself the speaker models and put those in the db
# using the scripts to create the gmm files.
#

from voiceid import VConf, sr, db, utils
from wx.lib.pubsub import setuparg1
import MplayerCtrl as mpc
import os.path
import subprocess
import sys
import threading
import time
import wx
import wx.lib.agw.ultimatelistctrl as ULC
import wx.lib.buttons as buttons

configuration = VConf()
local = 'local'
if sys.platform == 'win32' or sys.platform == 'darwin':
    local = ''
try:
    import platform
    if platform and hasattr(platform,'linux_distribution') and platform.linux_distribution()[0] in ['CentOS','Fedora','Red Hat Linux','Red Hat Enterprise Linux']:
        local = ''
except ImportError:
    pass

dirName = os.path.join(sys.prefix, local, 'share', 'voiceid')
bitmapDir = os.path.join(dirName, 'bitmaps')
dbDir = os.path.join(os.path.expanduser('~'), '.voiceid', 'gmm_db')
configuration.KEEP_INTERMEDIATE_FILES = True
LIST_ID = 26
PLAY_ID = 1
EDIT_ID = 0
MODE_DEFAULT = 311
MODE_NOISE = 312
OK_DIALOG = 33
CANCEL_DIALOG = 34


def get_length(filepath):
    """Capture video length

    :type filename: string
    :param filepath: video's path"""
    try:

        command = """mplayer  -vo null -ao null -frames 0 -identify %s""" % filepath

        #2>/dev/null |sed -ne '/^ID_/ {s/[]()|&;<>`'"'"'\\!$" []/\\&/g;p}'
        result = utils.check_cmd_output(command)
        r = result[0].split('\n')
        for row in r:
            if row.startswith("ID_LENGTH"):
                return row.split("=")[1]

    except Exception, e:
        print  e


class Controller(object):
    """A controller build the window interface and bind it all the control functions

    :type line: App
    :param app: App initializes the application"""

    def __init__(self, app, cl_args=None):

        self.model = Model()
        self.frame = MainFrame()
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.player = Player(self.frame)
        self.clusters_list = ClustersList(self.frame)
        sizer.Add(self.player, 5, wx.EXPAND)
        sizer.Add(self.clusters_list, 3, wx.EXPAND)
        self.frame.SetSizer(sizer)
        self.frame.Layout()
        sp = wx.StandardPaths.Get()
        self.currentFolder = sp.GetDocumentsDir()

        """ Binding toolbar buttons to control's function """
        self.frame.Bind(wx.EVT_MENU, self.on_add_file, self.frame.add_file_menu_item)
        self.frame.Bind(wx.EVT_MENU, self.on_close, self.frame.quit_file_menu_item)
        self.frame.Bind(wx.EVT_MENU, self.on_run_all, self.frame.all_menu_item)
        self.frame.Bind(wx.EVT_MENU, self.on_run_recognition, self.frame.recognition_menu_item)
        self.frame.Bind(wx.EVT_MENU, self.on_run_diarization, self.frame.diarization_menu_item)
        self.frame.Bind(wx.EVT_MENU, self.on_change_mode, self.frame.def_mode_menu_item)
        self.frame.Bind(wx.EVT_MENU, self.on_change_mode, self.frame.noise_mode_menu_item)
        self.frame.Bind(wx.EVT_MENU, self.on_save, self.frame.save_menu_item)
        self.frame.Bind(wx.EVT_MENU, self.on_select_db, self.frame.db_menu_item)

        self.frame.Bind(wx.EVT_SIZE, self.draw_selected_clusters)
        self.player.Bind(wx.EVT_TIMER, self.on_update_playback)
        self.frame.Bind(wx.EVT_CLOSE, self.on_close)

        self.clusters_list.list.Bind(ULC.EVT_LIST_COL_CHECKING, self.on_check_col_clusters_list)
        self.clusters_list.list.Bind(ULC.EVT_LIST_ITEM_CHECKED, self.on_check_item_clusters_list)
        self.clusters_list.list.Bind(ULC.EVT_LIST_END_LABEL_EDIT, self.on_edit_cluster)
        #self.player.colorPanel.Bind(wx.EVT_PAINT, self.draw_selected_clusters)

        self._setting_mode = -1

        Publisher.subscribe(self.update_status, "update_status")
        Publisher.subscribe(self.update_list, "update_list")
        Publisher.subscribe(self.update_info_video, "update_info")

        if cl_args:
            if len(cl_args) == 3:
                dbDir = cl_args[2]
                self.model.set_db(dbDir)
            if len(cl_args) >1:
                path = cl_args[1]
                self.model.load_video(path)
                self.on_load_file(path)




    def on_close(self, ev):
        """Destroy all processes and windows"""
        try:
            self.player.mpc.Quit()
        except:
            print "MplayerCtrl not started"
        self.frame.Destroy()

    def on_load_file(self, path):
        self.currentFolder = os.path.dirname(path[0])
        trackPath = '"%s"' % path.replace("\\", "/")
        self.player.load_file(trackPath)
        json_path = os.path.splitext(trackPath)[0] + '.json'
        json_path = json_path.replace('"', '')
        self.frame.enable_menu(True)
        self.clusters_list.clean_list()
        try:
            self.player.colorPanel.clear()
        except:
            pass
        #self.clusters_list.set_info_video("")

        if os.path.exists(json_path):
            self.model.load_json(json_path)
            self.frame.save_menu_item.Enable(True)
            wx.CallAfter(Publisher.sendMessage, "update_list", "Loading finished")
        else:
            self.frame.save_menu_item.Enable(False)
        wx.CallAfter(Publisher.sendMessage, "update_info")




    def on_add_file(self, event):
        """Adds a Movie and start playing it"""
        wildcard = "Media Files (*.*)|*.*"
        json_path = ""
        dlg = wx.FileDialog(
            self.frame, message="Choose a file",
            defaultDir=self.currentFolder,
            defaultFile="",
            wildcard=wildcard,
            style=wx.OPEN | wx.CHANGE_DIR)
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            self.currentFolder = os.path.dirname(path[0])
            trackPath = '"%s"' % path.replace("\\", "/")
            self.player.load_file(trackPath)
            json_path = os.path.splitext(trackPath)[0] + '.json'
            json_path = json_path.replace('"', '')

        self.frame.enable_menu(True)
        self.clusters_list.clean_list()
        try:
            self.player.colorPanel.clear()
        except:
            pass
        #self.clusters_list.set_info_video("")

        if os.path.exists(json_path):
            self.model.load_json(json_path)
            self.frame.save_menu_item.Enable(True)
            wx.CallAfter(Publisher.sendMessage, "update_list", "Loading finished")
        else:
            self.frame.save_menu_item.Enable(False)
        wx.CallAfter(Publisher.sendMessage, "update_info")

    def on_select_db(self, event):
        """Set database path"""
        dialog = wx.DirDialog(None, "Choose a directory:", style=wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        global dbDir
        if dialog.ShowModal() == wx.ID_OK:
            dbDir = dialog.GetPath()
            self.model.set_db(dbDir)
	    print "setting ["+dbDir+"] as db"
            wx.CallAfter(Publisher.sendMessage, "update_info")
            #print "on_select_db 1" +self.model.voiceid.get_clusters()
            try:
                path_video = self.player.video_path.replace('"', '')
                self.model.load_video(str(path_video))
                trackPath = '"%s"' % path_video.replace("\\", "/")
                json_path = os.path.splitext(trackPath)[0] + '.json'
                json_path = json_path.replace('"', '')
                if os.path.exists(json_path):
                    self.model.load_json(json_path)
            	self.model.set_db(dbDir)
            except StandardError, e:
                print e
                #print "No video to load"
            #print "on_select_db 2" +self.model.voiceid.get_clusters()
        dialog.Destroy()

    def log_on_processing(self):
        """Updates status bar while process input file"""
        old_status = self.model.get_status()
        wx.CallAfter(Publisher.sendMessage, "update_status", self.model.get_working_status() + " ...")
        while self.thread_processing.isAlive():
            time.sleep(2)
            status = self.model.get_status()
            try:
                if status != old_status:
                    old_status = self.model.get_status()
                    wx.CallAfter(Publisher.sendMessage, "update_status", self.model.get_working_status() + " ...")
            except StandardError:
                print "Error in print_logger"

        self.on_finish_processing()

    def on_finish_processing(self):
        """Enables Speaker Recognition button and update speakers list"""
        wx.CallAfter(Publisher.sendMessage, "update_status", self.model.get_map_status())
        self.frame.enable_menu(True)
        wx.CallAfter(Publisher.sendMessage, "update_list", "Process finished")
        wx.CallAfter(Publisher.sendMessage, "update_info")

    def log_on_save_changes(self):
        self.frame.enable_menu(False)
        while self.thread_saving.isAlive():
            time.sleep(2)
            wx.CallAfter(Publisher.sendMessage, "update_status", "Saving changes...")
        wx.CallAfter(Publisher.sendMessage, "update_list", "Changes saved")
        wx.CallAfter(Publisher.sendMessage, "update_info")
        wx.CallAfter(Publisher.sendMessage, "update_status", "Changes saved")
        self.frame.enable_menu(True)

    def on_change_mode(self, event):
        id = event.GetId()
        if id == MODE_DEFAULT:
            self.model.set_mode(0)
        else:
            self.model.set_mode(1)

    def update_status(self, msg):
        """Receives data from thread and updates the status bar

        :type msg: Message
        :param msg: text to update status bar"""
        self.frame.set_status_text(msg.data)

    def on_update_playback(self, event):
        """Updates playback slider and track counter"""
        try:
            offset = self.player.mpc.GetTimePos()
        except:
            return
        mod_off = str(offset)[-1]
        if mod_off == '0':
            offset = int(offset)

            self.player.playbackSlider.SetValue(offset)
            secsPlayed = time.strftime('%M:%S', time.gmtime(offset))
            self.player.trackCounter.SetLabel(secsPlayed)

        if len(self.clusters_list.list.checked) > 0:
            self.on_play_segments(event)

    def on_save(self, event):
        """Exports info to json format"""

        self.thread_saving = threading.Thread(target=self.model.save_changes)
        self.thread_saving.start()
        thread_logger = threading.Thread(target=self.log_on_save_changes)
        thread_logger.start()

    def on_run_all(self, event):
        """Runs Speaker Recognition"""
        if self.player.video_path == None:
            self.show_alert("Select a file video/audio!", "ERROR!")
        else:
            self.clusters_list.clean_list()
            self.player.colorPanel.clear()
            self.frame.enable_menu(False)
            path = self.player.video_path.replace('"', '')
            self.model.load_video(str(path))
            self.thread_processing = threading.Thread(target=self.model.extract_speakers)
            self.thread_processing.start()
            self.thread_logger = threading.Thread(target=self.log_on_processing)
            self.thread_logger.start()

    def on_run_recognition(self, event):
        """Match clusters"""
        if self.player.video_path == None:
            self.show_alert("Select a file video/audio!", "ERROR!")
        else:
            path = self.player.video_path.replace('"', '')
#            path_basename = str(os.path.basename(str(path)))
#            path_without_ext = os.path.splitext(str(path))[0]
            self.model.load_video(str(path))
            if os.path.exists(self.model.voiceid.get_file_basename() + ".seg") and os.path.exists(self.model.voiceid.get_file_basename() + '.wav'):
                self.clusters_list.clean_list()
                self.player.colorPanel.clear()
                self.frame.enable_menu(False)
                self.thread_processing = threading.Thread(target=self.model.match_clusters)
                self.thread_processing.start()
                self.thread_logger = threading.Thread(target=self.log_on_processing)
                self.thread_logger.start()
            else:
                self.show_alert("You need the wave and seg files", "ERROR!")

    def on_run_diarization(self, event):
        if self.player.video_path == None:
            self.show_alert("Select a file video/audio!", "ERROR!")
        else:
            path = self.player.video_path.replace('"', '')
#            path_basename = str(os.path.basename(str(path)))
#            path_without_ext = os.path.splitext(str(path))[0]
            self.model.load_video(str(path))
            if os.path.exists(self.model.voiceid.get_file_basename() + '.wav'):
                self.clusters_list.clean_list()
                self.player.colorPanel.clear()
                self.frame.enable_menu(False)
                self.thread_processing = threading.Thread(target=self.model.diarization)
                self.thread_processing.start()
                self.thread_logger = threading.Thread(target=self.log_on_processing)
                self.thread_logger.start()
            else:
                self.show_alert("You need the wave files", "ERROR!")

    def update_list(self, msg):
        """Receives data to updates clusters list

        :type msg: Message
        :param msg: text to update list"""
        self.clusters_list.clean_list()
        clusters = self.model.get_clusters()
        clusters_review = []

        for c in clusters.values():
            #print "before name %s, speaker %s, duration %s" % (c.get_name(), c.get_speaker(), c.get_duration())
#            if float(c.get_duration())/100 > 3:
#                clusters_review.append(c)
#        for c in clusters_review:
#            print "after name %s, speaker %s, duration %s" % (c.get_name(), c.get_speaker(), c.get_duration())
            self.clusters_list.add_cluster(c.get_name(), c.get_speaker(), c.get_duration()/100)
        self.player.colorPanel.Refresh()
        #wx.PostEvent(self,wx.EVT_PAINT)

    def update_info_video(self, msg):
        """Receives data to updates video info

        :type msg: Message
        :param msg: text to update video info"""
        text = ""

        try:
            u, k = self.model.get_clusters_info()
            total_seconds = float(self.player.video_length)
            hours = int(total_seconds / 3600)
            minuts = int(total_seconds / 60)
            seconds = int(total_seconds - minuts * 60)
            if len(str(hours)) <2:
                hours = "0"+str(hours)
            if len(str(minuts)) <2:
                minuts = "0"+str(minuts)
            text = "*Video: \n %s \n Length: %s:%s:%s \n\n *Database folder: %s \n\n *Speakers : %s unknown + %s known" % (str(os.path.basename(self.player.video_path)),  str(hours),str(minuts),str(seconds), str(os.path.basename(self.model.get_db())), str(u), str(k))
        except:
            if self.player.video_length != None:
                total_seconds = float(self.player.video_length)
                hours = int(total_seconds / 3600)
                minuts = int(total_seconds / 60)
                seconds = int(total_seconds - minuts * 60)
                if len(str(hours)) <2:
                    hours = "0"+str(hours)
                if len(str(minuts)) <2:
                    minuts = "0"+str(minuts)
                text = "*Video - \n %s \n Length - %s:%s:%s \n\n *Database folder - %s \n\n" % (str(os.path.basename(self.player.video_path)), str(hours),str(minuts),str(seconds), str(os.path.basename(self.model.get_db())))
            else:
                text = "*Database folder: %s \n\n" % str(os.path.basename(self.model.get_db()))
        self.clusters_list.set_info_video(text)

    def on_check_col_clusters_list(self, event):
        """Selects or deselects all checkboxes in clusters list, drawing them"""

        list_items = self.clusters_list.list
        item = list_items.GetColumn(0)
        if item.IsChecked():
            list_items.checked = []
        else:
            for index in range(list_items.GetItemCount()):
                cluster = list_items.GetItem(index, 1)
                if not cluster.GetText() in list_items.checked:
                    list_items.checked.append(cluster.GetText())
        self.draw_selected_clusters()
        self.init_player_seek()

    def on_check_item_clusters_list(self, event):
        """Selects a checkbox, drawing it"""
        list_items = self.clusters_list.list
        cluster = list_items.GetItem(event.m_itemIndex, 1)
        col = list_items.GetColumn(0)
        if cluster.GetText() in list_items.checked:
            if col.IsChecked():
                col.Check(False) #not work
            list_items.checked.remove(cluster.GetText())
        else:
            list_items.checked.append(cluster.GetText())
        self.draw_selected_clusters(event)
        #self.player.colorPanel.Refresh()
        self.init_player_seek()

    def on_edit_cluster(self, event):
        """Sets new name for the edited cluster"""
        list_items = self.clusters_list.list
        cluster = list_items.GetItem(event.m_itemIndex, 1)
        speaker_item = list_items.GetItem(event.m_itemIndex, 0)

        speaker = event.GetText()
        if str(event.GetText()) == "":
            speaker = "unknown"
            speaker_item.SetText("unknown")#not work
        list_items.Refresh()
        list_items.Update()
        self.model.set_cluster(str(cluster.GetText()), str(speaker))

        wx.CallAfter(Publisher.sendMessage, "update_status", "WARNING: Unsaved changes!")

    def init_player_seek(self):
        """Seek video position"""
        if len(self.clusters_list.list.checked) > 0:
            self.on_play_clusters()
        else:
            self.player.on_play(None)

    def draw_selected_clusters(self, event=None):
        """Draws all selected clusters"""
        result = []
        list_items = self.clusters_list.list
        items = list_items.checked
        for c in items:
            cluster = self.model.get_cluster(c)
            color = self.clusters_list.get_color(c)
            for s in cluster._segments:
                result.append((s.get_start(), s.get_end(), color))

        self.frame.Layout()
        wx.CallAfter(self.player.draw_cluster_segs, result, event)



    def get_start_time(self):
        list_items = self.clusters_list.list
        start_time = self.model.get_cluster(list_items.checked[0])._segments[0].get_start()
        for l in list_items.checked:
            c = self.model.get_cluster(l)
            if c._segments[0].get_start() < start_time:
                start_time = c._segments[0].get_start()
        return start_time

    def on_play_clusters(self, event=None):
        """Plays all selected clusters"""
        start_time = self.get_start_time()
        self.player.mpc.Mute(1)
        self.player.mpc.Seek(float(start_time) / 100 , 2)
        self.toggle_pause()
        self.player.mpc.Mute(0)
        self.player.playbackSlider.SetValue(float(start_time) / 100)
        try:
            secsPlayed = self.player.mpc.GetTimePos()
            secsPlayed = time.strftime('%M:%S', time.gmtime(secsPlayed))
            self.player.trackCounter.SetLabel(secsPlayed)
        except:
            "Problems with mpc.GetTimePos()"

    def on_play_segments(self, event):
        """Plays individual segments of all selected clusters"""
        to_secs = 100
        list_items = self.clusters_list.list
        start_time = self.get_start_time()
        items = list_items.checked
        segments = []
        for c in items:
            cluster = self.model.get_cluster(c)
            segments.extend(cluster._segments[:])
        segments = sorted(segments, key=lambda seg: seg._start)
        segments_rev = segments[:]
        segments_rev.reverse()
        offset = self.player.mpc.GetTimePos()
        n = 0
        for s in segments_rev:
            end = float(s.get_end()) / to_secs
            if offset >= end :
                next_ = len(segments) - n
                if  n > 0 :
                    self.toggle_play()
                    start = float(segments[ next_ ].get_start()) / to_secs
                    self.player.mpc.Seek(start, 2)
                else:
                    self.toggle_pause()
                    self.on_play_clusters(event)
                break
            elif offset >= float(s.get_start()) / to_secs:
                break
            elif offset <= float(start_time) / to_secs:
                self.on_play_clusters(event)
                #self.player.on_play(event)
                #self.toggle_play()
                #print "offset <= float(start_time) / 100"
                break
            n += 1

    def toggle_play(self):
        """If player is not running, play it"""
        #wx.CallAfter(Publisher.sendMessage, "update_status", "Train ON ...")
        if not self.player.playbackTimer.IsRunning():
            self.player.mpc.Pause()
            self.player.playbackTimer.Start()

    def toggle_pause(self):
        """If player is running, pause it"""
        #wx.CallAfter(Publisher.sendMessage, "update_status", "Train OFF ...")
        if self.player.playbackTimer.IsRunning():
            self.player.mpc.Pause()
            self.player.playbackTimer.Stop()

    def show_alert(self, text, type):
        dlg = wx.MessageDialog(self.frame, text, type, wx.OK)
        result = dlg.ShowModal()
        dlg.Destroy()

class ClusterForm(wx.Dialog):
    """Build a form to insert the correct speaker name"""
    def __init__(self, parent, title):
        wx.Dialog.__init__(self, parent, 20, title, wx.DefaultPosition, wx.Size(250, 100))
        vbox = wx.BoxSizer(wx.VERTICAL)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        buttonbox = wx.BoxSizer(wx.HORIZONTAL)
        fgs = wx.FlexGridSizer(3, 2, 9, 25)
        title = wx.StaticText(self, label="Speaker")
        self.tc1 = wx.TextCtrl(self, size=(150, 25))
        fgs.AddMany([(title), (self.tc1, 1, wx.EXPAND)])
        fgs.AddGrowableRow(2, 1)
        fgs.AddGrowableCol(1, 1)
        hbox.Add(fgs, flag=wx.ALL | wx.EXPAND, border=15)
        self.b_ok = wx.Button(self, label='Ok', id=OK_DIALOG)
        self.b_cancel = wx.Button(self, label='Cancel', id=CANCEL_DIALOG)
        buttonbox.Add(self.b_ok, 1, border=15)
        buttonbox.Add(self.b_cancel, 1, border=15)
        vbox.Add(hbox, flag=wx.ALIGN_CENTER | wx.ALL | wx.EXPAND)
        vbox.Add(buttonbox, flag=wx.ALIGN_CENTER)
        self.SetSizer(vbox)

class MainFrame(wx.Frame):
    """Builds an external window that acts as a container"""

    def __init__(self):
        if sys.platform == 'win32':
            wx.Frame.__init__(self, None, title="Voiceid Player", size=(950, 600),  style= wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX)
        else:
            wx.Frame.__init__(self, None, title="Voiceid Player", size=(950, 600))
        self._create_menu()
        self.sb = self.CreateStatusBar()
        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Show()

    def _create_menu(self):
        """Creates a menu"""
        menubar = wx.MenuBar()
        fileMenu = wx.Menu()
        srMenu = wx.Menu()
        srSettings = wx.Menu()
        self.add_file_menu_item = fileMenu.Append(wx.NewId(), "&Open video", "Add Media File")
        self.quit_file_menu_item = fileMenu.Append(wx.NewId(), "&Quit", "quit")
        #self.run_menu_item = srMenu.Append(wx.NewId(), "&Run", "Extracts speakers and recognize them")
        self.db_menu_item = srMenu.Append(wx.NewId(), "&Select Db", "Creates new db or select an existing")

        submenu_run = wx.Menu()
        self.all_menu_item = submenu_run.Append(wx.NewId(), 'All', 'Make diarization and match voices', kind=wx.ITEM_NORMAL)
        self.diarization_menu_item = submenu_run.Append(wx.NewId(), 'Diarization', 'Make segmentation file', kind=wx.ITEM_NORMAL)
        self.recognition_menu_item = submenu_run.Append(wx.NewId(), 'Recognition', 'Compare voices with models in the db by loading a seg file', kind=wx.ITEM_NORMAL)

        self.run_menu_item = srMenu.AppendMenu(wx.NewId(), "&Run", submenu_run, "Extracts speakers and recognize them")
        self.save_menu_item = srMenu.Append(wx.NewId(), "&Save ", "Save data in json file")

        submenu_set = wx.Menu()
        self.def_mode_menu_item = submenu_set.Append(MODE_DEFAULT, 'Default', 'Make diarization standard', kind=wx.ITEM_RADIO,)
        self.noise_mode_menu_item = submenu_set.Append(MODE_NOISE, 'Noise', 'Make diarization for video with noise (ex. meetings)', kind=wx.ITEM_RADIO)
        self.mode_menu_item = srSettings.AppendMenu(wx.NewId(), "&Mode", submenu_set, "Chooce different processing mode")

        self.save_menu_item.Enable(False)
        self.run_menu_item.Enable(False)
        self.mode_menu_item.Enable(False)

        menubar.Append(fileMenu, '&File')
        menubar.Append(srMenu, '&Speaker Recognition')
        menubar.Append(srSettings, '&Settings')
        self.SetMenuBar(menubar)

    def set_status_text(self, text):
        """Set text in footer bar"""
        #TODO: set status text
        self.sb.SetStatusText(text)

    def on_size(self, event):
        self.Layout()

    def enable_menu(self, enable):
        self.quit_file_menu_item.Enable(True)
        if enable:
            self.add_file_menu_item.Enable(True)
            self.db_menu_item.Enable(True)
            self.run_menu_item.Enable(True)
            self.db_menu_item.Enable(True)
            self.mode_menu_item.Enable(True)
            self.save_menu_item.Enable(True)
        else:
            self.add_file_menu_item.Enable(False)
            self.db_menu_item.Enable(False)
            self.run_menu_item.Enable(False)
            self.db_menu_item.Enable(False)
            self.mode_menu_item.Enable(False)
            self.save_menu_item.Enable(False)


class Player(wx.Panel):
    """Builds a MpLayerCtrl Player"""

    def __init__(self, parent):
        wx.Panel.__init__(self, parent, -1)
        self.parent = parent
        self.video_length = 0
        self.video_pos = 0
        self.video_path = None
        #self.mpc = mpc.MplayerCtrl(self, 0, u'mplayer', [u'cache', u'1024'])
        self.mpc = wx.Panel(self, -1, size=(400, 300))
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.controlSizer = self.build_player_controls()
        self.sliderSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.colorSizer = wx.BoxSizer(wx.VERTICAL)
        self.playbackSlider = wx.Slider(self, size=wx.DefaultSize)
        self.colorPanel = ColorPanel(self, 99)
        self.colorSizer.Add(self.colorPanel, 1, wx.ALL | wx.EXPAND, 0)
        # create slider
        self.colorSizer.Add(self.playbackSlider, 1, wx.ALL | wx.EXPAND, 0)
        self.sliderSizer.Add(self.colorSizer, 1, wx.ALL | wx.EXPAND, 0)
        # create track counter
        self.trackCounter = wx.StaticText(self, label="00:00")
        self.sliderSizer.Add(self.trackCounter, 0, wx.ALL | wx.CENTER, 5)
        # set up playback timer
        self.playbackTimer = wx.Timer(self)
        self.sizer.Add(self.mpc, 1, wx.EXPAND | wx.ALL, 5)
#        self.sizer.Add(self.colorPanel,0, wx.ALL | wx.EXPAND, 5)
        self.sizer.Add(self.sliderSizer, 0, wx.ALL | wx.EXPAND, 5)
        self.sizer.Add(self.controlSizer, 0, wx.ALL | wx.CENTER, 5)
        # bind buttons to function control
        self.Bind(mpc.EVT_MEDIA_STARTED, self.on_media_started)
        self.Bind(mpc.EVT_MEDIA_FINISHED, self.on_media_finished)
        self.Bind(mpc.EVT_PROCESS_STARTED, self.on_process_started)
        self.Bind(mpc.EVT_PROCESS_STOPPED, self.on_process_stopped)
        self.Bind(wx.EVT_SCROLL_CHANGED, self.update_slider, self.playbackSlider)
        #self.Bind(wx.EVT_PAINT, self.repaint)
        #self.Bind(wx.EVT_SIZE, self.on_size)
        #self.mpc.Bind(wx.EVT_SIZE, self.on_size)
        #self.mpc.Bind(wx.EVT_MAXIMIZE, self.on_size)
        self.SetSizerAndFit(self.sizer)
        self.sizer.Layout()

    def init_objects(self):
        """Resets video info in the player"""
        self.video_length = 0
        self.video_pos = 0
        self.video_path = None

    def draw_cluster_segs(self, segs, event = None):
        """Draws segments of all selected clusters

        :type segs: array
        :param segs: segments info of all selected clusters (seg_start, seg_end, seg_color )"""
        self.colorPanel.clear()
        for s, e, c in segs:
            self.colorPanel.write_slice(float(s) / 100, float(e) / 100, c, event)


    def repaint(self, event):
        """Repaint video ..."""
        try:
            self.mpc.FindFocus()
        except:
            pass

    def update_slider(self, event):
        """Set the playback slider position"""
        self.mpc.Seek(self.playbackSlider.GetValue(), 2)

    def build_btn(self, btnDict, sizer):
        """Builds buttons player"""
        bmp = btnDict['bitmap']
        handler = btnDict['handler']
        img = wx.Bitmap(os.path.join(bitmapDir, bmp))
        btn = buttons.GenBitmapButton(self, bitmap=img,
                                      name=btnDict['name'])
        btn.SetInitialSize()
        btn.Bind(wx.EVT_BUTTON, handler)
        sizer.Add(btn, 0, wx.LEFT, 3)

    def build_player_controls(self):
        """Builds the player bar controls"""
        controlSizer = wx.BoxSizer(wx.HORIZONTAL)
        btnData = [{'bitmap':'backward.png',
                    'handler':self.on_prev, 'name':'prev'},
                   {'bitmap':'pause.png',
                    'handler':self.on_pause, 'name':'pause'},
                   {'bitmap':'play.png',
                    'handler': self.on_play, 'name':'play'},
                    {'bitmap':'forward.png',
                    'handler':self.on_next, 'name':'next'}
                   ]
        for btn in btnData:
            self.build_btn(btn, controlSizer)
        return controlSizer

    def set_video_length(self, length):
        """Set video length"""
        self.video_length = length

    def set_video_path(self, path):
        """Set video path"""
        self.video_path = path

    def load_file(self, path):
        self.init_objects()
        self.set_video_path(path)
        self.video_length = get_length(path)
        path_srt = os.path.splitext(path)[0] + '.srt'
        self.sizer.Detach(self.mpc)
        mplayer = u'mplayer'
        self.mpc = mpc.MplayerCtrl(self, 0, mplayer, mplayer_args=['-sub', path_srt])
        self.sizer.Insert(0, self.mpc, 1, wx.EXPAND | wx.ALL, 5)
        self.sizer.Layout()

    def on_media_started(self, event):
        """Init player"""
        print 'Media started!'
        self.video_length = get_length(self.video_path)
        self.mpc.SetProperty("loop", 0)
        self.mpc.SetProperty("osdlevel", 0)
        r = "%.1f" % round(float(self.video_length), 1)
        self.video_length = float(r)
        self.playbackSlider.SetRange(0, self.video_length)
        self.playbackTimer.Start(100)
        #Pause on start
        if self.playbackTimer.IsRunning():
            self.mpc.Pause()
            self.playbackTimer.Stop()

    def on_media_finished(self, event):
        """Media finished!"""
        print 'Media finished!'
        self.playbackTimer.Start()

    def on_play(self, event):
        """Play video"""
        if not self.playbackTimer.IsRunning():
            #print "playing..."
            self.mpc.Pause()
            self.playbackTimer.Start()

    def on_pause(self, event):
        """Pause video"""
        if self.playbackTimer.IsRunning():
            #print "pausing..."
            self.mpc.Pause()
            self.playbackTimer.Stop()

    def on_process_started(self, event):
        """When process started ..."""
        print 'Process started!'
        self.mpc.Loadfile(self.video_path)

    def on_process_stopped(self, event):
        """When process stopped ..."""
        print 'Process stopped!'

    def on_next(self, event):
        """Forward video of 5 minuts"""
        print "forwarding..."
        self.mpc.Seek(5)

    def on_prev(self, event):
        """Backward video of 5 minuts"""
        print "backwarding..."
        self.mpc.Seek(-5)

    def on_size(self, event):
        """Update player layout"""
        self.mpc.Update()
        self.mpc.Refresh()
        self.mpc.Layout()

class CheckListCtrl(ULC.UltimateListCtrl):
    """Builds a list with checkboxes an editable fields."""
    def __init__(self, parent):
        self.parent = parent
        ULC.UltimateListCtrl.__init__(self, parent , agwStyle=ULC.ULC_AUTO_CHECK_CHILD | ULC.ULC_EDIT_LABELS | ULC.ULC_REPORT | ULC.ULC_SINGLE_SEL | ULC.ULC_VRULES | ULC.ULC_HRULES)
        self.checked = []


class ClustersList(wx.Panel):
    """Builds the cluster's list"""
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, -1, size=(150, 650))
        self.parent = parent
        self.list = CheckListCtrl(self)
        self.info = wx.Panel(self)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.speakers_GRB = {}
        self.buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.buttons_sizer.ShowItems(False)
        self.info.text_info = wx.StaticText(self.info, 1, "")
        sb_list = wx.StaticBox(self, label=" Speakers ")
        sb_info = wx.StaticBox(self, label=" Info ")
        if sys.platform != 'darwin':
            self.boxsizer_list = wx.StaticBoxSizer(sb_list, wx.VERTICAL)
            self.boxsizer_list.Add(self.list, 5, wx.EXPAND | wx.EXPAND, 2)
        self.boxsizer_info = wx.StaticBoxSizer(sb_info, wx.VERTICAL)
        self.boxsizer_info.Add(self.info, 5, wx.EXPAND | wx.ALL, 2)
        first = ULC.UltimateListItem()
        first._mask = wx.LIST_MASK_TEXT | wx.LIST_MASK_FORMAT | ULC.ULC_MASK_CHECK
        first._kind = 1
        first._text = 'Speaker'
        first._font = wx.Font(13, wx.ROMAN, wx.NORMAL, wx.BOLD)
        if sys.platform == 'win32':
            first.SetWidth(150)
        else:
            first.SetWidth(wx.LIST_AUTOSIZE_USEHEADER)
        self.list.InsertColumnInfo(0, first)
        second = ULC.UltimateListItem()
        second._mask = wx.LIST_MASK_TEXT | wx.LIST_MASK_FORMAT
        second._text = 'Cluster'
        second.SetWidth(wx.LIST_AUTOSIZE_USEHEADER)
        self.list.InsertColumnInfo(1, second)
        self.list.InsertColumn(2, '', wx.LIST_AUTOSIZE_USEHEADER)
        fourty = ULC.UltimateListItem()
        fourty._mask = wx.LIST_MASK_TEXT | wx.LIST_MASK_FORMAT
        fourty._text = 'Length'
        fourty.SetWidth(wx.LIST_AUTOSIZE_USEHEADER)
        self.list.InsertColumnInfo(3, fourty)
        self.list.SetBackgroundColour("white")
        self.Bind(wx.EVT_SIZE, self.on_size)
        self.info.Bind(wx.EVT_SIZE, self.on_size)
        self.list.Bind(wx.EVT_SIZE, self.on_size)
        self.list.Bind(wx.EVT_MOTION, self.on_mouse_over)
        self.columns = 0
        self.sizer.Add(self.boxsizer_info, 2, wx.EXPAND | wx.ALL, 2)
        if sys.platform != 'darwin':
            self.sizer.Add(self.boxsizer_list, 5, wx.EXPAND | wx.ALL, 2)
        else:
            self.sizer.Add(self.list, 5, wx.EXPAND | wx.ALL, 2)
        self.SetSizer(self.sizer)
        self.sizer.Layout()

    def add_cluster(self, cluster_label, cluster_speaker, length):
        """Add a new cluster item in list

        :type cluster_label: string
        :type cluster_speaker: string
        :param cluster_label: cluster identifier  ( S0, S1 ...)
        :param cluster_speaker: speaker name"""
        import random
        def randomColor():
            return (int(random.random() * 255), int(random.random() * 255), int(random.random() * 255))
        color = randomColor()
        while color in self.speakers_GRB.keys():
            color = randomColor()
        self.speakers_GRB[cluster_label] = color
        secs = time.strftime('%M:%S', time.gmtime(length))
        data = {self.columns : (cluster_speaker, cluster_label, "", secs)}
        for key, d in data.items():
            index = self.list.Append(d)
            self.list.SetItemData(index, key)
        item2 = self.list.GetItem(self.columns, 2)
        item1 = self.list.GetItem(self.columns, 0)

        item2.SetMask(ULC.ULC_MASK_BACKCOLOUR)
        item2.SetBackgroundColour(wx.Colour(color[0], color[1], color[2]))
        self.list.SetItem(item2)
        self.list.SetItemKind(item1, 0, 1)
        self.columns += 1

    def clean_list(self):
        """Resets list objects"""
        self.speakers_GRB = {}
        self.columns = 0
        self.list.SetFocus()
        self.list.DeleteAllItems()
        self.list.checked = []

    def clean_info(self):
        self.set_info_video("")

    def set_info_video(self, text):
        """Set info video

        :type text: string
        :param text: info video as title and extracted speakers"""
        self.info.text_info.SetLabel(text)

    def get_color(self, speaker):
        """Return related speaker's color

        :type speaker: string
        :param speaker: speaker name"""
        return self.speakers_GRB[speaker]

    def on_size(self, event):
        """Update layouts on size event"""
        self.list.Refresh()
        self.list.Layout()
        self.info.Refresh()
        self.info.Layout()
        self.Refresh()
        self.Layout()

    def on_mouse_over(self, event):
        pass

class ColorPanel(wx.Panel):
    """Draws a graphical representation of clusters"""

    def __init__(self, parent, myid):
        wx.Panel.__init__(self, parent, myid)
        # start the paint event for DrawRectangle() and FloodFill()
        self.parent = parent


    def clear(self):
        """Clear all"""
        self.dc = wx.ClientDC(self)
        self.dc.Clear()
        #del self.dc

    def write_slice(self, start_time, end_time, color, event=None):
        """Calculates area to draw the segment

        :type start_time: float
        :param start_time: segment start time
        :type end_time: float
        :param end_time: segment end time
        :type color: string
        :param color: the color to be used to draw the segment"""

        width = self.GetSizeTuple()[0] - 5
        time_l = self.parent.video_length
        pixel4sec = float(width) / float(time_l)
        duration = end_time - start_time
        w = duration * pixel4sec
        if w < 1:
            w = 1
        self._write_rectangle(start_time * pixel4sec, 10 , w, 10, color, event)

    def _write_rectangle(self, x, y, w, h, color, event=None):
        """Draw a specific area

        :type x: float
        :param x: x-axis to start drawing
        :type y: float
        :param y: y-axis to start drawing
        :type w: float
        :param w: width area to draw
        :type h: float
        :param h: height area to draw
        :type color: string
        :param color: color to draw rectangle area"""
        self.dc = wx.ClientDC(self)
        self.dc.BeginDrawing()
        self.dc.SetPen(wx.Pen("BLACK", 1))
        # draw a few colorful rectangles ...
        self.dc.SetBrush(wx.Brush(color, wx.SOLID))
        self.dc.DrawRectangle(x, y, w, h)
        self.dc.EndDrawing()
        # free up the device context now
        del self.dc

class ClusterInfo():
    pass

class Model:
    """Model manage all data"""

    def __init__(self):
        global dbDir
        self.voiceid = None
        self.db = db.GMMVoiceDB(dbDir)
        self._clusters = None
        self.mode = 0
        self.json = None

    def load_video(self, video_path):
        """Init Voiceid object

        :type video_path: string
        :param video_path: video path"""
        self.voiceid = sr.Voiceid(self.db, video_path)
        self.video = video_path


    def load_json(self, json_path):
        """Init Voiceid object with json file

        :type json_path: string
        :param json_path: json path"""
#         print json_path
	try:
            opf = open(json_path, 'r')
            jdict = eval(opf.read())
            opf.close()
            db = jdict['db']
            self.set_db(db)
        except:
            print "Json error"

        try:
            opf = open(json_path, 'r')
            jdict = eval(opf.read())
            opf.close()
            db = jdict['db']
            self.set_db(db)
        except:
            print "Json error"
        try:
            self.voiceid = sr.Voiceid.from_json_file(self.db, json_path)
        except:
            print "Json file not found!"
        self.voiceid._automerge_segments()  # experimental
        self._clusters = self.voiceid.get_clusters()
        self.json = json_path

    def set_mode(self, mode):
        """
        Set diarization mode between a default configuration and a configuration for noisy video

        :type mode: integer
        :param mode: 1 ->Default conf | 2->Noisy video conf
        """
        self.mode = mode

    def extract_speakers(self):
        """Extracts speakers"""
        self.voiceid.set_noise_mode(self.mode)
        self.voiceid.extract_speakers(False, False, 4)
        self.voiceid._automerge_segments()  # experimental
        self._clusters = self.voiceid.get_clusters()
        #self.voiceid._verify_duration()

    def match_clusters(self):
        """Match clusters"""
        self.load_json(self.json)
#         self.voiceid.generate_seg_file(set_speakers=False)
        self.voiceid._to_trim()
        self.voiceid._cluster_matching(thrd_n=4)
        self.voiceid._automerge_segments()  # experimental
        self._clusters = self.voiceid.get_clusters()


    def diarization(self):
        #self.voiceid.Set
        self.voiceid.diarization()
        self.voiceid._extract_clusters()
        self.voiceid._automerge_segments()  # experimental
        self._clusters = self.voiceid.get_clusters()

    def get_status(self):
        """Return step number status"""
        return self.voiceid.get_status()

    def get_map_status(self):
        """Return step status"""
        return self.voiceid.status_map[self.voiceid.get_status()]

    def get_working_status(self):
        """Return current step status"""
        return self.voiceid.get_working_status()

    def get_clusters(self):
        """Return all clusters"""
        return self.voiceid.get_clusters()

    def get_clusters_info(self):
        """Return the number of unknown and known speakers"""
        unknown = 0
        known = 0
        if self._clusters and len(self._clusters) > 0:
            for c in self._clusters:
                if self._clusters[c].get_speaker() == 'unknown':
                    unknown += 1
                else:
                    known += 1
            return unknown, known
        else:
            raise "Not clusters found!"

    def get_cluster(self, label):
        """Return specific cluster

        :type label: string
        :param label: cluster identifier"""
        return self._clusters[label]

    def set_cluster(self, cluster_label, cluster_speaker):
        """Set speaker name for a specific cluster

        :type cluster_label: string
        :param cluster_label: label that identifies a cluster (ex. S0, S1 ... )
        :type cluster_speaker: string
        :param cluster_speaker: speaker represented by the specific cluster (ex. MarioMonti ... )"""
        cluster_speaker = cluster_speaker.strip()
        c = self._clusters[cluster_label]
        c.set_speaker(cluster_speaker)

    def save_changes(self):

        """Save all changes in the JSON file and database"""
        cl = self.voiceid.get_clusters()
        self.voiceid.update_db(1)
        self.voiceid.write_output("json")
        trackPath = '"%s"' % self.video.replace("\\", "/")
        json_path = os.path.splitext(trackPath)[0] + '.json'
        json_path = json_path.replace('"', '')
        if os.path.exists(json_path):
            self.json = json_path
        else:
            print "JSON file not saved"
        self.voiceid.write_output("srt")
        self._clusters = self.voiceid.get_clusters()

    def set_db(self, db_path):
        """Init db object

        :type db_path: string
        :param db_path: database location"""
        self.db = db.GMMVoiceDB(str(db_path))

    def get_db(self):
        """Init db object"""
        return self.db.get_path()

class App(wx.App):
    """Init Application object"""
    def __init__(self, *args, **kwargs):
        wx.App.__init__(self, *args[1:], **kwargs)
        cl_args = None
        if len(args) >=1:
            cl_args = args[0]
        print cl_args
        self.controller = Controller(self, cl_args)


    def OnExit(self):
        pass
        #self.controller.exit_()

if __name__ == "__main__":
    app = App(sys.argv, redirect=False)
    app.MainLoop()
