__author__ = 'chrismellinger'

# experiment with wxPython's
# wx.media.MediaCtrl(parent, id, pos, size, style, backend)
# the backend (szBackend) is usually figured by the control
# wxMEDIABACKEND_DIRECTSHOW   Windows
# wxMEDIABACKEND_QUICKTIME    Mac OS X
# wxMEDIABACKEND_GSTREAMER    Linux (?)
# plays files with extension .mid .mp3 .wav .au .avi .mpg
# tested with Python24 and wxPython26 on Windows XP   vegaseat  10mar2006
import wx
import wx.media
import wx.lib.mixins.listctrl  as  listmix
import os
import SpeakingCode


class InoutListCtrl(wx.ListCtrl, listmix.ListCtrlAutoWidthMixin):
    def __init__(self, parent, ID, pos=wx.DefaultPosition,
                 size=wx.DefaultSize, style=0):
        wx.ListCtrl.__init__(self, parent, ID, pos, size, style)
        listmix.ListCtrlAutoWidthMixin.__init__(self)

    def Select(self, idx, on):
        wx.ListCtrl.Select(self, idx=idx, on=on)
        if on:
            wx.ListCtrl.EnsureVisible(self, idx)


class LEDPanel(wx.Panel):
    def __init__(self, parent, id, color):
        wx.Panel.__init__(self, parent, id, size=(20, 20))

        self.curColor = color

        self.Bind(wx.EVT_PAINT, self.onPaint)

    def onPaint(self, evt):
        dc = wx.PaintDC(self)
        dc.Clear()
        dc.SetBrush(wx.Brush(self.curColor))
        dc.DrawCircle(10, 10, 7)

    def changeLED(self, newColor):
        self.curColor = newColor
        self.Refresh()


class Panel1(wx.Panel):
    def __init__(self, parent, id):
        #self.log = log
        wx.Panel.__init__(self, parent, -1, style=wx.TAB_TRAVERSAL|wx.CLIP_CHILDREN)
        # Create some controls
        try:
            self.mc = wx.media.MediaCtrl(self, style=wx.SIMPLE_BORDER)
        except NotImplementedError:
            self.Destroy()
            raise

        self.checkpointflag = False
        self.codeBank = None
        self.clusterBank = None
        self.checkclusterpointflag = False
        self.needToSaveFlag = False
        self.currentDataFile = None
        self.lightOn = False
        self.inOutSelectFlag = True
        self.clusterSelectFlag = True
        # This self.click flag tells us whether or not the selection was the result of a click.
        # Any call to a list.Select() method should set this flag to False first, unless the selection event should
        # be treated as a click (i.e., it should cause the video to seek).
        self.click = True
        self.LEDColors = {
            True:'Red',
            False:'Black'
                          }

        #Take care of the focus issue:
        self.Bind(wx.EVT_KILL_FOCUS, self.giveBackFocus)

        # Make the LED light panel:
        self.Light = LEDPanel(self, -1, 'White')

        # Create the speaker list control and set it up:
        self.InOutList = InoutListCtrl(self, -1, style=wx.LC_REPORT
                                 | wx.BORDER_SUNKEN
                                 #| wx.BORDER_NONE
                                 | wx.LC_EDIT_LABELS
                                 | wx.LC_SORT_ASCENDING
                                 #| wx.LC_NO_HEADER
                                 #| wx.LC_VRULES
                                 #| wx.LC_HRULES
                                 #| wx.LC_SINGLE_SEL
                                 )
        self.InOutList.InsertColumn(0, "In")
        self.InOutList.InsertColumn(1, "Out")
        #self.Bind(wx.EVT_LIST_DELETE_ITEM, self.OnListItemDelete, self.InOutList)
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.onInOutItemSelected, self.InOutList)

        # Create the cluster list control and set it up:
        self.ClusterList = InoutListCtrl(self, -1, style=wx.LC_REPORT
                                 | wx.BORDER_SUNKEN
                                 #| wx.BORDER_NONE
                                 | wx.LC_EDIT_LABELS
                                 | wx.LC_SORT_ASCENDING
                                 #| wx.LC_NO_HEADER
                                 #| wx.LC_VRULES
                                 #| wx.LC_HRULES
                                 #| wx.LC_SINGLE_SEL
                                 )
        self.ClusterList.InsertColumn(0, "In")
        self.ClusterList.InsertColumn(1, "Out")
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.onClusterItemSelected, self.ClusterList)

        # Here's the drop down for selecting a cluster:
        self.clusterChoice = wx.Choice(self, -1, style=wx.CB_SORT)
        self.Bind(wx.EVT_CHOICE, self.onClusterChoice, self.clusterChoice)

        # Time for checking the video position:
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onTimer)
        self.timer.Start(100)

        # Buttons!

        deleteListItemButton = wx.Button(self, -1, "Remove Point")
        self.Bind(wx.EVT_BUTTON, self.OnListItemDelete, deleteListItemButton)

        loadVideoButton = wx.Button(self, -1, "Load Video File", size=(120, 20))
        self.Bind(wx.EVT_BUTTON, self.onLoadVideoFile, loadVideoButton)

        self.loadDataButton = wx.Button(self, -1, "Load Data File", (120, 20))
        self.Bind(wx.EVT_BUTTON, self.onLoadDataFile, self.loadDataButton)
        self.loadDataButton.Disable()

        loadSegFile = wx.Button(self, -1, "Load .seg File")
        self.Bind(wx.EVT_BUTTON, self.loadSegFile, loadSegFile)

        renderData = wx.Button(self, -1, "Render Data")
        self.Bind(wx.EVT_BUTTON, self.renderData, renderData)
        renderData.Disable()

        makeNewCodeBankButton = wx.Button(self, -1, "New Data Object")
        self.Bind(wx.EVT_BUTTON, self.onNewCodeBank, makeNewCodeBankButton)

        saveCodeBankButton = wx.Button(self, -1, "Save Data")
        self.Bind(wx.EVT_BUTTON, self.saveCodes, saveCodeBankButton)

        saveCodeBankAsButton = wx.Button(self, -1, "Save Data As")
        self.Bind(wx.EVT_BUTTON, self.onSaveDataAs, saveCodeBankAsButton)

        playPauseButton = wx.Button(self, -1, "Play/Pause")
        self.Bind(wx.EVT_BUTTON, self.onPlayPause, playPauseButton)

        stopButton = wx.Button(self, -1, "Stop")
        self.Bind(wx.EVT_BUTTON, self.onStop, stopButton)

        jump1ForwardButton = wx.Button(self, -1, "2x", size=(55, 20))
        self.Bind(wx.EVT_BUTTON, self.playFaster, jump1ForwardButton)

        jump1BackwardButton = wx.Button(self, -1, ".5x", size=(55, 20))
        self.Bind(wx.EVT_BUTTON, self.playSlower, jump1BackwardButton)

        jump2ForwardButton = wx.Button(self, -1, "2>>", size=(55, 20))
        self.Bind(wx.EVT_BUTTON, self.jumpButton, jump2ForwardButton)

        jump2BackwardButton = wx.Button(self, -1, "<<2", size=(55, 20))
        self.Bind(wx.EVT_BUTTON, self.jumpButton, jump2BackwardButton)

        setInPoint = wx.Button(self, -1, "In", size=(55, 20))
        self.Bind(wx.EVT_BUTTON, self.setInPoint, setInPoint)

        setOutPoint = wx.Button(self, -1, "Out", size=(55, 20))
        self.Bind(wx.EVT_BUTTON, self.setOutPoint, setOutPoint)

        nextSpeakerPoint = wx.Button(self, -1, "Next Point")
        self.Bind(wx.EVT_BUTTON, self.nextSpeakerPoint, nextSpeakerPoint)

        prevSpeakerPoint = wx.Button(self, -1, "Previous Point")
        self.Bind(wx.EVT_BUTTON, self.prevSpeakerPoint, prevSpeakerPoint)

        nextClusterPoint = wx.Button(self, -1, "Next Point")
        self.Bind(wx.EVT_BUTTON, self.nextClusterPoint, nextClusterPoint)

        prevClusterPoint = wx.Button(self, -1, "Previous Point")
        self.Bind(wx.EVT_BUTTON, self.prevClusterPoint, prevClusterPoint)

        changePointSpeaker = wx.Button(self, -1, "Change Point Speaker")
        self.Bind(wx.EVT_BUTTON, self.changePointSpeaker, changePointSpeaker)

        copyPointToSpeaker = wx.Button(self, -1, "Copy Point to Speaker")
        self.Bind(wx.EVT_BUTTON, self.copyPointToSpeaker, copyPointToSpeaker)

        copyAllPointsToSpeaker = wx.Button(self, -1, "Copy All Points to Speaker")
        self.Bind(wx.EVT_BUTTON, self.copyAllPointsToSpeaker, copyAllPointsToSpeaker)

        #loadTestVid = wx.Button(self, -1, "Load Test Video")
        #self.Bind(wx.EVT_BUTTON, self.loadTestVideo, loadTestVid)

        slider = wx.Slider(self, -1, 0, 0, 0, size=wx.Size(300, -1))
        self.slider = slider
        self.Bind(wx.EVT_SLIDER, self.onSeek, slider)

        self.Bind(wx.EVT_CHAR_HOOK, self.char)
        #self.mc.Bind(wx.EVT_CHAR, self.char)

        self.actiondictionary = {
            72:self.onJump,
            74:self.playSlower,
            75:self.onPlayPause,
            76:self.playFaster,
            59:self.onJump,
            77:self.onStop,
            73:self.setInPoint,
            79:self.setOutPoint,
            13:self.addTimeCode,
            49:self.changeSpeaker,
            50:self.changeSpeaker,
            51:self.changeSpeaker,
            52:self.changeSpeaker,
            53:self.changeSpeaker,
            54:self.changeSpeaker,
            55:self.changeSpeaker,
            56:self.changeSpeaker,
            57:self.changeSpeaker,
            83:self.saveCodes,
            #114:self.changeLEDColor,
            #116:self.changeLEDColor,
        }

        self.jumpButtonValues = {
            jump1ForwardButton.GetId():1000,
            jump1BackwardButton.GetId():-1000,
            jump2ForwardButton.GetId():2000,
            jump2BackwardButton.GetId():-2000
        }

        self.jumpValues = {
            72:-2000,
            74:-1000,
            76:1000,
            59:2000
        }

        self.st_pos  = wx.StaticText(self, -1, "stop", size=(100,-1))
        self.in_point_txt = wx.StaticText(self, -1, "none")
        self.out_point_txt = wx.StaticText(self, -1, "none")
        self.speaker = wx.StaticText(self, -1, "Speaker")
        self.currentSpeakerNumber = wx.StaticText(self, -1, "none")
        self.clusterTxt = wx.StaticText(self, -1, "Cluster")
        self.needToSaveText = wx.StaticText(self, -1, "")

        # setup the button/label layout using sizers
        #vs00 = wx.BoxSizer(wx.HORIZONTAL)
        hs00 = wx.BoxSizer(wx.HORIZONTAL)

        # Left hand side that will hold the listcontrols and buttons for traversing them.
        vs01 = wx.BoxSizer(wx.VERTICAL)
        hs00.Add(vs01, 0)
        vs01.Add(self.speaker, 0, wx.ALIGN_LEFT)
        vs01.Add(self.currentSpeakerNumber, 0, wx.ALIGN_LEFT)
        vs01.Add(self.InOutList, 0, wx.EXPAND)
        hs01 = wx.BoxSizer(wx.HORIZONTAL)
        vs01.Add(hs01, 0, wx.EXPAND)
        hs01.Add((0, 0), 1)
        hs01.Add(nextSpeakerPoint, 0, wx.ALIGN_CENTER)
        hs01.Add((0, 0), 1)
        hs01.Add(prevSpeakerPoint, 0, wx.ALIGN_CENTER)
        hs01.Add((0, 0), 1)
        vs01.Add((0, 0), 1)
        vs01.Add(changePointSpeaker, 0, wx.ALIGN_CENTER)
        vs01.Add((0, 0), 1)
        vs01.Add(deleteListItemButton, 0, wx.ALIGN_CENTER)
        vs01.Add((60, 30), 1)
        vs01.Add(self.clusterTxt, 0, wx.ALIGN_LEFT)
        vs01.Add((0, 0), 1)
        vs01.Add(self.clusterChoice, 0, wx.ALIGN_LEFT)
        vs01.Add((0, 0), 1)
        vs01.Add(self.ClusterList, 0, wx.EXPAND)
        hs02 = wx.BoxSizer(wx.HORIZONTAL)
        hs02.Add((0, 0), 1)
        hs02.Add(nextClusterPoint, 0, wx.ALIGN_CENTER)
        hs02.Add((0, 0), 1)
        hs02.Add(prevClusterPoint, 0, wx.ALIGN_CENTER)
        hs02.Add((0, 0), 1)
        vs01.Add(hs02, 0, wx.EXPAND)
        vs01.Add((0, 0), 1)
        vs01.Add(copyPointToSpeaker, 0, wx.ALIGN_CENTER)
        vs01.Add((0, 0), 1)
        vs01.Add(copyAllPointsToSpeaker, 0, wx.ALIGN_CENTER)
        vs01.Add((0, 0), 1)

        # The middle column will hold the video and control buttons:
        vs02 = wx.BoxSizer(wx.VERTICAL)
        hs00.Add(vs02, 1, wx.EXPAND)
        hs03 = wx.BoxSizer(wx.HORIZONTAL)
        vs02.Add(hs03, 0, wx.EXPAND)
        hs03.Add(self.needToSaveText, 0, wx.EXPAND | wx.ALIGN_LEFT)
        hs03.Add((0, 0), 1)
        hs03.Add(loadVideoButton, 0, wx.EXPAND | wx.ALIGN_RIGHT)
        #hs03.Add((0, 0), 1)
        #hs03.Add(loadTestVid, 0, wx.ALIGN_RIGHT)
        vs02.Add(self.mc, 1, wx.EXPAND)
        vs02.Add(slider, 0, wx.EXPAND)
        hs04 = wx.BoxSizer(wx.HORIZONTAL)
        vs02.Add(hs04, 0, wx.EXPAND)
        hs04.Add((0, 0), 1)
        hs04.Add(setInPoint, 0, wx.ALIGN_CENTER)
        hs04.Add((0, 0), 1)
        hs04.Add(self.in_point_txt, 0, wx.ALIGN_CENTER)
        hs04.Add((0, 0), 1)
        hs04.Add(self.Light, 0, wx.ALIGN_CENTER)
        hs04.Add((0, 0), 1)
        hs04.Add(setOutPoint, 0, wx.ALIGN_CENTER)
        hs04.Add((0, 0), 1)
        hs04.Add(self.out_point_txt, 0, wx.ALIGN_CENTER)
        hs04.Add((0, 0), 1)
        hs05 = wx.BoxSizer(wx.HORIZONTAL)
        vs02.Add(hs05, 0, wx.EXPAND)
        hs05.Add((0, 0), 1)
        hs05.Add(stopButton, 0, wx.ALIGN_CENTER)
        hs05.Add((0, 0), 1)
        hs05.Add(jump2BackwardButton, 0, wx.ALIGN_CENTER)
        hs05.Add((0, 0), 1)
        hs05.Add(jump1BackwardButton, 0, wx.ALIGN_CENTER)
        hs05.Add((0, 0), 1)
        hs05.Add(playPauseButton, 0, wx.ALIGN_CENTER)
        hs05.Add((0, 0), 1)
        hs05.Add(jump1ForwardButton, 0, wx.ALIGN_CENTER)
        hs05.Add((0, 0), 1)
        hs05.Add(jump2ForwardButton, 0, wx.ALIGN_CENTER)
        hs05.Add((0, 0), 1)
        vs02.Add(self.st_pos, 0, wx.ALIGN_LEFT)

        # The third column will contain most load and save buttons:
        vs03 = wx.BoxSizer(wx.VERTICAL)
        hs00.Add(vs03, 0)
        vs03.Add(saveCodeBankButton, 0, wx.ALIGN_CENTER)
        vs03.Add((60, 10), 0, wx.EXPAND)
        vs03.Add(saveCodeBankAsButton, 0, wx.ALIGN_CENTER)
        vs03.Add((60, 10), 0, wx.EXPAND)
        vs03.Add(makeNewCodeBankButton, 0, wx.ALIGN_CENTER)
        vs03.Add((60, 10), 0, wx.EXPAND)
        vs03.Add(self.loadDataButton, 0, wx.ALIGN_CENTER)
        vs03.Add((60, 20), 0, wx.EXPAND)
        vs03.Add(loadSegFile, 0, wx.ALIGN_CENTER)
        vs03.Add((60, 10), 0, wx.EXPAND)
        vs03.Add(renderData, 0, wx.ALIGN_CENTER)

        # sizer = wx.GridBagSizer(10, 10)
        # sizer.Add(deleteListItemButton, (8, 1))
        # sizer.Add(loadVideoButton, (2, 9))
        # sizer.Add(self.loadDataButton, (5, 9))
        # sizer.Add(makeNewCodeBankButton, (4, 9))
        # sizer.Add(saveCodeBankButton, (3, 9))
        # sizer.Add(saveCodeBankAsButton, (9, 9))
        # sizer.Add(self.currentSpeakerNumber, (2, 1))
        # sizer.Add(self.speaker, (1, 1))
        # sizer.Add(playPauseButton, (8, 5))
        # sizer.Add(stopButton, (8, 2))
        # sizer.Add(jump1ForwardButton, (8, 6))
        # sizer.Add(jump2ForwardButton, (8, 7))
        # sizer.Add(jump1BackwardButton, (8, 4))
        # sizer.Add(jump2BackwardButton, (8, 3))
        # sizer.Add(goToStartButton, (5, 1))
        # sizer.Add(goToEndButton, (6, 1))
        # sizer.Add(setInPoint, (7, 2))
        # sizer.Add(setOutPoint, (7, 6))
        # sizer.Add(self.in_point_txt, (7, 3))
        # sizer.Add(self.out_point_txt, (7, 7))
        # # sizer.Add(self.st_file, (1, 2))
        # # sizer.Add(self.st_size, (2, 2))
        # # sizer.Add(self.st_len,  (3, 2))
        # sizer.Add(self.st_pos,  (7, 1))
        # sizer.Add(self.needToSaveText, (1, 2))
        # sizer.Add(self.mc, (2, 2), span=(4, 7))  # for .avi .mpg video files
        # sizer.Add(self.slider, (6, 2), span=(1, 7))
        # sizer.Add(self.Light, (7, 5))
        # sizer.Add(self.InOutList, (3, 1))

        self.SetSizer(hs00)

        # some stuff to record times
        self.p1 = []
        self.p2 = []
        self.p3 = []
        self.p4 = []

        self.currentIn = None
        self.currentOut = None

    def nextPoint(self, ctrl):
        """
        Selects the next item in a list and unselects everything else. If more than one item is selected,
        it treats the first item as the currently selected item.
        :param ctrl: The listctrl (or listview) object to work on
        """
        selected = ctrl.GetFirstSelected()
        if selected >= 0:
            next = selected + 1

            while selected >= 0:
                ctrl.Select(selected, on=False)
                selected = ctrl.GetNextSelected(selected)

            if next <= ctrl.GetItemCount() - 1:
                ctrl.Select(next, on=True)

            else:
                ctrl.Select(0, on=True)

        else:
            ctrl.Select(0, on=True)

    def prevPoint(self, ctrl):
        """
        Selects the previous item in a list and unselects everything else. If more than one item is selected,
        it treats the first item as the currently selected item.
        :param ctrl: The listctrl (or listview) object to work on
        """
        selected = ctrl.GetFirstSelected()
        if selected >= 0:
            prev = selected - 1

            ctrl.Select(selected, on=False)
            while selected >= 0:
                ctrl.Select(selected, on=False)
                selected = ctrl.GetNextSelected(selected)

            if prev >= 0:
                ctrl.Select(prev, on=True)

            else:
                last = ctrl.GetItemCount() - 1
                ctrl.Select(last, on=True)

        else:
            ctrl.Select(0, on=True)

    def nextSpeakerPoint(self, evt):
        self.nextPoint(self.InOutList)

    def prevSpeakerPoint(self, evt):
        self.prevPoint(self.InOutList)

    def nextClusterPoint(self, evt):
        self.nextPoint(self.ClusterList)

    def prevClusterPoint(self, evt):
        self.prevPoint(self.ClusterList)

    def changePointSpeaker(self, evt):
        if self.InOutList.GetSelectedItemCount() > 0:
            point = (
                int(self.InOutList.GetItemText(self.InOutList.GetFirstSelected(), col=0)),
                int(self.InOutList.GetItemText(self.InOutList.GetFirstSelected(), col=1))
            )

            speakers=[]
            for i in range(1, self.codeBank.numSpeakers+1):
                speakers.append(str(i))

            dlg = wx.SingleChoiceDialog(
                self, "Which speaker should this point belong to?", "Change Speaker",
                speakers, wx.CHOICEDLG_STYLE
            )

            if dlg.ShowModal() == wx.ID_OK:
                self.codeBank.removeinout(point)
                newSpeak = int(dlg.GetStringSelection())
                self.codeBank.changecurrentspeaker(newSpeak)
                self.addPoint(point)
                self.refreshThings()

                # Select the point so it's obvious:
                i = self.InOutList.FindItem(-1, str(point[0]))
                self.InOutList.Select(i, on=True)

    def copyPointToSpeaker(self, evt):
        if self.codeBank is not None:
            item = self.ClusterList.GetFirstSelected()
            while item >= 0:
                pt = (int(self.ClusterList.GetItemText(item, col=0)), int(self.ClusterList.GetItemText(item, col=1)))
                self.addPoint(pt)
                item = self.ClusterList.GetNextSelected(item)
            self.refreshThings()

    def copyAllPointsToSpeaker(self, evt):
        if self.codeBank is not None:
            for item in range(self.ClusterList.GetItemCount()):
                pt = (int(self.ClusterList.GetItemText(item, col=0)), int(self.ClusterList.GetItemText(item, col=1)))
                self.addPoint(pt)
            self.refreshThings()

    def loadSegFile(self, evt):

        dlg = wx.FileDialog(self, message="Choose a .seg file",
                            defaultDir=os.getcwd(), defaultFile="",
                            style=wx.OPEN | wx.CHANGE_DIR, wildcard = "*.seg")
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            self.doLoadSegFile(path)

        dlg.Destroy()

    def doLoadSegFile(self, path):
        self.clusterBank = SpeakingCode.SpeakingCodes(self.mc.Length())
        self.clusterBank.loadsegfile(path)
        self.currentCluster = self.clusterBank.currentSpeaker
        self.checkclusterpointflag = True
        self.reloadClusterChoice()
        self.reloadClusterList()
        self.checkclusterpointflag = True # Tells the timer to check the cluster list points

    def reloadClusterChoice(self):
        self.clusterChoice.Clear()
        items = []
        for c in range(1, self.clusterBank.numSpeakers+1):
            items.append(self.clusterBank.speakerDescriptions[c])
        items.sort()
        self.clusterChoice.AppendItems(items)
        curCluster = self.clusterBank.speakerDescriptions[self.clusterBank.currentSpeaker]
        i = self.clusterChoice.FindString(curCluster)
        self.clusterChoice.SetSelection(i)

    def renderData(self, evt):
        pass
    
    def onClusterChoice(self, evt):
        i = self.clusterChoice.GetCurrentSelection()
        item = self.clusterChoice.GetString(i)
        newCluster = self.clusterBank.invSpeakDesc[item]
        self.clusterBank.currentSpeaker = newCluster
        self.currentCluster = newCluster
        self.reloadClusterList()

    def onKeyDown(self, evt):
        #print evt
        if evt == wx.WXK_SPACE:
            self.setInPoint(evt)
            print "space"

        evt.Skip()

    def onKeyUp(self, evt):
        if evt == wx.WXK_SPACE:
            self.setOutPoint(evt)

        evt.Skip()

    def onGoToStartButton(self, evt):
        s = self.InOutList.GetFirstSelected()
        if s > -1:
            pos = int(self.InOutList.GetItemText(s, col=0))
            self.mc.Seek(pos)
            #self.InOutList.SetItemState(s, 0, wx.LIST_STATE_SELECTED)

    def onGoToEndButton(self, evt):
        s = self.InOutList.GetFirstSelected()
        if s > -1:
            pos = int(self.InOutList.GetItemText(s, col=1))
            self.mc.Seek(pos)
            #self.InOutList.SetItemState(s, 0, wx.LIST_STATE_SELECTED)

    def OnListItemDelete(self, evt):
        #selectedcount = self.InOutList.GetSelectedItemCount()
        item = self.InOutList.GetFirstSelected()
        while item >= 0:
            nitem = self.InOutList.GetNextSelected(item)
            code = (int(self.InOutList.GetItemText(item, col=0)), int(self.InOutList.GetItemText(item, col=1)))
            self.codeBank.removeinout(code)
            #self.InOutList.SetItemState(s, 0, wx.LIST_STATE_SELECTED)
            self.InOutList.DeleteItem(item)
            item = nitem

        self.needToSave(True)

    def changeSpeaker(self, evt):
        s = evt - 48
        if self.codeBank.changecurrentspeaker(s):
            self.currentSpeakerNumber.SetLabel(str(self.codeBank.currentSpeaker))
            print self.codeBank.currentSpeaker
            self.reloadSpeakerList()

    def onSaveDataAs(self, evt):
        dlg = wx.FileDialog(self, message="Choose a filename", wildcard="SCD files (*.scd)|*.scd", style=wx.FD_SAVE | wx.CHANGE_DIR)
        if dlg.ShowModal() == wx.ID_OK :
            path = dlg.GetPath()
            self.doSaveData(path)
        dlg.Destroy()

    def saveCodes(self, evt):

        if self.currentDataFile is None:
            dlg = wx.FileDialog(self, message="Choose a filename", wildcard="SCD files (*.scd)|*.scd", style=wx.FD_SAVE | wx.CHANGE_DIR)
            if dlg.ShowModal() == wx.ID_OK :
                path = dlg.GetPath()
                self.doSaveData(path)
                dlg.Destroy()

        else:
            path = self.currentDataFile
            self.doSaveData(path)

    def doSaveData(self, path):
        self.codeBank.savedata(path)
        self.needToSave(False)
        self.currentDataFile = path

    def onLoadVideoFile(self, evt):
        dlg = wx.FileDialog(self, message="Choose a media file",
                            defaultDir=os.getcwd(), defaultFile="",
                            style=wx.OPEN | wx.CHANGE_DIR )
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            dlg.Destroy()
            if self.doLoadVideoFile(path) < 0:
                return -1

        if self.codeBank is None:
            self.onNewCodeBank(1)
        self.loadDataButton.Enable()
        return 1

    def loadTestVideo(self, evt):
        self.wantToSave()
        path = os.path.join("/Users", "chrismellinger", "Google Drive", "GroupAnalysis",
                            "Study1", "Group2", "Group 2.mp4")
        self.doLoadVideoFile(path)

        self.onNewCodeBank(1)
        self.loadDataButton.Enable()

    def onLoadDataFile(self, evt):
            self.wantToSave()
            dlg = wx.FileDialog(
                self, message="Choose a file",
                defaultDir=os.getcwd(),
                wildcard="(.scd)|.scd",
                style=wx.FD_OPEN | wx.CHANGE_DIR | wx.FD_FILE_MUST_EXIST
                )
            if dlg.ShowModal() == wx.ID_OK:
                path = dlg.GetPath()
                self.codeBank = self.codeBank.loaddata(path)
                self.currentDataFile = path
                self.refreshThings()
            dlg.Destroy()

    def refreshThings(self):
        self.in_point_txt.SetLabel(str(self.currentIn))
        self.out_point_txt.SetLabel(str(self.currentOut))
        self.currentSpeakerNumber.SetLabel(str(self.codeBank.currentSpeaker))
        self.reloadSpeakerList()

    def reloadSpeakerList(self):
        self.InOutList.DeleteAllItems()
        a = 0
        for i in self.codeBank.codes[self.codeBank.currentSpeaker]:
            self.InOutList.Append(i)
            self.InOutList.SetItemData(a, i[0])
            a += 1
        self.InOutList.SortItems(self.codeBank.itemCompare)

    def reloadClusterList(self):
        self.ClusterList.DeleteAllItems()
        a = 0
        for i in self.clusterBank.codes[self.clusterBank.currentSpeaker]:
            self.ClusterList.Append(i)
            self.ClusterList.SetItemData(a, i[0])
            a += 1
        self.ClusterList.SortItems(self.clusterBank.itemCompare)

    def wantToSave(self):
        """
        Asks the user if they want to save the data file if it hasn't been saved since the last change.
        :return: -1 if cancel, 1 if "Yes" (after the save occurs), and 2 if "No." 3 if no save is needed.
        """
        if self.needToSaveFlag:
            dlg = wx.MessageDialog(self, "Do you want to save your current data? If you don't, you may lose work.",
                                   "Save Work?",
                                   wx.YES_NO | wx.YES_DEFAULT | wx.CANCEL #| wx.ICON_INFORMATION
                                   )
            response = dlg.ShowModal()
            if response == wx.ID_YES:
                response2 = self.saveCodes(None)
                if response2 == wx.ID_CANCEL:
                    return -1
                else:
                    return 1
            elif response == wx.ID_CANCEL:
                return -1
            else:
                return 2
            dlg.Destroy()
        else:
            return 3

    def needToSave(self, need):
        """
        Sets text appropriately for the save message.
        :param need: True if data needs to saved, False if not.
        :return: Nothing
        """
        self.needToSaveFlag = need
        if need:
            self.needToSaveText.SetLabel("data needs saved")
        else:
            self.needToSaveText.SetLabel("data saved!")

    def onNewCodeBank(self, evt):
        if self.wantToSave() > 0:
            self.codeBank = SpeakingCode.SpeakingCodes(self.mc.Length(), numSpeakers=5)
            self.currentSpeakerNumber.SetLabel(str(self.codeBank.currentSpeaker))
            print "Number of speakers ", self.codeBank.numSpeakers
            self.checkpointflag = True # Tells the timer to check the speaker list points
            self.currentDataFile = None # Tells the "Save" button that we need to do a "Save As"
            self.needToSave(True) # Updates the save status text
            self.refreshThings()

    def addTimeCode(self, evt):

        newPoint = (self.currentIn, self.currentOut)
        self.addPoint(newPoint)
        self.currentIn = None
        self.currentOut = None
        #print self.codeBank.getcodes()
        self.needToSave(True)

    def addPoint(self, newPoint):
        self.codeBank.addinout(newPoint)
        #self.InOutList.Append(newPoint)
        self.reloadSpeakerList()

    def doLoadVideoFile(self, path):
        if not self.mc.Load(path):
            wx.MessageBox("Unable to load %s: Unsupported format?" % path, "ERROR", wx.ICON_ERROR | wx.OK)
            return -1
        else:
            folder, filename = os.path.split(path)
            #self.st_file.SetLabel('%s' % filename)
            self.mc.SetInitialSize(self.mc.GetBestSize())
            self.GetSizer().Layout()
            self.slider.SetRange(0, self.mc.Length())
            return 1

    def onJump(self, evt):
        jump = self.jumpValues[evt]
        pos = self.mc.Tell() + jump
        self.mc.Seek(pos)
        self.checkPoint(pos, checkList=True)
        self.checkClusterPoint(pos, checkList=True)

    def playFaster(self, evt):
        r = self.mc.GetPlaybackRate()
        if r < 0:
            newSpeed = r * 0.5
        elif r == 0:
            newSpeed = 1.0
        else:
            newSpeed = r * 2.0

        self.mc.SetPlaybackRate(newSpeed)

    def playSlower(self, evt):
        r = self.mc.GetPlaybackRate()
        if r > 0:
            newSpeed = r * 0.5
        elif r == 0:
            newSpeed = -1.0
        else:
            newSpeed = r * 2.0

        self.mc.SetPlaybackRate(newSpeed)

    def jumpButton(self, evt):
        button = evt.GetEventObject()
        value = self.jumpButtonValues[button.GetId()]
        pos = self.mc.Tell() + value
        self.mc.Seek(pos)
        self.checkPoint(pos, checkList=True)
        self.checkClusterPoint(pos, checkList=True)

    def onPlayPause(self, evt):
        if self.mc.GetState() == wx.media.MEDIASTATE_PLAYING:
            self.mc.Pause()
        else:
            self.mc.SetPlaybackRate(1.0)
            self.mc.Play()

    def onPause(self, evt):
        self.mc.Pause()

    def onStop(self, evt):
        self.mc.Stop()

    def onSeek(self, evt):
        offset = self.slider.GetValue()
        self.mc.Seek(offset)

    def setInPoint(self, evt):
        self.currentIn = self.mc.Tell()
        self.in_point_txt.SetLabel(str(self.currentIn))
        if self.currentIn > self.currentOut:
            self.currentOut = None
        elif self.currentOut > self.currentIn and self.currentOut is not None:
            self.addTimeCode(None)

    def setOutPoint(self, evt):
        self.currentOut = self.mc.Tell()
        self.out_point_txt.SetLabel(str(self.currentOut))
        if self.currentOut < self.currentIn:
            self.currentIn = None
        elif self.currentOut > self.currentIn and self.currentIn is not None:
            self.addTimeCode(None)

    def onTimer(self, evt):
        offset = self.mc.Tell()
        self.slider.SetValue(offset)
        if self.checkpointflag:
            self.checkPoint(offset)
        if self.checkclusterpointflag:
            self.checkClusterPoint(offset) # Add this.
        #self.st_size.SetLabel('size: %s ms' % self.mc.Length())
        #self.st_len.SetLabel('( %d seconds )' % (self.mc.Length()/1000))
        self.st_pos.SetLabel('position: %d ms' % offset)

    def checkPoint(self, curTime, checkList=False):

        # if self.currentIn is None and self.currentOut is None:
        #     yesIn = self.codeBank.checkinpoint(curTime)
        #     self.changeLEDColor(yesIn)
        yesIn = self.codeBank.checkinpoint(curTime)

        if self.currentOut is None and self.currentIn is not None and curTime >= self.currentIn:
            # This turns the LED on if an "in" point is set, but not an "out" point.
            self.out_point_txt.SetLabel(str(curTime))
            self.changeLEDColor(True)

        elif self.currentIn is None and curTime <= self.currentOut:
            # This turns on the LED if no "in" point is selected, but the time is less than the "out" point.
            self.in_point_txt.SetLabel(str(curTime))
            self.changeLEDColor(True)

        else:
            self.out_point_txt.SetLabel(str(self.currentOut))
            self.in_point_txt.SetLabel(str(self.currentIn))
            self.changeLEDColor(yesIn[0])

        # Now we'll check the list:
        if yesIn[0]:
            listItem = self.InOutList.FindItem(-1, str(yesIn[1][0]))
        else:
            listItem = -1

        if listItem >= 0 and (self.mc.GetState() == wx.media.MEDIASTATE_PLAYING or checkList):
            # We need to select the point, but first deselect everything else.
            for i in range(self.InOutList.GetItemCount()):
                self.InOutList.Select(i, on=False)
            self.click = False
            self.InOutList.Select(listItem, on=True)

    def checkClusterPoint(self, curTime, checkList=False):
        # Now we'll check the list:
        if self.checkclusterpointflag:
            yesIn = self.clusterBank.checkinpoint(curTime)
            if yesIn[0]:
                listItem = self.ClusterList.FindItem(-1, str(yesIn[1][0]))
            else:
                listItem = -1

            if listItem >= 0 and (self.mc.GetState() == wx.media.MEDIASTATE_PLAYING or checkList):
                # We need to select the point, but first deselect everything else.
                for i in range(self.ClusterList.GetItemCount()):
                    self.ClusterList.Select(i, on=False)
                self.click = False
                self.ClusterList.Select(listItem, on=True)

    def onInOutItemSelected(self, evt):
        self.itemSelected(self.InOutList)

    def onClusterItemSelected(self, evt):
        self.itemSelected(self.ClusterList)

    def itemSelected(self, list):
        # This self.click flag tells us whether or not the selection was the result of a click.
        # Any call to a list.Select() method should set this flag to False first.
        if self.click:
            item = list.GetFirstSelected()
            time = int(list.GetItemText(item, col=0))
            self.mc.Seek(time)
        self.click = True

    def changeLEDColor(self, evt):
        colorNow = self.LEDColors[evt]
        if self.Light.curColor == colorNow:
            return None
        else:
            self.Light.changeLED(colorNow)

    def char(self, evt):
        key = evt.GetKeyCode()
        #print(key)
        if key in self.actiondictionary.keys():
            self.actiondictionary[key](key)

    def giveBackFocus(self, evt):
        evt.SetWindow(self)


class MyFrame(wx.Frame):
    def __init__(self, parent=None, id=-1, label="Speaking Coder", size = (800, 600)):
        wx.Frame.__init__(self, parent, id, label, size=size)
        self.Bind(wx.EVT_CLOSE, self.onClose)

        self.panel = Panel1(self, -1)

    def onClose(self, evt):
        save = self.panel.wantToSave()
        if save > 0:
            self.Destroy()
        else:
            pass # Do nothing if they press Cancel.


if __name__ == '__main__':
    app = wx.App()
    # create a window/frame, no parent, -1 is default ID
    frame = MyFrame(None, -1, "Speaking Coder", size = (800, 600))
    # call the derived class
    #Panel1(frame, -1)
    frame.Show(1)
    app.MainLoop()