from localbits.main import key, secret
from localbits.localbitcoins import LocalBitcoin
import time, datetime

lclbit = LocalBitcoin(key, secret)

if __name__ == '__main__':
    while True:
        try:
            contactsToRelease = set(input("Input contacts to release:\n").split())
            for contact in contactsToRelease:
                st_code = lclbit.contactRelease(contact)[0]
                if st_code == 200:
                    print("Contact {0} released at".format(contact), datetime.datetime.now().strftime('%H:%M:%S %d.%m'))
                    time.sleep(1)
        except Exception as exc:
            print(exc)
            print("Restarting release function, check if contacts IDs are valid!")
