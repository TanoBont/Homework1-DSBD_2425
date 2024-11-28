import threading
import time
import yfinance as yf
import pytz
from database import SessionLocal, User, StockData
from datetime import datetime


class CircuitBreaker:
    def __init__(self, max_failures=5, reset_time=20, exception=Exception):
        self.max_failures = max_failures
        self.reset_time = reset_time
        self.exception = exception
        self.nFailures = 0
        self.state = 'CLOSED'
        self.last_failure_time = None  
        self.lock = threading.Lock()

    def fetch_stock_values(self, tickers):
        """Effettua una chiamata a Yahoo Finance per ogni ticker unico."""
        values = {}
        for ticker in tickers:
            try:
                data = yf.Ticker(ticker)
                last_price = data.fast_info['lastPrice']
                values[ticker] = last_price
            except Exception as e:
                print(f"Errore durante il recupero del ticker {ticker}: {e}")
                values[ticker] = None
        return values

    def update_stock_data(self):
        """Aggiorna i dati azionari per ciascun utente."""
        session = SessionLocal()
        users = session.query(User).all()

        # Ottieni i ticker unici
        tickers = set(user.ticker for user in users)

        with self.lock:
            if self.state == 'OPEN':
                time_since_failure = time.time() - self.last_failure_time
                if time_since_failure > self.reset_time:
                    self.state = 'HALF_OPEN'
                else:
                    raise CircuitBreakerOpenException("Circuito aperto, chiamata negata.")

            try:
                # Recupera i valori dei ticker unici
                ticker_values = self.fetch_stock_values(tickers)
            except self.exception as e:
                self.nFailures += 1
                self.last_failure_time = time.time()
                if self.nFailures >= self.max_failures:
                    self.state = 'OPEN'
                raise e

            # Reset del circuito dopo una chiamata riuscita in stato HALF_OPEN
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
                self.nFailures = 0

            # Aggiorna il database per ogni utente
            for user in users:
                value = ticker_values.get(user.ticker)
                if value is not None:
                    stock_data = StockData(
                        user_id=user.id,
                        ticker=user.ticker,
                        value=value,
                        timestamp=datetime.now()
                    )
                    session.add(stock_data)
                    print(f"Aggiornato il dato di {user.email} per {user.ticker}: {value}")
                else:
                    print(f"Nessun dato disponibile per {user.ticker}.")
            session.commit()
            session.close()


circuit_breaker = CircuitBreaker()


class CircuitBreakerOpenException(Exception):
    pass


def stock_market_open():
    #Verifica se il mercato è aperto (EU, Rome).
    time_zone = pytz.timezone('Europe/Rome')
    current_time = datetime.now(time_zone)
    
    if current_time.weekday() >= 5:
        return False
    
    # Orari di apertura del mercato (9:30 - 16:00)
    market_open = current_time.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = current_time.replace(hour=16, minute=0, second=0, microsecond=0)
    
    return market_open <= current_time <= market_close


if __name__ == '__main__':
    while True:
        if stock_market_open():
            try:
                circuit_breaker.update_stock_data()
            except CircuitBreakerOpenException as e:
                print(e)
        else:
            print("Mercato Azionario chiuso. Nessun Aggiornamento Eseguito.")
        time.sleep(150)
        
