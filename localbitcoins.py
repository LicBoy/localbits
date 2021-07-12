import hmac
import json
import urllib
import hashlib
import requests
import time
from datetime import datetime

class LocalBitcoin:
    baseurl = 'https://localbitcoins.fi'

    def __init__(self, hmac_auth_key, hmac_auth_secret, debug=False):
        self.hmac_auth_key = hmac_auth_key
        self.hmac_auth_secret = hmac_auth_secret
        self.debug = debug

    """
    Returns public user profile information
    """

    def getAccountInfo(self, username):
        return self.sendRequest('/api/account_info/' + username + '/', '', 'get')

    """
    Return the information of the currently logged in user (the owner of authentication token).
    """

    def getMyself(self):
        return self.sendRequest('/api/myself/', '', 'get')

    """
    Checks the given PIN code against the user's currently active PIN code.
    You can use this method to ensure the person using the session is the legitimate user.
    """

    def checkPinCode(self, code):
        return self.sendRequest('/api/pincode/', {'code': code}, 'post')

    """
    Return open and active contacts
    """

    def getDashboard(self):
        return self.sendRequest('/api/dashboard/', '', 'get')

    """
    Return released (successful) contacts
    """

    def getDashboardReleased(self):
        return self.sendRequest('/api/dashboard/released/', '', 'get')

    """
    Return canceled contacts
    """

    def getDashboardCanceled(self):
        return self.sendRequest('/api/dashboard/canceled/', '', 'get')

    """
    Return closed contacts, both released and canceled
    """

    def getDashboardClosed(self):
        return self.sendRequest('/api/dashboard/closed/', '', 'get')

    """
    Releases the escrow of contact specified by ID {contact_id}.
    On success there's a complimentary message on the data key.
    """

    def contactRelease(self, contact_id):
        endpoint = f'/api/contact_release/{contact_id}/'
        return self.sendRequest(endpoint, '', 'post')

    """
    Releases the escrow of contact specified by ID {contact_id}.
    On success there's a complimentary message on the data key.
    """

    def contactReleasePin(self, contact_id, pincode):
        return self.sendRequest('/api/contact_release_pin/' + contact_id + '/', {'pincode': pincode}, 'post')

    """
    Reads all messaging from the contact. Messages are on the message_list key.
    On success there's a complimentary message on the data key.
    attachment_* fields exist only if there is an attachment.
    """

    def getContactMessages(self, contact_id):
        return self.sendRequest('/api/contact_messages/' + contact_id + '/', '', 'get')

    """
    Marks a contact as paid.
    It is recommended to access this API through /api/online_buy_contacts/ entries' action key.
    """

    def markContactAsPaid(self, contact_id):
        return self.sendRequest('/api/contact_mark_as_paid/' + contact_id + '/', '', 'get')

    """
    Post a message to contact
    """

    def postMessageToContact(self, contact_id, message):
        return self.sendRequest('/api/contact_message_post/' + contact_id + '/', {'msg': message}, 'post')

    """
    Starts a dispute with the contact, if possible.
    You can provide a short description using topic. This helps support to deal with the problem.
    """

    def startDispute(self, contact_id, topic=None):
        topic = ''
        if topic != None:
            topic = {'topic': topic}
        return self.sendRequest('/api/contact_dispute/' + contact_id + '/', topic, 'post')

    """
    Cancels the contact, if possible
    """

    def cancelContact(self, contact_id):
        return self.sendRequest('/api/contact_cancel/' + contact_id + '/', '', 'post')

    """
    Attempts to fund an unfunded local contact from the seller's wallet.
    """

    def fundContact(self, contact_id):
        return self.sendRequest('/api/contact_fund/' + contact_id + '/', '', 'post')

    """
    Attempts to create a contact to trade bitcoins.
    Amount is a number in the advertisement's fiat currency.
    Returns the API URL to the newly created contact at actions.contact_url.
    Whether the contact was able to be funded automatically is indicated at data.funded.
    Only non-floating LOCAL_SELL may return unfunded, all other trade types either fund or fail.
    """

    def createContact(self, contact_id, ammount, message=None):
        post = ''
        if message == None:
            post = {'ammount': ammount}
        else:
            post = {'ammount': ammount, 'message': message}
        return self.sendRequest('/api/contact_create/' + contact_id + '/', post, 'post')

    """
    Gets information about a single contact you are involved in. Same fields as in /api/contacts/.
    """

    def getContactInfo(self, contact_id):
        return self.sendRequest('/api/contact_info/' + contact_id + '/', '', 'get')

    """
    Contacts is a comma-separated list of contact IDs that you want to access in bulk.
    The token owner needs to be either a buyer or seller in the contacts, contacts that do not pass this check are simply not returned.
    A maximum of 50 contacts can be requested at a time.
    The contacts are not returned in any particular order.
    """

    def getContactsInfo(self, contacts):
        contacts = ','.join(contacts)
        return self.sendRequest('/api/contact_info/', {'contacts': contacts}, 'get')['contact_list']

    """
    Returns maximum of 50 newest trade messages.
    Messages are ordered by sending time, and the newest one is first.
    The list has same format as /api/contact_messages/, but each message has also contact_id field.
    Optional parameter "after" shows messages after a specific date. It takes UTC date in ISO 8601 format.
    """

    def getRecentMessages(self, after = None):
        params = ''
        if after is not None:
            params = {'after': after}
        return self.sendRequest('/api/recent_messages/', params, 'get')

    """
    Gives feedback to user.
    Possible feedback values are: trust, positive, neutral, block, block_without_feedback as strings.
    You may also set feedback message field with few exceptions.
    Feedback block_without_feedback clears the message and with block the message is mandatory.
    """

    def postFeedbackToUser(self, username, feedback, msg=None):
        if feedback not in ['trust', 'positive', 'neutral', 'block', 'block_without_feedback']:
            raise ValueError(
                f"Haven't found feedback of type {feedback}! Check feedbacks in API.")
        post = {'feedback': feedback}
        if msg != None:
            post = {'feedback': feedback, 'msg': msg}

        return self.sendRequest(f'/api/feedback/{username}/', post, 'post')

    """
    Gets information about the token owner's wallet balance.
    """

    def getWallet(self):
        return self.sendRequest('/api/wallet/', '', 'get')

    """
    Same as /api/wallet/ above, but only returns the message, receiving_address_list and total fields.
    (There's also a receiving_address_count but it is always 1: only the latest receiving address is ever returned by this call.)
    Use this instead if you don't care about transactions at the moment.
    """

    def getWalletBalance(self):
        return self.sendRequest('/api/wallet-balance/', '', 'get')

    """
    Sends amount bitcoins from the token owner's wallet to address.
    Note that this API requires its own API permission called Money.
    On success, this API returns just a message indicating success.
    It is highly recommended to minimize the lifetime of access tokens with the money permission.
    Call /api/logout/ to make the current token expire instantly.
    """

    def walletSend(self, ammount, address):
        return self.sendRequest('/api/wallet-send/', {'ammount': ammount, 'address': address}, 'post')

    """
    As above, but needs the token owner's active PIN code to succeed.
    Look before you leap. You can check if a PIN code is valid without attempting a send with /api/pincode/.
    Security concern: To get any security beyond the above API, do not retain the PIN code beyond a reasonable user session, a few minutes at most.
    If you are planning to save the PIN code anyway, please save some headache and get the real no-pin-required money permission instead.
    """

    def walletSendWithPin(self, ammount, address, pincode):
        return self.sendRequest('/api/wallet-send-pin/', {'ammount': ammount, 'address': address, 'pincode': pincode},
                                'post')

    """
    Gets an unused receiving address for the token owner's wallet, its address given in the address key of the response.
    Note that this API may keep returning the same (unused) address if called repeatedly.
    """

    def getWalletAddress(self):
        return self.sendRequest('/api/wallet-addr/', '', 'post')

    """
    Expires the current access token immediately.
    To get a new token afterwards, public apps will need to reauthenticate,
    confidential apps can turn in a refresh token.
    """

    def logout(self):
        return self.sendRequest('/api/logout/', '', 'post')

    """
    Lists the token owner's all ads on the data key ad_list, optionally filtered.
    If there's a lot of ads, the listing will be paginated.
    Refer to the ad editing pages for the field meanings. List item structure is like so:
    """

    def getAllAds(self, visible : bool = None, trade_type : str = None, currency : str = None, countrycode : str = None):
        paramsDict = {}
        if visible is not None: paramsDict['visible'] = visible
        if trade_type is not None: paramsDict['trade_type'] = trade_type
        if currency is not None: paramsDict['currency'] = currency
        if countrycode is not None: paramsDict['countrycode'] = visible
        return self.sendRequest('/api/ads/', paramsDict, 'get')

    """
    Returns all advertisements from a comma-separated list of ad IDs. 
    Invalid advertisement ID's are ignored and no error is returned. 
    Otherwise it functions the same as /api/ad-get/{ad_id}/.
    """

    def getSeveralAds(self, adsList: list):
        adsArgs = ",".join(adsList)
        return self.sendRequest(endpoint='/api/ad-get/', params={'ads' : adsArgs}, method='get')['ad_list']

    """
    Get info about one AD, specifying or not Fields, which you want to get.
    If fields parameter is empty, all fields are returned.
    Use a request parameter of fields, which is a comma-separated list of field names.
    Only those fields will be returned in the data.
    """

    def getAdInfo(self, adID, adFields: list = None):
        params = {}
        if adFields is not None:
            adFields = ",".join(adFields)
            params = {'fields' : adFields}
        return self.sendRequest(endpoint=f'/api/ad-get/{adID}/',
                                params=params,
                                method='get')['ad_list'][0]['data']

    """
    Get info about several ads, which are contained in first List argument with specifying fields parameter.
    Fields are contained in second List parameter.
    """

    def getFieldsOfSeveralAds(self, adsList : list, fieldsList : list):
        adsArgs = ",".join(adsList)
        fieldsArgs = ",".join(fieldsList)
        return self.sendRequest(endpoint='/api/ad-get/', params={'ads' : adsArgs, 'fields' : fieldsArgs}, method='get')

    """
    Switch ad on or off.
    """

    def switchAd(self, adID, status : bool):
        adInfo = self.getAdInfo(adID, ['trade_type', 'visible', 'price_equation', 'lat', 'lon', 'countrycode',
                                'max_amount', 'msg', 'track_max_amount'])
        trackMaxAmount = False
        if adInfo['trade_type'] == 'ONLINE_BUY':
            trackMaxAmount = True
        if adInfo['visible'] == status:
            return (-1, f'Ad is already has status {status}')
        else:
            adNewParams = { 'visible' : status,
                            'price_equation': adInfo['price_equation'],
                            'lat': adInfo['lat'],
                            'lon': adInfo['lon'],
                            'countrycode': adInfo['countrycode'],
                            'max_amount': int(float(adInfo['max_amount'])),
                            'msg': adInfo['msg'],
                            'track_max_amount': trackMaxAmount,
                            'require_trade_volume' : 0.0} #Field against scammers
            return self.sendRequest(f'/api/ad/{adID}/', adNewParams, 'post')

    def changeAdField(self, ad_ID: str, **fieldsDict):
        adInfo = self.getAdInfo(ad_ID, ['trade_type', 'visible', 'price_equation', 'lat', 'lon', 'countrycode',
                                       'max_amount', 'msg', 'track_max_amount'])
        trackMaxAmount = False
        if adInfo['trade_type'] == 'ONLINE_BUY':
            trackMaxAmount = True
        adNewParams = {'visible': adInfo['visible'],
                       'price_equation': adInfo['price_equation'],
                       'lat': adInfo['lat'],
                       'lon': adInfo['lon'],
                       'countrycode': adInfo['countrycode'],
                       'max_amount': int(float(adInfo['max_amount'])),
                       'msg': adInfo['msg'],
                       'track_max_amount': trackMaxAmount,
                       'require_trade_volume': 0.0}  # Field against scammers
        for key, value in fieldsDict.items():
            adNewParams[key] = value
        return self.sendRequest(f'/api/ad/{ad_ID}/', adNewParams, 'post')

    def returnAdsWithTime(self, adsType: str, bankName: str) -> tuple:
        if adsType not in ['sell', 'buy']:
            raise ValueError(f"Haven't found ad type with value {adsType}!\nCheck that you return ads correctly!")
        if bankName not in ['sberbank', 'tinkoff', 'bank-vtb-vtb', 'alfa-bank']:
            raise ValueError(f"Haven't found bank name with value {adsType}!\nCheck that you return ads correctly!")
        ads = self.sendRequest(endpoint=f'/{adsType}-bitcoins-online/{bankName}/.json',
                               params='',
                               method='get')['ad_list']
        return (ads, time.time())

    """
    Base function of making requests with needed encoded info:
    Apiauth-Key: HMAC authentication key that you got when you created your HMAC authentication from the Apps dashboard.
    Apiauth-Nonce: A unique number given with each API request. It's value needs to be greater with each API request.
    Apiauth-Signature: Your API request signed with your HMAC secret that you got when you create your HMAC authentication from the Apps dashboard.
    """

    def sendRequest(self, endpoint, params, method):    #Base function
        time.sleep(3)
        params_encoded = ''
        if params != '':
            params_encoded = urllib.parse.urlencode(params)

        now = datetime.utcnow()
        epoch = datetime.utcfromtimestamp(0)
        delta = now - epoch
        nonce = round((delta.total_seconds()) * 1000)

        message = str(nonce) + self.hmac_auth_key + endpoint + params_encoded
        message_bytes = message.encode('utf-8')
        signature = hmac.new(self.hmac_auth_secret.encode('utf-8'), msg=message_bytes, digestmod=hashlib.sha256).hexdigest().upper()

        headers = {}
        headers['Apiauth-key'] = self.hmac_auth_key
        headers['Apiauth-Nonce'] = str(nonce)
        headers['Apiauth-Signature'] = signature

        if method == 'get':
            response = requests.get(self.baseurl + endpoint, headers=headers, params=params_encoded)
            if response.status_code == 200:
                js = response.json()
                if 'data' in js:
                    return js['data']
            else:
                js = json.loads(response.text)
                print(datetime.now().strftime("%d.%m %H:%M:%S"), endpoint, "GET ERROR, waiting 5sec...", '\n', response.text, "\n", js)
                time.sleep(5)
                return self.sendRequest(endpoint, params, 'get')
        elif method == 'post':
            response = requests.post(self.baseurl + endpoint, headers=headers, data=params)
            if response.status_code != 200:
                js = response.json()
            #Different errors need different solutuions
                print(datetime.now().strftime("%d.%m %H:%M:%S"), endpoint, f"POST ERROR, wating 15sec\n{js}")
                print(response.status_code, response.text)
                #CONTACTS RELEASE ERRORS
                if js['error']['message'] == "This is not a valid and releasable contact" and js['error']['error_code'] == 6:
                    # If contact is not releasable: contact is already released or contact is closed somehow else
                    print(f"{endpoint} can't be released, wrong ID or already released.")
                else:
                    time.sleep(15)
                    return self.sendRequest(endpoint, params, 'post')
            return (response.status_code, response.text)