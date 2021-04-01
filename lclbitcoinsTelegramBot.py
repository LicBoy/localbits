from telegram import ReplyKeyboardMarkup
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters,
                          ConversationHandler, PicklePersistence)

from localbits.tokens import telegramBotToken, telegramChatID
import re

class TelegramBot:

    """
    On object initialization pass telegram TOKEN and ChatID
    """
    contactsRegex = r'(^All$)|'

    def __init__(self, TOKEN, chatID, localBitcoinObject):
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

    """
    Contacts Dictionary has following structure:
        contactsDict[contact_id] = {
                    'sentCard' : True,
                    'askedFIO': True,
                    'closed' : False,
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
            botText += str(f"{key} - {self.releaseDict[key]['amount']}RUB - " + "; ".join(self.releaseDict[key]['buyerMessages']) + "\n")
        self.contactsRegex = self.contactsRegex[:-1]

        bitcoinBalance = self.localBitcoinObject.getWallet()['total']['balance']
        botText += f"\nYour balance is {bitcoinBalance} BTC."
        self.dispatcher.add_handler(MessageHandler(Filters.regex(self.contactsRegex), self.chooseContactsToRelease))
        self.updater.bot.send_message(self.chatID, text=botText, reply_markup=self.generateReplyKeyboard(dict))

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
            reply_text = f"Contact {contactID} was released!✅"
            del self.releaseDict[contactID]
        else:
            reply_text = f"Failed to release contact {contactID}❌!"
        self.updater.bot.edit_message_text(chat_id=self.chatID, message_id=messageID, text=reply_text)

    def main(self):
        self.updater.bot.send_message(self.chatID, text="Licman's LocalBitcoins helper bot started!")

    def start(self, update, context):
        self.updater.bot.send_message(chat_id=update.message.chat_id,text="Hello!\nThis is private(for now) Bot of https://localbitcoins.fi/accounts/profile/QLicman/ .")

if __name__ == '__main__':
    newBot = TelegramBot(telegramBotToken, telegramChatID)
    newBot.main()