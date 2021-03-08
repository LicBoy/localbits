from localbits.localbitcoins import LocalBitcoin
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
ignoreList = ['Nikitakomp7', 'Ellenna', 'DmitriiGrom']      #They usually invisible on BUY page
botsList = ['13_drunk_soul_13', 'Klaik', 'Slonya', 'DmitriiGrom']        #They are bots on SELL page
scanningShitList = ['DmitriiGrom']

def checkForBankNamesRegularExpression(bank_name):
    reSearchSber = re.search(regExpSber, bank_name)
    reSearchTink = re.search(regExpTink, bank_name)
    reSearchAlpha = re.search(regExpAlpha, bank_name)
    reSearchVtb = re.search(regExpVTB, bank_name)
    reSearchRoket = re.search(regExpRoket, bank_name)
    reSearchRaif = re.search(regExpRaif, bank_name)
    return (reSearchSber and not reSearchVtb and not reSearchAlpha and not reSearchRoket and not reSearchTink and not reSearchRaif)

#Get ads from online_buy category, U BUY HERE
def getListOfBuyAds(myLimits=[10000, 50000]): #returns list of ads dictionary
    req = requests.get(lclbit.baseurl + '/sell-bitcoins-online/sberbank/.json')
    while int(req.status_code) != 200:
        req = requests.get(lclbit.baseurl + '/sell-bitcoins-online/sberbank/.json')
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
def getListOfSellAdsPrices(adsAmount = 7): #returns list of float prices
    n = adsAmount
    vals = []
    req = requests.get(lclbit.baseurl + '/buy-bitcoins-online/sberbank/.json')
    while int(req.status_code != 200):
        req = requests.get(lclbit.baseurl + '/buy-bitcoins-online/sberbank/.json')
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
                #print(bank_name, temp_price)
                vals.append(temp_price)
                n-=1
            else:
                return vals
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
    logger.debug(f"Calculated medprice = {medPrice}, disp = {disp}")
    resPrice = medPrice + disp - spreadDif
    if sellPrices[0] - resPrice < minDif:
        resPrice = sellPrices[0] - minDif

    for ad in buyPrices:
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
    sell_Ads = getListOfSellAdsPrices(adsAmount=5)
    buy_Ads = getListOfBuyAds(myLimits)
    countGoodPriceForBUY(sell_Ads, buy_Ads, spreadDif=spreadDif, minDif=19500)

#Developing
def selling(border):
    ads = requests.get(lclbit.baseurl + '/buy-bitcoins-online/sberbank/.json')
    st_code = ads.status_code
    while int(st_code) != 200:
        print("Couldn't get ads. Code:", ads.status_code, ads.text, "trying to get ads again...")
        time.sleep(1)
        ads = requests.get(lclbit.baseurl + '/buy-bitcoins-online/sberbank/.json')
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
        elif min_amount <= 1500 and max_amount >= 5000 and '+' in ad['profile']['trade_count'] and username not in botsList and temp_price > border:
            if myPrice < temp_price and temp_price - myPrice == 2:
                break
            logger.debug(f"{username} - {temp_price}")
            newPrice = str(temp_price - 2)
            logger.debug(f"New SELL price is {newPrice}, before user {username}")
            print(
                f"New SELL price is - {newPrice}, before user {username}, minLim = {str(min_amount)}, maxLim = {str(max_amount)}")
            lclbit.sendRequest(f'/api/ad-equation/{online_sell}/', params={'price_equation' : newPrice}, method='post')
            break

def scanning():
    buyAds = getListOfBuyAds()[0:5]
    sellAds = getListOfSellAdsPrices(5)
    buyAdsPrices = [float(x['temp_price']) for x in buyAds]

    buyAverage = round(sum(buyAdsPrices) / len(buyAdsPrices))
    sellAverage = round(sum(sellAds) / len(sellAds))
    curDifference = sellAverage - buyAverage
    print(f'{datetime.datetime.now().strftime("%d.%m %H:%M:%S")} Scanning localbitcoins: ... {curDifference}')
    if curDifference > 105000:
        winsound.MessageBeep()

def chooseWorkType():   #User input function to define type of work
    pass

"""main"""
newContacts = set()
paymentCompletedList = set()
buyerMessages = {}
cardHolders = ['me', 'mom', 'almir', 'ayrat']
workTypes = ['all', 'contacts', 'selling', 'scanning']
if __name__ == "__main__":
    #Needed spread
    curSpread = int(input("ENTER SPREAD DIFFERENCE: "))

    #Card on which noney will come
    while True:
        cardHolder = input("ENTER CARD on which money will come ( " + " / ".join(cardHolders)  + " ): ").lower()
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

    #Get worktype
    while True:
        workType = input("ENTER WORKTYPE ( " + " / ".join(workTypes) + " ): ".lower())
        if workType in workTypes:
            break

    logger = get_logger()
    while True:
        try:
            with open('logs.log', 'w'): pass #Clearing log file
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
                sellBorder = float(input("Sell border: "))
                while time.time() < time.time() + workTime:
                    selling(sellBorder)
                    time.sleep(1)
                    checkDashboardForNewContacts(sberMessage)
                    time.sleep(2)
            elif workType == "scanning":
                while time.time() < time.time() + workTime:
                    scanning()
                    checkDashboardForNewContacts(sberMessage)
            else: print("NO SUCH FUNCTION")
        except Exception as exc:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            print(f"Some shit happened at  {datetime.datetime.now().strftime('%d.%m %H:%M:%S')}  restarting after 5 sec...")
            print(exc)
            traceback.print_exception(exc_type, exc_value, exc_traceback, limit=2, file=sys.stdout)
            time.sleep(5)
