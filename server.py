import grpc
from concurrent import futures
import time
import hashlib
from dsbd_pb2 import UserResponse, TickerResponse
from dsbd_pb2_grpc import DSBDServiceServicer, add_DSBDServiceServicer_to_server
from database import SessionLocal, User, StockData, RegistrationMessage, UpdateMessage
from threading import Lock

cache_lock = Lock()

class DSBDServer(DSBDServiceServicer):
    def __init__(self):
        self.session = SessionLocal()
        # Cache per registrazioni e aggiornamenti
        self.registration_cache = {}
        self.update_cache = {}

        # Inizializza le cache all'avvio
        self._initialize_caches()

    def _initialize_caches(self):
        """Riempie le cache con i message ID delle registrazioni e degli aggiornamenti."""
        registration_ids = self.session.query(RegistrationMessage.message_id).all()
        if registration_ids:
            self.registration_cache.update({msg_id[0]: True for msg_id in registration_ids})

        update_ids = self.session.query(UpdateMessage.message_id).all()
        if update_ids:
            self.update_cache.update({msg_id[0]: True for msg_id in update_ids})

    def LoginUser(self, request, context):
        email = request.email
        if self.session.query(User).filter_by(email=email).first():
            return UserResponse(success=True, message="Login riuscito.")
        return UserResponse(success=False, message="Login fallito, assicurati di essere registrato prima di effettuare il login.")

    def RegisterUser(self, request, context):
        email = request.email
        message_id = request.message_id
        ticker = request.ticker

        with cache_lock:
            if message_id in self.registration_cache:
                return UserResponse(success=False, message="Utente già registrato, l'ID del messaggio è in cache.")

        email_hash = hashlib.sha256(email.encode()).hexdigest()

        if message_id != email_hash:
            return UserResponse(success=False, message="ID del messaggio non valido.")

        new_user = User(email=email, ticker=ticker)
        self.session.add(new_user)

        reg_message = RegistrationMessage(message_id=message_id)
        self.session.add(reg_message)

        self.session.commit()
        with cache_lock:
            self.registration_cache[message_id] = True
        return UserResponse(success=True, message="Utente registrato con successo.")

    def UpdateUser(self, request, context):
        email = request.email
        ticker = request.ticker
        message_id = request.message_id

        with cache_lock:
            if message_id in self.update_cache:
                return UserResponse(success=False, message="Update dell'utente effettuato di recente, ID messaggio in cache.")

        user = self.session.query(User).filter_by(email=email).first()
        if not user:
            return UserResponse(success=False, message="Utente non trovato.")

        email_ticker_hash = hashlib.sha256((email + ticker).encode()).hexdigest()
        if message_id != email_ticker_hash:
            return UserResponse(success=False, message="ID messaggio non valido.")

        old_message_id = hashlib.sha256((email + user.ticker).encode()).hexdigest()
        with cache_lock:
            if old_message_id in self.update_cache:
                del self.update_cache[old_message_id]
        self.session.query(UpdateMessage).filter_by(message_id=old_message_id).delete()

        self.session.query(StockData).filter_by(user_id=user.id).delete()

        user.ticker = ticker
        self.session.add(UpdateMessage(message_id=message_id))
        self.session.commit()
        with cache_lock:
            self.update_cache[message_id] = True
        return UserResponse(success=True, message="Update effettuato con successo.")

    def DeleteUser(self, request, context):
        email = request.email
        user = self.session.query(User).filter_by(email=email).first()
        if not user:
            return UserResponse(success=False, message="Utente non trovato.")

        # Calcola gli ID delle cache
        reg_message_id = hashlib.sha256(email.encode()).hexdigest()
        update_message_id = hashlib.sha256((email + user.ticker).encode()).hexdigest()

        # Rimuovi gli ID delle registrazioni e aggiornamenti
        self.session.query(RegistrationMessage).filter_by(message_id=reg_message_id).delete()
        self.session.query(UpdateMessage).filter_by(message_id=update_message_id).delete()

        self.session.query(StockData).filter_by(user_id=user.id).delete()
        self.session.delete(user)
        self.session.commit()

        # Rimuovi dalle cache
        with cache_lock:
            if reg_message_id in self.registration_cache:
                del self.registration_cache[reg_message_id]
            if update_message_id in self.update_cache:
                del self.update_cache[update_message_id]

        return UserResponse(success=True, message="Utente eliminato con successo.")

    def GetTickerValue(self, request, context):
        self.session.expire_all()

        user = self.session.query(User).filter_by(email=request.email).first()
        if not user:
            return TickerResponse(success=False, message="Utente non trovato.")

        stock_data = self.session.query(StockData).filter_by(user_id=user.id).order_by(StockData.timestamp.desc()).first()
        if not stock_data:
            return TickerResponse(success=False, message="Nessun dato trovato.")
        return TickerResponse(success=True, value=stock_data.value)

    def GetTickerAverage(self, request, context):
        self.session.expire_all()

        user = self.session.query(User).filter_by(email=request.email).first()
        if not user:
            return TickerResponse(success=False, message="Utente non trovato.")

        stock_data = self.session.query(StockData).filter_by(user_id=user.id).order_by(StockData.timestamp.desc()).limit(request.lastXValues).all()
        if not stock_data:
            return TickerResponse(success=False, message="Nessun dato trovato.")

        avg_value = sum(data.value for data in stock_data) / len(stock_data)
        return TickerResponse(success=True, value=avg_value)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    add_DSBDServiceServicer_to_server(DSBDServer(), server)
    server.add_insecure_port('[::]:18072')
    server.start()
    print("Il server è in esecuzione sulla porta 18072...")
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == '__main__':
    serve()
