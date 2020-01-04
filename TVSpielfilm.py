from urllib.request import urlopen

import xmltodict
from core.dialog.model.DialogSession import DialogSession

from TVProgram import TVProvider, TimeSlotEnum


class TVSpielfilm(TVProvider):

    def _getFeed(self, session: DialogSession) -> dict:
        if self.getSlot(session) == TimeSlotEnum.prime:
            rssFile = urlopen('http://www.tvspielfilm.de/tv-programm/rss/heute2015.xml')
        elif self.getSlot(session) == TimeSlotEnum.night:
            rssFile = urlopen('http://www.tvspielfilm.de/tv-programm/rss/heute2200.xml')
        else:
            rssFile = urlopen('http://www.tvspielfilm.de/tv-programm/rss/jetzt.xml')

        data = rssFile.read()
        rssFile.close()

        return xmltodict.parse(data)

    def getProgram(self, session: DialogSession, channels: list) -> list:
        """ implement the logic here.
        return dict including lines with: Time, Channel, Show, Desc, Image
        """
        data = self._getFeed(session)

        result = list()

        for item in data['rss']['channel']['item']:
            entry = dict()
            entry['Image'] = ""
            if any("| " + chan + " |" in item['title'] for chan in channels):
                if 'enclosure' in item and '@url' in item['enclosure']:
                    entry['Image'] = "<img src=" + item['enclosure']['@url'] + " />"
                split = item['title'].split(" | ", 2)
                entry['Time'] = split[0].trim()
                entry['Channel'] = split[1].trim()
                entry['Show'] = split[2].trim()
                if 'description' in item:
                    entry['Desc'] = item['description']
                result.append(entry)
        return result

    def doReplacing(self, result_sentence: str) -> str:
        """replace channels"""
        result_sentence = result_sentence.replace("ServusTV Deutschland", "Servus TV")
        result_sentence = result_sentence.replace("SAT.1", "Sat 1")
        result_sentence = result_sentence.replace("DMAX", "De Max")
        result_sentence = result_sentence.replace("VOX", "wocks")
        return result_sentence
