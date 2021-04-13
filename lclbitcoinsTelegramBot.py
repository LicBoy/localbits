from telegram import ReplyKeyboardMarkup, ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters,
                          ConversationHandler, PicklePersistence)

from localbits.tokens import telegramBotToken, telegramChatID, online_buy, online_sell
from localbits.localbitcoins import LocalBitcoin

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
        self.exampleDict = {
        123: {
            'sentCard': True,
            'askedFIO': True,
            'closed': False,
            'payment_completed': False,
            'buyerMessages': ["John Smith"],
            'amount': '735'
        },
        126: {
            'sentCard': True,
            'askedFIO': True,
            'closed': False,
            'payment_completed': False,
            'buyerMessages': ["Paid", "Vanya"],
            'amount': '1080'
        },
        130: {
            'sentCard': True,
            'askedFIO': True,
            'closed': False,
            'payment_completed': False,
            'buyerMessages': ["There will be a lot of text", "some random shit that doesnt matter at all", "And then there will be his name, but not right now, later", "Finally, Dick"],
            'amount': '1488'
        },
        145: {
            'sentCard': True,
            'askedFIO': True,
            'closed': False,
            'payment_completed': True,
            'buyerMessages': ["I'm afk"],
            'amount': '10200'
        },
    }

        self.dispatcher.add_handler(CommandHandler('start', self.start))
        self.dispatcher.add_handler(CommandHandler('help', self.help))
        self.dispatcher.add_handler(CommandHandler('adsstatus', self.adsStatus))
        self.dispatcher.add_handler(CommandHandler('switchad', self.switchAd))

    """
    Given Dictionary has following structure:
        contactsDict[contact_id] = {
                    'payment_completed' : False,
                    'buyerMessages' : [],
                    'amount' : contact['amount']
                }
    """
    def sendPaymentCompletedMessage(self, dict):
        self.releaseDict = dict
        botText = "Some payments are ready:\n"
        self.contactsRegex = r'(^All$)|'
        for key in list(self.releaseDict):
            curKeyRegExp = f"(^{key}$)|"
            self.contactsRegex += curKeyRegExp
            botText += str(f"<b>{key}</b> - <b>{self.releaseDict[key]['amount']}</b>RUB - " + "; ".join(self.releaseDict[key]['buyerMessages']) + "\n")
        self.contactsRegex = self.contactsRegex[:-1]

        bitcoinBalance = self.localBitcoinObject.getWallet()['total']['balance']
        botText += f"\nBalance: <strong>{bitcoinBalance}</strong> BTC."
        self.dispatcher.add_handler(MessageHandler(Filters.regex(self.contactsRegex), self.chooseContactsToRelease))
        self.updater.bot.send_message(self.chatID, text=botText, reply_markup=self.generateReplyKeyboard(dict), parse_mode=ParseMode.HTML)

    def generateReplyKeyboard(self, dict):
        replyKeyboard = [[key for key in list(dict)]] + [['All']]
        markup = ReplyKeyboardMarkup(replyKeyboard, one_time_keyboard=True)
        return markup

    def chooseContactsToRelease(self, update, context):
        userMessage = update.message.text
        if userMessage == "All":
            for key in list(self.releaseDict):
                self.releaseContact(key)
        else:
            self.releaseContact(userMessage)

    def releaseContact(self, contactID):
        reply_text = f"Trying to release contact {contactID}..."
        messageID = self.updater.bot.send_message(chat_id=self.chatID, text=reply_text).message_id
        st_code = self.localBitcoinObject.contactRelease(contactID)[0]
        if st_code == 200:
            reply_text = f"Contact {contactID} release - success✅!"
            del self.releaseDict[contactID]
            #del self.localBitcoinObject.contacts
        else:
            reply_text = f"Contact {contactID} release - fail❌!"
        self.updater.bot.delete_message(chat_id=self.chatID, message_id=messageID)
        self.updater.bot.send_message(chat_id=self.chatID, text=reply_text)
        if len(self.releaseDict) > 0:
            self.sendPaymentCompletedMessage(self.releaseDict)

    def adsStatus(self, update, context):
        adsDict = self.localBitcoinObject.getSeveralAds(online_buy, online_sell)
        text = ""
        for ad in adsDict:
            ad = ad['data']
            if ad['visible']: text += '<i>On</i>🟢'
            else: text += '<i>Off</i>🔴'

            if ad['trade_type'] == 'ONLINE_SELL': text += '<b>Selling</b>'
            else: text += '<b>Buying</b>'
            text += f' | Limits: {int(float(ad["min_amount"]))} - {int(float(ad["max_amount_available"]))}\n'
        self.updater.bot.send_message(update.message.chat_id, text, parse_mode=ParseMode.HTML)

    def switchAd(self, update, context):
        severalAds = self.localBitcoinObject.getSeveralAds(online_buy, online_sell)
        print(severalAds)
        self.updater.bot.send_message(update.message.chat_id, text=context.args)

    def help(self, update, context):
        self.updater.bot.send_message(chat_id=update.message.chat_id,
                                      text="Paid contacts should be sent to you automatically. Choose contacts to release from buttons menu.\n\n"+
                                           "List of available commands:\n"
                                           "/switchAd - Switch ad on or off.\n"
                                           "/changeAdPrice - Change price of ad.\n"
                                           "/changeWorkMode - Change type of work.")

    def main(self):
        self.updater.bot.send_message(self.chatID, text="Licman's LocalBitcoins helper bot started!")


    def start(self, update, context):
        keyboard = [
            [
                InlineKeyboardButton(text="localbitcoins", url="https://localbitcoins.fi/accounts/profile/QLicman/")
            ]
        ]
        markup = InlineKeyboardMarkup(keyboard)
        self.updater.bot.send_message(chat_id=update.message.chat_id,
                                      text="Hello!\nThis is private(for now) localbitcoins bot of <a href=\"tg://user?id=560166970\">QLicman</a>\n",
                                      parse_mode=ParseMode.HTML, reply_markup=markup)

if __name__ == '__main__':
    newBot = TelegramBot(telegramBotToken, telegramChatID)
    newBot.main()