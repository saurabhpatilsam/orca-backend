import math
from enum import Enum

import requests

from app.utils.logging_setup import logger


chat_id = "-1002458621237"  # Replace with your chat ID
BOT_TOKEN = "8107668849:AAFKJF8FrJHTf5jkkX6TJJeqqvPVvt5NDwg"
ORCAMAX_H_CHAT_ID = "-1002458621237"


# use 'Markdown' or 'HTML' if you want to format the text
class MESSAGE_TYPE(Enum):
    Markdown = "Markdown"
    HTML = "HTML"


class TradeNotifierMixin:
    instrument_name: str
    account_name: str
    account_balance: float
    starting_balance: float
    win_trades: int
    lost_trades: int
    total_trades: int
    unique_id: str
    MODE: str
    api_endpoint = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    def send(self, full_message: str, msg_type=MESSAGE_TYPE.HTML.value):
        payload = {
            "chat_id": ORCAMAX_H_CHAT_ID,
            "text": full_message,
            "parse_mode": msg_type,
        }

        response = requests.post(self.api_endpoint, json=payload)

        if response.status_code == 200:
            print("Message sent successfully!")
        else:
            print(f"Failed to send message. Error: {response.text}")

    def get_account_info(self) -> list:
        message_text = [
            f"<b>{self.instrument_name} on {self.account_name} </b>",
            f"Balance: <code> {self.account_balance} </code>",
            f"So Far: <code> {self.account_balance - self.starting_balance} </code> ",
            f"Trades: <code>{self.total_trades} <b>W: {self.win_trades} L: {self.lost_trades}</b></code> ",
        ]
        return message_text

    def notify_profit(self, action, profit, flipped=False, flip_to: str = None):
        action_emoji = "💚" if action == ActionTypes.BUY.value else "♥️"
        message_text: list = [
            f"<b>✅ {self.run_symbol} {self.MODE} - {action_emoji}{action} {self.run_symbol}✅</b>",
            f"<b>ID: {self.unique_id} </b>",
            f"<b>Profit: </b><code>💰 ${math.ceil(profit)} 💰 </code>",
        ]
        message_text.extend(self.get_account_info())

        if flipped:
            if flip_to:
                message_text.insert(1, f"<b>🔄 Flipped: {flip_to} 🔄</b>")
            else:
                message_text.insert(1, f"<b>🔄 Flipped 🔄</b>")

        full_message = "\n".join(message_text)
        self.send(full_message)  # Await the send coroutine
        logger.debug("notify_profit sent")

    def notify_lost(self, action, lost, flipped=False, flip_to: str = None):
        action_emoji = "💚" if action == ActionTypes.BUY.value else "♥️"
        message_text = [
            f"<b>🔴{self.run_symbol} {self.MODE} - {action_emoji}{action}{self.run_symbol}🔴</b>",
            f"<b>ID: {self.unique_id} - {self.run_symbol} </b>",
            f"<b>Lost: </b><code>${math.ceil(lost)}</code>",
        ]
        message_text.extend(self.get_account_info())

        if flipped:
            if flip_to:
                message_text.insert(1, f"<b>🔄 Flipped to: {flip_to} 🔄</b>")
            else:
                message_text.insert(1, f"<b>🔄 Flipped 🔄</b>")

        full_message = "\n".join(message_text)
        self.send(full_message)  # Await the send coroutine
        logger.debug("notify_lost sent")

    def profit_reached(self):
        message_text = [
            f"<b>✅ 💰💰💰💰💰💰💰💰 ✅ ID: {self.unique_id}</b>",
            f"<b>{self.instrument_name} on {self.account_name} </b>",
            f"Balance: <code>{self.account_balance}</code>",
            f"<b> OrcaMax Stopped </b>",
        ]

        full_message = "\n".join(message_text)
        self.send(full_message)  # Await the send coroutine
        logger.debug("profit_reached sent")

    def lost_reached(self):
        message_text = [
            f"<b>🔴 🔻🔻🔻🔻🔻🔻 🔴 ID: {self.unique_id}</b>",
            f"<b>{self.instrument_name} on {self.account_name} </b>",
            f"Balance: <code>{self.account_balance}</code>",
            f"<b> OrcaMax Stopped </b>",
        ]

        full_message = "\n".join(message_text)
        self.send(full_message)  # Await the send coroutine
        logger.debug("lost_reached sent")

    def send_error(self, error):
        message_text = [
            f"<b>⚡️ ⚡️<code> Break on {self.account_name} </code>⚡️ ⚡️</b>",
            f"<b>⚡️<code> ID: {self.unique_id} </code>⚡️</b>",
            f"<b>Error:</b> <code>{error}</code>",
        ]
        full_message = "\n".join(message_text)
        self.send(full_message)  # Await the send coroutine
        logger.debug("send_error sent")


# Example of how to use the class
def main():
    notifier = TradeNotifierMixin()
    # Set properties for the notifier instance
    notifier.instrument_name = "BTC/USD"
    notifier.account_name = "MyAccount"
    notifier.account_balance = 1000.0
    notifier.win_trades = 5
    notifier.lost_trades = 2
    notifier.total_trades = 7
    notifier.MODE = "Trading Mode"

    notifier.notify_profit("Buy", 150)
    notifier.notify_lost("Sell", 50, flipped=True)
    notifier.send_break(
        1, notifier.instrument_name, notifier.account_name, notifier.account_balance
    )


# Run the main function
if __name__ == "__main__":
    main()




