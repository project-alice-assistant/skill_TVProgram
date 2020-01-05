import importlib
from enum import Enum

from abc import ABC, abstractmethod
from core.base.model.AliceSkill import AliceSkill
from core.base.model.Intent import Intent
from core.dialog.model.DialogSession import DialogSession
from core.util.Decorators import Online, IntentHandler


class TimeSlotEnum(Enum):
	prime = '2015'
	night = '2200'
	now = 'now'


class TVProvider(ABC):
	""" Abstract class to implement """

	@staticmethod
	def getSlot(session: DialogSession) -> TimeSlotEnum:
		tvTimeSlot = session.slotValue('TVTimeSlot')
		return TimeSlotEnum(tvTimeSlot) if tvTimeSlot else TimeSlotEnum.now


	@abstractmethod
	def getProgram(self, session: DialogSession, channels: list) -> list:
		""" implement the logic here.
		return dict including lines with: Time(unused), Channel, Show, Desc(unused), Image(unused)
		"""
		pass


class TVProgram(AliceSkill):
	"""
	Author: philipp2310
	Description: Read the television program from TVSpielfilm and maintain a list of favorite channels
	"""

	_DBNAME = 'favChannel'
	_FALLBACK_PROVIDER = 'TVSpielfilm'

	_DATABASE = {
		_DBNAME: [
			'username TEXT NOT NULL',
			'channel TEXT NOT NULL'
		]
	}

	def __init__(self):
		super().__init__(self._INTENTS, databaseSchema=self._DATABASE)


	def _getFavDB(self, session: DialogSession) -> list:
		favChannel = self.databaseFetch(
			tableName=self._DBNAME,
			query='SELECT * FROM :__table__ WHERE username = :username',
			values={'username': session.user},
			method='all'
		)
		if favChannel:
			return [item['channel'] for item in favChannel]
		return list()


	### Session Handling ###
	def _getChannelItems(self, session: DialogSession) -> list:
		items = [x.value['value'] for x in session.slotsAsObjects.get('channelItem', list()) if
				 x.value['value'] != "unknownword"]

		return items or self._getFavDB(session)


	### INTENTS ###
	@Online
	@IntentHandler('whatsOnTV_TVT')
	def whatsOnTVIntent(self, session: DialogSession, **_kwargs):
		""" get requested channels or get favourites!"""
		channels = self._getChannelItems(session)
		if not channels:
			self.readFavIntent(session)
			return

		""" get provider of data """
		class_name = self.getConfig('TVProvider')
		if not class_name:
			class_name = self._FALLBACK_PROVIDER
			self.updateConfig('TVProvider', class_name)
		module = importlib.import_module(f'skills.TVProgram.TVProvider.{class_name}')
		class_ = getattr(module, class_name)
		provider = class_()

		""" get List of dicts """
		program = provider.getProgram(session, channels)

		""" build result sentence """
		result_sentence = ''.join([
			f"{show['Channel']}: {show['Show']} . " for show in program
		])

		if not result_sentence:
			self.endDialog(session.sessionId, text=self.randomTalk('noInformation'))
		else:
			result_sentence = provider.doReplacing(result_sentence)
			self.endDialog(session.sessionId, text=self.randomTalk(f'{provider.getSlot(session).value}TV', [result_sentence]))


	#### Intents: Fav List handling
	@IntentHandler('delAllFav_TVT')
	def delFavListIntent(self, session: DialogSession, **_kwargs):
		self.continueDialog(
			sessionId=session.sessionId,
			text=self.randomTalk('chk_del_all'),
			intentFilter=[Intent('AnswerYesOrNo')],
			currentDialogState='deleteAllQuestion')


	@IntentHandler('AnswerYesOrNo', requiredState='deleteAllQuestion', isProtected=True)
	def confFavDelIntent(self, session: DialogSession, **_kwargs):
		if self.Commons.isYes(session):
			self.DatabaseManager.delete(
				tableName=self._DBNAME,
				query='DELETE FROM :__table__ WHERE username = :username',
				values={'username': session.user},
				callerName=self.name)
			self.endDialog(session.sessionId, text=self.randomTalk('del_all'))
		else:
			self.endDialog(session.sessionId, text=self.randomTalk('nodel_all'))


	@IntentHandler('addFav_TVT')
	def addFavIntent(self, session: DialogSession):
		channels = self._getChannelItems(session)
		if not channels:
			return

		newFavChannel = list()
		existingFavChannel = list()
		favChannels = self._getFavDB(session)
		for channel in channels:
			if channel in favChannels:
				existingFavChannel.append(channel)
			else:
				newFavChannel.append(channel)
				self.databaseInsert(tableName=self._DBNAME, values={'username': session.user, 'channel': channel})

		self.endDialog(session.sessionId, text=self._combineLists('add', newFavChannel, existingFavChannel))


	@IntentHandler('delFav_TVT')
	def delFavIntent(self, session: DialogSession):
		channels = self._getChannelItems(session)
		if not channels:
			return

		removedFavChannels = list()
		notExistingFavChannels = list()
		favChannels = self._getFavDB(session)
		for channel in channels:
			if channel not in favChannels:
				notExistingFavChannels.append(channel)
			else:
				removedFavChannels.append(channel)
				self.DatabaseManager.delete(
					tableName=self._DBNAME,
					query='DELETE FROM :__table__ WHERE username = :username AND channel = :channel',
					values={'username': session.user, 'channel': channel},
					callerName=self.name)

		self.endDialog(session.sessionId, text=self._combineLists('rem', removedFavChannels, notExistingFavChannels))


	@IntentHandler('checkFav_TVT')
	def checkFavIntent(self, session: DialogSession):
		channels = self._getChannelItems(session)
		if not channels:
			return
		
		foundChannels = list()
		missingChannels = list()
		favChannels = self._getFavDB(session)
		for channel in channels:
			if channel in favChannels:
				foundChannels.append(channel)
			else:
				missingChannels.append(channel)

		self.endDialog(session.sessionId, text=self._combineLists('chk', foundChannels, missingChannels))


	@IntentHandler('readFav_TVT')
	def readFavIntent(self, session: DialogSession, **_kwargs):
		"""read the content of the list"""
		favChannels = self._getFavDB(session)
		self.endDialog(session.sessionId, text=self._getTextForList('read', favChannels))


	#### general List/Text operations
	def _combineLists(self, answer: str, first: list, second: list) -> str:
		firstAnswer = self._getTextForList(answer, first) if first else ''
		secondAnswer = self._getTextForList(f'{answer}_f', second) if second else ''
		combinedAnswer = self.randomTalk('state_con', [firstAnswer, secondAnswer]) if first and second else ''

		return combinedAnswer or firstAnswer or secondAnswer


	def _getTextForList(self, pref: str, items: list) -> str:
		self.logInfo(items)
		"""Combine entries of list into wrapper sentence"""
		if not items:
			return self.randomTalk(f'{pref}_none')
		elif len(items) == 1:
			return self.randomTalk(f'{pref}_one', [items[0]])

		value = self.randomTalk(text='genericList', replace=[', '.join(items[:-1]), items[-1]])
		return self.randomTalk(f'{pref}_multi', [value])
