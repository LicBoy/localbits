from telegram import Update, ParseMode, ReplyKeyboardMarkup, ReplyKeyboardRemove,\
    InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import NetworkError
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters,
                          ConversationHandler, PicklePersistence, CallbackContext, CallbackQueryHandler)

from localbits.tokens import telegramBotToken, telegramChatID, online_buy, online_sell, myUserName,\
    ruslanSberCardMessage, momSberCardMessage, ayratSberCardMessage
from localbits.localbitcoins import LocalBitcoin

import re, time, datetime, urllib3
from typing import Union

class TelegramBot:

    """
    On object initialization pass telegram TOKEN and ChatID
    """
    contactsRegex = r'(^All$)|'

    def __init__(self, TOKEN : str, chatID : str, localBitcoinObject : LocalBitcoin):
        self.token = TOKEN
        self.chatID = chatID
        self.updater = Updater(self.token)
        self.dispatcher = self.updater.dispatcher
        self.localBitcoinObject = localBitcoinObject

        #This info strongly connected with bot's implementation
        self.worksDictionary = {
            'sell' : {'status' : False, 'sellBorder' : None, 'cardMessage' : None},
            'buy' : {'status' : False, 'buyDifference' : None},
            'scanning' : {'status' : False}
        }
        """
        Dictionary with contacts' info
        """
        self.contactsDictionary = {}

        """
        Dictionary with different banks' ads' list of dicts, adType and time of receiving this ads
        Example {'sberbank' : {'sell' : {'ads' : [adDict1, adDict2, ..., adDictN], 'time' : 2200000}}}
        Main key('sberbank') is bank's name, 'sell' is ad type, 
        'ads' is a list of dictionaries with every ad info, 'time' is last time.time() of receiving the ads.
        """
        self.recentAdsDictionary = {}

        self.dispatcher.add_handler(CommandHandler('start', self.start))
        self.dispatcher.add_handler(CommandHandler('help', self.help))
        self.dispatcher.add_handler(CommandHandler('adsstatus', self.adsStatus))
        self.dispatcher.add_handler(CommandHandler('switchad', self.switchAd))
        self.dispatcher.add_handler(CommandHandler('switchwork', self.switchWork))
        self.dispatcher.add_handler(CommandHandler('changeborder', self.changeBorder))

        self.lastCallbackQuery = '' #String needed for remembering last query callback
        self.feedbackMessageHandler = MessageHandler(filters = Filters.text & ~Filters.command,
                                                     callback=self.get_reputation_message_callback)
        self.sendMessageHandler = MessageHandler(filters=(Filters.text | Filters.document.category('image')) & ~Filters.command,
                                                 callback=self.get_message_send_message_callback)
        self.dispatcher.add_handler(CallbackQueryHandler(self.getReleaseCallback, pattern='^release_\S+$'))
        self.dispatcher.add_handler(CallbackQueryHandler(self.change_reputation_callback, pattern='^reputation_'))
        self.dispatcher.add_handler(CallbackQueryHandler(self.send_message_callback, pattern='^message_\S+$'))
        self.testDict = {
            '777' : {
                        'sentCard' : True,
                        'askedFIO': True,
                        'payment_completed' : True,
                        'buyerMessages' : ['Hi', 'Paid'],
                        'amount' : '777',
                        'tobe_deleted' : False
            }
        }

    def checkDashboardForNewContacts(self, msg, start=False):
        for contact_id in list(self.contactsDictionary):
            if self.contactsDictionary[contact_id]['tobe_deleted']:
                print(f"Contact {contact_id} is closed, dict updated")
                del self.contactsDictionary[contact_id]

        dashBoard = self.localBitcoinObject.sendRequest('/api/dashboard/seller/', '', 'get')
        for contact in dashBoard['contact_list']:
            contact = contact['data']
            contact_id = str(contact['contact_id'])
            username = contact['buyer']['username']
            paymentCompleted = contact['payment_completed_at'] is not None
            if not contact['disputed_at']:
                if start == True:
                    self.contactsDictionary[contact_id] = {
                        'username' : username,
                        'sentCard' : True,
                        'askedFIO': True,
                        'payment_completed' : paymentCompleted,
                        'buyerMessages' : [],
                        'amount' : contact['amount'],
                        'is_releasing' : False,
                        'tobe_deleted' : False
                    }
                else:
                    if contact_id not in self.contactsDictionary:
                        self.contactsDictionary[contact_id] = {
                            'username' : username,
                            'sentCard': False,
                            'askedFIO' : False,
                            'payment_completed': paymentCompleted,
                            'buyerMessages': [],
                            'amount': contact['amount'],
                            'is_releasing': False,
                            'tobe_deleted' : False,
                        }
                        postMessageRequest = self.localBitcoinObject.postMessageToContact(contact_id, msg)
                        if postMessageRequest[0] == 200:
                            self.contactsDictionary[contact_id]['sentCard'] = True #Changing dictionary only if message posting was succesful(code 200)
                            print('New contact: ', contact_id)
                    else:
                        self.contactsDictionary[contact_id]['payment_completed'] = paymentCompleted
                        messageReq = self.localBitcoinObject.getContactMessages(contact_id)
                        newMessages = messageReq['message_list']
                        newMessages = [msg['msg'] for msg in newMessages if msg['sender']['username'] != myUserName]
                        amountOfNewMessages = len(newMessages) - len(self.contactsDictionary[contact_id]['buyerMessages'])
                        self.contactsDictionary[contact_id]['buyerMessages'] = newMessages
                        if amountOfNewMessages > 0:
                            self.sendNewMessageFromUserMessage(contact_ID=contact_id, amountOfNewMessages=amountOfNewMessages)
                        if paymentCompleted:
                            # Get user's messages and ask for FIO if needed
                            if not self.contactsDictionary[contact_id]['askedFIO'] and len(
                                    self.contactsDictionary[contact_id]['buyerMessages']) == 0:
                                # There could be better way of determining if user sent his name
                                if self.localBitcoinObject.postMessageToContact(contact_id, message='инициалы?')[0] == 200:
                                    self.contactsDictionary[contact_id][
                                        'askedFIO'] = True  # Changing dictionary only if message posting was succesful(code 200)
        completedPayments = set([key for key in list(self.contactsDictionary) if self.contactsDictionary[key]['payment_completed']])
        for key in completedPayments:
            self.sendCompletedPaymentMessage(key)

    def sendCompletedPaymentMessage(self, contact_ID: str):
        botText = str(f"Payment completed:\n\n<i>ID{contact_ID}</i> - <b>{self.contactsDictionary[contact_ID]['amount']}</b> RUB - " + "; ".join(self.contactsDictionary[contact_ID]['buyerMessages']) + "\n")
        replyMarkup = self.get_payment_keyboard(contact_ID)
        if not self.contactsDictionary[contact_ID]['tobe_deleted']:
            msg_ID = self.sendMessageWithConnectionCheck(chat_id=self.chatID, text=botText,
                                            reply_markup=replyMarkup,
                                            parse_mode=ParseMode.HTML).message_id
            if self.contactsDictionary[contact_ID]['is_releasing']:
                self.updater.bot.delete_message(chat_id=self.chatID, message_id=msg_ID)

    def sendNewMessageFromUserMessage(self, contact_ID: str, amountOfNewMessages: int):
        botText = f"<i>ID {contact_ID}</i> | <b>{self.contactsDictionary[contact_ID]['amount']}</b> RUB |" \
                  f"<b>{self.contactsDictionary[contact_ID]['username']}</b> send message(s):\n\n"
        for msg in self.contactsDictionary[contact_ID]['buyerMessages'][-amountOfNewMessages:]:
            botText += ('<i>' + msg + '</i>\n')
        keyboard = [[]]
        if self.contactsDictionary[contact_ID]['payment_completed']:
            keyboard[0].append(InlineKeyboardButton("Release 💸", callback_data=f"release_{contact_ID}"))
        keyboard[0].append(InlineKeyboardButton("Message 💬", callback_data=f"message_{contact_ID}_{self.contactsDictionary[contact_ID]['username']}"))
        replyMarkup = InlineKeyboardMarkup(keyboard)
        self.sendMessageWithConnectionCheck(chat_id=self.chatID,
                                            text=botText,
                                            reply_markup=replyMarkup,
                                            parse_mode=ParseMode.HTML)

    def getReleaseCallback(self, update: Update, context: CallbackContext):
        query = update.callback_query
        contact_ID = query.data.split('_')[1]
        self.contactsDictionary[contact_ID]['is_releasing'] = True
        query.edit_message_text("Releasing contact...🕒", reply_markup=self.get_payment_keyboard(contact_ID))
        wasReleased = self.releaseContact(contact_ID)
        if wasReleased:
            query.edit_message_text(
                f"✅ <i>ID {contact_ID}</i> | <b>{self.contactsDictionary[contact_ID]['amount']}</b> RUB with "
                f"user <b>{self.contactsDictionary[contact_ID]['username']}</b> released.\n\n"
                f"You can leave your feedback for this user:",
                reply_markup=self.get_payment_keyboard(contact_ID, wasReleased=True),
            parse_mode=ParseMode.HTML)
        else:
            query.edit_message_text(
                f"❌ <i>ID {contact_ID}</i> | <b>{self.contactsDictionary[contact_ID]['amount']}</b> RUB couldn't release",
                reply_markup=self.get_payment_keyboard(contact_ID), parse_mode=ParseMode.HTML)
        query.answer()

    """
    Beautiful way of releasing contact using Localbitcoins's function of releasing.
    """
    def releaseContact(self, contactID) -> bool:
        st_code = self.localBitcoinObject.contactRelease(contactID)[0]
        if st_code == 200:
            self.contactsDictionary[contactID]['tobe_deleted'] = True
            return True
        return False


    def send_message_callback(self, update: Update, context: CallbackContext):
        query = update.callback_query
        self.lastCallbackQuery = query
        query.answer()
        keyboard = [['Отмена']]
        markup = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        msg = '💬 Input your message:'
        self.dispatcher.add_handler(self.sendMessageHandler)
        self.sendMessageWithConnectionCheck(chat_id=update.effective_chat.id,
                                            text=msg,
                                            reply_markup=markup)

    def get_message_send_message_callback(self, update: Update, context: CallbackContext):
        self.dispatcher.remove_handler(self.sendMessageHandler)
        messageText = update.message.text
        replyMsg = ''
        if messageText == 'Отмена':
            replyMsg = '❌ Canceled sending message.'
        else:
            contact_ID = self.lastCallbackQuery.split("_")[1]
            username = self.lastCallbackQuery.split("_", 2)[2]
            replyMsg = 'Sending message...🕒'
            msg_ID = self.sendMessageWithConnectionCheck(chat_id=update.effective_chat.id,
                                                text=replyMsg).message_id
            if self.localBitcoinObject.postMessageToContact(contact_id=contact_ID, message=messageText)[0] == 200:
                replyMsg = f"💬 Your message was sent to user <b>{username}</b>."
            else:
                replyMsg = f"❌ For some reason message wasn\'t sent to user <b>{username}</b>."
            self.updater.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_ID)
        self.sendMessageWithConnectionCheck(chat_id=update.effective_chat.id,
                                            text=replyMsg,
                                            reply_markup=ReplyKeyboardRemove(),
                                            parse_mode=ParseMode.HTML)


    def get_reputation_message_callback(self, update: Update, context: CallbackContext):
        print("Removed message handler for feedback!")
        self.dispatcher.remove_handler(self.feedbackMessageHandler)
        repStatus = self.lastCallbackQuery.split("_")[1]
        username = self.lastCallbackQuery.split("_", 2)[2]
        print("Entered message callback, got", update.effective_chat.id, update.message.text)
        text = update.message.text
        if text == 'Без комментария':
            text = None
        else:
            text += ' | QLicman'
        if repStatus == 'bad':
            repStatus = 'block'
        msgText = 'Sending feedback...🕒'
        msg_ID = self.sendMessageWithConnectionCheck(text=msgText,
                                                     chat_id=update.effective_chat.id,
                                                     reply_markup=ReplyKeyboardRemove()).message_id
        if self.localBitcoinObject.postFeedbackToUser(username=username, feedback=repStatus, msg=text)[0] == 200:
            msgText = f"✅ Your feedback was sent to user <b>{username}</b>."
        else:
            msgText = f"❌ Couldn't send feedback to user <b>{username}</b>"
        self.updater.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_ID)
        self.sendMessageWithConnectionCheck(chat_id=update.effective_chat.id,
                                            text=msgText)


    def change_reputation_callback(self, update: Update, context: CallbackContext):
        query = update.callback_query
        self.lastCallbackQuery = query.data
        print("Current feedback is", self.lastCallbackQuery)
        reputationStatus = query.data.split("_")[1]
        username = query.data.split("_", 2)[2]
        if reputationStatus == 'block': #If message is not needed
            msgText = ''
            if self.localBitcoinObject.postFeedbackToUser(username=username, feedback='block_without_feedback', msg=None)[0] == 200:
                msgText = f"{query.message.text} You have blocked user <b>{username}</b>"
            else:
                msgText = f"❌ Couldn't block user <b>{username}</b>"
            self.sendMessageWithConnectionCheck(chat_id=update.effective_chat.id,
                                                text=msgText,
                                                parse_mode=ParseMode.HTML)
        else:   #If message is needed for feedback
            self.getReputationMessage(update, context)

    def getReputationMessage(self, update: Update, context: CallbackContext):
        query = update.callback_query
        reputationStatus = query.data.split("_")[1]
        username = query.data.split("_", 2)[2]
        button_1, button_2 = '', ''
        if reputationStatus == 'trust':
            button_1, button_2 = 'Быстро и надёжно!', 'Надёжный покупатель.'
        elif reputationStatus == 'positive':
            button_1, button_2 = 'Всё хорошо!', 'Сделка прошла хорошо.'
        elif reputationStatus == 'neutral':
            button_1, button_2 = 'Нормально', 'Нечего сказать...'
        elif reputationStatus == 'bad':
            button_1, button_2 = 'Ужасная сделка!', 'Лучше блокируйте.'
        button_1, button_2 = button_1 + ' | ' + myUserName, button_2 + ' | ' + myUserName
        keyboard = [
            [button_1, button_2],
            ['Без комментария']
        ]
        if reputationStatus == 'bad':
            keyboard = [
                [button_1, button_2]
            ]
        query.answer()
        markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        icon =''
        for buttonRow in query.message['reply_markup']['inline_keyboard']:
            for button in buttonRow:
                if reputationStatus in button['callback_data']:
                    icon = button['text']
        print("Added message handler for feedback!")
        self.dispatcher.add_handler(self.feedbackMessageHandler)
        self.sendMessageWithConnectionCheck(chat_id=update.effective_chat.id,
                                            text=icon + '💬' + f" Feedback comment for user <b>{username}</b>:",
                                            reply_markup=markup,
                                            parse_mode=ParseMode.HTML)

    def get_payment_keyboard(self, contact_ID: str, wasReleased: bool = False) -> InlineKeyboardMarkup:
        username = self.contactsDictionary[contact_ID]['username']
        if not wasReleased:
            keyboard = [
                [
                    InlineKeyboardButton("Release 💸", callback_data=f"release_{contact_ID}"),
                    InlineKeyboardButton("Message 💬", callback_data=f"message_{contact_ID}_{username}")
                ]
            ]
        else:
            keyboard = [
                [
                    InlineKeyboardButton("😁", callback_data=f"reputation_trust_{username}"),
                    InlineKeyboardButton("😃", callback_data=f"reputation_positive_{username}"),
                    InlineKeyboardButton("😐", callback_data=f"reputation_neutral_{username}"),
                    InlineKeyboardButton("😡", callback_data=f"reputation_bad_{username}"),
                    InlineKeyboardButton("🚫", callback_data=f"reputation_block_{username}"),
                ],
                [
                    InlineKeyboardButton("Message 💬", callback_data=f"message_{contact_ID}_{username}")
                ]
            ]
        return InlineKeyboardMarkup(keyboard)
    """
    Get status of main SELL and BUY ads.
    """
    def adsStatus(self, update, context):
        adsDict = self.localBitcoinObject.getSeveralAds(online_buy, online_sell)
        bitcoinBalance = self.localBitcoinObject.getWalletBalance()['total']['balance']
        text = ""
        for ad in adsDict:
            ad = ad['data']
            if ad['visible']: text += '<i>On</i>🟢'
            else: text += '<i>Off</i>🔴'

            argumentsInfo = ''
            if ad['trade_type'] == 'ONLINE_SELL':
                text += '<b>Selling</b>'
                argumentsInfo = f"Sell Border: {self.worksDictionary['sell']['sellBorder']}\n" \
                                 f"Active Card: {self.worksDictionary['sell']['cardMessage']}"
            else:
                text += '<b>Buying</b>'
                argumentsInfo = f"Buy Difference: {self.worksDictionary['buy']['buyDifference']}"
            text += f'\nLimits: {int(float(ad["min_amount"]))} - {int(float(ad["max_amount_available"]))}\n{argumentsInfo}\n\n'
        text += f"\nBalance: <strong>{bitcoinBalance}</strong> BTC."
        self.sendMessageWithConnectionCheck(chat_id=self.chatID, text=text, parse_mode=ParseMode.HTML)

    """
    Switches needed ad(sell or buy) to needed status(OFF(0) or ON(1)) 
    """
    def switchAd(self, update, context):
        userArgs = " ".join(context.args)
        sellWordRegex, buyWordRegex, switchOnRegex, switchOffRegex = re.compile(r'sel'), re.compile(r'buy'), re.compile(r'on|1'), re.compile(r'off|0')

        switchBoolean = None
        replyMessage = ''

        if not switchOnRegex.search(userArgs) and not switchOffRegex.search(userArgs):
            replyMessage = f"Haven't found any status(ON/OFF)!❌"
        elif switchOffRegex.search(userArgs) and switchOnRegex.search(userArgs):
            replyMessage = f"Found both statuses. Choose ONE!❌"
        else:
            if switchOnRegex.search(userArgs): switchBoolean = True
            else: switchBoolean = False
            statusText, statusSymbol = self.returnStatusTextAndSymbol(switchBoolean)
            statusCode, adText = 0, ""

            if sellWordRegex.search(userArgs):
                statusCode = self.localBitcoinObject.switchAd(online_sell, switchBoolean)[0]
                adText = "SELL"
            elif buyWordRegex.search(userArgs):
                statusCode = self.localBitcoinObject.switchAd(online_buy, switchBoolean)[0]
                adText = "BUY"
            if statusCode == -1:  # If ad already has this status, so we don't need to send request to local
                replyMessage = f"{adText} AD is already has status {statusText}!{statusSymbol}"
            elif statusCode == 200:
                replyMessage = f"{adText} AD successfully switched to {statusText}!{statusSymbol}"

        if replyMessage == '':
            replyMessage = 'Haven\'t found any AD(SELL/BUY)!❌'
        self.sendMessageWithConnectionCheck(chat_id=update.message.chat_id, text=replyMessage)

    """
    Switches work modes on and off.
    """
    def switchWork(self, update, context):
        userArgs = " ".join(context.args)
        workSellRegex, workBuyRegex, workScanningRegex = re.compile(r'\bsel\w{0,4}'), re.compile(r'\bbuy\w{0,3}'), re.compile(r'\bscan\w{0,4}')
        switchOnRegex, switchOffRegex = re.compile(r'\bon\b'), re.compile(r'\boff\b')
        numberRegex = re.compile(r'-?\d+')
        cardMessageRegex = re.compile(r'(\bme\b)|(\bmom\b)|(\bayrat\b)')
        reply_text = ''
        workStatus : bool = None
        numberArgument = None
        cardMessage = None
        if switchOnRegex.search(userArgs):
            workStatus = True
        elif switchOffRegex.search(userArgs):
            workStatus = False
        if workStatus is None:
            reply_text = f"Haven't found any status(ON/OFF)!❌"

        else:
            if numberRegex.search(userArgs):
                numberArgument = int(numberRegex.search(userArgs).group())
            if cardMessageRegex.search(userArgs):
                cardMessage = cardMessageRegex.search(userArgs).group()

            if workSellRegex.search(userArgs):
                reply_text = self.actionOnWorkChoose('sell', workStatus, numberArgument, cardMessage)
            elif workBuyRegex.search(userArgs):
                reply_text = self.actionOnWorkChoose('buy', workStatus, numberArgument)
            elif workScanningRegex.search(userArgs):
                reply_text = self.actionOnWorkChoose('scanning', workStatus)
            else:
                reply_text = "Haven't found any work mode!❌"
        self.sendMessageWithConnectionCheck(update.message.chat_id, reply_text)

    """
    Controls which actions apply on work choose.
    """
    def actionOnWorkChoose(self, workType : str, switchStatus : bool, workArgument : int = None, sellCard : str = None):
        statusText, statusSymb = self.returnStatusTextAndSymbol(switchStatus)

        reply_text = ''
        if workType == 'buy' and workArgument == None:
            reply_text = f"Haven't found argument for {workType} work!❌"
        elif switchStatus == None:
            reply_text = f"Haven't found status for {workType} work!❌"
        elif self.worksDictionary[workType]['status'] and workType != 'sell' == switchStatus:
            reply_text = f"Work {workType} is already turned {statusText}!{statusSymb}"
        else:
            if workType == 'sell':
                requestCodeAndText = self.localBitcoinObject.switchAd(online_sell, switchStatus)
                if requestCodeAndText[0] == 200:
                    reply_text += f"SELL AD switched {statusText}!{statusSymb}\n"
                    reply_text += self.switchSellWork(switchStatus, workArgument, sellCard)
                elif requestCodeAndText[0] == -1:
                    reply_text += f"SELL AD is already was {statusText}!{statusSymb}\n"
                    reply_text += self.switchSellWork(switchStatus, workArgument, sellCard)
                else:
                    reply_text += f"With SELL AD other ERROR occured:\n" + requestCodeAndText[1]

            elif workType == 'buy':
                requestCodeAndText = self.localBitcoinObject.switchAd(online_buy, switchStatus)
                if requestCodeAndText[0] == 200:
                    self.worksDictionary['buy']['status'] = switchStatus
                    self.worksDictionary['buy']['buyDifference'] = workArgument
                    reply_text = f"BUY WORK was turned {statusText}!{statusSymb}"
                elif requestCodeAndText[0] == -1:
                    reply_text = f"BUY WORK is already was {statusText}!{statusSymb}"
                else:
                    reply_text = f"With BUY WORK other ERROR occured:\n" + requestCodeAndText[1]

            elif workType == 'scanning':
                self.worksDictionary['scanning']['status'] = switchStatus
                reply_text =  f"SCANNING WORK was turned {statusText}!{statusSymb}"
        return reply_text

    def switchSellWork(self, switchStatus : bool, sellBorder : int = None, cardMsg : str = None):
        workType = 'sell'
        reply_text = ''
        if switchStatus is None:
            reply_text = f"Haven't found any status(on/off) for SELL work!❌"
        else:
            statusText, statusSymbol = self.returnStatusTextAndSymbol(switchStatus)
            if switchStatus is True:
                if self.worksDictionary[workType]['status'] is False and self.worksDictionary[workType]['sellBorder'] is None and self.worksDictionary[workType]['cardMessage'] is None and (sellBorder is None or cardMsg is None):
                    reply_text = f"Haven't found some of arguments(cardMsg/sellborder) for first launch of SELL work!❌"
                elif self.worksDictionary[workType]['status'] is True:
                    self.worksDictionary[workType]['sellBorder'] = sellBorder
                    self.worksDictionary[workType]['cardMessage'] = cardMsg
                    reply_text = f"Changed arguments of work, but SELL work already has status {statusText}!{statusSymbol}"
                elif self.worksDictionary[workType]['status'] is False:
                    self.worksDictionary[workType]['status'] = switchStatus
                    self.worksDictionary[workType]['sellBorder'] = sellBorder
                    self.worksDictionary[workType]['cardMessage'] = cardMsg
                    reply_text = f"Changed status of SELL work to {statusText}!{statusSymbol}"
                if cardMsg == 'me':
                    self.worksDictionary[workType]['cardMessage'] = ruslanSberCardMessage
                elif cardMsg == 'mom':
                    self.worksDictionary[workType]['cardMessage'] = momSberCardMessage
                elif cardMsg == 'ayrat':
                    self.worksDictionary[workType]['cardMessage'] = ayratSberCardMessage
            elif switchStatus is False:
                if self.worksDictionary[workType]['status'] is False:
                    reply_text = f"SELL work already has status {statusText}!{statusSymbol}"
                else:
                    self.worksDictionary[workType]['status'] = switchStatus
                    reply_text = f"Changed status of SELL work to {statusText}!{statusSymbol}"
        return reply_text

    """
    Change border / difference on sell / buy ads.
    """
    def changeBorder(self, update, context):
        userArgs = " ".join(context.args)
        reply_message = ''
        sellAdRegex = re.compile(r'sel')
        buyAdRegex = re.compile(r'buy')
        numberRegex = re.compile(r'-?\d+')
        activeAd = ''
        currentNumber = 0
        if sellAdRegex.search(userArgs) and buyAdRegex.search(userArgs):
            reply_message = 'Found both sell and buy ad call. Choose ONE!❌'
            self.sendMessageWithConnectionCheck(update.message.chat_id, reply_message)
            return 0
        elif sellAdRegex.search(userArgs):
            activeAd = online_sell
        elif buyAdRegex.search(userArgs):
            activeAd = online_buy
        else:
            reply_message = "Haven't found any AD(sell/buy). Choose ONE!❌"
            self.sendMessageWithConnectionCheck(update.message.chat_id, reply_message)
            return 0

        if not numberRegex.search(userArgs):
            reply_message = "Haven't found number argument!❌"
            self.sendMessageWithConnectionCheck(update.message.chat_id, reply_message)
            return 0
        else:
            currentNumber = int(numberRegex.search(userArgs).group())
        if activeAd == online_sell:
            self.worksDictionary['sell']['sellBorder'] += currentNumber
            reply_message = f"Changed sell border on {currentNumber}!🟢\nNew border: {self.worksDictionary['sell']['sellBorder']}"
        elif activeAd == online_buy:
            self.worksDictionary['buy']['buyDifference'] += currentNumber
            reply_message = f"Changed buy difference on {currentNumber}!🟢nNew border: {self.worksDictionary['sell']['buyDifference']}"
        self.sendMessageWithConnectionCheck(update.message.chat_id, reply_message)

    """
    TODO: Change ads' prices or price changing algorithm.
    Probably useless.Ad
    """
    def changeAdPrice(self, update, context):
        userArgs = " ".join(context.args)
        sellWordRegex = re.compile(r'sel|all')
        buyWordRegex = re.compile(r'buy|all')
    """
    /help command handler.
    """
    def help(self, update, context):
        self.sendMessageWithConnectionCheck(chat_id=update.message.chat_id,
                                      text="Paid contacts should be sent to you automatically. Choose contacts to release from buttons menu.\n\n"+
                                           "List of available commands:\n"
                                           "/switchAd - Switch ad on or off.\n"
                                           "/changeAdPrice - Change price of ad.\n"
                                           "/changeWorkMode - Change type of work.")

    def main(self):
        self.sendMessageWithConnectionCheck(self.chatID, text="Licman's LocalBitcoins helper bot started!")

    """ 
    /start command handler
     """

    def start(self, update, context):
        keyboard = [
            [
                InlineKeyboardButton(text="localbitcoins", url="https://localbitcoins.fi/accounts/profile/QLicman/")
            ]
        ]
        markup = InlineKeyboardMarkup(keyboard)
        self.sendMessageWithConnectionCheck(chat_id=update.message.chat_id,
                                      text="Hello!\nThis is private(for now) localbitcoins bot of <a href=\"tg://user?id=560166970\">QLicman</a>\n",
                                      parse_mode=ParseMode.HTML, reply_markup=markup)

    """
    Function to send messages at random time, which can result in connection ERROR with telegram bot.
    It's needed to resend message if error occured.
    """

    def sendBotErrorMessage(self, msg):
        self.sendMessageWithConnectionCheck(self.chatID, msg)

    def sendMessageWithConnectionCheck(self,
                                       chat_id,
                                       text,
                                       reply_markup : Union[ReplyKeyboardMarkup, InlineKeyboardMarkup, ReplyKeyboardRemove] = None,
                                       parse_mode : ParseMode = None):
        try:
            return self.updater.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        except NetworkError as connectionExc:
            print(f"Connection aborted while trying to send {text} to {chat_id}, probably connection timeout.\n", connectionExc, "\nResending message...\n")
            return self.sendMessageWithConnectionCheck(chat_id, text, reply_markup, parse_mode)
        except Exception as exc:
            print(f"Other ERROR occured while sending telegram message!\n", exc)

    def returnRecentAds(self, adsType: str, bankName: str, filtered: bool = True) -> list:
        if bankName in self.recentAdsDictionary and adsType in self.recentAdsDictionary[bankName]:
            if time.time() - self.recentAdsDictionary[bankName][adsType]['time'] > 9.9: #Ads are updated every 10 secs
                newAds, newTime = self.localBitcoinObject.returnAdsWithTime(adsType, bankName)
                if filtered:
                    newAds = self.filterAds(adsType=adsType, ads_list=newAds)
                self.recentAdsDictionary[bankName][adsType]['ads'] = newAds
                self.recentAdsDictionary[bankName][adsType]['time'] = newTime
        else:
            newAds, newTime = self.localBitcoinObject.returnAdsWithTime(adsType, bankName)
            if filtered:
                newAds = self.filterAds(adsType=adsType, ads_list=newAds)
            self.recentAdsDictionary[bankName] = {adsType : {'ads' : newAds, 'time' : newTime}}
        return self.recentAdsDictionary[bankName][adsType]['ads']

    def filterAds(self, adsType: str, ads_list: list) -> list:
        filteredAds = []
        ind = 0
        if adsType == 'sell':
            for ad in ads_list:
                ad = ad['data']
                if ad['min_amount'] is None:
                    ads_list[ind]['data']['min_amount'] = '0'
                if ad['max_amount_available'] is None:
                    continue
                if float(ad['max_amount']) > 25000 and float(ad['min_amount']) < 49500:
                    filteredAds.append(ad)
                ind += 1
        elif adsType == 'buy':
            for ad in ads_list:
                ad = ad['data']
                if ad['min_amount'] is None:
                    ads_list[ind]['data']['min_amount'] = '0'
                if ad['max_amount_available'] is None:
                    continue
                if float(ad['max_amount_available']) > 3997 and float(ad['min_amount']) < 3100:
                    filteredAds.append(ad)
                ind += 1
        return filteredAds

    """
    Cosmetic helper function returning status 
    """
    def returnStatusTextAndSymbol(self, status : bool) -> (str, str):
        statusText = ''
        statusSymb = ''
        if status == True:
            statusText = 'ON'
            statusSymb = '🟢'
        else:
            statusText = 'OFF'
            statusSymb = '🔴'
        return (statusText, statusSymb)


if __name__ == '__main__':
    newBot = TelegramBot(telegramBotToken, telegramChatID, None )
    newBot.updater.start_polling()
    newBot.checkDashboardForNewContacts('mom', True)
