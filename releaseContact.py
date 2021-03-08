from localbits.main import key, secret
from localbits.localbitcoins import LocalBitcoin
import time, datetime

lclbit = LocalBitcoin(key, secret)

if __name__ == '__main__':
    while True:
        contactsToRelease = set(input("Input contacts to release:\n").split())
        for contact in contactsToRelease:
            lclbit.contactReleaseNew(contact)
            print("Contact {0} released at".format(contact), datetime.datetime.now().strftime('%d.%m %H:%M:%S'))
            time.sleep(1)
