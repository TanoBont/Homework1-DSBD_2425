import re
import time
import grpc
import hashlib
import dsbd_pb2
import dsbd_pb2_grpc

# Variabile globale per tenere traccia dell'utente loggato
logged_in_email = None

def calculate_message_id(email, ticker=None):
    """ Calcola l'ID univoco del messaggio."""
    if ticker:
        return hashlib.sha256((email + ticker).encode()).hexdigest()
    return hashlib.sha256(email.encode()).hexdigest()

def validate_email(email):
    """Verifica se l'indirizzo email è valido."""
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(email_regex, email) is not None

def validate_ticker(ticker):
    """Verifica se il ticker è valido (solo caratteri alfanumerici, max 5)."""
    ticker_regex = r'^[A-Za-z0-9]{1,5}$'
    return re.match(ticker_regex, ticker) is not None

def login(stub):
    """Gestisce il login dell'utente e aggiorna logged_in_email."""
    global logged_in_email
    email = input("Inserisci l'email per il login: ")
    if not validate_email(email):
        print("Formato email non valido, per favore riprova.")
        return None

    # Effettua la richiesta di login al server
    response = stub.LoginUser(dsbd_pb2.LoginUserRequest(email=email))
    if response.success:
        logged_in_email = email
        print(f"Login effettuato con successo per l'utente: {logged_in_email}")
        return email
    else:
        print("Login fallito:", response.message)
        return None

def register_user(stub):
    """Registra un nuovo utente con email e ticker."""
    email = input("Inserisci email: ")
    if not validate_email(email):
        print("Formato email non valido, per favore riprova.")
        return

    ticker = input("Insert Ticker: ")
    if not validate_ticker(ticker):
        print("Formato ticker non valido, deve essere composto da 1 a 5 caratteri alfanumerici.")
        return 

    message_id = calculate_message_id(email)
    response = stub.RegisterUser(dsbd_pb2.RegisterUserRequest(email=email, ticker=ticker, message_id=message_id))
    print("RegisterUser:", response.message)

def logout():
    """Effettua il logout e azzera la variabile logged_in_email."""
    global logged_in_email
    if logged_in_email:
        print(f"Logout effettuato da: {logged_in_email}")
        logged_in_email = None
    else:
        print("Nessun utente ha effettuato il login al momento.")

def main_menu():
    """Mostra il menu principale per login e registrazione."""
    print("\n=== Main Menu ===")
    print("1. Login")
    print("2. Registrazione")
    print("3. Esci")

def user_menu():
    """Mostra il menu per gli utenti loggati."""
    print("\n=== User Menu ===")
    print("1. Aggiorna ticker")
    print("2. Elimina utente e dati")
    print("3. Vedi ultimo valore del ticker")
    print("4. Vedi la media degli ultimi X valori del ticker")
    print("5. Logout")

def run():
    """Gestisce l'intera esecuzione dell'applicazione."""
    global logged_in_email

    with grpc.insecure_channel('localhost:18072') as channel:
        stub = dsbd_pb2_grpc.DSBDServiceStub(channel)

        while True:
            if not logged_in_email:
                # Mostra il menu principale per login e registrazione
                main_menu()
                selection = input("Seleziona cosa fare: ")
                if selection == '1':  # Login
                    login(stub)
                elif selection == '2':  # Register
                    register_user(stub)
                elif selection == '3':  # Exit
                    print("Arrivederci!")
                    break
                else:
                    print("Hai selezionato un'opzione non valida!")
            else:
                # Mostra il menu per gli utenti loggati
                user_menu()
                selection = input("Seleziona cosa fare: ")
                if selection == '1':  # Update user
                    new_ticker = input("Inserisci il nuovo ticker: ")
                    if not validate_ticker(new_ticker):
                        print("Formato ticker non valido, deve essere composto da 1 a 5 caratteri alfanumerici.")
                        continue

                    message_id = calculate_message_id(logged_in_email, new_ticker)
                    response = stub.UpdateUser(dsbd_pb2.UpdateUserRequest(email=logged_in_email, ticker=new_ticker, message_id=message_id))
                    print("UpdateUser:", response.message)
                elif selection == '2':  # Delete user
                    response = stub.DeleteUser(dsbd_pb2.DeleteUserRequest(email=logged_in_email))
                    print("DeleteUser:", response.message)
                    logout()
                elif selection == '3':  # Get last stock value
                    response = stub.GetTickerValue(dsbd_pb2.GetTickerRequest(email=logged_in_email))
                    print("LastStockValue:", response.value if response.success else response.message)
                elif selection == '4':  # Get average stock value
                    try:
                        nValues = int(input("Quanti valori devo considerare per la media? "))
                    except ValueError:
                        print("Numero non valido, per favore inserisci un intero positivo.")
                        continue

                    response = stub.GetTickerAverage(dsbd_pb2.GetTickerAverageRequest(email=logged_in_email, lastXValues=nValues))
                    print("AverageStockValue:", response.value if response.success else response.message)
                elif selection == '5':  # Logout
                    logout()
                else:
                    print("Hai selezionato un'opzione non valida!!")

if __name__ == '__main__':
    run()
