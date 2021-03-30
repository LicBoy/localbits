from telegram import ReplyKeyboardMarkup
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters,
                          ConversationHandler, PicklePersistence)

from localbits.tokens import telegramBotToken, telegramChatID

class TelegramBot:

    """
    On object initialization pass telegram TOKEN and ChatID
    """
    contactsRegex = r''

    def __init__(self, TOKEN, chatID, localBitcoinObject):
        self.token = TOKEN
        self.chatID = chatID
        self.updater = Updater(self.token)
        self.dispatcher = self.updater.dispatcher
        self.localBitcoinObject = localBitcoinObject
        self.exampleDict = {
        123: {
            'sentCard': True,
            'askedFIO': True,
            'closed': False,
            'payment_completed': True,
            'buyerMessages': ["John Smith"],
            'amount': '735'
        },
        126: {
            'sentCard': True,
            'askedFIO': True,
            'closed': False,
            'payment_completed': True,
            'buyerMessages': ["Paid", "Vanya"],
            'amount': '1080'
        },
        130: {
            'sentCard': True,
            'askedFIO': True,
            'closed': False,
            'payment_completed': True,
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
        self.dispatcher.add_handler(MessageHandler(Filters.text, self.releaseContact))

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
        botText = "These payments are ready:\n"
        for key in list(self.exampleDict):
            self.contactsRegex += f"(^{key}$)|"
            botText += str(f"{key} - {dict[key]['amount']}RUB - " + " ".join(dict[key]['buyerMessages']) + "\n")
        self.contactsRegex = self.contactsRegex[:-1]
        self.updater.bot.send_message(self.chatID, text=botText, reply_markup=self.generateReplyKeyboard(dict))

    def generateReplyKeyboard(self, dict):
        replyKeyboard = [[key for key in list(dict)]] + [['All']]
        markup = ReplyKeyboardMarkup(replyKeyboard, one_time_keyboard=True)
        #self.updater.bot.send_message(chat_id=self.chatID, text="These payments are completed:", reply_markup=markup)
        return markup

    def main(self):
        self.updater.bot.send_message(self.chatID, text="Licman's LocalBitcoins helper bot started!", reply_markup=self.generateReplyKeyboard(self.exampleDict))
        self.sendPaymentCompletedMessage(self.exampleDict)

    def sendCurSellPriceInfo(self, curPrice):
        self.updater.bot.send_message(self.chatID, text=f"Didn't change the price and it's {curPrice}")

    def releaseContact(self, update, context):
        userMessage = update.message.text
        messageID = self.updater.bot.send_message(chat_id=update.effective_chat.id, text=f"Trying to release contact {userMessage}...").message_id
        st_code = self.localBitcoinObject.contactRelease(userMessage)[0]
        if st_code != 200:
            self.updater.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=messageID, text=f"Failed to release contact {userMessage}❌!")
        else:
            self.updater.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=messageID, text=f"Contact {userMessage} was released!✅")

if __name__ == '__main__':
    newBot = TelegramBot(telegramBotToken, telegramChatID)
    newBot.main()