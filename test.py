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
online_buy = tokens.online_buy          #YOU BUY HERE
online_sell = tokens.online_sell        #YOU SELL HERE
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
VALID_ADS_TYPES = {'buy', 'sell'}
ADS_LIVE_TIME = 10.0
lastUsedFloat = 0

"""
Base class for running bot
"""
class LocalBitcoinBot:
    def __init__(self, localBitcoinObject : LocalBitcoin, telegramBotObject : TelegramBot):
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
    def getListOfBuyAds(self, myLimits=[10000, 50000]) -> list: #returns list of dictionaried ads
        ads = self.returnRecentAds('buy')
        vals = []
        for ad in ads:
            ad = ad['data']
            if ad['min_amount'] is None or ad['max_amount_available'] is None:
                continue

            #min_amount = float(ad['min_amount'])
            max_amount = float(ad['max_amount_available'])
            username = ad['profile']['username']
            if max_amount > myLimits[0] and username not in ignoreList: #can be improved
                vals.append(ad)
        return vals

    #Get ads from online_sell category, U SELL HERE
    def getListOfSellAds(self, adsAmount = 7) -> list: #returns list of dictionaried ads
        n = adsAmount
        vals = []
        ads = self.returnRecentAds('sell')
        for ad in ads:
            ad = ad['data']
            if ad['min_amount'] is None or ad['max_amount_available'] is None:
                continue

            min_amount = float(ad['min_amount'])
            max_amount_available = float(ad['max_amount_available'])
            username = ad['profile']['username']
            if min_amount <= 2560 and max_amount_available >= 3768 and username not in botsList:
                if n > 0:
                    vals.append(ad)
                    n -= 1
                else: break
        #Return top n or less amount of ads from 1st page
        return vals

    def countGoodPriceForBUY(self, sellAds : list, buyAds : list, spreadDif=100000, minDif=50000):
        medPrice = 0; disp = 0
        sellAdsPrices = [float(ad['temp_price']) for ad in sellAds]
        amount = len(sellAdsPrices)
        for price in sellAdsPrices:
            medPrice += price
        medPrice = medPrice / amount
        for price in sellAdsPrices:
            disp += (price - medPrice) ** 2
        disp = disp / amount
        disp = math.sqrt(disp)

        #print(medPrice, disp)
        logger.debug(f"Calculated medprice = {medPrice}, disp = {disp}")
        resPrice = medPrice + disp - spreadDif
        if sellAdsPrices[0] - resPrice < minDif:
            resPrice = sellAdsPrices[0] - minDif

        for ad in buyAds:
            if float(ad['temp_price']) < resPrice and ad['profile']['username'] != myUserName:
                resPrice = float(ad['temp_price']) + 2
                break
        resPrice = math.ceil(resPrice)
        return resPrice

    def checkDashboardForNewContacts(self, msg, start=False):
        if msg == 'me': msg = ruslanSberCardMessage
        elif msg == 'mom': msg = momSberCardMessage
        elif msg == 'ayrat': msg = ayratSberCardMessage

        hasCompletedPayment = False
        completedMessagesText = "Completed payments:\n"
        for contact_id in list(self.contactsDict):
            contactReq = self.localBitcoinObject.getContactInfo(contact_id)
            if contactReq['closed_at'] or contactReq['disputed_at']:
                print(f"Contact {contact_id} is closed, dict updated")
                del self.contactsDict[contact_id]
            elif self.contactsDict[contact_id]['payment_completed']:
                hasCompletedPayment = True
                completedMessagesText += f"{contact_id} - {self.contactsDict[contact_id]['amount']}RUB - " + " ".join(self.contactsDict[contact_id]['buyerMessages']) + "\n"
                self.telegramBotObject.addCompletedPayment(contact_id, self.contactsDict[contact_id]['amount'], self.contactsDict[contact_id]['buyerMessages'])
        if not hasCompletedPayment:
            self.telegramBotObject.releaseDict = {}
            self.telegramBotObject.contactsRegex = r'(^All$)|'

        if completedMessagesText != "Completed payments:\n":
            print(completedMessagesText)

        dashBoard = self.localBitcoinObject.sendRequest('/api/dashboard/seller/', '', 'get')
        for contact in dashBoard['contact_list']:
            contact = contact['data']
            contact_id = str(contact['contact_id'])
            paymentCompleted = contact['payment_completed_at']
            if not contact['disputed_at']:
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

    def returnRecentAds(self, adsType : str):
        if adsType not in VALID_ADS_TYPES:
            raise ValueError(f"Haven't found VALID worktype with value {adsType}!\nCheck that you return ads correctly!")
        curTime = time.time()
        printAmount = 10
        if adsType == 'buy':
            recentBuyAdsWithTime = self.telegramBotObject.recentBuyAdsWithTime
            if recentBuyAdsWithTime[1] is None or curTime - recentBuyAdsWithTime[1] > ADS_LIVE_TIME:
                response = requests.get(self.localBitcoinObject.baseurl + '/sell-bitcoins-online/sberbank/.json')
                while int(response.status_code) != 200:
                    response = requests.get(self.localBitcoinObject.baseurl + '/sell-bitcoins-online/sberbank/.json')
                ads = response.json()['data']['ad_list']
                for ad in ads:
                    ad = ad['data']
                    if printAmount > 0:
                        logger.debug(f"BUY: {ad['profile']['username']} : {ad['temp_price']} | {ad['min_amount']}-{ad['max_amount_available']}")
                        printAmount -= 1
                    else: break
                curTime = time.time()
                #print(f"{time.strftime('%d.%m %H:%M:%S')} Updated the recent BUY ads")
                self.telegramBotObject.recentBuyAdsWithTime = (ads, curTime)
            return self.telegramBotObject.recentBuyAdsWithTime[0]
        else:
            recentSellAdsWithTime = self.telegramBotObject.recentSellAdsWithTime
            if recentSellAdsWithTime[1] is None or curTime - recentSellAdsWithTime[1] > ADS_LIVE_TIME:
                response = requests.get(self.localBitcoinObject.baseurl + '/buy-bitcoins-online/sberbank/.json')
                while int(response.status_code) != 200:
                    response = requests.get(self.localBitcoinObject.baseurl + '/buy-bitcoins-online/sberbank/.json')
                ads = response.json()['data']['ad_list']
                for ad in ads:
                    ad = ad['data']
                    if ad['min_amount'] is None or ad['max_amount_available'] is None:
                        continue
                    if float(ad['min_amount']) <= 2560 and float(ad['max_amount_available']) >= 3768 and ad['profile']['username'] not in botsList:
                        if printAmount > 0:
                            logger.debug(f"SELL: {ad['profile']['username']} : {ad['temp_price']} | {ad['min_amount']}-{ad['max_amount_available']}")
                            printAmount -= 1
                        else: break
                curTime = time.time()
                #print(f"{time.strftime('%d.%m %H:%M:%S')} Updated the recent SELL ads")
                self.telegramBotObject.recentSellAdsWithTime = (ads, curTime)
            return self.telegramBotObject.recentSellAdsWithTime[0]

    def waitedToPrint(self, lastCall:float):
        global lastUsedFloat
        if lastCall != lastUsedFloat:
            lastUsedFloat = lastCall
            return True
        return False

    def get_logger(self):
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)

        fh = logging.FileHandler("logs.log", encoding='utf-8')
        fmt = '%(asctime)s - %(threadName)s - %(levelname)s - %(message)s'
        formatter = logging.Formatter(fmt)
        fh.setFormatter(formatter)

        logger.addHandler(fh)
        return logger

    #NEW
    def buying(self, spreadDif):
        myBuyAdd = self.localBitcoinObject.getAdInfo(online_buy)
        myLimits = [float(myBuyAdd['min_amount']), float(myBuyAdd['max_amount'])]
        sell_Ads = self.getListOfSellAds(adsAmount=5)
        buy_Ads = self.getListOfBuyAds(myLimits)
        resPrice = self.countGoodPriceForBUY(sell_Ads, buy_Ads, spreadDif=spreadDif, minDif=50000)
        print(f"{datetime.datetime.now().strftime('%d.%m %H:%M:%S')} NEW BUY price is {resPrice}!")
        self.localBitcoinObject.sendRequest(f'/api/ad-equation/{online_buy}/', params={'price_equation': str(resPrice)
                                                                                       }, method='post')

    #Developing
    def selling(self, border):
        ads = self.returnRecentAds('sell')
        myPrice = 0
        for ad in ads:
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
            elif min_amount <= 3100 and max_amount >= 4001 and username not in invisibleList and temp_price > border:
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
        sellAds = self.getListOfSellAds(3)
        buyAdsPrices = [float(x['temp_price']) for x in buyAds]
        sellAdsPrices = [float(x['temp_price']) for x in sellAds]

        buyAverage = round(sum(buyAdsPrices) / len(buyAdsPrices))
        sellAverage = round(sum(sellAdsPrices) / len(sellAdsPrices))
        curDifference = sellAverage - buyAverage
        if self.waitedToPrint(self.telegramBotObject.recentBuyAdsWithTime[1]):
            if curDifference > 120000:
                winsound.MessageBeep()
            print(f'{datetime.datetime.now().strftime("%d.%m %H:%M:%S")} Scanning localbitcoins: ... {curDifference}')

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
        if workType == 'idle':
            break
        elif workType in localbitcoinsBot.telegramBotObject.worksDictionary.keys():
            localbitcoinsBot.telegramBotObject.worksDictionary[workType]['status'] = True
            spreadNeeded = workType == 'all' or workType == 'buy'
            sellBorderNeeded = workType == 'all' or workType == 'sell'
            cardMessageNeeded = workType == 'all' or workType == 'sell' or workType == 'contacts'
            break
    if not workType == 'idle':
        #Card choose
        if cardMessageNeeded:
            #Card on which noney will come
            while True:
                cardHolder = input("ENTER CARD on which money will come ( " + " / ".join(localbitcoinsBot.cardHolders)  + " ): ").lower()
                if cardHolder in localbitcoinsBot.cardHolders:
                    if cardHolder == 'me':
                        sberMessage = ruslanSberCardMessage
                        localbitcoinsBot.telegramBotObject.worksDictionary['sell']['cardMessage'] = 'me'
                    elif cardHolder == 'ayrat':
                        sberMessage = ayratSberCardMessage
                        localbitcoinsBot.telegramBotObject.worksDictionary['sell']['cardMessage'] = 'ayrat'
                    elif cardHolder == 'mom':
                        sberMessage = momSberCardMessage
                        localbitcoinsBot.telegramBotObject.worksDictionary['sell']['cardMessage'] = 'mom'
                    elif cardHolder == 'almir':
                        sberMessage = almirSberCardMessage
                    break
        #BUY spread
        if spreadNeeded:
            curSpread = int(input("ENTER SPREAD DIFFERENCE: "))
            localbitcoinsBot.telegramBotObject.worksDictionary['buy']['buyDifference'] = curSpread
        #SELL border
        if sellBorderNeeded:
            sellBorder = int(input("ENTER SELL BORDER: "))
            localbitcoinsBot.telegramBotObject.worksDictionary['sell']['sellBorder'] = sellBorder
    logger = localbitcoinsBot.get_logger()
    while True:
        try:
            #localbitcoinsBot.telegramBotObject.updater.start_polling()
            with open('logs.log', 'w'): pass #Clearing log file
            if cardMessageNeeded:
                localbitcoinsBot.checkDashboardForNewContacts(localbitcoinsBot.telegramBotObject.worksDictionary['sell']['cardMessage'], start=True)
            while True:
                for workKey in localbitcoinsBot.telegramBotObject.worksDictionary.keys():
                    if localbitcoinsBot.telegramBotObject.worksDictionary[workKey]['status'] == True:
                        if workKey == 'sell':
                            localbitcoinsBot.selling(localbitcoinsBot.telegramBotObject.worksDictionary['sell']['sellBorder'])
                            localbitcoinsBot.checkDashboardForNewContacts(localbitcoinsBot.telegramBotObject.worksDictionary['sell']['cardMessage'])
                        elif workKey == 'buy':
                            localbitcoinsBot.buying(localbitcoinsBot.telegramBotObject.worksDictionary['buy']['buyDifference'])
                        elif workKey == 'scanning':
                            localbitcoinsBot.scanning()
        except Exception as exc:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            localbitcoinsBot.telegramBotObject.sendBotErrorMessage(f"LocalBot Error happened at  {datetime.datetime.now().strftime('%d.%m %H:%M:%S')}  restarting after 5 sec...")
            print(f"Some shit happened at  {datetime.datetime.now().strftime('%d.%m %H:%M:%S')}  restarting after 5 sec...\n", exc)
            traceback.print_exception(exc_type, exc_value, exc_traceback, limit=2, file=sys.stdout)
            time.sleep(5)
