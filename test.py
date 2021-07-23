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
askForFIOMessage = 'фио?'

#IGNORE this users
ignoreList = ['Nikitakomp7', 'Ellenna', 'DmitriiGrom']                  #They usually invisible on BUY page
botsList = ['13_drunk_soul_13', 'Klaik', 'Slonya', 'DmitriiGrom']        #They are bots on SELL page
invisibleList = ['erikdar7777']
lastUsedFloat = 0

"""
Base class for running bot
"""
class LocalBitcoinBot:
    def __init__(self, localBitcoinObject : LocalBitcoin, telegramBotObject : TelegramBot):
        self.localBitcoinObject = localBitcoinObject
        self.telegramBotObject = telegramBotObject

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
    def getListOfBuyAds(self, amount: int = 5) -> list: #returns list of dictionaried ads
        ads = self.telegramBotObject.returnRecentAds(adsType='sell', bankName='sberbank')
        if len(ads) < amount:
            amount = len(ads)
        for ad in ads[0:amount]:
            logger.debug(f"BUY AD: {ad['temp_price']} RUB | {ad['min_amount']} - {ad['max_amount_available']} | {ad['profile']['username']}")
        return ads[0:amount]

    #Get ads from online_sell category, U SELL HERE
    def getListOfSellAds(self, adsAmount: int = 7) -> list: #returns list of dictionaried ads
        ads = self.telegramBotObject.returnRecentAds(adsType='buy', bankName='sberbank')
        if len(ads) < adsAmount:
            adsAmount = len(ads)
        for ad in ads[0:adsAmount]:
            logger.debug(f"SELL AD: {ad['temp_price']} RUB | {ad['min_amount']} - {ad['max_amount_available']} | {ad['profile']['username']}")
        return ads[0:adsAmount]

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

    def buying(self, spreadDif):
        sell_Ads = self.getListOfSellAds(adsAmount=3)
        buy_Ads = self.getListOfBuyAds(amount=5)
        resPrice = self.countGoodPriceForBUY(sell_Ads, buy_Ads, spreadDif=spreadDif, minDif=40000)
        print(f"{datetime.datetime.now().strftime('%d.%m %H:%M:%S')} NEW BUY price is {resPrice}!")
        self.localBitcoinObject.sendRequest(f'/api/ad-equation/{online_buy}/', params={'price_equation': str(resPrice)
                                                                                       }, method='post')
    def selling(self, border):
        ads = self.telegramBotObject.returnRecentAds(adsType='buy', bankName='sberbank')
        myPrice = 0
        for ad in ads:
            if ad['max_amount_available'] is None:
                continue
            min_amount = 0
            if ad['min_amount'] is None:
                min_amount = 0
            else:
                min_amount = float(ad['min_amount'])
            max_amount = float(ad['max_amount_available'])
            temp_price = float(ad['temp_price'])
            username = ad['profile']['username']
            if username == myUserName:
                myPrice = temp_price
                continue
            elif min_amount <= 3550 and max_amount >= 4875 and username not in invisibleList and temp_price > border:
                if myPrice < temp_price and temp_price - myPrice == 2:
                    break
                logger.debug(f"{username} - {temp_price}")
                newPrice = str(temp_price - 2)
                logger.debug(f"New SELL price is {newPrice}, before user {username}")
                print(f"New SELL price is - {newPrice}, before user {username}, minLim = {str(min_amount)}, maxLim = {str(max_amount)}  {datetime.datetime.now().strftime('%H:%M:%S %d.%m')}")
                self.localBitcoinObject.sendRequest(f'/api/ad-equation/{online_sell}/', params={'price_equation' : newPrice}, method='post')
                break

    def scanning(self):
        buyAds = self.getListOfBuyAds(5)
        sellAds = self.getListOfSellAds(3)
        buyAdsPrices = [float(x['temp_price']) for x in buyAds]
        sellAdsPrices = [float(x['temp_price']) for x in sellAds]

        buyAverage = round(sum(buyAdsPrices) / len(buyAdsPrices))
        sellAverage = round(sum(sellAdsPrices) / len(sellAdsPrices))
        curDifference = sellAverage - buyAverage
        if self.waitedToPrint(time.time()):
            if curDifference > 120000:
                winsound.MessageBeep()
            print(f'{datetime.datetime.now().strftime("%d.%m %H:%M:%S")} Scanning localbitcoins: ... {curDifference}')


if __name__ == "__main__":
    localbitcoinsBot = LocalBitcoinBot(LocalBitcoin(key, secret), TelegramBot(tokens.telegramBotToken, tokens.telegramChatID, LocalBitcoin(key, secret)))
    logger = localbitcoinsBot.get_logger()
    with open('logs.log', 'w'):
        pass  # Clearing log file
    localbitcoinsBot.telegramBotObject.worksDictionary['scan']['status'] = True
    while True:
        try:
            localbitcoinsBot.telegramBotObject.updater.start_polling()
            localbitcoinsBot.telegramBotObject.checkDashboardForNewContacts(
                localbitcoinsBot.telegramBotObject.worksDictionary['sell']['cardOwner']['cardMessage'], start=True)
            while True:
                for workKey in localbitcoinsBot.telegramBotObject.worksDictionary.keys():
                    if localbitcoinsBot.telegramBotObject.worksDictionary[workKey]['status'] == True:
                        if workKey == 'sell':
                            localbitcoinsBot.selling(localbitcoinsBot.telegramBotObject.worksDictionary['sell']['sellBorder'])
                            localbitcoinsBot.telegramBotObject.checkDashboardForNewContacts(localbitcoinsBot.telegramBotObject.worksDictionary['sell']['cardOwner']['cardMessage'])
                        elif workKey == 'buy':
                            localbitcoinsBot.buying(localbitcoinsBot.telegramBotObject.worksDictionary['buy']['buyDifference'])
                        elif workKey == 'scan':
                            localbitcoinsBot.scanning()
        except json.decoder.JSONDecodeError as jsonError:
            print(
                f"JSON decode error happened {datetime.datetime.now().strftime('%d.%m %H:%M:%S')}, retrying in 10 sec...\n", jsonError)
            time.sleep(10)
        except Exception as exc:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            localbitcoinsBot.telegramBotObject.sendBotErrorMessage(f"LocalBot Error happened at  {datetime.datetime.now().strftime('%d.%m %H:%M:%S')}  restarting after 5 sec...")
            print(f"Some shit happened at  {datetime.datetime.now().strftime('%d.%m %H:%M:%S')}  restarting after 5 sec...\n", exc)
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=sys.stdout)
            time.sleep(5)
