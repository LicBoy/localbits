from telegram import Update, ParseMode, ReplyKeyboardMarkup, ReplyKeyboardRemove,\
    InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import NetworkError
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters,
                          ConversationHandler, PicklePersistence, CallbackContext, CallbackQueryHandler)

from localbits.tokens import telegramBotToken, telegramChatID, online_buy, online_sell, myUserName,\
    ruslanSberCardMessage, momSberCardMessage, ayratSberCardMessage
from localbits.localbitcoins import LocalBitcoin

import re, time
from typing import Union

class TelegramBot:
    MENU_CHOOSING_OPTION, CHANGING_ADS, CHANGING_WORKS = range(3)

    """
    On object initialization pass telegram TOKEN and ChatID
    """
    def __init__(self, TOKEN : str, chatID : str, localBitcoinObject : LocalBitcoin):
        self.token = TOKEN
        self.chatID = chatID
        self.updater = Updater(self.token)
        self.dispatcher = self.updater.dispatcher
        self.localBitcoinObject = localBitcoinObject

        #This info strongly connected with bot's implementation
        self.worksDictionary = {
            'sell' : {'status' : False, 'sellBorder' : None, 'cardOwner' : {'name' : None, 'cardMessage' : None}},
            'buy' : {'status' : False, 'buyDifference' : None},
            'scan' : {'status' : False}
        }
        self.CARDNAMES = ['Ruslan', 'Mom', 'Ayrat']
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

        """
        Last callbackquery data, needed to get user's text message once for feedback, message sending.
        """
        self.lastCallbackQuery = ''
        self.lastUpdate = None

        self.dispatcher.add_handler(CommandHandler('start', self.start))
        self.dispatcher.add_handler(CommandHandler('help', self.help))
        self.dispatcher.add_handler(CommandHandler('adsstatus', self.adsStatus))
        self.dispatcher.add_handler(CommandHandler('switchad', self.switchAd))
        self.dispatcher.add_handler(CommandHandler('switchwork', self.switchWork))
        self.dispatcher.add_handler(CommandHandler('changeborder', self.changeBorder))

        #Handler to catch message for feedback
        self.feedbackMessageHandler = MessageHandler(filters = Filters.text & ~Filters.command,
                                                     callback=self.get_reputation_message_callback)
        #Handler to catch message which will be sent to user
        self.sendMessageHandler = MessageHandler(filters=(Filters.text | Filters.document.category('image')) & ~Filters.command,
                                                 callback=self.get_message_send_message_callback)
        #Handler to catch message of digits to change ad limits.
        self.getNewLimitHandler = MessageHandler(filters=Filters.regex('^\d*[.,]?\d*$') | Filters.regex('^Отмена$'),
                                                 callback=self.get_new_limit_message_callback)
        #Handler to catch message of digits to input new work argument
        self.getNewWorkArgumentHandler = MessageHandler(filters=Filters.regex('^\d*[.,]?\d*$') | Filters.regex('^Отмена$'),
                                                 callback=self.get_work_numberArg_manually_message)
        self.dispatcher.add_handler(CallbackQueryHandler(self.getReleaseCallback, pattern='^release_\S+$'))
        self.dispatcher.add_handler(CallbackQueryHandler(self.change_reputation_callback, pattern='^reputation_'))
        self.dispatcher.add_handler(CallbackQueryHandler(self.send_message_callback, pattern='^message_\S+$'))

        self.menuHandler = ConversationHandler(
            entry_points=[
                CommandHandler('menu', self.command_menu),
                CallbackQueryHandler(self.command_menu_from_contact, pattern='^callback_menu_from_contact$')
            ],
            states={
                self.MENU_CHOOSING_OPTION: [
                    CallbackQueryHandler(self.command_menu_ads, pattern='^callback_ads$'),
                    CallbackQueryHandler(self.command_menu_works, pattern='^callback_works$'),
                    CallbackQueryHandler(self.command_menu_balance, pattern='^callback_wallet$'),
                    CallbackQueryHandler(self.command_menu_later, pattern='^callback_menu$'),
                ],
                self.CHANGING_ADS: [
                    CallbackQueryHandler(self.ads_switch, pattern='^callback_ad_switch_\d_\d+_\d+$'),
                    CallbackQueryHandler(self.change_limit_callback, pattern=f'^callback_ad_changeLimit_((max)|(min))?_\d+_\d+$'),
                    CallbackQueryHandler(self.command_menu_later, pattern='^callback_menu$')
                ],
                self.CHANGING_WORKS: [
                    CallbackQueryHandler(self.command_menu_works, pattern='(^callback_menu_works$)|(^callback_back$)'),
                    CallbackQueryHandler(self.work_sell_options, pattern='^callback_works_sell$'),
                    CallbackQueryHandler(self.work_buy_options, pattern='^callback_works_buy$'),
                    CallbackQueryHandler(self.work_scan_options, pattern='^callback_works_scan$'),
                    CallbackQueryHandler(self.command_menu_later, pattern='^callback_menu$'),
                    CallbackQueryHandler(self.work_switch, pattern='^callback_works_switch_\w*$'),
                    CallbackQueryHandler(self.change_work_numberArg_fromButton, pattern='^callback_work_\w+_\w+_[+-]\d+$'),
                    CallbackQueryHandler(self.change_work_numberArg_manually, pattern='^callback_work_\w+_\w+_manual$'),
                    CallbackQueryHandler(self.change_work_activeCard, pattern='^callback_sell_card_\w+$'),

                    CallbackQueryHandler(self.command_menu_works, pattern='^callback_works$'),
                    CallbackQueryHandler(self.command_menu_later, pattern='^callback_menu_later$')
                ]
        },
            fallbacks=[
            CommandHandler('menu', self.command_menu),
            CallbackQueryHandler(self.command_menu_later, pattern='^' + 'callback_menu' + '$')
        ])
        self.dispatcher.add_handler(self.menuHandler)
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
    """
    Function which compares dashboard on lclbitcoins and contacts dictionary and 
    makes needed changes for contacts.
    """
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

    """
    Function to send contact with 'completed_payment' == True status.
    """
    def sendCompletedPaymentMessage(self, contact_ID: str):
        botText = str(f"💸 Payment completed:\n\n<i>ID{contact_ID}</i> - <b>{self.contactsDictionary[contact_ID]['amount']}</b>"
                      f"RUB - " + "; ".join(self.contactsDictionary[contact_ID]['buyerMessages']) + "\n")
        replyMarkup = self.get_payment_keyboard(contact_ID)
        if not self.contactsDictionary[contact_ID]['tobe_deleted']:
            msg_ID = self.sendMessageWithConnectionCheck(chat_id=self.chatID, text=botText,
                                            reply_markup=replyMarkup,
                                            parse_mode=ParseMode.HTML).message_id
            if self.contactsDictionary[contact_ID]['tobe_deleted']:
                self.updater.bot.delete_message(chat_id=self.chatID, message_id=msg_ID)

    """
    Function to get user's new message from contact and send it through telegram bot.
    """
    def sendNewMessageFromUserMessage(self, contact_ID: str, amountOfNewMessages: int):
        botText = f"<i>💬 ID {contact_ID}</i> | <b>{self.contactsDictionary[contact_ID]['amount']}</b> RUB | " \
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

    """
    Function to catch release callback_data when user presses 'Release' button and try to release contact.
    """
    def getReleaseCallback(self, update: Update, context: CallbackContext):
        query = update.callback_query
        contact_ID = query.data.split('_')[1]
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
    Function to release contact using lcl API.
    Bool status of releasing is returned.
    """
    def releaseContact(self, contactID) -> bool:
        if self.localBitcoinObject.contactRelease(contactID)[0] == 200:
            self.contactsDictionary[contactID]['tobe_deleted'] = True
            return True
        return False

    """
    Function to catch send message callback_data when user presses 'Message' button.
    After, bot is expecting user to send text or image message to send it on lcl.
    """
    def send_message_callback(self, update: Update, context: CallbackContext):
        query = update.callback_query
        self.lastCallbackQuery = query.data
        query.answer()
        keyboard = [['Отмена']]
        markup = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        msg = '💬 Input your message:'
        self.dispatcher.add_handler(self.sendMessageHandler)
        self.sendMessageWithConnectionCheck(chat_id=update.effective_chat.id,
                                            text=msg,
                                            reply_markup=markup)

    """
    Callback used in MessageHandler to catch user's text or image message using Filters.
    Then, depending on what user has sent, either cancel sending message or send user's message on lcl.
    """
    def get_message_send_message_callback(self, update: Update, context: CallbackContext):
        self.dispatcher.remove_handler(self.sendMessageHandler)
        messageText = update.message.text
        replyMsg = ''
        if messageText == 'Отмена':
            replyMsg = '❌ Canceled sending message.'
        else:
            contact_ID = self.lastCallbackQuery.split("_")[1]
            username = self.lastCallbackQuery.split("_", 2)[2]
            replyMsg = '🕒 Sending message...'
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

    """
    Function to catch send feedback callback_data when user presses one of four reputation emojis button.
    Then, build a keyboard with appropriate comments, and after that, bot is waiting user to send
    only text message with the aim of sending this commentary with feedback.
    """
    def change_reputation_callback(self, update: Update, context: CallbackContext):
        query = update.callback_query
        self.lastCallbackQuery = query.data
        repStatus = query.data.split("_")[1]
        username = query.data.split("_", 2)[2]
        button_1, button_2 = '', ''
        if repStatus == 'trust':
            button_1, button_2 = 'Быстро и надёжно!', 'Надёжный покупатель.'
        elif repStatus == 'positive':
            button_1, button_2 = 'Всё хорошо!', 'Сделка прошла хорошо.'
        elif repStatus == 'neutral':
            button_1, button_2 = 'Нормально', 'Нечего сказать...'
        elif repStatus == 'block':
            button_1, button_2 = 'Ужасная сделка!', 'Лучше блокируйте.'
        button_1, button_2 = button_1 + ' | ' + myUserName, button_2 + ' | ' + myUserName
        keyboard = [
            [button_1, button_2],
            ['Без комментария']
        ]
        query.answer()
        markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        icon = ''
        for buttonRow in query.message['reply_markup']['inline_keyboard']:
            for button in buttonRow:
                if repStatus in button['callback_data']:
                    icon = button['text']
        self.dispatcher.add_handler(self.feedbackMessageHandler)
        self.sendMessageWithConnectionCheck(chat_id=update.effective_chat.id,
                                            text=icon + '💬' + f" Feedback comment for user <b>{username}</b>:",
                                            reply_markup=markup,
                                            parse_mode=ParseMode.HTML)

    """
    Function to get user's text message which will be commentary for chosen feedback status.
    If feedback status is block and no commentary given, block_without_feedback is sent, because
    'block' status requires mandatory commentary. Check lcl's 'postFeedbackToUser' function.
    """
    def get_reputation_message_callback(self, update: Update, context: CallbackContext):
        self.dispatcher.remove_handler(self.feedbackMessageHandler)
        repStatus = self.lastCallbackQuery.split("_")[1]
        username = self.lastCallbackQuery.split("_", 2)[2]
        text = update.message.text
        if text == 'Без комментария':
            text = None
            if repStatus == 'block':
                repStatus = 'block_without_feedback'
        else:
            text += ' | QLicman'
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

    """
    Function to build beautiful keyboard for contacts and paid contacts. 
    """
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
                    InlineKeyboardButton("🚫", callback_data=f"reputation_block_{username}"),
                ],
                [
                    InlineKeyboardButton("Message 💬", callback_data=f"message_{contact_ID}_{username}"),
                ],
                [
                    InlineKeyboardButton("Menu ⚙", callback_data='callback_menu_from_contact')
                ]
            ]
        return InlineKeyboardMarkup(keyboard)

    """
    Callback to start conversation and send menu.
    """
    def command_menu(self, update: Update, context: CallbackContext) -> int:
        keyboard = [
            [InlineKeyboardButton('Ads', callback_data='callback_ads'),
             InlineKeyboardButton('Works', callback_data='callback_works'),
             InlineKeyboardButton('Wallet', callback_data='callback_wallet')]
        ]
        replyMarkup = InlineKeyboardMarkup(keyboard)
        self.sendMessageWithConnectionCheck(chat_id=update.effective_chat.id,
                                            text='Menu ⚙',
                                            reply_markup=replyMarkup)
        return TelegramBot.MENU_CHOOSING_OPTION

    """
    Callback to return to menu later in conversation.
    """
    def command_menu_later(self, update: Update, context: CallbackContext) -> int:
        keyboard = [
            [InlineKeyboardButton('Ads', callback_data='callback_ads'),
             InlineKeyboardButton('Works', callback_data='callback_works'),
             InlineKeyboardButton('Wallet', callback_data='callback_wallet')]
        ]
        replyMarkup = InlineKeyboardMarkup(keyboard)
        query = update.callback_query
        query.edit_message_text('Menu ⚙', reply_markup=replyMarkup)
        return TelegramBot.MENU_CHOOSING_OPTION

    """
    Callback to start menu convesation from inline button.
    """
    def command_menu_from_contact(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        query.answer()
        keyboard = [
            [InlineKeyboardButton('Ads', callback_data='callback_ads'),
             InlineKeyboardButton('Works', callback_data='callback_works'),
             InlineKeyboardButton('Wallet', callback_data='callback_wallet')]
        ]
        replyMarkup = InlineKeyboardMarkup(keyboard)
        self.sendMessageWithConnectionCheck(chat_id=update.effective_chat.id,
                                            text='Menu ⚙',
                                            reply_markup=replyMarkup)
        return TelegramBot.MENU_CHOOSING_OPTION

    """
    Function to get ads info from lcl and send panel with ads' options.
    """
    def command_menu_ads(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        query.answer()
        query.edit_message_text('🕒...Getting ads info...')
        myAds = self.localBitcoinObject.getSeveralAds([online_buy, online_sell])
        adsKeyboard = self.get_ads_status_keyboard(myAds)
        replyMarkup = InlineKeyboardMarkup(adsKeyboard)
        query.edit_message_text('There are your ads.\n'
                                'You can switch them by clicking on status button\n'
                                'Or you can change your limits by clicking on corresponding button',
                                reply_markup=replyMarkup,
                                parse_mode=ParseMode.HTML)
        return TelegramBot.CHANGING_ADS

    """
    Function for building keyboard with ads info.
    """
    def get_ads_status_keyboard(self, adsList: list) -> list:
        adVisible = ''
        adType = ''
        bankName = ''
        keyboard = [
            [], #BankName and AdType
            [], #Ad status
            [], #Ad price equation
            [InlineKeyboardButton("Ad Limits", callback_data='callback_NULL')],
            [], #Ad limits
            [InlineKeyboardButton('Menu ⚙', callback_data='callback_menu')]
        ]
        adStatusIndex = 0
        limitButtonIndex = 0
        for ad in adsList:
            ad = ad['data']
            bankName = ad['online_provider'].upper()
            if ad['trade_type'] == 'ONLINE_SELL':
                adType = 'Selling'
            else:
                adType = 'Buying'
            firstRaw = InlineKeyboardButton(bankName + " " + adType,
                                            callback_data='callback_NULL')
            keyboard[0].append(firstRaw)
            adVisible = f'{self.returnStatusTextAndSymbol(ad["visible"])[0]} {self.returnStatusTextAndSymbol(ad["visible"])[1]}'
            secondRaw = InlineKeyboardButton(adVisible,
                                             callback_data=f'callback_ad_switch_{abs((int(ad["visible"])) - 1)}_{ad["ad_id"]}_{adStatusIndex}')
            keyboard[1].append(secondRaw)
            thirdRaw = InlineKeyboardButton(f"{ad['price_equation']} RUB", callback_data='callback_NULL')
            keyboard[2].append(thirdRaw)
            minLimit = InlineKeyboardButton(ad['min_amount'],
                                            callback_data=f'callback_ad_changeLimit_min_{ad["ad_id"]}_{limitButtonIndex}')
            limitButtonIndex += 1
            maxLimit = InlineKeyboardButton(ad['max_amount_available'],
                                            callback_data=f'callback_ad_changeLimit_max_{ad["ad_id"]}_{limitButtonIndex}')
            limitButtonIndex += 1
            keyboard[4].append(minLimit)
            keyboard[4].append(maxLimit)
            adStatusIndex += 1
        return keyboard

    """
    Function to answer 'switch ad' button.
    """
    def ads_switch(self, update: Update, context: CallbackContext) -> int:
        print("Joined switch Ad")
        query = update.callback_query
        replyText = ''
        ad_ID = query.data.split("_")[4]
        if ad_ID == online_buy: replyText = 'Buy'
        else: replyText = 'Sell'
        ad_newStatus = bool(int(query.data.split("_")[3]))
        index = int(query.data.split("_")[5])
        prevMarkup = query.message.reply_markup
        prevText = '\n'.join(query.message.text.split('\n')[-3:])
        query.edit_message_text('🕒...Switching ad...\n',
                                reply_markup=prevMarkup)

        if self.localBitcoinObject.switchAd(adID=ad_ID, status=ad_newStatus)[0] == 200:
            replyText += f' ad is now {self.returnStatusTextAndSymbol(ad_newStatus)[0]} {self.returnStatusTextAndSymbol(ad_newStatus)[1]}'
            buttonNewText = f'{self.returnStatusTextAndSymbol(ad_newStatus)[0]} {self.returnStatusTextAndSymbol(ad_newStatus)[1]}'
            prevMarkup.inline_keyboard[1][index] = InlineKeyboardButton(buttonNewText,
                                                                        callback_data=f'callback_ad_switch_{abs((int(ad_newStatus)) - 1)}_{ad_ID}_{index}')
        elif self.localBitcoinObject.switchAd(adID=ad_ID, status=ad_newStatus)[0] == -1:
            replyText += f' ad already was {self.returnStatusTextAndSymbol(ad_newStatus)[0]} {self.returnStatusTextAndSymbol(ad_newStatus)[1]}'
            buttonNewText = f'{self.returnStatusTextAndSymbol(ad_newStatus)[0]} {self.returnStatusTextAndSymbol(ad_newStatus)[1]}'
            prevMarkup.inline_keyboard[1][index] = InlineKeyboardButton(buttonNewText,
                                                                        callback_data=f'callback_ad_switch_{abs((int(ad_newStatus)) - 1)}_{ad_ID}_{index}')
        else:
            replyText = '❌ Couldn\'t switch ad for some reason!'
        query.answer()
        replyText += '\n\n' + prevText
        query.edit_message_text(text=replyText, reply_markup=prevMarkup)
        return TelegramBot.CHANGING_ADS

    """
    Function to catch 'change ad limit' inline button.
    """
    def change_limit_callback(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        query.answer()
        limitBorder = query.data.split("_")[3]
        self.lastCallbackQuery = query.data
        reply_text = f'📝 Input new {limitBorder} limit or choose Cancel:'
        keyboard = [
            ['Отмена']
        ]
        replyMarkup = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        self.menuHandler.states[self.CHANGING_ADS].append(self.getNewLimitHandler)
        self.sendMessageWithConnectionCheck(chat_id=update.effective_chat.id, text=reply_text, reply_markup=replyMarkup)
        self.lastUpdate = update
        return TelegramBot.CHANGING_ADS

    """
    Function to get new limit from user's input and edit previous keyboard.
    """
    def get_new_limit_message_callback(self, update: Update, context: CallbackContext) -> int:
        self.menuHandler.states[self.CHANGING_ADS].remove(self.getNewLimitHandler)
        limitBorder = self.lastCallbackQuery.split("_")[3]
        ad_ID = self.lastCallbackQuery.split("_")[4]
        query = self.lastUpdate.callback_query
        msgText = ''
        newMarkup = query.message.reply_markup
        if update.message.text == 'Отмена':
            msgText = f'🔙 You have canceled changing the {limitBorder} limit!'
        else:
            newLimit = update.message.text
            msgText = f'Changing {limitBorder} limit...🕒'
            msg_ID = self.sendMessageWithConnectionCheck(text=msgText,
                                                         chat_id=update.effective_chat.id,
                                                         reply_markup=ReplyKeyboardRemove()).message_id
            statusCode = None
            if limitBorder == 'min':
                statusCode = self.localBitcoinObject.changeAdField(ad_ID=ad_ID, min_amount=newLimit)[0]
            elif limitBorder == 'max':
                statusCode = self.localBitcoinObject.changeAdField(ad_ID=ad_ID, max_amount=newLimit)[0]
            if statusCode == 200:
                self.updater.bot.delete_message(chat_id=update.effective_chat.id, message_id=msg_ID)
                msgText = f'📝 Successfully changed limit to {newLimit}!'
                buttonIndex = int(self.lastCallbackQuery.split('_')[5])
                newMarkup = query.message.reply_markup
                newMarkup.inline_keyboard[4][buttonIndex] = InlineKeyboardButton(newLimit,
                                                                                  callback_data=f'callback_ad_changeLimit_{limitBorder.split("_")[0]}_{ad_ID}_{buttonIndex}')
            else:
                msgText = f'❌ Failed to change limit to {newLimit}!'
        self.sendMessageWithConnectionCheck(chat_id=update.effective_chat.id,
                                            text=msgText,
                                            reply_markup=ReplyKeyboardRemove())
        query.edit_message_text(text=msgText + '\n\n' + '\n'.join(query.message.text.split('\n')[-3:]),
                                reply_markup=newMarkup)
        return TelegramBot.CHANGING_ADS

    """
    Function to catch 'Work' button in menu.
    """
    def command_menu_works(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        query.answer()
        keyboard = [
            [InlineKeyboardButton(f'Selling {self.returnStatusTextAndSymbol(self.worksDictionary["sell"]["status"])[1]}',
                                  callback_data='callback_works_sell'),
             InlineKeyboardButton(f'Buying {self.returnStatusTextAndSymbol(self.worksDictionary["buy"]["status"])[1]}',
                                  callback_data='callback_works_buy'),
             InlineKeyboardButton(f'Scanning {self.returnStatusTextAndSymbol(self.worksDictionary["scan"]["status"])[1]}',
                                  callback_data='callback_works_scan')],
            [InlineKeyboardButton('Menu ⚙',
                                  callback_data='callback_menu_later')]
        ]
        replyMarkup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text('Available works' + '\n'.join(query.message.text.split('\n')[-3:]),
                                reply_markup=replyMarkup)
        return TelegramBot.CHANGING_WORKS

    """
    Function to catch inline button for sell work.
    """
    def work_sell_options(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        markup = self.works_build_markup('sell')
        query.answer()
        query.edit_message_text(text=f'Sell work control', reply_markup=markup)
        return TelegramBot.CHANGING_WORKS

    """
    Function to catch inline button for buy work.
    """
    def work_buy_options(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        markup = self.works_build_markup('buy')
        query.answer()
        query.edit_message_text(text=f'Buy work control', reply_markup=markup)
        return TelegramBot.CHANGING_WORKS

    """
    Function to catch inline button for scan work.
    """
    def work_scan_options(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        markup = self.works_build_markup('scan')
        query.answer()
        query.edit_message_text(text=f'Scan work control', reply_markup=markup)
        return TelegramBot.CHANGING_WORKS

    """
    Returns keyboard markup for particular work.
    """
    def works_build_markup(self, workType: str) -> InlineKeyboardMarkup:
        statusText, statusIcon = self.returnStatusTextAndSymbol(not self.worksDictionary[workType]['status'])
        keyboard = [
            [InlineKeyboardButton(f'Turn {statusText} {statusIcon}', callback_data=f'callback_works_switch_{workType}')],
        ]
        if workType in ['buy', 'sell']:
            keyboard += self.works_build_numberArg_Part(workType)
            if workType == 'sell':
                buttonsList = [[]]
                cardPart = [[InlineKeyboardButton(f'Cards', callback_data='callback_NULL')]]
                for name in ['Ruslan', 'Mom', 'Ayrat']:
                    curButton = InlineKeyboardButton(f'{name} {self.returnStatusTextAndSymbol(self.worksDictionary["sell"]["cardOwner"]["name"] == name)[1]}',
                                          callback_data=f'callback_sell_card_{name}')
                    buttonsList[0].append(curButton)
                cardPart += buttonsList
                keyboard += cardPart
        keyboard += [[InlineKeyboardButton('Back 🔙', callback_data='callback_works')]]
        return InlineKeyboardMarkup(keyboard)

    """
    Returns list of buttons which change work's arguments limit.
    It is contained in sell and buy works markups. 
    """
    def works_build_numberArg_Part(self, workType: str, minNumThousands: int = 2, maxNumThousands: int = 10) -> list:
        if workType not in ['sell', 'buy']:
            raise ValueError(f"Haven't found worktype type with value {workType}!\nCheck that you gave valid argument!")
        dictKey = ''
        buttonText = ''
        if workType == 'sell':
            dictKey = 'sellBorder'
            buttonText = 'Sell Border'
        else:
            dictKey = 'buyDifference'
            buttonText = 'Buy Difference'
        raw = [
            [InlineKeyboardButton(f'{buttonText}',
                                  callback_data='callback_NULL')],
            [
                InlineKeyboardButton(f'-{minNumThousands}k',
                                     callback_data=f'callback_work_{workType}_{dictKey}_-{minNumThousands}'),
                InlineKeyboardButton(f'-{maxNumThousands}k',
                                     callback_data=f'callback_work_{workType}_{dictKey}_-{maxNumThousands}'),
                InlineKeyboardButton(f'{self.worksDictionary[workType][dictKey]}',
                                     callback_data=f'callback_work_{workType}_{dictKey}_manual'),
                InlineKeyboardButton(f'+{minNumThousands}k',
                                     callback_data=f'callback_work_{workType}_{dictKey}_+{minNumThousands}'),
                InlineKeyboardButton(f'+{maxNumThousands}k',
                                     callback_data=f'callback_work_{workType}_{dictKey}_+{maxNumThousands}'),
            ]
        ]
        return raw

    """
    Function switches work ON or OFF.
    Switches only if work can be switched.
    """
    def work_switch(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        query.answer()
        workType = query.data.split("_")[3]
        replyText = ''
        newMarkup = query.message.reply_markup
        if self.work_can_be_switched(workType):
            newStatus = not self.worksDictionary[workType]['status']
            self.worksDictionary[workType]['status'] = newStatus
            statusText, statusIcon = self.returnStatusTextAndSymbol(not newStatus)
            newMarkup.inline_keyboard[0][0] = InlineKeyboardButton(f'Turn {statusText} {statusIcon}',
                                                                   callback_data=f'callback_works_switch_{workType}')
            replyText = f'✅ Switched work status!'
        else:
            replyText = f"❌ Couldn't switch work ON!\n" \
                        f"For <i>sell</i> check that active card and sell border are set (not None). \n" \
                        f"For <i>buy</i> check that buy difference is set (not None)."
        query.edit_message_text(text=replyText, reply_markup=newMarkup, parse_mode=ParseMode.HTML)
        return TelegramBot.CHANGING_WORKS

    """
    Function to switch work. If some arguments of work are not there, you can't switch work on.
    For sell needed arguments are sell broder and active card.
    For buy needed argument is buy difference.
    """
    def work_can_be_switched(self, worktype: str) -> bool:
        if worktype == 'sell':
            if self.worksDictionary['sell']['sellBorder'] is None or self.worksDictionary['sell']['cardOwner'] is None:
                return False
        elif worktype == 'buy':
            if self.worksDictionary['buy']['buyDifference'] is None:
                return False
        return True

    def change_work_numberArg_fromButton(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        query.answer()
        workType = query.data.split("_")[2]
        dictKey = query.data.split("_")[3]
        numArg = int(query.data.split("_")[4])
        if self.worksDictionary[workType][dictKey] is not None:
            self.worksDictionary[workType][dictKey] += numArg * 1000
            newMarkup = query.message.reply_markup
            newMarkup.inline_keyboard[2][2] = InlineKeyboardButton(f'{self.worksDictionary[workType][dictKey]}',
                                                                   callback_data=f'callback_work_{workType}_{dictKey}_manual')
            query.edit_message_text(text='✅ Changed work argument!', reply_markup=newMarkup)
        else:
            query.edit_message_text(text=f'❌ Can\'t change work argument because it\'s not given now!',
                                    reply_markup=query.message.reply_markup)
        return TelegramBot.CHANGING_WORKS

    def change_work_numberArg_manually(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        query.answer()
        self.lastCallbackQuery = query.data
        reply_text = f'📝 Input new argument or choose Cancel:'
        keyboard = [
            ['Отмена']
        ]
        replyMarkup = ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        self.menuHandler.states[self.CHANGING_WORKS].append(self.getNewWorkArgumentHandler)
        self.sendMessageWithConnectionCheck(chat_id=update.effective_chat.id, text=reply_text, reply_markup=replyMarkup)
        self.lastUpdate = update
        return TelegramBot.CHANGING_WORKS

    def get_work_numberArg_manually_message(self, update: Update, context: CallbackContext) -> int:
        self.menuHandler.states[self.CHANGING_WORKS].remove(self.getNewWorkArgumentHandler)
        replyText = ''
        msgText = update.message.text
        if msgText == 'Отмена':
            replyText = '🔙 Canceled changing work argument!'
        else:
            workType = self.lastCallbackQuery.split("_")[2]
            dictKey = self.lastCallbackQuery.split("_")[3]
            self.worksDictionary[workType][dictKey] = int(msgText)
            replyText = f"✅ Successfully changed {workType} argument to {msgText}!"
            updateToChange = self.lastUpdate.callback_query
            newMarkup = updateToChange.message.reply_markup
            newMarkup.inline_keyboard[2][2] = InlineKeyboardButton(msgText, callback_data=self.lastCallbackQuery)
            updateToChange.edit_message_text(text=replyText, reply_markup=newMarkup)
        self.sendMessageWithConnectionCheck(chat_id=update.effective_chat.id,
                                            text=replyText,
                                            reply_markup=ReplyKeyboardRemove())
        return TelegramBot.CHANGING_WORKS

    def change_work_activeCard(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        query.answer()
        queryName = query.data.split("_")[3]
        self.setActiveCardPerson(queryName)
        buttonsList = []
        for name in ['Ruslan', 'Mom', 'Ayrat']:
            curButton = InlineKeyboardButton(
                f'{name} {self.returnStatusTextAndSymbol(self.worksDictionary["sell"]["cardOwner"]["name"] == name)[1]}',
                callback_data=f'callback_sell_card_{name}')
            buttonsList.append(curButton)
        newMarkup = query.message.reply_markup
        newMarkup.inline_keyboard[4] = buttonsList
        query.edit_message_text(text='✅ Changed active card!', reply_markup=newMarkup)
        return TelegramBot.CHANGING_WORKS

    def command_menu_balance(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        query.answer()
        prevMarkup = query.message.reply_markup
        query.edit_message_text(text=f"🕒 Getting your balance...")
        walletInfo = self.localBitcoinObject.getWallet()
        totalBalance = walletInfo['total']['balance']
        sendableBalance = walletInfo['total']['sendable']
        btcAdress = walletInfo['receiving_address']
        replyText = f"👨‍💻 {myUserName}\nTotal balance: <b>{totalBalance}</b>\n" \
                    f"Sendable amount: <b>{sendableBalance}</b>\n\n" \
                    f"Your BTC address: <i>{btcAdress}</i>"
        query.edit_message_text(text=replyText, reply_markup=prevMarkup, parse_mode=ParseMode.HTML)
        return TelegramBot.MENU_CHOOSING_OPTION

    """
    Get status of main SELL and BUY ads.
    """
    def adsStatus(self, update, context):
        adsDict = self.localBitcoinObject.getSeveralAds([online_buy, online_sell])
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
                                 f"Active Card: {self.worksDictionary['sell']['cardOwner']['cardMessage']}"
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
                replyMessage = f"{adText} AD i  s already has status {statusText}!{statusSymbol}"
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
                reply_text = self.actionOnWorkChoose('scan', workStatus)
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

            elif workType == 'scan':
                self.worksDictionary['scan']['status'] = switchStatus
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
                if self.worksDictionary[workType]['status'] is False and self.worksDictionary[workType]['sellBorder'] is None and self.worksDictionary[workType]['cardOwner']['cardMessage'] is None and (sellBorder is None or cardMsg is None):
                    reply_text = f"Haven't found some of arguments(cardMsg/sellborder) for first launch of SELL work!❌"
                elif self.worksDictionary[workType]['status'] is True:
                    self.worksDictionary[workType]['sellBorder'] = sellBorder
                    self.worksDictionary[workType]['cardOwner']['cardMessage'] = cardMsg
                    reply_text = f"Changed arguments of work, but SELL work already has status {statusText}!{statusSymbol}"
                elif self.worksDictionary[workType]['status'] is False:
                    self.worksDictionary[workType]['status'] = switchStatus
                    self.worksDictionary[workType]['sellBorder'] = sellBorder
                    self.worksDictionary[workType]['cardOwner']['cardMessage'] = cardMsg
                    reply_text = f"Changed status of SELL work to {statusText}!{statusSymbol}"
                if cardMsg == 'me':
                    self.setActiveCardPerson('Ruslan')
                elif cardMsg == 'mom':
                    self.setActiveCardPerson('Mom')
                elif cardMsg == 'ayrat':
                    self.setActiveCardPerson('Ayrat')
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
            reply_message = f"Changed sell border on {currentNumber}!🟢\nNew sell border: {self.worksDictionary['sell']['sellBorder']}"
        elif activeAd == online_buy:
            self.worksDictionary['buy']['buyDifference'] += currentNumber
            reply_message = f"Changed buy difference on {currentNumber}!🟢\nNew buy difference: {self.worksDictionary['buy']['buyDifference']}"
        self.sendMessageWithConnectionCheck(update.message.chat_id, reply_message)

    """
    TODO: Change ads' prices or price changing algorithm.
    Probably useless.
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
                if ad['max_amount_available'] is None or ad['max_amount'] is None:
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
                if float(ad['max_amount_available']) > 4650 and float(ad['min_amount']) < 3553:
                    filteredAds.append(ad)
                ind += 1
        return filteredAds

    """
    Active card name setter
    """
    def setActiveCardPerson(self, name: str):
        if name not in self.CARDNAMES:
            raise ValueError(f"Name {name} wasn't found in available cards' names!")
        activeCardMessage = ''
        if name == 'Ruslan':
            activeCardMessage = ruslanSberCardMessage
        elif name == 'Mom':
            activeCardMessage = momSberCardMessage
        elif name == 'Ayrat':
            activeCardMessage = ayratSberCardMessage
        self.worksDictionary['sell']['cardOwner']['name'] = name
        self.worksDictionary['sell']['cardOwner']['cardMessage'] = activeCardMessage

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
