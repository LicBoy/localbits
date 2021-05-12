from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters,
                          ConversationHandler, PicklePersistence)

from localbits.tokens import telegramBotToken, telegramChatID, online_buy, online_sell
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
        self.releaseDict = {}

        #This info strongly connected with bot's implementation
        self.worksDictionary = {
            'sell' : {'status' : False, 'sellBorder' : None, 'cardMessage' : None},
            'buy' : {'status' : False, 'buyDifference' : None},
            'scanning' : {'status' : False}
        }

        self.dispatcher.add_handler(CommandHandler('start', self.start))
        self.dispatcher.add_handler(CommandHandler('help', self.help))
        self.dispatcher.add_handler(CommandHandler('adsstatus', self.adsStatus))
        self.dispatcher.add_handler(CommandHandler('switchad', self.switchAd))
        self.dispatcher.add_handler(CommandHandler('switchwork', self.switchWork))
        self.dispatcher.add_handler(CommandHandler('changeborder', self.changeBorder))

    """
    Get dictionary of completed payments from main function
    and send this contacts to user.
    
    Given Dictionary has following structure:
        contactsDict[contact_id] = {
                    'amount' : contact['amount']
                    'buyerMessages' : [],
                }
    """
    def addCompletedPayment(self, contact_id, amount, messages):
        self.releaseDict[contact_id] = {'amount' : amount, 'buyerMessages' : messages}
        curKeyRegExp = f"(^{contact_id}$)|"
        self.contactsRegex += curKeyRegExp
        botText = str(f"Payment completed:\n<b>{contact_id}</b> - <b>{self.releaseDict[contact_id]['amount']}</b>RUB - " + "; ".join(self.releaseDict[contact_id]['buyerMessages']) + "\n")

        self.dispatcher.add_handler(MessageHandler(Filters.regex(self.contactsRegex), self.chooseContactsToRelease))
        self.sendMessageWithConnectionCheck(chat_id=self.chatID, text=botText,
                                            reply_markup=self.generateReplyKeyboard(self.releaseDict),
                                            parse_mode=ParseMode.HTML)

    """
    Generates keyboard for contacts in dictionary of completed payments with 'all' option to release all contacts.
    """
    def generateReplyKeyboard(self, dict):
        replyKeyboard = [[key for key in list(dict)]] + [['All']]
        markup = ReplyKeyboardMarkup(replyKeyboard, one_time_keyboard=True)
        return markup

    """
    Function to get user's message of contacts to be released.
    Then release contacts one by one using defined function.
    """
    def chooseContactsToRelease(self, update, context):
        userMessage = update.message.text
        if userMessage == "All":
            for key in list(self.releaseDict):
                self.releaseContact(key)
        else:
            self.releaseContact(userMessage)

    """
    Beautiful way of releasing contact using Localbitcoins's function of releasing.
    """
    def releaseContact(self, contactID):
        reply_text = f"Trying to release contact {contactID}..."
        messageID = self.sendMessageWithConnectionCheck(chat_id=self.chatID, text=reply_text).message_id
        st_code = self.localBitcoinObject.contactRelease(contactID)[0]
        if st_code == 200:
            reply_text = f"Contact {contactID} release - success✅!"
            del self.releaseDict[contactID]
        else:
            reply_text = f"Contact {contactID} release - fail❌!"
        self.updater.bot.delete_message(chat_id=self.chatID, message_id=messageID)
        markup = None
        if len(self.releaseDict) == 0:
            markup = ReplyKeyboardRemove()
        self.sendMessageWithConnectionCheck(chat_id=self.chatID, text=reply_text, reply_markup=markup)

        if len(self.releaseDict) == 0:
            self.contactsRegex = r'(^All$)|'

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

    #NEEDED TO BE REWRITED! NEED to catch special exception!
    def sendMessageWithConnectionCheck(self,
                                       chat_id,
                                       text,
                                       reply_markup : Union[ReplyKeyboardMarkup, InlineKeyboardMarkup, ReplyKeyboardRemove] = None,
                                       parse_mode : ParseMode = None):
        try:
            return self.updater.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        except urllib3.exceptions.HTTPError as connectionExc:
            print(f"Connection aborted while trying to send {text} to {chat_id}, probably connection timeout.\nResending message...\n", connectionExc)
            return self.sendMessageWithConnectionCheck(chat_id, text, reply_markup, parse_mode)
        except Exception as exc:
            print(f"Other ERROR occured while sending telegram message!\n", exc)

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
    newBot = TelegramBot(telegramBotToken, telegramChatID, None)
    newBot.updater.start_polling()
    newBot.checkWorkSelected()
