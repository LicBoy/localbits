from localbits.localbitcoins import LocalBitcoin
from localbits.lclbitcoinsTelegramBot import TelegramBot
import requests, json
import math
import time, datetime           # for logging
import logging, sys, traceback  # for errors
import re                       # for bank recognition (prbbly useless cause of localbitcoins new banks format)
import winsound                 # for alert testing
from localbits import tokens    # !!!PERSONAL DATA

key = tokens.key
secret = tokens.secret
online_buy = tokens.online_buy      #YOU BUY HERE
online_sell = tokens.online_sell     #YOU SELL HERE
myUserName = tokens.myUserName
ruslanSberCardMessage = tokens.ruslanSberCardMessage
ayratSberCardMessage = tokens.ayratSberCardMessage
momSberCardMessage = tokens.momSberCardMessage
almirSberCardMessage = tokens.almirSberCardMessage
askForFIOMessage = 'фио?'

#IGNORE this users
ignoreList = ['Nikitakomp7', 'Ellenna', 'DmitriiGrom']                  #They usually invisible on BUY page
botsList = ['13_drunk_soul_13', 'Klaik', 'Slonya', 'DmitriiGrom']        #They are bots on SELL page
invisibleList = ['erikdar7777']

"""
Base class for running bot
"""
class LocalBitcoinBot:
    def __init__(self, localBitcoinObject, telegramBotObject):
        self.localBitcoinObject = localBitcoinObject
        self.telegramBotObject = telegramBotObject
        self.contactsDict = {}
        self.cardHolders = ['me', 'mom', 'almir', 'ayrat']
        self.workTypes = ['all', 'sell', 'buy', 'contacts', 'scanning']

    def checkForBankNamesRegularExpression(self, bank_name):
        # Regular expressions for Banks: Sber, Tink, Alpha, VTB, Roket, Raif
        regExpSber = r'[$SCСĊⓈĆ₡℃∁ℭŠṠṢṤṦṨ][\W\d_]*[BБ6Ⓑ൫ℬḂḄḆ][\W\d_]*[EЕĖⒺĘḔḖḘḚḜẸẺẼẾỀỂỄỆῈΈἘἙἚἛἜἝ3][\W\d_]*[RPРℙⓇṖṖῬṔℛℜℝ℟ṘṚṜṞ]'
        regExpTink = r'[TТ][\W\d]*[ИUI][\W\d]*[НN][\W\d]*[ЬK]'
        regExpAlpha = r'[AА][\W\d]*[ЛL][\W\d]*[ЬP][\W\d]*[ФH][\W\d]*[AА]'
        regExpVTB = r'[ВV][\W\d]*[TТ][\W\d]*[BБ]'
        regExpRoket = r'[РRP][\W\d]*[OО][\W\d]*[КK][\W\d]*[ЕE][\W\d]*[ТT]'
        regExpRaif = r'[РRP][\W\d]*[АA][\W\d]*[ЙI][\W\d]*[ФF]'

        reSearchSber = re.search(regExpSber, bank_name)
        reSearchTink = re.search(regExpTink, bank_name)
        reSearchAlpha = re.search(regExpAlpha, bank_name)
        reSearchVtb = re.search(regExpVTB, bank_name)
        reSearchRoket = re.search(regExpRoket, bank_name)
        reSearchRaif = re.search(regExpRaif, bank_name)
        return (reSearchSber and not reSearchVtb and not reSearchAlpha and not reSearchRoket and not reSearchTink and not reSearchRaif)

    #Get ads from online_buy category, U BUY HERE
    def getListOfBuyAds(self, myLimits=[10000, 50000]): #returns list of dictionaried ads
        req = requests.get(self.localBitcoinObject.baseurl + '/sell-bitcoins-online/sberbank/.json')
        while int(req.status_code) != 200:
            req = requests.get(self.localBitcoinObject.baseurl + '/sell-bitcoins-online/sberbank/.json')
        ads = json.loads(req.text)['data']['ad_list']

        printCounter = 5 #Show only 5 ads in logger, but get all ads in list
        vals = []
        for ad in ads:
            ad = ad['data']
            if ad['min_amount'] is None or ad['max_amount_available'] is None:
                continue

            #min_amount = float(ad['min_amount'])
            max_amount = float(ad['max_amount_available'])
            username = ad['profile']['username']
            if max_amount > myLimits[0] and username not in ignoreList: #can be improved
                if printCounter > 0:
                    logger.debug(f"BUY: {ad['temp_price']} {username}")
                    printCounter -= 1
                vals.append(ad)
        return vals

    #Get ads from online_sell category, U SELL HERE
    def getListOfSellAdsPrices(self, adsAmount = 7): #returns list of float prices
        n = adsAmount
        vals = []
        req = requests.get(self.localBitcoinObject.baseurl + '/buy-bitcoins-online/sberbank/.json')
        while int(req.status_code != 200):
            req = requests.get(self.localBitcoinObject.baseurl + '/buy-bitcoins-online/sberbank/.json')
        js = json.loads(req.text)['data']['ad_list']
        for ad in js:
            ad = ad['data']
            if ad['min_amount'] is None or ad['max_amount_available'] is None:
                continue

            min_amount = float(ad['min_amount'])
            max_amount = float(ad['max_amount_available'])
            temp_price = float(ad['temp_price'])
            username = ad['profile']['username']
            if min_amount <= 1500 and max_amount > 5000 and '+' in ad['profile']['trade_count'] and username not in botsList:
                if n>0:
                    #print(username, max_amount, end= " ")
                    logger.debug(f"SELL: {str(temp_price)} {username}")
                    vals.append(temp_price)
                    n-=1
                else:
                    return vals
        #Return top 7 or less sell ads from 1st page
        return vals

    def countGoodPriceForBUY(self, sellPrices, buyPrices, spreadDif=100000, minDif=50000):
        medPrice = 0; disp = 0
        amount = len(sellPrices)
        for price in sellPrices:
            medPrice += price
        medPrice = medPrice / amount
        for price in sellPrices:
            disp += pow(abs(price - medPrice), 2)
        disp = disp / amount
        disp = math.sqrt(disp)

        #print(medPrice, disp)
        logger.debug(f"Calculated medprice = {medPrice}, disp = {disp}")
        resPrice = medPrice + disp - spreadDif
        if sellPrices[0] - resPrice < minDif:
            resPrice = sellPrices[0] - minDif

        for ad in buyPrices:
            if float(ad['temp_price']) < resPrice and ad['profile']['username'] != myUserName:
                resPrice = float(ad['temp_price']) + 2
                break
        resPrice = math.ceil(resPrice)
        print(f"New SELL price is - {resPrice},  {datetime.datetime.now().strftime('%H:%M:%S %d.%m')}")

        self.localBitcoinObject.sendRequest(f'/api/ad-equation/{online_buy}/', params={'price_equation': str(resPrice)
        }, method='post')

    def checkDashboardForNewContacts(self, msg, start=False):
        completedMessagesText = "Completed messages:\n"
        for contact_id in list(self.contactsDict):
            contactReq = self.localBitcoinObject.getContactInfo(contact_id)
            if contactReq['closed_at'] or contactReq['disputed_at']:
                print(f"Contact {contact_id} is closed, dict updated")
                del self.contactsDict[contact_id]
            elif self.contactsDict[contact_id]['payment_completed']:
                completedMessagesText += f"{contact_id} - {self.contactsDict[contact_id]['amount']}RUB - " + " ".join(self.contactsDict[contact_id]['buyerMessages']) + "\n"
                self.telegramBotObject.addCompletedPayment(contact_id, self.contactsDict[contact_id]['amount'], self.contactsDict[contact_id]['buyerMessages'])

        if completedMessagesText != "Completed messages:\n":
            print(completedMessagesText)
        """
        print("Completed payments:\n", " ".join([completedPayment for completedPayment in completedPayments]))
        for elem in completedPayments:
            buyerMsgs = ", ".join(completedPayments[elem]['buyerMessages'])
            print(f"{elem} - {completedPayments[elem]['amount']} RUB, msgs: {buyerMsgs}")
        """
        dashBoard = self.localBitcoinObject.sendRequest('/api/dashboard/seller/', '', 'get')
        for contact in dashBoard['contact_list']:
            contact = contact['data']
            contact_id = str(contact['contact_id'])
            paymentCompleted = contact['payment_completed_at']
            if start == True:
                self.contactsDict[contact_id] = {
                    'sentCard' : True,
                    'askedFIO': True,
                    'payment_completed' : False,
                    'buyerMessages' : [],
                    'amount' : contact['amount']
                }
                if paymentCompleted:
                    self.contactsDict[contact_id]['payment_completed'] = True
            else:
                if contact_id not in self.contactsDict:
                    self.contactsDict[contact_id] = {
                        'sentCard': False,
                        'askedFIO' : False,
                        'payment_completed': False,
                        'buyerMessages': [],
                        'amount': contact['amount']
                    }
                    postMessageRequest = self.localBitcoinObject.postMessageToContact(contact_id, msg)
                    if postMessageRequest[0] == 200:
                        self.contactsDict[contact_id]['sentCard'] = True #Changing dictionary only if message posting was succesful(code 200)
                        print('New contact: ', contact_id)
                if paymentCompleted:
                    self.contactsDict[contact_id]['payment_completed'] = True

                    #Get user's mesggages and ask for FIO if needed
                    messageReq = self.localBitcoinObject.getContactMessages(contact_id)
                    messages = messageReq['message_list']
                    self.contactsDict[contact_id]['buyerMessages'] = [msg['msg'] for msg in messages if msg['sender']['username'] != myUserName]
                    if not self.contactsDict[contact_id]['askedFIO'] and len(self.contactsDict[contact_id]['buyerMessages']) == 0:
                        #There could be better way of determining if user sent his name
                        if self.localBitcoinObject.postMessageToContact(contact_id, message=askForFIOMessage)[0] == 200:
                            self.contactsDict[contact_id]['askedFIO'] = True #Changing dictionary only if message posting was succesful(code 200)


    def get_logger(self):
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)

        fh = logging.FileHandler("logs.log", encoding='utf-8')
        fmt = '%(asctime)s - %(threadName)s - %(levelname)s - %(message)s'
        formatter = logging.Formatter(fmt)
        fh.setFormatter(formatter)

        logger.addHandler(fh)
        return logger

    def executeAll(self, border, sberMsg, spreadDif=100000):
        self.buying(spreadDif)
        self.selling(border)
        self.checkDashboardForNewContacts(sberMsg)

    #NEW
    def buying(self, spreadDif):
        myBuyAdd = self.localBitcoinObject.getAdInfo(online_buy)
        myLimits = [float(myBuyAdd['min_amount']), float(myBuyAdd['max_amount'])]
        sell_Ads = self.getListOfSellAdsPrices(adsAmount=5)
        buy_Ads = self.getListOfBuyAds(myLimits)
        self.countGoodPriceForBUY(sell_Ads, buy_Ads, spreadDif=spreadDif, minDif=50000)

    #Developing
    def selling(self, border):
        ads = requests.get(self.localBitcoinObject.baseurl + '/buy-bitcoins-online/sberbank/.json')
        while int(ads.status_code) != 200:
            print("Couldn't get ads. Code:", ads.status_code, ads.text, "trying to get ads again...")
            time.sleep(1)
            ads = requests.get(self.localBitcoinObject.baseurl + '/buy-bitcoins-online/sberbank/.json')
        js = json.loads(ads.text)['data']['ad_list']
        myPrice = 0
        for ad in js:
            ad = ad['data']
            if ad['min_amount'] is None or ad['max_amount_available'] is None:
                continue
            min_amount = float(ad['min_amount'])
            max_amount = float(ad['max_amount_available'])
            temp_price = float(ad['temp_price'])
            username = ad['profile']['username']
            if username == myUserName:
                myPrice = temp_price
                continue
            elif min_amount <= 2500 and max_amount >= 5000 and '+' in ad['profile']['trade_count'] and username not in invisibleList and temp_price > border:
                if myPrice < temp_price and temp_price - myPrice == 2:
                    break
                logger.debug(f"{username} - {temp_price}")
                newPrice = str(temp_price - 2)
                logger.debug(f"New SELL price is {newPrice}, before user {username}")
                print(f"New SELL price is - {newPrice}, before user {username}, minLim = {str(min_amount)}, maxLim = {str(max_amount)}  {datetime.datetime.now().strftime('%H:%M:%S %d.%m')}")
                self.localBitcoinObject.sendRequest(f'/api/ad-equation/{online_sell}/', params={'price_equation' : newPrice}, method='post')
                break

    def scanning(self):
        buyAds = self.getListOfBuyAds()[0:5]
        sellAds = self.getListOfSellAdsPrices(3)
        buyAdsPrices = [float(x['temp_price']) for x in buyAds]

        buyAverage = round(sum(buyAdsPrices) / len(buyAdsPrices))
        sellAverage = round(sum(sellAds) / len(sellAds))
        curDifference = sellAverage - buyAverage
        print(f'{datetime.datetime.now().strftime("%d.%m %H:%M:%S")} Scanning localbitcoins: ... {curDifference}')
        if curDifference > 195000:
            winsound.MessageBeep()

    def chooseWorkType(self):   #User input function to define type of work
        pass

"""main"""
if __name__ == "__main__":
    localbitcoinsBot = LocalBitcoinBot(LocalBitcoin(key, secret), TelegramBot(tokens.telegramBotToken, tokens.telegramChatID, LocalBitcoin(key, secret)))
    spreadNeeded = False
    sellBorderNeeded = False
    cardMessageNeeded = False
    #Get worktype
    while True:
        workType = input("ENTER WORKTYPE ( " + " / ".join(localbitcoinsBot.workTypes) + " ): ".lower())
        if workType in localbitcoinsBot.workTypes:
            spreadNeeded = workType == 'all' or workType == 'buy'
            sellBorderNeeded = workType == 'all' or workType == 'sell'
            cardMessageNeeded = workType == 'all' or workType == 'sell' or workType == 'contacts'
            break
    #Card choose
    if cardMessageNeeded:
        #Card on which noney will come
        while True:
            cardHolder = input("ENTER CARD on which money will come ( " + " / ".join(localbitcoinsBot.cardHolders)  + " ): ").lower()
            if cardHolder in localbitcoinsBot.cardHolders:
                if cardHolder == 'me': sberMessage = ruslanSberCardMessage
                elif cardHolder == 'ayrat': sberMessage = ayratSberCardMessage
                elif cardHolder == 'mom': sberMessage = momSberCardMessage
                elif cardHolder == 'almir': sberMessage = almirSberCardMessage
                break
    #BUY spread
    if spreadNeeded: curSpread = int(input("ENTER SPREAD DIFFERENCE: "))
    #SELL border
    if sellBorderNeeded: sellBorder = int(input("ENTER SELL BORDER: "))
    logger = localbitcoinsBot.get_logger()
    while True:
        try:
            localbitcoinsBot.telegramBotObject.updater.start_polling()
            with open('logs.log', 'w'): pass #Clearing log file
            workTime = 80000000
            if cardMessageNeeded: localbitcoinsBot.checkDashboardForNewContacts(sberMessage, start=True)
            while time.time() < time.time() + workTime:
                if workType == 'all': localbitcoinsBot.executeAll(border=sellBorder, sberMsg=sberMessage, spreadDif=curSpread)
                elif workType == 'contacts': localbitcoinsBot.checkDashboardForNewContacts(sberMessage)
                elif workType == 'sell':
                    localbitcoinsBot.selling(sellBorder)
                    localbitcoinsBot.checkDashboardForNewContacts(sberMessage)
                elif workType == 'buy': localbitcoinsBot.buying(curSpread)
                elif workType == "scanning": localbitcoinsBot.scanning()
        except Exception as exc:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            print(f"Some shit happened at  {datetime.datetime.now().strftime('%d.%m %H:%M:%S')}  restarting after 5 sec...")
            print(exc)
            traceback.print_exception(exc_type, exc_value, exc_traceback, limit=2, file=sys.stdout)
            time.sleep(5)
