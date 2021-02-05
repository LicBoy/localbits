from localbits.localbitcoins import LocalBitcoin
import requests, json
import math
import time, datetime
import logging, sys, traceback
import re

from localbits import tokens

key = tokens.key
secret = tokens.secret
online_buy = tokens.online_buy      #YOU BUY HERE
online_sell = tokens.online_sell     #YOU SELL HERE
myUserName = tokens.myUserName

lclbit = LocalBitcoin(key, secret)

#Regular expressions for Banks: Sber, Tink, Alpha, VTB, Roket, Raif
regExpSber = r'[$SCСĊⓈĆ₡℃∁ℭŠṠṢṤṦṨ][\W\d_]*[BБ6Ⓑ൫ℬḂḄḆ][\W\d_]*[EЕĖⒺĘḔḖḘḚḜẸẺẼẾỀỂỄỆῈΈἘἙἚἛἜἝ3][\W\d_]*[RPРℙⓇṖṖῬṔℛℜℝ℟ṘṚṜṞ]'
regExpTink = r'[TТ][\W\d]*[ИUI][\W\d]*[НN][\W\d]*[ЬK]'
regExpAlpha = r'[AА][\W\d]*[ЛL][\W\d]*[ЬP][\W\d]*[ФH][\W\d]*[AА]'
regExpVTB = r'[ВV][\W\d]*[TТ][\W\d]*[BБ]'
regExpRoket = r'[РRP][\W\d]*[OО][\W\d]*[КK][\W\d]*[ЕE][\W\d]*[ТT]'
regExpRaif = r'[РRP][\W\d]*[АA][\W\d]*[ЙI][\W\d]*[ФF]'

ruslanSberCardMessage = tokens.ruslanSberCardMessage
ayratSberCardMessage = tokens.ayratSberCardMessage
momSberCardMessage = tokens.momSberCardMessage
almirSberCardMessage = tokens.almirSberCardMessage
askForFIOMessage = 'фио?'

#IGNORE this users
ignoreList = ['Nikitakomp7', 'Ellenna', 'DmitriiGrom']  #They usually invisible on BUY page
botsList = ['13_drunk_soul_13', 'Klaik']                                           #They are bots on SELL page

def checkForBankNamesRegularExpression(bank_name):
    reSearchSber = re.search(regExpSber, bank_name)
    reSearchTink = re.search(regExpTink, bank_name)
    reSearchAlpha = re.search(regExpAlpha, bank_name)
    reSearchVtb = re.search(regExpVTB, bank_name)
    reSearchRoket = re.search(regExpRoket, bank_name)
    reSearchRaif = re.search(regExpRaif, bank_name)
    return (reSearchSber and not reSearchVtb and not reSearchAlpha and not reSearchRoket and not reSearchTink and not reSearchRaif)

#Get ads from online_buy category, U BUY HERE
def getListOfBuyAds(myLimits):
    req = requests.get(lclbit.baseurl + '/sell-bitcoins-online/sberbank/.json')
    while int(req.status_code) != 200:
        req = requests.get(lclbit.baseurl + '/sell-bitcoins-online/sberbank/.json')
    ads = json.loads(req.text)['data']['ad_list']
    vals = []
    for ad in ads:
        ad = ad['data']
        if ad['min_amount'] is None or ad['max_amount'] is None:
            continue

        #min_amount = float(ad['min_amount'])
        max_amount = float(ad['max_amount'])
        if max_amount > myLimits[0]: #can be improved
            vals.append(ad)
    return vals

#Get ads from online_sell category, U SELL HERE
def getListOfSellAds(adsAmount = 7):
    n = adsAmount
    vals = []
    ads = requests.get(lclbit.baseurl + '/buy-bitcoins-online/sberbank/.json')
    js = json.loads(ads.text)['data']['ad_list']
    for ad in js:
        ad = ad['data']
        if ad['min_amount'] is None or ad['max_amount'] is None:
            continue

        min_amount = float(ad['min_amount'])
        max_amount = float(ad['max_amount'])
        temp_price = float(ad['temp_price'])
        username = ad['profile']['username']
        if min_amount <= 1500 and max_amount > 2000 and '+' in ad['profile']['trade_count'] and username not in ignoreList:
            if n>0:
                #print(username, max_amount, end= " ")
                logger.debug("SELL: {1} {0}".format(str(temp_price), username))
                #print(bank_name, temp_price)
                vals.append(temp_price)
                n-=1
    #Return top 7 sell ads from 1st page
    return vals

def countGoodPriceForBUY(sellPrices, buyPrices, spreadDif=20000, minDif=18000):
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
    logger.debug("Calculated medprice = {0}, disp = {1}".format(medPrice, disp))
    resPrice = medPrice + disp - spreadDif
    if sellPrices[0] - resPrice < minDif:
        resPrice = sellPrices[0] - minDif

    for ad in buyPrices:
        logger.debug("BUY: {0}, {1}".format(ad['profile']['username'], ad['temp_price']))
        if float(ad['temp_price']) < resPrice and ad['profile']['username'] != myUserName:
            resPrice = float(ad['temp_price']) + 2
            break
    resPrice = math.ceil(resPrice)
    print("Counted price:", resPrice)
    lclbit.sendRequest('/api/ad-equation/{0}/'.format(online_buy), params={'price_equation': str(resPrice)
    }, method='post')

def checkDashboardForNewContacts(msg, start=False):
    dashBoard = lclbit.sendRequest('/api/dashboard/seller/', '', 'get')
    for contact in dashBoard['contact_list']:
        contact_id = str(contact['data']['contact_id'])
        paymentCompleted = contact['data']['payment_completed_at']
        if start == True:
            newContacts.add(contact_id)
            if paymentCompleted:
                paymentCompletedList.add(contact_id)
        else:
            if contact_id not in newContacts:
                newContacts.add(contact_id)
                print('New contact: ', contact_id)
                postMessageRequest = lclbit.postMessageToContact(contact_id, msg)
            if paymentCompleted and contact_id not in paymentCompletedList:
                paymentCompletedList.add(contact_id)
                print('Payment completed: ', contact_id)

                #Ask for FIO
                messageReq = lclbit.getContactMessages(contact_id)
                messages = messageReq['message_list']
                if len(messages) == 1:
                    lclbit.postMessageToContact(contact_id, message=askForFIOMessage)
        #newContacts = newContacts & set(dashBoard)

def paymentCompletedContactsControl():
    for contact_id in paymentCompletedList.copy():
        curContact = lclbit.sendRequest('/api/contact_info/{0}/'.format(contact_id), '', 'get')

        buyerName = curContact['buyer']['username']
        amount = curContact['amount']
        messageReq = lclbit.getContactMessages(contact_id)

        messages = messageReq['message_list']
        if contact_id in buyerMessages and buyerMessages[contact_id][3] is True:
            buyerMessages[contact_id] = [buyerName, amount, [], True]
        else:
            buyerMessages[contact_id] = [buyerName, amount, [], False]
        for msg in messages:
            if msg['sender']['username'] == buyerName:
                buyerMessages[contact_id][2].append(msg['msg'])
        buyerDidntWriteAnything = len(buyerMessages[contact_id][2]) == 0
        askedForFIO = buyerMessages[contact_id][3]
        if buyerDidntWriteAnything and not askedForFIO:
            buyerMessages[contact_id][3] = True
            lclbit.postMessageToContact(contact_id, message=askForFIOMessage)

        #Print info about new contacts
        logger.debug("Some payments are ready")
        for id, value in buyerMessages.items():
            logger.debug("{0} : {1}".format(id, value))
            print("Payment is ready", id, value)

def releaseContactInput(buyerMessages, timer = 10):
    while True:
        if len(buyerMessages) > 0:
            contactsToRelease = input("Enter ids to release:\n").split()
            for contact in contactsToRelease:
                #Release contact
                req = lclbit.contactRelease(contact)
                if int(req[0]) == 200:
                    print("{0} contact was released".format(contact))
                    logger.debug("{0} contact was released".format(contact))
                    buyerMessages.pop(contact, None)
                else:
                    print("Couldn't release contact {0} status code - {1}\nCheck id".format(contact, req[0]))
                time.sleep(3)
        time.sleep(timer)

def clearOldContactsFromList(*lists):
    for lst in list(lists):
        for contact_id in lst.copy():
            req = lclbit.sendRequest('/api/contact_info/{0}/'.format(contact_id), '', 'get')
            st_code = req[0]
            while int(st_code) != 200:
                req = lclbit.sendRequest('/api/contact_info/{0}/'.format(contact_id), '', 'get')
            if contact_id in lst and req[1]['closed_at'] is not None:
                lst.discard(contact_id)

def get_logger():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler("logs.log", encoding='utf-8')
    fmt = '%(asctime)s - %(threadName)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(fmt)
    fh.setFormatter(formatter)

    logger.addHandler(fh)
    return logger

def executeAll(spreadDif=21000):
    #Getting needed info---
    myBuyAdd = lclbit.sendRequest('/api/ad-get/{0}/'.format(online_buy), '', 'get')['ad_list'][0]['data']
    #mySellAdd = lclbit.sendRequest('/api/ad-get/{0}/'.format(online_sell), '', 'get')['ad_list'][0]['data']
    myLimits = [float(myBuyAdd['min_amount']) , float(myBuyAdd['max_amount'])]
    #---------
    sell_Ads = getListOfSellAds(adsAmount=5)
    buy_Ads = getListOfBuyAds(myLimits)
    countGoodPriceForBUY(sell_Ads, buy_Ads, spreadDif=spreadDif, minDif=19500)

#Developing
def selling():
    ads = requests.get(lclbit.baseurl + '/buy-bitcoins-online/ru/russian-federation/transfers-with-specific-bank/.json')
    st_code = ads.status_code
    while int(st_code) != 200:
        print("Couldn't get ads. Code:", ads.status_code, ads.text, "trying to get ads again...")
        time.sleep(1)
        ads = requests.get(lclbit.baseurl + '/buy-bitcoins-online/ru/russian-federation/transfers-with-specific-bank/.json')
    js = json.loads(ads.text)['data']['ad_list']
    my_price = 0
    for ad in js:
        ad = ad['data']
        if ad['min_amount'] is None or ad['max_amount'] is None:
            continue
        bank_name = ad['bank_name'].upper()
        # Check if bankName is Sberbank
        goodBankRegExp = checkForBankNamesRegularExpression(bank_name)
        min_amount = float(ad['min_amount'])
        max_amount = float(ad['max_amount'])
        temp_price = float(ad['temp_price'])
        username = ad['profile']['username']
        if goodBankRegExp:
            logger.debug("{0} - {1}".format(username, bank_name));
        if username == myUserName:
            my_price = temp_price
            continue
        elif goodBankRegExp and min_amount <= 1500 and max_amount >= 1000 and '+' in ad['profile']['trade_count'] \
                and  (my_price - temp_price == -5) and username not in botsList:
            break
        elif goodBankRegExp and min_amount <= 1500 and max_amount >= 1000 and '+' in ad['profile']['trade_count'] \
                and (my_price - temp_price != -5) and username not in botsList:
            newPrice = str(math.ceil(temp_price - 5))
            lclbit.sendRequest('/api/ad-equation/{}/'.format(online_sell), params={'price_equation' : newPrice}, method='post')
            logger.debug("New SELL price is {0}, before user {1}".format(newPrice, username))
            print("New SELL price is - {0}, before user - {1}".format(newPrice, username))
            break

"""main"""
newContacts = set()
paymentCompletedList = set()
buyerMessages = {}
cardHolders = ['me', 'mom', 'almir', 'ayrat']
workTypes = ['all', 'contacts', 'selling']
if __name__ == "__main__":
    #Needed spread
    curSpread = int(input("ENTER SPREAD DIFFERENCE: "))

    #Card on which noney will come
    while True:
        cardHolder = input("ENTER CARD on which money will come ( me / ayrat / mom / almir ) : ")
        if cardHolder in cardHolders:
            if cardHolder == 'me':
                sberMessage = ruslanSberCardMessage
            elif cardHolder == 'ayrat':
                sberMessage = ayratSberCardMessage
            elif cardHolder == 'mom':
                sberMessage = momSberCardMessage
            elif cardHolder == 'almir':
                sberMessage = almirSberCardMessage
            break

    while True:
        workType = input("ENTER WORKTYPE ( all / contacts / selling ) : ")
        if workType in workTypes:
            break

    logger = get_logger()
    while True:
        try:
            with open('logs.log', 'w'): pass
            workTime = 80000
            checkDashboardForNewContacts(sberMessage, start=True)
            if workType == 'all':
                while time.time() < time.time() + workTime:
                    executeAll(spreadDif=curSpread)
                    checkDashboardForNewContacts(sberMessage)
            elif workType == 'contacts':
                while time.time() < time.time() + workTime:
                    checkDashboardForNewContacts(sberMessage)
            elif workType == 'selling':
                while time.time() < time.time() + workTime:
                    selling()
                    time.sleep(1)
                    checkDashboardForNewContacts(sberMessage)
                    time.sleep(1)
            else: print("NO SUCH FUNCTION")
        except Exception as exc:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            print("Some shit happened at  {}  restarting after 5 sec...".format(datetime.datetime.now()))
            print(exc)
            traceback.print_exception(exc_type, exc_value, exc_traceback, limit=2, file=sys.stdout)
            time.sleep(5)
