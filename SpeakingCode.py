__author__ = 'chrismellinger'
import heapq
import pickle
import csv
import os


class SpeakingCodes:
    def __init__(self, videoLength, numSpeakers=1, speakerDescriptions={}):
        """Class for storing codes of speaking or not.
        :param videoLength: length of video in milliseconds
        :param numSpeakers: total number of speakers
        :param speakerDescriptions: dictionary of descriptions.
        """

        self.numSpeakers = numSpeakers
        self.speakerDescriptions = speakerDescriptions
        self.invSpeakDesc = {v: k for k, v in speakerDescriptions.iteritems()}
        self.videoLength = videoLength
        self.currentSpeaker = 1

        # set up the codes dictionary
        self.codes = {}
        self.setspeakers()

    def setspeakers(self):
        for i in range(1, self.numSpeakers + 1):
            if i not in self.codes.keys():
                self.codes[i] = []

    def changenumberofspeakers(self, newnumber):
        self.numSpeakers = newnumber
        self.setspeakers()

    def getcodes(self):
        return self.codes

    def changecurrentspeaker(self, newSpeaker):
        """
        Switches the current speaker.
        :param newSpeaker: The speaker to change to
        :return: True if successful, False if the speaker is out of range.
        """
        if newSpeaker <= self.numSpeakers:
            self.currentSpeaker = newSpeaker
            return True
        else:
            return False

    def addinout(self, inOut):
        """
        Adds a point to the currently active speaker.
        :param inOut: a tuple of two millisecond points, order doesn't matter.
        """
        assert type(inOut) is tuple
        if inOut[0] < inOut[1]:
            heapq.heappush(self.codes[self.currentSpeaker], inOut)
        else:
            tempCode = (inOut[1], inOut[0])
            heapq.heappush(self.codes[self.currentSpeaker], tempCode)

    def removeinout(self, code):
        assert type(code) is tuple
        self.codes[self.currentSpeaker].remove(code)

    def editpoint(self, speakerNumber, code):
        pass

    def itemCompare(self, item1, item2):
        """
        Item comparison method, implemented primarily for the GUI list sorting, but could be used here in the future.
        :param item1:
        :param item2:
        :return:
        """
        i1 = int(item1)
        i2 = int(item2)
        if i1 == i2:
            return 0
        elif i1 < i2:
            return -1
        elif i2 < i1:
            return 1

    def checkinpoint(self, time):
        """
        :param time: time in milliseconds
        :return: A tuple, if time is in a code, then (True, code). Otherwise, (False, None).
        """
        #time should be in milliseconds. Returns True or False"""

        for code in self.codes[self.currentSpeaker]:
            c0, c1 = code
            if c0 <= time <= c1:
                return (True, code)

        return (False, None)

    def checkspeakinginrange(self, t0, t1):
        """
        :param t0: start of range in milliseconds
        :param t1: end of range in milliseconds
        :return: True if the current speaker has an in or out point in the range (inclusive).
        """

        for code in self.codes[self.currentSpeaker]:
            if t0 <= code[0] <= t1 or t0 <= code[1] <= t1:
                return True

        return False

    def renderdata(self, filename, stepsize=1000, start=0, stop=-1, timeheaders=False):
        """
        :param stepsize: step size in milliseconds as int. Defaults to 1
        :param start: start time in milliseconds as int. Defaults to 0.
        :param stop: stop time in milliseconds as int. Defaults to self.videolength
        :param timeheaders: If True, column headers are times in ms. First column is speaker numbers.
        :return: a dictionary with speakers as keys and lists containing 0 or 1 at each timestep.
        """
        if stop == -1:
            stop = self.videoLength

        startms = int(start)
        stopms = int(stop)
        stepsizems = int(stepsize)
        # Set up the dictionary for render:
        renderdict={}
        timelist = ['Speaker']
        for p in self.codes.keys():
            renderdict[p] = {}
            renderdict[p]['Speaker'] = p

        for t in range(startms, stopms, stepsizems):
            #print t
            timelist.append(t)
            for p in self.codes.keys():
                #print p
                self.changecurrentspeaker(p)

                if self.checkinpoint(t):
                    c = 1
                elif self.checkspeakinginrange(t, t + (stepsize-1)):
                    c = 1
                else:
                    c = 0

                persondict = renderdict[p]
                persondict[t] = c



        if timeheaders:
            #first column is person
            #all columns after are labelled by timestep
            with open(filename, 'wb') as f:
                writer = csv.writer(f)
                print "opened and writer"

                # put the speakers in order so it looks nice later.
                people = renderdict.keys()
                people.sort()

                print "sorted"
                # Write header row
                writer.writerow(timelist)
                for p in people:
                    print p, " is being written"
                    writer.writerow([renderdict[p][t] for t in timelist])

        elif not timeheaders:
            with open(filename, 'wb') as f:
                writer = csv.writer(f)
                print "opened writer"

                # put the speakers in order so it looks nice later.
                people = renderdict.keys()
                people.sort()

                print "sorted"
                # Write header row
                header = ["Time"]
                for p in people:
                    header.append(p)
                writer.writerow(header)

                # Write each row. Skip the first entry of timelist because it's the string 'Speaker'
                for t in timelist[1:]:
                    print t, " is being written"
                    row = [t]
                    for p in people:
                        row.append(renderdict[p][t])
                    writer.writerow(row)

    def savedata(self, fileName):
        if fileName[-4:] != ".scd":
            fileName = fileName + ".scd"

        with open(fileName, "wb") as f:
            pickle.dump(self, f)

    def savecsvraw(self, fileName):
        if fileName[-4:] != ".csv":
            fileName = fileName + ".csv"

        with open(fileName, "wb") as f:

            speakers = []
            for h in self.codes.keys():
                speakers.append(h)
            speakers.sort()

            fileWrite = csv.writer(f)
            headerrow = ['Speaker', 'In', 'Out']
            fileWrite.writerow(headerrow)
            for person in speakers:
                for t in self.codes[person]:
                    # Write each row with the the speaker number in the first column,
                    # the in point in the second col, and the out point in the 3rd col
                    row = [person, t[0], t[1]]
                    fileWrite.writerow(row)

    def loaddata(self, fileName):
        with open(fileName, "rb") as f:
            c = pickle.load(f)

        return c

    def loadrawcsv(self, fileName):

        with open(fileName, "rb") as f:
            tempCodeBank = SpeakingCodes(0)
            reader = csv.reader(f)
            for row in reader:
                if row[0] == 'Speaker':
                    pass
                else:
                    speaker = int(row[0])
                    inPoint = int(row[1])
                    outPoint = int(row[2])
                    tempCodeBank.changecurrentspeaker(speaker)
                    tempCodeBank.addinout((inPoint, outPoint))
                    if speaker > tempCodeBank.numSpeakers:
                        tempCodeBank.numSpeakers = speaker

        return tempCodeBank

    def loadsegfile(self, fileName):
        """
        Loads a .seg file produced by voiceid. Arbitrarily assigns speaker numbers and stores
        the voiceid speaker id in the speakerDescrpitions dictionary
        :param fileName: .seg file to load
        """
        if fileName[-4:] == '.seg':

            with open(fileName, "rb") as f:
                r = csv.reader(f, delimiter=' ')
                tempDict = {}

                for row in r:
                    s = row[7]
                    IN = int(row[2]) * 10 # The seg file generates times in centiseconds, so convert to milliseconds.
                    OUT = (int(row[2])+int(row[3])) * 10
                    if row[7] in tempDict:
                        tempDict[s].append((IN, OUT))
                    else:
                        tempDict[s] = [(IN, OUT)]

            self.changenumberofspeakers(len(tempDict.keys()))
            i=1
            for k in tempDict.keys():
                self.speakerDescriptions[i] = k
                self.invSpeakDesc[k] = i
                self.codes[i] = tempDict[k]
                i += 1

        else:
            print "Not a seg file"


if __name__ == '__main__':
    c = SpeakingCodes(1000)
    c.loadsegfile('Group01_70min_.seg')
    print c.invSpeakDesc