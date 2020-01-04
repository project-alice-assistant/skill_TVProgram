import importlib
from abc import ABC, abstractmethod
from enum import Enum

from core.base.model.AliceSkill import AliceSkill
from core.base.model.Intent import Intent
from core.dialog.model.DialogSession import DialogSession
from core.util.Decorators import Online


class TimeSlotEnum(Enum):
    prime = '2015'
    night = '2200'
    now = 'now'


class TVProvider(ABC):
    """ Abstract class to implement """

    def getSlot(self, session: DialogSession) -> TimeSlotEnum:
        if not session.slotValue('TVTimeSlot'):
            return TimeSlotEnum.now
        else:
            return TimeSlotEnum(session.slotValue('TVTimeSlot'))

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
        'favChannel': [
            'username TEXT NOT NULL',
            'channel TEXT NOT NULL'
        ]
    }

    ### Intents
    _INTENT_WHATS_ON_TV = Intent('whatsOnTV_TVT')
    _INTENT_FAV_READ = Intent('readFav_TVT')
    _INTENT_FAV_CHECK = Intent('checkFav_TVT')
    _INTENT_FAV_ADD = Intent('addFav_TVT')
    _INTENT_FAV_DEL = Intent('delFav_TVT')
    _INTENT_FAV_DEL_ALL = Intent('delAllFav_TVT')
    _INTENT_FAV_CONF_DEL_ALL = Intent('AnswerYesOrNo', isProtected=True)
    _INTENT_SPELL_WORD = Intent('SpellWord', isProtected=True)

    def __init__(self):
        self._INTENTS = [
            (self._INTENT_WHATS_ON_TV, self.whatsOnTVIntent),
            (self._INTENT_FAV_READ, self.readFavIntent),
            (self._INTENT_FAV_CHECK, self.checkFavIntent),
            (self._INTENT_FAV_ADD, self.addFavIntent),
            (self._INTENT_FAV_DEL, self.delFavIntent),
            (self._INTENT_FAV_DEL_ALL, self.delFavListIntent),
            (self._INTENT_FAV_CONF_DEL_ALL, self.confFavDelIntent),
            self._INTENT_SPELL_WORD
        ]

        self._INTENT_SPELL_WORD.dialogMapping = {
            self._INTENT_FAV_ADD: self.addFavIntent,
            self._INTENT_FAV_DEL: self.delFavIntent,
            self._INTENT_FAV_CHECK: self.checkFavIntent
        }
        
        self._INTENT_FAV_CONF_DEL_ALL.dialogMapping = {
            self._INTENT_FAV_DEL_ALL: self.delFavListIntent
        }

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

    def _deleteFavList(self, session: DialogSession):
        self.DatabaseManager.delete(tableName=self._DBNAME,
                                    query='DELETE FROM :__table__ WHERE username = :username',
                                    values={'username': session.user},
                                    callerName=self.name)

    def _addFavItemInt(self, items: list, session: DialogSession) -> tuple:
        added = list()
        exist = list()
        already = self._getFavDB(session)
        for item in items:
            if item in already:
                exist.append(item)
            else:
                added.append(item)
                self.databaseInsert(tableName=self._DBNAME, values={'username': session.user, 'channel': item})

        return added, exist

    def _deleteFavItemInt(self, items: list, session: DialogSession) -> tuple:
        removed = list()
        exist = list()
        old = self._getFavDB(session)
        for item in items:
            if item not in old:
                exist.append(item)
            else:
                removed.append(item)

            self.DatabaseManager.delete(tableName=self._DBNAME,
                                        query='DELETE FROM :__table__ WHERE username = :username AND channel = :channel',
                                        values={'username': session.user, 'channel': item},
                                        callerName=self.name)

        return removed, exist

    def _checkFavListInt(self, items: list, session: DialogSession) -> tuple:
        found = list()
        missing = list()
        old = self._getFavDB(session)
        for item in items:
            if item in old:
                found.append(item)
            else:
                missing.append(item)
        return found, missing

    ### Session Handling ###
    def _getChannelItems(self, session: DialogSession) -> list:
        """get the values of channelItem as a list of strings"""
        if session.intentName == self._INTENT_SPELL_WORD:
            item = ''.join([slot.value['value'] for slot in session.slotsAsObjects['Letters']])
            return [item.capitalize()]

        items = [x.value['value'] for x in session.slotsAsObjects.get('channelItem', list()) if
                 x.value['value'] != "unknownword"]

        if not items:
            return self._getFavDB(session)

        return items

    ### INTENTS ###
    @Online
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
        result_sentence = ""
        for show in program:
            result_sentence += show['Channel'] + ": " + show['Show'] + " . "

        if not result_sentence:
            self.endDialog(session.sessionId, text=self.randomTalk('noInformation'))
        else:
            result_sentence = provider.doReplacing(result_sentence)
            self.endDialog(session.sessionId, text=self.randomTalk(f'{provider.getSlot(session).value}TV', [result_sentence]))

    #### Intents: Fav List handling
    def delFavListIntent(self, session: DialogSession, **_kwargs):
        self.continueDialog(
            sessionId=session.sessionId,
            text=self.randomTalk('chk_del_all'),
            intentFilter=[self._INTENT_FAV_CONF_DEL_ALL],
            currentDialogState=str(self._INTENT_FAV_DEL_ALL))

    def confFavDelIntent(self, session: DialogSession, **_kwargs):
        if self.Commons.isYes(session):
            self._deleteFavList(session)
            self.endDialog(session.sessionId, text=self.randomTalk('del_all'))
        else:
            self.endDialog(session.sessionId, text=self.randomTalk('nodel_all'))

    def addFavIntent(self, session: DialogSession):
        items = self._getChannelItems(session)
        if items:
            added, exist = self._addFavItemInt(items, session)
            self.endDialog(session.sessionId, text=self._combineLists('add', added, exist))

    def delFavIntent(self, session: DialogSession):
        items = self._getChannelItems(session)
        if items:
            removed, exist = self._deleteFavItemInt(items, session)
            self.endDialog(session.sessionId, text=self._combineLists('rem', removed, exist))

    def checkFavIntent(self, session: DialogSession):
        items = self._getChannelItems(session)
        if items:
            found, missing = self._checkFavListInt(items, session)
            self.endDialog(session.sessionId, text=self._combineLists('chk', found, missing))

    def readFavIntent(self, session: DialogSession, **_kwargs):
        """read the content of the list"""
        itemList = self._getFavDB(session)
        self.endDialog(session.sessionId, text=self._getTextForList('read', itemList))

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
