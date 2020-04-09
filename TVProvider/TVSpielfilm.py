import requests

import xmltodict
from core.dialog.model.DialogSession import DialogSession

from skills.TVProgram.TVProgram import TVProvider, TimeSlotEnum


class TVSpielfilm(TVProvider):

	def _getFeed(self, session: DialogSession) -> dict:
		if self.getSlot(session) == TimeSlotEnum.prime:
			url = 'http://www.tvspielfilm.de/tv-programm/rss/heute2015.xml'
		elif self.getSlot(session) == TimeSlotEnum.night:
			url = 'http://www.tvspielfilm.de/tv-programm/rss/heute2200.xml'
		else:
			url = 'http://www.tvspielfilm.de/tv-programm/rss/jetzt.xml'

		req = requests.get(url=url)

		return xmltodict.parse(req.content)

	def getProgram(self, session: DialogSession, channels: list) -> list:
		""" implement the logic here.
		return dict including lines with: Time, Channel, Show, Desc, Image
		"""
		data = self._getFeed(session)

		result = list()

		for item in data['rss']['channel']['item']:
			entry = {'Image': ""}
			if any(f"| {chan} |" in item['title'] for chan in channels):
				if '@url' in item.get('enclosure', ''):
					entry['Image'] = f"<img src={item['enclosure']['@url']} />"

				entry['Time'], entry['Channel'], entry['Show'] = item['title'].split(" | ", maxsplit=2)

				if 'description' in item:
					entry['Desc'] = item['description']
				result.append(entry)
		return result

	def doReplacing(self, resultSentence: str) -> str:
		"""replace channels"""
		return resultSentence \
			.replace("ServusTV Deutschland", "Servus TV") \
			.replace("SAT.1", "Sat 1") \
			.replace("DMAX", "De Max") \
			.replace("VOX", "wocks")
